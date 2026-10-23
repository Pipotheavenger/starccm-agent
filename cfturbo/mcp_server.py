"""MCP para operar CFturbo 2026 en modo batch editando el proyecto .cft directamente.

CFturbo no tiene API. Lo que sí tiene (verificado el 2026-10-23 con 2026.1.1):
  - `CFturbo.exe -batch X.cft-batch -log X.log` corre sin GUI.
  - El .cft es XML plano: cambiar d2, b2, nBl, Q, H, n... y volver a abrirlo en batch regenera
    la geometría (CFturbo recalcula lo que depende de eso y avisa en el log).
  - El batch exporta (StarCCM = STEP + .cfturbo-ccm; OpenFOAM = STL por superficie) y guarda.
  - El bloque <Updates> del batch solo se acepta si la plantilla la generó la GUI; por eso
    aquí NO se usa. Se edita el .cft copiado y se corre con <Updates/>.

Uso:   python mcp_server.py            (stdio, lo lanza Claude Code desde .mcp.json)
       python mcp_server.py --selftest (prueba con un cfturbo falso, sin licencia)

Env:   CFTURBO_EXE      ruta a CFturbo.exe (si falta, se busca en Program Files)
       CFTURBO_WORKDIR  carpeta de corridas temporales (default: %TEMP%/cfturbo-agent)
       CFTURBO_VERSIONS carpeta de versiones guardadas (default: ./versions); junto con WORKDIR
                        permite una galería aislada (pruebas con 0 o 20 corridas)

Cada corrida vive en WORKDIR/<name>_<timestamp>/ con: <name>.cft (copia editada), .cft-batch,
.cft-res, <name>_out.cft (lo que CFturbo guardó), *.log, exportes, run.json (resumen que lee la
interfaz controladora en ui/) y thumb.png (miniatura que sube la UI). Se conservan las KEEP_TMP
últimas; lo que el usuario guarda (cft_save) se copia a versions/<nombre>/.
Una corrida a la vez EN EL PC: %TEMP%/cfturbo-agent/running.lock (pid, nombre, hora), ruta fija
que no cambia con CFTURBO_WORKDIR (una sola licencia de CFturbo).
Cada corrida no fallida y cada versión guardada dejan una línea en recipes/bitacora.md.
"""
from __future__ import annotations

import glob
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
# Las corridas van a una carpeta temporal y se podan solas; solo lo que el usuario guarda
# (cft_save / botón "Guardar versión") pasa a versions/ dentro del proyecto.
WORKDIR = Path(os.environ.get("CFTURBO_WORKDIR", Path(tempfile.gettempdir()) / "cfturbo-agent"))
VERSIONS = Path(os.environ.get("CFTURBO_VERSIONS", HERE / "versions"))
# Candado global: misma ruta para todos los procesos aunque cada uno use otro WORKDIR (D-N2).
LOCK_FILE = Path(tempfile.gettempdir()) / "cfturbo-agent" / "running.lock"
PROJECTS = HERE / "projects"
RECIPES = HERE / "recipes"
KEEP_TMP = 8  # corridas temporales que se conservan (las guardadas no cuentan)
EXPORTS_DEFAULT = ("StarCCM", "OpenFOAM")  # STEP+ccm para la MV, STL para el visor
G = 9.80665

# Alias -> (regex sobre la ruta de la hoja, unidad en el .cft). Rutas: ver _leaf_path().
_IMP = r"RadialImpeller\[[^/]*\]/"
_MD = _IMP + r"MainDimensions/MainDimensionsElement\[[^/]*\]/"
ALIASES: dict[str, tuple[str, str]] = {
    "Q": (r"DesignPoint_\w+/QFlow$", "m3/s"),
    "H": (r"DesignPoint_\w+/Head$", "m"),
    "n": (r"DesignPoint_\w+/nRot$", "1/s"),
    "rho": (r"DesignPoint_\w+/FluidLiquid\[[^/]*\]/FluidRho$", "kg/m3"),
    "d2": (_MD + r"d2$", "m"),
    "b2": (_MD + r"b2$", "m"),
    "dS": (_MD + r"dS$", "m"),
    "dH": (_MD + r"dH$", "m"),
    "Psi": (_MD + r"Psi$", "-"),
    "b2_d2": (_MD + r"b2_d2$", "-"),
    "EtaH": (_MD + r"EtaH$", "-"),
    "AutoUpdate": (_MD + r"AutoUpdate$", "bool"),
    "nBl": (_IMP + r"BladeProperties/nBl$", "-"),
    "volute_d_out": (r"OutletVolute\[[^/]*\]/SpiralCasingDiff/Diameter$", "m"),
}
# Claves cómodas en unidades de ingeniería -> (alias SI, factor a SI)
CONV: dict[str, tuple[str, float]] = {
    "Q_m3h": ("Q", 1 / 3600), "H_m": ("H", 1.0), "n_rpm": ("n", 1 / 60),
    "d2_mm": ("d2", 1e-3), "b2_mm": ("b2", 1e-3), "dS_mm": ("dS", 1e-3), "dH_mm": ("dH", 1e-3),
    "volute_d_out_mm": ("volute_d_out", 1e-3),
}


def cfturbo_exe() -> str:
    exe = os.environ.get("CFTURBO_EXE")
    if exe:
        return exe
    hits = sorted(glob.glob(r"C:\Program Files\CFturbo*\CFturbo.exe"))
    if not hits:
        raise RuntimeError("No encuentro CFturbo.exe; define CFTURBO_EXE")
    return hits[-1]


def read_json(f: Path) -> dict:
    return json.loads(f.read_text(encoding="utf-8"))


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


# ---------------------------------------------------------------- XML del .cft
def _label(e: ET.Element) -> str:
    n = e.get("Name") or e.get("Caption")
    return f"{e.tag}[{n}]" if n else e.tag


def _leaves(root: ET.Element) -> list[tuple[str, ET.Element]]:
    """(ruta, hoja) para cada elemento con texto bajo <CFturboProject>. Ruta = Tag[Name]/..."""
    proj = root.find("CFturboProject")
    out: list[tuple[str, ET.Element]] = []
    stack = [(k, [k]) for k in reversed(list(proj))]
    while stack:
        node, chain = stack.pop()
        kids = list(node)
        if not kids and (node.text or "").strip():
            out.append(("/".join(_label(x) for x in chain), node))
        for k in reversed(kids):
            stack.append((k, chain + [k]))
    return out


