"""DOE con Design Manager en los workers. Corre en la .72 (orquestador); el solver solo en los workers.

    python doe/doe.py preparar G001 --worker 172.17.76.244   copia base.sim, macros con valores, compila, crea el .dmprj
    python doe/doe.py lanzar   G001                           corre el barrido en segundo plano (tarea programada)
    python doe/doe.py estado   [--json]                       estado de todos los jobs (lo usa el tablero)
    python doe/doe.py traer    G001                           resultados por punto → Excel en la carpeta de la bomba
    python doe/doe.py tablero                                 http://localhost:8770 con el avance en vivo

Estado en doe/plan.json: geometría → worker, carpeta remota, fase. La clave PoD vive solo en C:\\trabajo\\.env de cada worker.
"""
import argparse, base64, json, pathlib, subprocess, sys, time, datetime as dt

AQUI = pathlib.Path(__file__).parent
PLAN = AQUI / "plan.json"
DOE = "DOE-2026-11_PAT1"
REMOTO = rf"C:\trabajo\{DOE}"
WORKERS = ["172.17.76.244", "172.17.76.245", "172.17.77.9", "172.17.76.222"]
# clave que une un punto de plan.json con su resultados.json: el caudal en bomba; el proyecto PAT (../pat/pat.py) la
# cambia por «caso» (una combinación caudal × rpm) y reusa este módulo con sus propias carpetas
CLAVE_JSON = "Flujo_kg_s"
NP, ITS = 44, 1500   # 44 de 48 núcleos: margen para el sistema (con 46 y explorer.exe había sobresuscripción)
sys.path.insert(0, str(AQUI))
import rango  # noqa: E402

# la consola de Windows (cp1252) no imprime el «�» de los logs de STAR-CCM+ y tumbaba el despacho de G005
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


# ---------------------------------------------------------------- ssh

def ssh(ip: str, ps: str, timeout: int = 120) -> str:
    """PowerShell en el worker (la consola remota es cmd: va codificado)."""
    enc = base64.b64encode(ps.encode("utf-16-le")).decode()
    # ServerAlive: si la red cae con la conexión abierta, ssh se cuelga sin esto (el tablero quedó parado 30 min)
    r = subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", "-o", "ServerAliveInterval=15",
                        "-o", "ServerAliveCountMax=4", f"starccm@{ip}",
                        f"powershell -NoProfile -NonInteractive -ExecutionPolicy Bypass -EncodedCommand {enc}"],
                       capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL, encoding="utf-8", errors="replace")
    return "\n".join(l for l in r.stdout.splitlines() if "CLIXML" not in l and "<Objs" not in l).strip()


def scp(src, ip: str, dst: str, timeout: int = 1800, bajar: bool = False):
    a = [f"starccm@{ip}:{dst}", str(src)] if bajar else [str(src), f"starccm@{ip}:{dst}"]
    subprocess.run(["scp", "-q", "-r", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", "-o", "ServerAliveInterval=15",
                    "-o", "ServerAliveCountMax=4", *a], check=True, timeout=timeout, stdin=subprocess.DEVNULL)


def plan() -> dict:
    return json.loads(PLAN.read_text(encoding="utf-8")) if PLAN.exists() else {"doe": DOE, "geometrias": {}}


def guardar(p: dict):
    PLAN.write_text(json.dumps(p, indent=1, ensure_ascii=False), encoding="utf-8")


def geo(gid: str) -> dict:
    r = next((r for r in rango.todas(plan=plan()["geometrias"]) if r["id"].startswith(gid)), None)
    if not r:
        sys.exit(f"no encuentro {gid} en Geometrias_Prueba")
    return r


def plantilla(nombre: str, **v) -> str:
    t = (AQUI / "dm" / nombre).read_text(encoding="utf-8")
    for k, x in v.items():
        t = t.replace("{{" + k + "}}", str(x))
    return t


# ---------------------------------------------------------------- comandos

