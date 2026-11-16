r"""Repositorio unificado y base de datos del DOE PAT1 en modo turbina (Sebastián, 2026-11-16: «ármalos»).

    python consolidar_pat.py            → Desktop\Geometrias_Prueba\PAT_PAT1_resultados\
    python consolidar_pat.py imagenes   → baja las escenas PNG de los workers a datos\<id>\…\images\ (una vez, ~GB)

Deja en el destino:
  PAT_PAT1_modo_turbina.xlsx   base de datos: Leeme, Geometrias, Simulaciones, Embalamiento, BEP_por_rpm, Paredes,
                               Fronteras, Malla_regiones (en formato tabla, cruzables por id)
  PAT_PAT1_puntos.csv          una fila por simulación (barrido de 32 casos + puntos extra de embalamiento)
  REVISION.md                  chequeos físicos y numéricos, bomba por bomba
  datos\<id>\barrido\Q…\       resultados.json y reports\*.csv de cada caso (copia de pat\_traido)
  datos\<id>\embalamiento\Q…\  ídem de los puntos extra (pat\emb*\_traido)
  excels\<id>_PAT.xlsx         el Excel de cada bomba
No toca los workers (salvo `imagenes`) ni nada del modo bomba: de allí solo LEE la fila de geometría (doe/base_datos.py)."""
import csv, json, math, pathlib, shutil, statistics, sys

AQUI = pathlib.Path(__file__).parent
DOE_DIR = AQUI.parent / "doe"
sys.path.insert(0, str(DOE_DIR))
import rango, consolidar, base_datos   # noqa: E402  (modo bomba, solo lectura)

DESTINO = pathlib.Path(r"C:\Users\investigacion\Desktop\Geometrias_Prueba\PAT_PAT1_resultados")
PLAN_PAT = json.loads((AQUI / "plan.json").read_text(encoding="utf-8"))["geometrias"]
PLAN_BOMBA = json.loads((DOE_DIR / "plan.json").read_text(encoding="utf-8"))["geometrias"]
G = 9.81


def regimen(rep: dict) -> str:
    if (rep.get("H") or 0) <= 0:
        return "bomba inversa"
    return "turbina" if (rep.get("P_eje") or 0) > 0 else "freno"


def leer(gid: str) -> list[dict]:
    """Puntos del barrido (pat/_traido) y de embalamiento (pat/emb*/_traido) de una bomba, con su serie y carpeta."""
    out = []
    fuentes = [("barrido", AQUI / "_traido" / gid)] + [("embalamiento", d / "_traido" / gid) for d in sorted(AQUI.glob("emb*")) if d.is_dir()]
    for serie, base in fuentes:
        for rj in sorted(base.glob("Q*/resultados.json")):
            d = json.loads(rj.read_text(encoding="utf-8"))
            d["_serie"], d["_dir"] = serie, rj.parent
            out.append(d)
    return out


def embalamiento(pts: list[dict]) -> list[dict]:
    """Por rpm, Q donde M_turb cambia de signo (interpolación lineal entre los dos puntos vecinos que lo cambian)."""
    out = []
    for n in sorted({round(p["rpm"]) for p in pts}, reverse=True):
        fila = sorted((p for p in pts if round(p["rpm"]) == n), key=lambda p: p["Q_m3h"])
        for a, b in zip(fila, fila[1:]):
            ma, mb = a["reportes"].get("M_turb"), b["reportes"].get("M_turb")
            if ma is not None and mb is not None and (ma <= 0 < mb or mb <= 0 < ma):
                t = (0 - ma) / (mb - ma)
                q = a["Q_m3h"] + (b["Q_m3h"] - a["Q_m3h"]) * t
                out.append({"rpm": n, "Q_emb_m3h": q, "H_emb_m": a["reportes"]["H"] + (b["reportes"]["H"] - a["reportes"]["H"]) * t,
                            "Q_izq_m3h": a["Q_m3h"], "Q_der_m3h": b["Q_m3h"], "series": f"{a['_serie']}/{b['_serie']}"})
    return out