def _resolve(leaves: list[tuple[str, ET.Element]], key: str) -> tuple[str, ET.Element]:
    """key = alias, clave con unidad (d2_mm), regex o sufijo de ruta. Debe dar una sola hoja."""
    alias = CONV.get(key, (key, 1.0))[0]
    if alias in ALIASES:
        pat = re.compile(ALIASES[alias][0])
        hits = [(p, e) for p, e in leaves if pat.search(p)]
    else:
        hits = [(p, e) for p, e in leaves if p.endswith(key)]
        if not hits:
            try:
                rx = re.compile(key)
                hits = [(p, e) for p, e in leaves if rx.search(p)]
            except re.error:
                hits = []
    if len(hits) != 1:
        raise KeyError(f"'{key}': {len(hits)} coincidencias" + (": " + "; ".join(p[-90:] for p, _ in hits[:5]) if hits else ""))
    return hits[0]


def _to_si(key: str, value) -> str:
    """Valor como texto para el XML, convertido a SI si la clave trae unidad."""
    if isinstance(value, bool):
        return "True" if value else "False"
    if isinstance(value, str) and value.strip().lower() in ("true", "false"):  # "false" -> "False" (como CFturbo)
        return value.strip().capitalize()
    if key in CONV:
        return repr(float(value) * CONV[key][1])
    if isinstance(value, (int, float)):
        return repr(value) if isinstance(value, float) else str(value)
    return str(value)


def _set_ext_outlet(root: ET.Element, on) -> str:
    """Extensión CFD de salida del impulsor. Para apagarla no basta la bandera: CFturbo la vuelve a
    activar si el objeto <CFDSetup_RotSym_Extension_Outlet> sigue ahí (verificado 2026-10-23).
    Es la causa del aviso 'Extension is overlapping neighboring component' con voluta pegada."""
    on = str(on).lower() in ("true", "1", "yes", "si", "sí")
    done = []
    for cs in root.iter("CFDSetup_RotSym"):
        flag = cs.find("CFDSetup_RotSym_Extension_Outlet_Active")
        if flag is None:
            continue
        flag.text = "True" if on else "False"
        obj = cs.find("CFDSetup_RotSym_Extension_Outlet")
        if not on and obj is not None:
            cs.remove(obj)
        done.append(flag.text)
    if not done:
        raise KeyError("ext_outlet: el proyecto no tiene CFDSetup_RotSym")
    return done[0]


# Claves especiales de `edits` que hacen algo más que cambiar una hoja
SPECIAL = {"ext_outlet": _set_ext_outlet}


def _components(root: ET.Element) -> list[dict]:
    pl = root.find("CFturboProject/PolyList_CFturboDesign")
    comps = []
    for e in pl if pl is not None else []:
        comps.append({
            "index": int(e.get("Index", len(comps))),
            "type": e.tag.replace("CFturboDesign_", ""),
            "caption": (e.findtext("Caption") or e.get("Name") or e.tag),
            "active": (e.findtext("Active") or "True") == "True",
        })
    return comps


# ---------------------------------------------------------------- proyectos
def resolve_project(name_or_path: str) -> Path:
    p = Path(name_or_path)
    if p.suffix.lower() == ".cft" and p.exists():
        return p.resolve()
    d = PROJECTS / name_or_path
    cands = [d / f"{name_or_path}.cft"] + sorted(d.glob("*.cft"))
    for c in cands:
        if c.exists():
            return c.resolve()
    raise FileNotFoundError(f"No encuentro el proyecto '{name_or_path}' (ni ruta .cft ni projects/{name_or_path}/*.cft)")


def list_projects() -> list[dict]:
    out = []
    if PROJECTS.exists():
        for d in sorted(p for p in PROJECTS.iterdir() if p.is_dir()):
            cfts = sorted(d.glob("*.cft"))
            if cfts:
                runs = len(list(WORKDIR.glob(f"*/run.json"))) if WORKDIR.exists() else 0
                out.append({"name": d.name, "cft": str(cfts[0]), "runs_total": runs})
    return out


def _get(leaves, key, default=None):
    try:
        return float(_resolve(leaves, key)[1].text.strip())
    except (KeyError, ValueError):
        return default


def nq_calc(Q_m3h: float, H_m: float, n_rpm: float) -> dict:
    """nq = n[rpm]·sqrt(Q[m3/s])/H^0.75. Bandas orientativas para bombas (Gülich)."""
    Q = Q_m3h / 3600
    nq = n_rpm * math.sqrt(Q) / H_m ** 0.75
    if nq < 10:
        tipo = "radial muy lenta: considerar multietapa o subir rpm"
    elif nq < 30:
        tipo = "radial lenta"
    elif nq < 50:
        tipo = "radial normal"
    elif nq < 80:
        tipo = "radial rápida / semiaxial"
    elif nq < 160:
        tipo = "flujo mixto"
    else:
        tipo = "axial"
    return {"nq": round(nq, 1), "ns_us": round(nq * 51.6, 0), "tipo": tipo,
            "Q_m3s": Q, "P_hid_kW": round(998.2 * G * Q * H_m / 1000, 2)}


def project_info(name_or_path: str) -> dict:
    cft = resolve_project(name_or_path)
    root = ET.parse(cft).getroot()
    leaves = _leaves(root)
    Q, H, n = _get(leaves, "Q"), _get(leaves, "H"), _get(leaves, "n")
    info = {
        "name": cft.parent.name if cft.parent.parent == PROJECTS else cft.stem,
        "cft": str(cft),
        "project_type": root.findtext("CFturboProject/ProjectType"),
        "version": root.findtext("CFturboProject/Version"),
        "design_point": {
            "Q_m3h": round(Q * 3600, 3) if Q else None, "H_m": H,
            "n_rpm": round(n * 60, 1) if n else None,
            "fluid": fl.get("Name") if (fl := root.find(".//FluidLiquid")) is not None else None,
            "rho": _get(leaves, "rho"),
        },
        "components": _components(root),
        "dims": {
            "d2_mm": (_get(leaves, "d2") or 0) * 1000 or None,
            "b2_mm": (_get(leaves, "b2") or 0) * 1000 or None,
            "dS_mm": (_get(leaves, "dS") or 0) * 1000 or None,
            "dH_mm": (_get(leaves, "dH") or 0) * 1000 or None,
            "Psi": _get(leaves, "Psi"), "nBl": _get(leaves, "nBl"),
            "b2_d2": _get(leaves, "b2_d2"), "EtaH": _get(leaves, "EtaH"),
            "volute_d_out_mm": (_get(leaves, "volute_d_out") or 0) * 1000 or None,
            "AutoUpdate": _get_text(leaves, "AutoUpdate"),
        },
    }
    if Q and H and n:
        info["nq"] = nq_calc(Q * 3600, H, n * 60)
    # extensión CFD de salida del impulsor: None = no hay CFDSetup_RotSym (ext_outlet daría error),
    # True = activa (la UI marca «Quitar extensión» por defecto), False = ya apagada
    flags = [f.text.strip() == "True" for f in root.iter("CFDSetup_RotSym_Extension_Outlet_Active") if f.text]
    info["cfd_ext_outlet"] = any(flags) if flags else None
    return info


