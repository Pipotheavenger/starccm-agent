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
    espera_infra = 1800          # s antes de reintentar tras un fallo de infraestructura
    parar = LOTE / "PARAR"


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
    """Escritura atómica. En Windows os.replace falla (WinError 5) si otro proceso tiene el destino abierto (la sesión
    monitora leyendo estado.json): se reintenta unos segundos antes de rendirse."""
    tmp = Path(str(p) + ".tmp")
    tmp.write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")
    for i in range(20):
        try:
            os.replace(tmp, p)
            return
        except PermissionError:
            if i == 19:
                raise
            time.sleep(0.5)


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
    """Celdas de extensiones / celdas de la bomba a esa nq. Con ≥ 3 casos de extensiones gruesas (2 × base) a ±15 de nq,
    su mediana; si no, la fracción de las extensiones finas (mismo base, receta v1) a esa nq dividida por 2 (las celdas
    van ~1/base: base doble ≈ mitad de celdas)."""
    h = [e for e in P["historial_malla"] if e.get("celdas_sin_ext") and abs(e["nq"] - nq) <= 15]
    gruesas = [e["celdas"] / e["celdas_sin_ext"] - 1 for e in h if e.get("ext_base_factor") == 2]
    if len(gruesas) >= 3:
        return statistics.median(gruesas)
    finas = [e["celdas"] / e["celdas_sin_ext"] - 1 for e in h if e.get("ext_base_factor") != 2]
    return statistics.median(finas) / 2 if finas else 0.15


def modelo_malla(P: dict) -> list | None:
    """ln(celdas_bomba) = c0 + c1·ln(base) + c2·ln nq + c3·ln² nq sobre todo el historial. En 47 casos el D2 no explica
    nada (coef. −0,02) y c1 ≈ −0,97: las celdas van ~1/base, no 1/base³ (prismas y superficie dominan). Error ~6 % con
    validación cruzada dejando uno fuera."""
    h = [e for e in P["historial_malla"] if e.get("celdas_sin_ext") and e.get("base_mm") and e.get("estado") != "ERROR"]
    if len(h) < 8:
        return None
    A = [[1.0, math.log(e["base_mm"]), math.log(e["nq"]), math.log(e["nq"]) ** 2] for e in h]
    c = _mc(A, [math.log(e["celdas_sin_ext"]) for e in h])
    return c if c and -2.0 < c[1] < -0.4 else None


def exponente_malla(P: dict) -> float:
    """k en celdas ∝ base^−k, para la regla de remallado de la receta: base_nuevo = base·(celdas/objetivo)^(1/k)."""
    c = modelo_malla(P)
    return round(-c[1], 2) if c else 1.0


