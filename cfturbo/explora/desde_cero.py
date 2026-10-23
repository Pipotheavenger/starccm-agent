"""Bomba nueva para un punto de diseño (Q, H, n) sin plantilla de la GUI.

Procedimiento verificado 2026-10-23 con CFturbo 2026.1.1 (ver recipes/exploracion-desde-cero.md):
  1. Elegir el ejemplo de CFturbo (o proyecto de projects/) con nq más cercano.
  2. Escalar por semejanza TODAS las longitudes del .cft con k = (n0/n)·sqrt(H/H0) (mantiene Psi y
     d2 queda exacto). Ángulos, coeficientes y posiciones relativas no se tocan.
  3. Si el nq pedido difiere del de la base, corregir solo la dirección axial (x del meridiano, b2,
     anchos) con c = (b2/d2)_Gülich(nq) / (b2/d2)_Gülich(nq0). Probado de nq 20 a 55 desde nq37.
  4. Poner el punto de diseño nuevo con MainDimensions/AutoUpdate=False (la geometría escalada manda).
     CFturbo recalcula solo los ángulos de álabe (BladeProperties AutoUpdate1/2) y la voluta
     (SpiralCasing AutoUpdate: secciones según Q y cu) al abrir el proyecto en batch.

Uso:
  python explora/desde_cero.py 100 30 2900 C:\\ruta\\nueva.cft      # escribe y corre CFturbo
  python explora/desde_cero.py --selftest                          # usa el CFturbo real (~40-70 s)
"""
from __future__ import annotations

import math
import os
import re
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent  # carpeta cfturbo/
EXAMPLES = Path(r"C:\Program Files\CFturbo 2026.1.1\Examples\PUMP - Centrifugal, Mixed-flow")
EXAMPLES_AX = EXAMPLES.parent / "PUMP - Axial"

# Bases validadas en batch tras escalar (rc=0). nq se lee del archivo; el nombre solo documenta.
# Radiales con voluta (CP), semiaxiales con difusor de tazón (MP, sin voluta), axiales (AP).
# ponytail: fuera "CP nq38 (wastewater)" (b2 enorme, pocos álabes: diseño para sólidos), los
# multietapa (nq12, nq19, nq23) y los MP inline con 4 estatores; se pueden pasar con base=.
BASES = [EXAMPLES / b for b in ("CP nq8 (Barske).cft", "CP nq20 (trimmable).cft",
                                "CP nq31 (const TE angle).cft", "CP nq37 (end-suction).cft",
                                "CP nq49 (blade loading).cft", "MP nq94 (bowl diffuser).cft",
                                "MP nq125 (bowl diffuser).cft")] + \
        [EXAMPLES_AX / b for b in ("AP nq120 (meanline).cft", "AP nq172 (hydrofoil).cft",
                                   "AP nq295 (meanline).cft")]

# Hojas Float que son longitudes absolutas (m). x/y se tratan aparte.
LEN_TAGS = {"d2", "b2", "dS", "dH", "xVal", "yVal", "dxVal", "dyVal", "Distance", "Width", "Diameter",
            "Fillet", "LinLength", "LinRadius", "HeightOffset", "DistTolerance", "H6", "ExtensionLength",
            "Thickness", "dH2", "dS2", "xTipInlet", "xTipOutlet"}
# Longitudes en dirección axial (x del meridiano = z): reciben además el factor c.
AX_TAGS = {"x", "xVal", "dxVal", "Distance", "b2", "Width"}


def _M():
    """mcp_server se importa tarde para que CFTURBO_WORKDIR del selftest tenga efecto."""
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    import mcp_server
    return mcp_server


def b2d2_gulich(nq: float) -> float:
    """b2/d2 óptimo de Gülich para bombas radiales (válido ~nq 10-100)."""
    x = nq / 100
    return 0.017 + 0.262 * x - 0.08 * x ** 2 + 0.0093 * x ** 3


