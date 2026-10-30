"""Orquestador del lote CFD: geometrías de CFturbo (Desktop/Geometrias_Prueba/G0xx_*) → una simulación de bomba cada una.

Por geometría: prepara cases/<ID>/ (CAD, lote.json, macros con los valores puestos y compiladas con javac), lanza el
EJECUTOR (claude -p, Sonnet, sigue lote/receta.md con las tools del MCP), calcula los chequeos, lanza el REVISOR
(claude -p, Opus, lote/revision.md), hace un segundo intento si hace falta (extender iteraciones si H deriva, o rehacer
si el revisor lo pide), copia todo a <geometría>/CFD/ y aprende (historial de malla, propuestas con límites, lecciones).
Un solo solver a la vez: lote/.lock impide dos orquestadores.

Uso (desde starccm/):
  .venv\\Scripts\\python lote\\orquestador.py                       todas las pendientes (ni OK ni REVISAR), en orden
  .venv\\Scripts\\python lote\\orquestador.py --solo G002,G047      solo esas, desde cero
  .venv\\Scripts\\python lote\\orquestador.py --estados REVISAR,ERROR   re-correr las que estén en esos estados
  .venv\\Scripts\\python lote\\orquestador.py --extender G002 --hasta 1600   reabrir el .sim y seguir iterando
  .venv\\Scripts\\python lote\\orquestador.py --consolidar           rehace estado, CSV, xlsx, índice y curvas desde cases/
  .venv\\Scripts\\python lote\\orquestador.py --limpiar-backups      borra sims/*.sim~ de los casos ya entregados
  .venv\\Scripts\\python lote\\orquestador.py --preparar G002        prepara y compila las macros; sin licencia ni modelos
  .venv\\Scripts\\python lote\\orquestador.py --seco                 prueba en seco (ejecutor y revisor falsos, temporales)
  .venv\\Scripts\\python lote\\orquestador.py --estado               tabla de estado
Parar con calma: crear lote/PARAR (termina el intento en curso y sale).
"""
from __future__ import annotations

import csv
import json
import math
import os
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

LOTE = Path(__file__).resolve().parent
ST = LOTE.parent                      # starccm/
REPO = ST.parent
sys.path.insert(0, str(ST))
import mcp_server as M  # noqa: E402  (carga starccm/.env; sin efectos: el watchdog y el MCP solo arrancan en __main__)

GEO = Path(os.environ.get("LOTE_GEO", Path.home() / "Desktop" / "Geometrias_Prueba"))
GIT = shutil.which("git") or r"C:\Program Files\Git\cmd\git.exe"
CLAUDE = shutil.which("claude") or str(Path.home() / ".local" / "bin" / "claude.exe")
MODELO_EJECUTOR = os.environ.get("LOTE_MODELO_EJECUTOR", "sonnet")
MODELO_REVISOR = os.environ.get("LOTE_MODELO_REVISOR", "opus")
T_EJECUTOR = 5 * 3600
T_REVISOR = 1200
FUNCS = "Pressure,TotalPressure,Velocity,yplus"
# lo único que el revisor puede mover, y entre qué valores (física, fronteras, extensiones e iteraciones: nunca)
LIMITES = {"min_rotor_pct": (15.0, 40.0), "alabes_pct": (30.0, 100.0), "objetivo_celdas": (900000, 1850000),
           "urf_v": (0.3, 0.7), "urf_p": (0.1, 0.3)}
ESTADOS_FINALES = ("OK", "REVISAR")
MAX_INFRA_SEGUIDOS = 2


class Cfg:
    """Rutas que cambian en la prueba en seco (todo a un temporal, nada real se toca)."""
    seco = False
    geo = GEO
    params = LOTE / "parametros.json"
    estado = LOTE / "estado.json"
    eventos = LOTE / "eventos.log"
    propuestas = LOTE / "propuestas.json"
    lecciones_rev = LOTE / "lecciones_revisor.md"
    lock = LOTE / ".lock"
    prefijo = ""


class ErrorInfra(RuntimeError):
    """claude no pudo trabajar (cuota, red, sesión, timeout) y no dejó resultado: se reintenta en la próxima corrida."""


def ahora() -> str:
    return datetime.now().isoformat(timespec="seconds")


def evento(tipo: str, gid: str = "", msg: str = "", **extra) -> None:
    """Una línea JSON por evento: la sesión monitora (Remote Control) los lee y avisa al celular."""
    with open(Cfg.eventos, "a", encoding="utf-8") as f:
        f.write(json.dumps({"t": ahora(), "tipo": tipo, "id": gid, "msg": msg, **extra}, ensure_ascii=False) + "\n")
    print(f"[{ahora()}] {tipo} {gid} {msg}", flush=True)


def leer_json(p: Path, defecto=None):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return defecto


def escribir_json(p: Path, d) -> None:
    tmp = Path(str(p) + ".tmp")
    tmp.write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, p)


def finito(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) and abs(x) < 1e300


def interp(x: float, xs: list, ys: list) -> float | None:
    pares = sorted((a, b) for a, b in zip(xs, ys) if finito(a) and finito(b))
    for (x0, y0), (x1, y1) in zip(pares, pares[1:]):
        if x0 <= x <= x1 and x1 > x0:
            return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return None


# ---------------------------------------------------------------- geometrías

def geometrias() -> list[dict]:
    est = leer_json(Cfg.geo / "_estado.json", {})
    por_carpeta = {v.get("folder"): (k, v) for k, v in est.items()}
    out = []
    for d in sorted(Cfg.geo.iterdir()):
        if not (d.is_dir() and re.match(r"^G\d{3}_", d.name)):
            continue
        k, v = por_carpeta.get(d.name, (d.name.split("_")[0], {}))
        out.append({"id": Cfg.prefijo + k, "clave": k, "carpeta": d, "estado_cft": v})
    return out


def variante(nombre: str) -> dict:
    """Z, Δβ2 y fD2 del nombre de carpeta de una variante (vacío en las bases)."""
    out = {}
    for k, pat in (("Z", r"_Z(\d+)_"), ("dBeta2_deg", r"_dBeta2([+-]?[\d.]+)deg"), ("fD2", r"fD2-([\d.]+)")):
        m = re.search(pat, nombre)
        if m:
            out[k] = float(m.group(1)) if k != "Z" else int(m.group(1))
    return out


def datos(g: dict) -> dict:
    """Todo lo que la simulación necesita, leído del .cfturbo-ccm, del _estado.json de CFturbo y del nombre."""
    d = g["carpeta"]
    ccm = next(d.glob("*.cfturbo-ccm"))
    root = ET.parse(ccm).getroot()
    num = lambda e, t: float(e.find(t).text)
    vec = lambda e: [float(e.find(c).text) for c in ("x", "y", "z")]
    # la extensión de salida de CFturbo (Caption VoluteExtension, también tipo VoluteOut) NO se importa: las extensiones
    # se crean en la simulación (03-extensiones), iguales en todo el lote
    zonas = [z for z in root.findall("FluidZone") if "Extension" not in (z.findtext("Caption") or "")
             and "_Extension" not in z.findtext("Geometry")]
    tipos = [z.findtext("ComponentType") for z in zonas]
    if sorted(tipos) != ["RadialImp", "Stator", "VoluteOut"]:
        raise ValueError(f"{d.name}: se esperaban Stator, RadialImp y VoluteOut en el .cfturbo-ccm y hay {tipos}")
    imp = next(z for z in zonas if z.findtext("ComponentType") == "RadialImp")
    co = {{"Stator": "CO1", "RadialImp": "CO2", "VoluteOut": "CO3"}[z.findtext("ComponentType")]: d / z.findtext("Geometry")
          for z in zonas}
    rps = num(imp, "RotationalSpeed")
    m = re.search(r"Q([\d.]+)m3h_H([\d.]+)m_n(\d+)rpm", d.name)
    nq = int(re.search(r"_nq(\d+)_", d.name).group(1))
    cft = g["estado_cft"] or {}
    rep = cft.get("report", {}) or {}
    u2 = rep.get("u2")
    rpm = rps * 60.0
    D2 = u2 * 60.0 / (math.pi * abs(rpm)) if u2 else None
    beta2 = (rep.get("beta2_deg") or [None])[0]
    var = variante(d.name)
    return {
        "id": g["id"], "clave": g["clave"], "carpeta": str(d), "nombre": ccm.stem, "nq": nq,
        "tipo": "variante" if "variante" in d.name else "base", **var,
        "f_D2_real": cft.get("f_D2_real"), "base_gid": cft.get("base_gid"),
        "Q_m3h": float(m.group(1)), "H_diseno_m": float(m.group(2)), "rpm": rpm,
        "masa_kg_s": num(root.find("ProjectData"), "MassFlow"),
        "rho": num(root.find("FluidData"), "Density"), "mu": num(root.find("FluidData"), "DynamicViscosity"),
        "eje": vec(imp.find("RotationAxis")), "u2_cfturbo": u2,
        "D2_cfturbo_mm": round(D2 * 1000, 2) if D2 else None, "beta2_deg": beta2,
        "cad": {k: str(v) for k, v in co.items()},
    }


def base_de(g: dict, todas: list[dict]) -> dict | None:
    """La bomba base de una variante: base_gid de CFturbo o, si falta, la base de la misma nq."""
    v = g["estado_cft"] or {}
    if v.get("base_gid"):
        b = next((b for b in todas if b["clave"] == v["base_gid"]), None)
        if b:
            return b
    nq = re.search(r"_nq(\d+)_", g["carpeta"].name).group(1)
    return next((b for b in todas if f"_nq{nq}_base_" in b["carpeta"].name), None)


