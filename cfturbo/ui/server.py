"""Interfaz controladora del agente CFturbo.

Uso:  cfturbo\\.venv\\Scripts\\python -m uvicorn --app-dir cfturbo ui.server:app --port 8765
      (o el preview "cfturbo-ui" definido en .claude/launch.json)

Qué hace (detalle en ui/README.md):
  - GET  /, /app.js, /style.css       -> la página (index.html + módulo ES + estilos, sin build)
  - GET  /api/projects, /api/project/{name} -> proyectos base e info
  - GET  /api/poll   -> {runs (fila ligera de galería), status} en UNA petición, con ETag (304 si no cambió):
                        es lo único que sondea la página cada 3 s
  - GET  /api/runs[?fields=summary]   -> corridas temporales y versiones (summary = la fila de /api/poll), con ETag
  - GET  /api/runs/{id}               -> run.json completo de una corrida (curvas, reporte y timing incluidos)
  - DELETE /api/runs/{id}             -> borra una corrida temporal o una versión (409 si está corriendo)
  - GET  /api/new/suggest?Q&H&n[&base] -> base más cercana en nq para una bomba nueva, k y aviso (> ×1,5)
  - POST /api/new                     -> crea projects/<name>/<name>.cft por semejanza (409 si existe); no corre
                                         CFturbo: la página lanza después <name>_1 con /api/run
  - GET  /files/{id}/{archivo}        -> STL, STEP… de una corrida o versión (thumb.png y reporte en línea)
  - GET  /stl/{id}/{archivo}.stl      -> el mismo STL en binario para el visor (5× menos bytes; caché en .visor/)
  - POST /api/runs/{id}/thumb         -> guarda la miniatura PNG que captura el visor (thumb.png)
  - POST /api/run    -> corre CFturbo directamente (mcp_server.run_batch en un hilo); 409 si está ocupado
  - GET  /api/status -> running/running_name/running_since (candado running.lock) y chatting
  - POST /api/save   -> guarda una corrida como versión en versions/ (409 si el nombre existe)
  - POST /api/open   -> abre la carpeta de una corrida en el Explorador
  - POST /api/chat   -> lanza `claude -p` (Claude Code CLI, suscripción, sin API key) con las tools
                        cft_* y devuelve los eventos por SSE (kind: status, init, text, tool, tool_result,
                        ping, raw, result, error, stopped, done); `--resume` mantiene la conversación
  - POST /api/chat/stop -> mata la CLI del chat en curso y sus hijos (MCP, CFturbo)
Errores: siempre JSON {"detail": "texto"} (también los de validación, 422, y los inesperados, 500).
Una sola corrida de CFturbo a la vez (candado en disco de mcp_server, vale también para el chat y
otras sesiones) y un solo chat a la vez. Al apagar el servidor se matan el chat y el CFturbo propios.
"""
from __future__ import annotations

import hashlib
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
import xml.etree.ElementTree as ET
from collections import deque
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response, StreamingResponse
from pydantic import BaseModel, Field, field_validator

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
import mcp_server as cft  # noqa: E402

log = logging.getLogger("cfturbo-ui")
if not log.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s cfturbo-ui: %(message)s", "%H:%M:%S"))
    log.addHandler(_h)
    log.setLevel(logging.INFO)


class _QuietPoll(logging.Filter):
    """El sondeo (cada 3 s), el estado, los STL y las miniaturas no van al log de acceso si salen bien."""
    RX = re.compile(r'"GET /(api/poll|api/status|stl/|files/[^ ]*thumb\.png)[^"]*" (200|304)')

    def filter(self, rec: logging.LogRecord) -> bool:
        return not self.RX.search(rec.getMessage())


logging.getLogger("uvicorn.access").addFilter(_QuietPoll())

PNG_SIG = bytes([0x89]) + b"PNG" + bytes([13, 10, 26, 10])  # firma de un PNG
THUMB_MAX = 512_000
RUN_LOCK = threading.Lock()
CHAT_LOCK = threading.Lock()
CHAT_PROC: dict = {"p": None, "stopped": False}

