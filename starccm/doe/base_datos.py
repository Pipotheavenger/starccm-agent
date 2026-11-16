r"""Base de datos del DOE PAT1 en modo bomba: un solo Excel con todo (2026-11-10, Sebastián).

    python base_datos.py   → Desktop\Geometrias_Prueba\DOE_PAT1_resultados\DOE_PAT1_modo_bomba.xlsx

Hojas (todas en formato tabla, con id de geometría para cruzarlas):
  Leeme            qué hay en cada hoja, unidades, fuentes y avisos de calidad
  Geometrias       1 fila por bomba: parámetros del DOE, punto de diseño, dimensiones y predicción de CFturbo,
                   malla, ajustes de la simulación y resumen CFD (BEP, H y η en Qn, H a válvula cerrada)
  Simulaciones     1 fila por punto: entradas (caudal, rpm, fluido, iteraciones), todas las salidas de STAR-CCM+,
                   triángulos de velocidad, referencia CFturbo en ese caudal, calidad (residuales, deriva, balance, y+)
  Paredes          1 fila por punto y pared: y+ medio/mín/máx, fracciones de área por rango de y+, esfuerzo cortante
  Fronteras        1 fila por punto y entrada/salida: caudal, presión media, presión total, área
  Malla_regiones   1 fila por bomba y región: celdas
  Curvas_CFturbo   curva H, η y P de CFturbo (1D) de cada bomba
Fuentes: plan/rango del DOE (rango.py), DOE_geometrias_PAT_1_estado.xlsx, run.json de CFturbo de cada carpeta y
_traido\<id>\Q…\resultados.json (STAR-CCM+ 2602)."""
import json, math, pathlib, re

import excel, rango, consolidar

AQUI = pathlib.Path(__file__).parent
SALIDA = consolidar.DESTINO / "DOE_PAT1_modo_bomba.xlsx"
DOE_XLSX = pathlib.Path(r"C:\Users\investigacion\Desktop\Geometrias_Prueba\DOE_geometrias_PAT_1_estado.xlsx")
G = 9.81


def doe_tabla() -> dict:
    """Hoja DOE del Excel de geometrías (columnas de texto y números escritos; las fórmulas se recalculan aquí)."""
    import openpyxl
    ws = openpyxl.load_workbook(DOE_XLSX, read_only=True)["DOE"]
    filas = list(ws.iter_rows(values_only=True))
    cab = filas[0]
    return {f[0]: dict(zip(cab, f)) for f in filas[1:] if f[0]}


def fnum(x):
    try:
        return None if x is None or (isinstance(x, float) and math.isnan(x)) else float(x)
    except (TypeError, ValueError):
        return None