def _design_point(root: ET.Element) -> tuple[float, float, float]:
    dp = root.find("CFturboProject/DesignPoint_Pump")
    return (float(dp.findtext("QFlow")) * 3600, float(dp.findtext("Head")), float(dp.findtext("nRot")) * 60)


def _nq(Q_m3h: float, H_m: float, n_rpm: float) -> float:
    return n_rpm * math.sqrt(Q_m3h / 3600) / H_m ** 0.75


def candidatos() -> list[dict]:
    """Bases disponibles con su nq: ejemplos validados + proyectos del usuario en projects/."""
    paths = list(BASES) + sorted((ROOT / "projects").glob("*/*.cft"))
    out = []
    for p in paths:
        if not p.exists():
            continue
        root = ET.parse(p).getroot()
        if _impeller(root) is None:
            continue
        try:
            Q, H, n = _design_point(root)
            out.append({"cft": str(p), "nq": round(_nq(Q, H, n), 1), "Q_m3h": Q, "H_m": H, "n_rpm": n})
        except (TypeError, ValueError, AttributeError, ZeroDivisionError):
            continue
    return out


def _impeller(root: ET.Element) -> ET.Element | None:
    e = root.find(".//CFturboDesign_RadialImpeller")
    return e if e is not None else root.find(".//CFturboDesign_AxialImpeller")


def elegir_base(nq: float) -> dict:
    return min(candidatos(), key=lambda b: abs(math.log(nq / b["nq"])))


def escalar(root: ET.Element, k: float, c: float = 1.0, kv: float | None = None) -> int:
    """Multiplica por k todas las longitudes del proyecto (y por k·c las axiales). Devuelve cuántas.
    kv (velocidades, = k·n/n0) se aplica a la distribución cu(r) de los impulsores axiales."""
    n = 0

    def walk(e: ET.Element, path: str) -> None:
        nonlocal n
        for ch in e:
            p = f"{path}/{ch.tag}"
            t = (ch.text or "").strip()
            if ch.get("Type") == "Float" and t and not len(ch):
                pts = "/Points/Value" in p  # distribuciones (espesor, filetes): x relativa, y en m
                if ch.tag in LEN_TAGS:
                    do = True
                elif ch.tag == "x" and kv and "CuCmDefinition" in p:  # axial: x = cu [m/s], y = r [m]
                    ch.text = repr(float(t) * kv)
                    n += 1
                    do = False
                elif ch.tag in ("x", "y"):
                    do = not ("SkeletonLines" in p or "Export_Interfaces" in p) and (not pts or ch.tag == "y")
                else:  # espesores de álabe s1/s2
                    do = ch.tag == "Value" and re.search(r"/s[12]/Value$", p) is not None
                if do:
                    f = k * (c if ch.tag in AX_TAGS and not pts else 1.0)
                    ch.text = repr(float(t) * f)
                    n += 1
            walk(ch, p)

    walk(root.find("CFturboProject"), "")
    return n