def d2_esperado(g: dict, dat: dict, todas: list[dict]) -> float | None:
    """D2 esperado de la variante = D2 de su base × fD2 real (o el del nombre). En las variantes de nq 65 y 80 el u2 de
    _estado.json es el de la base (CFturbo no aplicó el recorte al informe), así que no se usa el u2 de la variante."""
    if dat["tipo"] == "base":
        return dat["D2_cfturbo_mm"]
    f = dat.get("f_D2_real") or dat.get("fD2")
    b = base_de(g, todas)
    u2b = ((b or {}).get("estado_cft") or {}).get("report", {}).get("u2") if b else None
    return round(u2b * 60.0 / (math.pi * abs(dat["rpm"])) * 1000 * f, 2) if (u2b and f) else None


def h_referencia(g: dict, dat: dict, todas: list[dict]) -> float | None:
    """H que predice CFturbo para ESTA geometría al caudal de diseño: su propia curva H(Q). Si el u2 de la variante es el
    de la base (recorte no aplicado al informe), la curva tampoco lo tiene: se escala por fD2²."""
    cft = g["estado_cft"] or {}
    c = cft.get("curves") or {}
    Hc = interp(dat["Q_m3h"], c.get("Q_m3h") or [], c.get("H_m") or [])
    if Hc is None or dat["tipo"] == "base":
        return Hc
    b = base_de(g, todas)
    u2b = ((b or {}).get("estado_cft") or {}).get("report", {}).get("u2") if b else None
    f = dat.get("f_D2_real") or dat.get("fD2")
    if f and u2b and dat.get("u2_cfturbo") and abs(dat["u2_cfturbo"] - u2b) < 0.05:
        Hc *= f * f
    return Hc


# ---------------------------------------------------------------- malla

def _mc(A: list, b: list) -> list | None:
    """Mínimos cuadrados por ecuaciones normales (sin numpy)."""
    n = len(A[0])
    Mx = [[sum(r[i] * r[j] for r in A) for j in range(n)] for i in range(n)]
    v = [sum(r[i] * y for r, y in zip(A, b)) for i in range(n)]
    for i in range(n):
        if abs(Mx[i][i]) < 1e-12:
            return None
        for j in range(i + 1, n):
            f = Mx[j][i] / Mx[i][i]
            for k in range(n):
                Mx[j][k] -= f * Mx[i][k]
            v[j] -= f * v[i]
    x = [0.0] * n
    for i in reversed(range(n)):
        x[i] = (v[i] - sum(Mx[i][k] * x[k] for k in range(i + 1, n))) / Mx[i][i]
    return x


def frac_extensiones(P: dict, nq: int) -> float:
    """Celdas de extensiones / celdas de la bomba, aprendido de los casos con extensiones gruesas (2 × base)."""
    h = [e for e in P["historial_malla"] if e.get("ext_base_factor") == 2 and e.get("celdas_sin_ext")]
    if len(h) >= 3:
        cerca = sorted(h, key=lambda e: abs(e["nq"] - nq))[:5]
        return statistics.median(e["celdas"] / e["celdas_sin_ext"] - 1 for e in cerca)
    return 0.06


def base_mm(P: dict, dat: dict) -> float:
    """Tamaño base para que la bomba (sin extensiones) dé objetivo/(1+ext) celdas. Modelo ajustado a todo el historial:
    ln(celdas_bomba) = c0 + c1·ln(D2/base) + c2·ln nq + c3·ln² nq (error ~8 % con validación cruzada en 47 casos). Con
    pocos datos o un ajuste raro, el vecino de nq más cercana con (D2/base)³."""
    D2 = dat.get("D2_esperado_mm") or dat["D2_cfturbo_mm"] or 250.0
    nq = dat["nq"]
    obj = P["objetivo_celdas"] / (1 + frac_extensiones(P, nq))
    h = [e for e in P["historial_malla"] if e.get("celdas_sin_ext") and e.get("D2_mm") and e.get("estado") != "ERROR"]
    if len(h) >= 8:
        A = [[1.0, math.log(e["D2_mm"] / e["base_mm"]), math.log(e["nq"]), math.log(e["nq"]) ** 2] for e in h]
        c = _mc(A, [math.log(e["celdas_sin_ext"]) for e in h])
        if c and c[1] > 0.5:
            ln = math.log(nq)
            l = (math.log(obj) - c[0] - c[2] * ln - c[3] * ln * ln) / c[1]
            ls = [a[1] for a in A]
            l = min(max(l, min(ls) - 0.1), max(ls) + 0.1)        # sin extrapolar lejos de lo visto
            return round(D2 / math.exp(l), 1)
    if h:
        e = min(h, key=lambda e: abs(e["nq"] - nq))
        return round(D2 / ((e["D2_mm"] / e["base_mm"]) * (obj / e["celdas_sin_ext"]) ** (1 / 3)), 1)
    return round(D2 / P["D2_sobre_base"], 1)


# ---------------------------------------------------------------- preparación del caso

def _render_tpl(src: Path, vals: dict) -> str:
    txt = src.read_text(encoding="utf-8")
    for k, v in vals.items():
        txt = txt.replace("{{" + k + "}}", str(v))
    falta = re.findall(r"\{\{([A-Z_0-9]+)\}\}", txt)
    if falta:
        raise ValueError(f"{src.name}: sin valor para {falta}")
    return txt


def _render_receta(nombre: str, vals: dict, extra_cabecera: str = "") -> str:
    """Recetas de recipes/ con parámetros como palabras sueltas (MODO, RHO…): se sustituyen solo fuera de comentarios."""
    out = []
    for ln in (ST / "recipes" / nombre).read_text(encoding="utf-8").splitlines():
        if not ln.lstrip().startswith("//"):
            for k, v in vals.items():
                ln = re.sub(rf"\b{k}\b", str(v).replace("\\", "/"), ln)
        out.append(ln)
    return extra_cabecera + "\n".join(out) + "\n"


def jp(p) -> str:
    return str(p).replace("\\", "/")


RECETAS_LOTE = (("11a-escenas-bomba", "bomba-escenas"), ("11b-escenas-fluido", "escenas-fluido"),
                ("11c-escena-malla", "escena-malla-rotor"), ("11d-escena-plano-vectores", "escena-plano-vectores"))


def valores(caso: Path, dat: dict, P: dict, base: float, max_it: int) -> dict:
    ax = ", ".join(repr(float(x)) for x in dat["eje"])
    return {**dat["cad_caso"], "BASE_MM": base, "BASE_EXT_MM": round(2 * base, 2), "MIN_ROTOR_PCT": P["min_rotor_pct"],
            "ALABES_PCT": P["alabes_pct"], "PRISMAS": P["prismas"], "L_IN_D": P["ext_entrada_D"], "L_OUT_D": P["ext_salida_D"],
            "RHO": dat["rho"], "MU": dat["mu"], "RPM": dat["rpm"], "MASA": dat["masa_kg_s"], "URF_V": P["urf_v"],
            "URF_P": P["urf_p"], "AX": ax, "BLOQUE": P["bloque"], "MAX_IT": max_it, "VENTANA": P["ventana_promedio"],
            "CONV_CSV": jp(caso / "reports" / "convergencia.csv"), "RES_CSV": jp(caso / "reports" / "residuales.csv"),
            "OUT_JSON": jp(caso / "resultado_solver.json"), "MALLA_JSON": jp(caso / "malla.json"),
            "IMG_DIR": jp(caso / "images")}


def render_iteracion(caso: Path, dat: dict, P: dict, max_it: int) -> None:
    """07 (iterar) y 08 (promedio) solo dependen de MAX_IT y de la ventana: se rehacen en cada intento, así el ejecutor
    nunca tiene que editarlas para seguir iterando."""
    mac = caso / "macros"
    lj = leer_json(caso / "lote.json", {}) or {}
    v = valores(caso, dat, P, lj.get("base_mm") or 0, max_it)
    (mac / "07-iterar-bloque.java").write_text(_render_tpl(LOTE / "macros" / "07-iterar-bloque.java", v), encoding="utf-8")
    (mac / "08-promedio.java").write_text(_render_receta("promediar-monitores.java", {
        "MONS": "H Monitor,M Monitor,eta Monitor,P_eje Monitor,Q_in Monitor,Q_out Monitor,pt_in Monitor,pt_out Monitor",
        "VENTANA": P["ventana_promedio"], "DESDE": max(0, max_it - P["ventana_promedio"]),
        "CSV": jp(caso / "reports" / "monitores_historial.csv")},
        "// Generada por lote/orquestador.py desde recipes/promediar-monitores.java\n"), encoding="utf-8")