def preparar(gid: str, ip: str, solo: list[int] | None = None, its: int | None = None):
    """solo: índices de caudal a correr (repetir los que faltan); por defecto los 10 en su orden. its: iteraciones por
    punto; si no se da, las que ya tenga la bomba en plan.json (las rehechas a 2000, 2026-11-10) o ITS."""
    g = geo(gid)
    its = its or plan()["geometrias"].get(g["id"], {}).get("its") or ITS
    d = rf"{REMOTO}\{g['id']}"
    w = lambda p: p.replace("\\", "/")
    flujos = [g["Flujo_kg_s"][i] for i in g["orden"] if solo is None or i in solo]
    if len(flujos) == 1:   # DM no corre un DISCRETE de 1 valor («at least 2 Values», G025 2026-11-09): repetirlo
        flujos.append(flujos[0] + 1e-6)   # +1e-6 kg/s: misma carpeta Q…_m3h; cuesta un punto más
    stage = AQUI / "_stage" / g["id"]
    stage.mkdir(parents=True, exist_ok=True)
    (stage / "antes_correr.java").write_text(plantilla("antes_correr.java", ITS=its), encoding="utf-8")
    (stage / "despues.java").write_text(plantilla("despues.java", PUNTOS=w(rf"{d}\puntos"), RHO=g["rho"], GUARDAR="true"), encoding="utf-8")
    (stage / "crear_estudio.java").write_text(plantilla(
        "crear_estudio.java", SIM=w(rf"{d}\base.sim"), PROJ=w(rf"{d}\{g['id']}.dmprj"),
        ANTES=w(rf"{d}\antes_correr.java"), DESPUES=w(rf"{d}\despues.java"),
        FLUJOS=", ".join(map(str, flujos)), NP=NP), encoding="utf-8")
    (stage / "rango.json").write_text(json.dumps(g, indent=1, ensure_ascii=False), encoding="utf-8")
    ssh(ip, f"New-Item -ItemType Directory -Force '{d}' | Out-Null")
    print("copiando macros y scripts…")
    (stage / "escenas.java").write_text(plantilla("escenas.java"), encoding="utf-8")
    for f in [*stage.iterdir(), *(AQUI / "scripts" / n for n in ("star.ps1", "compilar.ps1", "enmascarar.ps1", "render.ps1"))]:
        scp(f, ip, w(rf"{d}\{f.name}"))
    for n in ("estado.ps1", "enmascarar.ps1"):
        scp(AQUI / "scripts" / n, ip, f"C:/trabajo/{n}")
    if "True" not in ssh(ip, f"Test-Path '{d}\\base.sim'"):
        t = time.time()
        scp(g["sim"], ip, w(rf"{d}\base.sim"))
        print(f"base.sim copiado en {time.time() - t:.0f} s")
    print(ssh(ip, f"& '{d}\\compilar.ps1' -Files '{d}\\antes_correr.java','{d}\\despues.java','{d}\\crear_estudio.java','{d}\\escenas.java'"))
    p = plan()
    p["geometrias"][g["id"]] = {**p["geometrias"].get(g["id"], {}), "worker": ip, "dir": d, "fase": "preparada",
                                "solo": solo, "its": its,
                                "Q_m3h": g["Q_m3h"], "orden": g["orden"], "Flujo_kg_s": g["Flujo_kg_s"],
                                "carpeta": g["carpeta"], "preparada": dt.datetime.now().isoformat(timespec="seconds")}
    guardar(p)


def rehacer(gid: str):
    r"""Vuelve a correr puntos ya entregados (plan.json: "rehacer": {"solo": [índices] o null = los 10, "its": N}).
    2026-11-10, Sebastián: los 33 puntos que quedaron sin datos completos y las nq 10–25 que no convergieron, a 2000
    iteraciones. Los puntos viejos se apartan a _intento_rehacer\puntos\ (no se borran: el estado los contaría como
    hechos); el resto como un relanzamiento normal y el ciclo entrega, renderiza y poda al acabar."""
    p = plan(); gid = next(k for k in p["geometrias"] if k.startswith(gid)); e = p["geometrias"][gid]
    r = e["rehacer"]; g = geo(gid); d = e["dir"]
    idx = r.get("solo") or list(range(len(g["Q_m3h"])))
    qs = ",".join(str(g["Q_m3h"][i]) for i in idx)   # por caudal (±0,01 m³/h): el nombre Q…_m3h sale de Flujo y puede redondear distinto
    print(ssh(e["worker"], rf"""$a = '{d}\_intento_rehacer\puntos'; New-Item -ItemType Directory -Force $a | Out-Null
$qs = @({qs})
foreach ($o in @(Get-ChildItem '{d}\puntos' -Directory)) {{
  $q = [double]::Parse(($o.Name -replace '^Q|_m3h$', ''), [cultureinfo]::InvariantCulture)
  if (@($qs | ? {{ [math]::Abs($_ - $q) -lt 0.01 }}).Count) {{ $t = Join-Path $a $o.Name; if (Test-Path $t) {{ Remove-Item $t -Recurse -Force }}; Move-Item $o.FullName $t }} }}
'apartados=' + @(Get-ChildItem $a -Directory).Count""", timeout=300))
    reiniciar(gid)
    preparar(gid, e["worker"], solo=r.get("solo"), its=r.get("its"))
    p = plan(); x = p["geometrias"][gid]
    x.update(reintentos=0, v2=None, rehecho=dt.datetime.now().isoformat(timespec="seconds")); x.pop("rehacer", None)
    for k in ("render_fin", "extraer_fin"): x.pop(k, None)
    guardar(p)
    crear(gid)
    if plan()["geometrias"][gid]["fase"] != "creada":   # sin .dmprj DM sale al instante (G032 2026-11-10: el servidor de referencia no arrancó)
        raise RuntimeError("crear no dejó el .dmprj; queda en fase preparada para el ciclo")
    lanzar(gid)