def preparar(Q_m3h: float, H_m: float, n_rpm: float, destino_cft: str | Path, base: str | None = None) -> dict:
    """Escribe destino_cft escalado desde la base. No corre CFturbo."""
    nq = _nq(Q_m3h, H_m, n_rpm)
    b = next((x for x in candidatos() if x["cft"] == str(base)), None) if base else elegir_base(nq)
    if b is None:  # base explícita fuera de la lista
        root0 = ET.parse(base).getroot()
        Q0, H0, n0 = _design_point(root0)
        b = {"cft": str(base), "nq": round(_nq(Q0, H0, n0), 1), "Q_m3h": Q0, "H_m": H0, "n_rpm": n0}
    tree = ET.parse(b["cft"])
    root = tree.getroot()
    k = (b["n_rpm"] / n_rpm) * math.sqrt(H_m / b["H_m"])
    c = min(max(b2d2_gulich(nq) / b2d2_gulich(b["nq"]), 0.6), 1.5)
    axial = root.find(".//CFturboDesign_AxialImpeller") is not None
    if axial:
        c = 1.0  # ponytail: corrección b2/d2 de Gülich solo vale para radiales
    md = _impeller(root).find("MainDimensions/MainDimensionsElement")
    d2_0 = float(md.findtext("d2") or md.findtext("dS"))  # axial: diámetro de punta
    b2_0 = float(md.findtext("b2") or 0)
    nodos = escalar(root, k, c, kv=k * n_rpm / b["n_rpm"])
    for e in root.iter("b2_d2"):
        e.text = repr(float(e.text) * c)
    md.find("AutoUpdate").text = "False"  # con True, dS sale de Eps y rompe el meridiano si crece
    dp = root.find("CFturboProject/DesignPoint_Pump")
    dp.find("QFlow").text = repr(Q_m3h / 3600)
    dp.find("Head").text = repr(float(H_m))
    dp.find("nRot").text = repr(n_rpm / 60)
    for e in root.iter("TMeanSurfSet"):  # modo carga de álabe (dmXdSwirl) guarda su propia nRot
        if e.find("nRot") is not None:
            e.find("nRot").text = repr(n_rpm / 60)
    destino_cft = Path(destino_cft)
    destino_cft.parent.mkdir(parents=True, exist_ok=True)
    tree.write(destino_cft, xml_declaration=True, encoding="UTF-8")
    aviso = None
    if abs(math.log(nq / b["nq"])) > math.log(1.5):
        aviso = (f"nq {nq:.1f} lejos de la base (nq {b['nq']}): fuera de lo probado (factor 1.5). "
                 "Mejor crear una base en la GUI para esa banda.")
    return {"cft": str(destino_cft), "base": b["cft"], "nq": round(nq, 1), "nq_base": b["nq"],
            "k": k, "c_axial": c, "nodos_escalados": nodos,
            "d2_mm": d2_0 * k * 1000, "b2_mm": b2_0 * k * c * 1000, "aviso": aviso}


def _stl_diam_impulsor(run_dir: str) -> float | None:
    """Diámetro (mm) de la salida del impulsor medido en el STL 'Outflow' del rotor."""
    for f in Path(run_dir).glob("*Impeller*Outflow*.stl"):
        xs, ys = [], []
        for line in f.read_text(errors="replace").splitlines():
            s = line.split()
            if s and s[0] == "vertex":
                xs.append(float(s[1])); ys.append(float(s[2]))
        if xs:
            return max(max(xs) - min(xs), max(ys) - min(ys))  # STL de CFturbo en mm
    return None


def nueva_bomba(Q_m3h: float, H_m: float, n_rpm: float, destino_cft: str | Path, base: str | None = None,
                correr: bool = True, exports=("StarCCM", "OpenFOAM"), name: str | None = None) -> dict:
    """Crea destino_cft para (Q m³/h, H m, n rpm) desde la base más cercana en nq y, si correr,
    lo pasa por CFturbo (run_batch del MCP: misma carpeta temporal, candado y bitácora)."""
    out = preparar(Q_m3h, H_m, n_rpm, destino_cft, base)
    if not correr:
        return out
    M = _M()
    name = name or f"nueva_nq{int(out['nq'])}"
    r = M.run_batch(out["cft"], {}, name, exports=list(exports))
    d = (r.get("info") or {}).get("dims") or {}
    out.update(returncode=r.get("returncode"), status=r["status"], seconds=r.get("seconds"),
               warnings=r["warnings"], errors=r["errors"], run_dir=r["run_dir"],
               d2_mm_cfturbo=d.get("d2_mm"), b2_mm_cfturbo=d.get("b2_mm"), dS_mm_cfturbo=d.get("dS_mm"),
               volute_d_out_mm=d.get("volute_d_out_mm"), out_cft=str(Path(r["run_dir"]) / f"{name}_out.cft"),
               d2_mm_stl=_stl_diam_impulsor(r["run_dir"]))
    return out


