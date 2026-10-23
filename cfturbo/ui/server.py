"""Interfaz controladora del agente CFturbo.

Uso:  cfturbo\\.venv\\Scripts\\python -m uvicorn --app-dir cfturbo ui.server:app --port 8765
      (o el preview "cfturbo-ui" definido en .claude/launch.json)

Qué hace (detalle en ui/README.md):
  - GET  /, /app.js, /style.css       -> la página (index.html + módulo ES + estilos, sin build)
  - GET  /api/projects, /api/project/{name} -> proyectos base e info
  - GET  /api/runs[?fields=summary]   -> corridas temporales y versiones (summary: ligero, para el sondeo de 3 s)
  - GET  /api/runs/{id}               -> run.json completo de una corrida
  - GET  /files/{id}/{archivo}        -> STL, STEP… de una corrida o versión (thumb.png en línea)
  - POST /api/runs/{id}/thumb         -> guarda la miniatura PNG que captura el visor (thumb.png)
  - POST /api/run    -> corre CFturbo directamente (mcp_server.run_batch en un hilo); 409 si está ocupado
  - GET  /api/status -> running/running_name/running_since (candado running.lock) y chatting
  - GET  /api/poll   -> {runs (summary), status} en UNA petición: es lo único que sondea la página
  - POST /api/save   -> guarda una corrida como versión en versions/ (409 si el nombre existe)
  - POST /api/open   -> abre la carpeta de una corrida en el Explorador
  - POST /api/chat   -> lanza `claude -p` (Claude Code CLI, suscripción, sin API key) con las tools
                        cft_* y devuelve los eventos por SSE; `--resume` mantiene la conversación
  - POST /api/chat/stop -> mata la CLI del chat en curso y sus hijos (MCP, CFturbo)
Una sola corrida de CFturbo a la vez (candado en disco de mcp_server, vale también para el chat y
otras sesiones) y un solo chat a la vez.
"""
from __future__ import annotations

import json
import os
import queue
import shutil
import subprocess
import sys
import threading
import time
from collections import deque
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from pydantic import BaseModel

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
import mcp_server as cft  # noqa: E402

app = FastAPI(title="cfturbo-ui")
PNG_SIG = bytes([0x89]) + b"PNG" + bytes([13, 10, 26, 10])  # firma de un PNG
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
    "Termina siempre con una línea: qué corrida quedó y qué cambió."
)


def _clean_env() -> dict[str, str]:
    """La CLI debe autenticarse sola (llavero), no heredar la sesión anidada de Claude Code."""
    return {k: v for k, v in os.environ.items() if not k.startswith("CLAUDE")}


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
    try:
        return cft.project_info(name)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))


@app.get("/api/runs")
def runs(limit: int = 50, fields: str = "") -> list[dict]:
    """fields=summary: sin eventos ni geometría (lo usa el sondeo cada 3 s; el detalle va en /api/runs/{id})."""
    return cft.list_runs(max(1, min(limit, 500)), summary=fields == "summary")


def _run_dir(rid: str) -> Path:
    if not rid or any(c in rid for c in "/\\") or ".." in rid:
        raise HTTPException(400, "id inválido")
    try:
        return cft.find_run(rid)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))


class SaveReq(BaseModel):
    run_id: str
    name: str | None = None
    note: str = ""


@app.post("/api/save")
def api_save(req: SaveReq) -> dict:
    try:
        return cft.save_version(req.run_id, req.name, req.note)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    except FileExistsError as e:
        raise HTTPException(409, str(e))


@app.get("/api/runs/{rid}")
def run(rid: str) -> dict:
    return cft.read_json(_run_dir(rid) / "run.json")


@app.post("/api/runs/{rid}/thumb")
async def api_thumb(rid: str, request: Request) -> dict:
    data = await request.body()
    if not data.startswith(PNG_SIG) or len(data) > 512_000:
        raise HTTPException(400, "se espera un PNG de menos de 500 KB")
    (_run_dir(rid) / "thumb.png").write_bytes(data)
    return {"thumb": f"/files/{rid}/thumb.png"}