def simulacion(gid: str, bomba: dict, d: dict) -> dict:
    r = d.get("reportes") or {}
    res = d.get("residuales") or {}
    cv = d.get("convergencia") or {}
    n = d["rpm"]; w = n * math.pi / 30; r2 = (bomba.get("D2_mm") or 0) / 2000
    qn = bomba["CFD_Qn_m3h"]
    out = {"id": gid, "tipo": bomba["tipo"], "nq": bomba["nq"], "Z": bomba["Z"], "dBeta2_deg": bomba["dBeta2_deg"], "f_D2": bomba["f_D2"],
           "D2_mm": bomba["D2_mm"], "serie": d["_serie"], "caso": int(d["caso"]) if d.get("caso") is not None else None,
           # entradas
           "rpm": n, "omega_rad_s": w, "Q_m3h": d["Q_m3h"], "Q_m3s": d["Q_m3h"] / 3600, "Q_Qn": d["Q_m3h"] / qn,
           "Q_Qn_semejanza": d["Q_m3h"] / qn * 3000 / n, "Flujo_kg_s": d.get("Flujo_kg_s"), "rho_kg_m3": d.get("rho"),
           "iteraciones": d.get("iteracion"), "regimen": regimen(r),
           # salidas (convención turbina: H = (pt_entrada − pt_salida)/ρg, entrada = brida de la voluta)
           "H_m": r.get("H"), "eta": r.get("eta"), "P_eje_W": r.get("P_eje"), "P_hid_W": r.get("P_hid"), "M_Nm": r.get("M"),
           "M_turb_Nm": r.get("M_turb"), "pt_entrada_Pa": r.get("pt_in"), "pt_salida_Pa": r.get("pt_out"),
           "Q_entrada_kg_s": r.get("Q_in"), "Q_salida_kg_s": r.get("Q_out"),
           "psi_H": G * r["H"] / (w * r2) ** 2 if r.get("H") is not None and r2 else None,
           "phi_Q": (d["Q_m3h"] / 3600) / (w * r2 ** 3) if r2 else None,
           "n11": n * (2 * r2) / math.sqrt(r["H"]) if r.get("H") and r["H"] > 0 and r2 else None,
           "Q11": (d["Q_m3h"] / 3600) / ((2 * r2) ** 2 * math.sqrt(r["H"])) if r.get("H") and r["H"] > 0 and r2 else None,
           # triángulos (1 = radio mayor, entrada de la turbina) y Euler: H_Euler = (U1Vu1 − U2Vu2)/g, η_Euler = H_Euler/H
           "U1_m_s": r.get("U1"), "U2_m_s": r.get("U2"), "Vu1_m_s": r.get("Vu1"), "Vu2_m_s": r.get("Vu2"), "Vr1_m_s": r.get("Vr1"),
           "Vr2_m_s": r.get("Vr2"), "UVu1_m2_s2": r.get("UVu1"), "UVu2_m2_s2": r.get("UVu2"), "H_Euler_m": r.get("H_Euler"),
           "eta_Euler": r.get("eta_Euler"),
           # malla y calidad numérica
           "celdas": d.get("celdas"), "yplus_alabes_medio": d.get("yplus_alabes_medio"), "yplus_alabes_max": d.get("yplus_alabes_max"),
           "balance_masa_pct": d.get("balance_masa_pct")}
    for k, v in sorted(res.items()):
        out["res_" + k.split(":")[0].replace("-", "_").replace(" ", "_")] = v
    out["residual_max"] = max(res.values()) if res else None
    for nom in ("H", "M", "eta"):
        m = cv.get(nom + " Monitor") or {}
        out[f"{nom}_deriva_pct_100it"] = m.get("deriva100_pct")
        out[f"{nom}_oscil_pct_100it"] = m.get("oscil100_pct")
    out["carpeta_datos"] = f"datos/{gid}/{d['_serie']}/{d['_dir'].name}"
    return out