def crear(gid: str):
    p = plan(); gid = next(k for k in p["geometrias"] if k.startswith(gid)); e = p["geometrias"][gid]
    d = e["dir"]
    print(ssh(e["worker"], f"& '{d}\\star.ps1' -Dir '{d}' -Log '{d}\\crear.log' -StarArgs '-dmproject -batch crear_estudio.java' -Wait;"
                           f" Select-String -Path '{d}\\crear.log' -Pattern 'DM|rror|xception' | % Line | Select -First 60", timeout=900))
    if "True" in ssh(e["worker"], f"Test-Path '{d}\\{gid}.dmprj'"):
        e["fase"] = "creada"; guardar(p)


def reiniciar(gid: str):
    """Para el solver del worker de esa geometría y archiva el intento (proyecto, runtime, salidas de DM, logs) en
    _intentoN/. Nada se borra. `puntos\\` se queda: son resultados por caudal y un relanzamiento solo añade los que
    faltan. Después: preparar + crear + lanzar."""
    p = plan(); gid = next(k for k in p["geometrias"] if k.startswith(gid)); e = p["geometrias"][gid]
    d = e["dir"]
    print(ssh(e["worker"], rf"""
$m = Get-CimInstance Win32_Process | ? {{ ($_.ExecutablePath -like '*STAR-CCM+*' -and $_.Name -ne 'hydra_service.exe') -or
      ($_.Name -in 'powershell.exe','cmd.exe' -and $_.CommandLine -match 'star\.ps1|starccm\+') -and $_.ProcessId -ne $PID }}
$m | % {{ Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }}
Start-Sleep 5
$n = 1; while (Test-Path "{d}\_intento$n") {{ $n++ }}
$a = "{d}\_intento$n"; New-Item -ItemType Directory $a | Out-Null
Get-ChildItem '{d}' -Force | ? {{ $_.Name -in '.mdxruntime','{gid}','{gid}.dmprj','{gid}.dmprj~','correr.log','crear.log' }} | Move-Item -Destination $a
& C:\trabajo\enmascarar.ps1 -Dir $a | Out-Null
"cerrados=$(@($m).Count) archivado=$a"
""", timeout=300))
    e["fase"] = "preparada"; guardar(p)


def podar(gid: str):
    r"""Tras entregar: borra los `.sim` de todos los puntos salvo el de Qn (y base.sim, que está en la .72), más `_cache\` y
    `*.sim~` de DM. Lo de cada punto queda en resultados.json versión 2, el Excel y el informe de texto; un punto se
    reproduce corriendo base.sim con su Flujo. Decidido por Sebastián el 2026-11-09: las VM se congelaban con el
    datastore lleno (90 GB de C:\trabajo en el .244). Antes: ~10 GB por bomba; ahora ~1 GB."""
    p = plan(); gid = next(k for k in p["geometrias"] if k.startswith(gid)); e = p["geometrias"][gid]
    print(ssh(e["worker"], rf"""
$d = '{e['dir']}'; $qn = {rango_cache()[gid]['Qn_m3h']}
$antes = (Get-PSDrive C).Free
$pts = @(Get-ChildItem "$d\puntos" -Directory)
$cerca = $pts | Sort-Object {{ [math]::Abs([double]::Parse(($_.Name -replace '^Q|_m3h$', ''), [cultureinfo]::InvariantCulture) - $qn) }} | Select -First 1
$so = if ($cerca) {{ Join-Path $cerca.FullName 'sim_origen.txt' }} else {{ '' }}
$keep = if ($so -and (Test-Path $so)) {{ (Get-Content $so -Raw).Trim() }} else {{ '' }}
if ($keep -and -not (Test-Path $keep) -and $keep.StartsWith($d)) {{   # reiniciar lo movió a _intentoN\ (G025, 2026-11-09)
  $rel = $keep.Substring($d.Length).TrimStart('\')
  $keep = @(Get-ChildItem $d -Directory -Force -Filter '_intento*' | % {{ Join-Path $_.FullName $rel }} | ? {{ Test-Path $_ }})[0]
}}
if (-not $keep -or -not (Test-Path $keep)) {{ 'NO_PODADO: no se encuentra el .sim de Qn'; return }}
# -Force: DM marca ocultas sus carpetas (sin él no se borraba nada: G002 quedó en 19 GB)
Get-ChildItem $d -Recurse -Directory -Force -Filter _cache | Remove-Item -Recurse -Force
Get-ChildItem $d -Recurse -File -Force -Include *.sim, *.sim~ | ? {{ $_.FullName -ne $keep }} | Remove-Item -Force
'queda=' + $keep
'liberados_GB=' + [math]::Round(((Get-PSDrive C).Free - $antes)/1GB,1) + ' libre_GB=' + [math]::Round((Get-PSDrive C).Free/1GB)
""", timeout=600))