CLAUDE_BIN = os.environ.get("CFT_CLAUDE_BIN") or shutil.which("claude") or "claude"
CHAT_SYSTEM = (
    "Operas desde el panel web del controlador cfturbo (ui/). El usuario ve a tu lado el visor 3D, "
    "los hitos y la tabla de corridas, que se refrescan solos. Responde en español, corto, con tablas "
    "para números. Cuando pidan crear o variar una bomba usa cft_run directamente (sin pedir confirmación); "
    "cuando pidan resumen usa cft_runs y cft_info. Si CFturbo corrige un valor, dilo. "
    "Si te piden resumen, comparación, explicación o información, SOLO lees y respondes: no lances cft_run ni "
    "cft_save (si ves avisos, menciónalos y ofrece corregirlos). "
    "REGLA FIJA para las corridas que TÚ lances en esta petición (diseñar o variar): revisa warnings y errors y "
    "corrige SIEMPRE los de geometría (solapamientos, intersecciones, extensiones, flujo secundario) en una "
    "corrida nueva, sin que te lo pidan, hasta que desaparezcan o hasta 3 intentos; luego reporta qué quedó. "
    "Busca primero la solución en cft_recipe_search (p.ej. receta 'fix-extension-overlap': ext_outlet=False). "
    "Si cft_run responde que CFturbo está ocupado, espera y reintenta una vez; no insistas. "
    "Las corridas son temporales: cuando el usuario diga que un diseño le sirve, guárdalo con cft_save "
    "(nombre corto, note con el porqué) y registra el aprendizaje con cft_recipe_save. Antes de proponer "
    "un diseño consulta cft_recipe_search (recetas + bitácora de lo que funcionó). "
    "Para una bomba nueva desde un punto de diseño (Q, H, n) usa cft_new; para fijar ángulos de álabe, edits "
    "beta1_deg/beta2_deg en grados. Solo borra (cft_delete) si el usuario lo pide expresamente. "
    "Termina siempre con una línea: qué corrida quedó y qué cambió."
)


def _clean_env() -> dict[str, str]:
    """La CLI debe autenticarse sola (llavero), no heredar la sesión anidada de Claude Code."""
    return {k: v for k, v in os.environ.items() if not k.startswith("CLAUDE")}


def _kill_tree(p: subprocess.Popen) -> None:
    """Mata la CLI y sus hijos (mcp_server.py -> CFturbo.exe). Una corrida a medias queda «running» sin
    candado y list_runs la marca como interrumpida."""
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"], capture_output=True)
    if p.poll() is None:
        p.kill()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    yield
    # apagado: nada de procesos huérfanos (la CLI del chat con su MCP y CFturbo, y el CFturbo de /api/run)
    p = CHAT_PROC.get("p")
    if p and p.poll() is None:
        CHAT_PROC["stopped"] = True
        _kill_tree(p)
        log.info("apagado: chat detenido (pid %s)", p.pid)
    n = cft.kill_children()
    if n:
        log.info("apagado: %d CFturbo detenido(s); la corrida queda «interrumpida»", n)


app = FastAPI(title="cfturbo-ui", lifespan=lifespan)


# ---------------------------------------------------------------- errores coherentes: siempre {"detail": "texto"}
@app.exception_handler(RequestValidationError)
async def _validation(_req: Request, exc: RequestValidationError) -> JSONResponse:
    msgs = []
    for e in exc.errors():
        loc = ".".join(str(x) for x in e.get("loc", ()) if x not in ("body", "query", "path"))
        msgs.append(f"{loc}: {e.get('msg')}" if loc else str(e.get("msg")))
    return JSONResponse({"detail": "petición inválida · " + "; ".join(msgs)}, status_code=422)


@app.exception_handler(Exception)
async def _unexpected(_req: Request, exc: Exception) -> JSONResponse:
    # Starlette vuelve a lanzar la excepción tras responder: uvicorn deja la traza una vez en el log
    return JSONResponse({"detail": f"error interno: {type(exc).__name__}: {exc}"}, status_code=500)


def _json_etag(request: Request, obj) -> Response:
    """JSON con ETag (hash del cuerpo): si el cliente manda el mismo If-None-Match, 304 sin cuerpo."""
    body = json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    tag = '"' + hashlib.blake2b(body, digest_size=8).hexdigest() + '"'
    hdr = {"ETag": tag, "Cache-Control": "no-cache"}
    if request.headers.get("if-none-match") == tag:
        return Response(status_code=304, headers=hdr)
    return Response(body, media_type="application/json", headers=hdr)


