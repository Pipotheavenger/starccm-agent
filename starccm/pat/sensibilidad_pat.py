r"""Sensibilidad del comportamiento como turbina a Z, Δβ2 y f_D2 por familia de nq (Sebastián, 2026-11-16).

    python sensibilidad_pat.py  → PAT_PAT1_resultados\sensibilidad\ (PAT_PAT1_sensibilidad.xlsx, SENSIBILIDAD.md, *.png)

Lee la base PAT_PAT1_modo_turbina.xlsx. Por bomba:
  - BEP de turbina a 3000 rpm afinado con una parábola η(Q) por el máximo y sus dos vecinos (el barrido va a pasos de
    0,23 Qn: el máximo discreto cuantiza Q_BEP);
  - variaciones de cada variante frente a la base de su mismo nq (las bases son Z6, Δβ2 0, f_D2 1);
  - regresión sin término independiente Δy = a·(Z−6) + b·Δβ2 + c·(1−f_D2), por familia y conjunta, con error estándar.
Respuestas: η_t, Q_BEP_t/Qn, H_BEP_t/Hn, Q_emb/Qn (3000 rpm), η_b (bomba, CFD) y η_t − η_b."""
import json, math, pathlib, statistics

import numpy as np

AQUI = pathlib.Path(__file__).parent
REPO = pathlib.Path(r"C:\Users\investigacion\Desktop\Geometrias_Prueba\PAT_PAT1_resultados")
DESTINO = REPO / "sensibilidad"
FAMILIAS = {"baja (nq 15–25)": (15, 25), "media (nq 35–50)": (35, 50), "alta (nq 65–80)": (65, 80)}
VARS = [("Z−6", lambda g: g["Z"] - 6), ("Δβ2 (°)", lambda g: g["dBeta2_deg"]), ("1−f_D2", lambda g: 1 - g["f_D2"])]
RESP = [("eta_t", "η_t (turbina, BEP 3000 rpm)"), ("Q_t_Qn", "Q_BEP_t / Qn"), ("H_t_Hn", "H_BEP_t / Hn bomba"),
        ("Q_emb_Qn", "Q_emb / Qn (3000 rpm)"), ("eta_b", "η_b (bomba, CFD)"), ("eta_t_menos_eta_b", "η_t − η_b")]


def hoja(wb, nom):
    rows = list(wb[nom].iter_rows(values_only=True))
    return [dict(zip(rows[0], r)) for r in rows[1:]]


def bep_afinado(sims):
    """Parábola η(Q) por el máximo de turbina a 3000 rpm y sus vecinos; si el máximo está en el borde, el discreto."""
    t = sorted((s for s in sims if s["serie"] == "barrido" and s["rpm"] == 3000 and s["regimen"] == "turbina"), key=lambda s: s["Q_m3h"])
    if not t:
        return None
    i = max(range(len(t)), key=lambda k: t[k]["eta"])
    if 0 < i < len(t) - 1:
        q = [t[k]["Q_m3h"] for k in (i - 1, i, i + 1)]
        ce = np.polyfit(q, [t[k]["eta"] for k in (i - 1, i, i + 1)], 2)
        ch = np.polyfit(q, [t[k]["H_m"] for k in (i - 1, i, i + 1)], 2)
        if ce[0] < 0:
            qb = -ce[1] / (2 * ce[0])
            return {"Q": qb, "eta": float(np.polyval(ce, qb)), "H": float(np.polyval(ch, qb)), "borde": False}
    return {"Q": t[i]["Q_m3h"], "eta": t[i]["eta"], "H": t[i]["H_m"], "borde": True}


def regresion(filas, resp):
    X = np.array([[f(g) for _, f in VARS] for g in filas], float)
    y = np.array([g["d_" + resp] for g in filas], float)
    ok = ~np.isnan(y)
    X, y = X[ok], y[ok]
    n, p = X.shape
    if n <= p:
        return None
    b, *_ = np.linalg.lstsq(X, y, rcond=None)
    r = y - X @ b
    s2 = r @ r / (n - p)
    se = np.sqrt(np.diag(s2 * np.linalg.pinv(X.T @ X)))
    r2 = 1 - (r @ r) / (y @ y) if y @ y > 0 else float("nan")
    sd = X.std(axis=0)
    return {"n": n, "R2": r2, "coef": b, "se": se, "efecto_1sd": b * sd, "rms_resto": math.sqrt(r @ r / n)}