def lanzar_extraer(gid: str):
    """Bombas entregadas con resultados.json versión 1: re-extrae todo de sus .sim (scripts/extraer.ps1) en segundo
    plano antes de podarlas; deja extraer_fin.txt al acabar."""
    p = plan(); gid = next(k for k in p["geometrias"] if k.startswith(gid)); e = p["geometrias"][gid]
    d, ip = e["dir"], e["worker"]
    w = lambda s: s.replace("\\", "/")
    stage = AQUI / "_stage" / gid / "extraer"
    stage.mkdir(parents=True, exist_ok=True)
    (stage / "despues.java").write_text(plantilla("despues.java", PUNTOS=w(rf"{d}\puntos"), RHO=rango_cache()[gid]["rho"],
                                                  GUARDAR="false"), encoding="utf-8")
    ssh(ip, rf"New-Item -ItemType Directory -Force '{d}\extraer' | Out-Null")
    scp(stage / "despues.java", ip, w(rf"{d}\extraer\despues.java"))
    for n in ("extraer.ps1", "enmascarar.ps1", "compilar.ps1"):
        scp(AQUI / "scripts" / n, ip, w(rf"{d}\{n}"))
    r = ssh(ip, rf"& '{d}\compilar.ps1' -Files '{d}\extraer\despues.java'")
    if "OK" not in r:
        raise RuntimeError("extraer: no compila " + r[:300])
    cmd = rf"powershell -NoProfile -ExecutionPolicy Bypass -File {d}\extraer.ps1 -Dir {d}"
    print(ssh(ip, rf"Remove-Item '{d}\extraer_fin.txt' -ErrorAction SilentlyContinue; "
                  f"$r = Invoke-CimMethod Win32_Process -MethodName Create -Arguments @{{CommandLine='{cmd}'; CurrentDirectory='{d}'}};"
                  f" 'rc=' + $r.ReturnValue + ' pid=' + $r.ProcessId"))
    e.update(fase="extraer", extraer=dt.datetime.now().isoformat(timespec="seconds")); guardar(p)


def lanzar_render(gid: str):
    """Escenas fuera de DM (scripts/render.ps1), en segundo plano; deja render_fin.txt al acabar."""
    p = plan(); gid = next(k for k in p["geometrias"] if k.startswith(gid)); e = p["geometrias"][gid]
    d = e["dir"]
    cmd = f"powershell -NoProfile -ExecutionPolicy Bypass -File {d}\\render.ps1 -Dir {d}"
    print(ssh(e["worker"], f"Remove-Item '{d}\\render_fin.txt' -ErrorAction SilentlyContinue; "
                           f"$r = Invoke-CimMethod Win32_Process -MethodName Create -Arguments @{{CommandLine='{cmd}'; CurrentDirectory='{d}'}};"
                           f" 'rc=' + $r.ReturnValue + ' pid=' + $r.ProcessId"))
    e.update(fase="render", render=dt.datetime.now().isoformat(timespec="seconds")); guardar(p)


def lanzar(gid: str):
    """Win32_Process.Create: el proceso no cuelga del SSH (Start-Process sí muere al cerrar la sesión)."""
    p = plan(); gid = next(k for k in p["geometrias"] if k.startswith(gid)); e = p["geometrias"][gid]
    d = e["dir"]
    cmd = (f"powershell -NoProfile -ExecutionPolicy Bypass -File {d}\\star.ps1 -Dir {d} -Log {d}\\correr.log "
           f"-StarArgs \"-batch run {gid}.dmprj\" -Design -Wait")
    print(ssh(e["worker"], f"$r = Invoke-CimMethod Win32_Process -MethodName Create -Arguments @{{CommandLine='{cmd}'; CurrentDirectory='{d}'}};"
                           f" 'rc=' + $r.ReturnValue + ' pid=' + $r.ProcessId"))
    e.update(fase="corriendo", lanzada=dt.datetime.now().isoformat(timespec="seconds")); guardar(p)


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _fecha(s):
    """ISO («2026-11-04T07:49:20») o java.util.Date («Wed Nov 04 07:49:20 COT 2026») → datetime ingenuo (hora del worker)."""
    if not s:
        return None
    try:
        return dt.datetime.fromisoformat(s)
    except ValueError:
        pass
    try:
        p = s.split()
        return dt.datetime.strptime(" ".join(p[1:4] + p[-1:]), "%b %d %H:%M:%S %Y")
    except (ValueError, IndexError):
        return None