@app.get("/files/{rid}/{fname}")
def files(rid: str, fname: str) -> FileResponse:
    if any(c in fname for c in "/\\") or ".." in fname:
        raise HTTPException(400, "ruta inválida")
    f = _run_dir(rid) / fname
    if not f.is_file():
        raise HTTPException(404, "archivo no encontrado")
    media = {".stl": "model/stl", ".png": "image/png"}.get(f.suffix.lower(), "application/octet-stream")
    if media == "image/png":  # la miniatura se muestra en línea, no se descarga
        return FileResponse(f, media_type=media)
    return FileResponse(f, media_type=media, filename=fname)


# ---------------------------------------------------------------- ejecutar CFturbo
class RunReq(BaseModel):
    project: str                      # nombre en projects/ o ruta a un .cft (p.ej. el _out.cft de una corrida)
    edits: dict = {}
    name: str = "design"
    exports: list[str] = ["StarCCM", "OpenFOAM"]
    save: bool = True


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

    def work() -> None:
        try:
            cft.run_batch(req.project, req.edits, req.name, req.exports, req.save, lock=lock)
        finally:
            RUN_LOCK.release()

    threading.Thread(target=work, daemon=True).start()
    return {"started": True}


@app.get("/api/status")
def status() -> dict:
    lock = cft.run_lock_info()
    return {"running": RUN_LOCK.locked() or lock is not None, "running_name": (lock or {}).get("name"),
            "running_since": (lock or {}).get("started"), "chatting": CHAT_LOCK.locked(), "claude": CLAUDE_BIN,
            "workdir": str(cft.WORKDIR), "versions": str(cft.VERSIONS), "lock_file": str(cft.LOCK_FILE),
            "keep_tmp": cft.KEEP_TMP}


@app.get("/api/poll")
def poll(limit: int = 40) -> dict:
    """Sondeo de la página: una sola petición cada 3 s (si el servidor cae, un solo error por intento)."""
    return {"runs": cft.list_runs(max(1, min(limit, 500)), summary=True), "status": status()}


class OpenReq(BaseModel):
    run_id: str


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
    message: str
    session_id: str | None = None
    project: str | None = None


def _sse(obj: dict) -> str:
    return "data: " + json.dumps(obj, ensure_ascii=False) + "\n\n"


def _chat_events(req: ChatReq):
    """Generador síncrono (FastAPI lo corre en un hilo): lanza la CLI y traduce su stream-json a SSE."""
    if not CHAT_LOCK.acquire(blocking=False):
        yield _sse({"kind": "error", "text": "ya hay una conversación en curso; espera o pulsa Detener"})
        return
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
        hidden: set[str] = set()  # ids de tools internas (ToolSearch, Read…) que no se muestran al usuario
        q: queue.Queue = queue.Queue()
        threading.Thread(target=lambda: ([q.put(l) for l in p.stdout], q.put(None)), daemon=True).start()
        # stderr en su propio hilo: si se leyera al final, una tubería llena bloquearía a la CLI
        err_tail: deque[str] = deque(maxlen=40)
        err_thread = threading.Thread(target=lambda: [err_tail.append(l) for l in p.stderr], daemon=True)
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
        if CHAT_PROC.get("stopped"):
            yield _sse({"kind": "stopped", "text": "Detenido por el usuario"})
        elif rc not in (0, None) and err:
            yield _sse({"kind": "error", "text": err[-800:]})
        yield _sse({"kind": "done", "rc": rc})
    finally:
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
        return {"stopped": True}
    return {"stopped": False}


def _kill_tree(p: subprocess.Popen) -> None:
    """Mata la CLI y sus hijos (mcp_server.py -> CFturbo.exe). Una corrida a medias queda «running» sin
    candado y list_runs la marca como interrumpida."""
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"], capture_output=True)
    if p.poll() is None:
        p.kill()
