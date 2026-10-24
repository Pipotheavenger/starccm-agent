"""Informe PDF de un caso: todo lo de la simulación (detalle del .sim, convergencia, escenas, 3D) en un HTML
que Edge/Chrome sin ventana imprime a PDF. Sin dependencias: ni markdown ni librerías de PDF.

detalle = salida de recipes/informe-detalle.java: líneas «D\\tsección\\tobjeto\\tpropiedad\\tvalor».
"""
from __future__ import annotations

import base64
import csv
import html
import math
import os
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

SECCIONES = [  # (clave del detalle, título); el orden es el del informe
    ("general", "Simulación"), ("geometria", "Geometría: partes y superficies"), ("regiones", "Regiones"),
    ("fronteras", "Fronteras y condiciones de contorno"), ("interfaces", "Interfaces"),
    ("fisica", "Física: continuos y modelos"), ("materiales", "Materiales"), ("referencia", "Valores de referencia"),
    ("iniciales", "Condiciones iniciales"), ("marcos", "Marcos de referencia (rotación)"), ("malla", "Malla"),
    ("solver", "Solvers"), ("parada", "Criterios de parada"), ("reportes", "Reportes"), ("monitores", "Monitores"),
    ("funciones", "Funciones de campo de usuario"), ("derivadas", "Partes derivadas"), ("escenas", "Escenas del .sim"),
    ("graficos", "Gráficos del .sim"),
]
GRUPOS = [  # capítulos del informe -> secciones del detalle
    ("Geometría", ["geometria"]), ("Regiones, fronteras e interfaces", ["regiones", "fronteras", "interfaces"]),
    ("Física", ["fisica", "materiales", "referencia", "iniciales", "marcos"]), ("Malla", ["malla"]),
    ("Solver y criterios de parada", ["solver", "parada"]),
    ("Reportes, monitores y funciones", ["reportes", "monitores", "funciones"]),
    ("Objetos de postproceso del .sim", ["derivadas", "escenas", "graficos"]),
]
TITULO = dict(SECCIONES)


def parse_detalle(stdout: str) -> list[list[str]]:
    rows = []
    for ln in stdout.splitlines():
        f = ln.split("\t")
        if f[0] == "D" and len(f) >= 5:
            rows.append([f[1], f[2], f[3], "\t".join(f[4:])])
    return rows


e = html.escape


def _md_inline(s: str) -> str:
    s = e(s)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", s)
    return re.sub(r"(?<![*\w])\*([^*]+)\*(?!\*)", r"<i>\1</i>", s)


def md_to_html(md: str) -> str:
    """Markdown mínimo de los RESUMEN.md: títulos, tablas, listas, párrafos, código en línea, negrita."""
    out, para, lines = [], [], md.splitlines()
    i = 0

    def flush():
        if para:
            out.append("<p>" + _md_inline(" ".join(para)) + "</p>")
            para.clear()
    while i < len(lines):
        ln = lines[i].rstrip()
        if not ln.strip():
            flush()
        elif m := re.match(r"^(#{1,6})\s+(.*)", ln):
            flush()
            lvl = min(len(m.group(1)) + 2, 6)  # el RESUMEN va dentro de un capítulo h2
            out.append(f"<h{lvl}>{_md_inline(m.group(2))}</h{lvl}>")
        elif ln.lstrip().startswith("|") and i + 1 < len(lines) and re.match(r"^\s*\|?\s*:?-{2,}", lines[i + 1]):
            flush()
            cells = lambda s: [c.strip() for c in s.strip().strip("|").split("|")]  # noqa: E731
            hdr = cells(ln)
            i += 2
            body = []
            while i < len(lines) and lines[i].lstrip().startswith("|"):
                body.append(cells(lines[i]))
                i += 1
            out.append("<table><thead><tr>" + "".join(f"<th>{_md_inline(c)}</th>" for c in hdr) + "</tr></thead><tbody>"
                       + "".join("<tr>" + "".join(f"<td>{_md_inline(c)}</td>" for c in r) + "</tr>" for r in body) + "</tbody></table>")
            continue
        elif re.match(r"^\s*([-*]|\d+\.)\s+", ln):
            flush()
            items = []
            while i < len(lines) and re.match(r"^\s*([-*]|\d+\.)\s+", lines[i]):
                items.append(re.sub(r"^\s*([-*]|\d+\.)\s+", "", lines[i]))
                i += 1
            out.append("<ul>" + "".join(f"<li>{_md_inline(x)}</li>" for x in items) + "</ul>")
            continue
        else:
            para.append(ln.strip())
        i += 1
    flush()
    return "\n".join(out)