def _de_log(u: dict, nombre: str):
    """Valor de un monitor en la última fila del log del diseño (cabecera «H», «H Monitor», …)."""
    for k, v in (u or {}).items():
        if k == nombre or k.startswith(nombre + " "):
            return _num(v)
    return None


def estado(escribir: bool = True) -> dict:
    p = plan()
    viejo = json.loads((AQUI / "estado.json").read_text(encoding="utf-8")) if (AQUI / "estado.json").exists() else {}
    ips = sorted({e["worker"] for e in p["geometrias"].values()})
    remoto, workers = {}, []
    for ip in ips:
        try:
            w = json.loads(ssh(ip, rf"& C:\trabajo\estado.ps1 -Raiz '{REMOTO}'", timeout=240) or "{}")   # .218 con 31 puntos PAT: 105 s
            workers.append({"ip": ip, **{k: w.get(k) for k in ("host", "hora", "procesos_star", "cpu_pct", "c_libre_gb")}})
            for g in w.get("geometrias") or []:
                remoto[g["id"]] = (ip, w, g)
        except Exception as ex:
            workers.append({"ip": ip, "error": str(ex)[:120]})
    geos = []
    for gid, e in sorted(p["geometrias"].items()):
        ip, w, g = remoto.get(gid, (e["worker"], {}, {}))
        dis = {round(_num(d.get("Flujo")) or -1, 5): d for d in (g.get("disenos") or [])}
        for q in g.get("puntos") or []:      # resultados (en puntos\, fuera de la carpeta del diseño) por su Flujo
            r = q.get("resultados") or {}
            k = round(_num(r.get(CLAVE_JSON)) or -1, 5)
            dis[k] = {**dis.get(k, {}), "resultados": r, "imagenes": q.get("imagenes"), "fin": q.get("fin")}
        rg = rango_cache().get(gid) or {}
        Hcft = rg.get("H_cfturbo_m") or [None] * len(e["Q_m3h"])
        Ecft = rg.get("eta_cfturbo") or [None] * len(e["Q_m3h"])
        ahora = _fecha(w.get("hora"))
        puntos = []
        for orden, i in enumerate(e["orden"]):
            d = dis.get(round(e["Flujo_kg_s"][i], 5)) or next((v for k, v in dis.items() if abs(k - e["Flujo_kg_s"][i]) < 1e-4), None)
            r = (d or {}).get("resultados") or {}
            rep = r.get("reportes") or {}
            u = (d or {}).get("ultima") or {}
            ini, fin = _fecha((d or {}).get("inicio")), _fecha((d or {}).get("fin"))
            pt = {"n": orden + 1, "Q": e["Q_m3h"][i], "Hcft": Hcft[i], "etacft": Ecft[i], "meta": _num((d or {}).get("meta")),
                  "min": round(((fin if r else ahora) - ini).total_seconds() / 60, 1) if ini and (fin if r else ahora) else None,
                  "it": r.get("iteracion") or _num(u.get("Iteration")),
                  "H": rep.get("H", _de_log(u, "H")), "eta": rep.get("eta", _de_log(u, "eta")), "M": rep.get("M", _de_log(u, "M")),
                  "estado": "terminado" if r else ("corriendo" if d else "esperando")}
            if pt["meta"] and pt["it"]:
                pt["meta"] = int(pt["meta"]); pt["it"] = int(pt["it"])
            puntos.append(pt)
        hechos = sum(q["estado"] == "terminado" for q in puntos)
        act = next((q for q in puntos if q["estado"] == "corriendo"), None)
        # ritmo: s/iteración del punto en curso; minutos por punto (media de los terminados, si no, estimado)
        if act and act.get("min") and act.get("it"):
            act["s_it"] = round(60 * act["min"] / max(1, act["it"]), 2)
        dur = [q["min"] for q in puntos if q["estado"] == "terminado" and q.get("min")]
        min_punto = (sum(dur) / len(dur)) if dur else (act["s_it"] * ITS / 60 if act and act.get("s_it") else None)
        resto = len(puntos) - hechos - (1 if act else 0)
        eta_min = (min_punto * resto + max(0.0, min_punto - (act.get("min") or 0) if act else 0)) if min_punto else None
        frac = 0.0
        if act and act.get("meta") and act.get("it") is not None:
            it0 = _num(next(d for d in dis.values() if (d.get("resultados") is None))["it0"]) or 0
            if act["it"] < it0:          # DM borró el historial: el contador empezó en 0 (puntos lanzados con la macro vieja)
                it0 = 0
            frac = max(0.0, min(1.0, (act["it"] - it0) / max(1, act["meta"] - it0)))
        log = g.get("log") or []
        # DM ya salió (su lanzador no vive) pero faltan puntos: fallaron diseños (licencia retenida por un huérfano,
        # caída del solver…). Margen de 10 min tras lanzar para no confundirlo con el arranque.
        lanz = _fecha(e.get("lanzada"))
        acabado_dm = (g.get("dm_vivo") is False and e.get("fase") == "corriendo" and lanz
                      and (dt.datetime.now() - lanz).total_seconds() > 600)
        # terminada = 10 puntos Y el barrido ya cerró: el último punto escribe resultados.json antes de sus escenas y su
        # .sim, y al entregar se cierran los procesos STAR del worker
        est = ("terminado" if hechos == len(puntos) and g.get("dm_vivo") is not True else
               "corriendo" if hechos == len(puntos) else
               "incompleta" if acabado_dm else
               "error" if any("ERROR" in l or "rror:" in l for l in log[-5:]) else
               "corriendo" if (w.get("procesos_star") or 0) > 0 else
               e.get("fase", "esperando"))
        if est == "corriendo" and g.get("log_mod"):
            ult = max(filter(None, [g.get("log_mod"), *[d.get("log_mod") for d in dis.values()]]))
            if (dt.datetime.fromisoformat(w["hora"]) - dt.datetime.fromisoformat(ult)).total_seconds() > 3600:
                est = "sin_progreso"
        geos.append({"id": gid, "worker": ip, "estado": est, "puntos": sorted(puntos, key=lambda q: q["Q"]),
                     "faltan": [i for i in e["orden"] if puntos[e["orden"].index(i)]["estado"] != "terminado"],
                     "render_fin": g.get("render_fin"), "extraer_fin": g.get("extraer_fin"),
                     "avance": (hechos + frac) / len(puntos), "log": log[-8:],
                     "s_it": act.get("s_it") if act else None, "min_punto": round(min_punto, 1) if min_punto else None,
                     "faltan_min": round(eta_min) if eta_min else None,
                     "actual": f"punto {act['n']} · Q {act['Q']:.1f} m³/h" if act else ""})
    out = {"doe": p.get("doe", DOE), "hora": dt.datetime.now().isoformat(timespec="seconds"), "geometrias": geos, "workers": workers}
    if escribir:
        tmp = AQUI / "estado.json.tmp"   # atómico: el tablero no lee un JSON a medias
        tmp.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(AQUI / "estado.json")
        _eventos(viejo, out)
    return out


