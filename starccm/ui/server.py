"""Interfaz web local del agente STAR-CCM+ (starccm/ui).

Uso:  starccm\\.venv\\Scripts\\python -m uvicorn --app-dir starccm ui.server:app --port 8767
      (o el preview "starccm-ui" definido en .claude/launch.json de la raíz)
      starccm\\.venv\\Scripts\\python starccm\\ui\\server.py --selftest   -> prueba HTTP sin solver ni CLI

Qué hace:
  - GET  /, /app.js, /style.css        -> la página (sin build, sin frameworks)
  - GET  /api/cases                     -> casos de cases/<caso>/ (título, fecha, escenas, última fila de convergencia)
  - GET  /api/cases/{caso}              -> RESUMEN.md, lista de escenas PNG y reports/convergencia.csv como tabla
  - GET  /files/{caso}/images/{png}     -> una escena
  - GET  /api/status                    -> estado del solver: .server.json (pid, puerto, sim), minutos de
                                           inactividad, cola de agent.log, chat en curso
  - POST /api/server/stop {save}        -> server_stop del MCP (importado como módulo: este proceso corre fuera
                                           del sandbox del tool Bash, así que puede hablar con el solver)
  - POST /api/chat {message, session_id} -> lanza `claude -p` con cwd en starccm/ y el MCP «starccm» del
                                           .mcp.json de la raíz; eventos por SSE (status, init, text, tool,
                                           tool_result, ping, raw, result, error, stopped, done)
  - POST /api/chat/stop                 -> mata la CLI del chat y sus hijos
  - GET/POST /api/settings              -> dónde corre la simulación (run_where: local | server), persistido en
                                           starccm/.ui-settings.json (ignorado por git); el chat lo lleva en el prompt
  - GET  /api/tree[?refresh=1&case=]    -> árbol del .sim; cada lectura se guarda en cases/<caso>/tree.json
Errores: siempre JSON {"detail": "texto"}. Un chat a la vez; un apagado a la vez.
La UI nunca lanza el solver: eso lo hace Claude desde el chat (server_start del MCP).
"""
from __future__ import annotations

import csv
import json
import logging
import math
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
from collections import deque
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

HERE = Path(__file__).resolve().parent          # starccm/ui
ROOT = HERE.parent                              # starccm/
REPO = ROOT.parent                              # raíz del repo (.mcp.json)
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))  # surfaces.py, también cuando uvicorn carga «ui.server»
import mcp_server as scc  # noqa: E402  (no arranca nada al importar; solo lee .env)

CASES = ROOT / "cases"
AGENT_LOG = ROOT / "agent.log"
PNG_SIG = bytes([0x89]) + b"PNG\r\n\x1a\n"

log = logging.getLogger("starccm-ui")
if not log.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s starccm-ui: %(message)s", "%H:%M:%S"))
    log.addHandler(_h)
    log.setLevel(logging.INFO)
    log.propagate = False  # uvicorn pone un handler en el root: sin esto cada línea sale dos veces


class _QuietPoll(logging.Filter):
    RX = re.compile(r'"GET /(api/status|api/cases|api/progress|api/live|api/tree\?|files/|scenes/)[^"]*" (200|304)')

    def filter(self, rec: logging.LogRecord) -> bool:
        return not self.RX.search(rec.getMessage())


logging.getLogger("uvicorn.access").addFilter(_QuietPoll())

CHAT_LOCK = threading.Lock()
STOP_LOCK = threading.Lock()
CHAT_PROC: dict = {"p": None, "stopped": False}
CLAUDE_BIN = os.environ.get("STARCCM_CLAUDE_BIN") or shutil.which("claude") or "claude"
CHAT_SYSTEM = (
    "Operas desde el panel web del agente STAR-CCM+ (starccm/ui). El usuario ve a tu lado el árbol, el visor 3D, "
    "las escenas PNG, la salida en vivo y la convergencia, que se refrescan solos. Responde en español, corto, con "
    "tablas para números. Antes de escribir Java: recipe_search primero, docs_search segundo; precompila (run_java "
    "ya lo hace). Un solo servidor a la vez (server_start reutiliza el vivo); guarda con save tras cada bloque largo. "
    "Si te piden resumen, comparación o explicación, solo lees y respondes (no lances iterate ni server_start). "
    "DÓNDE CORRE: cada mensaje empieza con el caso y la ejecución elegida. Llama siempre a server_start sin where "
    "(toma la elección de la página): Local = este PC (STAR-CCM+ 2410); Servidor = Linux de vm/SERVIDOR.md "
    "(2502, 14 núcleos); en Servidor las rutas de starccm/ en tu Java se traducen solas, el CAD se sube solo y lo "
    "que escribas en cases/ vuelve solo al PC. "
    "CASO NUEVO (geometría en cases/<caso>/cad/): sigue el «Flujo estándar» de CLAUDE.md con las recetas bomba-* "
    "adaptando nombres de partes y fronteras (inspect para verlos), server_start(name=<caso>) para trabajar en "
    "sims/<caso>.sim, una operación de malla por parte, MRF con el eje y las rpm pedidas, reportes H, M, eta; itera "
    "en bloques de 100 con iterate y AÑADE una fila por bloque a cases/<caso>/reports/convergencia.csv con la "
    "cabecera iter,seconds,H,M,pt_in,pt_out,Q_in,Q_out,eta,continuity,xmom (usa Write/Edit: solo puedes escribir "
    "dentro de cases/); para hasta el criterio de CLAUDE.md. Al terminar: escenas presion_alabes, velocidad_plano, "
    "yplus, plano_vectores y malla a cases/<caso>/images/ (recetas bomba-escenas, escena-plano-vectores, "
    "escena-malla-rotor y export_scene con path), superficies con campo con la receta exportar-superficies-ensight "
    "(PATTERN «.», FUNCS «Pressure,TotalPressure,Velocity,WallYplus», OUT cases/<caso>/surfaces/_raw/superficies/"
    "superficies.case): el visor las convierte solo; y escribe cases/<caso>/RESUMEN.md (geometría, malla, física, "
    "resultados y tiempos en tablas, como cases/cursocfturbo/RESUMEN.md). Si algo falla dos veces, para y explica. "
    "Termina siempre con una línea: qué quedó hecho y qué cambió."
)


def _clean_env() -> dict[str, str]:
    """La CLI se autentica sola (llavero), no hereda la sesión anidada de Claude Code."""
    # sin STARCCM_PODKEY: el MCP la lee de sus .env; la CLI y sus tools (Read) no necesitan verla
    return {k: v for k, v in os.environ.items() if not k.startswith("CLAUDE") and k != "STARCCM_PODKEY"}


