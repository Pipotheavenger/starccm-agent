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
  - GET  /api/settings                  -> datos del solver local (versión, procesos) para la página
  - GET  /api/tree[?refresh=1&case=]    -> árbol del .sim; cada lectura se guarda en cases/<caso>/tree.json
  - GET  /api/surfaces, POST /api/surface -> datasets 3D del visor (GET convierte los _raw nuevos; POST exporta del solver)
  - POST /api/scene, GET /api/scenes    -> exportar una escena a PNG / listar las del .sim
  - POST /api/cases/new, PUT .../cad/{f} -> caso nuevo y subida de geometría; GET/POST .../roles = fronteras.json
  - GET  /api/progress, /api/live       -> salida del solver y de la última macro; PNG exportados
  - POST /api/open_gui                  -> abre la GUI de STAR-CCM+ con sims/<caso>.sim (sin solver batch vivo)
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
from starlette.requests import ClientDisconnect
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
    "El solver corre en este PC (STAR-CCM+ 2410). "
    "CASO NUEVO (geometría en cases/<caso>/cad/): sigue el «Flujo estándar» de CLAUDE.md con las recetas bomba-* "
    "adaptando nombres de partes y fronteras (inspect para verlos), server_start(name=<caso>) para trabajar en "
    "sims/<caso>.sim, una operación de malla por parte, MRF con el eje y las rpm pedidas, reportes H, M, eta; itera "
    "en bloques de 100 con iterate y AÑADE una fila por bloque a cases/<caso>/reports/convergencia.csv con la "
    "cabecera iter,seconds,H,M,pt_in,pt_out,Q_in,Q_out,eta,continuity,xmom (usa Write/Edit: solo puedes escribir "
    "dentro de cases/). ETAPAS en un caso nuevo: (1) prepara hasta tener malla, física, fronteras y reportes; (2) corre "
    "SOLO 100 iteraciones de prueba y entrega resultados completos (escenas, superficies, tabla de reportes y "
    "RESUMEN.md provisional); (3) PREGUNTA (bloque pregunta, abajo) si seguir hasta el criterio de parada, con las "
    "opciones «Seguir hasta el criterio de parada», «Cambiar algo antes» y «Parar aquí»; solo si el usuario "
    "confirma, sigue hasta el criterio de CLAUDE.md y vuelve a entregar todo. Resultados (en la etapa 2 y al final): escenas presion_alabes, velocidad_plano, "
    "yplus, plano_vectores y malla a cases/<caso>/images/ (recetas bomba-escenas, escena-plano-vectores, "
    "escena-malla-rotor y export_scene con path), superficies con campo con la receta exportar-superficies-ensight "
    "(PATTERN «.», FUNCS «Pressure,TotalPressure,Velocity,WallYplus», OUT cases/<caso>/surfaces/_raw/superficies/"
    "superficies.case): el visor las convierte solo; y escribe cases/<caso>/RESUMEN.md (geometría, malla, física, "
    "resultados y tiempos en tablas, como cases/cursocfturbo/RESUMEN.md). Si algo falla dos veces, para y explica. "
    "FRONTERAS: si existe cases/<caso>/fronteras.json es la asignación que hizo el usuario en el visor («región/frontera» → inlet | outlet | wall | interface | symmetry): úsala tal cual para los tipos de frontera, sin adivinar (inlet = mass flow inlet con el caudal pedido, outlet = pressure outlet 0 Pa). Si la geometría trae caras agrupadas o con nombres genéricos (Default, Faces, Surface…) y NO hay fronteras.json: separa las caras (receta separar-caras-por-angulo, ANGULO 89), exporta la geometría sin campos (receta exportar-superficies-ensight con PATTERN «.», FUNCS vacío y OUT cases/<caso>/surfaces/_raw/geometria/geometria.case) y PARA: pide al usuario que marque entrada y salida en el visor con el botón «Fronteras». Si la solución diverge (continuidad > 1 o creciendo), no sigas iterando: revisa fronteras y física. "
    "3D EN VIVO: antes de iterar (100 de prueba o la corrida larga) activa la exportación automática con la "
    "receta activar-autoexport (CADA 25 en la prueba de 100 iteraciones, 50 en corridas largas; FUNCS "
    "«Pressure,TotalPressure,Velocity,WallYplus»; OUT cases/<caso>/surfaces/_raw/vivo): el visor muestra el campo "
    "mientras itera, sin coste apreciable (~0,15 s por exportación). "
    "PREGUNTAR: cuando dudes (qué cara es entrada o salida, qué modelo físico, fluido, condiciones, si seguir) NO "
    "adivines: termina tu respuesta con UN bloque ```pregunta``` que contenga un JSON en una sola línea: "
    "{\"pregunta\": \"texto corto\", \"opciones\": [\"A\", \"B\", \"C\"], \"multiple\": false, \"ver\": \"…\"} "
    "y DETENTE hasta la respuesta. Las opciones son concretas (p. ej. modelos «k-omega SST», «k-epsilon realizable», "
    "«Laminar»), con tu recomendación primero y marcada «(recomendado)»; el usuario también puede escribir otra cosa. "
    "«ver» muestra al usuario lo que no tienes claro: «fronteras» abre el visor en modo Fronteras (si quieres que "
    "señale caras, añade \"caras\": [\"región/frontera\", …] con las dudosas), «escena:<archivo.png>» abre esa escena "
    "de cases/<caso>/images/ (expórtala antes), «3d» el visor, «graficos» la convergencia. Una sola pregunta por "
    "respuesta; si hay varias dudas, la más importante primero. "
    "NARRA: el usuario solo ve el chat. Antes de CADA herramienta escribe UNA frase corta (máx. 12 palabras) de "
    "qué vas a hacer y por qué; tras un resultado importante, una línea con el dato clave (celdas, H, residuo…). "
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
        subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"], capture_output=True, timeout=30)
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


# ---------------------------------------------------------------- solver local (la ejecución remota se quitó el 2026-10-24)
@app.get("/api/settings")
def api_settings() -> dict:
    return {"local": {"np": scc.NP, "version": "2410"}}


def _where_text() -> str:
    """Lo que el chat antepone a cada mensaje."""
    return f"solver: este PC, STAR-CCM+ 2410, np {scc.NP}"


# ---------------------------------------------------------------- casos
def _safe(name: str) -> str:
    if not name or len(name) > 100 or not re.fullmatch(r"[A-Za-z0-9_\-.]+", name) or ".." in name:
        raise HTTPException(400, "nombre inválido")
    return name


def _png_name(fname: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_\-.]+\.png", fname) or ".." in fname:
        raise HTTPException(400, "archivo inválido")
    return fname


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
    with open(f, encoding="utf-8-sig", errors="replace", newline="") as fh:  # BOM de Excel o bytes sueltos no tumban /api/cases
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
    rows = []
    for d in ds:
        try:
            rows.append(_case_row(d))
        except Exception as e:  # noqa: BLE001  un caso con archivos rotos no esconde a los demás
            log.warning("caso %s ilegible: %s", d.name, e)
            rows.append({"name": d.name, "title": d.name, "has_resumen": False, "date": "", "n_images": 0, "last": None})
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


