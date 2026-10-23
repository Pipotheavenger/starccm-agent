"""MCP para operar CFturbo en modo batch.

CFturbo no tiene API: se le pasa un XML (.cft-batch) con un bloque <Updates> de parámetros y
acciones Export/Save, y devuelve un .cft-res con los valores realizados. Este servidor hace
exactamente eso y nada más.

Uso:   python mcp_server.py            (stdio, lo lanza Claude Code desde .mcp.json)
       python mcp_server.py --selftest (prueba con un cfturbo falso, sin licencia)

Env:   CFTURBO_EXE      ruta a cfturbo.exe (si falta, se busca en Program Files)
       CFTURBO_WORKDIR  carpeta de trabajo (default: ./work)
"""
from __future__ import annotations

import glob
import json
import os
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORKDIR = Path(os.environ.get("CFTURBO_WORKDIR", HERE / "work"))
RECIPES = HERE / "recipes"


def cfturbo_exe() -> str:
    exe = os.environ.get("CFTURBO_EXE")
    if exe:
        return exe
    hits = sorted(glob.glob(r"C:\Program Files\CFturbo*\cfturbo.exe"))
    if not hits:
        raise RuntimeError("No encuentro cfturbo.exe; define CFTURBO_EXE")
    return hits[-1]


# ---------------------------------------------------------------- XML helpers
def _path(elem_chain: list[ET.Element]) -> str:
    """Ruta legible y única: Tag[Desc|Caption|Name]/... desde <Updates>."""
    parts = []
    for e in elem_chain:
        label = e.get("Desc") or e.get("Caption") or e.get("Name") or e.get("Alias")
        parts.append(f"{e.tag}[{label}]" if label else e.tag)
    return "/".join(parts)


def _walk_values(root: ET.Element):
    """Genera (ruta, elemento) para cada hoja con texto dentro de root."""
    stack = [(k, []) for k in reversed(list(root))]
    while stack:
        node, chain = stack.pop()
        kids = list(node)
        if not kids and (node.text or "").strip():
            yield _path(chain + [node]), node
        for k in reversed(kids):
            stack.append((k, chain + [node]))


def _updates(tree: ET.ElementTree) -> ET.Element:
    upd = tree.getroot().find(".//Updates")
    if upd is None:
        raise ValueError("El .cft-batch no tiene bloque <Updates>")
    return upd


def list_params(batch_file: str) -> list[dict]:
    tree = ET.parse(batch_file)
    out = []
    for path, node in _walk_values(_updates(tree)):
        out.append({
            "path": path,
            "value": node.text.strip(),
            "type": node.get("Type"),
            "alias": node.get("Alias"),
            "range": node.get("Range"),
            "unit": node.get("Unit"),
        })
    return out


def _index(root: ET.Element) -> dict[str, ET.Element]:
    """{ruta: nodo} y también {alias: nodo} para cada hoja."""
    index = {}
    for path, node in _walk_values(root):
        index[path] = node
        if node.get("Alias"):
            index[node.get("Alias")] = node
    return index


def apply_updates(tree: ET.ElementTree, updates: dict[str, str]) -> list[str]:
    """updates: {ruta o alias: valor}. Devuelve claves no encontradas."""
    index = _index(_updates(tree))
    missing = []
    for key, val in updates.items():
        node = index.get(key)
        if node is None:
            missing.append(key)
        else:
            node.text = str(val)
    return missing


def set_export(tree: ET.ElementTree, interface: str | None, workdir: Path, base: str) -> None:
    proj = tree.getroot().find(".//CFturboBatchProject")
    for a in proj.findall("BatchAction"):
        if a.get("Name") == "Export":
            proj.remove(a)
    if not interface:
        return
    a = ET.SubElement(proj, "BatchAction", {"Name": "Export"})
    ET.SubElement(a, "WorkingDir").text = str(workdir)
    ET.SubElement(a, "BaseFileName").text = base
    ET.SubElement(a, "ExportInterface").text = interface


def set_save(tree: ET.ElementTree, out_cft: Path | None) -> None:
    proj = tree.getroot().find(".//CFturboBatchProject")
    for a in proj.findall("BatchAction"):
        if a.get("Name") == "Save":
            proj.remove(a)
    if out_cft:
        a = ET.SubElement(proj, "BatchAction", {"Name": "Save"})
        ET.SubElement(a, "OutputFile").text = str(out_cft)