def _kill_tree(p: subprocess.Popen) -> None:
    if p.poll() is not None:  # ya terminó: su PID pudo reasignarse, no tocar nada
        return
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"], capture_output=True)
    if p.poll() is None:
        p.kill()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    scc.start_watchdog()  # el apagado por inactividad no depende de que siga vivo el MCP que arrancó el solver
    yield
    p = CHAT_PROC.get("p")
    if p and p.poll() is None:
        CHAT_PROC["stopped"] = True
        _kill_tree(p)
        log.info("apagado: chat detenido (pid %s)", p.pid)
    # el solver NO se apaga aquí: lo apaga el usuario (botón) o el watchdog del MCP


app = FastAPI(title="starccm-ui", lifespan=lifespan)


@app.exception_handler(RequestValidationError)
async def _validation(_req: Request, exc: RequestValidationError) -> JSONResponse:
    msgs = []
    for e in exc.errors():
        loc = ".".join(str(x) for x in e.get("loc", ()) if x not in ("body", "query", "path"))
        msgs.append(f"{loc}: {e.get('msg')}" if loc else str(e.get("msg")))
    return JSONResponse({"detail": "petición inválida · " + "; ".join(msgs)}, status_code=422)


@app.exception_handler(Exception)
async def _unexpected(_req: Request, exc: Exception) -> JSONResponse:
    return JSONResponse({"detail": f"error interno: {type(exc).__name__}: {exc}"}, status_code=500)


# ---------------------------------------------------------------- página
@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return (HERE / "index.html").read_text(encoding="utf-8")


@app.get("/app.js")
def app_js() -> FileResponse:
    return FileResponse(HERE / "app.js", media_type="text/javascript", headers={"Cache-Control": "no-cache"})


@app.get("/style.css")
def style_css() -> FileResponse:
    return FileResponse(HERE / "style.css", media_type="text/css", headers={"Cache-Control": "no-cache"})


# ---------------------------------------------------------------- dónde corre la simulación: Local (este PC) o Servidor (Linux)
SETTINGS_FILE = ROOT / ".ui-settings.json"   # ignorado por git; Claude puede leerlo con Read
SERVIDOR_MD = ROOT / "vm" / "SERVIDOR.md"


def _server_info() -> dict:
    """Resumen de vm/SERVIDOR.md: host del ssh y las primeras filas del inventario. Allí no hay claves."""
    info = {"host": None, "user": None, "rows": [], "label": "Servidor Linux", "version": "2502",
            "installed": True, "install": "/opt/Siemens/20.02.008-R8",  # vm/SERVIDOR.md
            "ready": True, "ssh": scc.SSH_HOST, "remote_dir": scc.REMOTE_DIR}  # mcp_server: server_start(where="server")
    if not SERVIDOR_MD.is_file():
        return info
    txt = SERVIDOR_MD.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"ssh\s+([\w.-]+)@([\d.]+)", txt)
    if m:
        info["user"], info["host"] = m.group(1), m.group(2)
    for ln in txt.splitlines():
        cells = [c.strip() for c in ln.strip().strip("|").split("|")]
        if ln.strip().startswith("|") and len(cells) == 2 and cells[0] != "dato" and cells[0].strip("-: "):
            info["rows"].append(cells)
        if len(info["rows"]) >= 6:
            break
    n = re.match(r"(\d+)\s*vCPU", dict(info["rows"]).get("CPU", ""))
    info["label"] = f"Servidor Linux ({n.group(1)} vCPU)" if n else "Servidor Linux"
    return info


def _settings() -> dict:
    try:
        d = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        d = {}
    where = d.get("run_where") if d.get("run_where") in ("local", "server") else "local"
    return {"run_where": where, "at": d.get("at"), "file": str(SETTINGS_FILE),
            "local": {"label": "Local (este PC)", "np": scc.NP, "version": "2410"}, "server": _server_info()}


class SettingsReq(BaseModel):
    run_where: Literal["local", "server"]


@app.get("/api/settings")
def api_settings() -> dict:
    return _settings()


@app.post("/api/settings")
def api_settings_set(req: SettingsReq) -> dict:
    SETTINGS_FILE.write_text(json.dumps({"run_where": req.run_where, "at": time.strftime("%Y-%m-%d %H:%M:%S")}, indent=1),
                             encoding="utf-8")
    log.info("ejecución elegida: %s", req.run_where)
    return _settings()


def _where_text() -> str:
    """Lo que el chat antepone a cada mensaje para que Claude sepa dónde debe correr."""
    s = _settings()
    if s["run_where"] == "server":
        sv = s["server"]
        tail = "remoto disponible: server_start lo lanza allí por SSH" if sv["ready"] else "remoto aún no disponible: no arranques nada allí, prepara y avisa"
        return f"ejecución elegida: {sv['label']} {sv['host'] or ''} · STAR-CCM+ {sv['version']} · {tail}".replace("  ", " ")
    return f"ejecución: Local (este PC, STAR-CCM+ {s['local']['version']}, np {s['local']['np']})"


# ---------------------------------------------------------------- casos
def _safe(name: str) -> str:
    if not name or len(name) > 100 or not re.fullmatch(r"[A-Za-z0-9_\-.]+", name) or ".." in name:
        raise HTTPException(400, "nombre inválido")
    return name


def _case_dir(name: str) -> Path:
    d = CASES / _safe(name)
    if not d.is_dir() or name.startswith(("_", ".")):
        raise HTTPException(404, f"no existe el caso {name}")
    return d


def _num(s: str):
    try:
        v = float(s)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None  # nan/inf no caben en JSON


def _convergencia(d: Path) -> dict | None:
    f = d / "reports" / "convergencia.csv"
    if not f.is_file():
        return None
    with open(f, encoding="utf-8", newline="") as fh:
        rows = list(csv.reader(fh))
    if not rows:
        return None
    cols = [c.strip() for c in rows[0]]
    data = [[_num(x) for x in r] for r in rows[1:] if r and any(x.strip() for x in r)]
    return {"columns": cols, "rows": data[-5000:], "truncated": len(data) > 5000, "file": "reports/convergencia.csv"}


def _images(d: Path) -> list[dict]:
    out = []
    for p in sorted((d / "images").glob("*.png")) if (d / "images").is_dir() else []:
        out.append({"file": p.name, "label": p.stem.replace("_", " "), "size": p.stat().st_size,
                    "mtime": int(p.stat().st_mtime)})
    return out


def _title(d: Path) -> str:
    r = d / "RESUMEN.md"
    if r.is_file():
        for line in r.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith("#"):
                return line.lstrip("#").strip()
    return d.name


def _case_row(d: Path) -> dict:
    r = d / "RESUMEN.md"
    conv = _convergencia(d)
    last = None
    if conv and conv["rows"]:
        last = dict(zip(conv["columns"], conv["rows"][-1]))
    return {"name": d.name, "title": _title(d), "has_resumen": r.is_file(),
            "date": time.strftime("%Y-%m-%d %H:%M", time.localtime(r.stat().st_mtime if r.is_file() else d.stat().st_mtime)),
            "n_images": len(_images(d)), "last": last}