_RANGO = {}


def rango_cache() -> dict:
    if not _RANGO:
        _RANGO.update({r["id"]: r for r in rango.todas(plan=plan()["geometrias"])})
    return _RANGO


def _eventos(viejo: dict, nuevo: dict):
    """Cambios desde la última lectura → doe/eventos.log (una línea JSON por evento; la sesión de Claude avisa con ellos)."""
    antes = {g["id"]: g for g in viejo.get("geometrias", [])}
    ev = []
    for g in nuevo["geometrias"]:
        a = antes.get(g["id"], {})
        pa = {q["n"]: q["estado"] for q in a.get("puntos", [])}
        for q in g["puntos"]:
            if q["estado"] == "terminado" and pa.get(q["n"]) != "terminado":
                ev.append({"tipo": "punto", "id": g["id"], "n": q["n"], "Q": q["Q"], "H": q["H"], "eta": q["eta"]})
        if g["estado"] != a.get("estado"):
            ev.append({"tipo": "estado", "id": g["id"], "de": a.get("estado"), "a": g["estado"]})
    with open(AQUI / "eventos.log", "a", encoding="utf-8") as f:
        for x in ev:
            f.write(json.dumps({"hora": nuevo["hora"], **x}, ensure_ascii=False) + "\n")
    for x in ev:
        print("EVENTO", json.dumps(x, ensure_ascii=False))


def _evento(**x):
    with open(AQUI / "eventos.log", "a", encoding="utf-8") as f:
        f.write(json.dumps({"hora": dt.datetime.now().isoformat(timespec="seconds"), **x}, ensure_ascii=False) + "\n")


