"""Excel de una geometría a partir de lo que dejó `despues.java` en cada diseño (resultados.json + reports/*.csv).

Hojas: Principales (una fila por caudal: Q, H, η, M, P, balance, iteraciones, convergencia), Curvas (H-Q con la de
CFturbo, η-Q y P-Q), Reportes (todos los reportes), Residuales, Convergencia (historial de H, M y η por punto),
Imagenes (rutas de las escenas en el worker), Paredes (y+ y cortante de cada pared), Entradas-salidas, Malla (celdas y
calidad), Monitores (convergencia de cada monitor), Todo (el JSON entero, plano) y Meta. Junto al Excel, <id>_informe.txt:
todo en texto, con el estado (OK/AVISO/FALLA) de cada punto. Desde 2026-11-09 solo se guarda el .sim de Qn.
"""
import csv, json, pathlib, statistics
from openpyxl import Workbook
from openpyxl.chart import ScatterChart, Reference, Series
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

G = 9.80665


def _csv(p: pathlib.Path) -> dict[str, list]:
    """CSV de un plot → {encabezado: [valores]}; la primera columna es la iteración."""
    with open(p, encoding="utf-8", errors="replace") as f:
        filas = [r for r in csv.reader(f) if r]
    if len(filas) < 2:
        return {}
    cols = {h.strip().strip('"'): [] for h in filas[0]}
    for r in filas[1:]:
        for h, v in zip(cols, r):
            try:
                cols[h].append(float(v))
            except ValueError:
                cols[h].append(None)
    return cols


def _serie(series: dict, nombre: str):
    """Historial de un reporte: columna cuyo nombre empieza por «<nombre> Monitor» o es «<nombre>»."""
    for h, v in series.items():
        base = h.split(":")[0].strip()
        if base in (nombre, f"{nombre} Monitor") or h.split("(")[0].strip() in (nombre, f"{nombre} Monitor"):
            return v
    return None


