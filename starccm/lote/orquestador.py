"""Orquestador del lote CFD: geometrías de CFturbo (Desktop/Geometrias_Prueba/G0xx_*) → una simulación de bomba cada una.

Por geometría: prepara cases/<ID>/ (CAD, lote.json, macros con los valores puestos y compiladas con javac), lanza el
EJECUTOR (claude -p, Sonnet, sigue lote/receta.md con las tools del MCP), calcula los chequeos, lanza el REVISOR
(claude -p, Opus, lote/revision.md), reintenta una vez si el revisor lo pide, copia todo a <geometría>/CFD/ y aprende:
historial de celdas por base y propuestas de robustez del revisor (con límites, commit en git). Un solo solver a la vez.

Uso (desde starccm/):
  .venv\\Scripts\\python lote\\orquestador.py                    todas las pendientes, en orden
  .venv\\Scripts\\python lote\\orquestador.py --solo G002,G047   solo esas (piloto)
  .venv\\Scripts\\python lote\\orquestador.py --preparar G002    prepara y compila las macros; sin licencia ni modelos
  .venv\\Scripts\\python lote\\orquestador.py --seco             prueba en seco (ejecutor y revisor falsos, temporales)
  .venv\\Scripts\\python lote\\orquestador.py --estado           tabla de estado
Parar con calma: crear lote/PARAR (termina la geometría en curso y sale).
"""
from __future__ import annotations

import csv
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
FUNCS = "Pressure,TotalPressure,Velocity,WallYplus"
LIMITES = {"D2_sobre_base": (35.0, 90.0), "min_rotor_pct": (15.0, 40.0), "alabes_pct": (30.0, 100.0),
           "objetivo_celdas": (900000, 1850000), "urf_v": (0.3, 0.7), "urf_p": (0.1, 0.3)}


class Cfg:
    """Rutas que cambian en la prueba en seco (todo a un temporal, nada real se toca)."""
    seco = False
    geo = GEO
    params = LOTE / "parametros.json"
    estado = LOTE / "estado.json"
    eventos = LOTE / "eventos.log"
    prefijo = ""


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
    fd2 = re.search(r"fD2-([\d.]+)", d.name)
    rep = g["estado_cft"].get("report", {}) if g["estado_cft"] else {}
    u2 = rep.get("u2")
    rpm = rps * 60.0
    D2 = u2 * 60.0 / (math.pi * abs(rpm)) if u2 else None
    beta2 = (rep.get("beta2_deg") or [None])[0]
    return {
        "id": g["id"], "carpeta": str(d), "nombre": ccm.stem, "nq": nq,
        "tipo": "variante" if "variante" in d.name else "base",
        "fD2": float(fd2.group(1)) if fd2 else None,
        "Q_m3h": float(m.group(1)), "H_diseno_m": float(m.group(2)), "rpm": rpm,
        "masa_kg_s": num(root.find("ProjectData"), "MassFlow"),
        "rho": num(root.find("FluidData"), "Density"), "mu": num(root.find("FluidData"), "DynamicViscosity"),
        "eje": vec(imp.find("RotationAxis")), "u2_cfturbo": u2,
        "D2_cfturbo_mm": round(D2 * 1000, 2) if D2 else None, "beta2_deg": beta2,
        "cad": {k: str(v) for k, v in co.items()},
    }


def d2_esperado(g: dict, dat: dict, todas: list[dict]) -> float | None:
    """D2 esperado de la variante = D2 de su base (misma nq) × fD2 del nombre. Si CFturbo no aplicó fD2, el radio medido
    lo delata (en _estado.json las variantes de nq 65 y nq 80 traen la misma u2 que su base)."""
    if dat["tipo"] == "base" or not dat["fD2"]:
        return dat["D2_cfturbo_mm"]
    base = next((b for b in todas if f"_nq{dat['nq']}_base_" in b["carpeta"].name), None)
    if not base:
        return None
    u2b = (base["estado_cft"].get("report") or {}).get("u2")
    return round(u2b * 60.0 / (math.pi * abs(dat["rpm"])) * 1000 * dat["fD2"], 2) if u2b else None