def ciclo_paso():
    """Una vuelta: estado; bomba terminada → Excel (fase «entregada»); si plan["auto"], worker libre → siguiente de la cola."""
    e = estado()
    p = plan()
    if p.get("pausa"):   # plan.json: solo leer estado (sin relanzar, entregar ni repartir); red inestable 2026-11-06
        return
    for g in e["geometrias"]:
        x = p["geometrias"][g["id"]]
        # sin_progreso: el log de DM lleva > 1 h quieto (PAT G014 2026-11-11: colgado lanzando un diseño, CPU 2 %)
        if g["estado"] in ("incompleta", "sin_progreso") and x.get("fase") == "corriendo":
            n = x.get("reintentos", 0)
            if n < 6:   # relanzar solo los que faltan; 6 por los cortes de red del 2026-11-05/06 (antes 2)
                try:
                    _evento(tipo="error", id=g["id"], que="incompleta", faltan=len(g["faltan"]), reintento=n + 1)
                    # solo antes de reiniciar: si preparar falla a medias (scp, PAT G008 2026-11-15), «retomar» no debe
                    # crear el estudio con todos los casos
                    p = plan(); p["geometrias"][g["id"]]["solo"] = g["faltan"]; guardar(p)
                    reiniciar(g["id"]); preparar(g["id"], x["worker"], solo=g["faltan"])
                    p = plan(); p["geometrias"][g["id"]]["reintentos"] = n + 1; guardar(p)
                    crear(g["id"]); lanzar(g["id"])
                    _evento(tipo="lanzada", id=g["id"], worker=x["worker"], solo=g["faltan"])
                except Exception as ex:
                    _evento(tipo="error", id=g["id"], que="relanzar", error=str(ex)[:200])
                continue
            g["estado"] = "terminado"   # agotados los reintentos: se entrega con los puntos que haya
        if g["estado"] == "terminado" and x.get("fase") == "corriendo":   # escenas fuera de DM antes de entregar
            try:
                lanzar_render(g["id"]); _evento(tipo="render", id=g["id"], worker=x["worker"])
            except Exception as ex:
                _evento(tipo="error", id=g["id"], que="render", error=str(ex)[:200])
            continue
        if x.get("fase") in ("render", "extraer") and not g.get(x["fase"] + "_fin"):
            continue
        if (g["estado"] == "terminado" or x.get("fase") == "extraer") and x.get("fase") != "entregada":
            try:
                out = traer(g["id"])
                p = plan(); p["geometrias"][g["id"]].update(fase="entregada", v2=True); guardar(p)
                _evento(tipo="entregada", id=g["id"], excel=str(out), faltan=len(g.get("faltan") or []))
                podar(g["id"])
                # el worker puede tener un servidor huérfano que retiene la licencia: dejarlo limpio para la siguiente
                ssh(x["worker"], r"Get-CimInstance Win32_Process | ? { $_.ExecutablePath -like '*STAR-CCM+*' -and "
                                 r"$_.Name -ne 'hydra_service.exe' } | % { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }")
            except Exception as ex:
                _evento(tipo="error", id=g["id"], que="traer", error=str(ex)[:200])
    if not p.get("auto"):
        return
    p = plan()
    ocupados = {x["worker"] for x in p["geometrias"].values() if x.get("fase") in ("preparada", "creada", "corriendo", "render", "extraer")}
    for gid, x in p["geometrias"].items():           # a medias (un despacho que falló): crear si falta y lanzar
        if x.get("fase") in ("preparada", "creada"):
            try:
                if x["fase"] == "preparada":
                    preparar(gid, x["worker"], solo=x.get("solo"), its=x.get("its"))   # rehace macros por si quedaron a medias
                    crear(gid)
                if plan()["geometrias"][gid]["fase"] == "creada":
                    lanzar(gid); _evento(tipo="lanzada", id=gid, worker=x["worker"])
            except Exception as ex:
                _evento(tipo="error", id=gid, que="retomar", worker=x["worker"], error=str(ex)[:200])
    cola = [r["id"] for r in rango.todas() if r["id"] not in p["geometrias"]]
    for ip in WORKERS:
        if ip in ocupados or ip in p.get("excluir", []):   # excluir: worker inestable (plan.json)
            continue
        # puntos a rehacer de este worker (plan.json "rehacer"): antes que las re-extracciones y la cola
        cand = [k for k, x in p["geometrias"].items() if x.get("worker") == ip and x.get("rehacer")]
        rh = min(cand, key=lambda k: len(p["geometrias"][k]["rehacer"].get("solo") or range(10)), default=None)   # sueltos primero
        if rh:
            try:
                rehacer(rh); _evento(tipo="lanzada", id=rh, worker=ip, que="rehacer")
            except Exception as ex:
                _evento(tipo="error", id=rh, que="rehacer", worker=ip, error=str(ex)[:200])
            continue
        # primero, las entregadas con la macro vieja de este worker: re-extraer y podar (libera ~9 GB cada una)
        vieja = next((k for k, x in p["geometrias"].items() if x.get("worker") == ip and x.get("fase") == "entregada" and not x.get("v2")), None)
        if vieja:
            try:
                lanzar_extraer(vieja); _evento(tipo="lanzada", id=vieja, worker=ip, que="extraer")
            except Exception as ex:
                _evento(tipo="error", id=vieja, que="extraer", worker=ip, error=str(ex)[:200])
                p = plan(); p["geometrias"][vieja]["v2"] = "fallo"; guardar(p)   # no reintentar en bucle
            continue
        if not cola:
            continue
        gid = cola.pop(0)
        try:
            preparar(gid, ip); crear(gid); lanzar(gid)
            _evento(tipo="lanzada", id=gid, worker=ip)
        except Exception as ex:
            _evento(tipo="error", id=gid, que="despachar", worker=ip, error=str(ex)[:200])


