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


def _get_ext_outlet(root: ET.Element) -> str:
    return root.find(".//CFDSetup_RotSym_Extension_Outlet_Active").text.strip()


# ---------------------------------------------------------------- ángulos y espesor de álabe
# BladeProperties/BladePropsArray[BladeValues]/BladePropsML[Main blade]/Beta1|Beta2|s1|s2: arrays Count=5
# (spans cubo→corona) de los que el .cft solo guarda los índices 0 (cubo) y Count-1 (corona); radianes y m.
# AutoUpdate1/2 = True: CFturbo recalcula βB1/βB2 solo. Para fijar un ángulo hay que ponerlos en False.
_IMPS = ("CFturboDesign_RadialImpeller", "CFturboDesign_AxialImpeller")


def _blade_mls(root: ET.Element) -> list[tuple[ET.Element, ET.Element]]:
    """(BladeProperties, BladePropsML) de cada álabe (principal y divisores) de los impulsores."""
    out = []
    for imp in (e for e in root.iter() if e.tag in _IMPS):
        bp = imp.find("BladeProperties")
        if bp is not None:
            out += [(bp, ml) for ml in bp.iter("BladePropsML")]
    return out


def _span_vals(arr: ET.Element) -> list[tuple[int, ET.Element]]:
    return sorted(((int(v.get("Index", 0)), v) for v in arr.findall("Value")), key=lambda x: x[0])


def _pair(v) -> list[float]:
    """Número (todos los spans), lista [cubo, corona] o su texto JSON -> [cubo, corona]."""
    if isinstance(v, str):
        v = json.loads(v.replace(";", ",")) if v.strip().startswith("[") else float(v.replace(",", "."))
    if isinstance(v, (int, float)):
        return [float(v), float(v)]
    if len(v) != 2:
        raise KeyError("se espera un número o [cubo, corona]")
    return [float(v[0]), float(v[1])]


def _write_span(arr: ET.Element, hub: float, shr: float) -> None:
    n = int(arr.get("Count", 5)) - 1 or 1
    for i, v in _span_vals(arr):  # índices intermedios (si los hay) por interpolación lineal, como CFturbo
        v.text = repr(hub + (shr - hub) * i / n)


def _read_span(arr: ET.Element | None) -> list[float] | None:
    if arr is None:
        return None
    vals = _span_vals(arr)
    return [float(vals[0][1].text), float(vals[-1][1].text)] if vals else None


def _main_ml(root: ET.Element):
    mls = _blade_mls(root)
    return next(((bp, ml) for bp, ml in mls if ml.get("Name") == "Main blade"), mls[0] if mls else (None, None))


def blade_info(root: ET.Element) -> dict:
    """βB1/βB2 cubo/corona en grados, espesor en mm y si los ángulos son automáticos (álabe principal)."""
    bp, ml = _main_ml(root)
    if ml is None:
        return {}
    deg = lambda p: [round(math.degrees(x), 3) for x in p] if p else [None, None]  # noqa: E731
    b1, b2 = deg(_read_span(ml.find("Beta1"))), deg(_read_span(ml.find("Beta2")))
    s = [float(v.text) for a in ("s1", "s2") if ml.find(a) is not None for _, v in _span_vals(ml.find(a))]
    return {"beta1_hub_deg": b1[0], "beta1_shroud_deg": b1[1], "beta2_hub_deg": b2[0], "beta2_shroud_deg": b2[1],
            "s_mm": round(sum(s) / len(s) * 1000, 4) if s else None,
            "beta_auto1": (bp.findtext("AutoUpdate1") or "").strip() == "True",
            "beta_auto2": (bp.findtext("AutoUpdate2") or "").strip() == "True"}


def _beta_setter(k: int):
    def setter(root: ET.Element, v) -> str:
        hub, shr = _pair(v)
        mls = _blade_mls(root)
        if not mls:
            raise KeyError(f"beta{k}_deg: el proyecto no tiene BladePropsML")
        for bp, ml in mls:
            arr = ml.find(f"Beta{k}")
            if arr is not None:
                _write_span(arr, math.radians(hub), math.radians(shr))
            au = bp.find(f"AutoUpdate{k}")
            if au is not None:
                au.text = "False"  # con True CFturbo pisa el ángulo pedido
        return json.dumps([round(hub, 3), round(shr, 3)])
    return setter


def _beta_getter(k: int):
    def getter(root: ET.Element) -> str:
        b = blade_info(root)
        return json.dumps([b[f"beta{k}_hub_deg"], b[f"beta{k}_shroud_deg"]])
    return getter