def _fmt(v) -> str:
    if v is None:
        return "–"
    if isinstance(v, float):
        if v != 0 and (abs(v) < 1e-3 or abs(v) >= 1e6):
            return f"{v:.3e}".replace(".", ",")
        return f"{v:.6g}".replace(".", ",")
    return str(v)


def _num(s):
    try:
        v = float(s)
        return v if math.isfinite(v) else None
    except (TypeError, ValueError):
        return None


def read_conv(case_dir: Path) -> tuple[list[str], list[list]]:
    f = case_dir / "reports" / "convergencia.csv"
    if not f.is_file():
        return [], []
    with open(f, encoding="utf-8-sig", errors="replace", newline="") as fh:
        rows = [r for r in csv.reader(fh) if r and any(x.strip() for x in r)]
    if not rows:
        return [], []
    return [c.strip() for c in rows[0]], [[_num(x) for x in r] for r in rows[1:]]


def svg_chart(title: str, xs: list, series: dict[str, list], log: bool = False, w: int = 720, h: int = 260) -> str:
    """Curva(s) frente a la iteración en SVG (ejes, rejilla, leyenda); log = eje Y logarítmico (residuales)."""
    pts = {k: [(x, y) for x, y in zip(xs, ys) if x is not None and y is not None and (not log or y > 0)] for k, ys in series.items()}
    pts = {k: v for k, v in pts.items() if v}
    if not pts:
        return ""
    tf = (lambda y: math.log10(y)) if log else (lambda y: y)
    allx = [p[0] for v in pts.values() for p in v]
    ally = [tf(p[1]) for v in pts.values() for p in v]
    x0, x1 = min(allx), max(allx)
    y0, y1 = min(ally), max(ally)
    if log:
        y0, y1 = math.floor(y0), math.ceil(y1)
    if x1 == x0:
        x1 = x0 + 1
    if y1 == y0:
        y0, y1 = y0 - 1, y1 + 1
    pad = (y1 - y0) * (0 if log else 0.08)
    y0, y1 = y0 - pad, y1 + pad
    L, R, T, B = 64, 16, 28, 34
    X = lambda x: L + (x - x0) / (x1 - x0) * (w - L - R)  # noqa: E731
    Y = lambda y: T + (1 - (y - y0) / (y1 - y0)) * (h - T - B)  # noqa: E731
    cols = ["#1f5fbf", "#d0452f", "#2a9d5b", "#a05ac8", "#c98a00"]
    g = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" class="chart"><text x="{L}" y="17" class="ct">{e(title)}</text>']
    ticks = range(int(y0), int(y1) + 1) if log else [y0 + (y1 - y0) * i / 4 for i in range(5)]
    for t in ticks:
        lab = f"1e{t}" if log else f"{t:.4g}".replace(".", ",")
        g.append(f'<line x1="{L}" x2="{w - R}" y1="{Y(t):.1f}" y2="{Y(t):.1f}" class="grid"/><text x="{L - 6}" y="{Y(t) + 4:.1f}" class="tk" text-anchor="end">{lab}</text>')
    for i in range(5):
        xv = x0 + (x1 - x0) * i / 4
        g.append(f'<text x="{X(xv):.1f}" y="{h - 14}" class="tk" text-anchor="middle">{int(round(xv))}</text>')
    g.append(f'<text x="{w - R}" y="{h - 2}" class="tk" text-anchor="end">iteración</text>')
    g.append(f'<rect x="{L}" y="{T}" width="{w - L - R}" height="{h - T - B}" class="frame"/>')
    lx = L + 8
    for c, (k, v) in zip(cols, pts.items()):
        d = " ".join(f"{X(x):.1f},{Y(tf(y)):.1f}" for x, y in v)
        g.append(f'<polyline points="{d}" fill="none" stroke="{c}" stroke-width="1.8"/>')
        if len(v) <= 60:
            g += [f'<circle cx="{X(x):.1f}" cy="{Y(tf(y)):.1f}" r="2.2" fill="{c}"/>' for x, y in v]
        g.append(f'<text x="{lx}" y="{T + 14}" class="lg" fill="{c}">■ {e(k)}</text>')
        lx += 12 + 7 * len(k)
    g.append("</svg>")
    return "".join(g)


