r"""Pruebas de convergencia en un worker libre (2026-11-10: nq 10–25 no convergen ni a 2000 iteraciones).

    python prueba.py lanzar G001 urf_p01 urf 1500 --urf_p 0.1 --urf_v 0.3
    python prueba.py lanzar G001 malla075 malla 1500 --factor 0.75
    python prueba.py leer G001 urf_p01

Corre dm/prueba.java sobre una copia del .sim de Qn (scripts/prueba.ps1) en <geometría>\pruebas\<nombre>\. Una prueba
por worker a la vez (una licencia por máquina); no pasa por plan.json ni por el tablero."""
import argparse, json, pathlib

import doe

AQUI = pathlib.Path(__file__).parent


def lanzar(gid: str, nombre: str, modo: str, its: int, urf_p: float = 0.2, urf_v: float = 0.5, factor: float = 1.0):
    e = doe.plan()["geometrias"][next(k for k in doe.plan()["geometrias"] if k.startswith(gid))]
    g = doe.geo(gid); d, ip = e["dir"], e["worker"]
    out = rf"{d}\pruebas\{nombre}"
    w = lambda p: p.replace("\\", "/")
    stage = AQUI / "_stage" / g["id"] / "pruebas" / nombre
    stage.mkdir(parents=True, exist_ok=True)
    (stage / "prueba.java").write_text(doe.plantilla("prueba.java", MODO=modo, DIR=w(out), ITS=its, URF_P=urf_p, URF_V=urf_v, FACTOR=factor), encoding="utf-8")
    doe.ssh(ip, f"New-Item -ItemType Directory -Force '{out}' | Out-Null")
    doe.scp(stage / "prueba.java", ip, w(rf"{out}\prueba.java"))
    for n in ("prueba.ps1", "enmascarar.ps1", "compilar.ps1"):
        doe.scp(AQUI / "scripts" / n, ip, w(rf"{d}\{n}"))
    r = doe.ssh(ip, rf"& '{d}\compilar.ps1' -Files '{out}\prueba.java'")
    if "OK" not in r:
        raise RuntimeError("prueba: no compila " + r[:400])
    cmd = rf"powershell -NoProfile -ExecutionPolicy Bypass -File {d}\prueba.ps1 -Dir {d} -Out {out} -Qn {g['Qn_m3h']}"
    print(doe.ssh(ip, f"$r = Invoke-CimMethod Win32_Process -MethodName Create -Arguments @{{CommandLine='{cmd}'; CurrentDirectory='{out}'}};"
                      f" 'rc=' + $r.ReturnValue + ' pid=' + $r.ProcessId"))


def leer(gid: str, nombre: str) -> str:
    e = doe.plan()["geometrias"][next(k for k in doe.plan()["geometrias"] if k.startswith(gid))]
    out = rf"{e['dir']}\pruebas\{nombre}"
    return doe.ssh(e["worker"], rf"""Select-String -Path '{out}\prueba.out' -Pattern '^PRUEBA|rror' -ErrorAction SilentlyContinue | % Line
if (Test-Path '{out}\prueba_fin.txt') {{ 'FIN ' + (Get-Content '{out}\prueba_fin.txt' -Raw).Trim() }}""", timeout=120)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd"); ap.add_argument("gid"); ap.add_argument("nombre")
    ap.add_argument("modo", nargs="?"); ap.add_argument("its", nargs="?", type=int)
    ap.add_argument("--urf_p", type=float, default=0.2); ap.add_argument("--urf_v", type=float, default=0.5)
    ap.add_argument("--factor", type=float, default=1.0)
    a = ap.parse_args()
    if a.cmd == "lanzar":
        lanzar(a.gid, a.nombre, a.modo, a.its, a.urf_p, a.urf_v, a.factor)
    else:
        print(leer(a.gid, a.nombre))