def _limit(limit: int) -> int:
    return max(1, min(limit, 500))  # acotado, no rechazado: -1 -> 1, 9999 -> 500


# ---------------------------------------------------------------- página y datos
@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return (HERE / "index.html").read_text(encoding="utf-8")


@app.get("/app.js")
def app_js() -> FileResponse:
    return FileResponse(HERE / "app.js", media_type="text/javascript", headers={"Cache-Control": "no-cache"})


@app.get("/style.css")
def style_css() -> FileResponse:
    return FileResponse(HERE / "style.css", media_type="text/css", headers={"Cache-Control": "no-cache"})


@app.get("/api/projects")
def projects() -> list[dict]:
    return cft.list_projects()


@app.get("/api/project/{name}")
def project(name: str) -> dict:
    if not name.strip() or len(name) > 1000:
        raise HTTPException(400, "nombre de proyecto inválido")
    try:
        return cft.project_info(name)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    except ET.ParseError as e:
        raise HTTPException(422, f"el .cft no es XML válido: {e}")


@app.get("/api/runs")
def runs(request: Request, limit: int = 50, fields: str = "") -> Response:
    """fields=summary: la fila ligera de la galería (la del sondeo); el detalle va en /api/runs/{id}."""
    if fields not in ("", "summary"):
        raise HTTPException(400, "fields debe ser vacío o «summary»")
    return _json_etag(request, cft.list_runs(_limit(limit), summary=fields == "summary"))


def _run_dir(rid: str) -> Path:
    if not rid or len(rid) > 200 or any(c in rid for c in "/\\:") or ".." in rid:
        raise HTTPException(400, "id inválido")
    try:
        return cft.find_run(rid)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))


def _run_file(rid: str, fname: str) -> Path:
    if not fname or any(c in fname for c in "/\\:") or ".." in fname:
        raise HTTPException(400, "ruta inválida")
    f = _run_dir(rid) / fname
    if not f.is_file():
        raise HTTPException(404, "archivo no encontrado")
    return f


class SaveReq(BaseModel):
    run_id: str = Field(min_length=1, max_length=200)
    name: str | None = Field(None, max_length=100)
    note: str = Field("", max_length=4000)


@app.post("/api/save")
def api_save(req: SaveReq) -> dict:
    _run_dir(req.run_id)  # 400/404
    try:
        out = cft.save_version(req.run_id, req.name, req.note)
    except FileExistsError as e:
        raise HTTPException(409, str(e))
    log.info("versión guardada: %s -> %s", req.run_id, out["id"])
    return out


@app.get("/api/runs/{rid}")
def run(rid: str) -> dict:
    f = _run_dir(rid) / "run.json"
    try:
        return cft.read_json(f)
    except ValueError as e:
        raise HTTPException(500, f"run.json ilegible en {rid}: {e}")


@app.delete("/api/runs/{rid}")
def api_delete(rid: str) -> dict:
    _run_dir(rid)  # 400/404
    try:
        out = cft.delete_run(rid)
    except cft.CFturboBusy as e:
        raise HTTPException(409, str(e))
    except OSError as e:
        raise HTTPException(500, f"no pude borrar: {e}")
    log.info("borrada: %s%s", rid, " (versión)" if out.get("version") else "")
    return out


def _qhn_ok(*xs: float) -> bool:
    return all(math.isfinite(x) and x > 0 for x in xs)


@app.get("/api/new/suggest")
def api_new_suggest(Q: float, H: float, n: float, base: str | None = None) -> dict:
    if not _qhn_ok(Q, H, n):
        raise HTTPException(400, "Q, H y n deben ser números positivos")
    try:
        return cft.suggest_base(Q, H, n, base or None)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))


class NewReq(BaseModel):
    Q_m3h: float
    H_m: float
    n_rpm: float
    name: str = Field(min_length=1, max_length=100)
    base: str | None = Field(None, max_length=1000)