@app.get("/api/cases")
def cases() -> list[dict]:
    if not CASES.is_dir():
        return []
    ds = [d for d in CASES.iterdir() if d.is_dir() and not d.name.startswith(("_", "."))]
    rows = [_case_row(d) for d in ds]
    rows.sort(key=lambda r: r["date"], reverse=True)
    return rows


@app.get("/api/cases/{name}")
def case(name: str) -> dict:
    d = _case_dir(name)
    r = d / "RESUMEN.md"
    return {**_case_row(d), "resumen": r.read_text(encoding="utf-8", errors="replace") if r.is_file() else "",
            "images": _images(d), "convergencia": _convergencia(d), "dir": str(d),
            "pump": (d / "pump.py").is_file()}


# ---------------------------------------------------------------- caso nuevo: carpeta + CAD subido desde la página
CAD_EXT = {".stp", ".step", ".x_t", ".x_b", ".igs", ".iges", ".stl", ".jt", ".sat", ".cfturbo-ccm", ".dbs", ".nas", ".msh"}
CAD_MAX = 2 * 1024 ** 3  # 2 GB por archivo


class NewCaseReq(BaseModel):
    name: str = Field(min_length=1, max_length=60, pattern=r"^[A-Za-z0-9_\-]+$")


@app.post("/api/cases/new")
def api_case_new(req: NewCaseReq) -> dict:
    """Crea cases/<nombre>/{cad,images,reports}. La IA hace el resto desde el chat."""
    d = CASES / req.name
    if d.exists():
        raise HTTPException(409, f"ya existe el caso {req.name}")
    for sub in ("cad", "images", "reports"):
        (d / sub).mkdir(parents=True)
    log.info("caso nuevo: cases/%s", req.name)
    return {"name": req.name, "dir": str(d)}


@app.put("/api/cases/{name}/cad/{fname}")
async def api_case_cad(name: str, fname: str, request: Request) -> dict:
    """Sube un archivo de geometría al cad/ del caso (cuerpo = el archivo tal cual, en trozos: sin multipart)."""
    d = _case_dir(name) / "cad"
    if not re.fullmatch(r"[A-Za-z0-9_\-. ]+", fname) or ".." in fname or not any(fname.lower().endswith(e) for e in CAD_EXT):
        raise HTTPException(400, f"archivo no admitido: usa {', '.join(sorted(CAD_EXT))}")
    if int(request.headers.get("content-length") or 0) > CAD_MAX:
        raise HTTPException(413, "archivo de más de 2 GB")
    d.mkdir(exist_ok=True)
    tmp = d / (fname + ".part")
    n = 0
    with open(tmp, "wb") as f:
        async for chunk in request.stream():
            n += len(chunk)
            if n > CAD_MAX:
                f.close(); tmp.unlink(missing_ok=True)
                raise HTTPException(413, "archivo de más de 2 GB")
            f.write(chunk)
    tmp.replace(d / fname)
    log.info("CAD subido: cases/%s/cad/%s (%d bytes)", name, fname, n)
    return {"file": f"cases/{name}/cad/{fname}", "bytes": n}


@app.get("/api/cases/{name}/cad")
def api_case_cad_list(name: str) -> dict:
    d = _case_dir(name) / "cad"
    return {"files": [{"name": f.name, "bytes": f.stat().st_size} for f in sorted(d.iterdir()) if f.is_file() and not f.name.endswith(".part")] if d.is_dir() else []}


@app.get("/files/{name}/images/{fname}")
def image(name: str, fname: str) -> FileResponse:
    d = _case_dir(name)
    if not re.fullmatch(r"[A-Za-z0-9_\-.]+\.png", fname) or ".." in fname:
        raise HTTPException(400, "archivo inválido")
    f = d / "images" / fname
    if not f.is_file():
        raise HTTPException(404, "no existe la escena")
    return FileResponse(f, media_type="image/png", headers={"Cache-Control": "private, max-age=60"})


# ---------------------------------------------------------------- en vivo: escenas exportadas del solver
SCENES_DIR = CASES / "_scenes"
SCENE_LOCK = threading.Lock()


def _png_rows(d: Path, src: str, url: str) -> list[dict]:
    if not d.is_dir():
        return []
    return [{"file": p.name, "label": p.stem.replace("_", " "), "src": src, "url": f"{url}/{p.name}",
             "mtime": int(p.stat().st_mtime), "size": p.stat().st_size} for p in d.glob("*.png")]


@app.get("/api/live")
def live(case: str | None = None) -> dict:
    """PNG exportados, los más nuevos primero: images/ del caso y cases/_scenes/ (destino por defecto de export_scene)."""
    rows = _png_rows(SCENES_DIR, "_scenes", "/scenes")
    if case:
        d = _case_dir(case)
        rows += _png_rows(d / "images", case, f"/files/{case}/images")
    rows.sort(key=lambda r: r["mtime"], reverse=True)
    return {"scenes": rows[:40]}


@app.get("/scenes/{fname}")
def scene_png(fname: str) -> FileResponse:
    if not re.fullmatch(r"[A-Za-z0-9_\-.]+\.png", fname) or ".." in fname:
        raise HTTPException(400, "archivo inválido")
    f = SCENES_DIR / fname
    if not f.is_file():
        raise HTTPException(404, "no existe la escena")
    return FileResponse(f, media_type="image/png", headers={"Cache-Control": "no-cache"})


def _solver_alive() -> bool:
    return scc.alive()  # local o remoto (por SSH, cacheado 8 s)


def _solver_busy_409() -> None:
    if not _solver_alive():
        raise HTTPException(409, "no hay solver vivo: pide a la IA que lo arranque (server_start)")
    # ponytail: el candado del MCP es por proceso; si Claude está inyectando una macro desde el chat,
    # un segundo cliente batch chocaría con la suya. Mientras el chat trabaja, no se toca el solver desde aquí.
    if CHAT_LOCK.locked():
        raise HTTPException(409, "La IA está usando el solver ahora; espera a que termine")


class SceneReq(BaseModel):
    name: str = Field(min_length=1, max_length=100, pattern=r"^[\w .\-()]+$")  # va a un literal Java
    case: str | None = Field(None, max_length=100)
    width: int = Field(1600, ge=200, le=4000)
    height: int = Field(1000, ge=200, le=4000)


@app.post("/api/scene")
def api_scene(req: SceneReq) -> dict:
    """Exporta la escena a PNG desde el solver vivo (~10 s: arranque del cliente batch)."""
    _solver_busy_409()
    if not SCENE_LOCK.acquire(blocking=False):
        raise HTTPException(409, "ya se está exportando una escena")
    try:
        path = str(_case_dir(req.case) / "images" / f"{scc._safe(req.name)}.png") if req.case else ""
        r = scc.export_scene(req.name, path, req.width, req.height)
        log.info("escena %s -> %s (%s s, ok=%s)", req.name, r.get("png"), r.get("seconds"), r.get("ok"))
        if not r.get("ok"):
            raise HTTPException(500, f"export_scene falló: {r.get('exception') or 'sin PNG'}")
        p = Path(r["png"])
        return {**r, "file": p.name, "url": (f"/files/{req.case}/images/{p.name}" if req.case else f"/scenes/{p.name}"),
                "mtime": int(p.stat().st_mtime)}
    finally:
        SCENE_LOCK.release()