def bep_por_rpm(gid: str, sims: list[dict]) -> list[dict]:
    out = []
    for n in sorted({s["rpm"] for s in sims if s["serie"] == "barrido"}, reverse=True):
        t = [s for s in sims if s["rpm"] == n and s["serie"] == "barrido" and s["regimen"] == "turbina"]
        if not t:
            out.append({"id": gid, "rpm": n, "Q_BEP_m3h": None}); continue
        b = max(t, key=lambda s: s["eta"])
        borde = b["Q_m3h"] == max(s["Q_m3h"] for s in sims if s["rpm"] == n and s["serie"] == "barrido")
        out.append({"id": gid, "rpm": n, "Q_BEP_m3h": b["Q_m3h"], "Q_BEP_Qn": b["Q_Qn"], "H_BEP_m": b["H_m"], "eta_max": b["eta"],
                    "P_eje_BEP_kW": b["P_eje_W"] / 1000, "M_turb_BEP_Nm": b["M_turb_Nm"], "n11_BEP": b["n11"], "Q11_BEP": b["Q11"],
                    "BEP_en_borde": borde})
    return out


def semejanza(sims: list[dict]) -> dict:
    """Casos a 1500 rpm frente a 3000 rpm interpolado al mismo caudal reducido (Q·3000/n): H₃₀₀₀ ≈ 4·H₁₅₀₀ y η igual.
    El BEP de cada rpm no sirve para esto: los caudales del barrido son los mismos a todas las rpm."""
    f3 = sorted(((s["Q_Qn"], s["H_m"], s["eta"]) for s in sims if s["rpm"] == 3000 and s["serie"] == "barrido" and s["regimen"] == "turbina"))
    dh, de = [], []
    for s in sims:
        if s["rpm"] != 1500 or s["serie"] != "barrido" or s["regimen"] != "turbina" or len(f3) < 2:
            continue
        q = s["Q_Qn"] * 2
        for a, b in zip(f3, f3[1:]):
            if a[0] <= q <= b[0]:
                t = (q - a[0]) / (b[0] - a[0])
                dh.append(abs((a[1] + (b[1] - a[1]) * t) / (4 * s["H_m"]) - 1) * 100)
                de.append(abs(a[2] + (b[2] - a[2]) * t - s["eta"]))
    return {"H_dev_max_pct": max(dh) if dh else None, "eta_dif_max": max(de) if de else None, "n": len(dh)}


def revisar(gid: str, sims: list[dict], beps: list[dict], emb: list[dict]) -> list[str]:
    av = []
    bar = [s for s in sims if s["serie"] == "barrido"]
    if len(bar) != 32: av.append(f"{len(bar)} casos en el barrido (se esperaban 32)")
    if len({s["celdas"] for s in sims}) > 1: av.append(f"celdas distintas entre casos: {sorted({s['celdas'] for s in sims})}")
    if any(s["iteraciones"] != 1500 for s in sims): av.append("iteraciones ≠ 1500 en algún caso")
    for s in sims:
        tag = f"{s['Q_m3h']:.1f} m³/h a {s['rpm']:.0f} rpm"
        if s["P_eje_W"] is not None and s["M_Nm"] is not None and abs(s["P_eje_W"] - s["M_Nm"] * s["omega_rad_s"]) > 0.01 * max(abs(s["P_eje_W"]), 1):
            av.append(f"P_eje ≠ M·ω en {tag}")
        if s["eta"] is not None and s["regimen"] == "turbina" and s["eta"] > 0.95: av.append(f"η = {s['eta']:.3f} en {tag}")
        if s["balance_masa_pct"] is not None and s["balance_masa_pct"] > 0.5: av.append(f"balance de masa {s['balance_masa_pct']:.2f} % en {tag}")
        if s["H_deriva_pct_100it"] is not None and abs(s["H_deriva_pct_100it"]) > 2 and s["regimen"] == "turbina":
            av.append(f"H sin estabilizar ({s['H_deriva_pct_100it']:.1f} %/100 it) en {tag}")
        if s["regimen"] == "bomba inversa": av.append(f"H ≤ 0 (bomba inversa) en {tag}")
    # H debe crecer con Q a rpm fija (turbina): bajadas > 5 % entre caudales vecinos
    for n in sorted({s["rpm"] for s in bar}):
        f = sorted((s for s in sims if s["rpm"] == n), key=lambda s: s["Q_m3h"])
        baja = [f"{a['Q_m3h']:.0f}→{b['Q_m3h']:.0f}" for a, b in zip(f, f[1:]) if b["H_m"] < a["H_m"] * 0.95]
        if baja: av.append(f"H baja al subir Q a {n:.0f} rpm: " + ", ".join(baja))
    sem = semejanza(sims)
    if sem["H_dev_max_pct"] is not None and sem["H_dev_max_pct"] > 10:
        av.append(f"semejanza 1500↔3000 rpm: H difiere hasta {sem['H_dev_max_pct']:.1f} % (H₃₀₀₀ frente a 4·H₁₅₀₀ al mismo Q·3000/n)")
    if sem["eta_dif_max"] is not None and sem["eta_dif_max"] > 0.05:
        av.append(f"semejanza 1500↔3000 rpm: η difiere hasta {sem['eta_dif_max']:.3f}")
    b = {x["rpm"]: x for x in beps if x.get("Q_BEP_m3h")}
    if any(x.get("BEP_en_borde") for x in beps): av.append("BEP en el caudal máximo del barrido (2,4 Qn) a " + ", ".join(f"{x['rpm']:.0f}" for x in beps if x.get("BEP_en_borde")) + " rpm: el máximo real puede estar más arriba")
    if not any(e["rpm"] == 3000 for e in emb): av.append("sin cambio de signo de M_turb a 3000 rpm")
    return av