WIN_RESERVED = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)), *(f"lpt{i}" for i in range(1, 10))}


class NewCaseReq(BaseModel):
    # empieza por letra o número: «_x» y «.x» los esconde /api/cases; CON, NUL… no se pueden crear en Windows
    name: str = Field(min_length=1, max_length=60, pattern=r"^[A-Za-z0-9][A-Za-z0-9_\-]*$")


@app.post("/api/cases/new")
def api_case_new(req: NewCaseReq) -> dict:
    """Crea cases/<nombre>/{cad,images,reports}. La IA hace el resto desde el chat."""
    d = CASES / req.name
    if req.name.lower() in WIN_RESERVED:
        raise HTTPException(400, f"«{req.name}» es un nombre reservado de Windows")
    # un intento anterior cortado (carpeta sin geometría ni resultados) se reanuda; uno con contenido no se pisa
    vacio = d.is_dir() and not (d / "RESUMEN.md").exists() and not (d / "reports" / "convergencia.csv").exists() \
        and not any(q.is_file() and not q.name.endswith(".part") for q in (d / "cad").glob("*"))
    if d.exists() and not vacio:
        raise HTTPException(409, f"ya existe el caso {req.name}")
    if (scc.SIMS / f"{req.name}.sim").exists():  # server_start(name) cargaría ese .sim viejo como si fuera el del caso nuevo
        raise HTTPException(409, f"ya existe sims/{req.name}.sim de otro trabajo: elige otro nombre")
    try:
        for sub in ("cad", "images", "reports"):
            (d / sub).mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise HTTPException(500, f"no pude crear cases/{req.name}: {e}")
    log.info("caso nuevo: cases/%s%s", req.name, " (reanudado)" if vacio else "")
    return {"name": req.name, "dir": str(d), "resumed": bool(vacio)}


@app.put("/api/cases/{name}/cad/{fname}")
async def api_case_cad(name: str, fname: str, request: Request) -> dict:
    """Sube un archivo de geometría al cad/ del caso (cuerpo = el archivo tal cual, en trozos: sin multipart)."""
    d = _case_dir(name) / "cad"
    if not re.fullmatch(r"[A-Za-z0-9_\-][A-Za-z0-9_\-. ]*", fname) or ".." in fname or not any(fname.lower().endswith(e) for e in CAD_EXT):
        raise HTTPException(400, f"archivo no admitido: nombre con letras, números, espacios, _ - . (sin acentos ni símbolos) y extensión {', '.join(sorted(CAD_EXT))}")
    if fname.split(".")[0].strip().lower() in WIN_RESERVED:
        raise HTTPException(400, f"«{fname}»: nombre reservado de Windows (CON, NUL, COM1…); renómbralo")
    if int(request.headers.get("content-length") or 0) > CAD_MAX:
        raise HTTPException(413, "archivo de más de 2 GB")
    d.mkdir(exist_ok=True)
    tmp = d / f"{fname}.{time.time_ns()}.part"  # dos subidas del mismo nombre no comparten el temporal
    n = 0
    done = False
    try:
        with open(tmp, "wb") as f:
            async for chunk in request.stream():
                n += len(chunk)
                if n > CAD_MAX:
                    raise HTTPException(413, "archivo de más de 2 GB")
                f.write(chunk)
        done = True
    except ClientDisconnect:  # la pestaña se cerró o la red cayó a mitad de subida
        log.warning("subida cortada por el cliente: cases/%s/cad/%s (%d bytes recibidos); descartada", name, fname, n)
        raise HTTPException(400, f"subida cortada ({n} bytes recibidos); vuelve a subirlo")
    finally:
        if not done:  # corte del cliente o archivo enorme: no dejar el .part a medias
            tmp.unlink(missing_ok=True)
    want = int(request.headers.get("content-length") or 0)
    if want and n != want:  # llegó menos (o más) de lo anunciado: no se publica un CAD cortado
        tmp.unlink(missing_ok=True)
        raise HTTPException(400, f"subida incompleta: {n} de {want} bytes; vuelve a subirlo")
    if n == 0:
        tmp.unlink(missing_ok=True)
        raise HTTPException(400, "archivo vacío")
    tmp.replace(d / fname)
    log.info("CAD subido: cases/%s/cad/%s (%d bytes)", name, fname, n)
    return {"file": f"cases/{name}/cad/{fname}", "bytes": n}


@app.get("/api/cases/{name}/cad")
def api_case_cad_list(name: str) -> dict:
    d = _case_dir(name) / "cad"
    return {"files": [{"name": f.name, "bytes": f.stat().st_size} for f in sorted(d.iterdir()) if f.is_file() and not f.name.endswith(".part")] if d.is_dir() else []}


# ---------------------------------------------------------------- papel de cada frontera, elegido por el usuario en el visor
ROLES = {"inlet", "outlet", "wall", "interface", "symmetry"}


class RolesReq(BaseModel):
    roles: dict[str, str] = Field(default_factory=dict)


@app.get("/api/cases/{name}/roles")
def api_roles(name: str) -> dict:
    f = _case_dir(name) / "fronteras.json"
    try:
        d = json.loads(f.read_text(encoding="utf-8")) if f.is_file() else {}
    except ValueError:
        d = {}
    if not isinstance(d, dict):  # fronteras.json corrupto (JSON válido pero no un objeto)
        d = {}
    roles = d.get("roles")
    roles = {k: v for k, v in roles.items() if v in ROLES} if isinstance(roles, dict) else {}
    return {"roles": roles, "at": d.get("at") if isinstance(d.get("at"), str) else None, "file": f"cases/{name}/fronteras.json"}


@app.post("/api/cases/{name}/roles")
def api_roles_set(name: str, req: RolesReq) -> dict:
    """Guarda cases/<caso>/fronteras.json: {«región/frontera»: inlet|outlet|wall|interface|symmetry}. La IA lo usa tal cual."""
    bad = {k: v for k, v in req.roles.items() if v not in ROLES or not k or len(k) > 200}
    if bad:
        raise HTTPException(422, f"papel no válido (usa {', '.join(sorted(ROLES))}): {list(bad)[:5]}")
    f = _case_dir(name) / "fronteras.json"
    f.write_text(json.dumps({"roles": req.roles, "at": time.strftime("%Y-%m-%d %H:%M:%S")}, ensure_ascii=False, indent=1), encoding="utf-8")
    log.info("fronteras de %s: %s", name, {r: sum(1 for v in req.roles.values() if v == r) for r in ROLES})
    return api_roles(name)


@app.get("/files/{name}/images/{fname}")
def image(name: str, fname: str) -> FileResponse:
    d = _case_dir(name)
    f = d / "images" / _png_name(fname)
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
    f = SCENES_DIR / _png_name(fname)
    if not f.is_file():
        raise HTTPException(404, "no existe la escena")
    return FileResponse(f, media_type="image/png", headers={"Cache-Control": "no-cache"})


def _solver_alive() -> bool:
    return scc.alive()