@app.post("/api/new")
def api_new(req: NewReq) -> dict:
    if not _qhn_ok(req.Q_m3h, req.H_m, req.n_rpm):
        raise HTTPException(400, "Q, H y n deben ser números positivos")
    try:
        out = cft.new_project(req.Q_m3h, req.H_m, req.n_rpm, req.name, req.base or None)
    except FileExistsError as e:
        raise HTTPException(409, str(e))
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))
    log.info("bomba nueva: projects/%s desde %s", out.get("name"), out.get("base_name"))
    return out


@app.post("/api/runs/{rid}/thumb")
async def api_thumb(rid: str, request: Request) -> dict:
    if int(request.headers.get("content-length") or 0) > THUMB_MAX:  # no leer cuerpos enormes
        raise HTTPException(400, "se espera un PNG de menos de 500 KB")
    d = _run_dir(rid)
    data = await request.body()
    if not data.startswith(PNG_SIG) or len(data) > THUMB_MAX:
        raise HTTPException(400, "se espera un PNG de menos de 500 KB")
    (d / "thumb.png").write_bytes(data)
    return {"thumb": f"/files/{rid}/thumb.png"}


@app.get("/files/{rid}/{fname}")
def files(rid: str, fname: str) -> FileResponse:
    f = _run_file(rid, fname)
    media = {".stl": "model/stl", ".png": "image/png", ".html": "text/html; charset=utf-8"}.get(f.suffix.lower(), "application/octet-stream")
    if f.suffix.lower() in (".png", ".html"):  # miniatura y reporte de diseño se ven en línea, no se descargan
        return FileResponse(f, media_type=media)
    return FileResponse(f, media_type=media, filename=fname)


@app.get("/stl/{rid}/{fname}")
def stl(rid: str, fname: str) -> FileResponse:
    """STL binario para el visor. La geometría de una corrida terminada no cambia: caché del navegador 1 h."""
    f = _run_file(rid, fname)
    if f.suffix.lower() != ".stl":
        raise HTTPException(400, "solo STL")
    return FileResponse(cft.stl_binary(f.parent, fname), media_type="model/stl",
                        headers={"Cache-Control": "private, max-age=3600"})


# ---------------------------------------------------------------- ejecutar CFturbo
class RunReq(BaseModel):
    project: str = Field(min_length=1, max_length=1000)  # nombre en projects/ o ruta a un .cft (p.ej. un _out.cft)
    edits: dict = {}
    name: str = Field("design", max_length=100)
    exports: list[str] = ["StarCCM", "OpenFOAM"]
    save: bool = True

    @field_validator("edits")
    @classmethod
    def _edits(cls, v: dict) -> dict:
        """Claves numéricas con número (o lista [cubo, corona] en β); booleanas con booleano. Evita
        que un texto en d2_mm llegue a CFturbo y deje una corrida basura."""
        num = ({k for k, (_, u) in cft.ALIASES.items() if u != "bool"} | set(cft.CONV) | {"beta1_deg", "beta2_deg", "s_mm"})
        boolean = {"AutoUpdate", "ext_outlet", "beta_auto"}
        def is_num(x) -> bool:
            if isinstance(x, bool):
                return False
            if isinstance(x, (int, float)):
                return True
            try:
                float(str(x).replace(",", "."))
                return True
            except ValueError:
                return False
        for k, val in v.items():
            if k in num:
                ok = is_num(val) or (isinstance(val, list) and val and all(is_num(x) for x in val) and k.startswith("beta"))
                if not ok:
                    raise ValueError(f"'{k}' necesita un número (recibí {val!r})")
            elif k in boolean and not (isinstance(val, bool) or str(val).lower() in ("true", "false")):
                raise ValueError(f"'{k}' necesita true/false (recibí {val!r})")
        return v

    @field_validator("exports")
    @classmethod
    def _exports(cls, v: list[str]) -> list[str]:
        bad = [x for x in v if x not in cft.EXPORTS_KNOWN]
        if bad:
            raise ValueError(f"exports desconocidos {bad}; válidos: {list(cft.EXPORTS_KNOWN)}")
        return list(dict.fromkeys(v))

    @field_validator("edits")
    @classmethod
    def _edits(cls, v: dict) -> dict:
        def ok(x) -> bool:
            if isinstance(x, (bool, str)):
                return len(str(x)) <= 200
            if isinstance(x, (int, float)):
                return math.isfinite(x)
            return isinstance(x, list) and 0 < len(x) <= 2 and all(isinstance(y, (int, float)) and math.isfinite(y) for y in x)
        if len(v) > 50 or any(not isinstance(k, str) or not k or len(k) > 200 for k in v):
            raise ValueError("edits: hasta 50 claves de texto")
        bad = [k for k, x in v.items() if not ok(x)]
        if bad:
            raise ValueError(f"edits con valor inválido (número, texto, booleano o [cubo, corona]): {bad}")
        return v