def main():
    import openpyxl
    wb = openpyxl.load_workbook(REPO / "PAT_PAT1_modo_turbina.xlsx", read_only=True, data_only=True)
    G = {g["id"]: g for g in hoja(wb, "Geometrias")}
    S = hoja(wb, "Simulaciones")
    filas = []
    for gid, g in G.items():
        b = bep_afinado([s for s in S if s["id"] == gid])
        qn, hn = g["CFD_Qn_m3h"], g["CFD_H_Qn_m"]
        f = {"id": gid, "tipo": g["tipo"], "nq": g["nq"], "Z": g["Z"], "dBeta2_deg": g["dBeta2_deg"] or 0.0, "f_D2": g["f_D2"] or 1.0,
             "eta_t": b["eta"] if b else None, "Q_t_Qn": b["Q"] / qn if b else None, "H_t_Hn": b["H"] / hn if b and hn else None,
             "BEP_en_borde": b["borde"] if b else None, "Q_emb_Qn": g["PAT_Q_emb_3000_Qn"], "eta_b": g["CFD_eta_max"]}
        f["eta_t_menos_eta_b"] = f["eta_t"] - f["eta_b"] if f["eta_t"] is not None and f["eta_b"] is not None else None
        filas.append(f)
    bases = {f["nq"]: f for f in filas if f["tipo"] == "base"}
    for f in filas:
        bz = bases.get(f["nq"])
        f["base"] = bz["id"] if bz else None
        for k, _ in RESP:
            f["d_" + k] = (f[k] - bz[k]) if bz and f[k] is not None and bz[k] is not None else float("nan")
    var = [f for f in filas if f["tipo"] == "variante" and f["base"] and f["id"][:4] != "G001"]
    efectos = []
    for fam, (a, z) in list(FAMILIAS.items()) + [("todas", (0, 999))]:
        sub = [f for f in var if a <= f["nq"] <= z]
        for k, nom in RESP:
            r = regresion(sub, k)
            if not r:
                continue
            fila = {"familia": fam, "respuesta": nom, "n": r["n"], "R2": r["R2"], "rms_resto": r["rms_resto"]}
            for j, (vn, _) in enumerate(VARS):
                fila[f"{vn} coef"] = r["coef"][j]; fila[f"{vn} ±se"] = r["se"][j]
                fila[f"{vn} signif"] = abs(r["coef"][j]) > 2 * r["se"][j]
                fila[f"{vn} efecto 1σ"] = r["efecto_1sd"][j]
            efectos.append(fila)
    DESTINO.mkdir(parents=True, exist_ok=True)
    escribir(filas, efectos)
    graficas(filas)
    resumen(filas, efectos)
    print(f"{len(filas)} bombas, {len(var)} variantes, {len(efectos)} regresiones → {DESTINO}")


def escribir(filas, efectos):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    wb = Workbook(); ws = wb.active; ws.title = "Leeme"
    for l in __doc__.strip().splitlines():
        ws.append([l])
    ws.append([]); ws.append(["Efectos: coef = cambio de la respuesta por unidad de variable (Z en álabes, Δβ2 en °, 1−f_D2 en fracción de D2);"])
    ws.append(["signif = |coef| > 2·se; efecto 1σ = coef × desviación de la variable en esa familia (comparable entre variables)."])
    ws.column_dimensions["A"].width = 130
    for nom, datos in (("Bombas", filas), ("Efectos", efectos)):
        ws = wb.create_sheet(nom)
        cab = list(dict.fromkeys(c for f in datos for c in f))
        ws.append(cab)
        for f in datos:
            ws.append([None if isinstance(v := f.get(c), float) and math.isnan(v) else v for c in cab])
        for c in ws[1]:
            c.font, c.fill = Font(bold=True, color="FFFFFF"), PatternFill("solid", fgColor="2F5597")
            c.alignment = Alignment(wrap_text=True)
        ws.freeze_panes = "B2"
    wb.save(DESTINO / "PAT_PAT1_sensibilidad.xlsx")