def _img(p: Path) -> str:
    return "data:image/png;base64," + base64.b64encode(p.read_bytes()).decode()


_LONG = re.compile(r"(?<![\w.])-?\d+\.\d{7,}(?:[eE][-+]?\d+)?(?![\w.])")


def _short(v) -> str:
    """69.48581111111105 -> 69.4858 (6 cifras); el resto del texto queda igual."""
    return _LONG.sub(lambda m: f"{float(m.group()):.6g}", str(v))


def _kv(rows: list[tuple[str, str]]) -> str:
    return '<table class="kv"><tbody>' + "".join(f"<tr><th>{e(str(k))}</th><td>{e(_short(v))}</td></tr>" for k, v in rows) + "</tbody></table>"


def _section_table(rows: list[list[str]]) -> str:
    """Objeto | propiedad | valor, con el objeto solo en su primera fila."""
    out, last = [], None
    for obj, k, v in rows:
        first = obj != last
        out.append(f'<tr class="{"first" if first else ""}"><td class="obj">{e(obj) if first else ""}</td><td>{e(k)}</td><td>{e(_short(v))}</td></tr>')
        last = obj
    return '<table class="det"><thead><tr><th>objeto</th><th>propiedad</th><th>valor</th></tr></thead><tbody>' + "".join(out) + "</tbody></table>"


def _size(n: int) -> str:
    for u in ("B", "kB", "MB", "GB"):
        if n < 1024 or u == "GB":
            return f"{n:.0f} {u}" if u == "B" else f"{n:.1f} {u}".replace(".", ",")
        n /= 1024
    return str(n)


CSS = """
@page { size: A4; margin: 16mm 14mm 18mm; @bottom-right { content: "pág. " counter(page) " / " counter(pages); font: 8pt sans-serif; color: #777; }
        @bottom-left { content: var(--pie); font: 8pt sans-serif; color: #777; } }
* { box-sizing: border-box; }
body { font: 9.5pt/1.4 "Segoe UI", system-ui, sans-serif; color: #1d2430; margin: 0; background: #fff; }
h1 { font-size: 22pt; margin: 0 0 4mm; color: #0f3d7a; }
h2 { font-size: 14pt; color: #0f3d7a; border-bottom: 1.5px solid #0f3d7a; padding-bottom: 1mm; margin: 0 0 3mm; break-before: page; }
h3 { font-size: 11pt; margin: 5mm 0 2mm; color: #23446e; }
h4, h5, h6 { font-size: 10pt; margin: 4mm 0 1.5mm; }
p { margin: 1.5mm 0; }
table { border-collapse: collapse; width: 100%; margin: 2mm 0 3mm; font-size: 8.5pt; }
th, td { border: 0.5px solid #c9d1dc; padding: 1mm 1.6mm; text-align: left; vertical-align: top; overflow-wrap: anywhere; }
thead th { background: #eaf0f8; }
tr { break-inside: avoid; }
table.kv th { width: 34%; background: #f4f6fa; font-weight: 600; }
table.det td.obj { font-weight: 600; width: 28%; }
table.det tr.first td { border-top: 1px solid #8fa3bf; }
table.det td:nth-child(2) { width: 27%; color: #3b4a5e; }
table.num td { text-align: right; font-variant-numeric: tabular-nums; }
code { font: 8.5pt Consolas, monospace; background: #f1f3f6; padding: 0 1mm; border-radius: 1mm; }
.cover { height: 250mm; display: flex; flex-direction: column; justify-content: center; }
.cover .sub { font-size: 12pt; color: #4a5a70; margin-bottom: 8mm; }
.kpis { display: grid; grid-template-columns: repeat(4, 1fr); gap: 2.5mm; margin: 4mm 0; }
.kpi { border: 0.5px solid #c9d1dc; border-radius: 2mm; padding: 2.5mm; background: #f7f9fc; }
.kpi b { display: block; font-size: 14pt; color: #0f3d7a; }
.kpi span { font-size: 8pt; color: #5a6a80; }
.note { font-size: 8.5pt; color: #5a6a80; }
.warn { border-left: 3px solid #d0452f; background: #fdf1ef; padding: 2mm 3mm; margin: 2mm 0; }
.toc li { margin: 0.6mm 0; }
figure { margin: 3mm 0 5mm; break-inside: avoid; text-align: center; }
figure img { max-width: 100%; max-height: 120mm; border: 0.5px solid #c9d1dc; }
figcaption { font-size: 8.5pt; color: #4a5a70; margin-top: 1mm; }
svg.chart { width: 100%; height: auto; break-inside: avoid; margin: 1mm 0 3mm; }
svg .ct { font: 600 11px sans-serif; fill: #23446e; } svg .tk { font: 9px sans-serif; fill: #5a6a80; }
svg .lg { font: 600 10px sans-serif; } svg .grid { stroke: #e3e8ef; } svg .frame { fill: none; stroke: #9aa8ba; }
"""


