r"""Una simulación transitoria (URANS, malla deslizante) de G025_nq50_B en su BEP de turbina a 3000 rpm, para comparar con
el estacionario MRF del DOE (Sebastián, 2026-11-16).

    python transitorio.py diag        → imprime el montaje del .sim (no itera, ~2 min)
    python transitorio.py correr      → 10 vueltas a 2°/paso, 8 it internas (~3 h)
    python transitorio.py estado      → últimas líneas TR y filas del CSV
    python transitorio.py traer       → baja transitorio.csv y compara con el estacionario
Worker .245 (donde está el .sim del BEP); carpeta C:\trabajo\TRANSITORIO_G025\ (copia; el .sim del DOE no se toca)."""
import json, pathlib, statistics, sys

AQUI = pathlib.Path(__file__).parent
sys.path.insert(0, str(AQUI.parent.parent / "doe"))
import doe   # noqa: E402

IP = "172.17.76.245"
SIM = r"C:\trabajo\PAT-2026-11_PAT1\G025_nq50_B\.mdxruntime\G025_nq50_B_20261111185028\Barrido\Design_2\base.sim"
OUT = r"C:\trabajo\TRANSITORIO_G025"
ESTACIONARIO = AQUI.parent / "_traido" / "G025_nq50_B" / "Q0429.120_m3h_n3000_rpm" / "resultados.json"
PARAM = {"NREV": 10, "GRADOS": 2.0, "INNER": 8}


def subir(modo: str):
    java = (AQUI / "transitorio.java").read_text(encoding="utf-8")
    for k, v in {**PARAM, "MODO": modo, "OUT": OUT.replace("\\", "/")}.items():
        java = java.replace("{{" + k + "}}", str(v))
    tmp = AQUI / "_stage"; tmp.mkdir(exist_ok=True)
    (tmp / "transitorio.java").write_text(java, encoding="utf-8")
    doe.ssh(IP, f"New-Item -ItemType Directory -Force '{OUT}' | Out-Null")
    w = OUT.replace("\\", "/")
    doe.scp(tmp / "transitorio.java", IP, f"{w}/transitorio.java")
    doe.scp(AQUI / "transitorio.ps1", IP, f"{w}/transitorio.ps1")
    doe.scp(AQUI.parent.parent / "doe" / "scripts" / "compilar.ps1", IP, f"{w}/compilar.ps1")
    print(doe.ssh(IP, rf"& '{OUT}\compilar.ps1' -Files '{OUT}\transitorio.java'"))


def lanzar(limite: int):
    cmd = rf"powershell -NoProfile -ExecutionPolicy Bypass -File {OUT}\transitorio.ps1 -Sim {SIM} -Out {OUT} -Limite {limite}"
    print(doe.ssh(IP, f"$r = Invoke-CimMethod Win32_Process -MethodName Create -Arguments @{{CommandLine='{cmd}'; CurrentDirectory='{OUT}'}};"
                      " 'pid=' + $r.ProcessId"))


def estado():
    print(doe.ssh(IP, rf"""Select-String -Path '{OUT}\transitorio.out' -Pattern '^TR|rror|xception' -ErrorAction SilentlyContinue | % Line | Select -Last 60
if (Test-Path '{OUT}\transitorio.csv') {{ 'filas=' + (Get-Content '{OUT}\transitorio.csv').Count }}
Get-Content '{OUT}\transitorio_fin.txt' -ErrorAction SilentlyContinue"""))


def traer():
    dst = AQUI / "_traido"; dst.mkdir(exist_ok=True)
    doe.scp(dst / "transitorio.csv", IP, OUT.replace("\\", "/") + "/transitorio.csv", bajar=True)
    filas = [l.split(",") for l in (dst / "transitorio.csv").read_text().splitlines()[1:]]
    cab = "paso,t_s,angulo_deg,vuelta,H,M,eta,P_eje,P_hid,Q_in,Q_out,pt_in,pt_out".split(",")
    F = [dict(zip(cab, map(float, f))) for f in filas]
    nrev = int(max(f["vuelta"] for f in F))
    est = json.loads(ESTACIONARIO.read_text(encoding="utf-8"))["reportes"]
    print(f"{len(F)} pasos, {nrev} vueltas")
    for v in range(1, nrev + 1):
        x = [f for f in F if f["vuelta"] == v]
        print(f"vuelta {v:2d}: H {statistics.mean(f['H'] for f in x):.3f}  M {statistics.mean(f['M'] for f in x):.3f}  η {statistics.mean(f['eta'] for f in x):.4f}")
    ult = [f for f in F if f["vuelta"] > nrev - 5]   # media de las 5 últimas vueltas
    res = {}
    for k in ("H", "M", "eta", "P_eje"):
        v = [f[k] for f in ult]
        res[k] = (statistics.mean(v), min(v), max(v), est[k])
        m = res[k][0]
        print(f"{k:6s} transitorio {m:10.4f} (±{(max(v) - min(v)) / 2 / abs(m) * 100:.2f} % pico)  estacionario {est[k]:10.4f}  dif {(m / est[k] - 1) * 100:+.2f} %")
    return res


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "estado"
    if cmd == "diag":
        subir("diag"); lanzar(1800)
    elif cmd == "correr":
        subir("correr"); lanzar(43200)
    elif cmd == "estado":
        estado()
    elif cmd == "traer":
        traer()