def _get_text(leaves, key):
    try:
        return _resolve(leaves, key)[1].text.strip()
    except KeyError:
        return None


def list_params(name_or_path: str, filter: str = "", limit: int = 300) -> dict:
    root = ET.parse(resolve_project(name_or_path)).getroot()
    leaves = _leaves(root)
    rx = re.compile(filter, re.I) if filter else None
    rows = [{"path": p, "value": e.text.strip(), "type": e.get("Type")}
            for p, e in leaves if not rx or rx.search(p)]
    aliases = {}
    for a, (_, unit) in ALIASES.items():
        try:
            p, e = _resolve(leaves, a)
            aliases[a] = {"value": e.text.strip(), "unit": unit, "path": p}
        except KeyError as err:
            aliases[a] = {"error": str(err)}
    return {"aliases": aliases, "total": len(rows), "params": rows[:limit]}


# ---------------------------------------------------------------- batch
def _batch_xml(cft: Path, run_dir: Path, base: str, exports: list[str], comps: list[dict], save: Path | None) -> str:
    vals = "".join(
        f'<Value Type="Integer" Caption="{c["caption"]}" Index="{i}">{c["index"] + 1}</Value>'
        for i, c in enumerate(comps) if c["active"])
    ec = f'<ExportComponents Type="Array1" Count="{sum(c["active"] for c in comps)}">{vals}</ExportComponents>'
    acts = "".join(
        f'<BatchAction Name="Export"><WorkingDir>{run_dir}</WorkingDir><BaseFileName>{base}</BaseFileName>'
        f'<ExportInterface Type="Enum">{x}</ExportInterface>{ec}</BatchAction>' for x in exports)
    if save:
        acts += f'<BatchAction Name="Save"><OutputFile>{save}</OutputFile></BatchAction>'
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<CFturboFile Version="2026.1">\n'
            f'<CFturboBatchProject InputFile="{cft}"><Updates/><Output/>{acts}</CFturboBatchProject>\n</CFturboFile>\n')


_LOG_RX = re.compile(r"^\S+ \S+ \[(WARN|ERROR)\]\s+(\S.*?) - (.*)$")
_STL_RX = re.compile(r"_Co(\d+)_\[?([^\]]+?)\]?(Extension)?-(?:CFD)?Flowdomain-(\w+)\.stl$", re.I)


def _parse_log(run_dir: Path) -> tuple[list[str], list[str]]:
    """Avisos y errores de todos los .log de la corrida: el de -log trae poco; los hints del
    proyecto (acoplamientos, extensiones, licencia) van al <name>.log que CFturbo crea solo."""
    warns, errs = [], []
    for log in sorted(run_dir.glob("*.log")):
        for line in log.read_text(encoding="utf-8", errors="replace").splitlines():
            m = _LOG_RX.match(line)
            if not m:
                continue
            msg = f"{m.group(2)}: {m.group(3)}".strip()
            if m.group(1) == "ERROR":
                errs.append(msg)
            elif "Logfile not writable" not in msg:
                warns.append(msg)
    dd = lambda xs: list(dict.fromkeys(xs))  # noqa: E731
    return dd(warns), dd(errs)


def _geometry(run_dir: Path) -> list[dict]:
    geo = []
    for f in sorted(run_dir.glob("*.stl")):
        m = _STL_RX.search(f.name)
        geo.append({"file": f.name, "kind": "stl",
                    "component": (m.group(2) + (" ext" if m.group(3) else "")) if m else f.stem,
                    "boundary": m.group(4) if m else "", "bytes": f.stat().st_size})
    return geo


# ---------------------------------------------------------------- candado: una corrida de CFturbo a la vez
# Vale entre procesos (UI, chat por MCP, otra sesión de Claude Code, otro WORKDIR): LOCK_FILE con PID y nombre.
LOCK_MAX_AGE = 40 * 60  # s; run_batch corta a CFturbo a los 30 min, así que más viejo es basura


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":  # ojo: os.kill(pid, 0) en Windows MATA el proceso; se consulta con la API
        import ctypes
        k32 = ctypes.windll.kernel32
        h = k32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return False
        code = ctypes.c_ulong()
        ok = k32.GetExitCodeProcess(h, ctypes.byref(code))
        k32.CloseHandle(h)
        return bool(ok) and code.value == 259  # STILL_ACTIVE
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def run_lock_info() -> dict | None:
    """Corrida en marcha según el candado, o None. Borra candados de procesos muertos."""
    f = LOCK_FILE
    try:
        info = read_json(f)
    except FileNotFoundError:
        return None
    except (OSError, ValueError):
        info = {}
    if _pid_alive(int(info.get("pid", 0))) and time.time() - info.get("t", 0) < LOCK_MAX_AGE:
        return info
    f.unlink(missing_ok=True)
    return None


class CFturboBusy(RuntimeError):
    pass


def acquire_lock(name: str) -> Path:
    """Toma el candado global o lanza CFturboBusy. La UI lo toma ANTES de responder a /api/run."""
    f = LOCK_FILE
    f.parent.mkdir(parents=True, exist_ok=True)
    name = re.sub(r"[^A-Za-z0-9_-]+", "_", name) or "design"
    for _ in range(2):
        try:
            with f.open("x", encoding="utf-8") as fh:  # creación atómica
                json.dump({"pid": os.getpid(), "name": name, "t": time.time(), "started": _now()}, fh)
            return f
        except FileExistsError:
            busy = run_lock_info()  # si estaba muerto lo borra y se reintenta
            if busy:
                raise CFturboBusy(f"CFturbo ocupado con «{busy.get('name')}» (pid {busy.get('pid')}); espera a que termine")
    raise CFturboBusy("no pude tomar el candado de CFturbo")