def _solver_busy_409() -> None:
    if not _solver_alive():
        raise HTTPException(409, "no hay solver vivo: pide a la IA que lo arranque (server_start)")
    # ponytail: el candado del MCP es por proceso; si Claude está inyectando una macro desde el chat,
    # un segundo cliente batch chocaría con la suya. Mientras el chat trabaja, no se toca el solver desde aquí.
    if CHAT_LOCK.locked():
        raise HTTPException(409, "La IA está usando el solver ahora; espera a que termine")
    if scc.macro_running():  # otra sesión (Claude Code, otra pestaña) con una macro en marcha: dos clientes batch chocan
        raise HTTPException(409, "hay una macro en marcha (de otra sesión); espera a que termine")


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
        t = json.loads(f.read_text(encoding="utf-8")) if f and f.is_file() else {}
    except ValueError:
        return {}
    return t if isinstance(t, dict) else {}


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
        except (ValueError, KeyError, TypeError, AttributeError) as e:
            log.warning("manifest ilegible %s: %s", f, e)
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


# ---------------------------------------------------------------- archivo .sim del caso: dónde está y dónde copiarlo
def _sim_info(name: str) -> dict:
    sim = scc.SIMS / f"{_safe(name)}.sim"
    st = scc._state()
    dest = scc.sim_destino(name)
    info = {"path": str(sim), "exists": sim.is_file(), "folder": str(scc.SIMS),
            "loaded": scc.alive(st) and Path(st.get("sim") or "").resolve() == sim.resolve(), "destino": dest}
    if sim.is_file():
        info.update(size=sim.stat().st_size, mtime=time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(sim.stat().st_mtime)))
    if dest and Path(dest).is_file():
        info.update(destino_mtime=time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(Path(dest).stat().st_mtime)))
    return info


@app.get("/api/cases/{name}/sim")
def api_sim(name: str) -> dict:
    """Ruta del .sim de trabajo del caso (sims/<caso>.sim), tamaño, fecha, si está cargado y la copia elegida."""
    _case_dir(name)
    return _sim_info(name)


_DIALOG = r"""
import sys, tkinter as tk
from tkinter import filedialog
r = tk.Tk(); r.withdraw(); r.attributes("-topmost", True)
p = filedialog.asksaveasfilename(parent=r, title="Dónde guardar la simulación (.sim)", initialdir=sys.argv[1],
                                 initialfile=sys.argv[2], defaultextension=".sim", filetypes=[("STAR-CCM+", "*.sim")])
sys.stdout.write(p or "")
"""


def _ask_path(initial_dir: str, initial_file: str) -> str:
    """Diálogo «Guardar como» nativo de Windows (tkinter en un proceso aparte: no bloquea ni mezcla hilos con uvicorn)."""
    r = subprocess.run([sys.executable, "-c", _DIALOG, initial_dir, initial_file], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=600)
    return r.stdout.strip()


class SimDestReq(BaseModel):
    path: str | None = Field(None, max_length=500)   # vacío + browse: abre el diálogo; "" sin browse: quita la copia
    browse: bool = False
    copy_now: bool = True


@app.post("/api/cases/{name}/sim/destino")
def api_sim_destino(name: str, req: SimDestReq) -> dict:
    """Elige dónde queda una copia del .sim (diálogo nativo o ruta escrita). Se guarda en cases/<caso>/caso.json y el
    MCP la actualiza tras cada guardado (save, apagar). Con copy_now copia ya (guardando antes si está cargado)."""
    d = _case_dir(name)
    path = (req.path or "").strip().strip('"')
    if req.browse:
        cur = scc.sim_destino(name)
        path = _ask_path(str(Path(cur).parent) if cur else str(Path.home() / "Documents"), f"{name}.sim")
        if not path:
            return {**_sim_info(name), "cancelled": True}
    f = d / "caso.json"
    try:
        conf = json.loads(f.read_text(encoding="utf-8")) if f.is_file() else {}
    except ValueError:
        conf = {}
    conf = conf if isinstance(conf, dict) else {}
    if not path:
        conf.pop("sim_destino", None)
        f.write_text(json.dumps(conf, ensure_ascii=False, indent=1), encoding="utf-8")
        return _sim_info(name)
    p = Path(path)
    if p.suffix.lower() != ".sim":
        p = p.with_suffix(".sim")
    if not p.is_absolute() or not p.parent.exists():
        raise HTTPException(400, f"ruta no válida o carpeta inexistente: {p}")
    if p.resolve() == (scc.SIMS / f"{name}.sim").resolve():
        raise HTTPException(400, "esa es la propia copia de trabajo (sims/): elige otra ruta")
    conf["sim_destino"] = str(p)
    f.write_text(json.dumps(conf, ensure_ascii=False, indent=1), encoding="utf-8")
    log.info("copia del .sim de %s -> %s", name, p)
    out: dict = {}
    if req.copy_now and (scc.SIMS / f"{name}.sim").is_file():
        if _sim_info(name)["loaded"] and not CHAT_LOCK.locked() and not scc.macro_running():
            r = scc.save()   # guardar primero: la copia lleva lo último del solver (save ya copia al destino)
            out["saved"] = r.get("ok")
            out["copia"] = r.get("copia")
        else:
            out["copia"] = scc.mirror_sim(scc.SIMS / f"{name}.sim")
            if _sim_info(name)["loaded"]:
                out["aviso"] = "la IA o una macro está usando el solver: se copió el último .sim guardado"
    return {**_sim_info(name), **out}


class RevealReq(BaseModel):
    what: Literal["sim", "destino", "pdf", "carpeta"]
    file: str | None = Field(None, max_length=200)


@app.post("/api/cases/{name}/reveal")
def api_reveal(name: str, req: RevealReq) -> dict:
    """Abre el Explorador con el archivo seleccionado (.sim de trabajo, su copia, un PDF del caso o la carpeta)."""
    d = _case_dir(name)
    if req.what == "sim":
        p = scc.SIMS / f"{name}.sim"
    elif req.what == "destino":
        p = Path(scc.sim_destino(name) or "")
    elif req.what == "pdf":
        if not req.file or not re.fullmatch(r"[A-Za-z0-9_\-.]+\.pdf", req.file):
            raise HTTPException(400, "archivo inválido")
        p = d / "reports" / req.file
    else:
        p = d
    if not p.exists():
        raise HTTPException(404, f"no existe {p}")
    if os.name == "nt":
        subprocess.Popen(["explorer", str(p)] if p.is_dir() else ["explorer", f"/select,{p}"])
    return {"path": str(p)}


# ---------------------------------------------------------------- informe PDF: todo lo de la simulación
import informe  # noqa: E402  (starccm/ui/informe.py: HTML del informe -> PDF con Edge sin ventana)

REPORT_LOCK = threading.Lock()
RECIPE_DETALLE = scc.RECIPES / "informe-detalle.java"


class ReportReq(BaseModel):
    refresh: bool = True                                  # leer el detalle del solver si está vivo con este caso
    view3d: str | None = Field(None, max_length=20_000_000)  # PNG del visor (data URL)