@app.post("/api/run")
def api_run(req: RunReq) -> dict:
    if not RUN_LOCK.acquire(blocking=False):
        raise HTTPException(409, "ya hay una corrida de CFturbo en marcha")
    try:
        cft.resolve_project(req.project)
        # el candado en disco (global, cubre chat/MCP y otros procesos) se toma AQUÍ, antes de responder:
        # si otro lo tiene, el usuario recibe 409 y no un «started» que luego no corre
        lock = cft.acquire_lock(req.name)
    except FileNotFoundError as e:
        RUN_LOCK.release()
        raise HTTPException(404, str(e))
    except cft.CFturboBusy:
        RUN_LOCK.release()
        busy = cft.run_lock_info() or {}
        raise HTTPException(409, f"CFturbo trabajando ({busy.get('name', 'otra corrida')})")
    except BaseException as e:  # D2-7: cualquier otro fallo no deja RUN_LOCK tomado
        RUN_LOCK.release()
        raise HTTPException(500, f"no pude lanzar la corrida: {e}")
    try:
        threading.Thread(target=_work, args=(req, lock), daemon=True, name=f"run-{req.name}").start()
    except BaseException:
        lock.unlink(missing_ok=True)
        RUN_LOCK.release()
        raise
    log.info("corrida lanzada: %s (%s, %d cambios)", req.name, Path(req.project).name, len(req.edits))
    return {"started": True}


def _work(req: RunReq, lock: Path) -> None:
    """Hilo de /api/run: corre, libera RUN_LOCK pase lo que pase y deja listos los STL binarios del visor
    (la página los pedirá en el siguiente sondeo; si llega antes, espera a esta conversión, no la repite)."""
    r: dict = {}
    try:
        r = cft.run_batch(req.project, req.edits, req.name, req.exports, req.save, lock=lock)
        log.info("corrida %s: %s en %s s, fases %s", r.get("id"), r.get("status"), r.get("seconds"), r.get("timing"))
    except BaseException:
        log.exception("la corrida %s falló", req.name)
    finally:
        RUN_LOCK.release()
    try:
        d = Path(r.get("run_dir", ""))
        t = time.time()
        for g in r.get("geometry") or []:
            cft.stl_binary(d, g["file"])
        if r.get("geometry"):
            log.info("visor: %d STL en binario en %.1f s", len(r["geometry"]), time.time() - t)
    except Exception:
        log.exception("no pude preparar los STL del visor de %s", r.get("id"))


@app.get("/api/status")
def status() -> dict:
    lock = cft.run_lock_info()
    return {"running": RUN_LOCK.locked() or lock is not None, "running_name": (lock or {}).get("name"),
            "running_since": (lock or {}).get("started"), "chatting": CHAT_LOCK.locked(), "claude": CLAUDE_BIN,
            "workdir": str(cft.WORKDIR), "versions": str(cft.VERSIONS), "lock_file": str(cft.LOCK_FILE),
            "keep_tmp": cft.KEEP_TMP}


@app.get("/api/poll")
def poll(request: Request, limit: int = 40) -> Response:
    """Sondeo de la página: una sola petición cada 3 s; 304 sin cuerpo si nada cambió (ETag)."""
    return _json_etag(request, {"runs": cft.list_runs(_limit(limit), summary=True), "status": status()})


class OpenReq(BaseModel):
    run_id: str = Field(min_length=1, max_length=200)