def bomba_modo_bomba(rg: dict, doe_xl: dict) -> dict:
    """Fila de Geometrias del modo bomba (dimensiones, CFturbo, resumen CFD de bomba): solo lectura de doe/."""
    pts = consolidar.puntos(rg["id"], rg)
    fil = [consolidar.fila(rg["id"], rg, consolidar.geometria(rg), d) for d in pts]
    res, _ = consolidar.revisar(rg["id"], fil, rg, PLAN_BOMBA.get(rg["id"], {}).get("its") or 1500)
    return base_datos.geometria(rg, doe_xl, PLAN_BOMBA, pts, fil, res)


LEEME = [
    ("DOE PAT1 – base de datos en modo turbina (PAT)", ""),
    ("", ""),
    ("Contenido", "47 geometrías (21 base y 26 variantes) del DOE en modo bomba, corridas como turbina: barrido de 32 casos (4 rpm × 8 caudales) = 1504 simulaciones, más 148 puntos extra de embalamiento a 3000 rpm. STAR-CCM+ 2602, estacionario."),
    ("Barrido", "rpm 3000, 1500, 1000 y 500 × Q = 0,8 … 2,4 Qn en 8 pasos (Qn = caudal de diseño en bomba a 3000 rpm)."),
    ("Embalamiento", "Ronda 1: 3000 rpm, Q = 0,7 · 0,55 · 0,4 Qn (G001: 2,6 · 3,0 · 3,4 Qn; G002 no, ya cruza). Ronda 2: 0,35 · 0,3 Qn en G004, G010, G019, G027, G029."),
    ("Física", "Misma malla y modelos que en bomba (k-ω SST, All y+, MRF, agua 998,2 kg/m³, Cell Quality Remediation; URF p 0,2 / v 0,5; 1500 it por caso). Caudal invertido: entra por la brida de la voluta (caudal másico impuesto) y sale por la boca de la bomba (presión 0 Pa). MRF girando al revés que en bomba, a +rpm."),
    ("", ""),
    ("Hojas", ""),
    ("Geometrias", "1 fila por bomba: lo del modo bomba (parámetros del DOE, dimensiones y predicción de CFturbo con prefijo cft_, resumen CFD de bomba con prefijo CFD_) + resumen PAT (prefijo PAT_): BEP de turbina a 3000 rpm, relaciones con el BEP de bomba, embalamiento."),
    ("Simulaciones", "1 fila por caso (serie = barrido o embalamiento): entradas, salidas, coeficientes ψ = gH/(ωr2)², φ = Q/(ωr2³), n11 = n·D2/√H y Q11 = Q/(D2²√H), triángulos, Euler, calidad numérica."),
    ("BEP_por_rpm", "Máxima η con P_eje > 0 en cada rpm del barrido."),
    ("Embalamiento", "Q donde M_turb cambia de signo, por bomba y rpm (interpolación lineal entre los dos casos vecinos)."),
    ("Paredes / Fronteras", "y+ por pared; caudal, presión media, presión total y área de entrada y salida, por caso."),
    ("Malla_regiones", "Celdas por región de cada bomba."),
    ("", ""),
    ("Convención", "H = (pt_entrada − pt_salida)/(ρg) con la entrada en la voluta; P_hid = ρgQH; P_eje = M·ω con signo (> 0: la máquina entrega potencia, turbina); M_turb = P_eje/|ω|; η = P_eje/P_hid. Régimen: turbina (H > 0, P_eje > 0), freno (H > 0, P_eje ≤ 0), bomba inversa (H ≤ 0)."),
    ("Euler", "1 = radio mayor (entrada de la turbina): H_Euler = (U1Vu1 − U2Vu2)/g, η_Euler = H_Euler/H."),
    ("Q_Qn_semejanza", "Q/Qn × 3000/n: caudal reducido a 3000 rpm por semejanza (Q ∝ n), para comparar rpm."),
    ("", ""),
    ("Avisos", ""),
    ("Residuales", "Continuidad 0,03–0,3 en muchos casos (como en bomba nq 10–25): H y M estables (deriva < 2 %/100 it) es el criterio que se usó."),
    ("G001", "A 3000 rpm el barrido es todo freno; entre 2,4 y 2,6 Qn la H salta de 83 a 131 m (puntos en freno con reuso de solución frente a puntos nuevos en frío): el embalamiento (2,41 Qn) vale, la H justo ahí es dudosa."),
    ("Vu2_inf y factor_deslizamiento", "Anulados en PAT (no tienen sentido en turbina); no están en esta base."),
    ("Simulaciones guardadas", "Solo el .sim del BEP de turbina a la rpm más alta con P_eje > 0 de cada bomba (en el worker); G001 guardó por error un caso de freno a 3000 rpm."),
    ("Detalle", "REVISION.md en esta carpeta; datos por caso en datos\\<id>\\barrido|embalamiento\\Q…\\ (JSON, CSV de monitores e imágenes)."),
]