def _detalle(name: str, refresh: bool) -> tuple[dict | None, str | None]:
    """Detalle del .sim: del solver (si está vivo con el caso y libre) o el último guardado en reports/detalle.json."""
    f = _case_dir(name) / "reports" / "detalle.json"
    aviso = None
    if refresh and _sim_info(name)["loaded"]:
        if CHAT_LOCK.locked() or scc.macro_running():
            aviso = "la IA o una macro está usando el solver: uso el último detalle guardado"
        else:
            r = scc.run_java(RECIPE_DETALLE.read_text(encoding="utf-8"), timeout_s=600)
            rows = informe.parse_detalle(r.get("stdout") or "")
            if r.get("ok") and rows:
                det = {"rows": rows, "at": time.strftime("%Y-%m-%d %H:%M:%S"), "sim": scc._state().get("sim"),
                       "origen": "solver vivo", "seconds": r.get("seconds")}
                f.parent.mkdir(exist_ok=True)
                f.write_text(json.dumps(det, ensure_ascii=False), encoding="utf-8")
                return det, None
            aviso = f"la lectura del solver falló ({r.get('exception') or 'sin datos'}): uso el último detalle guardado"
    try:
        det = json.loads(f.read_text(encoding="utf-8")) if f.is_file() else None
    except ValueError:
        det = None
    if isinstance(det, dict) and det.get("rows"):
        det["origen"] = "lectura guardada (reports/detalle.json)"
        return det, aviso
    return None, aviso or (None if _sim_info(name)["loaded"] else "sin solver vivo con este caso ni detalle guardado")


@app.post("/api/cases/{name}/report")
def api_report(name: str, req: ReportReq) -> dict:
    """Informe PDF del caso en cases/<caso>/reports/informe_<caso>_<fecha>.pdf: portada, resultados, RESUMEN,
    3D, geometría, regiones y fronteras con sus condiciones, física, materiales, marcos, malla, solver, criterios de
    parada, reportes, convergencia (curvas y tabla), escenas y archivos. ~10 s de solver (si está vivo) + ~5 s de PDF."""
    d = _case_dir(name)
    if not REPORT_LOCK.acquire(blocking=False):
        raise HTTPException(409, "ya se está generando un informe")
    try:
        t0 = time.time()
        det, aviso = _detalle(name, req.refresh)
        view = req.view3d if req.view3d and req.view3d.startswith("data:image/png;base64,") else None
        sim = _sim_info(name)
        ctx = {"detalle": det, "view3d": view, "roles": api_roles(name)["roles"], "cad": api_case_cad_list(name)["files"],
               "datasets": [x for x in api_surfaces(name)["datasets"] if x["name"] != "demo"][:3], "version": "2410",
               "sim": {"path": sim["path"] if sim["exists"] else None, "size": sim.get("size"), "mtime": sim.get("mtime")}}
        (d / "reports").mkdir(exist_ok=True)
        html_f = d / "reports" / "informe.html"
        html_f.write_text(informe.build_html(d, ctx), encoding="utf-8")
        pdf = d / "reports" / f"informe_{name}_{time.strftime('%Y%m%d_%H%M')}.pdf"
        try:
            pdf_s = informe.to_pdf(html_f, pdf)
        except (RuntimeError, subprocess.TimeoutExpired) as e:
            raise HTTPException(500, f"no pude imprimir el PDF: {e}")
        log.info("informe %s: %s (%d kB, detalle=%s, %.0f s)", name, pdf.name, pdf.stat().st_size // 1024,
                 det.get("origen") if det else None, time.time() - t0)
        return {"pdf": pdf.name, "path": str(pdf), "url": f"/files/{name}/reports/{pdf.name}", "bytes": pdf.stat().st_size,
                "seconds": round(time.time() - t0, 1), "pdf_seconds": pdf_s, "aviso": aviso,
                "detalle": {"origen": det.get("origen"), "at": det.get("at"), "n": len(det["rows"])} if det else None}
    finally:
        REPORT_LOCK.release()


@app.get("/files/{name}/reports/{fname}")
def report_file(name: str, fname: str) -> FileResponse:
    if not re.fullmatch(r"[A-Za-z0-9_\-.]+\.(pdf|html|csv|json)", fname) or ".." in fname:
        raise HTTPException(400, "archivo inválido")
    f = _case_dir(name) / "reports" / fname
    if not f.is_file():
        raise HTTPException(404, "no existe el archivo")
    mt = {"pdf": "application/pdf", "html": "text/html", "csv": "text/csv", "json": "application/json"}[fname.rsplit(".", 1)[1]]
    return FileResponse(f, media_type=mt, headers={"Content-Disposition": f'inline; filename="{fname}"', "Cache-Control": "no-cache"})


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


_RAW_FAILED: dict[str, float] = {}  # exportación cruda que no se pudo convertir -> su mtime (no reintentar cada sondeo)


def _raw_iter(cf: Path) -> int | None:
    """Iteración de una exportación automática («vivo@00600.case» -> 600); None si es una exportación suelta."""
    m = re.search(r"@(\d+)\.case$", cf.name)
    return int(m.group(1)) if m else None


def _prune_raw(keep: Path) -> None:
    """Borra las exportaciones automáticas anteriores a la convertida. «vivo@00600.case» usa «vivo@0060000000.*»:
    se conserva todo lo que empieza por «vivo@00600» y se borra el resto de «vivo@…»."""
    prefix = keep.name[:-len(".case")]
    for f in keep.parent.glob(prefix.split("@", 1)[0] + "@*"):
        if not f.name.startswith(prefix):
            try:
                f.unlink()
            except OSError as e:
                log.warning("no pude borrar %s: %s", f, e)