def build_html(case_dir: Path, ctx: dict) -> str:
    """ctx: detalle {rows, at, sim, origen}, sim {path, size, mtime}, roles, view3d (data URL PNG), datasets, cad, version."""
    name = case_dir.name
    res = case_dir / "RESUMEN.md"
    resumen = res.read_text(encoding="utf-8", errors="replace") if res.is_file() else ""
    title = next((ln.lstrip("#").strip() for ln in resumen.splitlines() if ln.startswith("#")), f"Caso {name}")
    det = ctx.get("detalle") or {}
    rows = det.get("rows") or []
    by_sec: dict[str, list] = {}
    for sec, obj, k, v in rows:
        by_sec.setdefault(sec, []).append([obj, k, v])
    cols, conv = read_conv(case_dir)
    last = dict(zip(cols, conv[-1])) if conv else {}
    now = time.strftime("%Y-%m-%d %H:%M")
    simf = ctx.get("sim") or {}
    chapters = []  # (id, título, html)

    # ---- resultados clave
    kp = []
    for k, lab, unit in (("H", "Altura H", "m"), ("M", "Torque M", "N·m"), ("eta", "Eficiencia η", ""), ("Q_in", "Caudal entrada", "kg/s"),
                         ("Q_out", "Caudal salida", "kg/s"), ("pt_in", "p total entrada", "Pa"), ("pt_out", "p total salida", "Pa"),
                         ("continuity", "Residuo continuidad", ""), ("iter", "Iteraciones", "")):
        if last.get(k) is not None:
            v = last[k]
            txt = f"{v * 100:.2f} %".replace(".", ",") if k == "eta" and abs(v) <= 1.5 else (str(int(v)) if k == "iter" else _fmt(v))
            kp.append(f'<div class="kpi"><b>{e(txt)}</b><span>{e(lab)}{" · " + unit if unit else ""}</span></div>')
    if last.get("Q_in") is not None and last.get("Q_out") is not None and last["Q_in"]:
        bal = (abs(last["Q_out"]) - abs(last["Q_in"])) / abs(last["Q_in"]) * 100
        kp.append(f'<div class="kpi"><b>{bal:+.3f} %</b><span>Balance de masa</span></div>'.replace(".", ","))
    rep_rows = [(obj, v) for obj, k, v in by_sec.get("reportes", []) if k == "valor"]
    h = []
    if kp:
        h.append('<div class="kpis">' + "".join(kp) + "</div>")
        h.append(f'<p class="note">Última fila de <code>reports/convergencia.csv</code> (iteración {int(last["iter"]) if last.get("iter") is not None else "–"}).</p>')
    if rep_rows:
        h.append("<h3>Valor de todos los reportes del .sim</h3>" + _kv(rep_rows))
    if not h:
        h.append('<p class="warn">Sin resultados todavía: no hay convergencia.csv ni reportes leídos del solver.</p>')
    chapters.append(("resultados", "Resultados clave", "".join(h)))

    if resumen:
        chapters.append(("resumen", "Resumen del caso (RESUMEN.md)", md_to_html(resumen)))

    # ---- 3D
    h = []
    if ctx.get("view3d"):
        h.append(f'<figure><img src="{ctx["view3d"]}"><figcaption>Vista 3D del visor al generar el informe</figcaption></figure>')
    for ds in ctx.get("datasets") or []:
        m = ds.get("manifest") or {}
        h.append(f"<h3>Dataset «{e(ds['name'])}»</h3>" + _kv([
            ("triángulos", f"{m.get('n_triangles', 0):,}".replace(",", ".")), ("vértices", f"{m.get('n_vertices', 0):,}".replace(",", ".")),
            ("superficies", len(m.get("parts", []))), ("campos", ", ".join(s.get("name", "") for s in m.get("scalars", [])) or "–"),
            ("exportado", m.get("exported") or "–"), *([("iteración (3D en vivo)", m["iteration"])] if m.get("iteration") is not None else []),
            ("marcos rotatorios", ", ".join(f"{r['region']} {r['rpm']:.0f} rpm" for r in m.get("rotation", [])) or "–")]))
    if h:
        chapters.append(("vista3d", "Superficies 3D", "".join(h)))

    # ---- capítulos del detalle del .sim
    if not rows:
        aviso = ('<p class="warn">Sin detalle del .sim: el solver no estaba vivo con este caso y no hay lectura guardada. '
                 'Arranca el solver con el caso (o pídeselo a la IA) y vuelve a exportar para incluir regiones, condiciones, física, malla y solver.</p>')
    else:
        aviso = f'<p class="note">Detalle leído del solver ({e(det.get("origen", ""))}) el {e(det.get("at", ""))} · {len(rows)} propiedades.</p>'
    gen = by_sec.get("general", [])
    for gtitle, secs in GRUPOS:
        h = [aviso] if gtitle == "Geometría" else []
        if gtitle == "Geometría" and ctx.get("cad"):
            h.append("<h3>Archivos de geometría (cad/)</h3><table><thead><tr><th>archivo</th><th>tamaño</th></tr></thead><tbody>"
                     + "".join(f"<tr><td>{e(f['name'])}</td><td>{_size(f['bytes'])}</td></tr>" for f in ctx["cad"]) + "</tbody></table>")
        if gtitle == "Regiones, fronteras e interfaces" and ctx.get("roles"):
            h.append("<h3>Papel de cada cara elegido en el visor (fronteras.json)</h3>"
                     + _kv(sorted(ctx["roles"].items())))
        for s in secs:
            if by_sec.get(s):
                h.append(f"<h3>{e(TITULO[s])}</h3>" + _section_table(by_sec[s]))
        if len(h) > (1 if gtitle == "Geometría" else 0):
            chapters.append((secs[0], gtitle, "".join(h)))

    # ---- convergencia
    if conv:
        xs = [r[cols.index("iter")] if "iter" in cols else i for i, r in enumerate(conv)]
        col = lambda c: [r[cols.index(c)] if c in cols and cols.index(c) < len(r) else None for r in conv]  # noqa: E731
        h = []
        res_c = [c for c in cols if c in ("continuity", "xmom", "ymom", "zmom", "tke", "sdr") or "residual" in c.lower()]
        if res_c:
            h.append(svg_chart("Residuales", xs, {c: col(c) for c in res_c}, log=True))
        for c, lab in (("H", "Altura H (m)"), ("M", "Torque M (N·m)"), ("eta", "Eficiencia η")):
            if c in cols:
                h.append(svg_chart(lab, xs, {c: col(c)}))
        if "Q_in" in cols and "Q_out" in cols:
            h.append(svg_chart("Caudal másico (kg/s)", xs, {"|Q_in|": [abs(v) if v is not None else None for v in col("Q_in")], "Q_out": col("Q_out")}))
        h.append("<h3>Tabla completa (reports/convergencia.csv)</h3><table class=\"num\"><thead><tr>" + "".join(f"<th>{e(c)}</th>" for c in cols)
                 + "</tr></thead><tbody>" + "".join("<tr>" + "".join(f"<td>{_fmt(v)}</td>" for v in r) + "</tr>" for r in conv) + "</tbody></table>")
        chapters.append(("convergencia", "Convergencia", "".join(h)))

    # ---- escenas
    imgs = sorted((case_dir / "images").glob("*.png")) if (case_dir / "images").is_dir() else []
    if imgs:
        chapters.append(("escenas", "Escenas", "".join(
            f'<figure><img src="{_img(p)}"><figcaption>{e(p.stem.replace("_", " "))} · <code>images/{e(p.name)}</code> · '
            f'{time.strftime("%Y-%m-%d %H:%M", time.localtime(p.stat().st_mtime))}</figcaption></figure>' for p in imgs)))

    # ---- anexo: archivos del caso
    files = [p for p in sorted(case_dir.rglob("*")) if p.is_file() and "_raw" not in p.parts and p.suffix not in (".f32", ".u32")]
    chapters.append(("archivos", "Anexo: archivos del caso", "<table><thead><tr><th>archivo</th><th>tamaño</th><th>modificado</th></tr></thead><tbody>"
                     + "".join(f"<tr><td><code>{e(p.relative_to(case_dir).as_posix())}</code></td><td>{_size(p.stat().st_size)}</td>"
                               f"<td>{time.strftime('%Y-%m-%d %H:%M', time.localtime(p.stat().st_mtime))}</td></tr>" for p in files) + "</tbody></table>"))

    cover = _kv([("caso", name), ("archivo de la simulación", simf.get("path") or "–"),
                 ("tamaño del .sim", _size(simf["size"]) if simf.get("size") else "–"),
                 ("guardado", simf.get("mtime") or "–"),
                 ("STAR-CCM+", next((v for o, k, v in gen if k == "versión"), None) or ctx.get("version") or "–"),
                 ("iteración del .sim", next((v for o, k, v in gen if k == "iteración"), None) or (int(last["iter"]) if last.get("iter") is not None else "–")),
                 ("detalle del .sim", f"{det.get('origen')} · {det.get('at')}" if rows else "no disponible"),
                 ("generado", now)])
    toc = '<ol class="toc">' + "".join(f'<li><a href="#{cid}">{e(t)}</a></li>' for cid, t, _ in chapters) + "</ol>"
    body = "".join(f'<h2 id="{cid}">{e(t)}</h2>{c}' for cid, t, c in chapters)
    pie = '"' + f"{name} · informe CFD · {now}".replace("\\", "/").replace('"', "'") + '"'  # CSS no entiende los \u de JSON
    return (f'<!doctype html><html lang="es"><head><meta charset="utf-8"><title>{e(title)}</title>'
            f"<style>:root {{ --pie: {pie}; }}{CSS}</style></head><body>"
            f'<section class="cover"><h1>{e(title)}</h1><div class="sub">Informe de simulación CFD · STAR-CCM+ · agente IA</div>{cover}'
            f"<h3>Contenido</h3>{toc}</section>{body}</body></html>")


