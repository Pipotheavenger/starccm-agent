r"""DOE en modo PAT (bomba como turbina): reusa la orquestación del modo bomba (../doe/doe.py) con sus propias carpetas.

    python pat.py plan                 → casos (caudal × rpm) de cada geometría
    python pat.py preparar G014 172.17.76.244   → copia base.sim, lo convierte a PAT (dm/pat_fisica.java) y deja el estudio
    python pat.py crear G014 / lanzar G014 / estado
    python pat.py tablero              → http://localhost:8771/tablero.html; da una vuelta de ciclo cada minuto

Barrido (Sebastián, 2026-11-10): rpm 3000, 1500, 1000 y 500 × 8 caudales entre 0,8 y 2,4 Q_BEP (Qn de bomba) = 32 casos.
Design Manager barre UN parámetro, «caso» (1…32); Flujo y rpm son expresiones del caso dentro del .sim. Así se reusan sin
cambios el relanzamiento de puntos sueltos, el estado y el tablero de doe.py (que emparejan por doe.CLAVE_JSON = "caso").
# ponytail: en plan.json el campo «Flujo_kg_s» guarda el número de caso (doe.py lo usa como clave del punto); el caudal
#           másico real va en «masa_kg_s».
Nada se escribe en las carpetas del modo bomba: plan.json, _traido y estado.json aquí; workers en C:\trabajo\PAT-2026-11_PAT1;
Excel en <carpeta de la bomba>\PAT\. Solo se guarda el .sim del BEP de turbina a 3000 rpm."""
import datetime as dt, json, pathlib, sys, types

AQUI = pathlib.Path(__file__).parent
sys.path.insert(0, str(AQUI.parent / "doe"))
import doe, rango   # noqa: E402  (los del modo bomba)

RPMS = [3000, 1500, 1000, 500]
FQ = [0.8 + i * (2.4 - 0.8) / 7 for i in range(8)]
PAT = "PAT-2026-11_PAT1"
PLAN_BOMBA = json.loads((AQUI.parent / "doe" / "plan.json").read_text(encoding="utf-8"))["geometrias"]

doe.AQUI, doe.PLAN, doe.DOE = AQUI, AQUI / "plan.json", PAT
doe.REMOTO = rf"C:\trabajo\{PAT}"
doe.CLAVE_JSON = "caso"
# 2026-11-11: 3 workers más solo para PAT (.207, .218, .230; mismo hardware, SSH y licencia probados)
doe.WORKERS = doe.WORKERS + ["172.17.76.207", "172.17.76.218", "172.17.76.230"]


def _base() -> list[dict]:
    """Geometrías del modo bomba (Qn, ρ, carpeta, base.sim), nq ≥ 30 primero y nq 10–25 al final (no convergen en bomba)."""
    todas = rango.todas(plan=PLAN_BOMBA)
    return sorted(todas, key=lambda r: (int(r["id"][1:4]) <= 13, r["id"]))


def geo(gid: str) -> dict:
    r = next(x for x in _base() if x["id"].startswith(gid))
    qn, rho = r["Qn_m3h"], r["rho"]
    casos = []
    for j, n in enumerate(RPMS):   # en zigzag: cada caso arranca de la solución de su vecino (reuso de DM)
        fq = FQ if j % 2 == 0 else FQ[::-1]
        casos += [(round(f * qn, 3), n) for f in fq]
    return {**r, "rpm_bomba": r["rpm"], "Q_m3h": [q for q, _ in casos], "rpms": [n for _, n in casos],
            "masa_kg_s": [round(q * rho / 3600, 6) for q, _ in casos], "Flujo_kg_s": [float(k + 1) for k in range(len(casos))],
            "orden": list(range(len(casos))), "H_cfturbo_m": None, "eta_cfturbo": None}


def rango_cache() -> dict:
    return {r["id"]: geo(r["id"]) for r in _base()}