def _sync_raw(case: str) -> list[str]:
    """Convierte las exportaciones EnSight crudas (surfaces/_raw/<nombre>/*.case) que aún no tengan dataset o sean
    más nuevas que él: así lo que exporte la IA desde el chat aparece solo en el visor."""
    d = _surf_dir(case)
    done = []
    # por carpeta, solo el .case más nuevo: la exportación automática (receta activar-autoexport) deja uno por
    # exportación («vivo@00600.case»…); el visor muestra el último y los anteriores se borran (≈4 MB cada uno)
    newest_case: dict[Path, Path] = {}
    for cf in (d / "_raw").glob("*/*.case") if (d / "_raw").is_dir() else []:
        cur = newest_case.get(cf.parent)
        if cur is None or (_raw_iter(cf), cf.stat().st_mtime) > (_raw_iter(cur), cur.stat().st_mtime):
            newest_case[cf.parent] = cf
    for cf in sorted(newest_case.values()):
        name = cf.parent.name
        if not re.fullmatch(r"[A-Za-z0-9_\-]+", name):
            continue
        man = d / name / "manifest.json"
        newest = max(q.stat().st_mtime for q in cf.parent.iterdir() if q.is_file())  # el .case se escribe antes que los datos
        if time.time() - newest < 3 or _RAW_FAILED.get(str(cf)) == newest:  # aún se está escribiendo, o ya falló con estos archivos
            continue
        it = _raw_iter(cf)
        if man.is_file() and man.stat().st_mtime >= newest:
            # en vivo la siguiente exportación puede llegar mientras se convierte la anterior: manda la iteración
            try:
                if it is None or json.loads(man.read_text(encoding="utf-8")).get("iteration") == it:
                    continue
            except ValueError:
                pass
        meta = next((m for m in (cf.with_name(cf.name + ".meta"), cf.parent / f"{name}.meta") if m.is_file()), None)
        bounds, rotation = _meta_lines(meta.read_text(encoding="utf-8", errors="replace")) if meta else ([], [])
        try:
            surf.convert_case(cf, d / name, {"boundaries": bounds, "rotation": rotation, "exported": time.strftime(
                "%Y-%m-%d %H:%M:%S", time.localtime(cf.stat().st_mtime)), "source_meta": bool(meta),
                **({"iteration": it, "live": True} if it is not None else {})})
            done.append(name)
            if it is not None:
                _prune_raw(cf)
            log.info("superficie %s/%s convertida desde _raw (%d fronteras, %d marcos)", case, name, len(bounds), len(rotation))
        except Exception as e:  # noqa: BLE001
            _RAW_FAILED[str(cf)] = newest
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
        except ValueError as e:
            log.warning("manifest ilegible %s: %s", m, e)
            continue
        if not (isinstance(man, dict) and isinstance(man.get("parts"), list) and isinstance(man.get("scalars"), list)):
            log.warning("manifest sin partes/escalares %s", m)
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
    starting = bool(pid) and not alive and scc._pid_alive(pid)  # proceso vivo con el puerto aún cerrado: arrancando (o colgado)
    return {"alive": alive, "pid": pid, "port": st.get("port"), "host": st.get("host"), "sim": st.get("sim"),

            "started": st.get("started"), "np": st.get("np"), "startup_seconds": st.get("startup_seconds"),
            "idle_min": round(scc.idle_disk_seconds() / 60, 1) if alive else None,  # la misma medida en disco que usa el watchdog
            "idle_limit_min": scc.IDLE_MIN, "stale": bool(pid) and not alive and not starting, "starting": starting,
            "stopping": STOP_LOCK.locked(), "chatting": CHAT_LOCK.locked(),
            "log": _log_tail(), "claude": CLAUDE_BIN, "state_file": str(scc.STATE_FILE)}


class StopReq(BaseModel):
    save: bool = True


@app.post("/api/server/stop")
def api_server_stop(req: StopReq) -> dict:
    if CHAT_LOCK.locked():  # no inyectar saveState+kill mientras Claude tiene una macro en marcha
        raise HTTPException(409, "La IA está usando el solver; pulsa Detener en el chat primero")
    if scc.macro_running():  # otra sesión (o una macro que sigue tras Detener) está trabajando en el solver
        raise HTTPException(409, "hay una macro en marcha en el solver; espera a que termine (pestaña Salida)")
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


_STEP_RX = [  # palabra clave del Java -> paso legible (el primero que aparezca)
    (r"importCadPart|PartImportManager", "Importando la geometría"), (r"newRegionsFromParts|RegionManager\(\)\.newRegion", "Creando regiones"),
    (r"setPresentationName\(.*(inlet|outlet|blade|hub|shroud)", "Nombrando fronteras"), (r"Interface", "Creando interfaces"),
    (r"AutoMeshOperation|MeshOperationManager|executeMeshOperation|\.execute\(\)", "Mallando"),
    (r"PhysicsContinuum|SegregatedFlowModel|KOmegaTurbulence|SstKwTurbModel", "Configurando la física"),
    (r"RotatingReferenceFrame|ReferenceFrame", "Marco rotatorio (MRF)"), (r"MassFlowBoundary|PressureBoundary|setBoundaryType", "Condiciones de contorno"),
    (r"createReport|ExpressionReport|MassFlowAverage|MomentReport", "Creando reportes"), (r"getSimulationIterator\(\)\.step", "Iterando"),
    (r"ImportManager\(\)\.export|\.case", "Exportando superficies con campo"), (r"createScene|ScalarDisplayer|VectorDisplayer|PlaneSection", "Creando escena"),
    (r"saveState", "Guardando"), (r"println\(.*(getParts|getRegions|getBoundaries)", "Leyendo la simulación"),
]
_TOOL_LABEL = {"server_start": "Arrancando el solver", "server_stop": "Guardando y apagando el solver", "server_status": "Consultando el solver",
               "inspect": "Leyendo la simulación", "iterate": "Iterando", "export_scene": "Exportando escena", "save": "Guardando",
               "recipe_search": "Buscando recetas", "recipe_save": "Guardando receta", "docs_search": "Consultando la API de STAR-CCM+"}


def _tool_label(name: str, inp: dict) -> str:
    """Una frase corta de qué hace la herramienta, para el chat (el detalle va plegado)."""
    inp = inp or {}
    if name == "run_java":
        body = str(inp.get("body", ""))
        m = re.search(r"//\s*QUE:\s*(.+)", body)
        if m:
            return m.group(1).strip()[:90]
        for rx, lab in _STEP_RX:
            if re.search(rx, body):
                return lab
        return "Ejecutando una macro Java"
    lab = _TOOL_LABEL.get(name) or {"Read": "Leyendo un archivo", "Write": "Escribiendo un archivo", "Edit": "Editando un archivo",
                                    "Glob": "Buscando archivos", "Grep": "Buscando en archivos"}.get(name, name)
    extra = inp.get("n") and f"{inp['n']} iteraciones" or inp.get("name") or inp.get("path") or (inp.get("query") and f"«{inp['query']}»") \
        or (inp.get("file_path") and Path(str(inp["file_path"])).name) or (inp.get("sim_path") and Path(str(inp["sim_path"])).name)
    return f"{lab}: {extra}" if extra else lab