def run_batch(project: str, edits: dict | None = None, name: str = "design",
              exports: list[str] | tuple[str, ...] | None = None, save: bool = True,
              lock: Path | None = None) -> dict:
    """Copia el .cft a WORKDIR/<name>_<ts>/, aplica edits {alias|clave_unidad|sufijo: valor}, corre CFturbo
    (exporta y guarda) y devuelve realizados, correcciones, avisos, errores y archivos.
    Lanza CFturboBusy si otra corrida (de cualquier proceso) tiene el candado. `lock`: candado ya
    tomado con acquire_lock (se libera al terminar)."""
    if lock is None:
        resolve_project(project)  # 404 antes de tomar el candado
        lock = acquire_lock(name)
    try:
        return _run_batch(project, edits, name, exports, save)
    finally:
        lock.unlink(missing_ok=True)


def _run_batch(project: str, edits: dict | None, name: str,
               exports: list[str] | tuple[str, ...] | None, save: bool) -> dict:
    edits = dict(edits or {})
    exports = list(exports if exports is not None else EXPORTS_DEFAULT)
    src = resolve_project(project)
    name = re.sub(r"[^A-Za-z0-9_-]+", "_", name) or "design"
    run_dir = WORKDIR / f"{name}_{time.strftime('%Y%m%d-%H%M%S')}"
    for i in range(1, 100):  # dos corridas en el mismo segundo
        if not run_dir.exists():
            break
        run_dir = run_dir.with_name(f"{name}_{time.strftime('%Y%m%d-%H%M%S')}_{i}")
    run_dir.mkdir(parents=True)
    t0 = time.time()
    events: list[dict] = []
    res: dict = {"id": run_dir.name, "name": name, "project": str(src),
                 "started": datetime.now().isoformat(timespec="milliseconds"),
                 "status": "running", "edits": edits, "requested_si": {}, "realized": {}, "corrected": {},
                 "exports": {}, "geometry": [], "warnings": [], "errors": [], "events": events,
                 "run_dir": str(run_dir)}

    def ev(msg: str) -> None:
        events.append({"t": _now(), "msg": msg})
        (run_dir / "run.json").write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding="utf-8")

    ev(f"Proyecto base: {src.name}")
    cft = run_dir / f"{name}.cft"
    shutil.copy2(src, cft)
    tree = ET.parse(cft)
    leaves = _leaves(tree.getroot())
    comps = _components(tree.getroot())
    try:
        for k, v in edits.items():
            if k in SPECIAL:
                res["requested_si"][k] = SPECIAL[k](tree.getroot(), v)
                continue
            p, e = _resolve(leaves, k)
            e.text = _to_si(k, v)
            res["requested_si"][k] = e.text
    except KeyError as err:
        res.update(status="error", errors=[f"parámetro no encontrado: {err}"], seconds=0)
        ev("Parámetro no encontrado")
        return res
    if edits:
        tree.write(cft, xml_declaration=True, encoding="UTF-8")
        ev(f"Editados {len(edits)} parámetros en la copia del .cft")
    out_cft = run_dir / f"{name}_out.cft" if save else None
    batch = run_dir / f"{name}.cft-batch"
    batch.write_text(_batch_xml(cft, run_dir, name, exports, comps, out_cft), encoding="utf-8")
    log = run_dir / "cfturbo.log"
    ev("CFturbo arrancando (batch)")
    try:
        p = subprocess.run([cfturbo_exe(), "-batch", str(batch), "-log", str(log)],
                           capture_output=True, text=True, timeout=1800, cwd=run_dir)
        rc = p.returncode
    except subprocess.TimeoutExpired:
        rc = -1
        res["errors"].append("CFturbo no terminó en 30 min")
    res["returncode"] = rc  # 0 limpio, 1 con avisos, 2 con errores
    res["seconds"] = round(time.time() - t0, 1)
    ev(f"CFturbo terminó (rc={rc}, {res['seconds']} s)")
    w, e_ = _parse_log(run_dir)
    res["warnings"], res["errors"] = w, res["errors"] + e_
    res_file = cft.with_suffix(".cft-res")
    if res_file.exists():
        res["actions"] = []
        for a in ET.parse(res_file).getroot().iter("BatchAction"):
            # Export no trae <State>; cada componente trae State="..." en su <Value>
            st = a.findtext("State") or ",".join(f"{v.get('Caption')}={v.get('State')}" for v in a.iter("Value")) or "?"
            res["actions"].append(f"{a.get('Name')}{(' ' + a.findtext('ExportInterface')) if a.findtext('ExportInterface') else ''}: {st}")
    for x in exports:
        pats = {"StarCCM": ["*.stp", "*.cfturbo-ccm", "*.java"], "OpenFOAM": ["*.stl"],
                "General": ["*.geo-xml", "*.stp", "*.igs", "*.stl"]}.get(x, ["*"])
        res["exports"][x] = sorted({f.name for pt in pats for f in run_dir.glob(pt)})
    res["geometry"] = _geometry(run_dir)
    n_files = sum(len(v) for v in res["exports"].values())
    ev(f"Exportados {n_files} archivos" if n_files else "Sin archivos exportados")
    if out_cft and out_cft.exists():
        out_root = ET.parse(out_cft).getroot()
        lv = _leaves(out_root)
        for k in edits:
            try:
                if k == "ext_outlet":
                    real = out_root.find(".//CFDSetup_RotSym_Extension_Outlet_Active").text.strip()
                else:
                    real = _resolve(lv, k)[1].text.strip()
            except (KeyError, AttributeError):
                continue
            res["realized"][k] = real
            try:
                if abs(float(real) - float(res["requested_si"][k])) > 1e-9 * max(1.0, abs(float(real))):
                    res["corrected"][k] = [res["requested_si"][k], real]
            except ValueError:  # booleanos y texto: CFturbo puede cambiar mayúsculas (false/False)
                if real.lower() != str(res["requested_si"][k]).lower():
                    res["corrected"][k] = [res["requested_si"][k], real]
        try:
            res["info"] = project_info(str(out_cft))
        except Exception as err:  # ponytail: info es cortesía, no debe tumbar la corrida
            res["info_error"] = str(err)
    res["status"] = "error" if res["errors"] or rc not in (0, 1) else ("warn" if res["warnings"] else "ok")
    res["saved"] = False
    ev({"ok": "Corrida OK", "warn": "Corrida con avisos", "error": "Corrida con errores"}[res["status"]])
    if res["status"] != "error":
        _bitacora(res)
    prune_tmp(exclude=run_dir.name)
    return res