def preparar(g: dict, todas: list[dict], P: dict, intento: int = 1, tipo_intento: str = "completo",
             instrucciones: str = "", max_it: int | None = None) -> dict:
    """Intento 1: caso nuevo con todas las macros. Intentos siguientes: se respetan las macros del ejecutor (base
    remallado…) salvo 07 y 08, que se rehacen con las iteraciones del intento."""
    dat = datos(g)
    caso = M.CASES / g["id"]
    for sub in ("cad", "macros", "reports", "images", "surfaces/_raw/superficies", "logs"):
        (caso / sub).mkdir(parents=True, exist_ok=True)
    cad = {}
    for k, f in dat["cad"].items():
        dst = caso / "cad" / Path(f).name
        if not dst.is_file():
            shutil.copy2(f, dst)
        cad[k] = jp(dst)
    dat["cad_caso"] = cad
    ccm = next(Path(dat["carpeta"]).glob("*.cfturbo-ccm"))
    shutil.copy2(ccm, caso / "cad" / ccm.name)
    lj = leer_json(caso / "lote.json", {}) or {}
    dat["D2_esperado_mm"] = d2_esperado(g, dat, todas)
    base = lj.get("base_mm") or base_mm(P, dat)
    max_it = max_it or lj.get("iteraciones") or P["iteraciones"]
    destino = Path(dat["carpeta"]) / "CFD" / f"{dat['nombre']}.sim"
    lote = {**{k: v for k, v in dat.items() if k != "cad_caso"}, "H_referencia_m": h_referencia(g, dat, todas),
            "base_mm": base, "intento": intento, "tipo_intento": tipo_intento, "instrucciones_reintento": instrucciones,
            "receta_version": P["receta_version"], "max_celdas": P["max_celdas"], "objetivo_celdas": P["objetivo_celdas"],
            "iteraciones": max_it, "iteraciones_extension": P["iteraciones_extension"], "ventana_promedio": P["ventana_promedio"],
            "parametros": {k: P[k] for k in ("min_rotor_pct", "alabes_pct", "prismas", "ext_entrada_D", "ext_salida_D", "urf_v", "urf_p")},
            "sim_destino": str(destino), "preparado": ahora()}
    escribir_json(caso / "lote.json", lote)
    escribir_json(caso / "caso.json", {"sim_destino": str(destino), "titulo": f"{g['clave']} (lote)"})
    mac = caso / "macros"
    if intento == 1:
        v = valores(caso, dat, P, base, max_it)
        for t in sorted((LOTE / "macros").glob("*.java")):
            (mac / t.name).write_text(_render_tpl(t, v), encoding="utf-8")
        cab = "// Generada por lote/orquestador.py desde recipes/{}\n"
        # las interfaces no tienen caras hasta inicializar; 06 inicializa, y si aun así no encuentra, usa estos nombres
        (mac / "06-euler.java").write_text(_render_receta("reportes-euler-triangulos.java", {
            "MODO": "bomba", "RHO": dat["rho"], "H_REPORT": "H", "BETA2": dat["beta2_deg"] if dat["beta2_deg"] else "",
            "ENTRADA_ROTOR": "Inflow [int_entrada 1]", "SALIDA_ROTOR": "Outflow [int_salida 1]"},
            cab.format("reportes-euler-triangulos.java")), encoding="utf-8")
        (mac / "10-superficies.java").write_text(_render_receta("exportar-superficies-ensight.java", {
            "PATTERN": ".", "FUNCS": FUNCS, "OUT": jp(caso / "surfaces" / "_raw" / "superficies" / "superficies.case"),
            "PLANOS": "auto"}, cab.format("exportar-superficies-ensight.java")), encoding="utf-8")
        for k, r in RECETAS_LOTE:
            (mac / f"{k}.java").write_text(_render_receta(f"{r}.java", {}, cab.format(f"{r}.java")), encoding="utf-8")
    render_iteracion(caso, dat, P, max_it)
    errores = compilar(mac)
    if errores:
        raise RuntimeError("macros que no compilan: " + "; ".join(f"{k}: {e[:400]}" for k, e in errores.items()))
    return lote


def compilar(mac: Path) -> dict:
    """javac de STAR-CCM+ sobre cada macro envuelta como la envuelve el MCP: sin licencia ni servidor."""
    errores = {}
    if not M._javac():
        return {}
    for f in sorted(mac.glob("*.java")):
        body = f.read_text(encoding="utf-8")
        imports = ",".join(m.strip() for m in re.findall(r"^//\s*imports:\s*(.+)$", body, flags=re.M))
        tag = "lote_" + re.sub(r"\W", "_", f.stem)
        tmp = Path(tempfile.mkdtemp(prefix="lote-javac-"))
        src = tmp / f"Agent_{tag}.java"
        src.write_text(M._wrap(body, imports, tag), encoding="utf-8")
        old = M.MACROS
        M.MACROS = tmp
        try:
            e = M._precompile(src)
        finally:
            M.MACROS = old
            shutil.rmtree(tmp, ignore_errors=True)
        if e:
            errores[f.name] = e
    return errores


# ---------------------------------------------------------------- agentes

def env_cli() -> dict:
    e = {k: v for k, v in os.environ.items() if not k.startswith("CLAUDE") and k != "STARCCM_PODKEY"}
    e["PATH"] = str(Path.home() / ".local" / "bin") + os.pathsep + e.get("PATH", "")
    e["LOTE_PROPUESTAS"] = str(Cfg.propuestas)   # solo lo usa falso_claude en --seco
    return e


