"""Interfaz controladora del agente CFturbo: sirve la página, lista corridas y entrega geometría.

Uso:  .venv\Scripts\python -m uvicorn ui.server:app --port 8765   (o preview "cfturbo-ui")
No llama a CFturbo ni a Claude: solo lee work/<corrida>/run.json y projects/. El cerebro es
Claude Code vía MCP; la página genera el prompt que el usuario pega en Claude Code.
"""
from __future__ import annotations

import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
import mcp_server as cft  # noqa: E402

app = FastAPI(title="cfturbo-ui")


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


@app.get("/api/runs/{rid}")
def run(rid: str) -> dict:
    f = cft.WORKDIR / rid / "run.json"
    if "/" in rid or "\\" in rid or not f.exists():
        raise HTTPException(404, "corrida no encontrada")
    return cft.read_json(f)


@app.get("/files/{rid}/{fname}")
def files(rid: str, fname: str) -> FileResponse:
    if any(c in rid + fname for c in "/\\") or ".." in rid + fname:
        raise HTTPException(400, "ruta inválida")
    f = cft.WORKDIR / rid / fname
    if not f.is_file():
        raise HTTPException(404, "archivo no encontrado")
    media = "model/stl" if f.suffix.lower() == ".stl" else "application/octet-stream"
    return FileResponse(f, media_type=media, filename=fname)