def _bitacora(r: dict, note: str = "") -> None:
    """Biblioteca del agente: una línea por corrida que salió bien (y por versión guardada).
    recipe_search la indexa, así Claude ve qué combinaciones funcionaron antes de proponer."""
    RECIPES.mkdir(exist_ok=True)
    f = RECIPES / "bitacora.md"
    if not f.exists():
        f.write_text("# Bitácora de corridas (automática)\n\nQué se pidió, qué quedó y cómo salió. "
                     "Las recetas con el porqué van en archivos aparte (cft_recipe_save).\n\n", encoding="utf-8")
    d = (r.get("info") or {}).get("dims") or {}
    dims = ", ".join(f"{k} {v}" for k, v in (("d2", d.get("d2_mm")), ("b2", d.get("b2_mm")), ("nBl", d.get("nBl")),
                                             ("Psi", d.get("Psi"))) if v is not None)
    edits = ", ".join(f"{k}={v}" for k, v in (r.get("edits") or {}).items()) or "sin cambios"
    corr = "; corrigió " + ", ".join(f"{k} {a}->{b}" for k, (a, b) in r.get("corrected", {}).items()) if r.get("corrected") else ""
    line = (f"- {(r.get('started') or _now())[:16].replace('T', ' ')} | {r.get('name')} | base {Path(r.get('project', '')).stem} | "
            f"pedido: {edits} | quedó: {dims} | {r.get('status')} ({len(r.get('warnings') or [])} avisos){corr}"
            + (f" | {note}" if note else "") + "\n")
    with f.open("a", encoding="utf-8") as fh:
        fh.write(line)


def _all_run_dirs() -> list[Path]:
    dirs = []
    for base in (WORKDIR, VERSIONS):
        if base.exists():
            dirs += [f.parent for f in base.glob("*/run.json")]
    return dirs


def find_run(run_id: str) -> Path:
    for d in _all_run_dirs():
        if d.name == run_id:
            return d
    raise FileNotFoundError(f"corrida '{run_id}' no encontrada (ni temporal ni guardada)")


def save_version(run_id: str, name: str | None = None, note: str = "") -> dict:
    """Copia una corrida temporal a versions/<name>/ (lo único que sobrevive a la poda)."""
    src = find_run(run_id)
    name = re.sub(r"[^A-Za-z0-9_.-]+", "_", name or run_id) or run_id
    dst = VERSIONS / name
    if dst.exists() and dst != src:
        raise FileExistsError(f"ya existe versions/{name}")
    if dst != src:
        VERSIONS.mkdir(exist_ok=True)
        shutil.copytree(src, dst)  # incluye thumb.png (miniatura de la UI) si existe
        if src.parent != VERSIONS:  # la temporal queda marcada para no verse como duplicada en la galería
            rs = read_json(src / "run.json")
            rs["saved_as_version"] = dst.name
            (src / "run.json").write_text(json.dumps(rs, indent=1, ensure_ascii=False), encoding="utf-8")
    r = read_json(dst / "run.json")
    r.pop("saved_as_version", None)
    r["saved_from"] = src.name
    r.update(saved=True, saved_as=str(dst), id=dst.name, run_dir=str(dst), note=note or r.get("note", ""))
    r.setdefault("events", []).append({"t": _now(), "msg": f"Guardada como versión «{name}»"})
    (dst / "run.json").write_text(json.dumps(r, indent=1, ensure_ascii=False), encoding="utf-8")
    _bitacora(r, note=f"VERSIÓN GUARDADA versions/{name}" + (f": {note}" if note else ""))
    return {"saved_as": str(dst), "id": dst.name}


def prune_tmp(keep: int = KEEP_TMP, exclude: str = "") -> list[str]:
    """Borra las corridas temporales más viejas dejando `keep`. Las de versions/ no se tocan."""
    if not WORKDIR.exists():
        return []
    dirs = sorted((d for d in WORKDIR.iterdir() if d.is_dir() and d.name != exclude), key=lambda d: d.stat().st_mtime, reverse=True)
    gone = []
    for d in dirs[max(keep - 1, 0):]:
        shutil.rmtree(d, ignore_errors=True)
        gone.append(d.name)
    return gone


