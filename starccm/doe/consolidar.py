r"""Junta el DOE en un solo sitio y lo revisa (2026-11-10, Sebastián: «repositorio unificado» y «que todas tengan sentido»).

    python consolidar.py [destino]   (por defecto Desktop\Geometrias_Prueba\DOE_PAT1_resultados)

Deja en el destino:
  DOE_PAT1_puntos.csv / .xlsx   una fila por punto (47 bombas × 10): entradas de la geometría, salidas, calidad
  DOE_PAT1_bombas.xlsx          una fila por bomba: BEP, H en Qn frente a CFturbo, avisos
  REVISION.md                   lo raro que encontró, bomba por bomba
  datos\<id>\Q…\                resultados.json y reports\*.csv de cada punto (copia de _traido)
  excels\                       el <id>_barrido.xlsx y <id>_informe.txt de cada bomba
  datos\<id>\Q…\images\         escenas PNG del punto (python consolidar.py imagenes; ~1 GB, una vez)
main() no toca los workers; las imágenes se bajan aparte con bajar_imagenes()."""
import csv, json, math, pathlib, re, shutil, statistics, sys

import excel, rango

AQUI = pathlib.Path(__file__).parent
DESTINO = pathlib.Path(r"C:\Users\investigacion\Desktop\Geometrias_Prueba\DOE_PAT1_resultados")


def geometria(r: dict) -> dict:
    """nq, tipo y modificación de la variante desde el nombre de la carpeta (G003_nq15_variante_Z6_dBeta2-4.3deg_fD2-0.960_…)."""
    n = pathlib.Path(r["carpeta"]).name
    m = lambda pat: (re.search(pat, n) or [None, None])[1]
    return {"nq": float(m(r"_nq(\d+)")), "tipo": "variante" if "_variante_" in n else "base", "Z": m(r"_Z(\d+)_"),
            "dBeta2_deg": m(r"dBeta2([+-][\d.]+)deg"), "fD2": m(r"fD2-([\d.]+)"),
            "Qn_diseno_m3h": float(m(r"_Q([\d.]+)m3h")), "Hn_diseno_m": float(m(r"_H([\d.]+)m_"))}


def puntos(gid: str, rg: dict) -> list[dict]:
    out = []
    for rj in sorted((AQUI / "_traido" / gid).glob("Q*/resultados.json")):
        d = json.loads(rj.read_text(encoding="utf-8"))
        series = {}
        for c in (rj.parent / "reports").glob("*.csv"):
            series.update(excel._csv(c))
        d["_series"], d["_dir"] = series, rj.parent
        fl = d.get("Flujo_kg_s")
        i = min(range(len(rg["Flujo_kg_s"])), key=lambda k: abs(rg["Flujo_kg_s"][k] - (fl or 0)))
        d["_Q"], d["_i"] = fl * 3600 / rg["rho"], i
        out.append(d)
    return sorted(out, key=lambda d: d["_Q"])