def selftest() -> None:
    import tempfile
    tmp = Path(tempfile.gettempdir()) / "cfturbo-explora" / "selftest"
    os.environ["CFTURBO_WORKDIR"] = str(tmp)  # no tocar las corridas de la UI
    M = _M()
    M._bitacora = lambda *a, **k: None  # el selftest no escribe en recipes/bitacora.md
    # 1) Sin CFturbo: escalado puro (k=0.5, c=1) duplica nada y reduce longitudes a la mitad.
    base = EXAMPLES / "CP nq37 (end-suction).cft"
    assert base.exists(), base
    r0 = ET.parse(base).getroot()
    r1 = ET.parse(base).getroot()
    n = escalar(r1, 0.5)
    assert n > 200, n
    md0 = r0.find(".//MainDimensionsElement[@Name='Version 1.']")
    md1 = r1.find(".//MainDimensionsElement[@Name='Version 1.']")
    for tag in ("d2", "b2", "dS", "dH"):
        assert abs(float(md1.findtext(tag)) - 0.5 * float(md0.findtext(tag))) < 1e-12, tag
    assert md1.findtext("Psi") == md0.findtext("Psi")  # adimensionales intactos
    sk = ".//SkeletonLines//ProgPoints/Value/y"
    assert [e.text for e in r1.iterfind(sk)] == [e.text for e in r0.iterfind(sk)]  # ángulos intactos
    assert abs(b2d2_gulich(37.4) - 0.104) < 0.002  # coincide con el ejemplo nq37
    print("selftest offline OK")
    # 2) Con CFturbo real: Q=100 m³/h, H=30 m, n=2900 rpm (nq 37.7 → base nq37, k≈0.813).
    t0 = time.time()
    r = nueva_bomba(100, 30, 2900, tmp / "nueva_Q100_H30_n2900.cft", exports=("OpenFOAM",), name="selftest_nueva")
    dt = time.time() - t0
    print({k: r.get(k) for k in ("base", "nq", "k", "c_axial", "returncode", "status", "d2_mm", "d2_mm_cfturbo",
                                 "d2_mm_stl", "b2_mm", "b2_mm_cfturbo", "volute_d_out_mm", "warnings", "errors")})
    assert r["returncode"] == 0 and not r["errors"] and not r["warnings"], r
    assert abs(r["d2_mm_cfturbo"] - r["d2_mm"]) < 0.01, r
    # El STL 'Outflow' del rotor nq37 llega más allá de d2 (hasta la entrada de la voluta): en el ejemplo
    # sin escalar mide 232.0 mm con d2 = 206.3 (relación 1.1246, medido 2026-10-23). Escalado debe conservarla.
    assert r["d2_mm_stl"] and abs(r["d2_mm_stl"] / r["d2_mm"] - 232.0 / 206.3) < 0.005, r
    # 3) nq lejos de la base (nq 25 desde nq20/31) también debe salir sin errores.
    r2 = nueva_bomba(60, 50, 3500, tmp / "nueva_nq25.cft", exports=("OpenFOAM",), name="selftest_nq25")
    print({k: r2.get(k) for k in ("base", "nq", "k", "c_axial", "returncode", "status", "d2_mm", "d2_mm_cfturbo",
                                  "d2_mm_stl", "warnings", "errors")})
    assert r2["returncode"] in (0, 1) and not r2["errors"], r2
    print(f"selftest OK ({dt:.0f} s la primera corrida, {time.time() - t0:.0f} s total)")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        selftest()
    elif len(sys.argv) >= 5:
        import json
        Q, H, n_ = map(float, sys.argv[1:4])
        print(json.dumps(nueva_bomba(Q, H, n_, sys.argv[4]), indent=1, ensure_ascii=False))
    else:
        print(__doc__)