def _clip(v, n: int = 3000):
    """Recorta los textos largos de lo que se manda a la página (un run_java de 200 kB no viaja entero por SSE ni se guarda)."""
    if isinstance(v, str):
        return v if len(v) <= n else v[:n] + f"… [{len(v) - n} caracteres más]"
    if isinstance(v, dict):
        return {k: _clip(x, n) for k, x in v.items()}
    if isinstance(v, list):
        return [_clip(x, n) for x in v[:50]]
    return v


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
    CHAT_PROC["stop_req"] = False
    try:
        prompt = f"({'Caso seleccionado en el panel: cases/' + req.case + ' · ' if req.case else ''}{_where_text()})\n{req.message}"
        cmd = ([sys.executable, CLAUDE_BIN] if CLAUDE_BIN.lower().endswith(".py") else [CLAUDE_BIN]) + ["-p", prompt, "--output-format", "stream-json", "--verbose",
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
        if CHAT_PROC.pop("stop_req", False):  # «Detener» llegó mientras se lanzaba la CLI
            CHAT_PROC["stopped"] = True
            _kill_tree(p)
        log.info("chat: CLI lanzada (pid %s%s)", p.pid, ", continúa sesión" if req.session_id else "")
        hidden: set[str] = set()
        q: queue.Queue = queue.Queue()
        threading.Thread(target=lambda: ([q.put(ln) for ln in p.stdout], q.put(None)), daemon=True).start()
        err_tail: deque[str] = deque(maxlen=40)
        err_thread = threading.Thread(target=lambda: [err_tail.append(ln) for ln in p.stderr], daemon=True)
        err_thread.start()
        yield _sse({"kind": "status", "text": "La IA está arrancando…"})
        t0 = last_ping = time.time()
        while True:
            try:
                line = q.get(timeout=2)
            except queue.Empty:
                if p.poll() is not None:  # la CLI murió pero algún hijo suyo mantiene la tubería abierta: no esperar el EOF
                    break
                if time.time() - last_ping >= 15:
                    last_ping = time.time()
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
                        yield _sse({"kind": "text", "text": _clip(scc._redact(b["text"]), 40000)})
                    elif b.get("type") == "tool_use":
                        name = b.get("name", "")
                        if name in ("Write", "Edit"):
                            yield _sse({"kind": "tool", "name": name, "label": _tool_label(name, b.get("input") or {}),
                                        "input": {"file_path": (b.get("input") or {}).get("file_path")}})
                            continue
                        if not name.startswith("mcp__starccm__"):
                            hidden.add(b.get("id", ""))
                            continue
                        short = name.replace("mcp__starccm__", "")
                        yield _sse({"kind": "tool", "name": short, "label": _tool_label(short, b.get("input") or {}),
                                    "input": json.loads(scc._redact(json.dumps(_clip(b.get("input")))))})
            elif t == "user":
                for b in o.get("message", {}).get("content", []):
                    if isinstance(b, dict) and b.get("type") == "tool_result" and b.get("tool_use_id") not in hidden:
                        c = b.get("content")
                        txt = c if isinstance(c, str) else " ".join(x.get("text", "") for x in c if isinstance(x, dict))
                        yield _sse({"kind": "tool_result", "text": scc._redact(txt)[:800], "is_error": bool(b.get("is_error"))})
            elif t == "result":
                yield _sse({"kind": "result", "subtype": o.get("subtype"), "session_id": o.get("session_id"),
                            "turns": o.get("num_turns"), "seconds": round(time.time() - t0),
                            "text": _clip(scc._redact(str(o.get("result"))), 2000) if o.get("subtype") != "success" else None})
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


# La CLI ya no muere si se cierra o recarga la pestaña: un hilo consume _chat_events y guarda cada evento; las
# pestañas se enganchan (POST /api/chat la empieza, GET /api/chat/stream se vuelve a enganchar desde el evento N).
CHAT_RUN: dict = {"id": 0, "events": [], "done": True, "message": "", "case": None, "started": None}
CHAT_COND = threading.Condition()


def _chat_worker(req: "ChatReq", rid: int) -> None:
    try:
        for ev in _chat_events(req):
            if ev.startswith('data: {"kind": "ping"'):
                continue  # los latidos no se guardan: el índice de reenganche (frm) cuenta solo eventos reales, como la página
            with CHAT_COND:
                if CHAT_RUN["id"] == rid:
                    CHAT_RUN["events"].append(ev)
                    CHAT_COND.notify_all()
    except Exception as e:  # noqa: BLE001  sin esto la página se quedaba sin respuesta ni «done»
        log.exception("chat: el hilo falló")
        with CHAT_COND:
            if CHAT_RUN["id"] == rid:
                CHAT_RUN["events"] += [_sse({"kind": "error", "text": f"error interno del chat: {type(e).__name__}: {e}"}), _sse({"kind": "done", "rc": -1})]
    finally:
        with CHAT_COND:
            if CHAT_RUN["id"] == rid:
                CHAT_RUN["done"] = True
            CHAT_COND.notify_all()


def _chat_stream(rid: int, frm: int = 0):
    i, t0 = max(0, frm), time.time()
    while True:
        with CHAT_COND:
            if CHAT_RUN["id"] != rid:
                return
            if i >= len(CHAT_RUN["events"]) and not CHAT_RUN["done"]:
                CHAT_COND.wait(timeout=15)
            evs, done = CHAT_RUN["events"][i:], CHAT_RUN["done"]
        for ev in evs:
            i += 1
            yield ev
        if not evs:
            if done:
                return
            yield _sse({"kind": "ping", "t": round(time.time() - t0)})


_SSE_HDR = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}


@app.post("/api/chat")
def api_chat(req: ChatReq) -> StreamingResponse:
    with CHAT_COND:  # comprobar y reservar bajo el mismo candado: dos POST a la vez no lanzan dos CLI
        if CHAT_LOCK.locked() or not CHAT_RUN["done"]:  # la conversación en curso sigue intacta
            return StreamingResponse(iter([_sse({"kind": "error", "text": "ya hay una conversación en curso; espera o pulsa Detener"})]),
                                     media_type="text/event-stream", headers=_SSE_HDR)
        rid = CHAT_RUN["id"] + 1
        CHAT_RUN.update(id=rid, events=[], done=False, message=req.message, case=req.case, started=time.strftime("%Y-%m-%d %H:%M:%S"))
    threading.Thread(target=_chat_worker, args=(req, rid), daemon=True, name=f"chat-{rid}").start()
    return StreamingResponse(_chat_stream(rid, 0), media_type="text/event-stream", headers=_SSE_HDR)


@app.get("/api/chat/current")
def api_chat_current() -> dict:
    """La conversación en curso o la última: para que una pestaña nueva o recargada la muestre y se enganche."""
    return {"id": CHAT_RUN["id"], "running": not CHAT_RUN["done"], "n": len(CHAT_RUN["events"]),
            "message": CHAT_RUN["message"], "case": CHAT_RUN["case"], "started": CHAT_RUN["started"]}


@app.get("/api/chat/stream")
def api_chat_stream(id: int, frm: int = 0) -> StreamingResponse:
    if id != CHAT_RUN["id"]:
        raise HTTPException(404, "esa conversación ya no está en memoria")
    return StreamingResponse(_chat_stream(id, frm), media_type="text/event-stream", headers=_SSE_HDR)


@app.post("/api/chat/stop")
def api_chat_stop() -> dict:
    p = CHAT_PROC["p"]
    if p and p.poll() is None:
        CHAT_PROC["stopped"] = True
        _kill_tree(p)
        log.info("chat: detenido por el usuario (pid %s)", p.pid)
        return {"stopped": True}
    if CHAT_LOCK.locked() and p is None:  # la CLI aún se está lanzando: se detiene en cuanto exista
        CHAT_PROC["stop_req"] = True
        return {"stopped": True}
    return {"stopped": False}