def geometria(rg: dict, doe: dict, plan: dict, pts: list[dict], filas: list[dict], res: dict) -> dict:
    run = json.loads((pathlib.Path(rg["carpeta"]) / "run.json").read_text(encoding="utf-8"))
    info, dims, rep = run.get("info", {}), run.get("info", {}).get("dims", {}), run.get("report", {})
    d = doe.get(rg["id"], {})
    dp = info.get("design_point", {})
    nq = info.get("nq", {})
    npshr = rep.get("npshr_m") or {}
    gul = npshr.get("Gülich")
    p0 = next((p for p in pts if p.get("version_json")), pts[0])
    x = plan.get(rg["id"], {})
    out = {
        "id": rg["id"], "tipo": d.get("tipo"), "nq": fnum(d.get("nq")), "banda_nq": d.get("banda_nq"), "rol": d.get("rol"),
        "Z": int(dims["nBl"]) if dims.get("nBl") else None, "dBeta2_deg": fnum(d.get("Δβ2 (°)")), "f_D2": fnum(d.get("f_D2")),
        "voluta": d.get("voluta"), "carpeta": pathlib.Path(rg["carpeta"]).name,
        # punto de diseño (entrada de CFturbo)
        "n_diseno_rpm": dp.get("n_rpm"), "Q_diseno_m3h": dp.get("Q_m3h"), "H_diseno_m": dp.get("H_m"), "rho_kg_m3": dp.get("rho"),
        "fluido": dp.get("fluid"), "Q_diseno_m3s": nq.get("Q_m3s"), "P_hid_diseno_kW": nq.get("P_hid_kW"), "ns_us": nq.get("ns_us"),
        "tipo_rodete": nq.get("tipo"),
        # dimensiones principales (CFturbo)
        "D2_mm": dims.get("d2_mm"), "b2_mm": dims.get("b2_mm"), "b2_D2": dims.get("b2_d2"), "Ds_succion_mm": dims.get("dS_mm"),
        "Dh_cubo_mm": dims.get("dH_mm"), "espesor_alabe_mm": dims.get("s_mm"),
        "beta1_cubo_deg": dims.get("beta1_hub_deg"), "beta1_cubierta_deg": dims.get("beta1_shroud_deg"),
        "beta2_cubo_deg": dims.get("beta2_hub_deg"), "beta2_cubierta_deg": dims.get("beta2_shroud_deg"),
        "angulo_abrazado_deg": rep.get("wrap_deg"), "garganta_rodete_mm2": rep.get("throat_mm2"),
        "w2_w1": (rep.get("w2_w1") or [None])[0], "Psi_coef_presion": dims.get("Psi"),
        "D_salida_voluta_mm": dims.get("volute_d_out_mm"), "garganta_voluta_mm2": rep.get("volute_throat_mm2"),
        # predicción 1D de CFturbo en el diseño
        "cft_eta_h_pct": rep.get("eta_h_pct"), "cft_eta_v_pct": rep.get("eta_v_pct"), "cft_eta_m_pct": rep.get("eta_m_pct"),
        "cft_eta_total_pct": rep.get("eta_st_pct"), "cft_u2_m_s": rep.get("u2"), "cft_cu2_m_s": rep.get("cu2"),
        "cft_cm2_m_s": rep.get("cm2"), "cft_P_eje_kW": rep.get("P_kW"), "cft_M_Nm": rep.get("torque_Nm"),
        "cft_NPSHa_m": rep.get("npsha_m"), "cft_NPSHr_Gulich_m": gul[0] if isinstance(gul, list) else gul,
        "cft_H_Qn_m": rg["Hn_cfturbo_m"],
        # simulación (STAR-CCM+)
        "CFD_rpm": abs(rg["rpm"]), "CFD_Qn_m3h": rg["Qn_m3h"], "CFD_Qmax_m3h": rg["Qmax_m3h"], "CFD_puntos": len(pts),
        "CFD_iteraciones": x.get("its") or 1500, "CFD_celdas": p0.get("celdas"),
        "CFD_modelos": "; ".join(sum((m for m in (p0.get("modelos") or {}).values()), [])),
        "CFD_urf_p": (p0.get("solvers") or {}).get("Segregated Flow", {}).get("PressureSolver"),
        "CFD_urf_v": (p0.get("solvers") or {}).get("Segregated Flow", {}).get("VelocitySolver"),
        "CFD_frontera_entrada": "presión total 0 Pa", "CFD_frontera_salida": "caudal másico (parámetro Flujo)",
        "CFD_worker": x.get("worker"),
    }
    for k in ("H_Qn_m", "H_Qn_H_cfturbo", "eta_Qn", "eta_Qn_cfturbo", "Q_BEP_m3h", "Q_BEP_Qn", "eta_max", "H_BEP_m",
              "H_cierre_m", "H_cierre_H_Qn", "P_eje_Qn_kW", "yplus_alabes_Qn"):
        out["CFD_" + k] = res.get(k)
    out["avisos"] = res.get("detalle")
    return out