def preparar(gid: str, ip: str, solo: list[int] | None = None, its: int | None = None):
    """Lo de doe.preparar (macros, scripts, base.sim de bomba desde la .72) y, la primera vez, la conversión a PAT."""
    g = geo(gid)
    _preparar_doe(gid, ip, solo, its)
    d = rf"{doe.REMOTO}\{g['id']}"
    if "True" in doe.ssh(ip, f"Test-Path '{d}\\pat_ok.txt'"):
        return
    stage = AQUI / "_stage" / g["id"]
    (stage / "pat_fisica.java").write_text(doe.plantilla(
        "pat_fisica.java", CASO_FLUJO=", ".join(map(str, g["masa_kg_s"])), CASO_RPM=", ".join(str(float(n)) for n in g["rpms"]),
        RHO=g["rho"]), encoding="utf-8")
    doe.scp(stage / "pat_fisica.java", ip, f"{d}\\pat_fisica.java".replace("\\", "/"))
    print(doe.ssh(ip, f"& '{d}\\compilar.ps1' -Files '{d}\\pat_fisica.java'"))
    out = doe.ssh(ip, f"& '{d}\\star.ps1' -Dir '{d}' -Log '{d}\\pat_fisica.log' -StarArgs '-batch pat_fisica.java base.sim' -Wait;"
                      f" Select-String -Path '{d}\\pat_fisica.log' -Pattern 'PAT_|rror|xception' | % Line | Select -First 40", timeout=1800)
    print(out)
    if "PAT_OK" not in out:
        raise RuntimeError(f"{gid}: la conversión a PAT no terminó (ver {d}\\pat_fisica.log)")
    doe.ssh(ip, f"Set-Content '{d}\\pat_ok.txt' '{dt.datetime.now().isoformat(timespec='seconds')}'")


def traer(gid: str):
    """Baja resultados.json y reports\\ de cada punto a _traido\\<id>\\ y arma <carpeta>\\PAT\\<id>_PAT.xlsx."""
    p = doe.plan(); gid = next(k for k in p["geometrias"] if k.startswith(gid)); e = p["geometrias"][gid]
    lst = doe.ssh(e["worker"], f"Get-ChildItem '{e['dir']}\\puntos' -Recurse -Filter resultados.json | % {{"
                               f" $d=$_.DirectoryName; $d + '|' + ((Get-ChildItem \"$d\\images\" -Filter *.png | % FullName) -join ';') }}", timeout=180)
    local = AQUI / "_traido" / gid
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
    e = doe.plan(); e["geometrias"][gid]["excel"] = str(out); doe.guardar(e)
    print("Excel:", out)
    return out


def regimen(r: dict) -> str:
    rep = r.get("reportes") or {}
    if (rep.get("H") or 0) <= 0:
        return "bomba inversa"
    return "turbina" if (rep.get("P_eje") or 0) > 0 else "freno"


def embalamiento(pts: list[dict]) -> list[dict]:
    """Por cada rpm, caudal donde M_turb pasa por cero (interpolación lineal entre los dos puntos que cambian de signo)."""
    out = []
    for n in sorted({round(p.get("rpm") or 0) for p in pts}):
        fila = sorted((p for p in pts if round(p.get("rpm") or 0) == n), key=lambda p: p["Q_m3h"])
        for a, b in zip(fila, fila[1:]):
            ma, mb = (a["reportes"] or {}).get("M_turb"), (b["reportes"] or {}).get("M_turb")
            if ma is not None and mb is not None and (ma <= 0 < mb or mb <= 0 < ma):
                q = a["Q_m3h"] + (b["Q_m3h"] - a["Q_m3h"]) * (0 - ma) / (mb - ma)
                ha, hb = a["reportes"]["H"], b["reportes"]["H"]
                out.append({"rpm": n, "Q_embalamiento_m3h": q, "H_m": ha + (hb - ha) * (q - a["Q_m3h"]) / (b["Q_m3h"] - a["Q_m3h"])})
    return out


def excel_bomba(gid: str, local: pathlib.Path, salida: pathlib.Path) -> pathlib.Path:
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill
    pts = [json.loads(f.read_text(encoding="utf-8")) for f in sorted(local.glob("Q*/resultados.json"))]
    pts.sort(key=lambda p: (-(p.get("rpm") or 0), p.get("Q_m3h") or 0))
    wb = Workbook(); ws = wb.active; ws.title = "Puntos"
    claves = ["H", "eta", "P_eje", "P_hid", "M", "M_turb", "omega", "pt_in", "pt_out", "Q_in", "Q_out", "U1", "U2", "Vu1", "Vu2",
              "Vr1", "Vr2", "UVu1", "UVu2", "H_Euler", "eta_Euler", "yplus_max_alabes", "yplus_min_alabes"]
    cab = ["caso", "rpm", "Q (m³/h)", "Flujo (kg/s)", "régimen", "iteraciones", "balance de masa (%)", "y+ medio álabes", "celdas"] + claves
    ws.append(cab)
    for c in ws[1]: c.font, c.fill = Font(bold=True), PatternFill("solid", fgColor="DDE7F5")
    for p in pts:
        rep = p.get("reportes") or {}
        ws.append([p.get("caso"), p.get("rpm"), p.get("Q_m3h"), p.get("Flujo_kg_s"), regimen(p), p.get("iteracion"),
                   p.get("balance_masa_pct"), p.get("yplus_alabes_medio"), p.get("celdas")] + [rep.get(k) for k in claves])
    ws.freeze_panes = "C2"
    ws2 = wb.create_sheet("Embalamiento")
    ws2.append(["rpm", "Q embalamiento (m³/h)", "H (m)"])
    for f in embalamiento(pts): ws2.append([f["rpm"], f["Q_embalamiento_m3h"], f["H_m"]])
    salida.parent.mkdir(parents=True, exist_ok=True)
    wb.save(salida)
    return salida