def _conv(v: list | None, ventana: int = 200) -> dict:
    """Deriva (%/100 it.) y oscilación (% pico a pico) de las últimas `ventana` iteraciones."""
    v = [x for x in (v or []) if x is not None]
    if len(v) < 20:
        return {"deriva_pct_100it": None, "oscilacion_pct": None, "media_ventana": None}
    w = v[-ventana:]
    m = statistics.fmean(w)
    a, b = statistics.fmean(w[: len(w) // 2]), statistics.fmean(w[len(w) // 2:])
    return {"deriva_pct_100it": 100 * (b - a) / abs(m) / (len(w) / 2 / 100) if m else None,
            "oscilacion_pct": 100 * (max(w) - min(w)) / abs(m) if m else None, "media_ventana": m}


def armar(gid: str, traido: pathlib.Path, rango: dict, salida: pathlib.Path, worker: str = "") -> pathlib.Path:
    puntos = []
    for rj in sorted(traido.rglob("resultados.json")):
        r = json.loads(rj.read_text(encoding="utf-8"))
        series = {}
        for c in (rj.parent / "reports").glob("*.csv"):
            for h, v in _csv(c).items():
                series[f"{c.stem}|{h}"] = v
        r["_series"] = {h.split("|", 1)[1]: v for h, v in series.items()}
        r["_dir"] = rj.parent.name
        r["_imagenes"] = json.loads((rj.parent / "imagenes.json").read_text(encoding="utf-8")) if (rj.parent / "imagenes.json").exists() else []
        puntos.append(r)
    rho = rango.get("rho", 998.2)
    for p in puntos:   # caudal y referencia de CFturbo por el Flujo del diseño
        fl = p.get("Flujo_kg_s")
        i = min(range(len(rango["Flujo_kg_s"])), key=lambda k: abs(rango["Flujo_kg_s"][k] - (fl or 0)))
        p["_Q"], p["_Hcft"], p["_orden"] = fl * 3600 / rho if fl is not None else None, rango["H_cfturbo_m"][i], rango["orden"].index(i) + 1
        p["_etacft"] = (rango.get("eta_cfturbo") or [None] * len(rango["Q_m3h"]))[i]
    puntos.sort(key=lambda p: p["_Q"] or 0)

    wb = Workbook()
    neg = Font(bold=True)
    head = PatternFill("solid", fgColor="DDE7F5")

    def hoja(ws, cab, filas):
        ws.append(cab)
        for c in ws[1]:
            c.font, c.fill = neg, head
        for f in filas:
            ws.append(f)
        for j, h in enumerate(cab, 1):
            ws.column_dimensions[get_column_letter(j)].width = max(10, min(28, len(str(h)) + 2))
        ws.freeze_panes = "B2"

    ws = wb.active
    ws.title = "Principales"
    cab = ["Q (m³/h)", "Flujo (kg/s)", "Q/Qn", "orden de corrida", "H (m)", "H CFturbo (m)", "η", "η CFturbo", "M (N·m)", "P_eje (W)",
           "P_hid (W)", "H_Euler (m)", "η_Euler", "pt_in (Pa)", "pt_out (Pa)", "Q_in (kg/s)", "Q_out (kg/s)",
           "balance de masa (%)", "iteraciones", "celdas", "y+ medio álabes", "y+ máx álabes", "continuidad final",
           "deriva H (%/100 it)", "oscilación H (%)", "H media 200 it (m)", "convergió", "diseño"]
    filas = []
    for p in puntos:
        rep, res = p.get("reportes") or {}, p.get("residuales") or {}
        ch = _conv(_serie(p["_series"], "H"))
        cont = next((float(v) for k, v in res.items() if k.lower().startswith("continuity")), None)
        conv = None
        if ch["deriva_pct_100it"] is not None:
            conv = "sí" if abs(ch["deriva_pct_100it"]) < 0.5 and (ch["oscilacion_pct"] or 0) < 2 and (p.get("balance_masa_pct") or 0) < 1 else "no"
        filas.append([p["_Q"], p.get("Flujo_kg_s"), p["_Q"] / rango["Qn_m3h"] if p["_Q"] else None, p["_orden"],
                      rep.get("H"), p["_Hcft"], rep.get("eta"), p["_etacft"], rep.get("M"), rep.get("P_eje"), rep.get("P_hid"),
                      rep.get("H_Euler"), rep.get("eta_Euler"), rep.get("pt_in"), rep.get("pt_out"), rep.get("Q_in"),
                      rep.get("Q_out"), p.get("balance_masa_pct"), p.get("iteracion"), p.get("celdas"),
                      p.get("yplus_alabes_medio"), p.get("yplus_alabes_max"), cont, ch["deriva_pct_100it"],
                      ch["oscilacion_pct"], ch["media_ventana"], conv, p["_dir"]])
    hoja(ws, cab, filas)
    n = len(filas)

    # curva completa que predice CFturbo (todos sus puntos), para comparar con los 10 de CFD
    cc = rango.get("curva_cft") or {}
    wf = wb.create_sheet("CFturbo")
    cq, ch_, ce, cp = cc.get("Q_m3h") or [], cc.get("H_m") or [], cc.get("eta") or [], cc.get("P_kW") or []
    hoja(wf, ["Q (m³/h)", "H CFturbo (m)", "η CFturbo", "P CFturbo (W)", "Q/Qn"],
         [[q, h, ce[i] if i < len(ce) else None, cp[i] * 1000 if i < len(cp) and cp[i] is not None else None, q / rango["Qn_m3h"]]
          for i, (q, h) in enumerate(zip(cq, ch_))])
    m = len(cq)

    wc = wb.create_sheet("Curvas")
    # (título, columna CFD en Principales, columna CFturbo en la hoja CFturbo, eje)
    for k, (titulo, c_cfd, c_cft, yt) in enumerate([("H-Q", 5, 2, "H (m)"), ("η-Q", 7, 3, "η"), ("P-Q (P_eje)", 10, 4, "P (W)")]):
        ch = ScatterChart()
        ch.title, ch.x_axis.title, ch.y_axis.title, ch.style, ch.height, ch.width = titulo, "Q (m³/h)", yt, 13, 9, 16
        s = Series(Reference(ws, min_col=c_cfd, min_row=1, max_row=n + 1), Reference(ws, min_col=1, min_row=2, max_row=n + 1),
                   title="CFD")
        s.marker.symbol, s.graphicalProperties.line.noFill = "circle", True
        ch.series.append(s)
        if m:
            t = Series(Reference(wf, min_col=c_cft, min_row=2, max_row=m + 1), Reference(wf, min_col=1, min_row=2, max_row=m + 1),
                       title="CFturbo")
            t.marker.symbol, t.smooth = "none", True
            ch.series.append(t)
        wc.add_chart(ch, f"A{1 + 20 * k}")

    nombres = sorted({k for p in puntos for k in (p.get("reportes") or {})})
    hoja(wb.create_sheet("Reportes"), ["Q (m³/h)", *nombres], [[p["_Q"], *[(p.get("reportes") or {}).get(k) for k in nombres]] for p in puntos])
    rn = sorted({k for p in puntos for k in (p.get("residuales") or {})})
    hoja(wb.create_sheet("Residuales"), ["Q (m³/h)", *rn], [[p["_Q"], *[_f((p.get("residuales") or {}).get(k)) for k in rn]] for p in puntos])

    wv = wb.create_sheet("Convergencia")
    cab, cols = ["iteración"], []
    for p in puntos:
        it = next((v for h, v in p["_series"].items() if h.lower().startswith("iteration")), None)
        for nom in ("H", "M", "eta"):
            v = _serie(p["_series"], nom)
            if v:
                cab.append(f"{nom} Q={p['_Q']:.1f}")
                cols.append(dict(zip(it or range(len(v)), v)))
    its = sorted({i for c in cols for i in c})
    hoja(wv, cab, [[i, *[c.get(i) for c in cols]] for i in its])

    hoja(wb.create_sheet("Imagenes"), ["Q (m³/h)", "escena", "ruta en el worker"],
         [[p["_Q"], pathlib.PureWindowsPath(i).stem, f"{worker}:{i}"] for p in puntos for i in p["_imagenes"]])

    # desde 2026-11-09 solo queda el .sim de Qn: lo demás de cada punto vive aquí (resultados.json versión 2)
    hoja(wb.create_sheet("Paredes"), ["Q (m³/h)", "pared", "y+ medio", "y+ mín", "y+ máx", "área 30<y+<300", "área y+>300",
                                      "área y+<1", "τ media (Pa)"],
         [[p["_Q"], k, v.get("yplus_medio"), v.get("yplus_min"), v.get("yplus_max"), v.get("frac_area_30_300"),
           v.get("frac_area_gt_300"), v.get("frac_area_lt_1"), v.get("tau_media_Pa")]
          for p in puntos for k, v in (p.get("paredes") or {}).items()])
    hoja(wb.create_sheet("Entradas-salidas"), ["Q (m³/h)", "frontera", "caudal (kg/s)", "p media (Pa)", "pt masa (Pa)", "área (m²)"],
         [[p["_Q"], k, v.get("caudal_kg_s"), v.get("p_media_Pa"), v.get("pt_masa_Pa"), v.get("area_m2")]
          for p in puntos for k, v in (p.get("entradas_salidas") or {}).items()])
    regs = sorted({k for p in puntos for k in (p.get("celdas_region") or {})})
    cal = sorted({f"{k} {m}" for p in puntos for k, v in (p.get("calidad_malla") or {}).items() if isinstance(v, dict) for m in v})
    mal = sorted({k for p in puntos for k, v in (p.get("calidad_malla") or {}).items() if not isinstance(v, dict)})
    hoja(wb.create_sheet("Malla"), ["Q (m³/h)", "celdas", *[f"celdas {r}" for r in regs], *cal, *mal],
         [[p["_Q"], p.get("celdas"), *[(p.get("celdas_region") or {}).get(r) for r in regs],
           *[((p.get("calidad_malla") or {}).get(c.rsplit(" ", 1)[0]) or {}).get(c.rsplit(" ", 1)[1]) for c in cal],
           *[(p.get("calidad_malla") or {}).get(m) for m in mal]] for p in puntos])
    mon = sorted({k for p in puntos for k in (p.get("convergencia") or {})})
    hoja(wb.create_sheet("Monitores"), ["Q (m³/h)", "monitor", "iteraciones", "último", "media 100 it", "desv 100 it",
                                        "deriva 100 it (%)", "oscilación 100 it (%)"],
         [[p["_Q"], k, v.get("n"), v.get("ultimo"), v.get("media100"), v.get("desv100"), v.get("deriva100_pct"), v.get("oscil100_pct")]
          for p in puntos for k, v in sorted((p.get("convergencia") or {}).items())])
    # todo lo del JSON, plano (entradas, modelos, solvers, criterios, tipos de frontera…): nada se pierde
    hoja(wb.create_sheet("Todo"), ["Q (m³/h)", "clave", "valor"],
         [[p["_Q"], k, v] for p in puntos for k, v in plano({x: y for x, y in p.items() if not x.startswith("_")})])

    wm = wb.create_sheet("Meta")
    for k in ("id", "carpeta", "rpm", "rho", "Qn_m3h", "Hn_cfturbo_m", "Qmax_m3h", "Qmax_rel"):
        wm.append([k, rango.get(k)])
    wm.append(["worker", worker])
    wm.append(["puntos con resultado", n])
    wm.append(["criterio", "1500 iteraciones por punto, desde el punto vecino (reuso de Design Manager)"])
    wm.append(["convergió", "deriva |H| < 0,5 %/100 it, oscilación H < 2 %, balance < 1 % (últimas 200 it)"])
    salida.parent.mkdir(parents=True, exist_ok=True)
    wb.save(salida)
    informe(gid, puntos, rango, salida.with_name(f"{gid}_informe.txt"), worker)
    return salida


def chequeos(p: dict) -> list[tuple[str, str, str]]:
    """Estado de un punto: (criterio, valor, OK|AVISO|FALLA|sin dato). Criterios del CLAUDE.md («no sirve»)."""
    rep, res, cv, out = p.get("reportes") or {}, p.get("residuales") or {}, p.get("convergencia") or {}, []
    def c(nom, v, ok, aviso=None, fmt="{:.3g}"):
        out.append((nom, "—" if v is None else fmt.format(v), "sin dato" if v is None else "OK" if ok(v) else "AVISO" if aviso and aviso(v) else "FALLA"))
    rmax = max((abs(_f(v)) for v in res.values() if isinstance(_f(v), float)), default=None)
    c("residual máximo final < 1e-4", rmax, lambda v: v < 1e-4, lambda v: v < 1e-2, "{:.2e}")
    for nom in ("H", "M", "eta"):
        m = next((v for k, v in cv.items() if k.split(" Monitor")[0] == nom), None)
        d = m.get("deriva100_pct") if m else _conv(_serie(p.get("_series") or {}, nom), 100)["deriva_pct_100it"]   # versión 1: del CSV
        c(f"deriva {nom} < 0,5 %/100 it", None if d is None else abs(d), lambda v: v < 0.5, lambda v: v < 2)
    c("balance de masa < 0,5 %", p.get("balance_masa_pct"), lambda v: v < 0.5, lambda v: v < 1)
    y = p.get("yplus_alabes_medio")
    c("y+ medio álabes 30–300 (o < 5)", y, lambda v: 30 <= v <= 300 or v < 5, lambda v: v < 30)
    cm, n = p.get("calidad_malla") or {}, p.get("celdas")
    malas = sum(cm.get(k) or 0 for k in ("malas_calidad_lt_1e-2", "malas_skew_gt_85", "malas_volchange_lt_1e-3")) if cm else None
    c("celdas malas < 0,1 %", 100 * malas / n if malas is not None and n else None, lambda v: v < 0.1, lambda v: v < 1)
    c("H > 0", rep.get("H"), lambda v: v > 0)
    return out


def informe(gid: str, puntos: list, rango: dict, salida: pathlib.Path, worker: str = ""):
    """Texto plano con todo de cada punto (entradas, malla, paredes, convergencia y estado); lo que queda al borrar los .sim."""
    L = [f"INFORME DOE {gid}", f"carpeta: {rango.get('carpeta')}", f"worker: {worker}",
         f"rpm {rango.get('rpm')}  rho {rango.get('rho')} kg/m3  Qn {rango.get('Qn_m3h')} m3/h  Hn CFturbo {rango.get('Hn_cfturbo_m')} m  "
         f"Qmax {rango.get('Qmax_m3h')} m3/h ({rango.get('Qmax_rel')} Qn)", f"puntos con resultado: {len(puntos)}", ""]
    p0 = next((p for p in puntos if p.get("modelos")), puntos[0] if puntos else {})
    for k in ("modelos", "solvers", "criterios_parada", "marcos_rpm", "parametros", "fronteras_tipo"):
        if p0.get(k):
            L.append(f"[{k}] (del punto Q={p0.get('_Q', 0):.1f})")
            L += [f"  {a}: {b}" for a, b in plano(p0[k])]
    L.append("")
    L.append(f"{'Q m3/h':>9} {'Q/Qn':>5} {'H m':>8} {'H cft':>7} {'eta':>6} {'eta cft':>7} {'M N·m':>9} {'P_eje kW':>9} {'bal %':>6} {'y+ al':>6} {'estado':>7}")
    for p in puntos:
        r, ch = p.get("reportes") or {}, chequeos(p)
        est = "FALLA" if any(x[2] == "FALLA" for x in ch) else "AVISO" if any(x[2] == "AVISO" for x in ch) else "OK"
        f = lambda v, n=2, e=1: "—" if not isinstance(v, (int, float)) else f"{v * e:.{n}f}"
        L.append(f"{f(p['_Q'], 1):>9} {f(p['_Q'] / rango['Qn_m3h'] if p['_Q'] else None):>5} {f(r.get('H')):>8} {f(p['_Hcft']):>7} "
                 f"{f(r.get('eta'), 3):>6} {f(p['_etacft'], 3):>7} {f(r.get('M'), 1):>9} {f(r.get('P_eje'), 1, 1e-3):>9} "
                 f"{f(p.get('balance_masa_pct'), 3):>6} {f(p.get('yplus_alabes_medio'), 0):>6} {est:>7}")
    for p in puntos:
        L += ["", "=" * 100, f"PUNTO Q = {p['_Q']:.3f} m3/h  (Flujo {p.get('Flujo_kg_s')} kg/s, orden {p['_orden']}, carpeta {p['_dir']})",
              f"iteración {p.get('iteracion')}  celdas {p.get('celdas')}  extraído {p.get('extraido', '— (versión 1: sin malla ni paredes)')}"]
        if p.get("sim"):
            L.append(f"sim: {p['sim']}")
        L.append("[estado]")
        L += [f"  {e:<8} {n:<36} {v}" for n, v, e in chequeos(p)]
        for k in ("reportes", "entradas_salidas", "celdas_region", "calidad_malla", "paredes", "convergencia", "residuales"):
            if p.get(k):
                L.append(f"[{k}]")
                L += [f"  {a}: {b}" for a, b in plano(p[k])]
        errs = [f"  {k}: {v}" for k, v in p.items() if k.startswith("error")]
        if errs:
            L += ["[errores de extracción]", *errs]
        if p.get("_imagenes"):
            L.append("[escenas en el worker]")
            L += [f"  {worker}:{i}" for i in p["_imagenes"]]
    salida.write_text("\n".join(L) + "\n", encoding="utf-8")
    return salida


def plano(d, pre=""):
    """JSON anidado → [(«a/b/c», valor)]; las listas van como texto."""
    for k, v in d.items():
        if isinstance(v, dict):
            yield from plano(v, f"{pre}{k}/")
        else:
            yield f"{pre}{k}", ", ".join(map(str, v)) if isinstance(v, list) else v


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return x