def simulacion(rg: dict, geo: dict, d: dict, f: dict) -> dict:
    r = d.get("reportes") or {}
    res = d.get("residuales") or {k: v[-1] for k, v in d["_series"].items() if "Residual" in k and v}
    cv = d.get("convergencia") or {}
    out = {"id": rg["id"], "tipo": geo["tipo"], "nq": geo["nq"], "Z": geo["Z"], "dBeta2_deg": geo["dBeta2_deg"], "f_D2": geo["f_D2"],
           "D2_mm": geo["D2_mm"], "b2_mm": geo["b2_mm"],
           # entradas
           "punto_orden": f["punto"], "Q_m3h": f["Q_m3h"], "Q_m3s": f["Q_m3h"] / 3600, "Q_Qn": f["Q_Qn"], "Flujo_kg_s": d.get("Flujo_kg_s"),
           "rpm": abs(rg["rpm"]), "omega_rad_s": abs(rg["rpm"]) * math.pi / 30, "rho_kg_m3": rg["rho"], "iteraciones": d.get("iteracion"),
           # salidas principales
           "H_m": r.get("H"), "eta": r.get("eta"), "M_Nm": r.get("M"), "P_eje_W": r.get("P_eje"), "P_hid_W": r.get("P_hid"),
           "pt_entrada_Pa": r.get("pt_in"), "pt_salida_Pa": r.get("pt_out"), "Q_entrada_kg_s": r.get("Q_in"), "Q_salida_kg_s": r.get("Q_out"),
           "psi_H": G * r["H"] / (abs(rg["rpm"]) * math.pi / 30 * geo["D2_mm"] / 2000) ** 2 if r.get("H") is not None and geo["D2_mm"] else None,
           "phi_Q": (f["Q_m3h"] / 3600) / (abs(rg["rpm"]) * math.pi / 30 * (geo["D2_mm"] / 2000) ** 3) if geo["D2_mm"] else None,
           # triángulos de velocidad y Euler
           "U1_m_s": r.get("U1"), "U2_m_s": r.get("U2"), "Vu1_m_s": r.get("Vu1"), "Vu2_m_s": r.get("Vu2"), "Vr1_m_s": r.get("Vr1"),
           "Vr2_m_s": r.get("Vr2"), "UVu1_m2_s2": r.get("UVu1"), "UVu2_m2_s2": r.get("UVu2"), "H_Euler_m": r.get("H_Euler"),
           "eta_Euler": r.get("eta_Euler"), "Vu2_inf_m_s": r.get("Vu2_inf"), "factor_deslizamiento": r.get("factor_deslizamiento"),
           # referencia CFturbo en este caudal
           "cft_H_m": f["H_cfturbo_m"], "cft_eta": f["eta_cfturbo"], "H_H_cft": f["H_H_cfturbo"],
           # malla y calidad
           "celdas": d.get("celdas"), "celdas_calidad_lt_1e-2": f["celdas_calidad_lt_1e-2"], "celdas_skew_gt_85": f["celdas_skew_gt_85"],
           "yplus_alabes_medio": f["yplus_alabes_medio"], "yplus_alabes_max": f["yplus_alabes_max"], "yplus_alabes_min": r.get("yplus_min_alabes"),
           "balance_masa_pct_punto": f["balance_pct_punto"], "balance_masa_pct_Qn": f["balance_pct_Qn"]}
    for k, v in sorted(res.items()):
        out["res_" + k.split(":")[0].replace("-", "_").replace(" ", "_")] = v
    out["residual_max"] = f["residual_max"]
    for nom in ("H", "M", "eta", "Q_in", "pt_out"):
        m = cv.get(nom + " Monitor") or {}
        out[f"{nom}_media_100it"] = m.get("media100")
        out[f"{nom}_deriva_pct_100it"] = m.get("deriva100_pct")
        out[f"{nom}_oscil_pct_100it"] = m.get("oscil100_pct")
    out["H_deriva_pct_100it"] = out["H_deriva_pct_100it"] if out["H_deriva_pct_100it"] is not None else f["deriva_H_pct"]
    out["chequeo_residual"], out["chequeo_deriva_H"] = f["chequeo_residual"], f["chequeo_deriva_H"]
    out["datos"] = f["datos"]
    out["carpeta_datos"] = f["carpeta_datos"]
    return out