def podar(gid: str):
    """Deja solo el .sim del BEP de turbina a la rpm más alta con P_eje > 0 (3000 salvo nq bajas); lo demás queda en JSON, imágenes y Excel."""
    p = doe.plan(); gid = next(k for k in p["geometrias"] if k.startswith(gid)); e = p["geometrias"][gid]
    pts = [(f.parent.name, json.loads(f.read_text(encoding="utf-8"))) for f in (AQUI / "_traido" / gid).glob("Q*/resultados.json")]
    turb = [(n, r) for n, r in pts if ((r.get("reportes") or {}).get("P_eje") or 0) > 0]
    # nq bajas (G001): a 3000 rpm todo el barrido es freno → BEP de turbina a la rpm más alta con P_eje > 0
    rmax = max((round(r.get("rpm") or 0) for _, r in turb), default=None)
    cand = [(n, r) for n, r in turb if round(r.get("rpm") or 0) == rmax] or pts
    keep_dir = max(cand, key=lambda t: (t[1].get("reportes") or {}).get("eta") or -9)[0]
    print(doe.ssh(e["worker"], rf"""
$d = '{e['dir']}'
$so = Join-Path "$d\puntos\{keep_dir}" 'sim_origen.txt'
$keep = if (Test-Path $so) {{ (Get-Content $so -Raw).Trim() }} else {{ '' }}
if ($keep -and -not (Test-Path $keep) -and $keep.StartsWith($d)) {{
  $rel = $keep.Substring($d.Length).TrimStart('\')
  $keep = @(Get-ChildItem $d -Directory -Force -Filter '_intento*' | % {{ Join-Path $_.FullName $rel }} | ? {{ Test-Path $_ }})[0]
}}
if (-not $keep -or -not (Test-Path $keep)) {{ 'NO_PODADO: no se encuentra el .sim del BEP'; return }}
$antes = (Get-PSDrive C).Free
Get-ChildItem $d -Recurse -Directory -Force -Filter _cache | Remove-Item -Recurse -Force
Get-ChildItem $d -Recurse -File -Force -Include *.sim, *.sim~ | ? {{ $_.FullName -ne $keep }} | Remove-Item -Force
'queda=' + $keep + ' ({keep_dir})'
'liberados_GB=' + [math]::Round(((Get-PSDrive C).Free - $antes)/1GB,1) + ' libre_GB=' + [math]::Round((Get-PSDrive C).Free/1GB)
""", timeout=600))


# doe.py llama a estos por su nombre global: con esto trabaja con los casos y las carpetas PAT
_preparar_doe = doe.preparar
doe.geo, doe.rango_cache, doe.preparar, doe.traer, doe.podar = geo, rango_cache, preparar, traer, podar
doe.rango = types.SimpleNamespace(todas=lambda *a, **k: _base())


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "plan"
    if cmd == "plan":
        for r in _base():
            g = geo(r["id"])
            print(f"{g['id']:<13} Qn {g['Qn_m3h']:7.1f}  Q {g['Q_m3h'][0]:.1f}…{max(g['Q_m3h']):.1f}  casos {len(g['Q_m3h'])}")
    elif cmd == "preparar":
        preparar(sys.argv[2], sys.argv[3])
    elif cmd in ("crear", "lanzar", "traer", "podar"):
        getattr(doe, cmd)(sys.argv[2])
    elif cmd == "estado":
        print(json.dumps(doe.estado(), ensure_ascii=False)[:3000])
    elif cmd == "tablero":
        doe.tablero(puerto=8771)