def run_batch(template: str, updates: dict[str, str], export: str | None, name: str,
              save_cft: bool) -> dict:
    """Escribe un .cft-batch desde la plantilla, corre CFturbo, lee el .cft-res."""
    run_dir = WORKDIR / f"{name}_{time.strftime('%Y%m%d-%H%M%S')}"
    run_dir.mkdir(parents=True)
    tree = ET.parse(template)
    missing = apply_updates(tree, updates)
    if missing:
        return {"ok": False, "error": f"parámetros no encontrados: {missing}"}
    # el InputFile de la plantilla suele ser relativo a donde se guardó: lo hacemos absoluto
    proj = tree.getroot().find(".//CFturboBatchProject")
    src = Path(proj.get("InputFile"))
    if not src.is_absolute():
        src = Path(template).parent / src
    proj.set("InputFile", str(src.resolve()))
    set_export(tree, export, run_dir, name)
    set_save(tree, run_dir / f"{name}.cft" if save_cft else None)
    batch = run_dir / f"{name}.cft-batch"
    tree.write(batch, xml_declaration=True, encoding="utf-8")

    log = run_dir / "cfturbo.log"
    t0 = time.time()
    cmd = [cfturbo_exe(), "-batch", str(batch), "-verbose", "-log", str(log)]
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
    res_file = batch.with_suffix(".cft-res")
    result = {
        "ok": p.returncode == 0 and res_file.exists(),
        "returncode": p.returncode,
        "seconds": round(time.time() - t0, 1),
        "run_dir": str(run_dir),
        "stdout_tail": p.stdout[-2000:],
        "stderr_tail": p.stderr[-2000:],
        "exported": sorted(str(f) for f in run_dir.iterdir() if f.suffix not in (".cft-batch", ".cft-res", ".log")),
    }
    if res_file.exists():
        res = ET.parse(res_file)
        realized = {k: n.text.strip() for k, n in _index(_updates(res)).items()}
        result["realized"] = {k: realized.get(k) for k in updates}
        result["corrected"] = {k: (updates[k], realized.get(k)) for k in updates
                               if realized.get(k) is not None and str(updates[k]) != realized.get(k)}
        outp = res.getroot().find(".//Output")
        if outp is not None:
            result["output"] = {path: node.text.strip() for path, node in _walk_values(outp)}
    return result


# ---------------------------------------------------------------- recipes
def recipe_search(query: str) -> list[dict]:
    RECIPES.mkdir(exist_ok=True)
    q = query.lower().split()
    hits = []
    for f in sorted(RECIPES.glob("*.md")):
        text = f.read_text(encoding="utf-8")
        if all(w in text.lower() or w in f.name.lower() for w in q):
            hits.append({"file": f.name, "head": text.splitlines()[0] if text else ""})
    return hits


def recipe_save(name: str, body: str) -> str:
    RECIPES.mkdir(exist_ok=True)
    f = RECIPES / f"{name}.md"
    f.write_text(body, encoding="utf-8")
    return str(f)


# ---------------------------------------------------------------- MCP
def serve() -> None:
    from mcp.server.fastmcp import FastMCP

    mcp = FastMCP("cfturbo")

    @mcp.tool()
    def cft_params(batch_template: str) -> list[dict]:
        """Lista los parámetros editables de una plantilla .cft-batch (ruta, valor actual, alias, rango)."""
        return list_params(batch_template)

    @mcp.tool()
    def cft_run(batch_template: str, updates: dict, name: str = "design",
                export_interface: str | None = "General", save_cft: bool = True) -> dict:
        """Aplica updates {ruta_o_alias: valor} a la plantilla, corre CFturbo en batch y devuelve
        valores realizados, correcciones automáticas, bloque Output y archivos exportados.
        export_interface: General (STEP/IGES según config), StarCCM, OpenFOAM, Report, PerformanceData, None."""
        return run_batch(batch_template, updates, export_interface, name, save_cft)

    @mcp.tool()
    def cft_log(run_dir: str, tail: int = 100) -> str:
        """Últimas líneas del log de CFturbo de una corrida."""
        f = Path(run_dir) / "cfturbo.log"
        return "\n".join(f.read_text(encoding="utf-8", errors="replace").splitlines()[-tail:]) if f.exists() else "(sin log)"

    @mcp.tool()
    def cft_recipe_search(query: str) -> list[dict]:
        """Busca recetas guardadas (combinaciones de parámetros, lecciones) por palabras."""
        return recipe_search(query)

    @mcp.tool()
    def cft_recipe_save(name: str, body: str) -> str:
        """Guarda una receta en recipes/<name>.md. Primera línea: qué hace."""
        return recipe_save(name, body)

    mcp.run()