def escribir_db(salida: pathlib.Path, hojas: dict[str, list[dict]]):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    from openpyxl.utils import get_column_letter
    from openpyxl.worksheet.table import Table, TableStyleInfo
    wb = Workbook()
    ws = wb.active; ws.title = "Leeme"
    for a, b in LEEME: ws.append([a, b])
    ws["A1"].font = Font(bold=True, size=14)
    for row in ws.iter_rows(min_row=3):
        if row[0].value and not row[1].value: row[0].font = Font(bold=True)
        row[1].alignment = Alignment(wrap_text=True, vertical="top")
    ws.column_dimensions["A"].width = 26; ws.column_dimensions["B"].width = 140
    for nom, filas in hojas.items():
        cab = list(dict.fromkeys(c for f in filas for c in f))
        ws = wb.create_sheet(nom)
        ws.append(cab)
        for f in filas:
            ws.append([v if not isinstance(v := f.get(c), (list, dict)) else json.dumps(v, ensure_ascii=False) for c in cab])
        for c in ws[1]:
            c.font, c.fill = Font(bold=True, color="FFFFFF"), PatternFill("solid", fgColor="2F5597")
            c.alignment = Alignment(wrap_text=True, vertical="center")
        for j, h in enumerate(cab, 1):
            ws.column_dimensions[get_column_letter(j)].width = max(9, min(26, len(h) + 2))
        ws.row_dimensions[1].height = 42
        ws.freeze_panes = "B2"
        t = Table(displayName=nom, ref=f"A1:{get_column_letter(len(cab))}{len(filas) + 1}")
        t.tableStyleInfo = TableStyleInfo(name="TableStyleLight9", showRowStripes=True)
        ws.add_table(t)
    salida.parent.mkdir(parents=True, exist_ok=True)
    wb.save(salida)