def paredes(rg, d, f):
    for k, v in (d.get("paredes") or {}).items():
        reg, nom = k.split("/", 1)
        if nom in ("Inflow", "Outflow"):   # caras de interfaz (JSON v2 de antes del arreglo del 2026-11-09)
            continue
        yield {"id": rg["id"], "Q_m3h": f["Q_m3h"], "Q_Qn": f["Q_Qn"], "region": reg, "pared": nom, **v}


def fronteras(rg, d, f):
    for k, v in (d.get("entradas_salidas") or {}).items():
        reg, nom = k.split("/", 1)
        yield {"id": rg["id"], "Q_m3h": f["Q_m3h"], "region": reg, "frontera": nom, **v}


LEEME = [
    ("DOE PAT1 – base de datos en modo bomba", ""),
    ("", ""),
    ("Contenido", "47 geometrías (21 base y 26 variantes) × 10 caudales = 470 simulaciones estacionarias en STAR-CCM+ 2602."),
    ("Modo", "Bomba: giro 3000 rpm, caudal impuesto en la salida (parámetro Flujo), presión total 0 Pa en la entrada."),
    ("Modelo", "k-ω SST, All y+, MRF (rotor congelado), agua 998,2 kg/m³, Cell Quality Remediation; URF p 0,2 / v 0,5."),
    ("Iteraciones", "1500 por punto; G001–G004 rehechas a 2000 (2026-11-10)."),
    ("", ""),
    ("Hojas", ""),
    ("Geometrias", "1 fila por bomba: parámetros del DOE (nq, Z, Δβ2, f_D2, voluta), punto de diseño, dimensiones y predicción 1D de CFturbo (prefijo cft_), malla y resumen CFD (prefijo CFD_)."),
    ("Simulaciones", "1 fila por punto: entradas (Q, Q/Qn, Flujo, rpm, ω, ρ, iteraciones), salidas de STAR-CCM+, coeficientes ψ = gH/U2² y φ = Q/(ω·r2³), triángulos de velocidad, Euler, referencia CFturbo y calidad numérica."),
    ("Paredes", "y+ medio/mín/máx, fracción de área con y+ < 1, 30–300 y > 300, esfuerzo cortante medio, por pared y punto."),
    ("Fronteras", "Entrada y salida de cada punto: caudal, presión estática media, presión total másica, área."),
    ("Malla_regiones", "Celdas por región de cada bomba (estator = boca de entrada, rotor, voluta, extensiones)."),
    ("Curvas_CFturbo", "Curva H–Q, η–Q y P–Q de la predicción 1D de CFturbo."),
    ("", ""),
    ("Unidades", "Q m³/h (Q_m3s en m³/s), H m, M N·m, P W (kW donde se indica), p Pa, velocidades m/s, ángulos °, longitudes mm."),
    ("Signos", "rpm de la simulación −3000 (se guarda en positivo); Q_entrada < 0 = entra; P_eje = −M·ω."),
    ("", ""),
    ("Avisos de calidad", ""),
    ("nq 10–25", "G001–G013: residual de continuidad 0,03–2 sin bajar (resto ~5e-3); H y M estables ±2 % frente a 2000 it, relajación baja y malla × 0,75 (pruebas en G001 y G002). H ~24 % sobre CFturbo y η_Euler > 1 cerca de Qn."),
    ("nq 35–57 base", "H en Qn 14–29 % por debajo de CFturbo, con buena convergencia."),
    ("Variantes fD2 < 0,9", "Su BEP cae en 0,6–0,8 Qn; por encima de 1,1–1,3 Qn la H es negativa (régimen de freno/turbina)."),
    ("Caudal ≈ 0", "Punto de 0,1 m³/h: balance y η no tienen sentido en %; flujo recirculante, H ±1,5 %."),
    ("η de CFturbo", "cft_eta por caudal es casi constante por familia (0,559 nq 10–25; 0,866 nq 30–57): no usarla como validación."),
    ("y+", "Medio en álabes 8–19 (zona de transición, tratada con All y+)."),
    ("Detalle", "REVISION.md y LEEME.md en esta carpeta; datos crudos por punto en datos\\<id>\\Q…\\ (JSON, CSV de monitores e imágenes)."),
]