def fila(gid: str, rg: dict, geo: dict, d: dict) -> dict:
    r = d.get("reportes") or {}
    g = lambda k: r.get(k)
    conv = d.get("convergencia") or {}
    def deriva(nom):
        m = next((v for k, v in conv.items() if k.split(" ")[0] == nom), None)
        if m: return abs(m["deriva100_pct"]) if m.get("deriva100_pct") is not None else None, m.get("oscil100_pct")
        c = excel._conv(excel._serie(d["_series"], nom), 100)
        return abs(c["deriva_pct_100it"]) if c["deriva_pct_100it"] is not None else None, c.get("oscilacion_pct")
    res = d.get("residuales") or {}
    if not res:   # versión 1: última fila del CSV de residuales
        res = {k: v[-1] for k, v in d["_series"].items() if "Residual" in k and v}
    qn_kg = rg["Qn_m3h"] * rg["rho"] / 3600
    qi, qo = g("Q_in"), g("Q_out")
    cal = d.get("calidad_malla") or {}
    est = {c.split(" <")[0]: e for c, _, e in excel.chequeos(d)}
    H, Hc = g("H"), rg["H_cfturbo_m"][d["_i"]]
    return {
        "id": gid, **geo, "rpm": abs(rg["rpm"]), "rho": rg["rho"], "Qn_m3h": rg["Qn_m3h"], "Hn_cfturbo_m": rg["Hn_cfturbo_m"],
        "punto": rg["orden"].index(d["_i"]) + 1, "Q_m3h": round(d["_Q"], 3), "Q_Qn": round(d["_Q"] / rg["Qn_m3h"], 4),
        "H_m": H, "H_cfturbo_m": Hc, "H_H_cfturbo": H / Hc if H is not None and Hc else None,
        "eta": g("eta"), "eta_cfturbo": rg["eta_cfturbo"][d["_i"]] if rg.get("eta_cfturbo") else None,
        "M_Nm": g("M"), "P_eje_W": g("P_eje"), "P_hid_W": g("P_hid"), "H_Euler_m": g("H_Euler"), "eta_Euler": g("eta_Euler"),
        "U2_m_s": g("U2"), "Vu2_m_s": g("Vu2"), "Vu1_m_s": g("Vu1"), "factor_deslizamiento": g("factor_deslizamiento"),
        "pt_in_Pa": g("pt_in"), "pt_out_Pa": g("pt_out"), "Q_in_kg_s": qi, "Q_out_kg_s": qo,
        "balance_pct_punto": d.get("balance_masa_pct"),
        "balance_pct_Qn": abs(qi + qo) / qn_kg * 100 if qi is not None and qo is not None else None,
        "iteraciones": d.get("iteracion"), "celdas": d.get("celdas"),
        "yplus_alabes_medio": d.get("yplus_alabes_medio"), "yplus_alabes_max": g("yplus_max_alabes") or d.get("yplus_alabes_max"),
        "residual_max": max(res.values()) if res else None, "continuidad": res.get("Continuity: Residual") or res.get("Continuity"),
        "deriva_H_pct": deriva("H")[0], "oscil_H_pct": deriva("H")[1], "deriva_M_pct": deriva("M")[0],
        "celdas_calidad_lt_1e-2": cal.get("malas_calidad_lt_1e-2"), "celdas_skew_gt_85": cal.get("malas_skew_gt_85"),
        "datos": "completos" if d.get("version_json") else "basicos (sin y+ por pared ni calidad de malla)",
        "chequeo_residual": est.get("residual máximo final"), "chequeo_deriva_H": est.get("deriva H"),
        "carpeta_datos": f"datos/{gid}/{d['_dir'].name}",
    }