def _set_beta_auto(root: ET.Element, on) -> str:
    on = str(on).lower() in ("true", "1", "yes", "si", "sí")
    for bp, _ in _blade_mls(root):
        for k in ("AutoUpdate1", "AutoUpdate2"):
            if bp.find(k) is not None:
                bp.find(k).text = "True" if on else "False"
    return "True" if on else "False"


def _get_beta_auto(root: ET.Element) -> str:
    b = blade_info(root)
    return "True" if b.get("beta_auto1") and b.get("beta_auto2") else "False"


def _set_thickness(root: ET.Element, v) -> str:
    hub, shr = _pair(v)
    mls = _blade_mls(root)
    if not mls:
        raise KeyError("s_mm: el proyecto no tiene BladePropsML")
    for _, ml in mls:
        for a in ("s1", "s2"):  # s1 = borde de ataque, s2 = borde de salida
            if ml.find(a) is not None:
                _write_span(ml.find(a), hub / 1000, shr / 1000)
    return json.dumps([round(hub, 4), round(shr, 4)])


def _get_thickness(root: ET.Element) -> str:
    _, ml = _main_ml(root)
    p = _read_span(ml.find("s1")) if ml is not None else None
    return json.dumps([round(x * 1000, 4) for x in p]) if p else "null"


# Claves especiales de `edits` que hacen algo más que cambiar una hoja: (aplicar, leer lo realizado)
SPECIAL = {"ext_outlet": (_set_ext_outlet, _get_ext_outlet),
           "beta1_deg": (_beta_setter(1), _beta_getter(1)), "beta2_deg": (_beta_setter(2), _beta_getter(2)),
           "beta_auto": (_set_beta_auto, _get_beta_auto), "s_mm": (_set_thickness, _get_thickness)}


def _differs(req: str, real: str) -> bool:
    """¿CFturbo cambió lo pedido? Números con tolerancia relativa, listas [cubo, corona] con 0,01,
    texto/booleanos sin distinguir mayúsculas (CFturbo escribe False/True)."""
    try:
        a, b = json.loads(req), json.loads(real)
        if isinstance(a, list) and isinstance(b, list):
            return len(a) != len(b) or any(x is None or y is None or abs(x - y) > 0.01 for x, y in zip(a, b))
    except (ValueError, TypeError):
        pass
    try:
        return abs(float(real) - float(req)) > 1e-9 * max(1.0, abs(float(real)))
    except ValueError:
        return real.lower() != str(req).lower()


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
            **blade_info(root),
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
# STL de OpenFOAM: <base>_Co<i>_<caption>[Extension]-[CFD]Flowdomain[(virtual)]-<frontera>.stl, con caption
# entre corchetes ([Impeller_1]) o sin ellos (Impeller, RadialImpeller, Stator_1) según el ejemplo de origen.
_STL_RX = re.compile(r"_Co(\d+)_\[?(.+?)\]?(Extension)?-(?:CFD)?Flowdomain(?:\(virtual\))?-(\w+)\.stl$", re.I)


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


# ---------------------------------------------------------------- curvas (PerformanceData) y reporte (Report)
def parse_perf(f: Path, design: dict | None = None) -> dict | None:
    """<base>.cft-pp (XML <Characteristic><Curve Name Desc><Points><Value><x/><y/>) -> curvas H-Q, η-Q, P-Q.
    CFturbo 2026.1.1 da «Δpt - ṁ» (bar vs kg/s) y «η - ṁ» (% vs kg/s): se pasan a Q m³/h, H m, η %, P kW
    (P = ρ·g·Q·H/η, potencia al eje estimada). Curvas que no se reconocen quedan en `others` por nombre."""
    try:
        root = ET.parse(f).getroot()
    except (OSError, ET.ParseError):
        return None
    design = design or {}
    rho = design.get("rho") or 998.2
    curves, others = {}, []
    for c in root.iter("Curve"):
        pts = []
        for v in c.iter("Value"):
            try:
                pts.append((float(v.findtext("x")), float(v.findtext("y"))))
            except (TypeError, ValueError):
                continue
        name, desc = c.get("Name") or "", c.get("Desc") or ""
        key = ("dpt" if re.search(r"pressure|Δp|dp", desc + name, re.I) else
               "eta" if re.search(r"effic|η", desc + name, re.I) else
               "npsh" if re.search(r"npsh", desc + name, re.I) else None)
        if key and key not in curves and pts:
            curves[key] = pts
        others.append({"name": name, "desc": desc, "n": len(pts), "used": key is not None})
    if "dpt" not in curves:
        return {"names": others} if others else None
    xs = [x for x, _ in curves["dpt"]]
    Q = [x / rho * 3600 for x in xs]
    # unidad de Δpt: bar en 2026.1.1; si hay altura de diseño se elige el factor (bar, kPa, Pa) que la reproduce
    fac = 1e5
    if design.get("Q_m3h") and design.get("H_m"):
        def h_at(f_):
            i = min(range(len(Q)), key=lambda j: abs(Q[j] - design["Q_m3h"]))
            return curves["dpt"][i][1] * f_ / (rho * G)
        fac = min((1e5, 1e3, 1.0), key=lambda f_: abs(math.log(max(h_at(f_), 1e-12) / design["H_m"])))
    H = [y * fac / (rho * G) for _, y in curves["dpt"]]
    out = {"Q_m3h": [round(q, 3) for q in Q], "H_m": [round(h, 3) for h in H], "names": others,
           "design": {"Q_m3h": design.get("Q_m3h"), "H_m": design.get("H_m")}}
    if "eta" in curves and len(curves["eta"]) == len(xs):
        eta = [y for _, y in curves["eta"]]
        if max(eta) <= 1.5:  # fracción -> %
            eta = [e * 100 for e in eta]
        out["eta_pct"] = [round(e, 3) for e in eta]
        out["P_kW"] = [round(rho * G * q / 3600 * h / (e / 100) / 1000, 3) if e > 0.5 else None
                       for q, h, e in zip(Q, H, eta)]
    if "npsh" in curves and len(curves["npsh"]) == len(xs):
        out["NPSH_m"] = [round(y, 3) for _, y in curves["npsh"]]
    return out