@app.get("/api/scenes")
def api_scenes() -> dict:
    """Nombres de las escenas del .sim abierto (inspect('scenes'), ~10 s)."""
    _solver_busy_409()
    with SCENE_LOCK:
        r = scc.inspect("scenes")
    return {"ok": r.get("ok"), "seconds": r.get("seconds"), "names": [s["name"] for s in r.get("scene", [])],
            **({"exception": r["exception"]} if r.get("exception") else {})}


# ---------------------------------------------------------------- progreso: log del servidor y macros (la «terminal»)
def _tail_file(p: Path, nbytes: int = 24_000, nlines: int = 80) -> list[str]:
    if not p.is_file():
        return []
    with open(p, "rb") as f:
        f.seek(0, 2)
        size = f.tell()
        f.seek(max(0, size - nbytes))
        lines = f.read().decode("utf-8", "replace").splitlines()
    if size > nbytes and lines:
        lines = lines[1:]  # la primera puede venir cortada
    return [scc._redact(ln)[:400] for ln in lines[-nlines:]]


def _is_fake(p: Path) -> bool:
    """Salida del starccm+ falso del selftest (hasta el 2026-10-23 escribía en sims/ y macros/ reales)."""
    try:
        with open(p, "rb") as f:
            head = f.read(600)
        return any(m in head for m in (b"FAKE", b"<fake>", b"starccm-selftest-"))
    except OSError:
        return False


def _server_log_path() -> Path | None:
    st = scc._state()
    p = Path(st.get("log") or "")
    if p.is_file():
        return p
    logs = sorted(scc.SIMS.glob("*.server.log"), key=lambda q: q.stat().st_mtime) if scc.SIMS.is_dir() else []
    logs = [q for q in logs if not _is_fake(q)]
    return logs[-1] if logs else None


def _last_macro() -> Path | None:
    """La macro más nueva que no sea del starccm+ falso (mira como mucho las 5 últimas)."""
    macros = sorted(scc.MACROS.glob("Agent_*.java"), key=lambda q: q.stat().st_mtime) if scc.MACROS.is_dir() else []
    for m in reversed(macros[-5:]):
        o = m.with_suffix(".out")
        if not (o.is_file() and _is_fake(o)):
            return m
    return None


@app.get("/api/progress")
def progress() -> dict:
    """Cola del log del servidor de STAR-CCM+, última macro inyectada (en marcha si aún no tiene .out) y su salida."""
    lp = _server_log_path()
    out: dict = {"server_log": {"file": str(lp) if lp else None, "size": lp.stat().st_size if lp else 0,
                                "mtime": int(lp.stat().st_mtime) if lp else None, "tail": _tail_file(lp) if lp else []},
                 "agent_log": _log_tail(8), "macro": None}
    m = _last_macro()
    if m:
        o = m.with_suffix(".out")
        body = m.read_text(encoding="utf-8", errors="replace")
        i, j = body.find("try {"), body.rfind("} catch")
        core = body[i + 5:j].strip() if 0 <= i < j else body
        tail = _tail_file(o, 20_000, 80) if o.is_file() else []
        # el MCP escribe el .out en vivo: la macro sigue en marcha hasta que aparece AGENT_END (o un error del cliente)
        done = any(("AGENT_END" in ln) or ln.startswith("--- stderr") for ln in tail)
        out["macro"] = {"file": m.name, "started": int(m.stat().st_mtime), "running": not done and _solver_alive(),
                        "finished": int(o.stat().st_mtime) if (o.is_file() and done) else None,
                        "body": scc._redact(core)[:1500], "out": tail[-40:]}
    return out


# ---------------------------------------------------------------- árbol de la simulación (inspect tree, con caché)
TREE: dict = {"data": None, "at": None, "sim": None}
TREE_LOCK = threading.Lock()


def _tree_file(sim: str | None) -> Path | None:
    """cases/<caso>/tree.json (el caso se llama como el .sim); fuera de git por el patrón de cases/."""
    stem = Path(sim).stem if sim else ""
    return CASES / stem / "tree.json" if stem and (CASES / stem).is_dir() else None


def _tree_load(case: str | None) -> dict:
    f = CASES / _safe(case) / "tree.json" if case else None
    try:
        return json.loads(f.read_text(encoding="utf-8")) if f and f.is_file() else {}
    except ValueError:
        return {}


def _tree_derived(case: str | None) -> dict:
    """Árbol reconstruido SOLO con lo que hay en disco (sin solver): fronteras del manifest de superficies,
    reportes/monitores de convergencia.csv y escenas de images/. Sin regiones ni modelos (eso exige inspect tree)."""
    try:
        d = _case_dir(case) if case else None
    except HTTPException:
        d = None
    if not d:
        return {}
    data: dict = {}
    mans = sorted((d / "surfaces").glob("*/manifest.json"), key=lambda f: f.stat().st_mtime, reverse=True) if (d / "surfaces").is_dir() else []
    for f in mans[:1]:
        try:
            m = json.loads(f.read_text(encoding="utf-8"))
            data["boundary"] = [{"name": p["name"], "type": f"{p['ni'] // 3:,} triáng.".replace(",", ".")} for p in m.get("parts", []) if p.get("ni")]
        except (ValueError, KeyError, TypeError):
            pass
    conv = _convergencia(d)
    if conv:
        rep = [c for c in conv["columns"] if c not in ("iter", "seconds")]
        last = dict(zip(conv["columns"], conv["rows"][-1])) if conv["rows"] else {}
        data["report"] = [{"name": c, "type": "reporte", "value": None if last.get(c) is None else f"{last[c]:.4g}".replace(".", ",")} for c in rep]
        data["monitor"] = [{"name": c, "type": "monitor"} for c in rep]
        data["solver"] = [{"name": "iteraciones", "value": str(int(last["iter"])) if last.get("iter") is not None else "–"}]
    imgs = _images(d)
    if imgs:
        data["scene"] = [{"name": i["label"], "type": "PNG"} for i in imgs]
    if not data:
        return {}
    ref = max([f.stat().st_mtime for f in mans[:1]] + [(d / "reports" / "convergencia.csv").stat().st_mtime if conv else 0] + [i["mtime"] for i in imgs])
    return {"data": data, "at": int(ref), "sim": None, "seconds": None, "derived": True}