def tablero(puerto: int = 8770, cada: int = 60):
    """Sirve doe/ en http://localhost:8770/tablero.html y da una vuelta de ciclo_paso() cada `cada` s en un hilo."""
    import threading, http.server, functools

    def bucle():
        while True:
            try:
                ciclo_paso()
            except Exception as ex:
                print("ciclo falló:", ex)
            time.sleep(cada)
    threading.Thread(target=bucle, daemon=True).start()
    h = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(AQUI))
    h.log_message = lambda *a: None
    print(f"tablero: http://localhost:{puerto}/tablero.html")
    http.server.ThreadingHTTPServer(("127.0.0.1", puerto), h).serve_forever()


def traer(gid: str) -> pathlib.Path | None:
    """Baja resultados.json y reports/ de cada diseño terminado (los .sim y las imágenes se quedan en el worker) y arma
    <carpeta de la bomba>\\DOE\\<id>_barrido.xlsx."""
    import excel
    p = plan(); gid = next(k for k in p["geometrias"] if k.startswith(gid)); e = p["geometrias"][gid]
    lst = ssh(e["worker"], f"Get-ChildItem '{e['dir']}' -Recurse -Filter resultados.json | ? {{ $_.FullName -notmatch '_intento' }} | % {{"
                           f" $d=$_.DirectoryName; $d + '|' + ((Get-ChildItem \"$d\\images\" -Filter *.png | % FullName) -join ';') }}", timeout=180)
    local = AQUI / "_traido" / gid
    for linea in filter(None, lst.splitlines()):
        d, imgs = linea.split("|", 1)
        dst = local / pathlib.PureWindowsPath(d).name
        dst.mkdir(parents=True, exist_ok=True)
        scp(dst / "resultados.json", e["worker"], f"{d}\\resultados.json".replace("\\", "/"), bajar=True)
        try:
            scp(dst, e["worker"], f"{d}\\reports".replace("\\", "/"), bajar=True)
        except subprocess.CalledProcessError:
            pass
        (dst / "imagenes.json").write_text(json.dumps([i for i in imgs.split(";") if i], ensure_ascii=False), encoding="utf-8")
    if not local.exists():
        print("sin diseños terminados todavía"); return None
    g = rango_cache()[gid]
    out = excel.armar(gid, local, g, pathlib.Path(e["carpeta"]) / "DOE" / f"{gid}_barrido.xlsx", e["worker"])
    e["excel"] = str(out); guardar(p)
    print("Excel:", out)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd")
    ap.add_argument("gid", nargs="?")
    ap.add_argument("--worker", default=WORKERS[0])
    a = ap.parse_args()
    if a.cmd == "preparar":
        preparar(a.gid, a.worker)
    elif a.cmd == "crear":
        crear(a.gid)
    elif a.cmd == "lanzar":
        lanzar(a.gid)
    elif a.cmd == "estado":
        e = estado()
        for g in e["geometrias"]:
            print(f'{g["id"]:<14} {g["worker"]:<15} {g["estado"]:<12} {100 * g["avance"]:5.1f} %  {g["actual"]}')
    elif a.cmd == "reiniciar":
        reiniciar(a.gid)
    elif a.cmd == "traer":
        traer(a.gid)
    elif a.cmd == "podar":
        podar(a.gid)
    elif a.cmd == "tablero":
        tablero()
    else:
        sys.exit(f"comando desconocido: {a.cmd}")


if __name__ == "__main__":
    main()