def main(destino: pathlib.Path = DESTINO):
    destino.mkdir(parents=True, exist_ok=True)
    doe_xl = base_datos.doe_tabla()
    hojas = {k: [] for k in ("Geometrias", "Simulaciones", "BEP_por_rpm", "Embalamiento", "Paredes", "Fronteras", "Malla_regiones")}
    texto = []
    for rg in rango.todas(plan=PLAN_BOMBA):
        gid = rg["id"]
        geo = bomba_modo_bomba(rg, doe_xl)
        pts = leer(gid)
        sims = sorted((simulacion(gid, geo, d) for d in pts), key=lambda s: (s["serie"] != "barrido", -s["rpm"], s["Q_m3h"]))
        beps = bep_por_rpm(gid, sims)
        emb = embalamiento(pts)
        av = revisar(gid, sims, beps, emb)
        b3 = next((x for x in beps if x["rpm"] == 3000 and x.get("Q_BEP_m3h")), None)
        bt = b3 or next((x for x in beps if x.get("Q_BEP_m3h")), {})
        e3 = next((e for e in emb if e["rpm"] == 3000), {})
        pump_q, pump_h, pump_eta = geo.get("CFD_Q_BEP_m3h"), geo.get("CFD_H_BEP_m"), geo.get("CFD_eta_max")
        geo.update({
            "PAT_casos_barrido": sum(s["serie"] == "barrido" for s in sims), "PAT_casos_embalamiento": sum(s["serie"] != "barrido" for s in sims),
            "PAT_BEP_rpm": bt.get("rpm"), "PAT_Q_BEP_m3h": bt.get("Q_BEP_m3h"), "PAT_Q_BEP_Qn": bt.get("Q_BEP_Qn"), "PAT_H_BEP_m": bt.get("H_BEP_m"),
            "PAT_eta_max": bt.get("eta_max"), "PAT_P_eje_BEP_kW": bt.get("P_eje_BEP_kW"), "PAT_BEP_en_borde": bt.get("BEP_en_borde"),
            # relaciones turbina/bomba a 3000 rpm (correlaciones PAT clásicas: Q_t/Q_b, H_t/H_b, η_t/η_b)
            "PAT_Qt_Qb": b3["Q_BEP_m3h"] / pump_q if b3 and pump_q else None,
            "PAT_Ht_Hb": b3["H_BEP_m"] / pump_h if b3 and pump_h else None,
            "PAT_etat_etab": b3["eta_max"] / pump_eta if b3 and pump_eta else None,
            "PAT_Q_emb_3000_m3h": e3.get("Q_emb_m3h"), "PAT_Q_emb_3000_Qn": e3["Q_emb_m3h"] / geo["CFD_Qn_m3h"] if e3 else None,
            "PAT_H_emb_3000_m": e3.get("H_emb_m"),
            "PAT_semejanza_H_dev_max_pct": semejanza(sims)["H_dev_max_pct"], "PAT_semejanza_eta_dif_max": semejanza(sims)["eta_dif_max"],
            "PAT_sim_guardada": next((f"{x['rpm']:.0f} rpm, {x['Q_BEP_m3h']:.1f} m³/h" for x in beps if x.get("Q_BEP_m3h")), None),
            "PAT_avisos": " | ".join(av),
        })
        hojas["Geometrias"].append(geo)
        hojas["Simulaciones"] += sims
        hojas["BEP_por_rpm"] += beps
        hojas["Embalamiento"] += [{"id": gid, "nq": geo["nq"], "Qn_m3h": geo["CFD_Qn_m3h"], **e, "Q_emb_Qn": e["Q_emb_m3h"] / geo["CFD_Qn_m3h"]} for e in emb]
        for d in pts:
            base = {"id": gid, "serie": d["_serie"], "rpm": d["rpm"], "Q_m3h": d["Q_m3h"]}
            for k, v in (d.get("paredes") or {}).items():
                reg, nom = k.split("/", 1)
                if nom not in ("Inflow", "Outflow"): hojas["Paredes"].append({**base, "region": reg, "pared": nom, **v})
            for k, v in (d.get("entradas_salidas") or {}).items():
                reg, nom = k.split("/", 1)
                hojas["Fronteras"].append({**base, "region": reg, "frontera": nom, **v})
        p0 = next((p for p in pts if p.get("celdas_region")), {})
        hojas["Malla_regiones"] += [{"id": gid, "region": k, "celdas": v} for k, v in (p0.get("celdas_region") or {}).items()]
        # texto de revisión
        texto.append(f"## {gid}  ({geo['tipo']}, nq {geo['nq']:.0f})")
        if b3: texto.append(f"BEP turbina a 3000 rpm: Q {b3['Q_BEP_m3h']:.1f} m³/h ({b3['Q_BEP_Qn']:.2f} Qn), H {b3['H_BEP_m']:.1f} m, η {b3['eta_max']:.3f}"
                            + (f" · Qt/Qb {geo['PAT_Qt_Qb']:.2f}, Ht/Hb {geo['PAT_Ht_Hb']:.2f}" if geo["PAT_Qt_Qb"] else ""))
        texto.append("Embalamiento: " + (", ".join(f"{e['rpm']:.0f} rpm → {e['Q_emb_m3h']:.1f} m³/h ({e['Q_emb_m3h'] / geo['CFD_Qn_m3h']:.2f} Qn)" for e in emb) or "—"))
        texto += [f"- {a}" for a in av] or ["- sin avisos"]
        texto.append("")
        # copia de datos y Excel
        for d in {(p["_serie"], p["_dir"]) for p in pts}:
            shutil.copytree(d[1], destino / "datos" / gid / d[0] / d[1].name, dirs_exist_ok=True)
        x = PLAN_PAT.get(gid, {})
        xl = pathlib.Path(x.get("carpeta", rg["carpeta"])) / "PAT" / f"{gid}_PAT.xlsx"
        if xl.exists():
            (destino / "excels").mkdir(exist_ok=True); shutil.copy2(xl, destino / "excels" / xl.name)
        print(gid, len(sims), "casos,", len(av), "avisos", flush=True)
    cab = list(dict.fromkeys(c for f in hojas["Simulaciones"] for c in f))
    with open(destino / "PAT_PAT1_puntos.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=cab, delimiter=";"); w.writeheader(); w.writerows(hojas["Simulaciones"])
    escribir_db(destino / "PAT_PAT1_modo_turbina.xlsx", hojas)
    (destino / "REVISION.md").write_text("# Revisión del DOE PAT1 en modo turbina\n\n" + "\n".join(texto), encoding="utf-8")
    print({k: len(v) for k, v in hojas.items()}, "->", destino)
    return hojas


def bajar_imagenes(destino: pathlib.Path = DESTINO):
    """Escenas de cada caso (en el worker: <dir>\\puntos\\Q…\\images) → datos\\<id>\\<serie>\\Q…\\images\\, un hilo por worker."""
    import concurrent.futures, tempfile
    sys.path.insert(0, str(AQUI))
    import doe
    trabajos = []
    for serie, plan in [("barrido", AQUI / "plan.json")] + [("embalamiento", d / "plan.json") for d in sorted(AQUI.glob("emb*")) if (d / "plan.json").exists()]:
        for gid, e in json.loads(plan.read_text(encoding="utf-8"))["geometrias"].items():
            trabajos.append((e["worker"], gid, serie, e["dir"]))
    def una(t):
        ip, gid, serie, d = t
        with tempfile.TemporaryDirectory() as tmp:
            doe.scp(tmp, ip, (d + "/puntos").replace("\\", "/"), bajar=True)
            n = 0
            for img in pathlib.Path(tmp).glob("puntos/Q*/images"):
                dst = destino / "datos" / gid / serie / img.parent.name / "images"
                shutil.copytree(img, dst, dirs_exist_ok=True); n += len(list(dst.glob("*.png")))
        return f"{gid} {serie} {n}"
    por_worker = {}
    for t in trabajos: por_worker.setdefault(t[0], []).append(t)
    with concurrent.futures.ThreadPoolExecutor(len(por_worker)) as ex:
        for r in ex.map(lambda ts: [una(t) for t in ts], por_worker.values()):
            for x in r: print(x, flush=True)


if __name__ == "__main__":
    if sys.argv[1:2] == ["imagenes"]:
        bajar_imagenes()
    else:
        main(pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else DESTINO)