def browser() -> str | None:
    for p in (os.environ.get("STARCCM_PDF_BROWSER"), r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
              r"C:\Program Files\Microsoft\Edge\Application\msedge.exe", r"C:\Program Files\Google\Chrome\Application\chrome.exe",
              shutil.which("msedge"), shutil.which("chrome"), shutil.which("chromium")):
        if p and Path(p).is_file():
            return p
    return None


def to_pdf(html_file: Path, pdf_file: Path, timeout: int = 180) -> float:
    """Imprime el HTML a PDF con Edge/Chrome sin ventana (perfil temporal: no choca con el navegador abierto)."""
    exe = browser()
    if not exe:
        raise RuntimeError("no encuentro Edge ni Chrome para imprimir el PDF (define STARCCM_PDF_BROWSER)")
    pdf_file = pdf_file.resolve()
    pdf_file.unlink(missing_ok=True)
    prof = Path(tempfile.mkdtemp(prefix="starccm-pdf-"))
    t0 = time.time()
    try:
        r = subprocess.run([exe, "--headless=new", "--disable-gpu", "--no-first-run", "--no-pdf-header-footer",
                            f"--user-data-dir={prof}", f"--print-to-pdf={pdf_file}", html_file.resolve().as_uri()],
                           capture_output=True, timeout=timeout, stdin=subprocess.DEVNULL)
        # Edge puede salir (código 0) antes de terminar de escribir: esperar a que el PDF exista y deje de crecer
        last, deadline = -1, time.time() + 60
        while time.time() < deadline:
            n = pdf_file.stat().st_size if pdf_file.is_file() else -1
            if n > 0 and n == last:
                break
            last = n
            time.sleep(0.5)
    finally:
        shutil.rmtree(prof, ignore_errors=True)
    if not pdf_file.is_file() or pdf_file.read_bytes()[:4] != b"%PDF":
        err = (r.stderr or b"").decode("utf-8", "replace").strip().splitlines()
        raise RuntimeError(f"el navegador no escribió el PDF (código {r.returncode}): {' | '.join(err[-3:])[:400]}")
    return round(time.time() - t0, 1)