# ---------------------------------------------------------------- selftest
FAKE_BATCH = """<?xml version="1.0" standalone="yes"?>
<CFturboFile Version="2025.1">
  <CFturboBatchProject InputFile="pump.cft">
    <Updates>
      <Impeller Desc="Impeller">
        <MainDimensions Desc="Main dimensions">
          <Value Type="Float" Alias="d2" Desc="Outlet diameter" Unit="mm" Range="150:250">200</Value>
          <Value Type="Float" Alias="b2" Desc="Outlet width" Unit="mm">20</Value>
        </MainDimensions>
        <Blades Desc="Blade properties">
          <Value Type="Integer" Alias="nblades" Desc="Number of blades">6</Value>
          <Value Type="Float" Alias="beta2" Desc="Outlet angle" Unit="deg">22.5</Value>
        </Blades>
      </Impeller>
    </Updates>
    <Output>
      <Value Type="Float" Desc="Min throat area">0.0</Value>
    </Output>
  </CFturboBatchProject>
</CFturboFile>
"""

FAKE_CFTURBO = r'''
import sys, shutil, pathlib, xml.etree.ElementTree as ET
args = sys.argv[1:]
batch = pathlib.Path(args[args.index("-batch") + 1])
tree = ET.parse(batch)
# CFturbo real corrige valores fuera de rango: simulamos d2 > 250 -> 250
for v in tree.getroot().iter("Value"):
    if v.get("Alias") == "d2" and float(v.text) > 250:
        v.text = "250"
out = tree.getroot().find(".//Output/Value")
if out is not None:
    out.text = "0.0042"
tree.write(batch.with_suffix(".cft-res"))
for a in tree.getroot().iter("BatchAction"):
    if a.get("Name") == "Export":
        wd = pathlib.Path(a.findtext("WorkingDir")); base = a.findtext("BaseFileName")
        (wd / f"{base}.stp").write_text("fake step")
print("fake cfturbo ok")
'''


def selftest() -> None:
    global WORKDIR
    import tempfile
    tmp = Path(tempfile.mkdtemp())
    WORKDIR = tmp / "work"
    (tmp / "pump.cft").write_text("<cft/>")
    tpl = tmp / "pump.cft-batch"
    tpl.write_text(FAKE_BATCH)
    fake = tmp / "fake_cfturbo.py"
    fake.write_text(FAKE_CFTURBO)
    # ponytail: el "exe" falso es python + script; en Windows real CFTURBO_EXE apunta a cfturbo.exe
    wrapper = tmp / ("fake.cmd" if os.name == "nt" else "fake.sh")
    if os.name == "nt":
        wrapper.write_text(f'@"{sys.executable}" "{fake}" %*\n')
    else:
        wrapper.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{fake}" "$@"\n')
        wrapper.chmod(0o755)
    os.environ["CFTURBO_EXE"] = str(wrapper)

    params = list_params(str(tpl))
    assert {p["alias"] for p in params} == {"d2", "b2", "nblades", "beta2"}, params

    r = run_batch(str(tpl), {"d2": 300, "nblades": 7}, "General", "t1", save_cft=True)
    assert r["ok"], r
    assert r["realized"]["nblades"] == "7", r
    assert r["corrected"]["d2"] == (300, "250"), r          # corrección automática detectada
    assert r["output"]["Value[Min throat area]"] == "0.0042", r
    assert any(f.endswith("t1.stp") for f in r["exported"]), r

    r2 = run_batch(str(tpl), {"noexiste": 1}, None, "t2", save_cft=False)
    assert not r2["ok"] and "noexiste" in r2["error"], r2

    global RECIPES
    RECIPES = tmp / "recipes"
    recipe_save("prueba-d2", "# sube d2 para más altura\nd2 +10% => H +20%")
    assert recipe_search("altura d2")[0]["file"] == "prueba-d2.md"

    shutil.rmtree(tmp)
    print("selftest OK")


if __name__ == "__main__":
    selftest() if "--selftest" in sys.argv else serve()