def base_mm(P: dict, dat: dict) -> float:
    """Tamaño base para que la bomba (sin extensiones) dé objetivo/(1+ext) celdas, con el modelo del historial. Sin
    extrapolar: el base queda dentro de lo visto a nq parecida (±15 %). Sin modelo: el vecino de nq más cercana."""
    nq = dat["nq"]
    obj = P["objetivo_celdas"] / (1 + frac_extensiones(P, nq))
    h = [e for e in P["historial_malla"] if e.get("celdas_sin_ext") and e.get("base_mm") and e.get("estado") != "ERROR"]
    c = modelo_malla(P)
    if c:
        ln = math.log(nq)
        base = math.exp((math.log(obj) - c[0] - c[2] * ln - c[3] * ln * ln) / c[1])
        cerca = [e["base_mm"] for e in h if abs(e["nq"] - nq) <= 10] or [e["base_mm"] for e in h]
        return round(min(max(base, 0.85 * min(cerca)), 1.15 * max(cerca)), 1)
    if h:
        e = min(h, key=lambda e: abs(e["nq"] - nq))
        return round(e["base_mm"] * (e["celdas_sin_ext"] / obj), 1)
    D2 = dat.get("D2_esperado_mm") or dat["D2_cfturbo_mm"] or 250.0
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
    # nq bajas: H se asienta entre 1300 y 1500 (9 de 13 casos ≤ nq 25 lo necesitaron); empezar ahí ahorra reabrir el .sim
    nb = P.get("iteraciones_nq_bajo") or {}
    it0 = nb["iteraciones"] if nb and dat["nq"] <= nb["nq_max"] else P["iteraciones"]
    max_it = max_it or lj.get("iteraciones") or it0
    destino = Path(dat["carpeta"]) / "CFD" / f"{dat['nombre']}.sim"
    lote = {**{k: v for k, v in dat.items() if k != "cad_caso"}, "H_referencia_m": h_referencia(g, dat, todas),
            "base_mm": base, "exponente_malla": exponente_malla(P), "intento": intento, "tipo_intento": tipo_intento,
            "instrucciones_reintento": instrucciones,
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
    """claude -p con salida stream-json a `log`. Devuelve rc, segundos, coste, subtipo y si se cortó por tiempo.
    `--setting-sources project`: sin los plugins y skills del usuario (menos contexto y coste en cada sesión)."""
    cmd = [CLAUDE, "-p", prompt, "--model", modelo, "--output-format", "stream-json", "--verbose",
           "--setting-sources", "project", "--mcp-config", str(REPO / ".mcp.json"), "--strict-mcp-config",
           "--allowedTools", permitidas,
           "--disallowedTools", "Bash,PowerShell,NotebookEdit,WebFetch,WebSearch,mcp__starccm__recipe_save,"
                                "Read(**/.env*),Read(**/.starccm-agent.env)",
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
        except BaseException:   # Ctrl+C o cierre: el hijo tiene su propia consola y no se entera; matarlo antes de salir
            subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"], capture_output=True)
            raise
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
    # sin recipe_save (recipes/ es compartida) ni docs/inspect sueltos que no hacen falta. Riesgo asumido: run_java y
    # run_java_file ejecutan Java en la JVM del solver, que puede hacer cualquier cosa; el veto a Bash no lo cubre.
    mcp = ",".join(f"mcp__starccm__{t}" for t in ("server_start", "server_stop", "server_status", "run_java",
                                                   "run_java_file", "inspect", "save", "recipe_search", "export_scene"))
    permitidas = f"{mcp},Read,Glob,Grep,Write(cases/{g['id']}/**),Edit(cases/{g['id']}/**)"
    return claude(prompt, MODELO_EJECUTOR, permitidas, caso / "logs" / f"ejecutor_{n}.jsonl", T_EJECUTOR, 250)


def es_infra(r: dict) -> bool:
    """claude no llegó a trabajar: salió con error sin línea `result` (cuota, red, sesión) o con un error de la API.
    Agotar turnos o el tiempo es un problema del caso, no de infraestructura."""
    if r.get("cortado") or r.get("subtipo") == "error_max_turns":
        return False
    return bool(r.get("rc")) and r.get("subtipo") in (None, "error_during_execution")


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

def _vivo(pid, imagen: str = "") -> bool:
    """PID vivo y, si se da `imagen`, con ese ejecutable (tras un reinicio el PID puede ser de otro proceso)."""
    try:
        if not (pid and M._pid_alive(int(pid))):
            return False
        if not imagen or Cfg.seco:
            return True
        r = subprocess.run(["tasklist", "/FI", f"PID eq {int(pid)}", "/FO", "CSV", "/NH"], capture_output=True, text=True)
        return imagen.lower() in r.stdout.lower()
    except Exception:  # noqa: BLE001
        return False


def lote_vivo() -> dict | None:
    """El candado de otro orquestador vivo, o None."""
    l = leer_json(Cfg.lock, {}) or {}
    if l and int(l.get("pid") or 0) != os.getpid() and _vivo(l.get("pid"), "python"):
        return l
    return None


def tomar_lock() -> bool:
    """lote/.lock con el PID: dos orquestadores sobre una licencia de una copia se pisan. Si el anterior murió, se limpia
    lo que dejó (su claude hijo y el solver)."""
    if (l := lote_vivo()):
        print(f"Ya hay un orquestador vivo (PID {l['pid']}, desde {l.get('inicio')}). Si no es así, borra {Cfg.lock}.")
        return False
    l = leer_json(Cfg.lock, {}) or {}
    if l.get("hijo") and _vivo(l["hijo"], "claude"):
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


def _tendencia(pts: list) -> tuple[float, float, float]:
    """Media, pendiente (% de la media por 100 it.) y oscilación sin tendencia (2·σ del residuo, % de la media)."""
    xs = [x for x, _ in pts]
    ys = [y for _, y in pts]
    m, mx = sum(ys) / len(ys), sum(xs) / len(xs)
    sxx = sum((x - mx) ** 2 for x in xs)
    b = sum((x - mx) * (y - m) for x, y in pts) / sxx if sxx else 0.0
    res = [y - (m + b * (x - mx)) for x, y in pts]
    return m, b * 100 / abs(m) * 100, 2 * statistics.pstdev(res) / abs(m) * 100


def historial(caso: Path, ventana: int = 200) -> dict:
    """Por monitor, en las últimas `ventana` iteraciones: media, mín., máx., deriva (pendiente lineal en % por 100 it.) y
    oscilación sin tendencia (2·σ del residuo, %). La deriva también en 2 × ventana: una oscilación lenta (G001) da
    pendiente en 200 it. que desaparece en 400; una deriva real (G003, G005) sale en las dos con el mismo signo."""
    hdr, datos_ = leer_monitores(caso)
    if not datos_:
        return {}
    it_max = max(r[0] for r in datos_)
    out = {}
    for j, nombre in enumerate(hdr[1:], start=1):
        todos = [(r[0], r[j]) for r in datos_ if j < len(r) and finito(r[j])]
        pts = [p for p in todos if p[0] > it_max - ventana]
        if not pts:
            continue
        ys = [y for _, y in pts]
        m = sum(ys) / len(ys)
        d = {"media": m, "min": min(ys), "max": max(ys), "n": len(ys), "ultimo": ys[-1]}
        if len(pts) >= 10 and abs(m) > 1e-9:
            _, d["deriva_pct_100it"], d["oscilacion_pct"] = _tendencia(pts)
            largo = [p for p in todos if p[0] > it_max - 2 * ventana]
            if len(largo) >= 1.5 * len(pts):
                _, d["deriva_larga_pct_100it"], _ = _tendencia(largo)
        out[nombre] = d
    out["_iteracion"] = it_max
    return out


def deriva_real(d: dict, limite: float) -> bool:
    """Deriva por encima del límite en la ventana Y en la ventana doble con el mismo signo (si hay ventana doble)."""
    a = d.get("deriva_pct_100it")
    if a is None or abs(a) <= limite:
        return False
    b = d.get("deriva_larga_pct_100it")
    return b is None or (abs(b) > limite / 2 and (a > 0) == (b > 0))


def eta_referencia(nq: int, estado: dict, excluir: str = "") -> float | None:
    """η esperada a esa nq según las OTRAS bases ya simuladas en este lote (interpolación por nq). Solo tiene sentido
    para bases: la η de una variante cae por su propia geometría."""
    pts = sorted((e["nq"], e["eta"]) for k, e in estado.items()
                 if k != excluir and e.get("tipo") == "base" and e.get("estado") == "OK" and finito(e.get("eta")) and e.get("nq"))
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
    # caudal: el másico impuesto en la salida tiene que ser el del punto de diseño (ρ·Q), y por la entrada tiene que
    # entrar lo mismo (la salida es la BC: compararla consigo misma no detecta nada)
    masa = lote.get("masa_kg_s")
    if masa and lote.get("rho") and lote.get("Q_m3h"):
        dqd = (masa / (lote["rho"] * lote["Q_m3h"] / 3600) - 1) * 100
        chk("caudal BC = ρ·Q de diseño %", dqd, f"|x| <= {C['Q_bc_tol_pct']}", abs(dqd) <= C["Q_bc_tol_pct"])
    qin = (h.get("Q_in") or {}).get("media", rep.get("Q_in"))
    if finito(qin) and masa:
        dqi = (abs(qin) / masa - 1) * 100
        chk("caudal que entra = BC %", dqi, f"|x| <= {C['balance_max_pct']}", abs(dqi) <= C["balance_max_pct"])
    # giro: con el par con el signo de una turbina la bomba gira al revés o el eje está mal. La 09 nueva siempre lo
    # escribe (lleva r_te_max_m): si falta o es null, la 09 falló a medias y no se puede dar por bueno
    sig = res.get("M_signo_ok")
    if sig is not None or "r_te_max_m" in res:
        chk("par con signo de bomba (giro y eje)", sig, "true", sig is True)
    if finito(Mm):
        chk("par no nulo", Mm, "|M| > 0", abs(Mm) > 1e-6)
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
    eref = eta_referencia(lote["nq"], estado or {}, g["id"]) if lote["tipo"] == "base" else None
    if eref is not None and finito(eta):
        chk("eta frente a las otras bases del lote a esa nq", eta - eref, f"±{C['eta_banda_nq']}",
            abs(eta - eref) <= C["eta_banda_nq"], grave=False)
    hh = h.get("H") or {}
    lim = C["deriva_H_max_pct_100it"]
    if "deriva_pct_100it" in hh:
        # deriva de H y de η graves (son los números que se entregan); la de M, aviso
        for mon, nombre, grave in (("H", "deriva de H %/100 it.", True), ("eta", "deriva de η %/100 it.", True),
                                   ("M", "deriva de M %/100 it.", False)):
            d = h.get(mon) or {}
            if "deriva_pct_100it" in d:
                chk(nombre, d["deriva_pct_100it"], f"|x| <= {lim} (en {P['ventana_promedio']} y {2 * P['ventana_promedio']} it.)",
                    not deriva_real(d, lim), grave=grave)
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
        # en nq bajas la fricción de disco es de por sí 20–35 % de la potencia (Gülich): el límite sube
        fmax = C["M_discos_max_frac"] if lote["nq"] >= 25 else C.get("M_discos_max_frac_nq_bajo", 0.45)
        fr = abs(md / mt)
        chk("par de discos / par total", fr, f"<= {fmax}", fr <= fmax, grave=False)
    imgs = len(list((caso / "images").glob("*.png")))
    chk("escenas PNG", imgs, f">= {C['escenas_min']}", imgs >= C["escenas_min"], grave=False)
    chk("ejecutor terminó", eje.get("estado"), "COMPLETO", eje.get("estado") == "COMPLETO")
    graves = [c["chequeo"] for c in lista if c["grave"] and not c["ok"]]
    out = {"H_m": H, "M_Nm": Mm, "eta": eta, "H_rel": Hrel, "H_ref_m": Href, "H_rel_curva": Hcur,
           "deriva_H_pct_100it": hh.get("deriva_pct_100it"), "oscilacion_H_pct": hh.get("oscilacion_pct"),
           "D2_medido_mm": round(2 * rmax * 1000, 2) if rmax else None, "celdas": cel, "iteracion": it,
           "graves_fallidos": graves, "avisos": [c["chequeo"] for c in lista if not c["grave"] and not c["ok"]],
           # iterar más solo arregla una deriva (y moderada): una oscilación sin deriva es física (carga parcial, nq bajas)
           "extender_util": bool(graves) and set(graves) <= {"deriva de H %/100 it.", "deriva de η %/100 it.",
                                                             "oscilación de H % (2σ sin tendencia)"}
                            and bool({"deriva de H %/100 it.", "deriva de η %/100 it."} & set(graves))
                            and abs(hh.get("deriva_pct_100it") or 0) < 10,
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
            shutil.copytree(caso / sub, dst / sub, dirs_exist_ok=True)
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
    if P.get("borrar_backups_sim") and dsim.is_file() and sim.is_file():
        for b in M.SIMS.glob(f"{g['id']}.sim~*"):
            # copias de seguridad de STAR-CCM+: sobran si el último guardado es posterior (si el guardado final falló,
            # el .sim~ puede ser la única copia buena y se queda)
            if b.stat().st_mtime < sim.stat().st_mtime:
                b.unlink(missing_ok=True)
    return dst


MAX_LECCIONES_NUEVAS = 40


def anotar_leccion(gid: str, leccion: str) -> str | None:
    """Las lecciones del revisor no entran en el prompt del ejecutor: van filtradas (una línea, corta, sin repetir el
    comienzo de otra, como mucho 40 sin consolidar) a lecciones_revisor.md. lote/lecciones.md (la que lee el ejecutor)
    solo la cambia una persona."""
    t = re.sub(r"\s+", " ", (leccion or "")).strip()
    if not t or len(t) > 320:
        return None
    if Cfg.lecciones_rev.is_file() and Cfg.lecciones_rev.read_text(encoding="utf-8").split("## Nuevas")[-1].count("\n- ") >= MAX_LECCIONES_NUEVAS:
        evento("aviso", gid, f"lecciones_revisor.md tiene {MAX_LECCIONES_NUEVAS} lecciones sin consolidar: no añado más")
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
        # base real de las extensiones: el que dejó la 02 (remalla con 2 × BASE_MM), no el que se puso en la 03
        mj = (leer_json(caso / "malla.json", {}) or {}).get("malla_02") or {}
        bext = mj.get("base_ext_mm") or (float(me.group(1)) if me else None)
        if finito(bext):
            entrada["ext_base_factor"] = round(bext / float(mb.group(1)))
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

COLS = ["id", "estado", "conflicto", "alertas", "graves", "tipo", "nq", "Z", "dBeta2_deg", "fD2", "intentos", "iteracion", "H_m", "H_rel",
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
    e["conflicto"] = conflicto(e.get("estado"), e["graves"], chq.get("extender_util"))
    return e


def conflicto(estado_: str | None, graves: list, extender_util: bool | None) -> str:
    """El veredicto se respeta, pero si los chequeos lo contradicen se dice en la tabla (no se reescribe en silencio)."""
    if estado_ == "OK" and graves:
        return "OK del revisor, pero los chequeos fallan: " + ", ".join(graves) + (" → --extender" if extender_util else "")
    if estado_ == "REVISAR" and not graves:
        return "REVISAR sin ningún chequeo grave: re-revisar"
    return ""


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
    v0 = it[-1] - ventana
    fig, axs = plt.subplots(len(cols), 1, figsize=(8, 2.2 * len(cols)), sharex=True)
    axs = axs if len(cols) > 1 else [axs]
    for ax, (n, j) in zip(axs, cols):
        ys = [r[j] for r in d[i0:]]
        ax.plot(it[i0:], ys, lw=1, color="#1f5fa8")
        ax.axvspan(v0, it[-1], color="#f2c14e", alpha=0.25, zorder=0)              # ventana del promedio
        fin = [r[j] for r in d if r[0] > v0]
        m = sum(fin) / len(fin)
        ax.axhline(m, color="#b35900", lw=1, ls="--")
        ax.text(it[-1], m, f" {m:.3g}", va="center", fontsize=8, color="#b35900")
        # escala de las últimas ~500 it.: el transitorio inicial no debe esconder la oscilación final
        cola = [r[j] for r in d if r[0] > it[-1] - 500]
        lo, hi = min(cola), max(cola)
        pad = max(hi - lo, abs(m) * 0.02) * 0.6
        ax.set_ylim(lo - pad, hi + pad)
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
        fiable = lambda e: e.get("estado") == "OK" and not e.get("conflicto")
        ws.append([])
        ws.append(["TOTAL", f"OK {sum(f.get('estado') == 'OK' for f in filas)} · REVISAR "
                            f"{sum(f.get('estado') == 'REVISAR' for f in filas)}"] + [""] * (COLS.index("minutos") - 2)
                  + [round(sum(f.get("minutos") or 0 for f in filas), 1), round(sum(f.get("coste_usd") or 0 for f in filas), 2)])
        ws2 = wb.create_sheet("Base_vs_variantes")
        ws2.append(["variante", "base", "nq", "Z", "dBeta2_deg", "fD2", "H_var_m", "H_base_m", "dH_pct", "eta_var",
                    "eta_base", "deta", "estado_var", "estado_base", "comparación fiable"])
        for f in filas:
            if f.get("tipo") != "variante":
                continue
            lote = leer_json(M.CASES / f["id"] / "lote.json", {}) or {}
            b = estado.get(Cfg.prefijo + (lote.get("base_gid") or ""), {})
            if finito(f.get("H_m")) and finito(b.get("H_m")):
                ws2.append([f["id"], lote.get("base_gid"), f.get("nq"), f.get("Z"), f.get("dBeta2_deg"), f.get("fD2"),
                            f["H_m"], b["H_m"], (f["H_m"] / b["H_m"] - 1) * 100, f.get("eta"), b.get("eta"),
                            (f.get("eta") or 0) - (b.get("eta") or 0), f.get("estado"), b.get("estado"),
                            "sí" if fiable(f) and fiable(b) else "no: " + ("base " if not fiable(b) else "") +
                            ("variante" if not fiable(f) else "")])
        ws3 = wb.create_sheet("Chequeos")
        ws3.append(["id", "chequeo", "valor", "limite", "ok", "grave"])
        for f in filas:
            for c in (leer_json(M.CASES / f["id"] / "chequeos.json", {}) or {}).get("chequeos", []):
                ws3.append([f["id"], c["chequeo"], _celda(c["valor"]) if not isinstance(c["valor"], (dict, list)) else str(c["valor"]),
                            c["limite"], c["ok"], c["grave"]])
        from openpyxl.styles import Font, PatternFill
        fmt = {"H_m": "0.0", "H_rel": "0.00", "H_ref_m": "0.0", "H_rel_curva": "0.00", "M_Nm": "0.0", "eta": "0.000",
               "deriva_H_pct_100it": "0.00", "oscilacion_H_pct": "0.00", "celdas": "#,##0", "base_mm": "0.0",
               "D2_esperado_mm": "0.0", "D2_medido_mm": "0.0", "minutos": "0.0", "coste_usd": "0.00", "fD2": "0.000",
               "H_var_m": "0.0", "H_base_m": "0.0", "dH_pct": "0.0", "eta_var": "0.000", "eta_base": "0.000", "deta": "+0.000;-0.000"}
        anchos = {"motivo": 60, "alertas": 40, "graves": 40, "conflicto": 40, "id": 16, "variante": 16, "chequeo": 40, "limite": 28}
        for w in (ws, ws2, ws3):
            w.freeze_panes = "B2"
            w.auto_filter.ref = f"A1:{get_column_letter(w.max_column)}{1 + len(filas) if w is ws else w.max_row}"
            hdr = [c.value for c in w[1]]
            for i, h in enumerate(hdr, start=1):
                w.cell(1, i).font = Font(bold=True)
                w.cell(1, i).fill = PatternFill("solid", fgColor="DDE6F0")
                w.column_dimensions[get_column_letter(i)].width = anchos.get(h, 12)
                if h in fmt:
                    for row in w.iter_rows(min_row=2, min_col=i, max_col=i):
                        row[0].number_format = fmt[h]
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

def archivar_intento(caso: Path, gid: str, n: int, tipo_siguiente: str) -> None:
    """Antes de un intento nuevo, lo que dejó el anterior se aparta a cases/<ID>/_intento<n>/: si el nuevo falla, sus
    chequeos no pueden leer los resultados viejos como propios. En «rehacer» también se aparta el .sim (el ejecutor
    empieza de cero) y las curvas; en «extender» el .sim y las curvas siguen (se continúa desde ahí)."""
    dst = caso / f"_intento{n}"
    dst.mkdir(exist_ok=True)
    for f in ("resultado_solver.json", "ejecucion.json", "veredicto.json", "chequeos.json", "RESUMEN.md"):
        if (caso / f).is_file():
            shutil.move(str(caso / f), dst / f)
    if tipo_siguiente == "rehacer":
        for sub in ("reports", "images"):
            if (caso / sub).is_dir():
                shutil.move(str(caso / sub), dst / sub)
                (caso / sub).mkdir()
        sim = M.SIMS / f"{gid}.sim"
        if sim.is_file() and not Cfg.seco:
            (M.SIMS / "_previos").mkdir(exist_ok=True)
            shutil.move(str(sim), M.SIMS / "_previos" / f"{gid}_intento{n}_{datetime.now():%Y%m%d_%H%M%S}.sim")


def reanudable(gid: str, previo: dict) -> list | None:
    """Qué intentos quedan de un caso que no terminó, sin volver a gastar solver en lo ya hecho:
    - «en curso» o ERROR con la ejecución del intento terminada (corte, reinicio, fallo al entregar): ese intento desde
      los chequeos;
    - PENDIENTE (PARAR llegó cuando tocaba un segundo intento): ese segundo intento.
    Devuelve [(intento, tipo, instrucciones, max_it, ya_ejecutado)] o None."""
    caso = M.CASES / gid
    lote = leer_json(caso / "lote.json")
    if not lote or previo.get("estado") not in ("en curso", "ERROR", "PENDIENTE"):
        return None
    if previo.get("estado") == "PENDIENTE" and lote.get("pendiente"):
        p = lote["pendiente"]
        return [(p["intento"], p["tipo"], p["instrucciones"], p.get("max_it"), False)]
    eje = leer_json(caso / "ejecucion.json", {}) or {}
    res = caso / "resultado_solver.json"
    if eje.get("estado") in ("COMPLETO", "REVISAR") and res.is_file() and res.stat().st_mtime >= (caso / "lote.json").stat().st_mtime:
        return [(lote["intento"], lote.get("tipo_intento", "completo"), lote.get("instrucciones_reintento", ""),
                 lote.get("iteraciones"), True)]
    return None


def parar_pedido() -> bool:
    return Cfg.parar.is_file()


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
        intentos = [(lj["intento"] + 1, "extender", f"Seguir iterando hasta {extender_hasta} sin remallar.", extender_hasta, False)]
    elif retomar:
        evento("aviso", gid, f"retomo el intento {retomar[0][0]} ({retomar[0][1]})"
                             + (": la ejecución ya había terminado" if retomar[0][4] else ""))
        intentos = retomar
    else:
        # intento limpio: lo de un intento anterior se aparta (no se borra)
        if not Cfg.seco and (M.SIMS / f"{gid}.sim").is_file():
            ap = M.SIMS / "_previos"
            ap.mkdir(exist_ok=True)
            shutil.move(str(M.SIMS / f"{gid}.sim"), ap / f"{gid}_{datetime.now():%Y%m%d_%H%M%S}.sim")
        if caso.is_dir():
            (M.CASES / "_previos").mkdir(exist_ok=True)
            shutil.move(str(caso), M.CASES / "_previos" / f"{gid}_{datetime.now():%Y%m%d_%H%M%S}")
        intentos = [(1, "completo", "", None, False)]
    ver, chq, lote = {}, {}, {}
    while intentos:
        intento, tipo, instr, max_it, ya = intentos.pop(0)
        if ya:
            lote = leer_json(caso / "lote.json")
        else:
            if intento > 1 and caso.is_dir():
                archivar_intento(caso, gid, intento - 1, tipo)
            lote = preparar(g, todas, P, intento, tipo, instr, max_it)
            e["intentos"] = intento
            escribir_json(Cfg.estado, estado)
            evento("inicio", gid, f"intento {intento} ({tipo}): nq {lote['nq']} {lote['tipo']}, Q {lote['Q_m3h']} m³/h, "
                                  f"H diseño {lote['H_diseno_m']} m, base {lote['base_mm']} mm, {lote['iteraciones']} it.")
            t_int = time.time()
            r = ejecutar(g, lote)
            coste += r.get("coste_usd") or 0
            asegurar_solver_apagado(gid)
            res = caso / "resultado_solver.json"
            fresco = res.is_file() and res.stat().st_mtime >= t_int - 1
            if not fresco and es_infra(r):
                raise ErrorInfra(f"el ejecutor no dejó resultado (rc {r.get('rc')}, {r.get('subtipo')})")
            if not fresco:
                evento("aviso", gid, f"el ejecutor terminó sin resultado ({r.get('subtipo')}"
                                     f"{', cortado por tiempo' if r.get('cortado') else ''}): lo decide la revisión")
        e["intentos"] = intento
        chq = chequear(g, lote, P, estado)
        # extender: hasta iteraciones_extension, y al menos 500 más de las que ya tiene (nq bajas empiezan en 1500)
        hasta_ext = max(P["iteraciones_extension"], lote["iteraciones"] + 500)
        puede_extender = intento == 1
        siguiente = None
        if chq["extender_util"] and intento == 1 and puede_extender:
            # H (o η) aún deriva y todo lo demás está bien: seguir iterando es lo que pediría el revisor; no se le gasta
            ins = (f"H sigue moviéndose (deriva {chq['deriva_H_pct_100it']:.2f} %/100 it., oscilación "
                   f"{chq['oscilacion_H_pct']:.2f} %): seguir de {lote['iteraciones']} a {hasta_ext} it. sin remallar.")
            siguiente = (2, "extender", ins, hasta_ext, False)
        else:
            rv = revisar(g, lote)
            coste += rv.get("coste_usd") or 0
            v = caso / "veredicto.json"
            ver = (leer_json(v, {}) if v.is_file() and v.stat().st_mtime >= chq_mtime(caso) else {}) \
                or veredicto_denegado(caso / "logs" / f"revisor_{intento}.jsonl")
            if ver.get("estado") not in ("OK", "REINTENTAR", "REVISAR"):  # sin revisor: los chequeos deciden
                ver = {"estado": "OK" if not chq["graves_fallidos"] else "REVISAR",
                       "motivo": "sin veredicto del revisor; decidido por los chequeos: " + (", ".join(chq["graves_fallidos"]) or "todo bien")}
            ver.setdefault("alertas", chq["avisos"])
            if ver["estado"] == "REINTENTAR" and intento == 1:
                tipo2 = "extender" if ver.get("reintento") == "extender" and puede_extender else "rehacer"
                siguiente = (2, tipo2, ver.get("instrucciones_reintento") or ver.get("motivo", ""),
                             hasta_ext if tipo2 == "extender" else None, False)
            elif ver["estado"] == "REINTENTAR":
                ver["estado"] = "REVISAR"
            escribir_json(v, ver)
        if siguiente:
            if parar_pedido():
                # PARAR: el segundo intento queda apuntado y se hará al relanzar (no se cierra el caso a medias)
                lote["pendiente"] = dict(zip(("intento", "tipo", "instrucciones", "max_it"), siguiente[:4]))
                escribir_json(caso / "lote.json", lote)
                e.update(estado="PENDIENTE", motivo=f"PARAR antes del intento {siguiente[0]} ({siguiente[1]})", fin=ahora())
                escribir_json(Cfg.estado, estado)
                tabla(estado)
                evento("aviso", gid, f"queda pendiente el intento {siguiente[0]} ({siguiente[1]}) por PARAR")
                return
            evento("reintento", gid, f"{siguiente[1]}: {siguiente[2][:280]}")
            intentos.append(siguiente)
    destino = entregar(g, lote, P)
    curva_convergencia(caso, P["ventana_promedio"])
    if (caso / "images" / "convergencia.png").is_file():
        shutil.copy2(caso / "images" / "convergencia.png", destino / "images" / "convergencia.png")
    cambios = aprender(g, lote, ver, P)
    e.update({k: lote.get(k) for k in ("tipo", "nq", "Z", "dBeta2_deg", "fD2", "base_mm", "D2_esperado_mm")})
    e.update({k: chq.get(k) for k in ("iteracion", "H_m", "H_rel", "H_ref_m", "H_rel_curva", "M_Nm", "eta",
                                      "deriva_H_pct_100it", "oscilacion_H_pct", "celdas", "D2_medido_mm")})
    e.update(estado=ver["estado"], motivo=ver.get("motivo", ""), alertas=ver.get("alertas", []), graves=chq["graves_fallidos"],
             conflicto=conflicto(ver["estado"], chq["graves_fallidos"], chq.get("extender_util")),
             minutos=round((time.time() - t0) / 60, 1), coste_usd=round(coste, 2), fin=ahora(), destino=str(destino))
    escribir_json(Cfg.estado, estado)
    tabla(estado)
    fmt = lambda x, n=1: "—" if not finito(x) else f"{x:.{n}f}"
    evento("fin", gid, f"{ver['estado']}: H {fmt(chq['H_m'])} m ({fmt((chq['H_rel'] or 0) * 100, 0)} % del diseño), "
                       f"η {fmt(chq['eta'], 3)}, {chq['celdas']} celdas, {e['minutos']} min. {ver.get('motivo', '')[:200]}",
           estado=ver["estado"], cambios=cambios)


def chq_mtime(caso: Path) -> float:
    f = caso / "chequeos.json"
    return f.stat().st_mtime - 1 if f.is_file() else 0.0


def esperar(segundos: float) -> None:
    """Espera atenta a PARAR (para no tener el lote dormido si alguien quiere pararlo)."""
    fin = time.time() + segundos
    while time.time() < fin and not parar_pedido():
        time.sleep(min(30.0, max(0.0, fin - time.time())))


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
    if any(a in argv for a in ("--preparar", "--consolidar", "--limpiar-backups")) and (l := lote_vivo()):
        print(f"Hay un lote corriendo (PID {l['pid']}): espera a que termine (o crea lote/PARAR) antes de esto.")
        return 2
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
        # .sim~ de casos entregados; con --incluir-sims también sims/<ID>.sim cuando la copia entregada es idéntica en
        # tamaño (deja de poderse --extender sin volver a copiarla desde CFD\)
        libres = 0
        for k, v in estado.items():
            if v.get("estado") not in ESTADOS_FINALES:
                continue
            borrar = list(M.SIMS.glob(f"{k}.sim~*"))
            lote = leer_json(M.CASES / k / "lote.json", {}) or {}
            sim, dsim = M.SIMS / f"{k}.sim", Path(lote.get("sim_destino", "")) if lote.get("sim_destino") else None
            if "--incluir-sims" in argv and sim.is_file() and dsim and dsim.is_file() and dsim.stat().st_size == sim.stat().st_size:
                borrar.append(sim)
            for b in borrar:
                try:
                    tam = b.stat().st_size
                    b.unlink()
                    libres += tam
                except OSError as ex:
                    print(f"no pude borrar {b.name}: {ex}")
        print(f"liberados {libres / 1e9:.1f} GB en sims/")
        return 0
    if not tomar_lock():
        return 2
    hechos: list[str] = []
    try:
        evento("arranque", "", f"PID {os.getpid()}")
        asegurar_solver_apagado("")       # un solver que dejó una corrida anterior caída no debe bloquear la licencia
        extender = arg("--extender")
        hasta = None
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
        infra, i = 0, 0
        while i < len(cola):
            g = cola[i]
            if parar_pedido():
                evento("lote_parado", "", "encontré lote/PARAR")
                break
            try:
                una(g, todas, estado, hasta)
                hechos.append(g["clave"])
                infra, i = 0, i + 1
            except ErrorInfra as ex:
                infra += 1
                asegurar_solver_apagado(g["id"])
                estado.setdefault(g["id"], {}).update(estado="ERROR_INFRA", motivo=str(ex)[:300], fin=ahora())
                escribir_json(Cfg.estado, estado)
                tabla(estado)
                if infra > MAX_INFRA_SEGUIDOS:
                    evento("lote_parado", "", f"{infra} fallos de infraestructura seguidos (¿cuota, red o sesión de claude?): "
                                              "paro; relanzar retoma desde aquí")
                    break
                evento("error", g["id"], f"infraestructura ({infra}/{MAX_INFRA_SEGUIDOS + 1}): {str(ex)[:220]}. "
                                         f"Espero {Cfg.espera_infra // 60} min y lo reintento")
                esperar(Cfg.espera_infra)    # cuota o red suelen volver solas; no se avanza para no quemar la cola
            except Exception as ex:  # noqa: BLE001  una geometría rota no para el lote
                asegurar_solver_apagado(g["id"])
                estado.setdefault(g["id"], {}).update(estado="ERROR", motivo=str(ex)[:300], fin=ahora())
                try:
                    escribir_json(Cfg.estado, estado)
                except OSError:
                    pass
                tabla(estado)
                evento("error", g["id"], str(ex)[:300])
                infra, i = 0, i + 1
        Cfg.parar.unlink(missing_ok=True)   # PARAR ya surtió efecto (o llegó en la última geometría)
        resumen = [v.get("estado") for v in estado.values()]
        consolidado(estado)
        evento("lote_fin", "", f"OK {resumen.count('OK')}, REVISAR {resumen.count('REVISAR')}, "
                               f"ERROR {resumen.count('ERROR') + resumen.count('ERROR_INFRA')}, PENDIENTE {resumen.count('PENDIENTE')}")
        return 0
    except KeyboardInterrupt:
        evento("lote_abortado", "", "interrumpido (Ctrl+C o cierre)")
        asegurar_solver_apagado("")
        return 130
    finally:
        commit_aprendizaje(hechos)
        soltar_lock()


def seco() -> int:
    """Prueba en seco de punta a punta con ejecutor y revisor falsos (lote/falso_claude.py), todo en un temporal, sin git
    y con un prefijo propio del proceso (dos pruebas a la vez no se pisan). Cubre:
    1. G002 (nq 15, empieza en 1500) que deriva → extensión automática → OK; G033 con claude caído 2 veces → espera y
       reintento → OK; G034 con el par al revés → REINTENTAR, pero llega PARAR → PENDIENTE y el lote se para;
    2. relanzar retoma G034 en su intento 2 (con lo del intento 1 apartado) → REVISAR;
    3. G002 «en curso» con la ejecución hecha se retoma desde los chequeos, sin ejecutor;
    4. --extender G002 con claude caído: los resultados viejos no cuentan como nuevos → ERROR_INFRA y lote parado."""
    tmp = Path(tempfile.mkdtemp(prefix="lote-seco-"))
    pre = f"SECO{os.getpid()}_"
    try:
        (tmp / "geo").mkdir()
        shutil.copy2(GEO / "_estado.json", tmp / "geo" / "_estado.json")
        for d in GEO.iterdir():
            if d.is_dir() and d.name[:5] in ("G002_", "G033_", "G034_"):
                shutil.copytree(d, tmp / "geo" / d.name, ignore=shutil.ignore_patterns("CFD", "*.html", "*.pdf"))
        shutil.copy2(LOTE / "parametros.json", tmp / "parametros.json")
        n0 = len(leer_json(tmp / "parametros.json")["historial_malla"])
        ids0 = {h["caso"] for h in leer_json(tmp / "parametros.json")["historial_malla"]}
        Cfg.seco, Cfg.geo, Cfg.params, Cfg.estado, Cfg.eventos, Cfg.prefijo = True, tmp / "geo", tmp / "parametros.json", tmp / "estado.json", tmp / "eventos.log", pre
        Cfg.propuestas, Cfg.lecciones_rev, Cfg.lock, Cfg.parar, Cfg.espera_infra =             tmp / "propuestas.json", tmp / "lecciones_revisor.md", tmp / ".lock", tmp / "PARAR", 0
        os.environ.update(FALSO_DIR=str(tmp), FALSO_CAIDO="G033:2", FALSO_PARAR="G034")
        g2, g33, g34 = pre + "G002_nq15_B", pre + "G033_nq65_B", pre + "G034_nq65_V"
        est_ = lambda k, c="estado": (leer_json(Cfg.estado, {}) or {}).get(k, {}).get(c)
        fallos = []
        rc = main(["--solo", "G002,G033,G034"])
        P = leer_json(Cfg.params)
        for k, v in ((g2, "OK"), (g33, "OK"), (g34, "PENDIENTE")):
            if est_(k) != v:
                fallos.append(f"1: {k} {est_(k)} (esperaba {v})")
        if est_(g2, "intentos") != 2 or est_(g2, "iteracion") != max(P["iteraciones_extension"], 1500 + 500):
            fallos.append(f"1: G002 debía extenderse sola (intentos {est_(g2, 'intentos')}, it. {est_(g2, 'iteracion')})")
        if not (tmp / "geo" / "_lote_simulacion.csv").is_file() or not (tmp / "geo" / "_indice_CFD.html").is_file():
            fallos.append("1: faltan _lote_simulacion.csv o _indice_CFD.html")
        if not any((tmp / "geo").glob("G002_*/CFD/*.sim")) or not any((tmp / "geo").glob("G002_*/CFD/images/*.png")):
            fallos.append("1: la entrega de G002 no tiene .sim o imágenes")
        if len(P["historial_malla"]) < n0 or not {"G002_nq15_B", "G033_nq65_B"} <= {h["caso"] for h in P["historial_malla"]}:
            fallos.append("1: historial de malla")
        if P["min_rotor_pct"] != 40.0 or P["iteraciones"] != 1000:
            fallos.append("1: propuestas: límite o prohibición no aplicados")
        if Cfg.lock.is_file() or Cfg.parar.is_file():
            fallos.append("1: quedó el .lock o PARAR")
        os.environ.pop("FALSO_PARAR")
        main(["--solo", "G034"])
        if est_(g34) != "REVISAR" or est_(g34, "intentos") != 2 or not (M.CASES / g34 / "_intento1" / "veredicto.json").is_file():
            fallos.append(f"2: G034 no se retomó en su intento 2 ({est_(g34)}, {est_(g34, 'intentos')})")
        est = leer_json(Cfg.estado, {})
        est[g2]["estado"] = "en curso"
        escribir_json(Cfg.estado, est)
        os.environ["FALSO_CAIDO"] = "todos"
        (M.CASES / g2 / "lote.json").touch()
        os.utime(M.CASES / g2 / "resultado_solver.json")
        main(["--solo", "G002"])
        if est_(g2) != "OK":
            fallos.append(f"3: no se retomó G002 desde los chequeos ({est_(g2)})")
        main(["--extender", "G002", "--hasta", "2500"])
        if est_(g2) != "ERROR_INFRA":
            fallos.append(f"4: --extender con claude caído debía dar ERROR_INFRA y dio {est_(g2)}")
        if "lote_parado" not in (tmp / "eventos.log").read_text(encoding="utf-8"):
            fallos.append("4: tres fallos de infraestructura seguidos debían parar el lote")
        ok = not fallos and rc == 0
        print("SECO:", "todo en verde" if ok else "FALLA " + "; ".join(fallos),
              json.dumps({k.replace(pre, ""): v.get("estado") for k, v in leer_json(Cfg.estado, {}).items()}))
        print((tmp / "eventos.log").read_text(encoding="utf-8"))
        return 0 if ok else 1
    finally:
        for k in ("FALSO_CAIDO", "FALSO_PARAR", "FALSO_DIR"):
            os.environ.pop(k, None)
        for d in M.CASES.glob(pre + "*"):
            shutil.rmtree(d, ignore_errors=True)
        for d in (M.CASES / "_previos").glob(pre + "*") if (M.CASES / "_previos").is_dir() else []:
            shutil.rmtree(d, ignore_errors=True)
        for f in M.SIMS.glob(pre + "*"):
            f.unlink(missing_ok=True)
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    for s in (sys.stdout, sys.stderr):  # consola o log de Windows en cp1252: η y ³ no deben tumbar el lote
        s.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main(sys.argv[1:]))