def _mark_orphan(d: Path, r: dict) -> dict:
    """Corrida que dice «running» sin candado: su proceso murió (p.ej. Detener mató el chat que la
    lanzó). Se marca como error para que no quede «Corriendo…» para siempre."""
    try:
        age = time.time() - datetime.fromisoformat(r.get("started", "")).timestamp()
    except ValueError:
        age = LOCK_MAX_AGE
    if age < 15:  # margen: el candado se toma antes de crear la carpeta, pero no cuesta nada esperar
        return r
    r.update(status="error", errors=(r.get("errors") or []) + ["Corrida interrumpida: el proceso que la lanzó terminó"])
    r.setdefault("events", []).append({"t": _now(), "msg": "Corrida interrumpida"})
    try:
        (d / "run.json").write_text(json.dumps(r, indent=1, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass
    return r


def list_runs(limit: int = 50, summary: bool = False) -> list[dict]:
    """summary=True: versión ligera para el sondeo de la UI (sin eventos, geometría ni lista de archivos)."""
    runs = []
    keys = ("id", "name", "started", "status", "seconds", "edits", "realized", "corrected",
            "errors", "warnings", "exports", "geometry", "events", "info", "run_dir", "note",
            "saved_as_version", "saved_from")
    lock = run_lock_info()
    for d in _all_run_dirs():
        try:
            r = read_json(d / "run.json")
        except (OSError, ValueError):
            continue
        if r.get("status") == "running" and (lock or {}).get("name") != r.get("name"):
            r = _mark_orphan(d, r)
        row = {k: r.get(k) for k in keys}
        if row["saved_as_version"] and not (VERSIONS / row["saved_as_version"] / "run.json").is_file():
            row["saved_as_version"] = None  # la versión se borró (o vive en otra carpeta): no anunciarla
        row["saved"] = d.parent == VERSIONS
        th = d / "thumb.png"  # miniatura que captura el visor de la UI; el mtime sirve de ?v= anti-caché
        row["thumb"] = int(th.stat().st_mtime) if th.is_file() else 0
        if summary:
            row["n_stl"] = sum(1 for g in r.get("geometry") or [] if g.get("kind") == "stl")
            row["n_files"] = sum(len(v) for v in (r.get("exports") or {}).values())
            for k in ("events", "geometry", "exports"):
                row.pop(k)
        runs.append(row)
    runs.sort(key=lambda r: (r.get("started") or "", r.get("id") or ""), reverse=True)
    return runs[:limit]


# ---------------------------------------------------------------- recipes
def recipe_search(query: str) -> list[dict]:
    RECIPES.mkdir(exist_ok=True)
    q = [w for w in re.split(r"[\s,;]+", query.lower()) if len(w) > 2]
    hits = []
    for f in sorted(RECIPES.glob("*.md")):
        text = f.read_text(encoding="utf-8")
        low = text.lower() + " " + f.name.lower()
        score = sum(1 for w in q if w in low)
        if score:  # ranking por palabras coincidentes: una consulta larga no debe dejar sin resultados
            lines = text.splitlines()
            hits.append({"file": f.name, "score": score, "head": lines[0] if lines else "",
                         "snippet": " ".join(l.strip() for l in lines[1:8] if l.strip())[:300]})
    hits.sort(key=lambda h: -h["score"])
    return hits[:10]


def recipe_save(name: str, body: str) -> str:
    RECIPES.mkdir(exist_ok=True)
    f = RECIPES / f"{name}.md"
    f.write_text(body, encoding="utf-8")
    return str(f)


# ---------------------------------------------------------------- MCP
def serve() -> None:
    try:  # mcp >= 2: FastMCP pasó a llamarse MCPServer (misma API de tool()/run())
        from mcp.server.mcpserver import MCPServer as FastMCP
    except ImportError:
        from mcp.server.fastmcp import FastMCP

    mcp = FastMCP("cfturbo")

    @mcp.tool()
    def cft_projects() -> list[dict]:
        """Proyectos base disponibles en projects/<nombre>/<nombre>.cft."""
        return list_projects()

    @mcp.tool()
    def cft_info(project: str) -> dict:
        """Punto de diseño (Q m3/h, H m, n rpm, nq), fluido, componentes y dimensiones principales
        de un proyecto (nombre en projects/ o ruta a un .cft, incluido un *_out.cft de una corrida)."""
        return project_info(project)

    @mcp.tool()
    def cft_params(project: str, filter: str = "", limit: int = 300) -> dict:
        """Alias editables con su valor actual y lista de hojas del XML cuya ruta cumpla `filter`
        (regex, sin distinguir mayúsculas). Úsalo para encontrar la ruta de un parámetro sin alias."""
        return list_params(project, filter, limit)

    @mcp.tool()
    def cft_run(project: str, edits: dict | None = None, name: str = "design",
                exports: list[str] | None = None, save: bool = True) -> dict:
        """Copia el proyecto a la carpeta temporal (<name>_<ts>/), aplica `edits` y corre CFturbo en batch.
        `project`: nombre en projects/ o ruta a un .cft (p.ej. el *_out.cft de una corrida, para iterar).
        edits: {clave: valor}. Claves: alias SI (Q m3/s, H m, n 1/s, rho, d2 b2 dS dH m, Psi, b2_d2,
        EtaH, nBl, AutoUpdate, volute_d_out), claves con unidad (Q_m3h, H_m, n_rpm, d2_mm, b2_mm,
        dS_mm, dH_mm, volute_d_out_mm), ext_outlet=False (quita la extensión CFD de salida del
        impulsor: arregla "Extension is overlapping neighboring component"; no usar si no hay
        componente aguas abajo) o un sufijo/regex de ruta del XML (ver cft_params), p.ej.
        "MeanSurface[Mean surface]/Coupled": False (arregla "Coupling partially deactivated" al cambiar nBl).
        REGLA: si la corrida que TÚ lanzas devuelve warnings/errors de geometría (solapamientos,
        intersecciones, extensiones), corrígelos en una nueva corrida antes de dar el resultado.
        Una corrida a la vez: si otra está en marcha falla con "CFturbo ocupado". exports: subconjunto de
        ["StarCCM", "OpenFOAM", "General"]; por defecto StarCCM (STEP + .cfturbo-ccm) y OpenFOAM (STL).
        Devuelve requested_si, realized, corrected (lo que CFturbo cambió), warnings, errors,
        exports, geometry y run_dir. Si CFturbo corrige un valor, decirlo al usuario."""
        return run_batch(project, edits, name, exports, save)

    @mcp.tool()
    def cft_runs(limit: int = 20) -> list[dict]:
        """Últimas corridas (temporales y versiones guardadas, campo `saved`), de la más reciente a la
        más antigua. Las temporales se podan solas: lo que importe, guardarlo con cft_save."""
        return list_runs(limit)

    @mcp.tool()
    def cft_save(run_id: str, name: str | None = None, note: str = "") -> dict:
        """Guarda una corrida como versión en versions/<name>/ (sobrevive a la poda) y la anota en la
        bitácora. Úsalo cuando el usuario diga que un diseño le sirve. `note`: por qué sirve."""
        return save_version(run_id, name, note)

    @mcp.tool()
    def cft_log(run_dir: str, tail: int = 80) -> str:
        """Últimas líneas del log de CFturbo de una corrida (ruta run_dir o id)."""
        d = Path(run_dir)
        if not d.exists():
            d = find_run(run_dir)
        f = d / "cfturbo.log"
        return "\n".join(f.read_text(encoding="utf-8", errors="replace").splitlines()[-tail:]) if f.exists() else "(sin log)"

    @mcp.tool()
    def cft_nq(Q_m3h: float, H_m: float, n_rpm: float) -> dict:
        """Velocidad específica nq y tipo de máquina orientativo para un punto de diseño."""
        return nq_calc(Q_m3h, H_m, n_rpm)

    @mcp.tool()
    def cft_recipe_search(query: str) -> list[dict]:
        """Biblioteca del proyecto: busca por palabras en las recetas y en la bitácora automática de
        corridas (recipes/bitacora.md). Consultar SIEMPRE antes de proponer un diseño."""
        return recipe_search(query)

    @mcp.tool()
    def cft_recipe_save(name: str, body: str) -> str:
        """Guarda un aprendizaje en recipes/<name>.md (primera línea: qué logra). Llamar cada vez que
        una combinación de parámetros funcione o se descubra algo de CFturbo: es la memoria del agente."""
        return recipe_save(name, body)

    mcp.run()


# ---------------------------------------------------------------- selftest
FAKE_CFT = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<CFturboFile Version="2026.1" Info="selftest">
  <CFturboProject Type="Object">
    <Version>2026.1.1.128</Version>
    <ProjectType Type="Enum">Pump</ProjectType>
    <DesignPoint_Pump Type="Object">
      <nRot Type="Float">60</nRot>
      <QFlow Type="Float">0.0630555555555556</QFlow>
      <Head Type="Float">70</Head>
      <FluidLiquid Type="Object" Name="Water (20°C)"><FluidRho Type="Float">998.2</FluidRho></FluidLiquid>
    </DesignPoint_Pump>
    <PolyList_CFturboDesign Type="Object">
      <CFturboDesign_Stator Type="Object" Name="[Stator_1]" Index="0"><Active Type="Boolean">True</Active><Caption>[Stator_1]</Caption></CFturboDesign_Stator>
      <CFturboDesign_RadialImpeller Type="Object" Name="[Impeller_1]" Index="1">
        <Active Type="Boolean">True</Active><Caption>[Impeller_1]</Caption>
        <MainDimensions Type="Object"><MainDimensionsElement Type="Object" Name="Version 1.">
          <Psi Type="Float">0.908</Psi><AutoUpdate Type="Boolean">False</AutoUpdate>
          <dH Type="Float">0.03725</dH><dS Type="Float">0.1227</dS><b2 Type="Float">0.02146</b2><d2 Type="Float">0.2063</d2>
        </MainDimensionsElement></MainDimensions>
        <BladeProperties Type="Object"><nBl Type="Integer">6</nBl></BladeProperties>
        <CFDSetup_RotSym Type="Object"><CFDSetup_RotSym_Extension_Outlet_Active Type="Boolean">True</CFDSetup_RotSym_Extension_Outlet_Active>
          <CFDSetup_RotSym_Extension_Outlet Type="Object"></CFDSetup_RotSym_Extension_Outlet></CFDSetup_RotSym>
      </CFturboDesign_RadialImpeller>
      <CFturboDesign_OutletVolute Type="Object" Name="[Volute_1]" Index="2"><Active Type="Boolean">True</Active><Caption>[Volute_1]</Caption>
        <SpiralCasingDiff Type="Object"><Diameter Type="Float">0.1</Diameter></SpiralCasingDiff></CFturboDesign_OutletVolute>
    </PolyList_CFturboDesign>
  </CFturboProject>
</CFturboFile>
"""

FAKE_CFTURBO = r'''
import sys, pathlib, shutil, xml.etree.ElementTree as ET
args = sys.argv[1:]
batch = pathlib.Path(args[args.index("-batch") + 1]); log = pathlib.Path(args[args.index("-log") + 1])
root = ET.parse(batch).getroot(); proj = root.find("CFturboBatchProject")
cft = pathlib.Path(proj.get("InputFile")); tree = ET.parse(cft)
# CFturbo real corrige valores imposibles: simulamos d2 > 0.3 -> 0.3
d2 = tree.getroot().find(".//MainDimensionsElement/d2")
if float(d2.text) > 0.3: d2.text = "0.3"
lines = ["x y [WARN]    BatchMode - Blade mean lines: 2: [Impeller_1]: Coupling partially deactivated."]
for a in proj.findall("BatchAction"):
    if a.get("Name") == "Export":
        wd = pathlib.Path(a.findtext("WorkingDir")); base = a.findtext("BaseFileName"); itf = a.findtext("ExportInterface")
        caps = [v.get("Caption") for v in a.iter("Value")]
        for i, c in enumerate(caps, 1):
            if itf == "StarCCM": (wd / f"{base}_Co{i}.stp").write_text("fake step")
            if itf == "OpenFOAM":
                for b in ("Hub", "Inflow"): (wd / f"{base}_Co{i}_{c}-Flowdomain-{b}.stl").write_text("solid fake\nendsolid")
        if itf == "StarCCM": (wd / f"{base}.cfturbo-ccm").write_text("<CFD-Pre/>")
        a.append(ET.Element("State")); a[-1].text = "success"
    if a.get("Name") == "Save":
        tree.write(a.findtext("OutputFile"), xml_declaration=True, encoding="UTF-8"); a.append(ET.Element("State")); a[-1].text = "success"
ET.ElementTree(root).write(cft.with_suffix(".cft-res"))
log.write_text("\n".join(lines) + "\n")
sys.exit(1)  # 1 = con avisos, como CFturbo
'''


def selftest() -> None:
    global WORKDIR, PROJECTS, RECIPES, VERSIONS, LOCK_FILE
    tmp = Path(tempfile.mkdtemp())
    WORKDIR, PROJECTS, RECIPES, VERSIONS = tmp / "work", tmp / "projects", tmp / "recipes", tmp / "versions"
    LOCK_FILE = tmp / "lock" / "running.lock"  # el selftest no debe tocar el candado real del PC
    (PROJECTS / "fake").mkdir(parents=True)
    (PROJECTS / "fake" / "fake.cft").write_text(FAKE_CFT, encoding="utf-8")
    fake = tmp / "fake_cfturbo.py"
    fake.write_text(FAKE_CFTURBO)
    # ponytail: el "exe" falso es python + script; en Windows real CFTURBO_EXE apunta a CFturbo.exe
    wrapper = tmp / ("fake.cmd" if os.name == "nt" else "fake.sh")
    if os.name == "nt":
        wrapper.write_text(f'@"{sys.executable}" "{fake}" %*\n')
    else:
        wrapper.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{fake}" "$@"\n')
        wrapper.chmod(0o755)
    os.environ["CFTURBO_EXE"] = str(wrapper)

    assert [p["name"] for p in list_projects()] == ["fake"]
    info = project_info("fake")
    assert abs(info["nq"]["nq"] - 37.3) < 0.5, info["nq"]
    assert info["dims"]["nBl"] == 6 and [c["caption"] for c in info["components"]] == ["[Stator_1]", "[Impeller_1]", "[Volute_1]"], info
    pr = list_params("fake", "nBl|d2$")
    assert pr["aliases"]["d2"]["value"] == "0.2063" and pr["total"] == 2, pr
    assert info["cfd_ext_outlet"] is True, info.get("cfd_ext_outlet")

    r = run_batch("fake", {"d2_mm": 220, "nBl": 7, "Q_m3h": 250, "AutoUpdate": True}, "t1")
    assert r["status"] == "warn" and r["returncode"] == 1, (r["status"], r["errors"])
    assert r["realized"]["d2_mm"] == "0.22" and r["realized"]["nBl"] == "7" and r["realized"]["AutoUpdate"] == "True", r["realized"]
    assert abs(float(r["realized"]["Q_m3h"]) - 250 / 3600) < 1e-9 and not r["corrected"], r
    assert r["exports"]["StarCCM"] == ["t1.cfturbo-ccm", "t1_Co1.stp", "t1_Co2.stp", "t1_Co3.stp"], r["exports"]
    assert len(r["geometry"]) == 6 and r["geometry"][0]["boundary"] in ("Hub", "Inflow"), r["geometry"]
    assert r["info"]["dims"]["d2_mm"] == 220.0 and r["actions"][0].startswith("Export StarCCM: "), r
    assert r["actions"][-1] == "Save: success", r["actions"]
    assert (Path(r["run_dir"]) / "run.json").exists() and r["events"][-1]["msg"] == "Corrida con avisos"

    r2 = run_batch("fake", {"d2_mm": 400}, "t2", exports=["StarCCM"])
    assert r2["corrected"]["d2_mm"] == ["0.4", "0.3"], r2["corrected"]  # corrección detectada
    r3 = run_batch("fake", {"noexiste": 1}, "t3")
    assert r3["status"] == "error" and "noexiste" in r3["errors"][0], r3
    assert [x["name"] for x in list_runs(2)] == ["t3", "t2"]
    assert _to_si("AutoUpdate", "false") == "False" and _to_si("x", "TRUE") == "True"

    # candado entre procesos: vivo -> CFturboBusy; muerto (pid inexistente) -> se limpia y corre
    lockf = LOCK_FILE
    assert run_lock_info() is None and not lockf.exists()
    lockf.parent.mkdir(parents=True, exist_ok=True)
    lockf.write_text(json.dumps({"pid": os.getpid(), "name": "otra", "t": time.time()}), encoding="utf-8")
    assert run_lock_info()["name"] == "otra"
    try:
        run_batch("fake", {}, "bloqueada", exports=[])
        raise AssertionError("debió fallar con CFturboBusy")
    except CFturboBusy as e:
        assert "otra" in str(e)
    # el candado es global: otro WORKDIR (otro proceso, p.ej. el Explorador) también queda bloqueado
    wd0 = WORKDIR
    WORKDIR = tmp / "otro_workdir"
    try:
        run_batch("fake", {}, "otro_wd", exports=[])
        raise AssertionError("otro WORKDIR debió ver el candado")
    except CFturboBusy:
        pass
    WORKDIR = wd0
    # la UI toma el candado antes de responder y se lo pasa a run_batch, que lo libera al terminar
    lockf.unlink()
    lk = acquire_lock("ui run")
    assert run_lock_info()["name"] == "ui_run"
    assert run_batch("fake", {"ext_outlet": False}, "ui_run", exports=[], lock=lk)["realized"]["ext_outlet"] == "False"
    assert not lockf.exists()
    assert project_info(str(Path(list_runs(1)[0]["run_dir"]) / "ui_run_out.cft"))["cfd_ext_outlet"] is False
    # corrida «running» sin candado (su proceso murió) -> error «interrumpida»; con candado sigue corriendo
    orphan = WORKDIR / "huerfana_1"
    orphan.mkdir()
    (orphan / "run.json").write_text(json.dumps({"id": "huerfana_1", "name": "huerfana", "status": "running",
                                                 "started": "2026-01-01T00:00:00.000"}), encoding="utf-8")
    assert [x for x in list_runs() if x["id"] == "huerfana_1"][0]["status"] == "error"
    assert "interrumpida" in read_json(orphan / "run.json")["errors"][0]
    shutil.rmtree(orphan)
    lockf.write_text(json.dumps({"pid": 2 ** 30, "name": "muerta", "t": time.time()}), encoding="utf-8")
    assert run_batch("fake", {}, "tras_muerta", exports=[])["status"] in ("ok", "warn")
    assert not lockf.exists() and run_lock_info() is None
    assert nq_calc(227, 70, 3600)["tipo"] == "radial normal"

    # versiones y poda: t1 guardada sobrevive, las temporales se reducen a KEEP
    # miniatura de la UI: list_runs la anuncia y save_version la copia con la versión
    (Path(r["run_dir"]) / "thumb.png").write_bytes(b"\x89PNG\r\n\x1a\nfake")
    assert [x for x in list_runs() if x["id"] == r["id"]][0]["thumb"] > 0
    lite = list_runs(summary=True)[0]
    assert "events" not in lite and "geometry" not in lite and "n_stl" in lite and "thumb" in lite, lite
    sv = save_version(r["id"], "bomba_v1", note="sirve")
    assert (VERSIONS / "bomba_v1" / "run.json").exists() and sv["id"] == "bomba_v1"
    assert (VERSIONS / "bomba_v1" / "thumb.png").read_bytes().startswith(b"\x89PNG")
    assert read_json(Path(r["run_dir"]) / "run.json")["saved_as_version"] == "bomba_v1"
    assert read_json(VERSIONS / "bomba_v1" / "run.json")["saved_from"] == r["id"]
    assert [x for x in list_runs() if x["saved"]][0]["id"] == "bomba_v1"
    assert [x for x in list_runs() if x["saved"]][0]["thumb"] > 0
    for i in range(KEEP_TMP + 2):
        run_batch("fake", {}, f"p{i}", exports=[])
    assert len([d for d in WORKDIR.iterdir() if d.is_dir()]) == KEEP_TMP, list(WORKDIR.iterdir())
    assert (VERSIONS / "bomba_v1").exists()
    bit = (RECIPES / "bitacora.md").read_text(encoding="utf-8")
    assert "VERSIÓN GUARDADA versions/bomba_v1" in bit and "| t1 |" in bit and "| t3 |" not in bit, bit

    # «★ como X» colgante: si la versión se borra, list_runs deja de anunciarla (D-N6)
    for v, expect in (("bomba_v1", "bomba_v1"), ("borrada", None)):
        dd = WORKDIR / f"marcada_{v}"
        dd.mkdir()
        (dd / "run.json").write_text(json.dumps({"id": dd.name, "name": dd.name, "status": "ok", "saved_as_version": v}), encoding="utf-8")
        assert [x for x in list_runs(100) if x["id"] == dd.name][0]["saved_as_version"] == expect, v
        shutil.rmtree(dd)
    recipe_save("prueba-d2", "# sube d2 para más altura\nd2 +10% => H +20%")
    assert recipe_search("altura d2")[0]["file"] == "prueba-d2.md"
    assert any(h["file"] == "bitacora.md" for h in recipe_search("bomba_v1"))
    shutil.rmtree(tmp)
    print("selftest OK")


if __name__ == "__main__":
    selftest() if "--selftest" in sys.argv else serve()