@app.get("/api/tree")
def api_tree(refresh: int = 0, case: str | None = None) -> dict:
    """Árbol del .sim abierto (solver, parts, regions, physics, mesh_ops, reports, monitors, scenes).
    Sin refresh devuelve la última lectura: la de memoria si es del caso pedido, si no la guardada en
    cases/<caso>/tree.json (sobrevive al reinicio de la UI y al apagado del solver). Cada lectura es una macro, ~10 s."""
    if refresh:
        _solver_busy_409()
        if not TREE_LOCK.acquire(blocking=False):
            raise HTTPException(409, "ya se está leyendo el árbol")
        try:
            r = scc.inspect("tree")
            if not r.get("ok"):
                raise HTTPException(500, f"inspect falló: {r.get('exception') or r}")
            TREE.update(data={k: v for k, v in r.items() if isinstance(v, list)}, at=int(time.time()),
                        sim=scc._state().get("sim"), seconds=r.get("seconds"))
            log.info("árbol leído: %s en %s s", {k: len(v) for k, v in TREE['data'].items()}, r.get("seconds"))
            f = _tree_file(TREE["sim"])
            if f:
                f.write_text(json.dumps(TREE, ensure_ascii=False), encoding="utf-8")
        finally:
            TREE_LOCK.release()
    t = TREE if TREE["data"] and (not case or Path(TREE["sim"] or "").stem == case) else _tree_load(case)
    if not t.get("data"):
        t = _tree_derived(case)
    return {"tree": t.get("data"), "at": t.get("at"), "sim": t.get("sim"), "seconds": t.get("seconds"),
            "alive": _solver_alive(), "from_disk": t is not TREE and bool(t.get("data")), "derived": bool(t.get("derived"))}


# ---------------------------------------------------------------- abrir la GUI de STAR-CCM+ con el .sim del caso
class GuiReq(BaseModel):
    case: str = Field(min_length=1, max_length=100)