def _report_rows(html: str) -> list[tuple[tuple[str, ...], str, str, str, str]]:
    """Tabla del reporte HTML -> (ruta de cabeceras, etiqueta, símbolo, unidad, valor). La profundidad la dan
    las celdas vacías (&nbsp;) del principio de cada fila; las filas de una sola celda son cabeceras."""
    import html as _html
    rows, stack = [], []
    for tr in re.findall(r"(?is)<tr[^>]*>(.*?)</tr>", html):
        cells = [_html.unescape(re.sub(r"(?is)<br\s*/?>", " ", re.sub(r"(?s)<(?!br)[^>]+>", "", c))).replace("\xa0", " ").strip()
                 for c in re.findall(r"(?is)<td[^>]*>(.*?)</td>", tr)]
        cells = [re.sub(r"\s+", " ", c) for c in cells]
        depth = 0
        while depth < len(cells) and not cells[depth]:
            depth += 1
        rest = cells[depth:]
        if not rest:
            continue
        if len(rest) == 1 or not any(rest[1:]):
            stack = stack[:depth] + [rest[0]]
            continue
        rest += [""] * (4 - len(rest))
        rows.append((tuple(stack[:depth]), rest[0], rest[1], rest[2], rest[3]))
    return rows


def _num(s: str):
    """'20.7' -> 20.7 · '[20.7, 17.2]' -> [20.7, 17.2] · '4.77 .. 10.06' -> [4.77, 10.06] · otro -> texto."""
    s = s.strip()
    nums = re.findall(r"-?\d+(?:\.\d+)?(?:E[-+]?\d+)?", s, re.I)
    if not nums:
        return s or None
    vals = [float(x) for x in nums]
    return vals[0] if len(vals) == 1 and not s.startswith("[") else vals