def claude(prompt: str, modelo: str, permitidas: str, log: Path, timeout: int, max_turnos: int) -> dict:
    """claude -p con salida stream-json a `log`. Devuelve rc, segundos, coste, subtipo y si se cortó por tiempo."""
    cmd = [CLAUDE, "-p", prompt, "--model", modelo, "--output-format", "stream-json", "--verbose",
           "--mcp-config", str(REPO / ".mcp.json"), "--strict-mcp-config", "--allowedTools", permitidas,
           "--disallowedTools", "Bash,PowerShell,NotebookEdit,WebFetch,WebSearch,Read(**/.env*),Read(**/.starccm-agent.env)",
           "--max-turns", str(max_turnos)]
    if Cfg.seco:
        cmd = [sys.executable, str(LOTE / "falso_claude.py"), "-p", prompt, "--model", modelo]
    t0 = time.time()
    res = {"rc": None, "segundos": 0, "coste_usd": None, "cortado": False, "subtipo": None}
    with open(log, "w", encoding="utf-8") as out:
        p = subprocess.Popen(cmd, cwd=ST, env=env_cli(), stdin=subprocess.DEVNULL, stdout=out, stderr=subprocess.STDOUT,
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        lock_hijo(p.pid)
        try:
            res["rc"] = p.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"], capture_output=True)
            res["cortado"] = True
        finally:
            lock_hijo(None)
    res["segundos"] = round(time.time() - t0)
    for ln in log.read_text(encoding="utf-8", errors="replace").splitlines()[::-1]:
        if '"type":"result"' in ln.replace(" ", ""):
            try:
                o = json.loads(ln)
                res.update(coste_usd=o.get("total_cost_usd"), turnos=o.get("num_turns"), subtipo=o.get("subtype"))
            except ValueError:
                pass
            break
    return res


def ejecutar(g: dict, lote: dict) -> dict:
    caso = M.CASES / g["id"]
    n = lote["intento"]
    prompt = (f"Caso {g['id']}: cases/{g['id']}/. Lee lote/receta.md y lote/lecciones.md y sigue la receta con los datos "
              f"de cases/{g['id']}/lote.json (intento {n}, tipo «{lote['tipo_intento']}»: si no es «completo», mira la "
              f"sección de la receta para ese tipo y las instrucciones_reintento de lote.json). Trabaja solo, sin preguntar.")
    permitidas = f"mcp__starccm__*,Read,Glob,Grep,Write(cases/{g['id']}/**),Edit(cases/{g['id']}/**)"
    return claude(prompt, MODELO_EJECUTOR, permitidas, caso / "logs" / f"ejecutor_{n}.jsonl", T_EJECUTOR, 250)


def revisar(g: dict, lote: dict) -> dict:
    caso = M.CASES / g["id"]
    ultimo = lote["intento"] >= 2
    prompt = (f"Revisa el caso {g['id']} (cases/{g['id']}/) siguiendo lote/revision.md. Intento {lote['intento']} "
              f"({'último: no puedes pedir REINTENTAR' if ultimo else 'puedes pedir REINTENTAR'}). "
              f"Escribe cases/{g['id']}/veredicto.json (ruta relativa).")
    # Write se rige por las reglas Edit(...): sin Edit(...) el revisor no puede crear veredicto.json en -p
    prop = os.path.relpath(Cfg.propuestas, ST).replace("\\", "/")
    permitidas = (f"Read,Glob,Grep,Edit(cases/{g['id']}/veredicto.json),Write(cases/{g['id']}/veredicto.json),"
                  f"Edit({prop}),Write({prop})")
    return claude(prompt, MODELO_REVISOR, permitidas, caso / "logs" / f"revisor_{lote['intento']}.jsonl", T_REVISOR, 40)


def veredicto_denegado(log: Path) -> dict:
    """Si el revisor intentó escribir veredicto.json y se le negó el permiso, rescata ese contenido del log."""
    try:
        for ln in log.read_text(encoding="utf-8", errors="replace").splitlines()[::-1]:
            if '"permission_denials"' not in ln:
                continue
            for d in json.loads(ln).get("permission_denials") or []:
                ti = d.get("tool_input") or {}
                if str(ti.get("file_path", "")).replace("\\", "/").endswith("/veredicto.json"):
                    return json.loads(ti.get("content", "{}"))
            break
    except (OSError, ValueError):
        pass
    return {}


def asegurar_solver_apagado(gid: str) -> None:
    """Nunca dejar la licencia tomada: guardar y apagar; si el guardado falla o el proceso sigue vivo, apagar sin guardar."""
    if Cfg.seco:
        return
    try:
        st = M._state()
        if not (st.get("pid") and M.alive(st)):
            return
        evento("aviso", gid, "el solver seguía encendido: lo guardo y lo apago")
        r = M.server_stop(save=True)
        if not r.get("stopped") or M.alive(M._state()):
            evento("aviso", gid, f"no se pudo guardar al apagar ({str(r)[:200]}): apago sin guardar")
            M.server_stop(save=False)
    except Exception as e:  # noqa: BLE001
        evento("error", gid, f"no pude apagar el solver: {e}")


# ---------------------------------------------------------------- candado de instancia única

def _vivo(pid) -> bool:
    try:
        return bool(pid) and M._pid_alive(int(pid))
    except Exception:  # noqa: BLE001
        return False


def tomar_lock() -> bool:
    """lote/.lock con el PID: dos orquestadores sobre una licencia de una copia se pisan. Si el anterior murió, se limpia
    lo que dejó (su claude hijo y el solver)."""
    l = leer_json(Cfg.lock, {}) or {}
    if l and _vivo(l.get("pid")) and int(l["pid"]) != os.getpid():
        print(f"Ya hay un orquestador vivo (PID {l['pid']}, desde {l.get('inicio')}). Si no es así, borra {Cfg.lock}.")
        return False
    if l.get("hijo") and _vivo(l["hijo"]):
        subprocess.run(["taskkill", "/PID", str(l["hijo"]), "/T", "/F"], capture_output=True)
        evento("aviso", "", f"maté el claude huérfano {l['hijo']} del orquestador anterior")
    escribir_json(Cfg.lock, {"pid": os.getpid(), "inicio": ahora(), "hijo": None})
    return True


def lock_hijo(pid) -> None:
    l = leer_json(Cfg.lock, None)
    if l is not None and l.get("pid") == os.getpid():
        l["hijo"] = pid
        escribir_json(Cfg.lock, l)


def soltar_lock() -> None:
    l = leer_json(Cfg.lock, {}) or {}
    if l.get("pid") == os.getpid():
        Cfg.lock.unlink(missing_ok=True)


# ---------------------------------------------------------------- chequeos

def leer_monitores(caso: Path) -> tuple[list[str], list[list[float]]]:
    f = caso / "reports" / "monitores_historial.csv"
    if not f.is_file():
        return [], []
    filas = list(csv.reader(f.open(encoding="utf-8-sig", errors="replace")))
    if len(filas) < 3:
        return [], []
    hdr = [h.strip().strip('"').split(":")[0].replace(" Monitor", "").strip() for h in filas[0]]
    datos_ = []
    for r in filas[1:]:
        try:
            datos_.append([float(x) for x in r])
        except ValueError:
            continue
    return hdr, datos_


def historial(caso: Path, ventana: int = 200) -> dict:
    """Por monitor, en las últimas `ventana` iteraciones: media, mín., máx. y, para H, deriva (pendiente lineal en % por
    100 it.) y oscilación sin tendencia (2·σ del residuo, %). La oscilación por semirrango confunde ruido con deriva."""
    hdr, datos_ = leer_monitores(caso)
    if not datos_:
        return {}
    it_max = max(r[0] for r in datos_)
    sel = [r for r in datos_ if r[0] > it_max - ventana]
    out = {}
    for j, nombre in enumerate(hdr[1:], start=1):
        pts = [(r[0], r[j]) for r in sel if j < len(r) and finito(r[j])]
        if not pts:
            continue
        ys = [y for _, y in pts]
        m = sum(ys) / len(ys)
        d = {"media": m, "min": min(ys), "max": max(ys), "n": len(ys), "ultimo": ys[-1]}
        if len(pts) >= 10 and abs(m) > 1e-9:
            xs = [x for x, _ in pts]
            mx = sum(xs) / len(xs)
            sxx = sum((x - mx) ** 2 for x in xs)
            b = sum((x - mx) * (y - m) for x, y in pts) / sxx if sxx else 0.0
            res = [y - (m + b * (x - mx)) for x, y in pts]
            d["deriva_pct_100it"] = b * 100 / abs(m) * 100
            d["oscilacion_pct"] = 2 * statistics.pstdev(res) / abs(m) * 100
        out[nombre] = d
    out["_iteracion"] = it_max
    return out


def eta_referencia(nq: int, estado: dict) -> float | None:
    """η esperada a esa nq según las bases ya simuladas en este lote (interpolación por nq)."""
    pts = sorted((e["nq"], e["eta"]) for e in estado.values()
                 if e.get("tipo") == "base" and e.get("estado") == "OK" and finito(e.get("eta")) and e.get("nq"))
    if len(pts) < 3:
        return None
    if nq <= pts[0][0]:
        return pts[0][1]
    if nq >= pts[-1][0]:
        return pts[-1][1]
    return interp(nq, [p[0] for p in pts], [p[1] for p in pts])


def r_te_base(lote: dict) -> float | None:
    """Radio máximo del borde de salida medido en la base de esta variante (de su resultado ya simulado)."""
    bid = lote.get("base_gid")
    if not bid:
        return None
    r = leer_json(M.CASES / (Cfg.prefijo + bid) / "resultado_solver.json", {}) or {}
    v = r.get("r_te_max_m", r.get("r_salida_alabe_m"))
    return v if finito(v) else None


def chequear(g: dict, lote: dict, P: dict, estado: dict | None = None) -> dict:
    caso = M.CASES / g["id"]
    res = leer_json(caso / "resultado_solver.json", {}) or {}
    eje = leer_json(caso / "ejecucion.json", {}) or {}
    h = historial(caso, P["ventana_promedio"])
    C = P["chequeos"]
    rep = res.get("reportes", {}) or {}
    H = (h.get("H") or {}).get("media", rep.get("H"))
    Mm = (h.get("M") or {}).get("media", rep.get("M"))
    eta = (h.get("eta") or {}).get("media", rep.get("eta"))
    lista = []

    def chk(nombre, valor, limite, ok, grave=True):
        lista.append({"chequeo": nombre, "valor": round(valor, 4) if finito(valor) else valor, "limite": limite,
                      "ok": bool(ok), "grave": grave})

    it = res.get("iteracion", 0) or 0
    chk("iteraciones", it, f">= {lote['iteraciones']}", it >= lote["iteraciones"])
    cel = res.get("celdas")
    chk("celdas", cel, f"<= {P['max_celdas']}", finito(cel) and cel <= P["max_celdas"])
    bal = res.get("balance_masa_pct")
    chk("balance de masa %", bal, f"<= {C['balance_max_pct']}", finito(bal) and abs(bal) <= C["balance_max_pct"])
    # fronteras: el caudal que sale debe ser el impuesto (detecta BC cambiada o mal asignada)
    dq = res.get("Q_out_vs_masa_pct")
    qo, masa = res.get("Q_out_kg_s", rep.get("Q_out")), lote.get("masa_kg_s")
    if not finito(dq) and finito(qo) and masa:
        dq = (abs(qo) - masa) / masa * 100
    if finito(dq):
        chk("caudal de salida = BC %", dq, f"|x| <= {C['Q_bc_tol_pct']}", abs(dq) <= C["Q_bc_tol_pct"])
    # giro: con el par con el signo de una turbina (o par ~0) la bomba gira al revés o el eje está mal
    sig = res.get("M_signo_ok")
    if sig is not None:
        chk("par con signo de bomba (giro y eje)", sig, "true", sig is True)
    chk("H > 0", H, "> 0", finito(H) and H > 0)
    Hrel = H / lote["H_diseno_m"] if finito(H) else None
    Href = lote.get("H_referencia_m")
    Hcur = H / Href if (finito(H) and finito(Href) and Href > 0) else None
    if lote["tipo"] == "base":
        chk("H / H diseño", Hrel, f"{C['H_rel_min']}–{C['H_rel_max']}", Hrel is not None and C["H_rel_min"] <= Hrel <= C["H_rel_max"])
    else:
        # la H de una variante es física de la variante: solo es error clave si es absurda frente a su propia curva
        chk("H / H curva CFturbo de la variante", Hcur, f">= {C['H_curva_grave_min']}",
            Hcur is None or Hcur >= C["H_curva_grave_min"])
    if Hcur is not None:
        chk("H dentro de lo que predice CFturbo", Hcur, f"{C['H_curva_aviso_min']}–{C['H_curva_aviso_max']}",
            C["H_curva_aviso_min"] <= Hcur <= C["H_curva_aviso_max"], grave=False)
    chk("eta", eta, f"{C['eta_min']}–{C['eta_max']}", finito(eta) and C["eta_min"] <= eta <= C["eta_max"])
    eref = eta_referencia(lote["nq"], estado or {})
    if eref is not None and finito(eta):
        chk("eta frente a las bases del lote a esa nq", eta - eref, f"±{C['eta_banda_nq']}", abs(eta - eref) <= C["eta_banda_nq"], grave=False)
    hh = h.get("H") or {}
    if "deriva_pct_100it" in hh:
        chk("deriva de H %/100 it.", hh["deriva_pct_100it"], f"|x| <= {C['deriva_H_max_pct_100it']}",
            abs(hh["deriva_pct_100it"]) <= C["deriva_H_max_pct_100it"])
        chk("oscilación de H % (2σ sin tendencia)", hh["oscilacion_pct"], f"<= {C['oscilacion_H_max_pct']}",
            hh["oscilacion_pct"] <= C["oscilacion_H_max_pct"])
    else:
        chk("historial de monitores", None, f">= 10 iteraciones de H en {caso / 'reports'}", False)
    # D2: en flujo mixto el borde de salida es inclinado y su radio máximo no es D2 → se compara variante contra base
    rmax = res.get("r_te_max_m", res.get("r_salida_alabe_m"))
    rmax = rmax if finito(rmax) else None
    D2e = lote.get("D2_esperado_mm")
    if lote["tipo"] == "base" and rmax and D2e and lote["nq"] < C["d2_nq_flujo_mixto"]:
        dif = (2 * rmax * 1000 - D2e) / D2e * 100
        chk("D2 medido vs esperado %", dif, f"±{C['d2_tol_pct']}", abs(dif) <= C["d2_tol_pct"], grave=False)
    elif lote["tipo"] == "variante" and rmax:
        rb, f = r_te_base(lote), lote.get("f_D2_real") or lote.get("fD2")
        if rb and f:
            dif = (rmax / rb - f) / f * 100
            chk("recorte: r_TE variante / base vs fD2 %", dif, f"±{C['d2_var_tol_pct']}", abs(dif) <= C["d2_var_tol_pct"], grave=False)
    ym = res.get("yplus_alabes_max")
    if finito(ym):
        chk("y+ máximo en álabes", ym, f"<= {C['yplus_max']}", ym <= C["yplus_max"], grave=False)
    md, mt = res.get("M_discos"), res.get("M_total", Mm)
    if finito(md) and finito(mt) and abs(mt) > 1e-9:
        fr = abs(md / mt)
        chk("par de discos / par total", fr, f"<= {C['M_discos_max_frac']}", fr <= C["M_discos_max_frac"], grave=False)
    imgs = len(list((caso / "images").glob("*.png")))
    chk("escenas PNG", imgs, f">= {C['escenas_min']}", imgs >= C["escenas_min"], grave=False)
    chk("ejecutor terminó", eje.get("estado"), "COMPLETO", eje.get("estado") == "COMPLETO")
    graves = [c["chequeo"] for c in lista if c["grave"] and not c["ok"]]
    out = {"H_m": H, "M_Nm": Mm, "eta": eta, "H_rel": Hrel, "H_ref_m": Href, "H_rel_curva": Hcur,
           "deriva_H_pct_100it": hh.get("deriva_pct_100it"), "oscilacion_H_pct": hh.get("oscilacion_pct"),
           "D2_medido_mm": round(2 * rmax * 1000, 2) if rmax else None, "celdas": cel, "iteracion": it,
           "graves_fallidos": graves, "avisos": [c["chequeo"] for c in lista if not c["grave"] and not c["ok"]],
           "solo_falta_convergencia": bool(graves) and set(graves) <= {"deriva de H %/100 it.", "oscilación de H % (2σ sin tendencia)"},
           "chequeos": lista, "promedios": h}
    escribir_json(caso / "chequeos.json", out)
    return out


# ---------------------------------------------------------------- entrega y aprendizaje

def entregar(g: dict, lote: dict, P: dict) -> Path:
    caso = M.CASES / g["id"]
    dst = Path(lote["carpeta"]) / "CFD"
    dst.mkdir(parents=True, exist_ok=True)
    for sub in ("images", "reports"):
        if (caso / sub).is_dir():
            if (dst / sub).is_dir():
                shutil.rmtree(dst / sub, ignore_errors=True)   # sin restos de corridas anteriores
            shutil.copytree(caso / sub, dst / sub)
    if (caso / "surfaces" / "_raw" / "superficies").is_dir():
        shutil.copytree(caso / "surfaces" / "_raw" / "superficies", dst / "surfaces", dirs_exist_ok=True)
    for f in ("RESUMEN.md", "lote.json", "resultado_solver.json", "chequeos.json", "veredicto.json", "ejecucion.json", "malla.json"):
        if (caso / f).is_file():
            shutil.copy2(caso / f, dst / f)
    sim = M.SIMS / f"{g['id']}.sim"
    dsim = Path(lote["sim_destino"])
    if sim.is_file() and (not dsim.is_file() or dsim.stat().st_mtime < sim.stat().st_mtime or dsim.stat().st_size != sim.stat().st_size):
        tmp = dsim.with_name(dsim.name + ".copiando")
        shutil.copy2(sim, tmp)
        os.replace(tmp, dsim)
    if P.get("borrar_backups_sim") and dsim.is_file():
        for b in M.SIMS.glob(f"{g['id']}.sim~*"):   # copias de seguridad de STAR-CCM+ de este caso: ya está entregado
            b.unlink(missing_ok=True)
    return dst


def anotar_leccion(gid: str, leccion: str) -> str | None:
    """Las lecciones del revisor no entran tal cual en el prompt del ejecutor: van validadas (una línea, corta, sin
    repetir) a lecciones_revisor.md. lote/lecciones.md (la que lee el ejecutor) solo la cambia una persona."""
    t = re.sub(r"\s+", " ", (leccion or "")).strip()
    if not t or len(t) > 320:
        return None
    previo = Cfg.lecciones_rev.read_text(encoding="utf-8") if Cfg.lecciones_rev.is_file() else \
        "# Lecciones del revisor\n\nLas escribe el orquestador desde veredicto.json; las lee el revisor. Las útiles para el " \
        "ejecutor las pasa una persona a lecciones.md.\n\n"
    clave = re.sub(r"\W+", " ", t.lower())[:80]
    if clave in re.sub(r"\W+", " ", previo.lower()):
        return None
    Cfg.lecciones_rev.write_text(previo + f"- {datetime.now():%Y-%m-%d} · {gid} · {t}\n", encoding="utf-8")
    return t


def aprender(g: dict, lote: dict, ver: dict, P: dict) -> list[str]:
    """Historial de malla (celdas por base), propuestas del revisor dentro de LIMITES y lección. Devuelve los cambios.
    El commit se hace una vez al final del lote (commit_aprendizaje)."""
    caso = M.CASES / g["id"]
    cambios = []
    res = leer_json(caso / "resultado_solver.json", {}) or {}
    m02 = (caso / "macros" / "02-malla.java").read_text(encoding="utf-8") if (caso / "macros" / "02-malla.java").is_file() else ""
    mb = re.search(r"double BASE_MM = ([\d.]+)", m02)
    m03 = (caso / "macros" / "03-extensiones.java").read_text(encoding="utf-8") if (caso / "macros" / "03-extensiones.java").is_file() else ""
    me = re.search(r"double BASE_EXT_MM = ([\d.]+)", m03)
    D2 = lote.get("D2_esperado_mm") or lote.get("D2_cfturbo_mm")
    if finito(res.get("celdas")) and mb and D2:
        ext = sum(v for k, v in (res.get("celdas_region") or {}).items() if k.startswith("ext_"))
        entrada = {"caso": g["clave"], "nq": lote["nq"], "D2_mm": D2, "base_mm": float(mb.group(1)),
                   "celdas_sin_ext": res["celdas"] - ext, "celdas": res["celdas"], "estado": ver.get("estado")}
        if me:
            entrada["ext_base_factor"] = round(float(me.group(1)) / float(mb.group(1)))
        P["historial_malla"] = [e for e in P["historial_malla"] if e["caso"] != g["clave"]] + [entrada]
        cambios.append(f"historial de malla: {g['clave']} base {mb.group(1)} mm → {res['celdas']} celdas")
    prop = leer_json(Cfg.propuestas, []) or []
    aplicadas = False
    for p in prop if isinstance(prop, list) else []:
        k, v = p.get("parametro"), p.get("valor")
        if k in LIMITES and finito(v):
            lo, hi = LIMITES[k]
            v2 = min(hi, max(lo, v))
            if P.get(k) != v2:
                cambios.append(f"{k}: {P.get(k)} → {v2} ({p.get('razon', '')})")
                P[k] = v2
                aplicadas = True
        else:
            cambios.append(f"propuesta rechazada (fuera de lo permitido): {p}")
    if aplicadas:
        P["receta_version"] += 1
    Cfg.propuestas.unlink(missing_ok=True)
    if (t := anotar_leccion(g["clave"], ver.get("leccion", ""))):
        cambios.append(f"lección: {t[:120]}")
    escribir_json(Cfg.params, P)
    return cambios


def commit_aprendizaje(casos: list[str]) -> None:
    if Cfg.seco or not casos:
        return
    archivos = ["starccm/lote/parametros.json", "starccm/lote/lecciones_revisor.md"]
    archivos = [a for a in archivos if (REPO / a).is_file()]
    r = subprocess.run([GIT, "-C", str(REPO), "add", "--", *archivos], capture_output=True, text=True)
    if r.returncode == 0:
        r = subprocess.run([GIT, "-C", str(REPO), "diff", "--cached", "--quiet", "--", *archivos], capture_output=True)
        if r.returncode == 0:
            return   # nada que guardar
        msg = (f"lote: aprendido de {len(casos)} casos ({', '.join(casos[:6])}{'…' if len(casos) > 6 else ''})\n\n"
               "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>")
        r = subprocess.run([GIT, "-C", str(REPO), "commit", "-m", msg, "--", *archivos], capture_output=True, text=True)
    if r.returncode:
        evento("aviso", "", f"git no guardó el aprendizaje: {(r.stderr or r.stdout or '')[-300:]}")


# ---------------------------------------------------------------- tablas, consolidado e índice

COLS = ["id", "estado", "alertas", "graves", "tipo", "nq", "Z", "dBeta2_deg", "fD2", "intentos", "iteracion", "H_m", "H_rel",
        "H_ref_m", "H_rel_curva", "M_Nm", "eta", "deriva_H_pct_100it", "oscilacion_H_pct", "celdas", "base_mm",
        "D2_esperado_mm", "D2_medido_mm", "minutos", "coste_usd", "motivo", "fin"]


def _celda(v):
    if v is None:
        return ""
    if isinstance(v, float):
        return round(v, 4)
    if isinstance(v, list):
        return ", ".join(map(str, v))
    return v


def tabla(estado: dict) -> None:
    """CSV del lote. Si está bloqueado (abierto en Excel) no tumba nada: se avisa y se reintenta en la próxima."""
    f = Cfg.geo / "_lote_simulacion.csv"
    tmp = f.with_name(f.name + ".tmp")
    try:
        with open(tmp, "w", newline="", encoding="utf-8-sig") as fh:
            w = csv.writer(fh, delimiter=";")
            w.writerow(COLS)
            for k in sorted(estado):
                w.writerow([k] + [_celda(estado[k].get(c)) for c in COLS[1:]])
        os.replace(tmp, f)
    except OSError as e:
        evento("aviso", "", f"no pude escribir {f.name} (¿abierto en Excel?): {e}")


def fila_estado(gid: str, previo: dict | None = None) -> dict | None:
    """Reconstruye la fila de estado de un caso desde lo que hay en cases/<ID>/ (para --consolidar)."""
    caso = M.CASES / gid
    lote = leer_json(caso / "lote.json")
    if not lote:
        return None
    chq = leer_json(caso / "chequeos.json", {}) or {}
    ver = leer_json(caso / "veredicto.json", {}) or {}
    e = dict(previo or {})
    e.update({k: lote.get(k) for k in ("tipo", "nq", "Z", "dBeta2_deg", "fD2", "base_mm", "D2_esperado_mm")})
    e.update({k: chq.get(k) for k in ("iteracion", "H_m", "H_rel", "H_ref_m", "H_rel_curva", "M_Nm", "eta",
                                      "deriva_H_pct_100it", "oscilacion_H_pct", "celdas", "D2_medido_mm")})
    e["intentos"] = lote.get("intento")
    e["graves"] = chq.get("graves_fallidos") or []
    if ver.get("estado") in ESTADOS_FINALES:
        e["estado"] = ver["estado"]
        e["motivo"] = ver.get("motivo", "")
        e["alertas"] = ver.get("alertas") or chq.get("avisos") or []
    return e


def curva_convergencia(caso: Path, ventana: int = 200) -> Path | None:
    """PNG con H, M y η por iteración desde monitores_historial.csv (sin matplotlib no hay curva, y no pasa nada)."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return None
    hdr, d = leer_monitores(caso)
    if not d:
        return None
    cols = [(n, hdr.index(n)) for n in ("H", "M", "eta") if n in hdr]
    if not cols:
        return None
    it = [r[0] for r in d]
    i0 = next((i for i, x in enumerate(it) if x >= 50), 0)   # las primeras iteraciones aplastan la escala
    fig, axs = plt.subplots(len(cols), 1, figsize=(8, 2.2 * len(cols)), sharex=True)
    axs = axs if len(cols) > 1 else [axs]
    for ax, (n, j) in zip(axs, cols):
        ax.plot(it[i0:], [r[j] for r in d[i0:]], lw=1)
        ax.axvspan(max(it[-1] - ventana, it[i0]), it[-1], color="0.85", zorder=0)   # ventana del promedio
        ax.set_ylabel({"H": "H [m]", "M": "M [N·m]", "eta": "η"}[n])
        ax.grid(alpha=0.3)
    axs[-1].set_xlabel("iteración")
    axs[0].set_title(caso.name)
    fig.tight_layout()
    out = caso / "images" / "convergencia.png"
    fig.savefig(out, dpi=90)
    plt.close(fig)
    return out


def consolidado(estado: dict) -> None:
    """_resultados_CFD.xlsx (resultados, base vs variantes, chequeos) e _indice_CFD.html en Geometrias_Prueba."""
    filas = [{"id": k, **v} for k, v in sorted(estado.items())]
    try:
        from openpyxl import Workbook
        from openpyxl.utils import get_column_letter
        wb = Workbook()
        ws = wb.active
        ws.title = "Resultados"
        ws.append(COLS)
        for f in filas:
            ws.append([_celda(f.get(c)) for c in COLS])
        ws2 = wb.create_sheet("Base_vs_variantes")
        ws2.append(["variante", "base", "nq", "Z", "dBeta2_deg", "fD2", "H_var_m", "H_base_m", "dH_pct", "eta_var", "eta_base", "deta"])
        for f in filas:
            if f.get("tipo") != "variante":
                continue
            lote = leer_json(M.CASES / f["id"] / "lote.json", {}) or {}
            b = estado.get(Cfg.prefijo + (lote.get("base_gid") or ""), {})
            if finito(f.get("H_m")) and finito(b.get("H_m")):
                ws2.append([f["id"], lote.get("base_gid"), f.get("nq"), f.get("Z"), f.get("dBeta2_deg"), f.get("fD2"),
                            f["H_m"], b["H_m"], (f["H_m"] / b["H_m"] - 1) * 100, f.get("eta"), b.get("eta"),
                            (f.get("eta") or 0) - (b.get("eta") or 0)])
        ws3 = wb.create_sheet("Chequeos")
        ws3.append(["id", "chequeo", "valor", "limite", "ok", "grave"])
        for f in filas:
            for c in (leer_json(M.CASES / f["id"] / "chequeos.json", {}) or {}).get("chequeos", []):
                ws3.append([f["id"], c["chequeo"], _celda(c["valor"]) if not isinstance(c["valor"], (dict, list)) else str(c["valor"]),
                            c["limite"], c["ok"], c["grave"]])
        for w in (ws, ws2, ws3):
            w.freeze_panes = "B2"
            for i in range(1, w.max_column + 1):
                w.column_dimensions[get_column_letter(i)].width = 14
        out = Cfg.geo / "_resultados_CFD.xlsx"
        tmp = out.with_name("_resultados_CFD.tmp.xlsx")
        wb.save(tmp)
        os.replace(tmp, out)
    except ImportError:
        evento("aviso", "", "sin openpyxl: no hay _resultados_CFD.xlsx (pip install openpyxl)")
    except OSError as e:
        evento("aviso", "", f"no pude escribir _resultados_CFD.xlsx (¿abierto en Excel?): {e}")
    # índice HTML con enlaces relativos a cada carpeta CFD y miniaturas
    color = {"OK": "#1a7f37", "REVISAR": "#b35900", "ERROR": "#c62828", "ERROR_INFRA": "#c62828"}
    filas_html = []
    for f in filas:
        lote = leer_json(M.CASES / f["id"] / "lote.json", {}) or {}
        carpeta = Path(lote.get("carpeta", "")).name
        img = lambda n: f'<a href="{carpeta}/CFD/images/{n}"><img src="{carpeta}/CFD/images/{n}" loading="lazy"></a>'
        num = lambda x, n=2: "" if not finito(x) else f"{x:.{n}f}"
        filas_html.append(
            f'<tr><td><a href="{carpeta}/CFD/">{f["id"]}</a></td>'
            f'<td style="color:{color.get(f.get("estado"), "#555")};font-weight:600">{f.get("estado", "")}</td>'
            f'<td>{num(f.get("H_m"), 1)}</td><td>{num(f.get("H_rel"))}</td><td>{num(f.get("eta"), 3)}</td>'
            f'<td>{f.get("celdas") or ""}</td><td>{num(f.get("deriva_H_pct_100it"))}</td>'
            f'<td class="m">{_celda(f.get("alertas")) or ""}</td><td>{img("presion_alabes.png")}</td>'
            f'<td>{img("convergencia.png")}</td></tr>')
    html = ("<!doctype html><meta charset='utf-8'><title>Lote CFD</title><style>body{font:14px system-ui;margin:16px}"
            "table{border-collapse:collapse}td,th{border-bottom:1px solid #ddd;padding:4px 8px;text-align:left;vertical-align:top}"
            "img{height:70px}.m{max-width:260px;font-size:12px;color:#555}</style>"
            f"<h1>Lote CFD · {len(filas)} geometrías · {datetime.now():%Y-%m-%d %H:%M}</h1>"
            "<p>Resultados en <a href='_resultados_CFD.xlsx'>_resultados_CFD.xlsx</a> y "
            "<a href='_lote_simulacion.csv'>_lote_simulacion.csv</a>.</p>"
            "<table><tr><th>caso</th><th>estado</th><th>H [m]</th><th>H/diseño</th><th>η</th><th>celdas</th>"
            "<th>deriva H %/100it</th><th>alertas</th><th>álabes</th><th>convergencia</th></tr>"
            + "".join(filas_html) + "</table>")
    try:
        (Cfg.geo / "_indice_CFD.html").write_text(html, encoding="utf-8")
    except OSError as e:
        evento("aviso", "", f"no pude escribir _indice_CFD.html: {e}")


def consolidar(estado: dict) -> dict:
    """Rehace estado.json, el CSV, el xlsx, las curvas y el índice desde lo que hay en cases/ (fuente de verdad).
    Vuelve a calcular los chequeos con los criterios actuales (sin solver): completa en lote.json lo que las versiones
    anteriores no guardaban (curva de CFturbo, base, recorte) y respeta el veredicto del revisor."""
    todas = geometrias()
    P = leer_json(Cfg.params)
    for g in todas:
        lote = leer_json(M.CASES / g["id"] / "lote.json")
        if lote and (M.CASES / g["id"] / "resultado_solver.json").is_file():
            dat = datos(g)
            dat["D2_esperado_mm"] = d2_esperado(g, dat, todas)
            for k in ("Z", "dBeta2_deg", "fD2", "f_D2_real", "base_gid", "clave", "D2_esperado_mm"):
                lote.setdefault(k, dat.get(k))
            lote["H_referencia_m"] = h_referencia(g, dat, todas)
            escribir_json(M.CASES / g["id"] / "lote.json", lote)
            chequear(g, lote, P, estado)
            cfd = Path(lote["carpeta"]) / "CFD"
            if cfd.is_dir():
                for f in ("lote.json", "chequeos.json"):
                    shutil.copy2(M.CASES / g["id"] / f, cfd / f)
    for g in todas:
        e = fila_estado(g["id"], estado.get(g["id"]))
        if not e:
            continue
        estado[g["id"]] = e
        lote = leer_json(M.CASES / g["id"] / "lote.json", {}) or {}
        if curva_convergencia(M.CASES / g["id"]) and lote.get("carpeta"):
            dst = Path(lote["carpeta"]) / "CFD" / "images"
            if dst.is_dir():
                shutil.copy2(M.CASES / g["id"] / "images" / "convergencia.png", dst / "convergencia.png")
    escribir_json(Cfg.estado, estado)
    tabla(estado)
    consolidado(estado)
    return estado


# ---------------------------------------------------------------- bucle

def reanudable(gid: str, previo: dict) -> dict | None:
    """Un caso que quedó «en curso» (corte, reinicio) con la ejecución del intento ya terminada se retoma desde los
    chequeos, sin volver a gastar solver. Devuelve su lote.json o None."""
    caso = M.CASES / gid
    lote = leer_json(caso / "lote.json")
    if previo.get("estado") != "en curso" or not lote:
        return None
    eje = leer_json(caso / "ejecucion.json", {}) or {}
    if eje.get("estado") in ("COMPLETO", "REVISAR") and (caso / "resultado_solver.json").is_file() \
            and (caso / "resultado_solver.json").stat().st_mtime >= (caso / "lote.json").stat().st_mtime:
        return lote
    return None


def parar_pedido() -> bool:
    return (LOTE / "PARAR").is_file() and not Cfg.seco


def una(g: dict, todas: list[dict], estado: dict, extender_hasta: int | None = None) -> None:
    gid = g["id"]
    caso = M.CASES / gid
    P = leer_json(Cfg.params)
    t0 = time.time()
    coste = 0.0
    previo = estado.get(gid, {})
    retomar = reanudable(gid, previo) if extender_hasta is None else None
    e = {"estado": "en curso", "inicio": ahora(), "intentos": 0,
         "anterior": {k: previo.get(k) for k in ("estado", "H_m", "eta", "fin", "motivo") if previo.get(k) is not None}}
    estado[gid] = e
    escribir_json(Cfg.estado, estado)
    if extender_hasta:
        lj = leer_json(caso / "lote.json")
        if not lj or not (M.SIMS / f"{gid}.sim").is_file():
            raise RuntimeError(f"no hay caso o .sim que extender: {caso}, sims/{gid}.sim")
        intentos = [(lj["intento"] + 1, "extender", f"Seguir iterando hasta {extender_hasta} sin remallar.", extender_hasta)]
    elif retomar:
        evento("aviso", gid, f"retomo el intento {retomar['intento']}: la ejecución ya había terminado")
        intentos = [(retomar["intento"], retomar.get("tipo_intento", "completo"), retomar.get("instrucciones_reintento", ""),
                     retomar.get("iteraciones"))]
    else:
        # intento limpio: lo de un intento anterior se aparta (no se borra)
        if not Cfg.seco and (M.SIMS / f"{gid}.sim").is_file():
            ap = M.SIMS / "_previos"
            ap.mkdir(exist_ok=True)
            shutil.move(str(M.SIMS / f"{gid}.sim"), ap / f"{gid}_{datetime.now():%Y%m%d_%H%M%S}.sim")
        if caso.is_dir():
            (M.CASES / "_previos").mkdir(exist_ok=True)
            shutil.move(str(caso), M.CASES / "_previos" / f"{gid}_{datetime.now():%Y%m%d_%H%M%S}")
        intentos = [(1, "completo", "", None)]
    ver, chq, lote = {}, {}, {}
    while intentos:
        intento, tipo, instr, max_it = intentos.pop(0)
        lote = preparar(g, todas, P, intento, tipo, instr, max_it) if not (retomar and intento == retomar["intento"]) else retomar
        e["intentos"] = intento
        if not (retomar and intento == retomar["intento"]):
            evento("inicio", gid, f"intento {intento} ({tipo}): nq {lote['nq']} {lote['tipo']}, Q {lote['Q_m3h']} m³/h, "
                                  f"H diseño {lote['H_diseno_m']} m, base {lote['base_mm']} mm, {lote['iteraciones']} it.")
            r = ejecutar(g, lote)
            coste += r.get("coste_usd") or 0
            asegurar_solver_apagado(gid)
            if not (caso / "resultado_solver.json").is_file() and (r.get("rc") or r.get("cortado") or r.get("subtipo") != "success"):
                raise ErrorInfra(f"el ejecutor no dejó resultado (rc {r.get('rc')}, {r.get('subtipo')}, "
                                 f"{'cortado por tiempo' if r.get('cortado') else 'sin corte'})")
        chq = chequear(g, lote, P, estado)
        puede_extender = lote["iteraciones"] < P["iteraciones_extension"]
        if chq["solo_falta_convergencia"] and intento == 1 and puede_extender and not parar_pedido():
            # H aún se mueve y todo lo demás está bien: seguir iterando es lo que pediría el revisor; no se le gasta
            ins = (f"H sigue moviéndose (deriva {chq['deriva_H_pct_100it']:.2f} %/100 it., oscilación "
                   f"{chq['oscilacion_H_pct']:.2f} %): seguir de {lote['iteraciones']} a {P['iteraciones_extension']} it. sin remallar.")
            evento("reintento", gid, ins)
            intentos.append((2, "extender", ins, P["iteraciones_extension"]))
            continue
        rv = revisar(g, lote)
        coste += rv.get("coste_usd") or 0
        ver = leer_json(caso / "veredicto.json", {}) or veredicto_denegado(caso / "logs" / f"revisor_{intento}.jsonl")
        if ver.get("estado") not in ("OK", "REINTENTAR", "REVISAR"):  # sin revisor: los chequeos deciden
            ver = {"estado": "OK" if not chq["graves_fallidos"] else "REVISAR",
                   "motivo": "sin veredicto del revisor; decidido por los chequeos: " + (", ".join(chq["graves_fallidos"]) or "todo bien")}
        ver.setdefault("alertas", chq["avisos"])
        escribir_json(caso / "veredicto.json", ver)
        if ver["estado"] == "REINTENTAR" and intento == 1 and not parar_pedido():
            tipo2 = "extender" if ver.get("reintento") == "extender" and puede_extender else "rehacer"
            instr = ver.get("instrucciones_reintento") or ver.get("motivo", "")
            evento("reintento", gid, f"{tipo2}: {instr[:280]}")
            intentos.append((2, tipo2, instr, P["iteraciones_extension"] if tipo2 == "extender" else None))
            continue
        if ver["estado"] == "REINTENTAR":
            ver["estado"] = "REVISAR"
            escribir_json(caso / "veredicto.json", ver)
    destino = entregar(g, lote, P)
    curva_convergencia(caso)
    if (caso / "images" / "convergencia.png").is_file():
        shutil.copy2(caso / "images" / "convergencia.png", destino / "images" / "convergencia.png")
    cambios = aprender(g, lote, ver, P)
    e.update({k: lote.get(k) for k in ("tipo", "nq", "Z", "dBeta2_deg", "fD2", "base_mm", "D2_esperado_mm")})
    e.update({k: chq.get(k) for k in ("iteracion", "H_m", "H_rel", "H_ref_m", "H_rel_curva", "M_Nm", "eta",
                                      "deriva_H_pct_100it", "oscilacion_H_pct", "celdas", "D2_medido_mm")})
    e.update(estado=ver["estado"], motivo=ver.get("motivo", ""), alertas=ver.get("alertas", []), graves=chq["graves_fallidos"],
             minutos=round((time.time() - t0) / 60, 1), coste_usd=round(coste, 2), fin=ahora(), destino=str(destino))
    escribir_json(Cfg.estado, estado)
    tabla(estado)
    fmt = lambda x, n=1: "—" if not finito(x) else f"{x:.{n}f}"
    evento("fin", gid, f"{ver['estado']}: H {fmt(chq['H_m'])} m ({fmt((chq['H_rel'] or 0) * 100, 0)} % del diseño), "
                       f"η {fmt(chq['eta'], 3)}, {chq['celdas']} celdas, {e['minutos']} min. {ver.get('motivo', '')[:200]}",
           estado=ver["estado"], cambios=cambios)


def main(argv: list[str]) -> int:
    if "--seco" in argv:
        return seco()
    todas = geometrias()
    estado = leer_json(Cfg.estado, {}) or {}
    arg = lambda k: argv[argv.index(k) + 1] if k in argv and argv.index(k) + 1 < len(argv) else None
    if "--estado" in argv:
        for k in sorted(estado):
            print(k, estado[k].get("estado"), estado[k].get("H_m"), estado[k].get("eta"), str(estado[k].get("motivo", ""))[:80])
        return 0
    if "--preparar" in argv:
        ids = arg("--preparar").split(",")
        P = leer_json(Cfg.params)
        for g in todas:
            if any(g["clave"].startswith(i) for i in ids):
                lote = preparar(g, todas, P)
                print(f"{g['id']}: listo, base {lote['base_mm']} mm, D2 esperado {lote['D2_esperado_mm']} mm, "
                      f"{len(list((M.CASES / g['id'] / 'macros').glob('*.java')))} macros compiladas")
        return 0
    if "--consolidar" in argv:
        consolidar(estado)
        print(f"consolidado: {len(estado)} casos → {Cfg.geo / '_resultados_CFD.xlsx'}, _lote_simulacion.csv, _indice_CFD.html")
        return 0
    if "--limpiar-backups" in argv:
        libres = 0
        for k, v in estado.items():
            if v.get("estado") in ESTADOS_FINALES:
                for b in M.SIMS.glob(f"{k}.sim~*"):
                    libres += b.stat().st_size
                    b.unlink()
        print(f"liberados {libres / 1e9:.1f} GB de sims/*.sim~")
        return 0
    if not tomar_lock():
        return 2
    hechos: list[str] = []
    try:
        evento("arranque", "", f"PID {os.getpid()}")
        asegurar_solver_apagado("")       # un solver que dejó una corrida anterior caída no debe bloquear la licencia
        extender = arg("--extender")
        if extender:
            hasta = int(arg("--hasta") or leer_json(Cfg.params)["iteraciones_extension"])
            cola = [g for g in todas if any(g["clave"].startswith(s) for s in extender.split(","))]
        else:
            solo = arg("--solo")
            estados = set(arg("--estados").split(",")) if arg("--estados") else None
            cola = [g for g in todas if (solo is None or any(g["clave"].startswith(s) for s in solo.split(",")))
                    and (estados is None or estado.get(g["id"], {}).get("estado") in estados)
                    and (solo is not None or estados is not None or estado.get(g["id"], {}).get("estado") not in ESTADOS_FINALES)]
        evento("lote_inicio", "", f"{len(cola)} geometrías: {', '.join(g['clave'] for g in cola)}")
        infra = 0
        for g in cola:
            if parar_pedido():
                evento("lote_parado", "", "encontré lote/PARAR")
                (LOTE / "PARAR").unlink(missing_ok=True)
                break
            try:
                una(g, todas, estado, hasta if extender else None)
                hechos.append(g["clave"])
                infra = 0
            except ErrorInfra as ex:
                infra += 1
                asegurar_solver_apagado(g["id"])
                estado.setdefault(g["id"], {}).update(estado="ERROR_INFRA", motivo=str(ex)[:300], fin=ahora())
                escribir_json(Cfg.estado, estado)
                tabla(estado)
                evento("error", g["id"], f"infraestructura: {str(ex)[:280]}")
                if infra >= MAX_INFRA_SEGUIDOS:
                    evento("lote_parado", "", f"{infra} fallos de infraestructura seguidos (¿cuota, red o sesión de claude?): "
                                              "paro para no quemar la cola; relanzar retoma desde aquí")
                    break
            except Exception as ex:  # noqa: BLE001  una geometría rota no para el lote
                asegurar_solver_apagado(g["id"])
                estado.setdefault(g["id"], {}).update(estado="ERROR", motivo=str(ex)[:300], fin=ahora())
                escribir_json(Cfg.estado, estado)
                tabla(estado)
                evento("error", g["id"], str(ex)[:300])
        resumen = [v.get("estado") for v in estado.values()]
        consolidado(estado)
        evento("lote_fin", "", f"OK {resumen.count('OK')}, REVISAR {resumen.count('REVISAR')}, "
                               f"ERROR {resumen.count('ERROR') + resumen.count('ERROR_INFRA')}")
        return 0
    except KeyboardInterrupt:
        evento("lote_abortado", "", "interrumpido (Ctrl+C o cierre)")
        asegurar_solver_apagado("")
        return 130
    finally:
        commit_aprendizaje(hechos)
        soltar_lock()


def seco() -> int:
    """Prueba en seco de punta a punta con ejecutor y revisor falsos (lote/falso_claude.py), todo en un temporal y sin git.
    Cubre: G002 base que deriva → extensión automática → OK; G034 variante con el par al revés → REINTENTAR → REVISAR;
    G033 con claude caído → ERROR_INFRA; y luego reanudar un caso «en curso» con la ejecución ya hecha."""
    tmp = Path(tempfile.mkdtemp(prefix="lote-seco-"))
    try:
        (tmp / "geo").mkdir()
        shutil.copy2(GEO / "_estado.json", tmp / "geo" / "_estado.json")
        for d in GEO.iterdir():
            if d.is_dir() and d.name[:5] in ("G002_", "G033_", "G034_"):
                shutil.copytree(d, tmp / "geo" / d.name, ignore=shutil.ignore_patterns("CFD", "*.html", "*.pdf"))
        shutil.copy2(LOTE / "parametros.json", tmp / "parametros.json")
        n0 = len(leer_json(tmp / "parametros.json")["historial_malla"])
        ids0 = {h["caso"] for h in leer_json(tmp / "parametros.json")["historial_malla"]}
        Cfg.seco, Cfg.geo, Cfg.params, Cfg.estado, Cfg.eventos, Cfg.prefijo = True, tmp / "geo", tmp / "parametros.json", tmp / "estado.json", tmp / "eventos.log", "SECO_"
        Cfg.propuestas, Cfg.lecciones_rev, Cfg.lock = tmp / "propuestas.json", tmp / "lecciones_revisor.md", tmp / ".lock"
        os.environ["FALSO_CAIDO"] = "G033"
        rc = main(["--solo", "G002,G033,G034"])
        est = leer_json(Cfg.estado, {})
        P = leer_json(Cfg.params)
        fallos = []
        exp = {"SECO_G002_nq15_B": "OK", "SECO_G034_nq65_V": "REVISAR", "SECO_G033_nq65_B": "ERROR_INFRA"}
        for k, v in exp.items():
            if est.get(k, {}).get("estado") != v:
                fallos.append(f"{k}: {est.get(k, {}).get('estado')} (esperaba {v})")
        if est.get("SECO_G002_nq15_B", {}).get("intentos") != 2 or est.get("SECO_G002_nq15_B", {}).get("iteracion") != P["iteraciones_extension"]:
            fallos.append("G002 debía extenderse automáticamente a iteraciones_extension")
        if not (tmp / "geo" / "_lote_simulacion.csv").is_file() or not (tmp / "geo" / "_indice_CFD.html").is_file():
            fallos.append("faltan _lote_simulacion.csv o _indice_CFD.html")
        if not any((tmp / "geo").glob("G002_*/CFD/*.sim")) or not any((tmp / "geo").glob("G002_*/CFD/images/*.png")):
            fallos.append("la entrega de G002 no tiene .sim o imágenes")
        if len(P["historial_malla"]) != len(ids0 | {"G002_nq15_B", "G034_nq65_V"}) or len(P["historial_malla"]) < n0:
            fallos.append("historial de malla")
        if P["min_rotor_pct"] != 40.0 or P["iteraciones"] != 1000:
            fallos.append("propuestas: límite o prohibición no aplicados")
        if Cfg.lock.is_file():
            fallos.append("quedó el .lock")
        # reanudar: G002 «en curso» con la ejecución hecha → se retoma sin ejecutor (falso caído para todos)
        est["SECO_G002_nq15_B"]["estado"] = "en curso"
        escribir_json(Cfg.estado, est)
        os.environ["FALSO_CAIDO"] = "todos"
        (M.CASES / "SECO_G002_nq15_B" / "lote.json").touch()
        os.utime(M.CASES / "SECO_G002_nq15_B" / "resultado_solver.json")
        main(["--solo", "G002"])
        if leer_json(Cfg.estado, {}).get("SECO_G002_nq15_B", {}).get("estado") != "OK":
            fallos.append("no se retomó G002 desde los chequeos")
        print("SECO:", "todo en verde" if not fallos and rc == 0 else "FALLA " + "; ".join(fallos),
              json.dumps({k: v.get("estado") for k, v in leer_json(Cfg.estado, {}).items()}))
        print((tmp / "eventos.log").read_text(encoding="utf-8"))
        return 0 if not fallos and rc == 0 else 1
    finally:
        os.environ.pop("FALSO_CAIDO", None)
        for d in M.CASES.glob("SECO_*"):
            shutil.rmtree(d, ignore_errors=True)
        for d in (M.CASES / "_previos").glob("SECO_*") if (M.CASES / "_previos").is_dir() else []:
            shutil.rmtree(d, ignore_errors=True)
        for f in M.SIMS.glob("SECO_*"):
            f.unlink(missing_ok=True)
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    for s in (sys.stdout, sys.stderr):  # consola o log de Windows en cp1252: η y ³ no deben tumbar el lote
        s.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main(sys.argv[1:]))
