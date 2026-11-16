"""Rango hidráulico de cada geometría a partir de su curva H(Q) de CFturbo (Geometrias_Prueba/_estado.json).

10 puntos lineales entre Q_MIN = 0,1 m³/h y Q_max, donde Q_max es el caudal en que la H de CFturbo cae a FRAC_H de su H
en Qn («ya bajó demasiado»; si la curva acaba antes, su último punto). El punto más cercano a Qn se reemplaza por Qn exacto.
Orden de corrida (`orden`): Qn primero, luego hacia caudal bajo y después hacia caudal alto, para que cada diseño reuse la
solución de su vecino. Flujo = caudal másico en kg/s (como el lote). Decidido por Sebastián el 2026-11-04.
    python doe/rango.py [--frac 0.25] [--json plan_rango.json]
"""
import argparse, json, pathlib

GEO = pathlib.Path(r"C:\Users\investigacion\Desktop\Geometrias_Prueba")
N, Q_MIN, FRAC_H, QMAX_CORTADA = 10, 0.1, 0.25, 1.6


def interp(x, xs, ys):
    for (x0, y0), (x1, y1) in zip(zip(xs, ys), zip(xs[1:], ys[1:])):
        if x0 <= x <= x1:
            return y0 + (y1 - y0) * (x - x0) / (x1 - x0) if x1 != x0 else y0
    return None


def rango(e: dict, frac: float = FRAC_H) -> dict | None:
    c = e.get("curves") or {}
    Q, H = c.get("Q_m3h") or [], c.get("H_m") or []
    lote = next((e["folder"] / "CFD" / "lote.json" for _ in [0] if (e["folder"] / "CFD" / "lote.json").exists()), None)
    if not lote or len(Q) < 3:
        return None
    L = json.loads(lote.read_text(encoding="utf-8"))
    qn, rho = L["Q_m3h"], L["rho"]
    hn = interp(qn, Q, H)
    qmax = next((q for q, h in zip(Q, H) if q > qn and h <= frac * hn), None)
    if qmax is None:
        # la curva de CFturbo se acaba (en 2 Qn) antes de bajar al 25 %: con su último punto CFD daba H negativa
        # (G025 a 2,0 Qn; G028 ya a 1,78 Qn). Sebastián, 2026-11-05: recortar a 1,6 Qn.
        qmax = min(Q[-1], QMAX_CORTADA * qn)
    qs = [Q_MIN + i * (qmax - Q_MIN) / (N - 1) for i in range(N)]
    i_n = min(range(N), key=lambda i: abs(qs[i] - qn))
    qs[i_n] = qn
    orden = [i_n] + list(range(i_n - 1, -1, -1)) + list(range(i_n + 1, N))
    return {"id": L["id"], "carpeta": str(e["folder"]), "sim": L["sim_destino"], "rpm": L["rpm"], "rho": rho,
            "Qn_m3h": qn, "Hn_cfturbo_m": round(hn, 2), "Qmax_m3h": round(qmax, 2), "Qmax_rel": round(qmax / qn, 2),
            "Q_m3h": [round(q, 3) for q in qs], "Flujo_kg_s": [round(q * rho / 3600, 6) for q in qs],
            "H_cfturbo_m": [round(interp(q, Q, H) or 0, 2) if q >= Q[0] else None for q in qs],
            "eta_cfturbo": [round((interp(q, Q, c.get("eta_pct") or []) or 0) / 100, 4) if q >= Q[0] and c.get("eta_pct") else None for q in qs],
            "orden": orden,
            # curva completa que predice CFturbo (para la hoja «CFturbo» del Excel)
            "curva_cft": {"Q_m3h": Q, "H_m": H, "eta": [e / 100 for e in c.get("eta_pct") or []], "P_kW": c.get("P_kW") or []}}


def aplicar_plan(r: dict, x: dict | None) -> dict:
    """Si la geometría ya corrió con otra lista de caudales (plan.json), la manda esa: G016 y G028 corrieron antes del
    tope de 1,6 Qn (2026-11-05) y sus 10 caudales llegan a 2 Qn. Rehace Flujo, orden y la referencia de CFturbo."""
    qs = (x or {}).get("Q_m3h")
    if not qs or [round(q, 3) for q in qs] == r["Q_m3h"]:
        return r
    c, rho, qn = r["curva_cft"], r["rho"], r["Qn_m3h"]
    i_n = min(range(len(qs)), key=lambda i: abs(qs[i] - qn))
    return {**r, "Q_m3h": [round(q, 3) for q in qs], "Flujo_kg_s": [round(q * rho / 3600, 6) for q in qs],
            "Qmax_m3h": round(max(qs), 2), "Qmax_rel": round(max(qs) / qn, 2),
            "H_cfturbo_m": [round(interp(q, c["Q_m3h"], c["H_m"]) or 0, 2) if q >= c["Q_m3h"][0] else None for q in qs],
            "eta_cfturbo": [round(interp(q, c["Q_m3h"], c["eta"]) or 0, 4) if q >= c["Q_m3h"][0] and c["eta"] else None for q in qs],
            "orden": (x or {}).get("orden") or [i_n] + list(range(i_n - 1, -1, -1)) + list(range(i_n + 1, len(qs)))}


def todas(frac: float = FRAC_H, plan: dict | None = None) -> list[dict]:
    """plan: geometrías de plan.json; si se da, cada una con los caudales con que corrió de verdad (aplicar_plan)."""
    est = json.loads((GEO / "_estado.json").read_text(encoding="utf-8"))
    out = []
    for gid, e in est.items():
        # la ruta de _estado.json es la del PC donde corrió CFturbo: buscar la carpeta local por el prefijo «G001_»
        d = next(GEO.glob(gid.split("_")[0] + "_*/CFD"), None)
        e = {**e, "folder": d.parent if d else None}
        if e["folder"] and (r := rango(e, frac)):
            out.append(aplicar_plan(r, (plan or {}).get(r["id"])))
    return sorted(out, key=lambda r: r["id"])


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--frac", type=float, default=FRAC_H)
    ap.add_argument("--json")
    a = ap.parse_args()
    R = todas(a.frac)
    for r in R:
        print(f'{r["id"]:<14} Qn {r["Qn_m3h"]:7.1f}  Qmax {r["Qmax_m3h"]:7.1f} ({r["Qmax_rel"]:.2f} Qn)  rpm {r["rpm"]:.0f}  '
              f'Q: {" ".join(f"{q:.1f}" for q in r["Q_m3h"])}')
    print(len(R), "geometrías")
    if a.json:
        pathlib.Path(a.json).write_text(json.dumps(R, indent=1, ensure_ascii=False), encoding="utf-8")