def parse_report(f: Path) -> dict | None:
    """Valores clave del reporte de diseño (export «Report» -> <base>.html, una tabla). Del impulsor: βB1/βB2
    [cubo, corona], envolvente Δφ, área de garganta, w2/w1 [cubo, corona], ηh/ηv/ηm/η etapa, NPSHR por
    correlación, cu2/cm2/u2, potencia y par; de la voluta, el área de garganta de la lengua."""
    try:
        rows = _report_rows(f.read_text(encoding="utf-8-sig", errors="replace"))
    except OSError:
        return None
    comp = lambda r: r[0][0] if r[0] else ""  # noqa: E731  «2: [Impeller_1]»
    imp = [r for r in rows if re.search(r"impeller|rotor", comp(r), re.I)]
    vol = [r for r in rows if re.search(r"volute", comp(r), re.I)]

    def first(rs, label, under=None, sym=None, last=False):
        hits = [r for r in rs if r[1] == label and (under is None or under in r[0]) and (sym is None or r[2] == sym)]
        return _num((hits[-1] if last else hits[0])[4]) if hits else None

    rep = {
        "beta1_deg": first(imp, "Blade angle leading edge", "Blade properties"),
        "beta2_deg": first(imp, "Blade angle trailing edge", "Blade properties"),
        "wrap_deg": first(imp, "Wrap angle", "Blade mean lines", "Δφ"),
        "throat_mm2": first(imp, "Cross section area", "Throat", last=True),
        "w2_w1": [first(imp, "Rel. deceleration hub"), first(imp, "Rel. deceleration shroud")],
        "eta_h_pct": first(imp, "Hydraulic efficiency", sym="ηh"),
        "eta_v_pct": first(imp, "Volumetric efficiency", sym="ηv"),
        "eta_m_pct": first(imp, "Mechanical efficiency", sym="ηm"),
        "eta_st_pct": first(imp, "Stage efficiency", sym="ηSt"),
        "cu2": first(imp, "Abs. circumferential velocity", "Outlet - Velocity triangle"),
        "cm2": first(imp, "Meridional velocity", "Outlet - Velocity triangle"),
        "u2": first(imp, "Peripheral speed", "Outlet - Velocity triangle"),
        "P_kW": first(imp, "Required driving power"),
        "torque_Nm": first(imp, "Torque", "Power"),
        "npsha_m": first(imp, "(Available at inlet)"),
        "npshr_m": {r[1]: _num(r[4]) for r in imp if r[2] == "NPSHR"} or None,
        "volute_throat_mm2": first(vol, "Throat area"),
    }
    if rep["w2_w1"] == [None, None]:
        rep["w2_w1"] = None
    return {k: v for k, v in rep.items() if v is not None} or None


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
    if "PerformanceData" not in exports:  # curvas características: siempre (28 KB, no cuesta tiempo)
        exports.append("PerformanceData")
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
                res["requested_si"][k] = SPECIAL[k][0](tree.getroot(), v)
                continue
            p, e = _resolve(leaves, k)
            e.text = _to_si(k, v)
            res["requested_si"][k] = e.text
    except (KeyError, ValueError, TypeError) as err:
        res.update(status="error", errors=[f"parámetro no encontrado o valor inválido: {err}"], seconds=0)
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
                "General": ["*.geo-xml", "*.stp", "*.igs", "*.stl"], "Report": ["*.html"],
                "PerformanceData": ["*.cft-pp"]}.get(x, ["*"])
        res["exports"][x] = sorted({f.name for pt in pats for f in run_dir.glob(pt)})
    res["geometry"] = _geometry(run_dir)
    n_files = sum(len(v) for v in res["exports"].values())
    ev(f"Exportados {n_files} archivos" if n_files else "Sin archivos exportados")
    if out_cft and out_cft.exists():
        out_root = ET.parse(out_cft).getroot()
        lv = _leaves(out_root)
        for k in edits:
            try:
                real = SPECIAL[k][1](out_root) if k in SPECIAL else _resolve(lv, k)[1].text.strip()
            except (KeyError, AttributeError, IndexError):
                continue
            res["realized"][k] = real
            if _differs(res["requested_si"][k], real):
                res["corrected"][k] = [res["requested_si"][k], real]
        try:
            res["info"] = project_info(str(out_cft))
        except Exception as err:  # ponytail: info es cortesía, no debe tumbar la corrida
            res["info_error"] = str(err)
    dp = (res.get("info") or {}).get("design_point") or {}
    curves = parse_perf(run_dir / f"{name}.cft-pp", dp)
    if curves:
        res["curves"] = curves
    if (run_dir / f"{name}.html").exists():
        res["report"] = parse_report(run_dir / f"{name}.html")
        res["report_file"] = f"{name}.html"
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
    dims = ", ".join(f"{k} {round(v, 2) if isinstance(v, float) else v}" for k, v in (("d2", d.get("d2_mm")), ("b2", d.get("b2_mm")), ("nBl", d.get("nBl")),
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


def delete_run(run_id: str) -> dict:
    """Borra una corrida temporal o una versión guardada (carpeta entera). No borra la que está corriendo.
    Si era versión, la anota en la bitácora; la temporal de origen deja de anunciar «★ como X» sola."""
    d = find_run(run_id)
    r = {}
    try:
        r = read_json(d / "run.json")
    except (OSError, ValueError):
        pass
    lock = run_lock_info()
    if r.get("status") == "running" and lock and lock.get("name") == r.get("name"):
        raise CFturboBusy(f"«{run_id}» está corriendo; espera a que termine")
    version = d.parent.resolve() == VERSIONS.resolve()
    shutil.rmtree(d)
    if d.exists():
        raise OSError(f"no pude borrar {d} (¿archivo abierto?)")
    if version:
        _bitacora(r or {"name": run_id}, note=f"VERSIÓN BORRADA versions/{d.name}")
    return {"deleted": d.name, "version": version, "path": str(d)}


# ---------------------------------------------------------------- bomba nueva por semejanza (explora/desde_cero.py)
def _desde_cero():
    """Prototipo del Explorador (recipes/exploracion-desde-cero.md), cargado como módulo sin tocar sys.path.
    Su ROOT apunta a la carpeta que contiene PROJECTS (el selftest la cambia)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("desde_cero", HERE / "explora" / "desde_cero.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.ROOT = PROJECTS.parent
    return mod


_CANDS: dict = {}


def pump_bases() -> list[dict]:
    """Bases para una bomba nueva (ejemplos de CFturbo + projects/*/*.cft con impulsor) con su nq.
    Leerlas cuesta ~1 s (XML de 0,2–1 MB): se cachea por lista de archivos y mtime."""
    dc = _desde_cero()
    paths = [p for p in list(dc.BASES) + sorted(PROJECTS.glob("*/*.cft")) if p.exists()]
    key = tuple((str(p), p.stat().st_mtime) for p in paths)
    if _CANDS.get("key") != key:
        _CANDS.update(key=key, val=dc.candidatos())
    return _CANDS["val"]


def suggest_base(Q_m3h: float, H_m: float, n_rpm: float, base: str | None = None) -> dict:
    """Base más cercana en nq (o la pedida), factor de escala k y aviso si el salto de nq es > ×1,5."""
    nq = n_rpm * math.sqrt(Q_m3h / 3600) / H_m ** 0.75
    cands = pump_bases()
    b = next((c for c in cands if c["cft"] == base or Path(c["cft"]).stem == base), None) if base else         min(cands, key=lambda c: abs(math.log(nq / c["nq"])), default=None)
    if b is None:
        raise FileNotFoundError(f"no hay base {'«' + base + '»' if base else 'disponible'}")
    ratio = nq / b["nq"]
    return {"nq": round(nq, 1), "tipo": nq_calc(Q_m3h, H_m, n_rpm)["tipo"], "base": b["cft"],
            "base_name": Path(b["cft"]).stem, "nq_base": b["nq"], "ratio": round(ratio, 2),
            "k": round((b["n_rpm"] / n_rpm) * math.sqrt(H_m / b["H_m"]), 4),
            "aviso": (f"nq {nq:.1f} lejos de la base (nq {b['nq']}, ×{max(ratio, 1 / ratio):.2f}): fuera de lo "
                      "probado (×1,5). Mejor crear una base en la GUI para esa banda.") if abs(math.log(ratio)) > math.log(1.5) else None,
            "bases": [{"name": Path(c["cft"]).stem, "cft": c["cft"], "nq": c["nq"]} for c in cands]}


def new_project(Q_m3h: float, H_m: float, n_rpm: float, name: str, base: str | None = None) -> dict:
    """Crea projects/<name>/<name>.cft escalando por semejanza la base más cercana en nq (no corre CFturbo)."""
    name = re.sub(r"[^A-Za-z0-9_-]+", "_", name or "").strip("_")
    if not name:
        raise ValueError("falta el nombre del proyecto")
    if not (Q_m3h > 0 and H_m > 0 and n_rpm > 0):
        raise ValueError("Q, H y n deben ser positivos")
    dst = PROJECTS / name / f"{name}.cft"
    if dst.parent.exists():
        raise FileExistsError(f"ya existe projects/{name}")
    sug = suggest_base(Q_m3h, H_m, n_rpm, base)
    try:
        out = _desde_cero().preparar(Q_m3h, H_m, n_rpm, dst, sug["base"])
    except Exception:
        shutil.rmtree(dst.parent, ignore_errors=True)
        raise
    _CANDS.clear()
    out.update(name=name, base_name=sug["base_name"], tipo=sug["tipo"], aviso=sug["aviso"], ratio=sug["ratio"])
    return out


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
            "saved_as_version", "saved_from", "report", "report_file")  # curvas: solo en run.json
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
            for k in ("events", "geometry", "exports", "report"):
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
        (d2, b2, dS, dH, Psi, nBl, βB1/βB2 cubo y corona en grados, espesor s_mm, beta_auto1/2) de un proyecto (nombre en projects/ o ruta a un .cft, incluido un *_out.cft de una corrida)."""
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
        Álabe: beta1_deg / beta2_deg = número (todos los spans) o [cubo, corona] en grados (fija el ángulo:
        pone BladeProperties/AutoUpdate1|2=False, si no CFturbo lo recalcula); beta_auto=True vuelve a ángulos
        automáticos; s_mm = espesor (número o [cubo, corona]) en LE y TE.
        REGLA: si la corrida que TÚ lanzas devuelve warnings/errors de geometría (solapamientos,
        intersecciones, extensiones), corrígelos en una nueva corrida antes de dar el resultado.
        Una corrida a la vez: si otra está en marcha falla con "CFturbo ocupado". exports: subconjunto de
        ["StarCCM", "OpenFOAM", "General", "Report"]; por defecto StarCCM (STEP + .cfturbo-ccm) y OpenFOAM
        (STL). "Report" añade el reporte de diseño <name>.html y su resumen en `report` (βB1/βB2, Δφ,
        garganta, w2/w1, ηh/ηv/ηm, NPSHR, cu2/cm2). Siempre se exportan las curvas (PerformanceData) ->
        `curves` (Q_m3h, H_m, eta_pct, P_kW; predicción 1D de CFturbo, no CFD).
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
    def cft_delete(run_id: str) -> dict:
        """Borra una corrida temporal o una versión guardada (carpeta entera, no se puede deshacer). Solo si
        el usuario lo pide expresamente. No borra la que está corriendo."""
        return delete_run(run_id)

    @mcp.tool()
    def cft_new(Q_m3h: float, H_m: float, n_rpm: float, name: str, base: str | None = None,
                run: bool = True) -> dict:
        """Bomba nueva para un punto de diseño sin pasar por la GUI: escala por semejanza el ejemplo de CFturbo
        (o proyecto de projects/) con nq más cercano y crea projects/<name>/<name>.cft (aparece en cft_projects).
        `base`: nombre o ruta de la base (por defecto la más cercana en nq). Si run, corre CFturbo una vez
        (<name>_1) para validar. `aviso` si el nq queda a más de ×1,5 del de la base. La forma (ángulos,
        relación de cubo, nº de álabes) es la del ejemplo: es un punto de partida, después iterar con cft_run."""
        out = new_project(Q_m3h, H_m, n_rpm, name, base)
        if run:
            r = run_batch(out["name"], {}, f"{out['name']}_1")
            d = (r.get("info") or {}).get("dims") or {}
            out.update(run_id=r["id"], status=r["status"], warnings=r["warnings"], errors=r["errors"],
                       d2_mm_cfturbo=d.get("d2_mm"), run_dir=r["run_dir"])
        return out

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
        <BladeProperties Type="Object"><nBl Type="Integer">6</nBl>
          <AutoUpdate1 Type="Boolean">True</AutoUpdate1><AutoUpdate2 Type="Boolean">True</AutoUpdate2>
          <BladePropsArray Type="Object" Name="BladeValues"><BladePropsML Type="Object" Name="Main blade" Index="0">
            <s1 Count="5" Type="Array1"><Value Type="Float" Index="0">0.0031</Value><Value Type="Float" Index="4">0.0031</Value></s1>
            <s2 Count="5" Type="Array1"><Value Type="Float" Index="0">0.0031</Value><Value Type="Float" Index="4">0.0031</Value></s2>
            <Beta1 Count="5" Type="Array1"><Value Type="Float" Index="0">0.360726262380079</Value><Value Type="Float" Index="4">0.300924941996874</Value></Beta1>
            <Beta2 Count="5" Type="Array1"><Value Type="Float" Index="0">0.566273602266752</Value><Value Type="Float" Index="4">0.400868459859807</Value></Beta2>
          </BladePropsML></BladePropsArray></BladeProperties>
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
# ángulos automáticos: con AutoUpdate2=True CFturbo recalcula βB2 (aquí: lo deja en 32,4° en el cubo)
bp = tree.getroot().find(".//BladeProperties")
if bp.findtext("AutoUpdate2") == "True": bp.find(".//Beta2/Value").text = "0.566273602266752"
PP = ('<CFturboPerformancePredictionFile><Characteristic>'
      '<Curve Name="Δpt - ṁ" Desc="Total pressure diff. versus Mass flow"><Points Count="3">%s</Points></Curve>'
      '<Curve Name="η - ṁ" Desc="Efficiency versus Mass flow"><Points Count="3">%s</Points></Curve>'
      '</Characteristic></CFturboPerformancePredictionFile>')
pt = lambda pts: "".join(f'<Value Index="{i}"><x>{x}</x><y>{y}</y></Value>' for i, (x, y) in enumerate(pts))
HTML = ('<table><tr><td>2: [Impeller_1]</td></tr><tr><td>&nbsp;</td><td>Blade properties</td></tr>'
        '<tr><td>&nbsp;</td><td>&nbsp;</td><td>Blade angle leading edge</td><td>βB1</td><td>[°]</td><td>[20.7, 17.2]</td></tr>'
        '<tr><td>&nbsp;</td><td>&nbsp;</td><td>Blade angle trailing edge</td><td>βB2</td><td>[°]</td><td>[32.4, 23]</td></tr>'
        '<tr><td>&nbsp;</td><td>Efficiency</td></tr>'
        '<tr><td>&nbsp;</td><td>&nbsp;</td><td>Hydraulic efficiency</td><td>ηh</td><td>[%]</td><td>92.1</td></tr>'
        '<tr><td>&nbsp;</td><td>&nbsp;</td><td>Gülich</td><td>NPSHR</td><td>[m]</td><td>4.77 .. 10.06</td></tr>'
        '<tr><td>3: [Volute_1]</td></tr><tr><td>&nbsp;</td><td>Throat area</td><td>A</td><td>[mm²]</td><td>4760.8</td></tr></table>')
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
        if itf == "PerformanceData":  # 63 kg/s ≈ 227 m³/h; 6,86 bar ≈ 70 m
            (wd / f"{base}.cft-pp").write_text(PP % (pt([(12.6, 10.08), (62.9, 6.855), (125.9, 2.19)]), pt([(12.6, 32.7), (62.9, 86.6), (125.9, 48.3)])), encoding="utf-8")
        if itf == "Report": (wd / f"{base}.html").write_text(HTML, encoding="utf-8")
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
    fake.write_text(FAKE_CFTURBO, encoding="utf-8")
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
    dm = info["dims"]
    assert (round(dm["beta1_hub_deg"], 1), round(dm["beta2_shroud_deg"], 1), dm["s_mm"]) == (20.7, 23.0, 3.1), dm
    assert dm["beta_auto1"] and dm["beta_auto2"], dm
    # _STL_RX: captions con y sin corchetes, Flowdomain(virtual), extensiones CFD (ejemplos CP nq8/20/31, MP, AP)
    for fn, comp, bnd in (("x_Co2_[Impeller_1]-Flowdomain-Hub.stl", "Impeller_1", "Hub"),
                          ("x_Co2_Impeller-Flowdomain(virtual)-BladePS.stl", "Impeller", "BladePS"),
                          ("x_Co1_RadialImpeller-Flowdomain-Shroud.stl", "RadialImpeller", "Shroud"),
                          ("x_Co1_Stator_1-Flowdomain(virtual)-RSIConnectionOutHub.stl", "Stator_1", "RSIConnectionOutHub"),
                          ("x_Co3_[Volute_1]Extension-CFDFlowdomain-Walls.stl", "Volute_1 ext", "Walls"),
                          ("x_Co2_ImpellerExtension-CFDFlowdomain-Outflow.stl", "Impeller ext", "Outflow")):
        m = _STL_RX.search(fn)
        assert m and (m.group(2) + (" ext" if m.group(3) else ""), m.group(4)) == (comp, bnd), (fn, m and m.groups())

    r = run_batch("fake", {"d2_mm": 220, "nBl": 7, "Q_m3h": 250, "AutoUpdate": True}, "t1")
    assert r["status"] == "warn" and r["returncode"] == 1, (r["status"], r["errors"])
    assert r["realized"]["d2_mm"] == "0.22" and r["realized"]["nBl"] == "7" and r["realized"]["AutoUpdate"] == "True", r["realized"]
    assert abs(float(r["realized"]["Q_m3h"]) - 250 / 3600) < 1e-9 and not r["corrected"], r
    assert r["exports"]["StarCCM"] == ["t1.cfturbo-ccm", "t1_Co1.stp", "t1_Co2.stp", "t1_Co3.stp"], r["exports"]
    assert len(r["geometry"]) == 6 and r["geometry"][0]["boundary"] in ("Hub", "Inflow"), r["geometry"]
    assert r["info"]["dims"]["d2_mm"] == 220.0 and r["actions"][0].startswith("Export StarCCM: "), r
    assert r["actions"][-1] == "Save: success", r["actions"]
    assert (Path(r["run_dir"]) / "run.json").exists() and r["events"][-1]["msg"] == "Corrida con avisos"

    assert abs(r["curves"]["H_m"][1] - 70) < 0.05 and abs(r["curves"]["Q_m3h"][1] - 226.85) < 0.01 and r["curves"]["eta_pct"][1] == 86.6, r["curves"]
    assert abs(r["curves"]["P_kW"][1] - 49.88) < 0.05 and "report" not in r, r["curves"]
    assert "t1.cft-pp" in r["exports"]["PerformanceData"], r["exports"]
    # ángulos fijos: AutoUpdate2=False y CFturbo los respeta; espesor en LE/TE; reporte HTML parseado
    rb = run_batch("fake", {"beta2_deg": 26, "beta1_deg": [20, 18], "s_mm": 3.5}, "tb", exports=["Report"])
    assert rb["realized"]["beta2_deg"] == "[26.0, 26.0]" and rb["realized"]["beta1_deg"] == "[20.0, 18.0]", rb["realized"]
    assert rb["realized"]["s_mm"] == "[3.5, 3.5]" and not rb["corrected"], (rb["realized"], rb["corrected"])
    bi = rb["info"]["dims"]
    assert not bi["beta_auto2"] and not bi["beta_auto1"] and abs(bi["beta2_hub_deg"] - 26) < 1e-6 and bi["s_mm"] == 3.5, bi
    assert rb["report"]["beta1_deg"] == [20.7, 17.2] and rb["report"]["eta_h_pct"] == 92.1, rb["report"]
    assert rb["report"]["npshr_m"] == {"Gülich": [4.77, 10.06]} and rb["report"]["volute_throat_mm2"] == 4760.8, rb["report"]
    assert rb["report_file"] == "tb.html" and rb["exports"]["Report"] == ["tb.html"], rb["exports"]
    # beta_auto=True vuelve al automático: el falso CFturbo recalcula βB2 y eso NO es una corrección
    ra = run_batch(str(Path(rb["run_dir"]) / "tb_out.cft"), {"beta_auto": True}, "ta", exports=[])
    assert ra["realized"]["beta_auto"] == "True" and abs(ra["info"]["dims"]["beta2_hub_deg"] - 32.445) < 0.01, ra["info"]["dims"]
    assert run_batch("fake", {"beta2_deg": "abc"}, "tbad", exports=[])["status"] == "error"
    assert _differs("[26.0, 26.0]", "[26.004, 25.999]") is False and _differs("[26.0, 26.0]", "[24.0, 26.0]")

    r2 = run_batch("fake", {"d2_mm": 400}, "t2", exports=["StarCCM"])
    assert r2["corrected"]["d2_mm"] == ["0.4", "0.3"], r2["corrected"]  # corrección detectada
    r3 = run_batch("fake", {"noexiste": 1}, "t3")
    assert r3["status"] == "error" and "noexiste" in r3["errors"][0], r3
    assert [x["name"] for x in list_runs(2)] == ["t3", "t2"]
    assert "curves" not in list_runs(1)[0] and "report" not in list_runs(1, summary=True)[0]
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
    # borrar: temporal y versión (la versión deja línea en la bitácora); la que corre no se borra
    tmp_id = list_runs(1)[0]["id"]
    assert delete_run(tmp_id)["version"] is False and not any(x["id"] == tmp_id for x in list_runs(100))
    sv2 = save_version(list_runs(1)[0]["id"], "para_borrar")
    assert delete_run(sv2["id"]) == {"deleted": "para_borrar", "version": True, "path": str(VERSIONS / "para_borrar")}
    assert "VERSIÓN BORRADA versions/para_borrar" in (RECIPES / "bitacora.md").read_text(encoding="utf-8")
    run_d = WORKDIR / "corriendo_1"
    run_d.mkdir()
    (run_d / "run.json").write_text(json.dumps({"id": run_d.name, "name": "corriendo", "status": "running", "started": _now()}), encoding="utf-8")
    lk = acquire_lock("corriendo")
    try:
        delete_run(run_d.name)
        raise AssertionError("no debe borrar la corrida en marcha")
    except CFturboBusy:
        pass
    lk.unlink()
    shutil.rmtree(run_d)
    try:
        delete_run("no_existe")
        raise AssertionError
    except FileNotFoundError:
        pass

    # bomba nueva por semejanza desde la base «fake» (nq 37,3): H ×1,21 -> k = 1,1, d2 = 1,1·206,3
    sg = suggest_base(227, 84.7, 3600, base="fake")
    assert sg["base_name"] == "fake" and abs(sg["k"] - 1.1) < 1e-3 and sg["aviso"] is None, sg
    assert suggest_base(900, 20, 3600, base="fake")["aviso"], "nq ×3 debe avisar"
    nw = new_project(227, 84.7, 3600, "nueva bomba!", base="fake")
    assert nw["name"] == "nueva_bomba" and abs(nw["d2_mm"] - 1.1 * 206.3) < 0.01, nw
    assert "nueva_bomba" in [p["name"] for p in list_projects()]
    ni = project_info("nueva_bomba")
    assert abs(ni["dims"]["d2_mm"] - 226.93) < 0.01 and ni["design_point"]["H_m"] == 84.7 and ni["dims"]["AutoUpdate"] == "False", ni
    assert abs(ni["dims"]["s_mm"] - 3.41) < 1e-6, ni["dims"]  # el espesor también escala
    try:
        new_project(227, 84.7, 3600, "nueva_bomba", base="fake")
        raise AssertionError("debe negarse a pisar un proyecto")
    except FileExistsError:
        pass
    assert run_batch("nueva_bomba", {}, "nueva_1", exports=[])["status"] in ("ok", "warn")

    recipe_save("prueba-d2", "# sube d2 para más altura\nd2 +10% => H +20%")
    assert recipe_search("altura d2")[0]["file"] == "prueba-d2.md"
    assert any(h["file"] == "bitacora.md" for h in recipe_search("bomba_v1"))
    shutil.rmtree(tmp)
    print("selftest OK")


if __name__ == "__main__":
    selftest() if "--selftest" in sys.argv else serve()
