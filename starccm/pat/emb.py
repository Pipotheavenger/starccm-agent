r"""Puntos extra de embalamiento (opción B, Sebastián 2026-11-15): estudio aparte del barrido PAT, misma orquestación.

    python emb.py plan                → bombas y caudales extra
    python emb.py tablero             → http://localhost:8772/tablero.html (ciclo cada minuto, como pat.py)

En el barrido de 32 casos M_turb solo cambia de signo en G001 y G002; las demás embalan por debajo de 0,8 Qn. Aquí, a
3000 rpm: 0,7 · 0,55 · 0,4 Qn (de más a menos caudal, hacia el embalamiento); G001, cuyo barrido a 3000 rpm es todo
freno, 2,6 · 3,0 · 3,4 Qn. G002 ya cruza a 3000 rpm: no va. 45 bombas × 3 = 135 casos.
Carpetas propias: plan/estado/eventos/_traido en pat/emb/, workers en C:\trabajo\PAT-2026-11_PAT1_emb. No se guarda ningún
.sim. Resultado: hojas «Puntos embalamiento» y «Embalamiento» (recalculada con los puntos de 3000 rpm del barrido + los
extra) en el mismo <carpeta>\PAT\<id>_PAT.xlsx."""
import json, pathlib, sys

AQUI = pathlib.Path(__file__).parent
sys.path.insert(0, str(AQUI))
import pat, doe   # noqa: E402  (pat ya deja doe apuntando a PAT; aquí se reapunta a emb)

EMB = AQUI / "emb"
FQ_EXTRA = [0.7, 0.55, 0.4]
FQ_G001 = [2.6, 3.0, 3.4]
SIN_EXTRA = ("G002",)   # ya cruza a 3000 rpm dentro del barrido
DIR = "PAT-2026-11_PAT1_emb"

doe.AQUI, doe.PLAN, doe.DOE = EMB, EMB / "plan.json", DIR
doe.REMOTO = rf"C:\trabajo\{DIR}"
pat.AQUI = EMB   # preparar (_stage), traer y podar (_traido) de pat.py escriben aquí
_base_pat = pat._base


def _base() -> list[dict]:
    return [r for r in _base_pat() if not r["id"].startswith(SIN_EXTRA)]


def geo(gid: str) -> dict:
    r = next(x for x in _base() if x["id"].startswith(gid))
    qn, rho = r["Qn_m3h"], r["rho"]
    fq = FQ_G001 if r["id"].startswith("G001") else FQ_EXTRA
    q = [round(f * qn, 3) for f in fq]
    return {**r, "rpm_bomba": r["rpm"], "Q_m3h": q, "rpms": [3000] * len(q),
            "masa_kg_s": [round(x * rho / 3600, 6) for x in q], "Flujo_kg_s": [float(k + 1) for k in range(len(q))],
            "orden": list(range(len(q))), "H_cfturbo_m": None, "eta_cfturbo": None}


def rango_cache() -> dict:
    return {r["id"]: geo(r["id"]) for r in _base()}


def excel_bomba(gid: str, local: pathlib.Path, salida: pathlib.Path) -> pathlib.Path:
    """Añade al Excel del barrido la hoja de puntos extra y rehace «Embalamiento» con los de 3000 rpm de ambos."""
    from openpyxl import load_workbook
    from openpyxl.styles import Font, PatternFill
    # todas las rondas de puntos extra (emb/, emb2/…): la hoja se rehace con todas
    dirs = {local, *(d / "_traido" / gid for d in AQUI.glob("emb*") if d.is_dir())}
    extra = [json.loads(f.read_text(encoding="utf-8")) for d in dirs for f in sorted(d.glob("Q*/resultados.json"))]
    barrido = [json.loads(f.read_text(encoding="utf-8")) for f in sorted((AQUI / "_traido" / gid).glob("Q*/resultados.json"))]
    wb = load_workbook(salida)
    for n in ("Puntos embalamiento", "Embalamiento"):
        if n in wb.sheetnames: del wb[n]
    ws = wb.create_sheet("Puntos embalamiento")
    claves = ["H", "eta", "P_eje", "P_hid", "M", "M_turb", "omega", "pt_in", "pt_out", "Q_in", "Q_out", "H_Euler", "eta_Euler"]
    ws.append(["rpm", "Q (m³/h)", "Q/Qn", "Flujo (kg/s)", "régimen", "iteraciones", "balance de masa (%)"] + claves)
    for c in ws[1]: c.font, c.fill = Font(bold=True), PatternFill("solid", fgColor="DDE7F5")
    qn = geo(gid)["Qn_m3h"]
    for p in sorted(extra, key=lambda p: p.get("Q_m3h") or 0):
        rep = p.get("reportes") or {}
        ws.append([p.get("rpm"), p.get("Q_m3h"), (p.get("Q_m3h") or 0) / qn, p.get("Flujo_kg_s"), pat.regimen(p),
                   p.get("iteracion"), p.get("balance_masa_pct")] + [rep.get(k) for k in claves])
    ws2 = wb.create_sheet("Embalamiento")
    ws2.append(["rpm", "Q embalamiento (m³/h)", "H (m)", "Q/Qn"])
    for f in pat.embalamiento(barrido + extra):
        ws2.append([f["rpm"], f["Q_embalamiento_m3h"], f["H_m"], f["Q_embalamiento_m3h"] / qn])
    wb.save(salida)
    return salida