def main(salida: pathlib.Path = SALIDA):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    from openpyxl.utils import get_column_letter
    from openpyxl.worksheet.table import Table, TableStyleInfo
    doe, plan = doe_tabla(), json.loads((AQUI / "plan.json").read_text(encoding="utf-8"))["geometrias"]
    hojas = {k: [] for k in ("Geometrias", "Simulaciones", "Paredes", "Fronteras", "Malla_regiones", "Curvas_CFturbo")}
    for rg in rango.todas(plan=plan):
        gid = rg["id"]
        pts = consolidar.puntos(gid, rg)
        fil = [consolidar.fila(gid, rg, consolidar.geometria(rg), d) for d in pts]
        res, _ = consolidar.revisar(gid, fil, rg, plan.get(gid, {}).get("its") or 1500)
        geo = geometria(rg, doe, plan, pts, fil, res)
        hojas["Geometrias"].append(geo)
        for d, f in zip(pts, fil):
            hojas["Simulaciones"].append(simulacion(rg, geo, d, f))
            hojas["Paredes"] += list(paredes(rg, d, f))
            hojas["Fronteras"] += list(fronteras(rg, d, f))
        p0 = next((p for p in pts if p.get("celdas_region")), {})
        for reg, n in (p0.get("celdas_region") or {}).items():
            hojas["Malla_regiones"].append({"id": gid, "region": reg, "celdas": n})
        cur = json.loads((pathlib.Path(rg["carpeta"]) / "run.json").read_text(encoding="utf-8")).get("curves") or {}
        for i, q in enumerate(cur.get("Q_m3h") or []):
            hojas["Curvas_CFturbo"].append({"id": gid, "Q_m3h": q, "H_m": (cur.get("H_m") or [None] * (i + 1))[i],
                                            "eta_pct": (cur.get("eta_pct") or [None] * (i + 1))[i], "P_kW": (cur.get("P_kW") or [None] * (i + 1))[i]})
    # columnas iguales en todas las filas de cada hoja (los residuales cambian de nombre entre versiones)
    for k, filas in hojas.items():
        cab = list(dict.fromkeys(c for f in filas for c in f))
        hojas[k] = (cab, filas)
    wb = Workbook()
    ws = wb.active; ws.title = "Leeme"
    for a, b in LEEME:
        ws.append([a, b])
    ws["A1"].font = Font(bold=True, size=14)
    for c in ("A8", "A19"): ws[c].font = Font(bold=True)
    ws.column_dimensions["A"].width = 22; ws.column_dimensions["B"].width = 140
    for row in ws.iter_rows(min_row=3):
        row[1].alignment = Alignment(wrap_text=True, vertical="top")
    for nom, (cab, filas) in hojas.items():
        ws = wb.create_sheet(nom)
        ws.append(cab)
        for f in filas:
            ws.append([f.get(c) if not isinstance(f.get(c), (list, dict)) else json.dumps(f.get(c), ensure_ascii=False) for c in cab])
        for c in ws[1]:
            c.font, c.fill = Font(bold=True, color="FFFFFF"), PatternFill("solid", fgColor="2F5597")
            c.alignment = Alignment(wrap_text=True, vertical="center")
        for j, h in enumerate(cab, 1):
            ws.column_dimensions[get_column_letter(j)].width = max(9, min(26, len(h) + 2))
        ws.row_dimensions[1].height = 42
        ws.freeze_panes = "B2" if nom != "Simulaciones" else "D2"
        t = Table(displayName=nom, ref=f"A1:{get_column_letter(len(cab))}{len(filas) + 1}")
        t.tableStyleInfo = TableStyleInfo(name="TableStyleLight9", showRowStripes=True)
        ws.add_table(t)
    salida.parent.mkdir(parents=True, exist_ok=True)
    wb.save(salida)
    print(salida, {k: len(v[1]) for k, v in hojas.items()})


if __name__ == "__main__":
    main()
