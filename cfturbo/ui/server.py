"""Interfaz controladora del agente CFturbo.

Uso:  cfturbo\\.venv\\Scripts\\python -m uvicorn --app-dir cfturbo ui.server:app --port 8765
      (o el preview "cfturbo-ui" definido en .claude/launch.json)

Qué hace:
  - sirve la página (ui/index.html) y la geometría de work/<corrida>/
  - POST /api/run   -> corre CFturbo directamente (mcp_server.run_batch) con los edits del formulario
  - POST /api/chat  -> lanza `claude -p` (Claude Code CLI, suscripción, sin API key) con las tools
                       cft_* y devuelve los eventos por SSE; `--resume` mantiene la conversación
  - POST /api/open  -> abre la carpeta de una corrida en el Explorador
Una sola corrida y un solo chat a la vez: CFturbo es una licencia y el chat ya corre CFturbo.
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
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from pydantic import BaseModel

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
import mcp_server as cft  # noqa: E402

app = FastAPI(title="cfturbo-ui")
RUN_LOCK = threading.Lock()
CHAT_LOCK = threading.Lock()
CHAT_PROC: dict[str, subprocess.Popen | None] = {"p": None}

CLAUDE_BIN = os.environ.get("CFT_CLAUDE_BIN") or shutil.which("claude") or "claude"
CHAT_SYSTEM = (
    "Operas desde el panel web del controlador cfturbo (ui/). El usuario ve a tu lado el visor 3D, "
    "los hitos y la tabla de corridas, que se refrescan solos. Responde en español, corto, con tablas "
    "para números. Cuando pidan crear o variar una bomba usa cft_run directamente (sin pedir confirmación); "
    "cuando pidan resumen usa cft_runs y cft_info. Si CFturbo corrige un valor, dilo. "
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
def runs(limit: int = 50) -> list[dict]:
    return cft.list_runs(limit)


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


@app.get("/files/{rid}/{fname}")
def files(rid: str, fname: str) -> FileResponse:
    if any(c in fname for c in "/\\") or ".." in fname:
        raise HTTPException(400, "ruta inválida")
    f = _run_dir(rid) / fname
    if not f.is_file():
        raise HTTPException(404, "archivo no encontrado")
    media = "model/stl" if f.suffix.lower() == ".stl" else "application/octet-stream"
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
    except FileNotFoundError as e:
        RUN_LOCK.release()
        raise HTTPException(404, str(e))

    def work() -> None:
        try:
            cft.run_batch(req.project, req.edits, req.name, req.exports, req.save)
        finally:
            RUN_LOCK.release()

    threading.Thread(target=work, daemon=True).start()
    return {"started": True}


@app.get("/api/status")
def status() -> dict:
    return {"running": RUN_LOCK.locked(), "chatting": CHAT_LOCK.locked(), "claude": CLAUDE_BIN,
            "workdir": str(cft.WORKDIR), "versions": str(cft.VERSIONS), "keep_tmp": cft.KEEP_TMP}


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
        q: queue.Queue = queue.Queue()
        threading.Thread(target=lambda: ([q.put(l) for l in p.stdout], q.put(None)), daemon=True).start()
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
                        yield _sse({"kind": "tool", "name": b.get("name", "").replace("mcp__cfturbo__", ""),
                                    "input": b.get("input")})
            elif t == "user":
                for b in o.get("message", {}).get("content", []):
                    if isinstance(b, dict) and b.get("type") == "tool_result":
                        c = b.get("content")
                        txt = c if isinstance(c, str) else " ".join(x.get("text", "") for x in c if isinstance(x, dict))
                        yield _sse({"kind": "tool_result", "text": txt[:600], "is_error": bool(b.get("is_error"))})
            elif t == "result":
                yield _sse({"kind": "result", "subtype": o.get("subtype"), "session_id": o.get("session_id"),
                            "turns": o.get("num_turns"), "seconds": round(time.time() - t0),
                            "text": o.get("result") if o.get("subtype") != "success" else None})
        rc = p.wait()
        err = p.stderr.read().strip() if p.stderr else ""
        if rc not in (0, None) and err:
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
        p.kill()
        return {"stopped": True}
    return {"stopped": False}