@app.post("/api/open_gui")
def api_open_gui(req: GuiReq) -> dict:
    """Lanza la GUI de STAR-CCM+ con sims/<caso>.sim. Solo sin servidor batch vivo (dos procesos sobre el
    mismo .sim se pisan) y con la licencia de .env (PoD cobra por hora: lo confirma la página)."""
    sim = scc.SIMS / f"{_safe(req.case)}.sim"
    if not sim.is_file():
        raise HTTPException(404, f"no existe sims/{sim.name}")
    if _solver_alive():
        raise HTTPException(409, "hay un servidor batch vivo sobre este .sim: apágalo primero (Apagar solver)")
    if scc.EXE.lower().endswith(".py"):
        raise HTTPException(409, "STARCCM_EXE apunta al starccm+ falso de pruebas")
    cmd = scc._starccm_cmd() + scc._lic_flags() + [str(sim)]
    flags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS if os.name == "nt" else 0
    p = subprocess.Popen(cmd, cwd=str(scc.SIMS), creationflags=flags, stdin=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    log.info("GUI de STAR-CCM+ lanzada: pid %s · %s", p.pid, scc._redact(" ".join(cmd)))
    scc._log(f"GUI lanzada desde la UI pid={p.pid} sim={sim}")
    return {"pid": p.pid, "sim": str(sim)}


# ---------------------------------------------------------------- superficies con campo para el visor 3D
import surfaces as surf  # noqa: E402  (starccm/ui/surfaces.py: EnSight/STL -> dataset binario)

SURF_LOCK = threading.Lock()
RECIPE_ENSIGHT = scc.RECIPES / "exportar-superficies-ensight.java"


def _surf_dir(case: str) -> Path:
    return _case_dir(case) / "surfaces"


def _meta_lines(text: str) -> tuple[list[str], list[dict]]:
    """BOUNDARY y ROTFRAME (salida de la receta exportar-superficies-ensight, en stdout o en <case>.meta)."""
    bounds, rotation = [], []
    for ln in text.splitlines():
        f = ln.split("\t")
        if f[0] == "BOUNDARY" and len(f) >= 2:
            bounds.append(f[1])
        elif f[0] == "ROTFRAME" and len(f) >= 5:
            try:
                rotation.append({"region": f[1], "axis": [float(x) for x in f[2].split(",")],
                                 "origin": [float(x) for x in f[3].split(",")], "rpm": float(f[4])})
            except ValueError:
                pass
    return bounds, rotation


def _sync_raw(case: str) -> list[str]:
    """Convierte las exportaciones EnSight crudas (surfaces/_raw/<nombre>/*.case) que aún no tengan dataset o sean
    más nuevas que él: así lo que exporte la IA desde el chat aparece solo en el visor."""
    d = _surf_dir(case)
    done = []
    for cf in sorted((d / "_raw").glob("*/*.case")) if (d / "_raw").is_dir() else []:
        name = cf.parent.name
        if not re.fullmatch(r"[A-Za-z0-9_\-]+", name):
            continue
        man = d / name / "manifest.json"
        if man.is_file() and man.stat().st_mtime >= cf.stat().st_mtime:
            continue
        meta = cf.with_name(cf.name + ".meta")
        bounds, rotation = _meta_lines(meta.read_text(encoding="utf-8", errors="replace")) if meta.is_file() else ([], [])
        try:
            surf.convert_case(cf, d / name, {"boundaries": bounds, "rotation": rotation, "exported": time.strftime(
                "%Y-%m-%d %H:%M:%S", time.localtime(cf.stat().st_mtime)), "source_meta": meta.is_file()})
            done.append(name)
            log.info("superficie %s/%s convertida desde _raw (%d fronteras, %d marcos)", case, name, len(bounds), len(rotation))
        except Exception as e:  # noqa: BLE001
            log.warning("no pude convertir %s: %s", cf, e)
    return done


@app.get("/api/surfaces")
def api_surfaces(case: str) -> dict:
    """Datasets listos del caso: cases/<caso>/surfaces/<nombre>/manifest.json (antes convierte los _raw nuevos)."""
    d = _surf_dir(case)
    if not SURF_LOCK.locked():
        _sync_raw(case)
    out = []
    for m in sorted(d.glob("*/manifest.json"), key=lambda p: p.stat().st_mtime, reverse=True) if d.is_dir() else []:
        try:
            man = json.loads(m.read_text(encoding="utf-8"))
        except ValueError:
            continue
        out.append({"name": m.parent.name, "mtime": int(m.stat().st_mtime), "manifest": man,
                    "url": f"/surfaces/{case}/{m.parent.name}"})
    return {"datasets": out}


@app.get("/surfaces/{case}/{ds}/{fname}")
def surface_file(case: str, ds: str, fname: str) -> FileResponse:
    if not re.fullmatch(r"[A-Za-z0-9_\-.]+", ds) or not re.fullmatch(r"[A-Za-z0-9_\-.]+\.(f32|u32|json)", fname) or ".." in ds + fname:
        raise HTTPException(400, "ruta inválida")
    f = _surf_dir(case) / ds / fname
    if not f.is_file():
        raise HTTPException(404, "no existe")
    media = "application/json" if fname.endswith(".json") else "application/octet-stream"
    return FileResponse(f, media_type=media, headers={"Cache-Control": "private, max-age=3600"})


class SurfaceReq(BaseModel):
    case: str = Field(min_length=1, max_length=100)
    name: str = Field("superficies", min_length=1, max_length=60, pattern=r"^[A-Za-z0-9_\-]+$")
    pattern: str = Field("blade|hub|shroud|volute|wall|casing", max_length=300)   # regex sobre "region/frontera"
    funcs: str = Field("Pressure,TotalPressure,Velocity,WallYplus", max_length=300, pattern=r"^[\w ,.\-\[\]()]+$")  # field functions internas


@app.post("/api/surface")
def api_surface(req: SurfaceReq) -> dict:
    """Exporta las fronteras que casan con `pattern` (EnSight, campos en vértices) con el solver vivo y las
    convierte al dataset del visor. Tarda lo que una macro (10 s) más la exportación (segundos a minutos)."""
    _solver_busy_409()
    if not SURF_LOCK.acquire(blocking=False):
        raise HTTPException(409, "ya se está exportando una superficie")
    try:
        raw = _surf_dir(req.case) / "_raw" / req.name
        raw.mkdir(parents=True, exist_ok=True)
        case_file = raw / f"{req.name}.case"
        body = (RECIPE_ENSIGHT.read_text(encoding="utf-8")
                .replace("PATTERN", scc._jstr(req.pattern))
                .replace("FUNCS", scc._jstr(req.funcs))
                .replace("OUT", scc._jpath(case_file)))
        t0 = time.time()
        r = scc.run_java(body, timeout_s=3600)
        if not r.get("ok"):
            raise HTTPException(500, f"export falló: {r.get('exception') or r.get('stdout', '')[-500:]}")
        if not case_file.is_file():
            raise HTTPException(500, f"STAR-CCM+ no escribió {case_file.name}; salida: {r.get('stdout', '')[-500:]}")
        bounds, rotation = _meta_lines(r["stdout"])  # marcos rotatorios: el visor gira esas regiones sobre su eje real
        man = surf.convert_case(case_file, _surf_dir(req.case) / req.name,
                                {"boundaries": bounds, "rotation": rotation, "pattern": req.pattern, "funcs": req.funcs,
                                 "exported": time.strftime("%Y-%m-%d %H:%M:%S"), "seconds": round(time.time() - t0, 1)})
        log.info("superficie %s/%s: %d partes, %d triángulos, %s escalares en %.0f s", req.case, req.name,
                 len(man["parts"]), man["n_triangles"], len(man["scalars"]), time.time() - t0)
        return {"name": req.name, "url": f"/surfaces/{req.case}/{req.name}", "manifest": man, "macro_seconds": r.get("seconds")}
    finally:
        SURF_LOCK.release()


# ---------------------------------------------------------------- estado del solver
def _last_activity() -> float | None:
    """Última macro (.java/.out) o .server.json: la misma medida en disco que usa el watchdog del MCP."""
    return scc.last_activity()


def _log_tail(n: int = 12) -> list[str]:
    if not AGENT_LOG.is_file():
        return []
    with open(AGENT_LOG, "rb") as f:
        f.seek(0, 2)
        f.seek(max(0, f.tell() - 20_000))
        lines = f.read().decode("utf-8", "replace").splitlines()
    return [ln[:300] for ln in lines if "starccm-selftest-" not in ln][-n:]  # sin las líneas de selftests viejos


@app.get("/api/status")
def status() -> dict:
    st = scc._state()
    pid = st.get("pid")
    alive = scc.alive(st)
    last = _last_activity()
    return {"alive": alive, "pid": pid, "port": st.get("port"), "host": st.get("host"), "sim": st.get("sim"),
            "where": st.get("where", "local") if pid else None, "rsim": st.get("rsim"),
            "started": st.get("started"), "np": st.get("np"), "startup_seconds": st.get("startup_seconds"),
            "idle_min": round((time.time() - last) / 60, 1) if (alive and last) else None,
            "idle_limit_min": scc.IDLE_MIN, "stale": bool(pid) and not alive,
            "stopping": STOP_LOCK.locked(), "chatting": CHAT_LOCK.locked(),
            "log": _log_tail(), "claude": CLAUDE_BIN, "state_file": str(scc.STATE_FILE)}


class StopReq(BaseModel):
    save: bool = True


@app.post("/api/server/stop")
def api_server_stop(req: StopReq) -> dict:
    if CHAT_LOCK.locked():  # no inyectar saveState+kill mientras Claude tiene una macro en marcha
        raise HTTPException(409, "La IA está usando el solver; pulsa Detener en el chat primero")
    if not STOP_LOCK.acquire(blocking=False):
        raise HTTPException(409, "ya se está apagando")
    try:
        t0 = time.time()
        r = scc.server_stop(save=req.save)
        r["seconds"] = round(time.time() - t0, 1)
        log.info("solver: stop -> %s", {k: v for k, v in r.items() if k != "stdout"})
        return r
    finally:
        STOP_LOCK.release()


# ---------------------------------------------------------------- chat con Claude Code CLI
class ChatReq(BaseModel):
    message: str = Field(min_length=1, max_length=20000)
    session_id: str | None = Field(None, pattern=r"^[A-Za-z0-9-]{1,64}$")
    case: str | None = Field(None, max_length=100)


def _sse(obj: dict) -> str:
    return "data: " + json.dumps(obj, ensure_ascii=False) + "\n\n"


def _ui_using_solver() -> str | None:
    """La UI inyecta macros con el MCP de ESTE proceso; el chat lo hace con otro proceso: no deben solaparse."""
    for lock, what in ((SURF_LOCK, "exportando superficies"), (SCENE_LOCK, "exportando una escena"),
                       (TREE_LOCK, "leyendo el árbol"), (STOP_LOCK, "apagando el solver")):
        if lock.locked():
            return what
    return None


def _chat_events(req: ChatReq):
    if not CHAT_LOCK.acquire(blocking=False):
        yield _sse({"kind": "error", "text": "ya hay una conversación en curso; espera o pulsa Detener"})
        return
    busy = _ui_using_solver()
    if busy:
        CHAT_LOCK.release()
        yield _sse({"kind": "error", "text": f"la página está {busy} con el solver; espera a que termine y reenvía"})
        return
    p = None
    try:
        prompt = f"({'Caso seleccionado en el panel: cases/' + req.case + ' · ' if req.case else ''}{_where_text()})\n{req.message}"
        cmd = [CLAUDE_BIN, "-p", prompt, "--output-format", "stream-json", "--verbose",
               "--mcp-config", str(REPO / ".mcp.json"), "--strict-mcp-config",
               # escribe SOLO dentro de cases/ (RESUMEN.md, convergencia.csv); nada de shell ni red
               "--allowedTools", "mcp__starccm__*,Read,Glob,Grep,Write(cases/**),Edit(cases/**)",
               "--disallowedTools", "Bash,NotebookEdit,WebFetch,WebSearch,Read(**/.env*),Read(**/.starccm-agent.env)",
               "--append-system-prompt", CHAT_SYSTEM, "--max-turns", "250"]
        if req.session_id:
            cmd += ["--resume", req.session_id]
        try:
            p = subprocess.Popen(cmd, cwd=ROOT, env=_clean_env(), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")
        except OSError as e:
            yield _sse({"kind": "error", "text": f"no pude lanzar la CLI de Claude Code ({CLAUDE_BIN}): {e}"})
            return
        CHAT_PROC["p"] = p
        CHAT_PROC["stopped"] = False
        log.info("chat: CLI lanzada (pid %s%s)", p.pid, ", continúa sesión" if req.session_id else "")
        hidden: set[str] = set()
        q: queue.Queue = queue.Queue()
        threading.Thread(target=lambda: ([q.put(ln) for ln in p.stdout], q.put(None)), daemon=True).start()
        err_tail: deque[str] = deque(maxlen=40)
        err_thread = threading.Thread(target=lambda: [err_tail.append(ln) for ln in p.stderr], daemon=True)
        err_thread.start()
        yield _sse({"kind": "status", "text": "La IA está arrancando…"})
        t0 = time.time()
        while True:
            try:
                line = q.get(timeout=15)
            except queue.Empty:
                yield _sse({"kind": "ping", "t": round(time.time() - t0)})
                continue
            if line is None:
                break
            line = line.strip()
            if not line:
                continue
            try:
                o = json.loads(line)
            except ValueError:
                yield _sse({"kind": "raw", "text": line[:500]})
                continue
            t = o.get("type")
            if t == "system" and o.get("subtype") == "init":
                yield _sse({"kind": "init", "session_id": o.get("session_id"), "model": o.get("model"),
                            "mcp": o.get("mcp_servers")})
            elif t == "assistant":
                for b in o.get("message", {}).get("content", []):
                    if b.get("type") == "text" and b.get("text"):
                        yield _sse({"kind": "text", "text": scc._redact(b["text"])})
                    elif b.get("type") == "tool_use":
                        name = b.get("name", "")
                        if not name.startswith("mcp__starccm__"):
                            hidden.add(b.get("id", ""))
                            continue
                        yield _sse({"kind": "tool", "name": name.replace("mcp__starccm__", ""), "input": json.loads(scc._redact(json.dumps(b.get("input"))))})
            elif t == "user":
                for b in o.get("message", {}).get("content", []):
                    if isinstance(b, dict) and b.get("type") == "tool_result" and b.get("tool_use_id") not in hidden:
                        c = b.get("content")
                        txt = c if isinstance(c, str) else " ".join(x.get("text", "") for x in c if isinstance(x, dict))
                        yield _sse({"kind": "tool_result", "text": scc._redact(txt)[:800], "is_error": bool(b.get("is_error"))})
            elif t == "result":
                yield _sse({"kind": "result", "subtype": o.get("subtype"), "session_id": o.get("session_id"),
                            "turns": o.get("num_turns"), "seconds": round(time.time() - t0),
                            "text": o.get("result") if o.get("subtype") != "success" else None})
        rc = p.wait()
        err_thread.join(timeout=2)
        err = scc._redact("".join(err_tail).strip())
        log.info("chat: terminó rc=%s en %.0f s%s", rc, time.time() - t0, " (detenido)" if CHAT_PROC.get("stopped") else "")
        if CHAT_PROC.get("stopped"):
            yield _sse({"kind": "stopped", "text": "Detenido por el usuario"})
        elif rc not in (0, None) and err:
            yield _sse({"kind": "error", "text": err[-800:]})
        yield _sse({"kind": "done", "rc": rc})
    finally:
        if p is not None and p.poll() is None:
            log.info("chat: conexión cerrada con la CLI en marcha; la detengo")
            _kill_tree(p)
        CHAT_PROC["p"] = None
        CHAT_LOCK.release()


@app.post("/api/chat")
def api_chat(req: ChatReq) -> StreamingResponse:
    return StreamingResponse(_chat_events(req), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.post("/api/chat/stop")
def api_chat_stop() -> dict:
    p = CHAT_PROC["p"]
    if p and p.poll() is None:
        CHAT_PROC["stopped"] = True
        _kill_tree(p)
        log.info("chat: detenido por el usuario (pid %s)", p.pid)
        return {"stopped": True}
    return {"stopped": False}


# ---------------------------------------------------------------- selftest
def _selftest() -> int:
    """Levanta uvicorn en un puerto libre y recorre los endpoints. Sin solver, sin licencia, sin CLI."""
    import socket
    import urllib.error
    import urllib.request

    import uvicorn

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    threading.Thread(target=server.run, daemon=True).start()
    base = f"http://127.0.0.1:{port}"
    for _ in range(50):
        if scc._port_open(port):
            break
        time.sleep(0.1)
    fails: list[str] = []

    def check(cond, msg):
        print(("  ok   " if cond else "  FAIL ") + msg)
        if not cond:
            fails.append(msg)

    def get(path, raw=False):
        try:
            with urllib.request.urlopen(base + path, timeout=10) as r:
                b = r.read()
                return r.status, (b if raw else json.loads(b) if r.headers.get_content_type() == "application/json" else b.decode("utf-8", "replace"))
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read() or b"{}")

    def post(path, body):
        req = urllib.request.Request(base + path, data=json.dumps(body).encode(), headers={"content-type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read() or b"{}")

    print(f"selftest: starccm-ui en {base}")
    c, body = get("/")
    check(c == 200 and "STAR-CCM+" in body, "GET / sirve la página")
    check(get("/app.js")[0] == 200 and get("/style.css")[0] == 200, "GET /app.js y /style.css")
    check(_num("nan") is None and _num("inf") is None and _num("1.5") == 1.5, "_num descarta nan/inf (JSON no los admite)")
    c, rows = get("/api/cases")
    names = [r["name"] for r in rows] if c == 200 else []
    check(c == 200 and isinstance(rows, list), f"GET /api/cases -> {len(names)} casos {names}")
    if "cursocfturbo" in names:
        c, d = get("/api/cases/cursocfturbo")
        check(c == 200 and d["resumen"].startswith("#"), "caso cursocfturbo: RESUMEN.md")
        check(len(d["images"]) >= 3, f"caso cursocfturbo: {len(d['images'])} escenas")
        conv = d["convergencia"] or {}
        check(conv and {"iter", "H", "M"} <= set(conv["columns"]) and len(conv["rows"]) >= 1,
              f"caso cursocfturbo: convergencia {len(conv.get('rows', []))} filas")
        if d["images"]:
            c, png = get(f"/files/cursocfturbo/images/{d['images'][0]['file']}", raw=True)
            check(c == 200 and png.startswith(PNG_SIG), "GET /files/.../images/<png> es un PNG")
    nombre = "selftest_caso_tmp"
    shutil.rmtree(CASES / nombre, ignore_errors=True)
    c, r = post("/api/cases/new", {"name": nombre})
    check(c == 200 and (CASES / nombre / "cad").is_dir(), "POST /api/cases/new crea cad/, images/, reports/")
    check(post("/api/cases/new", {"name": nombre})[0] == 409, "caso repetido -> 409")
    rq = urllib.request.Request(base + f"/api/cases/{nombre}/cad/pieza.stp", data=b"ISO-10303-21;\nEND-ISO-10303-21;\n", method="PUT")
    with urllib.request.urlopen(rq, timeout=10) as rr:
        up = json.loads(rr.read())
    lst = get(f"/api/cases/{nombre}/cad")[1]
    check(up.get("bytes", 0) > 0 and [f["name"] for f in lst.get("files", [])] == ["pieza.stp"], "PUT .../cad/pieza.stp sube y se lista")
    rq = urllib.request.Request(base + f"/api/cases/{nombre}/cad/malo.exe", data=b"x", method="PUT")
    try:
        urllib.request.urlopen(rq, timeout=10); bad = 200
    except urllib.error.HTTPError as e:
        bad = e.code
    check(bad == 400, "extensión no admitida -> 400")
    shutil.rmtree(CASES / nombre, ignore_errors=True)
    c, _ = get("/api/cases/no_existe")
    check(c == 404, "caso inexistente -> 404")
    c, _ = get("/files/cursocfturbo/images/..%2F..%2FRESUMEN.md")
    check(c in (400, 404), "ruta con .. rechazada")
    c, lv = get("/api/live?case=cursocfturbo" if "cursocfturbo" in names else "/api/live")
    check(c == 200 and isinstance(lv.get("scenes"), list), f"GET /api/live -> {len(lv.get('scenes', []))} PNG")
    import array
    import tempfile
    tmp = Path(tempfile.mkdtemp(prefix="starccm-ui-ens-"))
    man = surf.convert_case(surf.write_mini_case(tmp), tmp / "out")
    yp = array.array("f")
    yp.frombytes((tmp / "out" / "WallYplus.f32").read_bytes())
    check(man["n_vertices"] == 7 and man["n_triangles"] == 3 and len(man["scalars"]) == 3, "EnSight mini -> dataset (7 vértices, 3 triángulos, 3 escalares)")
    check(list(yp) == [30.0] * 4 + [45.0] * 3, "escalar por elemento repartido a los vértices de su parte")
    shutil.rmtree(tmp, ignore_errors=True)
    c, sf = get("/api/surfaces?case=cursocfturbo" if "cursocfturbo" in names else "/api/surfaces?case=" + (names[0] if names else "x"))
    check(c in (200, 404) and (c == 404 or isinstance(sf.get("datasets"), list)), f"GET /api/surfaces -> {len(sf.get('datasets', [])) if c == 200 else c}")
    c, pg = get("/api/progress")
    check(c == 200 and "server_log" in pg and "macro" in pg, f"GET /api/progress ({len(pg.get('server_log', {}).get('tail', []))} líneas de log, macro={bool(pg.get('macro'))})")
    check("FAKE" not in json.dumps(pg), "GET /api/progress no enseña el starccm+ falso del selftest")
    c, tr = get("/api/tree")
    check(c == 200 and "tree" in tr, "GET /api/tree (caché)")
    c, tr = get("/api/tree?case=cursocfturbo")
    check(c == 200 and "from_disk" in tr, f"GET /api/tree?case=cursocfturbo (de disco={tr.get('from_disk')})")
    check(c == 200 and (tr.get("tree") is None or tr.get("derived") or tr.get("from_disk")) and (tr.get("tree") or {}).get("boundary", [1]), "árbol de disco no vacío para cursocfturbo")
    # ajustes: dónde corre la simulación (se deja como estaba)
    orig = _settings()["run_where"]
    c, sg = get("/api/settings")
    check(c == 200 and sg["run_where"] in ("local", "server") and "host" in sg["server"] and "np" in sg["local"],
          f"GET /api/settings (run_where={sg['run_where']}, servidor {sg['server'].get('host')}, {len(sg['server']['rows'])} filas de SERVIDOR.md)")
    other = "server" if orig == "local" else "local"
    c, r = post("/api/settings", {"run_where": other})
    check(c == 200 and r["run_where"] == other and get("/api/settings")[1]["run_where"] == other, f"POST /api/settings {other} y relectura")
    c, r = post("/api/settings", {"run_where": "luna"})
    check(c == 422, "POST /api/settings con valor inválido -> 422")
    check(_where_text().startswith("ejecución elegida: Servidor" if other == "server" else "ejecución: Local"), f"prefijo del chat: {_where_text()[:60]}")
    post("/api/settings", {"run_where": orig})
    c, r = post("/api/open_gui", {"case": "no_existe"})
    check(c == 404, "POST /api/open_gui con caso inexistente -> 404")
    c, st = get("/api/status")
    check(c == 200 and "alive" in st and "log" in st and "idle_limit_min" in st, f"GET /api/status (alive={st.get('alive')})")
    if st.get("alive"):
        print("  skip server/stop: hay un solver vivo de verdad; no lo toco")
    else:
        c, r = post("/api/server/stop", {"save": True})
        check(c == 200 and r.get("stopped") is False, "POST /api/server/stop sin servidor -> stopped=false")
        c, r = post("/api/scene", {"name": "presion"})
        check(c == 409 and "solver" in r.get("detail", ""), "POST /api/scene sin servidor -> 409")
        c, _ = post("/api/scene", {"name": "x\"); System.exit(0); //"})
        check(c == 422, "POST /api/scene con comillas en el nombre -> 422 (no llega al Java)")
        c, _ = post("/api/surface", {"case": "cursocfturbo", "funcs": "P\"); //"})
        check(c == 422, "POST /api/surface con comillas en funcs -> 422")
        c, r = get("/api/tree?refresh=1")
        check(c == 409, "GET /api/tree?refresh=1 sin servidor -> 409")
        c, r = post("/api/surface", {"case": names[0] if names else "x"})
        check(c in (404, 409), "POST /api/surface sin servidor -> 409")
    c, r = post("/api/chat/stop", {})
    check(c == 200 and r.get("stopped") is False, "POST /api/chat/stop sin chat -> stopped=false")
    c, r = post("/api/chat", {"message": ""})
    check(c == 422 and "detail" in r, "POST /api/chat con mensaje vacío -> 422 JSON")
    server.should_exit = True
    print(f"selftest: {len(fails)} fallos" if fails else "selftest: todo en verde")
    return 1 if fails else 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(_selftest())
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("STARCCM_UI_PORT", "8767")))