# ---------------------------------------------------------------- selftest
def _selftest() -> int:
    """Levanta uvicorn en un puerto libre y recorre los endpoints. Sin solver, sin licencia, sin CLI."""
    import socket
    import urllib.error
    import urllib.parse
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
    c, r = post("/api/cases/new", {"name": nombre})
    check(c == 200 and r.get("resumed") is True, "caso vacío (intento cortado) se reanuda en vez de dar 409")
    check(post("/api/cases/new", {"name": "_oculto"})[0] == 422 and post("/api/cases/new", {"name": "CON"})[0] == 400, "caso nuevo: «_x» (se escondería) y «CON» (Windows) rechazados")
    rq = urllib.request.Request(base + f"/api/cases/{nombre}/cad/pieza.stp", data=b"ISO-10303-21;\nEND-ISO-10303-21;\n", method="PUT")
    with urllib.request.urlopen(rq, timeout=10) as rr:
        up = json.loads(rr.read())
    lst = get(f"/api/cases/{nombre}/cad")[1]
    check(up.get("bytes", 0) > 0 and [f["name"] for f in lst.get("files", [])] == ["pieza.stp"], "PUT .../cad/pieza.stp sube y se lista")
    check(post("/api/cases/new", {"name": nombre})[0] == 409, "caso con geometría repetido -> 409")
    rq = urllib.request.Request(base + f"/api/cases/{nombre}/cad/mi%20pieza%20v2.stp", data=b"ISO-10303-21;", method="PUT")
    with urllib.request.urlopen(rq, timeout=10) as rr:
        check(json.loads(rr.read()).get("bytes") == 13 and (CASES / nombre / "cad" / "mi pieza v2.stp").is_file(), "CAD con espacios en el nombre se sube")
    for malo in ("ni%C3%B1o.stp", "CON.stp", "a%3Fb.stp"):
        rq = urllib.request.Request(base + f"/api/cases/{nombre}/cad/{malo}", data=b"x", method="PUT")
        try:
            urllib.request.urlopen(rq, timeout=10); bad = 200
        except urllib.error.HTTPError as e:
            bad = e.code
        except (ConnectionError, urllib.error.URLError):  # rechazo antes de leer el cuerpo: el cliente puede ver el cierre
            bad = 400
        check(bad == 400 and not (CASES / nombre / "cad" / urllib.parse.unquote(malo)).exists(), f"CAD con nombre no admitido ({malo}) -> rechazado")
    import http.client  # subida cortada: anuncia 100 bytes, manda 10 y cuelga
    hc = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    hc.putrequest("PUT", f"/api/cases/{nombre}/cad/cortada.stp")
    hc.putheader("Content-Length", "100")
    hc.endheaders()
    hc.send(b"0123456789")
    hc.close()
    time.sleep(0.8)
    check(not list((CASES / nombre / "cad").glob("cortada*")), "subida cortada: no queda ni el archivo ni su .part")
    rq = urllib.request.Request(base + f"/api/cases/{nombre}/cad/malo.exe", data=b"x", method="PUT")
    try:
        urllib.request.urlopen(rq, timeout=10); bad = 200
    except urllib.error.HTTPError as e:
        bad = e.code
    except (ConnectionError, urllib.error.URLError):  # rechazo antes de leer el cuerpo
        bad = 400
    check(bad == 400, "extensión no admitida -> 400")
    c, r = post(f"/api/cases/{nombre}/roles", {"roles": {"rotor/Inflow": "inlet", "voluta/outlet": "outlet"}})
    check(c == 200 and r["roles"].get("rotor/Inflow") == "inlet" and get(f"/api/cases/{nombre}/roles")[1]["roles"].get("voluta/outlet") == "outlet",
          "fronteras: guardar y leer fronteras.json")
    check(post(f"/api/cases/{nombre}/roles", {"roles": {"x/y": "luna"}})[0] == 422, "fronteras: papel no válido -> 422")
    for malo in ("[1, 2]", "{", '{"roles": [1]}', '{"roles": {"a/b": "luna", "c/d": "inlet"}}'):  # fronteras.json corrupto no tumba la página
        (CASES / nombre / "fronteras.json").write_text(malo, encoding="utf-8")
        c, r = get(f"/api/cases/{nombre}/roles")
        check(c == 200 and isinstance(r["roles"], dict) and "luna" not in r["roles"].values(), f"fronteras.json corrupto ({malo[:18]}) -> 200 sin papeles inválidos")
    (CASES / nombre / "reports").mkdir(exist_ok=True)  # convergencia.csv con BOM y bytes sueltos: el listado de casos sigue vivo
    (CASES / nombre / "reports" / "convergencia.csv").write_bytes(b"\xef\xbb\xbfiter,H\n1,70.5\n2,\xff\n")
    c, rows = get("/api/cases")
    check(c == 200 and any(r["name"] == nombre for r in rows), "convergencia.csv con BOM/bytes sueltos no rompe /api/cases")
    (CASES / nombre / "surfaces" / "malo").mkdir(parents=True, exist_ok=True)  # manifests que no son un dataset: se ignoran
    for m in ("[]", "{}", '{"parts": 1}'):
        (CASES / nombre / "surfaces" / "malo" / "manifest.json").write_text(m, encoding="utf-8")
        c, r = get(f"/api/surfaces?case={nombre}")
        check(c == 200 and r["datasets"] == [], f"manifest inservible ({m}) -> se ignora")
    (CASES / nombre / "tree.json").write_text("[]", encoding="utf-8")
    c, r = get(f"/api/tree?case={nombre}")
    check(c == 200, "tree.json que no es un objeto -> 200")
    # archivo .sim: ruta, copia en otra carpeta (caso.json) y espejo tras guardar
    import tempfile
    tdir = Path(tempfile.mkdtemp(prefix="starccm-ui-sim-"))
    c, r = get(f"/api/cases/{nombre}/sim")
    check(c == 200 and r["exists"] is False and r["path"].endswith(f"{nombre}.sim") and r["destino"] is None, "GET .../sim: ruta del .sim de trabajo")
    check(post(f"/api/cases/{nombre}/sim/destino", {"path": "relativo.sim"})[0] == 400, "copia del .sim con ruta relativa -> 400")
    c, r = post(f"/api/cases/{nombre}/sim/destino", {"path": str(tdir / "copia"), "copy_now": False})
    check(c == 200 and r["destino"] == str(tdir / "copia.sim") and scc.sim_destino(nombre) == str(tdir / "copia.sim"), "copia del .sim: se guarda en caso.json (con extensión .sim)")
    (tdir / f"{nombre}.sim").write_bytes(b"SIM" * 1000)
    cp = scc.mirror_sim(tdir / f"{nombre}.sim")
    check(cp and cp["ok"] and (tdir / "copia.sim").read_bytes() == b"SIM" * 1000 and not list(tdir.glob("*.copiando")), "mirror_sim copia el .sim al destino tras guardar")
    c, r = post(f"/api/cases/{nombre}/sim/destino", {"path": "", "copy_now": False})
    check(c == 200 and r["destino"] is None, "quitar la copia del .sim")
    # informe PDF (sin solver: sin detalle del .sim, con convergencia y fronteras del caso de prueba)
    check(informe._short("69.48581111111105 kg/s · 10.0") == "69.4858 kg/s · 10.0" and "<table>" in informe.md_to_html("| a | b |\n|---|---|\n| 1 | 2 |"),
          "informe: números largos recortados y tablas de markdown")
    if informe.browser():
        c, r = post(f"/api/cases/{nombre}/report", {"refresh": False})
        pdf = CASES / nombre / "reports" / (r.get("pdf") or "x")
        check(c == 200 and pdf.is_file() and pdf.read_bytes()[:4] == b"%PDF" and r["detalle"] is None
              and "Sin detalle del .sim" in (CASES / nombre / "reports" / "informe.html").read_text(encoding="utf-8"),
              f"POST .../report -> PDF ({r.get('bytes', 0) // 1024} kB en {r.get('seconds')} s)")
        c, _ = get(f"/files/{nombre}/reports/{r.get('pdf')}")
        check(c == 200, "GET /files/<caso>/reports/<pdf>")
    shutil.rmtree(tdir, ignore_errors=True)
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
    viv = tmp / "vivo"
    viv.mkdir()
    for n in ("vivo.meta", "vivo@00600.case", "vivo@0060000000.geo", "vivo@00610.case", "vivo@0061000000.geo", "vivo@0061000000.Pressure"):
        (viv / n).write_text("x")
    _prune_raw(viv / "vivo@00610.case")
    check(_raw_iter(viv / "vivo@00610.case") == 610 and _raw_iter(viv / "superficies.case") is None
          and sorted(p.name for p in viv.iterdir()) == ["vivo.meta", "vivo@00610.case", "vivo@0061000000.Pressure", "vivo@0061000000.geo"],
          "3D en vivo: iteración del nombre y poda de las exportaciones anteriores")
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
    c, sg = get("/api/settings")
    check(c == 200 and "run_where" not in sg and "np" in sg["local"], "GET /api/settings: solo local")
    check(_where_text().startswith("solver: este PC"), f"prefijo del chat: {_where_text()}")
    c, r = post("/api/open_gui", {"case": "no_existe"})
    check(c == 404, "POST /api/open_gui con caso inexistente -> 404")
    c, st = get("/api/status")
    check(c == 200 and "alive" in st and "log" in st and "idle_limit_min" in st and "starting" in st, f"GET /api/status (alive={st.get('alive')})")
    long_ev = json.loads(_sse({"kind": "x", "v": _clip({"body": "A" * 50000, "n": 3})})[6:])
    check(len(long_ev["v"]["body"]) < 3100 and long_ev["v"]["n"] == 3, "_clip recorta los textos enormes de los eventos")
    if st.get("alive") or st.get("pid"):  # cualquier solver registrado (aunque el chequeo falle): nunca apagarlo
        print("  skip server/stop: hay un solver registrado en .server.json; no lo toco")
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
    # chat desacoplado de la pestaña, con la CLI falsa de tests/: cortar la conexión no mata la conversación y
    # una pestaña nueva se engancha y recibe lo que faltaba (pasos con etiqueta legible incluidos)
    global CLAUDE_BIN
    real_bin, CLAUDE_BIN = CLAUDE_BIN, str(ROOT / "tests" / "fake_claude.py")
    try:
        rq = urllib.request.Request(base + "/api/chat", data=json.dumps({"message": "hola"}).encode(), headers={"content-type": "application/json"}, method="POST")
        with urllib.request.urlopen(rq, timeout=30) as rr:
            first = rr.read(200)  # leo un trozo y cierro: como recargar la pestaña
        cur = get("/api/chat/current")[1]
        check(b"data:" in first and cur.get("running") is True, "chat: tras cerrar la conexión la conversación sigue en marcha")
        for _ in range(60):
            if not get("/api/chat/current")[1].get("running"):
                break
            time.sleep(0.25)
        with urllib.request.urlopen(base + f"/api/chat/stream?id={cur['id']}&frm=0", timeout=30) as rr:
            evs = [json.loads(x[6:]) for x in rr.read().decode("utf-8").split("\n\n") if x.startswith("data: ")]
        kinds = [e["kind"] for e in evs]
        lab = next((e.get("label") for e in evs if e["kind"] == "tool"), None)
        check("result" in kinds and "done" in kinds and "stopped" not in kinds, f"chat: la conversación terminó sola ({len(evs)} eventos)")
        check(lab == "importar los STEP del caso", f"chat: paso con etiqueta legible ({lab})")
    finally:
        CLAUDE_BIN = real_bin
    # el bloque ```pregunta``` llega entero como un evento de texto (la página lo parsea; aquí solo el viaje)
    real_bin, CLAUDE_BIN = CLAUDE_BIN, str(ROOT / "tests" / "fake_claude.py")
    try:
        rq = urllib.request.Request(base + "/api/chat", data=json.dumps({"message": "PREGUNTA_PRUEBA"}).encode(), headers={"content-type": "application/json"}, method="POST")
        with urllib.request.urlopen(rq, timeout=30) as rr:
            evs = [json.loads(x[6:]) for x in rr.read().decode("utf-8").split("\n\n") if x.startswith("data: ")]
        txt = next((e["text"] for e in evs if e["kind"] == "text"), "")
        check("```pregunta" in txt and json.loads(txt.split("```pregunta")[1].split("```")[0])["opciones"], "chat: la pregunta con opciones viaja íntegra")
    finally:
        CLAUDE_BIN = real_bin
    # los latidos no se guardan (el índice de reenganche cuenta eventos reales) y un fallo del hilo avisa a la página
    real_ev = _chat_events
    globals()["_chat_events"] = lambda req: iter([_sse({"kind": "ping", "t": 15}), _sse({"kind": "text", "text": "a"}), _sse({"kind": "ping", "t": 30})])
    try:
        with CHAT_COND:
            CHAT_RUN.update(id=9001, events=[], done=False)
        _chat_worker(ChatReq(message="x"), 9001)
        check([json.loads(e[6:])["kind"] for e in CHAT_RUN["events"]] == ["text"] and CHAT_RUN["done"], "chat: los ping no se guardan en los eventos")
        def boom(req):
            yield _sse({"kind": "text", "text": "b"})
            raise ValueError("fallo de prueba")
        globals()["_chat_events"] = boom
        with CHAT_COND:
            CHAT_RUN.update(id=9002, events=[], done=False)
        _chat_worker(ChatReq(message="x"), 9002)
        ks = [json.loads(e[6:])["kind"] for e in CHAT_RUN["events"]]
        check(ks == ["text", "error", "done"] and CHAT_RUN["done"], "chat: si el hilo falla la página recibe error y done")
    finally:
        globals()["_chat_events"] = real_ev
        with CHAT_COND:
            CHAT_RUN.update(id=0, events=[], done=True)
    CHAT_LOCK.acquire()  # «Detener» mientras la CLI se está lanzando: se recuerda y se aplica al existir
    try:
        check(api_chat_stop() == {"stopped": True} and CHAT_PROC.get("stop_req") is True, "chat: Detener durante el lanzamiento de la CLI queda pendiente")
    finally:
        CHAT_PROC["stop_req"] = False
        CHAT_LOCK.release()
    c, r = get("/api/chat/stream?id=424242")
    check(c == 404 and "detail" in r, "reenganche a una conversación que ya no existe -> 404 JSON")
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