def revisar(gid: str, filas: list[dict], rg: dict, its: int = 1500) -> tuple[dict, list[str]]:
    """Resumen de la bomba y lista de cosas raras (física o numérica)."""
    av = []
    ok = [f for f in filas if f["H_m"] is not None]
    bep = max(ok, key=lambda f: f["eta"] or -9)
    qn = min(ok, key=lambda f: abs(f["Q_Qn"] - 1))
    cero = ok[0]
    if len(filas) != 10: av.append(f"{len(filas)} puntos (se esperaban 10)")
    if len({f["celdas"] for f in filas}) > 1: av.append(f"celdas distintas entre puntos: {sorted({f['celdas'] for f in filas})}")
    if any(f["iteraciones"] != its for f in filas): av.append(f"iteraciones ≠ {its}: " + ", ".join(f"{f['Q_m3h']}→{f['iteraciones']}" for f in filas if f["iteraciones"] != 1500))
    if bep["eta"] > 0.93: av.append(f"η máx {bep['eta']:.3f}: demasiado alta para esta bomba")
    if not 0.6 <= bep["Q_Qn"] <= 1.3: av.append(f"BEP muy lejos de Qn: Q/Qn = {bep['Q_Qn']:.2f}")
    if qn["H_H_cfturbo"] is not None and not 0.8 <= qn["H_H_cfturbo"] <= 1.25:
        av.append(f"H en Qn = {qn['H_m']:.1f} m frente a {qn['H_cfturbo_m']:.1f} m de CFturbo ({qn['H_H_cfturbo']:.2f}×)")
    if qn["eta"] is not None and qn["eta_cfturbo"] and abs(qn["eta"] - qn["eta_cfturbo"]) > 0.15:
        av.append(f"η en Qn {qn['eta']:.3f} frente a {qn['eta_cfturbo']:.3f} de CFturbo")
    # forma de la curva: por encima del BEP H tiene que bajar siempre
    alto = [f for f in ok if f["Q_m3h"] >= bep["Q_m3h"]]
    if any(b["H_m"] > a["H_m"] * 1.005 for a, b in zip(alto, alto[1:])): av.append("H sube por encima del BEP")
    sube = [f"{a['Q_m3h']:.0f}→{b['Q_m3h']:.0f}" for a, b in zip(ok, ok[1:]) if b["Q_m3h"] < bep["Q_m3h"] and b["H_m"] > a["H_m"] * 1.08]
    if sube: av.append("H sube >8 % entre puntos bajo el BEP (inestabilidad o punto mal convergido): " + ", ".join(sube))
    if any(f["M_Nm"] is not None and f["M_Nm"] <= 0 for f in ok): av.append("momento ≤ 0 en algún punto")
    pe = [f["P_eje_W"] for f in ok]
    if any(abs(abs(f["P_eje_W"]) - abs(f["M_Nm"]) * abs(rg["rpm"]) * math.pi / 30) > 0.01 * abs(f["P_eje_W"]) for f in ok if f["P_eje_W"] and f["M_Nm"]):   # signo: P_eje = −M·ω con rpm < 0
        av.append("P_eje ≠ M·ω")
    # a carga parcial (Q/Qn < 0,7) la recirculación en la salida del rotor falsea Vu2: η_Euler > 1 ahí no es un error del caso
    if any(f["eta_Euler"] is not None and f["eta_Euler"] > 1.0 and f["Q_Qn"] >= 0.7 for f in ok): av.append("η_Euler > 1 cerca de Qn (H > H_Euler)")
    if any(f["eta"] is not None and f["eta"] > 1 for f in ok): av.append("η > 1")
    for f in ok:
        if f["Q_Qn"] > 0.2 and f["balance_pct_Qn"] is not None and f["balance_pct_Qn"] > 0.5:
            av.append(f"balance de masa {f['balance_pct_Qn']:.2f} % de Qn en {f['Q_m3h']:.0f} m³/h")
        if 0.5 <= f["Q_Qn"] <= 1.3 and f["deriva_H_pct"] is not None and f["deriva_H_pct"] > 2:
            av.append(f"H sin estabilizar en {f['Q_m3h']:.0f} m³/h (deriva {f['deriva_H_pct']:.1f} %/100 it)")
        if 0.5 <= f["Q_Qn"] <= 1.3 and f["residual_max"] and f["residual_max"] > 0.1:   # lo normal del DOE: ~5e-3
            av.append(f"residual alto {f['residual_max']:.1e} en {f['Q_m3h']:.0f} m³/h")
    neg = [f for f in ok if f["H_m"] < 0]
    if neg and neg[0]["Q_Qn"] < 1.2: av.append(f"H negativa ya en Q/Qn = {neg[0]['Q_Qn']:.2f}")
    basicos = sum(f["datos"] != "completos" for f in filas)
    if basicos: av.append(f"{basicos} punto(s) solo con datos básicos (sus .sim ya no existen)")
    res = {"id": gid, "nq": filas[0]["nq"], "tipo": filas[0]["tipo"], "Z": filas[0]["Z"], "dBeta2_deg": filas[0]["dBeta2_deg"],
           "fD2": filas[0]["fD2"], "Qn_m3h": rg["Qn_m3h"], "Hn_cfturbo_m": rg["Hn_cfturbo_m"], "Hn_diseno_m": filas[0]["Hn_diseno_m"],
           "H_Qn_m": qn["H_m"], "H_Qn_H_cfturbo": qn["H_H_cfturbo"], "eta_Qn": qn["eta"], "eta_Qn_cfturbo": qn["eta_cfturbo"],
           "Q_BEP_m3h": bep["Q_m3h"], "Q_BEP_Qn": bep["Q_Qn"], "eta_max": bep["eta"], "H_BEP_m": bep["H_m"],
           "H_cierre_m": cero["H_m"], "H_cierre_H_Qn": cero["H_m"] / qn["H_m"] if qn["H_m"] else None,
           "P_eje_Qn_kW": qn["P_eje_W"] / 1000 if qn["P_eje_W"] else None, "celdas": filas[0]["celdas"],
           "yplus_alabes_Qn": qn["yplus_alabes_medio"], "puntos_datos_basicos": basicos, "avisos": len(av), "detalle": " | ".join(av)}
    return res, av