def base_mm(P: dict, dat: dict) -> float:
    """Tamaño base desde el historial: el caso de nq más cercana da cuántas celdas salen por (D2/base)³; se ajusta
    al objetivo (las extensiones suman ~6 %)."""
    D2 = dat["D2_cfturbo_mm"] or 250.0
    h = sorted(P["historial_malla"], key=lambda e: (abs(e["nq"] - dat["nq"]), -len(e.get("caso", ""))))
    ratio = P["D2_sobre_base"]
    if h:
        e = h[0]
        ratio = (e["D2_mm"] / e["base_mm"]) * ((P["objetivo_celdas"] / 1.06) / e["celdas_sin_ext"]) ** (1 / 3)
    return round(D2 / ratio, 1)


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


def preparar(g: dict, todas: list[dict], P: dict, intento: int = 1, instrucciones: str = "") -> dict:
    dat = datos(g)
    caso = M.CASES / g["id"]
    for sub in ("cad", "macros", "reports", "images", "surfaces/_raw", "logs"):
        (caso / sub).mkdir(parents=True, exist_ok=True)
    cad = {}
    for k, f in dat["cad"].items():
        dst = caso / "cad" / Path(f).name
        if not dst.is_file():
            shutil.copy2(f, dst)
        cad[k] = jp(dst)
    ccm = next(Path(dat["carpeta"]).glob("*.cfturbo-ccm"))
    shutil.copy2(ccm, caso / "cad" / ccm.name)
    lj = leer_json(caso / "lote.json", {}) or {}
    base = lj.get("base_mm") or base_mm(P, dat)
    destino = Path(dat["carpeta"]) / "CFD" / f"{dat['nombre']}.sim"
    lote = {**dat, "D2_esperado_mm": d2_esperado(g, dat, todas), "base_mm": base, "intento": intento,
            "instrucciones_reintento": instrucciones, "receta_version": P["receta_version"],
            "max_celdas": P["max_celdas"], "objetivo_celdas": P["objetivo_celdas"], "iteraciones": P["iteraciones"],
            "parametros": {k: P[k] for k in ("min_rotor_pct", "alabes_pct", "prismas", "ext_entrada_D", "ext_salida_D", "urf_v", "urf_p")},
            "sim_destino": str(destino), "preparado": ahora()}
    escribir_json(caso / "lote.json", lote)
    escribir_json(caso / "caso.json", {"sim_destino": str(destino), "titulo": f"{g['clave']} (lote)"})
    ax = ", ".join(repr(float(x)) for x in dat["eje"])
    v = {**cad, "BASE_MM": base, "MIN_ROTOR_PCT": P["min_rotor_pct"], "ALABES_PCT": P["alabes_pct"], "PRISMAS": P["prismas"],
         "L_IN_D": P["ext_entrada_D"], "L_OUT_D": P["ext_salida_D"], "RHO": dat["rho"], "MU": dat["mu"], "RPM": dat["rpm"],
         "MASA": dat["masa_kg_s"], "URF_V": P["urf_v"], "URF_P": P["urf_p"], "AX": ax, "BLOQUE": P["bloque"],
         "MAX_IT": P["iteraciones"], "CONV_CSV": jp(caso / "reports" / "convergencia.csv"),
         "RES_CSV": jp(caso / "reports" / "residuales.csv"), "OUT_JSON": jp(caso / "resultado_solver.json"),
         "IMG_DIR": jp(caso / "images")}
    mac = caso / "macros"
    if intento == 1:  # en un reintento se respetan los cambios que el ejecutor hizo a sus macros (base remallado…)
        for t in sorted((LOTE / "macros").glob("*.java")):
            (mac / t.name).write_text(_render_tpl(t, v), encoding="utf-8")
        cab = "// Generada por lote/orquestador.py desde recipes/{}\n"
        (mac / "06-euler.java").write_text(_render_receta("reportes-euler-triangulos.java", {
            "MODO": "bomba", "RHO": dat["rho"], "H_REPORT": "H", "BETA2": dat["beta2_deg"] if dat["beta2_deg"] else "",
            "ENTRADA_ROTOR": "", "SALIDA_ROTOR": ""}, cab.format("reportes-euler-triangulos.java")), encoding="utf-8")
        (mac / "08-promedio.java").write_text(_render_receta("promediar-monitores.java", {
            "MONS": "H Monitor,M Monitor,eta Monitor,P_eje Monitor,Q_in Monitor,Q_out Monitor,pt_in Monitor,pt_out Monitor",
            "DESDE": P["iteraciones"] - 200, "CSV": jp(caso / "reports" / "monitores_historial.csv")},
            cab.format("promediar-monitores.java")), encoding="utf-8")
        (mac / "10-superficies.java").write_text(_render_receta("exportar-superficies-ensight.java", {
            "PATTERN": ".", "FUNCS": FUNCS, "OUT": jp(caso / "surfaces" / "_raw" / "superficies" / "superficies.case"),
            "PLANOS": "auto"}, cab.format("exportar-superficies-ensight.java")), encoding="utf-8")
        (caso / "surfaces" / "_raw" / "superficies").mkdir(parents=True, exist_ok=True)
        for k, r in (("11a-escenas-bomba", "bomba-escenas"), ("11b-escenas-fluido", "escenas-fluido"),
                     ("11c-escena-malla", "escena-malla-rotor"), ("11d-escena-plano-vectores", "escena-plano-vectores")):
            (mac / f"{k}.java").write_text(_render_receta(f"{r}.java", {}, cab.format(f"{r}.java")), encoding="utf-8")
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
    return e