@app.post("/api/open")
def api_open(req: OpenReq) -> dict:
    d = _run_dir(req.run_id)
    if os.name == "nt":
        os.startfile(str(d))  # type: ignore[attr-defined]
    else:
        subprocess.Popen(["xdg-open", str(d)])
    return {"opened": str(d)}


# ---------------------------------------------------------------- chat con Claude Code CLI
class ChatReq(BaseModel):
    message: str = Field(min_length=1, max_length=20000)
    session_id: str | None = Field(None, pattern=r"^[A-Za-z0-9-]{1,64}$")
    project: str | None = Field(None, max_length=200)


def _sse(obj: dict) -> str:
    return "data: " + json.dumps(obj, ensure_ascii=False) + "\n\n"


def _chat_events(req: ChatReq):
    """Generador síncrono (FastAPI lo corre en un hilo): lanza la CLI y traduce su stream-json a SSE.
    Si el navegador cierra la conexión, el generador se cierra y la CLI (con sus hijos) se mata."""
    if not CHAT_LOCK.acquire(blocking=False):
        yield _sse({"kind": "error", "text": "ya hay una conversación en curso; espera o pulsa Detener"})
        return
    p = None
    try:
        prompt = req.message
        if req.project:
            prompt = f"(Proyecto base seleccionado en el panel: {req.project})\n{prompt}"
        cmd = [CLAUDE_BIN, "-p", prompt, "--output-format", "stream-json", "--verbose",
               "--mcp-config", str(ROOT / ".mcp.json"), "--strict-mcp-config",
               "--allowedTools", "mcp__cfturbo__*,Read,Glob,Grep",
               "--disallowedTools", "Bash,Write,Edit,NotebookEdit,WebFetch,WebSearch",
               "--append-system-prompt", CHAT_SYSTEM, "--max-turns", "30"]
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
        hidden: set[str] = set()  # ids de tools internas (ToolSearch, Read…) que no se muestran al usuario
        q: queue.Queue = queue.Queue()
        threading.Thread(target=lambda: ([q.put(ln) for ln in p.stdout], q.put(None)), daemon=True).start()
        # stderr en su propio hilo: si se leyera al final, una tubería llena bloquearía a la CLI
        err_tail: deque[str] = deque(maxlen=40)
        err_thread = threading.Thread(target=lambda: [err_tail.append(ln) for ln in p.stderr], daemon=True)
        err_thread.start()
        yield _sse({"kind": "status", "text": "Claude Code arrancando…"})
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
                        yield _sse({"kind": "text", "text": b["text"]})
                    elif b.get("type") == "tool_use":
                        name = b.get("name", "").replace("mcp__cfturbo__", "")
                        if not name.startswith("cft_"):
                            hidden.add(b.get("id", ""))
                            continue
                        yield _sse({"kind": "tool", "name": name, "input": b.get("input")})
            elif t == "user":
                for b in o.get("message", {}).get("content", []):
                    if isinstance(b, dict) and b.get("type") == "tool_result" and b.get("tool_use_id") not in hidden:
                        c = b.get("content")
                        txt = c if isinstance(c, str) else " ".join(x.get("text", "") for x in c if isinstance(x, dict))
                        yield _sse({"kind": "tool_result", "text": txt[:600], "is_error": bool(b.get("is_error"))})
            elif t == "result":
                yield _sse({"kind": "result", "subtype": o.get("subtype"), "session_id": o.get("session_id"),
                            "turns": o.get("num_turns"), "seconds": round(time.time() - t0),
                            "text": o.get("result") if o.get("subtype") != "success" else None})
        rc = p.wait()
        err_thread.join(timeout=2)
        err = "".join(err_tail).strip()
        log.info("chat: terminó rc=%s en %.0f s%s", rc, time.time() - t0, " (detenido)" if CHAT_PROC.get("stopped") else "")
        if CHAT_PROC.get("stopped"):
            yield _sse({"kind": "stopped", "text": "Detenido por el usuario"})
        elif rc not in (0, None) and err:
            yield _sse({"kind": "error", "text": err[-800:]})
        yield _sse({"kind": "done", "rc": rc})
    finally:
        if p is not None and p.poll() is None:  # el navegador se fue a medias: no dejar la CLI (ni CFturbo) viva
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