def escribir_xlsx(ruta: pathlib.Path, hojas: dict[str, list[dict]]):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill
    wb = Workbook(); wb.remove(wb.active)
    for nom, filas in hojas.items():
        ws = wb.create_sheet(nom)
        cab = list(filas[0])
        ws.append(cab)
        for c in ws[1]: c.font, c.fill = Font(bold=True), PatternFill("solid", fgColor="DDE7F5")
        for f in filas: ws.append([f.get(k) for k in cab])
        ws.freeze_panes = "C2"
    wb.save(ruta)


def main(destino: pathlib.Path = DESTINO):
    destino.mkdir(parents=True, exist_ok=True)
    todas, bombas, texto = [], [], []
    plan = json.loads((AQUI / "plan.json").read_text(encoding="utf-8"))["geometrias"]
    for rg in rango.todas(plan=plan):
        gid, geo = rg["id"], geometria(rg)
        filas = [fila(gid, rg, geo, d) for d in puntos(gid, rg)]
        res, av = revisar(gid, filas, rg, plan.get(gid, {}).get("its") or 1500)
        todas += filas; bombas.append(res)
        texto.append(f"## {gid}  ({res['tipo']}, nq {res['nq']:.0f}" + (f", Z{res['Z']}, ΔBeta2 {res['dBeta2_deg']}°, fD2 {res['fD2']}" if res["tipo"] == "variante" else "") + ")")
        texto.append(f"H en Qn {res['H_Qn_m']:.1f} m (CFturbo {rg['Hn_cfturbo_m']:.1f}) · η máx {res['eta_max']:.3f} en Q/Qn {res['Q_BEP_Qn']:.2f}")
        texto += [f"- {a}" for a in av] or ["- sin avisos"]
        texto.append("")
        src = AQUI / "_traido" / gid
        if src.exists(): shutil.copytree(src, destino / "datos" / gid, dirs_exist_ok=True)
        e = plan.get(gid, {})
        for f in (pathlib.Path(e.get("carpeta", rg["carpeta"])) / "DOE").glob(f"{gid}_*"):
            (destino / "excels").mkdir(exist_ok=True); shutil.copy2(f, destino / "excels" / f.name)
    with open(destino / "DOE_PAT1_puntos.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(todas[0]), delimiter=";"); w.writeheader(); w.writerows(todas)
    escribir_xlsx(destino / "DOE_PAT1_puntos.xlsx", {"Puntos": todas})
    escribir_xlsx(destino / "DOE_PAT1_bombas.xlsx", {"Bombas": bombas})
    (destino / "REVISION.md").write_text("# Revisión del DOE PAT1\n\n" + "\n".join(texto), encoding="utf-8")
    print(f"{len(bombas)} bombas, {len(todas)} puntos -> {destino}")
    return bombas, todas


def bajar_imagenes(destino: pathlib.Path = DESTINO):
    """Escenas de cada punto (puntos/Q…/images/*.png, ~17 MB por bomba) → datos/<id>/Q…/images/, un worker por hilo."""
    import concurrent.futures, tempfile, doe
    plan = doe.plan()["geometrias"]
    def una(gid):
        e = plan[gid]
        if all((q / "images").exists() for q in (destino / "datos" / gid).glob("Q*")): return gid, "ya estaba"
        with tempfile.TemporaryDirectory() as t:
            doe.scp(t, e["worker"], (e["dir"] + "/puntos").replace("\\", "/"), bajar=True)
            n = 0
            for img in pathlib.Path(t).glob("puntos/Q*/images"):
                dst = destino / "datos" / gid / img.parent.name / "images"
                shutil.copytree(img, dst, dirs_exist_ok=True); n += len(list(dst.glob("*.png")))
        return gid, n
    por_worker = {}
    for gid, e in plan.items(): por_worker.setdefault(e["worker"], []).append(gid)
    with concurrent.futures.ThreadPoolExecutor(len(por_worker)) as ex:
        for r in ex.map(lambda gs: [una(g) for g in gs], por_worker.values()):
            for gid, n in r: print(gid, n, flush=True)


if __name__ == "__main__":
    if sys.argv[1:2] == ["imagenes"]:
        bajar_imagenes()
    else:
        main(pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else DESTINO)
