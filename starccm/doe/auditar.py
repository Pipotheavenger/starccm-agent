r"""Auditoría final del DOE en modo bomba (2026-11-10, antes de arrancar el modo PAT).

    python auditar.py            → imprime cada comprobación (OK / FALLA) y un resumen; con --sin-workers no usa SSH

Comprueba: datos locales (_traido), repositorio unificado (DOE_PAT1_resultados), Excel por bomba y base de datos, y en
cada worker los .sim que quedan, imágenes, procesos de STAR y disco libre."""
import hashlib, json, math, pathlib, sys

import consolidar, doe, rango

AQUI = pathlib.Path(__file__).parent
U = consolidar.DESTINO
fallas = []


def chk(ok: bool, que: str):
    if not ok:
        fallas.append(que)
        print("FALLA", que)


def md5(p: pathlib.Path) -> str:
    return hashlib.md5(p.read_bytes()).hexdigest()


def main(workers: bool = True):
    plan = doe.plan()["geometrias"]
    rg_todas = rango.todas(plan=plan)
    chk(len(rg_todas) == 47, f"47 geometrías en rango ({len(rg_todas)})")
    filas_db = {}
    import openpyxl
    ws = openpyxl.load_workbook(U / "DOE_PAT1_modo_bomba.xlsx", read_only=True)["Simulaciones"]
    rows = list(ws.iter_rows(values_only=True)); cab = rows[0]
    for r in rows[1:]:
        d = dict(zip(cab, r)); filas_db[(d["id"], round(d["Q_m3h"], 2))] = d
    chk(len(filas_db) == 470, f"470 filas en la base de datos ({len(filas_db)})")
    for rg in rg_todas:
        gid, x = rg["id"], plan.get(rg["id"], {})
        its = x.get("its") or 1500
        chk(x.get("fase") == "entregada" and x.get("v2") is True, f"{gid} fase entregada y v2 ({x.get('fase')}, {x.get('v2')})")
        qs = sorted((AQUI / "_traido" / gid).glob("Q*"))
        chk(len(qs) == 10, f"{gid} 10 puntos locales ({len(qs)})")
        vistos = set()
        for q in qs:
            d = json.loads((q / "resultados.json").read_text(encoding="utf-8"))
            Q = d["Flujo_kg_s"] * 3600 / rg["rho"]
            i = min(range(10), key=lambda k: abs(rg["Q_m3h"][k] - Q))
            chk(abs(rg["Q_m3h"][i] - Q) < 0.05, f"{gid}/{q.name} caudal fuera del plan")
            vistos.add(i)
            chk(d.get("version_json") == "2" or d.get("version_json") == 2, f"{gid}/{q.name} datos completos (v2)")
            chk(d.get("iteracion") == its, f"{gid}/{q.name} iteraciones {d.get('iteracion')} ≠ {its}")
            H = (d.get("reportes") or {}).get("H")
            chk(H is not None and math.isfinite(H), f"{gid}/{q.name} H finita")
            errs = [k for k in d if k.startswith("error_") and k not in ("error_modelos", "error_solvers")]
            chk(not errs, f"{gid}/{q.name} errores de extracción {errs}")
            u = U / "datos" / gid / q.name
            chk((u / "resultados.json").exists() and md5(u / "resultados.json") == md5(q / "resultados.json"), f"{gid}/{q.name} unificado = local")
            chk(len(list((u / "images").glob("*.png"))) > 0 if (u / "images").exists() else False, f"{gid}/{q.name} con imágenes en el unificado")
            f = filas_db.get((gid, round(Q, 2))) or filas_db.get((gid, round(rg["Q_m3h"][i], 2)))
            chk(f is not None and abs((f["H_m"] or 0) - H) < 1e-6, f"{gid}/{q.name} H en la base de datos = JSON")
        chk(len(vistos) == 10, f"{gid} los 10 caudales del plan ({len(vistos)})")
        carpeta = pathlib.Path(rg["carpeta"]) / "DOE"
        xl, inf = carpeta / f"{gid}_barrido.xlsx", carpeta / f"{gid}_informe.txt"
        chk(xl.exists() and inf.exists(), f"{gid} Excel e informe en la carpeta DOE")
        if xl.exists() and qs:
            ultimo = max((q / "resultados.json").stat().st_mtime for q in qs)
            chk(xl.stat().st_mtime >= ultimo - 60, f"{gid} Excel posterior a los últimos datos")
        chk((U / "excels" / xl.name).exists() and md5(U / "excels" / xl.name) == md5(xl) if xl.exists() else False, f"{gid} Excel copiado al unificado")
    if workers:
        por = {}
        for gid, x in plan.items(): por.setdefault(x["worker"], []).append((gid, x["dir"]))
        for ip, gs in por.items():
            dirs = ",".join(f"'{d}'" for _, d in gs)
            s = doe.ssh(ip, rf"""foreach ($d in @({dirs})) {{
  $s = @(Get-ChildItem $d -Recurse -Force -File -Include *.sim, *.sim~ -ErrorAction SilentlyContinue)
  $img = @(Get-ChildItem "$d\puntos" -Recurse -Filter *.png -ErrorAction SilentlyContinue).Count
  $pts = @(Get-ChildItem "$d\puntos" -Directory -ErrorAction SilentlyContinue).Count
  (Split-Path $d -Leaf) + '|' + $s.Count + '|' + [math]::Round(($s | Measure-Object Length -Sum).Sum/1GB,2) + '|' + $pts + '|' + $img + '|' + [math]::Round((Get-ChildItem $d -Recurse -Force -File -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum/1GB,2) }}
'STAR|' + @(Get-CimInstance Win32_Process | ? {{ $_.ExecutablePath -like '*STAR-CCM+*' -and $_.Name -ne 'hydra_service.exe' }}).Count
'LIBRE|' + [math]::Round((Get-PSDrive C).Free/1GB)""", timeout=600)
            for l in filter(None, (z.strip() for z in s.splitlines())):
                p = l.split("|")
                if p[0] == "STAR": chk(p[1] == "0", f"{ip} sin procesos de STAR vivos ({p[1]})"); continue
                if p[0] == "LIBRE": print(f"   {ip} libre {p[1]} GB"); continue
                if len(p) < 6: continue
                gid, nsim, gb, pts, img, tot = p[0], int(p[1]), p[2], int(p[3]), int(p[4]), p[5]
                chk(nsim == 1, f"{gid} en {ip}: 1 .sim (Qn) ({nsim}, {gb} GB)")
                chk(pts == 10 and img > 0, f"{gid} en {ip}: 10 puntos con imágenes ({pts}, {img} png)")
                print(f"   {gid} {ip} sims={nsim} ({gb} GB) puntos={pts} png={img} carpeta={tot} GB")
    print(f"\n{len(fallas)} fallas" if fallas else "\nAUDITORÍA OK: sin fallas")
    return fallas


if __name__ == "__main__":
    main("--sin-workers" not in sys.argv)