def claude(prompt: str, modelo: str, permitidas: str, log: Path, timeout: int, max_turnos: int) -> dict:
    """claude -p con salida stream-json a `log`. Devuelve rc, segundos, coste y si se cortó por tiempo."""
    cmd = [CLAUDE, "-p", prompt, "--model", modelo, "--output-format", "stream-json", "--verbose",
           "--mcp-config", str(REPO / ".mcp.json"), "--strict-mcp-config", "--allowedTools", permitidas,
           "--disallowedTools", "Bash,PowerShell,NotebookEdit,WebFetch,WebSearch,Read(**/.env*),Read(**/.starccm-agent.env)",
           "--max-turns", str(max_turnos)]
    if Cfg.seco:
        cmd = [sys.executable, str(LOTE / "falso_claude.py"), "-p", prompt, "--model", modelo]
    t0 = time.time()
    res = {"rc": None, "segundos": 0, "coste_usd": None, "cortado": False}
    with open(log, "w", encoding="utf-8") as out:
        p = subprocess.Popen(cmd, cwd=ST, env=env_cli(), stdin=subprocess.DEVNULL, stdout=out, stderr=subprocess.STDOUT,
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        try:
            res["rc"] = p.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"], capture_output=True)
            res["cortado"] = True
    res["segundos"] = round(time.time() - t0)
    for ln in log.read_text(encoding="utf-8", errors="replace").splitlines()[::-1]:
        if '"type":"result"' in ln.replace(" ", ""):
            try:
                o = json.loads(ln)
                res["coste_usd"] = o.get("total_cost_usd")
                res["turnos"] = o.get("num_turns")
                res["subtipo"] = o.get("subtype")
            except ValueError:
                pass
            break
    return res


def ejecutar(g: dict, lote: dict) -> dict:
    caso = M.CASES / g["id"]
    n = lote["intento"]
    extra = f"\nINTENTO {n}. Instrucciones del revisor: {lote['instrucciones_reintento']}\n" \
            "La simulación de este caso ya existe en sims/: server_start(name=...) la abre; sigue desde donde está." if n > 1 else ""
    prompt = (f"Caso {g['id']}: cases/{g['id']}/. Lee lote/receta.md y lote/lecciones.md y sigue la receta de principio a fin "
              f"con los datos de cases/{g['id']}/lote.json. Trabaja solo, sin preguntar.{extra}")
    permitidas = "mcp__starccm__*,Read,Glob,Grep,Write(cases/**),Edit(cases/**)"
    return claude(prompt, MODELO_EJECUTOR, permitidas, caso / "logs" / f"ejecutor_{n}.jsonl", T_EJECUTOR, 250)


def revisar(g: dict, lote: dict) -> dict:
    caso = M.CASES / g["id"]
    prompt = (f"Revisa el caso {g['id']} (cases/{g['id']}/) siguiendo lote/revision.md. Intento {lote['intento']} de 2. "
              f"Escribe cases/{g['id']}/veredicto.json.")
    # Write se rige por las reglas Edit(...): sin Edit(cases/**) el revisor no puede crear veredicto.json en -p
    permitidas = ("Read,Glob,Grep,Edit(cases/**),Write(cases/**),Edit(lote/lecciones.md),"
                  "Edit(lote/propuestas.json),Write(lote/propuestas.json)")
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
    if Cfg.seco:
        return
    st = M._state()
    if st.get("pid") and M.alive(st):
        evento("aviso", gid, "el ejecutor dejó el solver encendido: lo guardo y lo apago")
        try:
            M.server_stop(save=True)
        except Exception as e:  # noqa: BLE001
            evento("error", gid, f"no pude apagar el solver: {e}")


# ---------------------------------------------------------------- chequeos

def historial(caso: Path) -> dict:
    """Media, mínimo y máximo de las últimas 200 iteraciones desde el CSV de monitores (08-promedio)."""
    f = caso / "reports" / "monitores_historial.csv"
    if not f.is_file():
        return {}
    filas = list(csv.reader(f.open(encoding="utf-8-sig", errors="replace")))
    if len(filas) < 3:
        return {}
    hdr = [h.strip().strip('"') for h in filas[0]]
    datos_ = []
    for r in filas[1:]:
        try:
            datos_.append([float(x) for x in r])
        except ValueError:
            continue
    it_max = max(r[0] for r in datos_)
    sel = [r for r in datos_ if r[0] > it_max - 200]
    out = {}
    for j, h in enumerate(hdr[1:], start=1):
        nombre = h.split(":")[0].replace(" Monitor", "").strip()
        vals = [r[j] for r in sel if j < len(r)]
        if vals:
            out[nombre] = {"media": sum(vals) / len(vals), "min": min(vals), "max": max(vals), "n": len(vals)}
    return out


def chequear(g: dict, lote: dict, P: dict) -> dict:
    caso = M.CASES / g["id"]
    res = leer_json(caso / "resultado_solver.json", {}) or {}
    eje = leer_json(caso / "ejecucion.json", {}) or {}
    h = historial(caso)
    C = P["chequeos"]
    rep = res.get("reportes", {})
    H = (h.get("H") or {}).get("media", rep.get("H"))
    Mm = (h.get("M") or {}).get("media", rep.get("M"))
    eta = (h.get("eta") or {}).get("media", rep.get("eta"))
    lista = []

    def chk(nombre, valor, limite, ok, grave=True):
        lista.append({"chequeo": nombre, "valor": valor, "limite": limite, "ok": bool(ok), "grave": grave})

    it = res.get("iteracion", 0)
    chk("iteraciones", it, f">= {P['iteraciones']}", it >= P["iteraciones"])
    cel = res.get("celdas")
    chk("celdas", cel, f"<= {P['max_celdas']}", cel is not None and cel <= P["max_celdas"])
    bal = res.get("balance_masa_pct")
    chk("balance de masa %", bal, f"<= {C['balance_max_pct']}", bal is not None and bal <= C["balance_max_pct"])
    chk("H > 0", H, "> 0", H is not None and H > 0)
    Hrel = H / lote["H_diseno_m"] if H else None
    chk("H / H diseño", Hrel, f"{C['H_rel_min']}–{C['H_rel_max']}", Hrel is not None and C["H_rel_min"] <= Hrel <= C["H_rel_max"])
    chk("eta", eta, f"{C['eta_min']}–{C['eta_max']}", eta is not None and C["eta_min"] <= eta <= C["eta_max"])
    if h.get("H"):
        osc = (h["H"]["max"] - h["H"]["min"]) / 2 / abs(h["H"]["media"]) * 100
        chk("oscilación de H % (últimas 200)", osc, f"<= {C['oscilacion_H_max_pct']}", osc <= C["oscilacion_H_max_pct"])
    else:
        chk("oscilación de H % (últimas 200)", None, "historial de monitores", False)
    r = res.get("r_salida_alabe_m")
    D2e = lote.get("D2_esperado_mm")
    if r and D2e:
        dif = (2 * r * 1000 - D2e) / D2e * 100
        chk("D2 medido vs esperado %", round(dif, 2), f"±{C['d2_tol_pct']}", abs(dif) <= C["d2_tol_pct"], grave=False)
    imgs = len(list((caso / "images").glob("*.png")))
    chk("escenas PNG", imgs, ">= 6", imgs >= 6, grave=False)
    chk("ejecutor terminó", eje.get("estado"), "COMPLETO", eje.get("estado") == "COMPLETO")
    out = {"H_m": H, "M_Nm": Mm, "eta": eta, "H_rel": Hrel, "D2_medido_mm": round(2 * r * 1000, 2) if r else None,
           "celdas": cel, "graves_fallidos": [c["chequeo"] for c in lista if c["grave"] and not c["ok"]],
           "avisos": [c["chequeo"] for c in lista if not c["grave"] and not c["ok"]], "chequeos": lista, "promedios": h}
    escribir_json(caso / "chequeos.json", out)
    return out


# ---------------------------------------------------------------- entrega y aprendizaje

def entregar(g: dict, lote: dict) -> Path:
    caso = M.CASES / g["id"]
    dst = Path(lote["carpeta"]) / "CFD"
    dst.mkdir(parents=True, exist_ok=True)
    for sub in ("images", "reports"):
        if (caso / sub).is_dir():
            shutil.copytree(caso / sub, dst / sub, dirs_exist_ok=True)
    if (caso / "surfaces" / "_raw" / "superficies").is_dir():
        shutil.copytree(caso / "surfaces" / "_raw" / "superficies", dst / "surfaces", dirs_exist_ok=True)
    for f in ("RESUMEN.md", "lote.json", "resultado_solver.json", "chequeos.json", "veredicto.json", "ejecucion.json"):
        if (caso / f).is_file():
            shutil.copy2(caso / f, dst / f)
    sim = M.SIMS / f"{g['id']}.sim"
    dsim = Path(lote["sim_destino"])
    if sim.is_file() and (not dsim.is_file() or dsim.stat().st_mtime < sim.stat().st_mtime or dsim.stat().st_size != sim.stat().st_size):
        tmp = dsim.with_name(dsim.name + ".copiando")
        shutil.copy2(sim, tmp)
        os.replace(tmp, dsim)
    return dst


def aprender(g: dict, lote: dict, chq: dict, P: dict) -> list[str]:
    """Historial de malla (celdas por base) y propuestas del revisor dentro de LIMITES. Devuelve los cambios."""
    caso = M.CASES / g["id"]
    cambios = []
    res = leer_json(caso / "resultado_solver.json", {}) or {}
    m02 = (caso / "macros" / "02-malla.java").read_text(encoding="utf-8") if (caso / "macros" / "02-malla.java").is_file() else ""
    mb = re.search(r"double BASE_MM = ([\d.]+)", m02)
    if res.get("celdas") and mb and lote.get("D2_cfturbo_mm"):
        ext = sum(v for k, v in (res.get("celdas_region") or {}).items() if k.startswith("ext_"))
        P["historial_malla"] = [e for e in P["historial_malla"] if e["caso"] != g["clave"]] + [{
            "caso": g["clave"], "nq": lote["nq"], "D2_mm": lote["D2_cfturbo_mm"], "base_mm": float(mb.group(1)),
            "celdas_sin_ext": res["celdas"] - ext, "celdas": res["celdas"]}]
        cambios.append(f"historial de malla: {g['clave']} base {mb.group(1)} mm → {res['celdas']} celdas")
    prop = leer_json(LOTE / "propuestas.json", []) or []
    aplicadas = False
    for p in prop if isinstance(prop, list) else []:
        k, v = p.get("parametro"), p.get("valor")
        if k in LIMITES and isinstance(v, (int, float)):
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
    (LOTE / "propuestas.json").unlink(missing_ok=True)
    escribir_json(Cfg.params, P)
    if cambios and not Cfg.seco:
        subprocess.run([GIT, "-C", str(REPO), "add", "starccm/lote/parametros.json", "starccm/lote/lecciones.md"], capture_output=True)
        msg = f"lote: aprendido de {g['clave']} (receta v{P['receta_version']})\n\n" + "\n".join(f"- {c}" for c in cambios)
        subprocess.run([GIT, "-C", str(REPO), "commit", "-m", msg + "\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>",
                        "--", "starccm/lote/parametros.json", "starccm/lote/lecciones.md"], capture_output=True)
    return cambios


def tabla(estado: dict) -> None:
    f = Cfg.geo / "_lote_simulacion.csv"
    cols = ["id", "estado", "intentos", "H_m", "H_rel", "M_Nm", "eta", "celdas", "D2_medido_mm", "minutos", "coste_usd", "motivo", "fin"]
    with open(f, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow(cols)
        for k in sorted(estado):
            e = estado[k]
            w.writerow([k] + [("" if e.get(c) is None else round(e[c], 3) if isinstance(e.get(c), float) else e.get(c)) for c in cols[1:]])


# ---------------------------------------------------------------- bucle

def una(g: dict, todas: list[dict], estado: dict) -> None:
    gid = g["id"]
    caso = M.CASES / gid
    P = leer_json(Cfg.params)
    t0 = time.time()
    coste = 0.0
    e = estado.setdefault(gid, {})
    e.update(estado="en curso", inicio=ahora(), intentos=0)
    escribir_json(Cfg.estado, estado)
    # intento limpio: lo de un intento anterior interrumpido se aparta (no se borra)
    if not Cfg.seco and (M.SIMS / f"{gid}.sim").is_file():
        ap = M.SIMS / "_previos"
        ap.mkdir(exist_ok=True)
        shutil.move(str(M.SIMS / f"{gid}.sim"), ap / f"{gid}_{datetime.now():%Y%m%d_%H%M%S}.sim")
    if caso.is_dir():
        (M.CASES / "_previos").mkdir(exist_ok=True)
        shutil.move(str(caso), M.CASES / "_previos" / f"{gid}_{datetime.now():%Y%m%d_%H%M%S}")
    instr, ver = "", {}
    for intento in (1, 2):
        lote = preparar(g, todas, P, intento, instr)
        e["intentos"] = intento
        evento("inicio", gid, f"intento {intento}: nq {lote['nq']} {lote['tipo']}, Q {lote['Q_m3h']} m³/h, H diseño {lote['H_diseno_m']} m, base {lote['base_mm']} mm")
        r = ejecutar(g, lote)
        coste += r.get("coste_usd") or 0
        asegurar_solver_apagado(gid)
        chq = chequear(g, lote, P)
        rv = revisar(g, lote)
        coste += rv.get("coste_usd") or 0
        ver = leer_json(caso / "veredicto.json", {}) or veredicto_denegado(caso / "logs" / f"revisor_{intento}.jsonl")
        if ver.get("estado") in ("OK", "REINTENTAR", "REVISAR"):
            escribir_json(caso / "veredicto.json", ver)
        if ver.get("estado") not in ("OK", "REINTENTAR", "REVISAR"):  # sin revisor: los chequeos deciden
            ver = {"estado": "OK" if not chq["graves_fallidos"] else "REVISAR",
                   "motivo": "sin veredicto del revisor; decidido por los chequeos: " + (", ".join(chq["graves_fallidos"]) or "todo bien")}
            escribir_json(caso / "veredicto.json", ver)
        if ver["estado"] == "REINTENTAR" and intento == 1:
            instr = ver.get("instrucciones_reintento") or ver.get("motivo", "")
            evento("reintento", gid, instr[:300])
            continue
        if ver["estado"] == "REINTENTAR":
            ver["estado"] = "REVISAR"
        break
    destino = entregar(g, lote)
    cambios = aprender(g, lote, chq, P)
    e.update(estado=ver["estado"], motivo=ver.get("motivo", ""), H_m=chq["H_m"], H_rel=chq["H_rel"], M_Nm=chq["M_Nm"],
             eta=chq["eta"], celdas=chq["celdas"], D2_medido_mm=chq["D2_medido_mm"], minutos=round((time.time() - t0) / 60, 1),
             coste_usd=round(coste, 2), fin=ahora(), destino=str(destino))
    escribir_json(Cfg.estado, estado)
    tabla(estado)
    fmt = lambda x, n=1: "—" if x is None else f"{x:.{n}f}"
    evento("fin", gid, f"{ver['estado']}: H {fmt(chq['H_m'])} m ({fmt((chq['H_rel'] or 0) * 100, 0)} % del diseño), "
                       f"η {fmt(chq['eta'], 3)}, {chq['celdas']} celdas, {e['minutos']} min. {ver.get('motivo', '')[:200]}",
           estado=ver["estado"], cambios=cambios)


def main(argv: list[str]) -> int:
    if "--seco" in argv:
        return seco()
    todas = geometrias()
    estado = leer_json(Cfg.estado, {}) or {}
    if "--estado" in argv:
        for k in sorted(estado):
            print(k, estado[k].get("estado"), estado[k].get("H_m"), estado[k].get("eta"), estado[k].get("motivo", "")[:80])
        return 0
    if "--preparar" in argv:
        ids = argv[argv.index("--preparar") + 1].split(",")
        P = leer_json(Cfg.params)
        for g in todas:
            if any(g["id"].startswith(i) for i in ids):
                lote = preparar(g, todas, P)
                print(f"{g['id']}: listo, base {lote['base_mm']} mm, D2 esperado {lote['D2_esperado_mm']} mm, "
                      f"{len(list((M.CASES / g['id'] / 'macros').glob('*.java')))} macros compiladas")
        return 0
    solo = argv[argv.index("--solo") + 1].split(",") if "--solo" in argv else None
    cola = [g for g in todas if (solo is None or any(g["clave"].startswith(s) for s in solo))
            and (solo is not None or estado.get(g["id"], {}).get("estado") not in ("OK", "REVISAR"))]
    evento("lote_inicio", "", f"{len(cola)} geometrías: {', '.join(g['clave'] for g in cola)}")
    for g in cola:
        if (LOTE / "PARAR").is_file():
            evento("lote_parado", "", "encontré lote/PARAR")
            (LOTE / "PARAR").unlink(missing_ok=True)
            break
        try:
            una(g, todas, estado)
        except Exception as ex:  # noqa: BLE001  una geometría rota no para el lote
            asegurar_solver_apagado(g["id"])
            estado.setdefault(g["id"], {}).update(estado="ERROR", motivo=str(ex)[:300], fin=ahora())
            escribir_json(Cfg.estado, estado)
            tabla(estado)
            evento("error", g["id"], str(ex)[:300])
    resumen = {k: estado[k].get("estado") for k in estado}
    evento("lote_fin", "", f"OK {sum(v == 'OK' for v in resumen.values())}, REVISAR {sum(v == 'REVISAR' for v in resumen.values())}, "
                           f"ERROR {sum(v == 'ERROR' for v in resumen.values())}")
    return 0


def seco() -> int:
    """Prueba en seco de punta a punta: 2 geometrías copiadas a un temporal, ejecutor y revisor falsos
    (lote/falso_claude.py), parámetros y eventos en el temporal, sin git. Comprueba también que las macros compilan."""
    tmp = Path(tempfile.mkdtemp(prefix="lote-seco-"))
    try:
        (tmp / "geo").mkdir()
        shutil.copy2(GEO / "_estado.json", tmp / "geo" / "_estado.json")
        for d in GEO.iterdir():
            if d.is_dir() and (d.name.startswith("G002_") or d.name.startswith("G034_") or d.name.startswith("G033_")):
                shutil.copytree(d, tmp / "geo" / d.name, ignore=shutil.ignore_patterns("CFD", "*.html", "*.pdf"))
        shutil.copy2(LOTE / "parametros.json", tmp / "parametros.json")
        ids0 = {h["caso"] for h in leer_json(tmp / "parametros.json")["historial_malla"]}
        Cfg.seco, Cfg.geo, Cfg.params, Cfg.estado, Cfg.eventos, Cfg.prefijo = True, tmp / "geo", tmp / "parametros.json", tmp / "estado.json", tmp / "eventos.log", "SECO_"
        rc = main(["--solo", "G002,G034"])
        est = leer_json(Cfg.estado, {})
        ok = (rc == 0 and est.get("SECO_G002_nq15_B", {}).get("estado") == "OK" and est.get("SECO_G034_nq65_V", {}).get("estado") == "REVISAR"
              and (tmp / "geo" / "_lote_simulacion.csv").is_file()
              and any((tmp / "geo").glob("G002_*/CFD/*.sim")) and any((tmp / "geo").glob("G002_*/CFD/images/*.png"))
              and len(leer_json(Cfg.params)["historial_malla"]) == len(ids0 | {"G002_nq15_B", "G034_nq65_V"})  # las de antes + las dos
              and leer_json(Cfg.params)["min_rotor_pct"] == 40.0               # propuesta recortada a su límite
              and leer_json(Cfg.params).get("iteraciones") == 1000)            # propuesta prohibida rechazada
        print("SECO:", "todo en verde" if ok else "FALLA", json.dumps({k: v.get("estado") for k, v in est.items()}))
        print((tmp / "eventos.log").read_text(encoding="utf-8"))
        return 0 if ok else 1
    finally:
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