def graficas(filas):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    b = sorted((f for f in filas if f["tipo"] == "base"), key=lambda f: f["nq"])
    v = [f for f in filas if f["tipo"] == "variante"]
    fig, ax = plt.subplots(1, 3, figsize=(15, 4.4))
    for a, (k, nom) in zip(ax, [("eta_t", "η_t (turbina)"), ("Q_t_Qn", "Q_BEP_t / Qn"), ("Q_emb_Qn", "Q_emb / Qn a 3000 rpm")]):
        a.plot([f["nq"] for f in b if f[k]], [f[k] for f in b if f[k]], "-o", color="#2F5597", label="bases (Z6, Δβ2 0, f_D2 1)")
        sc = a.scatter([f["nq"] for f in v if f[k]], [f[k] for f in v if f[k]], c=[f["dBeta2_deg"] for f in v if f[k]], cmap="coolwarm",
                       vmin=-7, vmax=7, s=[(1.05 - f["f_D2"]) * 600 for f in v if f[k]], edgecolors="k", label="variantes (color Δβ2, tamaño 1−f_D2)")
        a.set_xlabel("nq"); a.set_title(nom); a.grid(alpha=.3)
    if ax[2].get_ylim()[1] > 1.2: ax[2].set_ylim(0.2, 1.0)
    fig.colorbar(sc, ax=ax, label="Δβ2 (°)", shrink=.8); ax[0].legend(fontsize=7, loc="lower center")
    fig.savefig(DESTINO / "tendencias_nq.png", dpi=130, bbox_inches="tight"); plt.close(fig)
    fig, ax = plt.subplots(1, 3, figsize=(15, 4.2), sharey=True)
    col = {"baja (nq 15–25)": "#C0392B", "media (nq 35–50)": "#2E86C1", "alta (nq 65–80)": "#28B463"}
    for a, (vn, fx) in zip(ax, VARS):
        for fam, (lo, hi) in FAMILIAS.items():
            s = [f for f in v if lo <= f["nq"] <= hi and not math.isnan(f["d_eta_t"])]
            a.scatter([fx(f) for f in s], [f["d_eta_t"] for f in s], color=col[fam], label=fam, s=40)
        a.axhline(0, color="k", lw=.6); a.set_xlabel(vn); a.grid(alpha=.3)
    ax[0].set_ylabel("Δη_t frente a la base del mismo nq"); ax[0].legend(fontsize=8)
    fig.savefig(DESTINO / "delta_eta_t.png", dpi=130, bbox_inches="tight"); plt.close(fig)


def resumen(filas, efectos):
    L = ["# Sensibilidad PAT1 en modo turbina", "", "Variantes frente a la base de su nq; regresión Δy = a·(Z−6) + b·Δβ2 + c·(1−f_D2).",
         "Efecto 1σ = cambio típico que produce cada variable en esa familia. ✔ = significativo (|coef| > 2·se).", ""]
    for fam in list(FAMILIAS) + ["todas"]:
        L += [f"## {fam}", "", "| respuesta | n | R² | Z−6 (1σ) | Δβ2 (1σ) | 1−f_D2 (1σ) |", "|---|---|---|---|---|---|"]
        for e in (e for e in efectos if e["familia"] == fam):
            c = lambda v: f"{e[v + ' efecto 1σ']:+.3f}{' ✔' if e[v + ' signif'] else ''}"
            L.append(f"| {e['respuesta']} | {e['n']} | {e['R2']:.2f} | {c('Z−6')} | {c('Δβ2 (°)')} | {c('1−f_D2')} |")
        L.append("")
    b = sorted((f for f in filas if f["tipo"] == "base"), key=lambda f: f["nq"])
    L += ["## Bases frente a nq", "", "| id | nq | η_t | Q_t/Qn | H_t/Hn | Q_emb/Qn | η_b |", "|---|---|---|---|---|---|---|"]
    fmt = lambda x: "—" if x is None else f"{x:.3f}"
    L += [f"| {f['id']} | {f['nq']:.0f} | {fmt(f['eta_t'])} | {fmt(f['Q_t_Qn'])} | {fmt(f['H_t_Hn'])} | {fmt(f['Q_emb_Qn'])} | {fmt(f['eta_b'])} |" for f in b]
    (DESTINO / "SENSIBILIDAD.md").write_text("\n".join(L), encoding="utf-8")


if __name__ == "__main__":
    main()