def traer(gid: str):
    """Como pat.traer, pero a _traido de emb y al Excel del barrido (no lo reescribe: le añade hojas)."""
    p = doe.plan(); gid = next(k for k in p["geometrias"] if k.startswith(gid)); e = p["geometrias"][gid]
    lst = doe.ssh(e["worker"], f"Get-ChildItem '{e['dir']}\\puntos' -Recurse -Filter resultados.json | % {{"
                               f" $d=$_.DirectoryName; $d + '|' + ((Get-ChildItem \"$d\\images\" -Filter *.png | % FullName) -join ';') }}", timeout=180)
    local = EMB / "_traido" / gid
    for linea in filter(None, lst.splitlines()):
        d, imgs = linea.split("|", 1)
        dst = local / pathlib.PureWindowsPath(d).name
        dst.mkdir(parents=True, exist_ok=True)
        doe.scp(dst / "resultados.json", e["worker"], f"{d}\\resultados.json".replace("\\", "/"), bajar=True)
        try:
            doe.scp(dst, e["worker"], f"{d}\\reports".replace("\\", "/"), bajar=True)
        except Exception:
            pass
        (dst / "imagenes.json").write_text(json.dumps([i for i in imgs.split(";") if i], ensure_ascii=False), encoding="utf-8")
    out = excel_bomba(gid, local, pathlib.Path(e["carpeta"]) / "PAT" / f"{gid}_PAT.xlsx")
    q = doe.plan(); q["geometrias"][gid]["excel"] = str(out); doe.guardar(q)
    print("Excel:", out)
    return out


def podar(gid: str):
    """Sin .sim: se borran todos (y los _cache) en cuanto el Excel está hecho."""
    p = doe.plan(); gid = next(k for k in p["geometrias"] if k.startswith(gid)); e = p["geometrias"][gid]
    print(doe.ssh(e["worker"], rf"""$d = '{e['dir']}'; $antes = (Get-PSDrive C).Free
Get-ChildItem $d -Recurse -Directory -Force -Filter _cache | Remove-Item -Recurse -Force
Get-ChildItem $d -Recurse -File -Force -Include *.sim, *.sim~ | Remove-Item -Force
'liberados_GB=' + [math]::Round(((Get-PSDrive C).Free - $antes)/1GB,1) + ' libre_GB=' + [math]::Round((Get-PSDrive C).Free/1GB)""", timeout=600))


# pat.py llama a geo/_base por su nombre global y doe.py a geo/rango_cache/traer/podar
pat.geo, pat._base = geo, _base
doe.geo, doe.rango_cache, doe.traer, doe.podar = geo, rango_cache, traer, podar
doe.rango.todas = lambda *a, **k: _base()


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "plan"
    if cmd == "plan":
        n = 0
        for r in _base():
            g = geo(r["id"]); n += len(g["Q_m3h"])
            print(f"{g['id']:<13} Qn {g['Qn_m3h']:7.1f}  Q {', '.join(f'{x:.1f}' for x in g['Q_m3h'])} m³/h a 3000 rpm")
        print("casos", n)
    elif cmd == "preparar":
        pat.preparar(sys.argv[2], sys.argv[3])
    elif cmd in ("crear", "lanzar", "traer", "podar"):
        getattr(doe, cmd)(sys.argv[2])
    elif cmd == "estado":
        print(json.dumps(doe.estado(), ensure_ascii=False)[:3000])
    elif cmd == "tablero":
        doe.tablero(puerto=8772)
