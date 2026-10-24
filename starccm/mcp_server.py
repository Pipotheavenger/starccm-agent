"""MCP para operar Simcenter STAR-CCM+ (2410, Windows) desde Claude Code.

Arquitectura: UN servidor de STAR-CCM+ vivo con el .sim en memoria (starccm+ -server -port P). Cada
tool inyecta una macro Java con un cliente batch (`starccm+ -host localhost:P -batch M.java -noexit`)
y lee lo que la macro imprimió con sim.println entre los marcadores AGENT_BEGIN/AGENT_END.
No se recarga el .sim entre pasos. Claude nunca resuelve física a mano: STAR-CCM+ es el solver.

Tools (11): server_start, server_stop, server_status, inspect, run_java, iterate, export_scene, save,
recipe_search, recipe_save, docs_search.

Uso:   python mcp_server.py            (stdio, lo lanza Claude Code desde .mcp.json)
       python mcp_server.py --selftest (starccm+ falso de tests/, sin licencia, ~5 s)

Env (se leen también de starccm/.env y de ~/.starccm-agent.env, formato KEY=VALUE):
  STARCCM_HOME     carpeta STAR-CCM+<ver> (default: la más nueva en C:\\Program Files\\Siemens)
  STARCCM_EXE      lanzador (default: $STARCCM_HOME/star/bin/starccm+.bat; un .py = falso de pruebas)
  STARCCM_PODKEY   clave Power-on-Demand. NUNCA en código, recetas, logs ni commits.
  STARCCM_LICPATH  servidor de licencias (default 1999@flex.cd-adapco.com)
  STARCCM_PORT     puerto del servidor (default 47827)
  STARCCM_NP       procesos paralelos (default: núcleos - 2)
  STARCCM_IDLE_MIN minutos sin tools antes de guardar y apagar (default 30; PoD cobra por hora)
  STARCCM_PRECOMPILE 1 (default) compila la macro con el javac del JDK de STAR-CCM+ antes de
                   inyectarla: un error de sintaxis o de nombre de clase vuelve en 2 s sin tocar
                   el servidor. 0 para saltarlo.

Carpetas (todas dentro de starccm/): sims/ (.sim de trabajo, nunca el original del usuario),
macros/ (cada macro inyectada, con su salida .out), cases/<caso>/ (cad, reportes, imágenes,
RESUMEN.md), recipes/ (snippets Java que funcionaron). Estado del servidor en .server.json.
"""
from __future__ import annotations

import glob
import html
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
SIMS = HERE / "sims"
MACROS = HERE / "macros"
CASES = HERE / "cases"
RECIPES = HERE / "recipes"
STATE_FILE = HERE / ".server.json"
AGENT_LOG = HERE / "agent.log"
KEEP_MACROS = 200


# ----------------------------------------------------------------------------- configuración
def _load_env_files() -> None:
    """KEY=VALUE de starccm/.env y ~/.starccm-agent.env; el entorno real manda."""
    for p in (HERE / ".env", Path.home() / ".starccm-agent.env"):
        if not p.is_file():
            continue
        for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.strip().removeprefix("export ").strip()
            v = v.strip().strip('"').strip("'")
            os.environ.setdefault(k, v)


_load_env_files()


def _find_home() -> Path | None:
    env = os.environ.get("STARCCM_HOME")
    if env:
        return Path(env)
    hits = sorted(glob.glob(r"C:\Program Files\Siemens\*\STAR-CCM+*"))
    return Path(hits[-1]) if hits else None


HOME = _find_home()
EXE = os.environ.get("STARCCM_EXE") or (str(HOME / "star" / "bin" / "starccm+.bat") if HOME else "starccm+")
PORT = int(os.environ.get("STARCCM_PORT", "47827"))
NP = int(os.environ.get("STARCCM_NP", str(max(1, (os.cpu_count() or 2) - 2))))
IDLE_MIN = float(os.environ.get("STARCCM_IDLE_MIN", "30"))
LICPATH = os.environ.get("STARCCM_LICPATH", "1999@flex.cd-adapco.com")
PRECOMPILE = os.environ.get("STARCCM_PRECOMPILE", "1") == "1"
DOC_DIR = (HOME / "doc" / "client" / "html") if HOME else None


def _starccm_cmd() -> list[str]:
    """Comando base. Un STARCCM_EXE .py es el falso de pruebas (python -I)."""
    if EXE.lower().endswith(".py"):
        return [sys.executable, "-I", EXE]
    return [EXE]


def _lic_flags() -> list[str]:
    key = os.environ.get("STARCCM_PODKEY", "")
    return ["-power", "-podkey", key, "-licpath", LICPATH] if key else []


def _redact(s: str) -> str:
    key = os.environ.get("STARCCM_PODKEY", "")
    return s.replace(key, "***PODKEY***") if key else s


def _javac() -> tuple[str, str] | None:
    """(javac, classpath) del JDK que trae STAR-CCM+, o None si no está o el exe es el falso."""
    if not HOME or not PRECOMPILE or EXE.lower().endswith(".py"):
        return None
    jdks = sorted(glob.glob(str(HOME.parent / "jdk" / "*" / "jdk*" / "bin" / "javac.exe")))
    if not jdks:
        return None
    plat = HOME / "star" / "lib" / "java" / "platform"
    cp = os.pathsep.join(str(plat / d / "*") for d in ("modules/ext", "modules", "core", "lib"))
    return jdks[-1], cp


# ----------------------------------------------------------------------------- estado
_lock = threading.RLock()
_last_tool = time.time()
_proc: subprocess.Popen | None = None


def _state() -> dict:
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_state(d: dict) -> None:
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(d, indent=1, ensure_ascii=False), encoding="utf-8")
    tmp.replace(STATE_FILE)


def _pid_alive(pid: int) -> bool:
    if not pid:
        return False
    if os.name == "nt":
        # OpenProcess + WaitForSingleObject: microsegundos (tasklist costaba ~0,19 s por sondeo de la UI)
        import ctypes
        k32 = ctypes.windll.kernel32
        k32.OpenProcess.restype = ctypes.c_void_p
        k32.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        k32.CloseHandle.argtypes = [ctypes.c_void_p]
        h = k32.OpenProcess(0x00100000, False, int(pid))  # SYNCHRONIZE
        if not h:
            return False
        try:
            return k32.WaitForSingleObject(h, 0) == 0x102  # WAIT_TIMEOUT: sigue corriendo
        finally:
            k32.CloseHandle(h)
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _pid_is_ours(pid: int) -> bool:
    """Evita matar un proceso ajeno si Windows reasignó el PID guardado (el PID es el del .bat/starccm+)."""
    if os.name != "nt":
        return True
    out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"], capture_output=True, text=True).stdout
    m = re.match(r'"([^"]+)"', out.strip())
    return bool(m) and re.search(r"cmd|star|java|python|mpi|ccm|hydra|smpd", m.group(1), re.I) is not None


def _port_open(port: int, host: str = "127.0.0.1") -> bool:
    try:
        with socket.create_connection((host, port), timeout=1.0):
            return True
    except OSError:
        return False


def _kill_tree(pid: int) -> None:
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)
    else:
        try:
            os.kill(pid, 9)
        except OSError:
            pass


# ----------------------------------------------------------------------------- ejecución remota (servidor Linux)
# El MCP sigue en este PC. En modo «server» (elegido en ui/ → .ui-settings.json, o STARCCM_RUN_WHERE=server, o el
# argumento where de server_start) el solver corre en el servidor por SSH con la llave del usuario:
#   - starccm+ -server en el servidor (licencia y STARCCM_HOME de su ~/.starccm-agent.env: la clave no sale del servidor)
#   - cada macro se sube por stdin, se inyecta con el cliente batch DEL SERVIDOR (2502; el de 2410 no conecta) y su
#     stdout vuelve EN VIVO al .out local (la pestaña Salida de ui/ funciona igual)
#   - las rutas de starccm/ dentro de la macro se traducen a REMOTE_DIR, y lo que la macro escriba en cases/ o
#     macros/ (PNG, CSV, EnSight) se trae de vuelta con un tar por SSH al terminar
#   - el .sim vive en REMOTE_DIR/sims (subirlo cuesta ~11 min por 158 MB): se sube solo si falta o cambió de tamaño
SSH_HOST = os.environ.get("STARCCM_SSH", "investigacion@172.17.76.78")
REMOTE_DIR = os.environ.get("STARCCM_REMOTE_DIR", "/home/investigacion/starccm-agent")
SETTINGS_FILE = HERE / ".ui-settings.json"
_SSH_OPTS = ["-o", "BatchMode=yes", "-o", "ConnectTimeout=10", "-o", "ServerAliveInterval=30", "-o", "StrictHostKeyChecking=accept-new", "-o", "LogLevel=ERROR"]
_REMOTE_ENV = "set -a; . ~/.starccm-agent.env; set +a; "  # STARCCM_HOME, STARCCM_PODKEY, STARCCM_LICPATH, STARCCM_NP
_REMOTE_EXE = '"$STARCCM_HOME/star/bin/starccm+"'
_REMOTE_LIC = '-power -podkey "$STARCCM_PODKEY" -licpath "$STARCCM_LICPATH"'


def run_where() -> str:
    """local | server: env STARCCM_RUN_WHERE manda; si no, lo elegido en la interfaz."""
    w = os.environ.get("STARCCM_RUN_WHERE", "").strip().lower()
    if w in ("local", "server"):
        return w
    try:
        w = json.loads(SETTINGS_FILE.read_text(encoding="utf-8")).get("run_where")
    except Exception:  # noqa: BLE001
        w = None
    return w if w in ("local", "server") else "local"


def _ssh_cmd(remote_cmd: str) -> list[str]:
    return [shutil.which("ssh") or "ssh", *_SSH_OPTS, SSH_HOST, remote_cmd]


def _ssh(remote_cmd: str, timeout: float = 60, input: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(_ssh_cmd(remote_cmd), capture_output=True, text=True, timeout=timeout, input=input,
                          encoding="utf-8", errors="replace")


def _rpath(p: str | os.PathLike) -> str:
    """Ruta local dentro de starccm/ -> ruta en el servidor (misma estructura bajo REMOTE_DIR)."""
    rel = Path(p).resolve().relative_to(HERE.resolve())
    return REMOTE_DIR + "/" + rel.as_posix()


def _translate(body: str) -> str:
    """Reescribe en el Java las rutas de starccm/ (con barra o barra invertida, en cualquier caja de letra de unidad) a REMOTE_DIR."""
    loc = _jpath(HERE.resolve())
    rx = re.escape(loc).replace("/", r"[/\\]+") + r"""([^"'\s]*)"""
    return re.sub(rx, lambda m: REMOTE_DIR + re.sub(r"[/\\]+", "/", m.group(1)), body, flags=re.I)


def _qs(s: str) -> str:
    return "'" + s.replace("'", "'\"'\"'") + "'"


_alive_cache: dict = {}


def _remote_alive(st: dict) -> bool:
    """¿Sigue vivo el starccm+ -server remoto y escucha su puerto? (cacheado 8 s: la UI sondea cada 5 s)."""
    key = (st.get("pid"), st.get("port"))
    hit = _alive_cache.get(key)
    if hit and time.time() - hit[0] < 8:
        return hit[1]
    try:
        r = _ssh(f"kill -0 {int(st['pid'])} 2>/dev/null && (exec 3<>/dev/tcp/127.0.0.1/{int(st['port'])}) 2>/dev/null && echo VIVO", timeout=20)
        ok = "VIVO" in r.stdout
    except Exception:  # noqa: BLE001
        ok = False
    _alive_cache[key] = (time.time(), ok)
    return ok


def alive(st: dict | None = None) -> bool:
    """Servidor vivo, local o remoto. La usan las tools y ui/server.py."""
    st = _state() if st is None else st
    if not st.get("pid"):
        return False
    if st.get("where") == "server":
        return _remote_alive(st)
    return _pid_alive(st["pid"]) and _port_open(st.get("port", 0))


def _pull_new(marker: str) -> list[str]:
    """Trae del servidor lo que la macro escribió en cases/ y macros/ (más nuevo que marker) a las mismas rutas locales."""
    import tarfile
    find = (f"cd {_qs(REMOTE_DIR)} && find cases macros -type f -newer {_qs(marker)} ! -name '*.java' ! -name '*.class' "
            f"! -name '.mark_*' 2>/dev/null")
    r = _ssh(find, timeout=60)
    files = [f for f in r.stdout.splitlines() if f and ".." not in f]
    if not files:
        return []
    p = subprocess.Popen(_ssh_cmd(f"cd {_qs(REMOTE_DIR)} && tar cf - " + " ".join(_qs(f) for f in files)), stdout=subprocess.PIPE)
    got = []
    with tarfile.open(fileobj=p.stdout, mode="r|") as tf:
        for m in tf:
            dst = (HERE / m.name).resolve()
            if not m.isfile() or HERE.resolve() not in dst.parents:
                continue
            dst.parent.mkdir(parents=True, exist_ok=True)
            with tf.extractfile(m) as fi, open(dst, "wb") as fo:
                shutil.copyfileobj(fi, fo)
            got.append(m.name)
    p.wait(timeout=60)
    return got


def _local_inputs(body: str) -> list[Path]:
    """Archivos de starccm/ que la macro menciona y existen en este PC (CAD de cases/<caso>/cad, CSV de entrada…).
    El .sim no: lo gestiona server_start."""
    loc = _jpath(HERE.resolve())
    rx = re.escape(loc).replace("/", r"[/\\]+") + r"""([^"'\s]*)"""
    out = []
    for m in re.finditer(rx, body, flags=re.I):
        rel = re.sub(r"[/\\]+", "/", m.group(1)).lstrip("/")
        f = (HERE / rel).resolve()
        if rel and f.is_file() and HERE.resolve() in f.parents and f.suffix.lower() not in (".sim", ".java", ".class") and f not in out:
            out.append(f)
    return out


def _push_inputs(files: list[Path]) -> list[str]:
    """Sube al servidor (tar por SSH) los que faltan allí o tienen otro tamaño. Devuelve las rutas subidas."""
    import io
    import tarfile
    if not files:
        return []
    rels = [f.relative_to(HERE.resolve()).as_posix() for f in files]
    r = _ssh(f"cd {_qs(REMOTE_DIR)} && for f in " + " ".join(_qs(x) for x in rels) + '; do printf "%s\\t%s\\n" "$(stat -c %s "$f" 2>/dev/null || echo -1)" "$f"; done', timeout=60)
    sizes = {}
    for ln in r.stdout.splitlines():
        if "\t" in ln:
            n, f = ln.split("\t", 1)
            sizes[f] = int(n) if n.lstrip("-").isdigit() else -1
    need = [(f, rel) for f, rel in zip(files, rels) if sizes.get(rel, -1) != f.stat().st_size]
    if not need:
        return []
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tf:
        for f, rel in need:
            tf.add(str(f), arcname=rel)
    up = subprocess.run(_ssh_cmd(f"mkdir -p {_qs(REMOTE_DIR)} && cd {_qs(REMOTE_DIR)} && tar xf -"), input=buf.getvalue(),
                        capture_output=True, timeout=3600)
    if up.returncode != 0:
        raise RuntimeError(f"no pude subir entradas al servidor: {up.stderr.decode('utf-8', 'replace')[-300:]}")
    return [rel for _, rel in need]


def _inject_remote(st: dict, src: Path, tag: str, timeout: float) -> tuple[int, str, bool, list[str]]:
    """Sube la macro, la corre con el cliente batch del servidor con su stdout en vivo al .out local, y trae lo nuevo."""
    raw = src.read_text(encoding="utf-8")
    pushed = _push_inputs(_local_inputs(raw))  # CAD y demás entradas que el servidor aún no tiene
    if pushed:
        _log(f"remoto: subidos {len(pushed)} archivo(s): {', '.join(pushed[:6])}")
    body = _translate(raw)
    rdir = f"{REMOTE_DIR}/macros"
    rsrc = f"{rdir}/{src.name}"
    marker = f"{rdir}/.mark_{tag}"
    # carpetas de destino que la macro vaya a usar (PNG, CSV, .case): el servidor no tiene las de este PC
    dirs = {REMOTE_DIR + "/" + d for d in ("sims", "macros", "cases")}
    for m in re.finditer(re.escape(REMOTE_DIR) + r"/[^\"'\s]+", body):
        dirs.add(m.group(0).rsplit("/", 1)[0])
    prep = "mkdir -p " + " ".join(_qs(d) for d in sorted(dirs)) + f" && cat > {_qs(rsrc)} && touch {_qs(marker)}"
    r = _ssh(prep, timeout=60, input=body)
    if r.returncode != 0:
        raise RuntimeError(f"no pude subir la macro al servidor: {r.stderr.strip()[-300:]}")
    run = (_REMOTE_ENV + f"cd {_qs(rdir)} && {_REMOTE_EXE} -host localhost:{int(st['port'])} -batch {_qs(src.name)} -noexit {_REMOTE_LIC}; "
           f"rc=$?; rm -f {_qs(marker)}.done; exit $rc")
    killed = False
    with open(src.with_suffix(".out"), "w", encoding="utf-8", errors="replace") as fo:
        p = subprocess.Popen(_ssh_cmd(run), stdout=fo, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")
        try:
            _, err = p.communicate(timeout=timeout)
            rc = p.returncode
        except subprocess.TimeoutExpired:
            _ssh(f"pkill -f {_qs(src.name)}", timeout=30)  # el cliente batch remoto de ESTA macro
            p.kill()
            rc, err, killed = -1, f"timeout {timeout}s: cliente batch remoto matado; la salida puede estar incompleta", True
    try:
        pulled = _pull_new(marker)
    except Exception as e:  # noqa: BLE001
        pulled, err = [], (err or "") + f"\n[pull] {e}"
    _ssh(f"rm -f {_qs(marker)}", timeout=30)
    return rc, err or "", killed, pulled


def _touch() -> None:
    """Marca actividad en memoria y en disco (mtime de .server.json): el watchdog de cualquier proceso la ve."""
    global _last_tool
    _last_tool = time.time()
    try:
        os.utime(STATE_FILE, None)
    except OSError:
        pass


def last_activity() -> float | None:
    """Última actividad medida en DISCO (la ven todos los procesos: MCP de Claude Code, MCP del chat de la UI, UI):
    la macro más reciente (.java o su .out, que crece en vivo mientras itera) o .server.json."""
    ts = []
    if MACROS.is_dir():
        ts += [p.stat().st_mtime for p in MACROS.glob("Agent_*") if p.is_file()]
    if STATE_FILE.is_file():
        ts.append(STATE_FILE.stat().st_mtime)
    return max(ts) if ts else None


def idle_seconds() -> float:
    last = last_activity()
    return time.time() - max(last or 0, _last_tool)


def _idle_stop() -> None:
    st = _state()
    if not (st.get("pid") and idle_seconds() > IDLE_MIN * 60 and alive(st)):
        return
    with _lock:  # si una tool de este proceso tenía el candado, se reevalúa al liberarse
        if idle_seconds() <= IDLE_MIN * 60:
            return
        r = server_stop(save=True)
        if r.get("save_error"):
            _log(f"watchdog: guardado falló, no apago: {r['save_error']}")


def _idle_watchdog() -> None:
    """Apagado por inactividad: PoD cobra por hora de sesión. Lo corren el MCP y la UI (proceso de larga vida)."""
    while True:
        time.sleep(60)
        try:
            _idle_stop()
        except Exception as e:  # noqa: BLE001
            _log(f"watchdog: {e}")


_wd_started = False


def start_watchdog() -> None:
    global _wd_started
    if not _wd_started:
        _wd_started = True
        threading.Thread(target=_idle_watchdog, daemon=True).start()


def _log(msg: str) -> None:
    with open(AGENT_LOG, "a", encoding="utf-8") as f:
        f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S} {_redact(msg)}\n")


# ----------------------------------------------------------------------------- macro java
IMPORTS = [
    "star.common.*", "star.base.neo.*", "star.base.report.*", "star.meshing.*", "star.flow.*",
    "star.kwturb.*", "star.vis.*", "star.cadmodeler.*", "star.prismmesher.*", "star.surfacewrapper.*",
    "star.material.*", "star.segregatedflow.*", "star.turbulence.*", "star.motion.*", "star.metrics.*",
    "star.resurfacer.*", "star.dualmesher.*",
    "java.util.*", "java.io.*",
]


def _wrap(body: str, imports: str, tag: str) -> str:
    extra = [i.strip().rstrip(";").removeprefix("import ").strip()
             for i in imports.replace("\n", ",").split(",") if i.strip()]
    imps = "\n".join(f"import {i};" for i in IMPORTS + [e for e in extra if e not in IMPORTS])
    cls = f"Agent_{tag}"
    return f"""{imps}

public class {cls} extends StarMacro {{
  public void execute() {{
    Simulation sim = getActiveSimulation();
    sim.println("AGENT_BEGIN {tag}");
    try {{
{body}
    }} catch (Exception e) {{
      StringWriter sw = new StringWriter();
      e.printStackTrace(new PrintWriter(sw));
      sim.println("AGENT_ERROR: " + e);
      sim.println(sw.toString());
    }}
    sim.println("AGENT_END {tag}");
  }}
}}
"""


def _prune_macros() -> None:
    files = sorted(MACROS.glob("Agent_*"), key=lambda p: p.stat().st_mtime)
    for p in files[:-KEEP_MACROS]:
        p.unlink(missing_ok=True)


def _precompile(src: Path) -> str | None:
    """Compila la macro con javac. Devuelve el texto del error o None si compila (o no hay javac)."""
    jc = _javac()
    if not jc:
        return None
    out = MACROS / ".classes"
    out.mkdir(exist_ok=True)
    r = subprocess.run([jc[0], "-nowarn", "-proc:none", "-cp", jc[1], "-d", str(out), str(src)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
    if r.returncode != 0:
        return (r.stderr or r.stdout)[-3000:]
    return None


def _inject(body: str, imports: str = "", timeout: float = 3600) -> dict:
    """Escribe la macro, la ejecuta con el cliente batch contra el servidor y devuelve su salida."""
    st = _state()
    remote = st.get("where") == "server"
    if not st.get("pid") or not (alive(st) if remote else _pid_alive(st["pid"])):
        raise RuntimeError("No hay servidor de STAR-CCM+ vivo. Usa server_start primero.")
    MACROS.mkdir(exist_ok=True)
    tag = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
    src = MACROS / f"Agent_{tag}.java"
    src.write_text(_wrap(body, imports, tag), encoding="utf-8")
    t0 = time.time()
    killed = False
    err_c = _precompile(src)
    if err_c:
        # el .out marca la macro como terminada (la pestaña Salida de ui/ no la da por «en marcha»)
        src.with_suffix(".out").write_text(_redact(f"javac: no compila\n{err_c}\n--- stderr\n"), encoding="utf-8")
        _touch()
        return {"ok": False, "stdout": "", "stderr": "", "exception": "javac: no compila",
                "trace": err_c, "seconds": round(time.time() - t0, 2), "macro": str(src), "returncode": 1}
    pulled: list[str] = []
    if remote:
        rc, err, killed, pulled = _inject_remote(st, src, tag, timeout)
        if pulled:
            _log(f"remoto: {len(pulled)} archivo(s) traídos del servidor: {', '.join(pulled[:6])}")
        out_file = src.with_suffix(".out")
    else:
        rc, err, killed, out_file = _inject_local(st, src, timeout)
    return _inject_result(st, src, tag, t0, rc, err, killed, out_file, pulled)


def _inject_local(st: dict, src: Path, timeout: float) -> tuple[int, str, bool, Path]:
    killed = False
    cmd = _starccm_cmd() + ["-host", f"localhost:{st['port']}", "-batch", str(src), "-noexit"] + _lic_flags()
    # El stdout del cliente va EN VIVO a <macro>.out (la pestaña Salida de ui/ lo sigue mientras itera);
    # una macro está en marcha mientras su .out no contiene AGENT_END. La UI enmascara la clave al leerlo.
    out_file = src.with_suffix(".out")
    with open(out_file, "w", encoding="utf-8", errors="replace") as fo:
        p = subprocess.Popen(cmd, stdout=fo, stderr=subprocess.PIPE, text=True, cwd=str(MACROS),
                             encoding="utf-8", errors="replace")
        try:
            _, err = p.communicate(timeout=timeout)
            rc = p.returncode
        except subprocess.TimeoutExpired:
            # subprocess.run solo mataba cmd.exe y esperaba al java hijo: se mata el árbol entero
            _kill_tree(p.pid)
            try:
                _, e2 = p.communicate(timeout=15)
            except Exception:  # noqa: BLE001
                e2 = ""
            rc, err = -1, f"timeout {timeout}s: cliente batch (pid {p.pid}) matado; la salida puede estar incompleta. {e2 or ''}"
            killed = True
    return rc, err, killed, out_file


def _inject_result(st: dict, src: Path, tag: str, t0: float, rc: int, err: str, killed: bool, out_file: Path, pulled: list[str]) -> dict:
    out = out_file.read_text(encoding="utf-8", errors="replace")
    secs = round(time.time() - t0, 2)
    # Salida de la macro: entre marcadores, del stdout del cliente; si no, del log del servidor.
    text = _between(out, tag)
    if text is None:
        text = _between(_tail_log(st), tag)
    err_match = re.search(r"AGENT_ERROR: (.*)", text or out)
    out_file.write_text(_redact(out + ("\n--- stderr\n" + err if err else "")), encoding="utf-8")
    _prune_macros()
    _touch()
    return {
        "ok": rc == 0 and not err_match and text is not None,
        "stdout": text if text is not None else _redact(out[-4000:]),
        "stderr": _redact(err[-2000:]) if err else "",
        "exception": err_match.group(1).strip() if err_match else None,
        "trace": _trace(text) if err_match else None,
        "seconds": secs,
        "macro": str(src),
        "returncode": rc,
        **({"client_killed": True} if killed else {}),
        **({"where": "server", "pulled": pulled} if st.get("where") == "server" else {}),
    }


def _between(out: str, tag: str) -> str | None:
    m = re.search(rf"AGENT_BEGIN {tag}\r?\n(.*?)AGENT_END {tag}", out or "", re.S)
    return m.group(1).strip() if m else None


def _trace(text: str) -> str:
    m = re.search(r"AGENT_ERROR: .*?\n(.*)", text or "", re.S)
    return (m.group(1).strip()[:3000]) if m else ""


def _tail_log(st: dict, n: int = 200_000) -> str:
    if st.get("where") == "server" and st.get("rlog"):  # log del servidor remoto; se deja copia local para ui/
        try:
            txt = _ssh(f"tail -c {int(n)} {_qs(st['rlog'])}", timeout=30).stdout
            if st.get("log"):
                Path(st["log"]).write_text(_redact(txt[-200_000:]), encoding="utf-8")
            return txt
        except Exception:  # noqa: BLE001
            return ""
    p = Path(st.get("log") or "")
    if not p.is_file():
        return ""
    with open(p, "rb") as f:
        f.seek(0, 2)
        size = f.tell()
        f.seek(max(0, size - n))
        return f.read().decode("utf-8", "replace")


# ----------------------------------------------------------------------------- MCP
try:
    from mcp.server.fastmcp import FastMCP  # mcp 1.x
except ImportError:  # mcp 2.x
    from mcp.server.mcpserver import MCPServer as FastMCP  # type: ignore

mcp = FastMCP("starccm")


@mcp.tool()
def server_start(sim_path: str = "", name: str = "", where: str = "") -> dict:
    """Levanta el servidor de STAR-CCM+ (o reutiliza el vivo). sim_path: .sim a abrir; se copia a
    sims/<name>.sim y se trabaja sobre la copia, nunca sobre el original. Vacío = simulación nueva.
    Devuelve host:port, pid, sim y segundos de arranque. Un solo servidor a la vez.
    where: local (este PC) | server (servidor Linux por SSH) | vacío = lo elegido en la interfaz (ui/)."""
    with _lock:
        _touch()
        st = _state()
        if st.get("pid") and alive(st):
            return {"reused": True, **st}
        where = (where or run_where()).strip().lower()
        if where == "server":
            return _server_start_remote(sim_path, name, st)
        if st.get("pid"):
            _log(f"servidor {st.get('pid')} muerto; limpio .server.json")
            STATE_FILE.unlink(missing_ok=True)
        SIMS.mkdir(exist_ok=True)
        sim = None
        if sim_path:
            srcp = Path(sim_path)
            if not srcp.is_file():
                raise FileNotFoundError(f"No existe {sim_path}")
            dst = SIMS / f"{name or srcp.stem}.sim"
            if srcp.resolve() != dst.resolve():
                shutil.copy2(srcp, dst)
            sim = dst
        elif name:
            sim = SIMS / f"{name}.sim"  # se creará con save()
        if _port_open(PORT):
            raise RuntimeError(f"Puerto {PORT} ocupado por otro proceso; cambia STARCCM_PORT o libéralo.")
        log = SIMS / f"{(sim.stem if sim else 'nuevo')}.server.log"
        cmd = _starccm_cmd() + ["-server", "-port", str(PORT), "-np", str(NP)] + _lic_flags()
        if sim and sim.is_file():
            cmd += ["-load", str(sim)]
        t0 = time.time()
        logf = open(log, "ab")
        flags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
        global _proc
        _proc = subprocess.Popen(cmd, stdout=logf, stderr=subprocess.STDOUT, cwd=str(SIMS), creationflags=flags)
        st = {"pid": _proc.pid, "port": PORT, "host": "localhost", "sim": str(sim) if sim else None,
              "log": str(log), "started": datetime.now().isoformat(timespec="seconds"), "np": NP,
              "cmd": _redact(" ".join(cmd))}
        _write_state(st)
        deadline = t0 + 600
        while time.time() < deadline:
            if _proc.poll() is not None:
                tail = _redact(_tail_log(st, 6000))
                STATE_FILE.unlink(missing_ok=True)
                raise RuntimeError(f"El servidor terminó con código {_proc.returncode} a los "
                                   f"{time.time()-t0:.0f}s. Cola del log:\n{tail[-3000:]}")
            if _port_open(PORT) and "Server::start" in _tail_log(st, 20000):
                break
            time.sleep(1)
        else:
            _kill_tree(_proc.pid)
            STATE_FILE.unlink(missing_ok=True)
            raise RuntimeError("El servidor no abrió el puerto en 600 s")
        st["startup_seconds"] = round(time.time() - t0, 1)
        _write_state(st)
        # Autoguardado en batch apagado: en 2410 viene activo y deja <sim>@meshed.sim y @NNNNN.sim
        # (gigas en una bomba). (Simulation no tiene setPresentationName: el nombre lo da save().)
        init = ("AutoSave as = sim.getSimulationIterator().getAutoSave();\n"
                "as.setAutoSaveBatch(false); as.setAutoSaveMesh(false);\n"
                'sim.println("INIT autosave off");\n')
        try:
            st["init"] = _inject(init, timeout=600)["stdout"][-200:]
        except Exception as e:  # noqa: BLE001
            st["init"] = f"init falló: {e}"
        _write_state(st)
        _log(f"servidor pid={st['pid']} puerto={PORT} sim={sim} en {st['startup_seconds']}s; {st['init']}")
        return st


def _server_start_remote(sim_path: str, name: str, old: dict) -> dict:
    """server_start en el servidor Linux: sube el .sim si falta (o cambió de tamaño) y lanza starccm+ -server con nohup."""
    if old.get("pid"):
        _log(f"servidor {old.get('pid')} ({old.get('where', 'local')}) muerto; limpio .server.json")
        STATE_FILE.unlink(missing_ok=True)
    SIMS.mkdir(exist_ok=True)
    t0 = time.time()
    chk = _ssh(_REMOTE_ENV + f'mkdir -p {_qs(REMOTE_DIR)}/sims {_qs(REMOTE_DIR)}/macros {_qs(REMOTE_DIR)}/cases && test -x {_REMOTE_EXE} && '
               f'test -n "$STARCCM_PODKEY" && echo NP=${{STARCCM_NP:-14}} && (exec 3<>/dev/tcp/127.0.0.1/{PORT}) 2>/dev/null && echo PUERTO_OCUPADO; true', timeout=30)
    if "NP=" not in chk.stdout:
        raise RuntimeError(f"El servidor {SSH_HOST} no está listo (SSH, STARCCM_HOME o STARCCM_PODKEY en ~/.starccm-agent.env): "
                           f"{(chk.stderr or chk.stdout).strip()[-300:]}. Comprueba con: bash vm/remote_check.sh")
    if "PUERTO_OCUPADO" in chk.stdout:
        raise RuntimeError(f"Puerto {PORT} ocupado en {SSH_HOST}: ¿quedó un starccm+ vivo? (bash vm/remote_check.sh)")
    np_ = int(re.search(r"NP=(\d+)", chk.stdout).group(1))
    sim = rsim = None
    uploaded = None
    if sim_path or name:
        srcp = Path(sim_path) if sim_path else None
        if srcp is not None and not srcp.is_file():
            raise FileNotFoundError(f"No existe {sim_path}")
        sim = SIMS / f"{name or srcp.stem}.sim"
        rsim = _rpath(sim)
        if srcp is not None:
            if srcp.resolve() != sim.resolve():
                shutil.copy2(srcp, sim)
            # tamaño y fecha del remoto: se sube SOLO si falta allí o si el del PC es más nuevo (el remoto puede tener
            # más trabajo guardado por save/server_stop en el servidor: nunca se pisa con uno más viejo)
            info = (_ssh(f"stat -c '%s %Y' {_qs(rsim)} 2>/dev/null || echo '-1 0'", timeout=30).stdout.split() or ["-1", "0"])[-2:]
            rsize, rmtime = int(info[0]), float(info[1])
            lsize, lmtime = sim.stat().st_size, sim.stat().st_mtime
            if rsize < 0 or (rsize != lsize and lmtime > rmtime + 5):  # lento: ~0,24 MB/s medido
                if rsize >= 0:
                    _ssh(f"cp -p {_qs(rsim)} {_qs(rsim + '.antes')}", timeout=600)  # copia del remoto por si acaso
                t1 = time.time()
                r = subprocess.run([shutil.which("scp") or "scp", *_SSH_OPTS, str(sim), f"{SSH_HOST}:{rsim}"],
                                   capture_output=True, text=True, timeout=7200)
                if r.returncode != 0:
                    raise RuntimeError(f"scp del .sim falló: {r.stderr.strip()[-300:]}")
                uploaded = round(time.time() - t1, 1)
    stem = sim.stem if sim else "nuevo"
    rlog = f"{REMOTE_DIR}/sims/{stem}.server.log"
    load = f"-load {_qs(rsim)}" if rsim and sim and sim.is_file() else ""
    # «cd X && nohup … &» mandaría al fondo la lista entera: esa subcapa sin redirigir retiene el stdout del SSH y lo cuelga
    launch = (_REMOTE_ENV + f"cd {_qs(REMOTE_DIR)}/sims || exit 1; setsid nohup {_REMOTE_EXE} -server -port {PORT} -np {np_} {_REMOTE_LIC} {load} "
              f"> {_qs(rlog)} 2>&1 < /dev/null & echo PID=$!")
    r = _ssh(launch, timeout=60)
    m = re.search(r"PID=(\d+)", r.stdout)
    if not m:
        raise RuntimeError(f"no pude lanzar starccm+ en {SSH_HOST}: {r.stderr.strip()[-300:]}")
    st = {"where": "server", "ssh": SSH_HOST, "pid": int(m.group(1)), "port": PORT, "host": SSH_HOST.split("@")[-1],
          "sim": str(sim) if sim else None, "rsim": rsim, "log": str(SIMS / f"{stem}.server.log"), "rlog": rlog,
          "started": datetime.now().isoformat(timespec="seconds"), "np": np_,
          "cmd": f"ssh {SSH_HOST} starccm+ -server -port {PORT} -np {np_} -power -podkey *** {load}".strip(),
          **({"uploaded_seconds": uploaded} if uploaded is not None else {})}
    _write_state(st)
    deadline = time.time() + 600
    while time.time() < deadline:
        tail = _tail_log(st, 20000)
        if "Server::start" in tail:
            break
        if not _ssh(f"kill -0 {st['pid']} 2>/dev/null && echo SI", timeout=20).stdout.strip():
            STATE_FILE.unlink(missing_ok=True)
            raise RuntimeError(f"starccm+ remoto terminó al arrancar. Cola del log:\n{_redact(tail)[-3000:]}")
        time.sleep(2)
    else:
        _ssh(f"kill {st['pid']}", timeout=20)
        STATE_FILE.unlink(missing_ok=True)
        raise RuntimeError("El servidor remoto no arrancó en 600 s")
    st["startup_seconds"] = round(time.time() - t0, 1)
    _write_state(st)
    _alive_cache.clear()
    init = ("AutoSave as = sim.getSimulationIterator().getAutoSave();\n"
            "as.setAutoSaveBatch(false); as.setAutoSaveMesh(false);\n"
            'sim.println("INIT autosave off");\n')
    try:
        st["init"] = _inject(init, timeout=600)["stdout"][-200:]
    except Exception as e:  # noqa: BLE001
        st["init"] = f"init falló: {e}"
    _write_state(st)
    _log(f"servidor REMOTO {SSH_HOST} pid={st['pid']} puerto={PORT} np={np_} sim={rsim} en {st['startup_seconds']}s"
         f"{f' (subida del .sim {uploaded}s)' if uploaded is not None else ''}; {st['init']}")
    return st


def _server_stop_remote(st: dict, save: bool, result: dict) -> dict:
    """server_stop en el servidor Linux: guarda allí (el .sim no se baja: tarda; queda en REMOTE_DIR/sims)."""
    if alive(st):
        if save and st.get("rsim"):
            sp = _jstr(st["rsim"])
            try:
                r = _inject(f'sim.saveState("{sp}");\nsim.println("SAVED " + "{sp}");\n', timeout=1800)
                ok, err = r["ok"] and "SAVED" in (r["stdout"] or ""), r.get("exception") or r.get("stderr") or r.get("stdout")
            except Exception as e:  # noqa: BLE001
                ok, err = False, str(e)
            if not ok:
                _log(f"server_stop remoto: guardado falló, servidor sigue vivo: {err}")
                return {"stopped": False, "saved": None, "save_error": str(err)[:500],
                        "reason": "no se pudo guardar; el servidor sigue vivo (save=False apaga sin guardar)"}
            result["saved"] = st["rsim"]
        try:
            result["stdout"] = _inject("sim.kill();\n", timeout=1800)["stdout"]
        except Exception as e:  # noqa: BLE001
            result["kill_error"] = str(e)
    for _ in range(30):
        if not _ssh(f"kill -0 {int(st['pid'])} 2>/dev/null && echo SI", timeout=20).stdout.strip():
            break
        time.sleep(2)
    else:
        _ssh(f"pkill -TERM -P {int(st['pid'])}; kill -TERM {int(st['pid'])}", timeout=20)
        result["forced"] = True
    _alive_cache.clear()
    _tail_log(st)  # copia final del log remoto para la pestaña Salida
    STATE_FILE.unlink(missing_ok=True)
    result["where"] = "server"
    _log(f"servidor REMOTO {st['pid']} apagado {result}")
    return result


@mcp.tool()
def server_stop(save: bool = True) -> dict:
    """Guarda (si save) y apaga el servidor. Limpia .server.json."""
    with _lock:
        _touch()
        st = _state()
        if not st.get("pid"):
            return {"stopped": False, "reason": "no había servidor"}
        result = {"stopped": True, "saved": None}
        if st.get("where") == "server":
            return _server_stop_remote(st, save, result)
        if _pid_alive(st["pid"]) and _port_open(st["port"]):
            if save and st.get("sim"):
                # el guardado va en su propia macro: si falla, el servidor sigue vivo y el trabajo no se pierde
                sp = _jstr(_jpath(st["sim"]))
                try:
                    r = _inject(f'sim.saveState("{sp}");\nsim.println("SAVED " + "{sp}");\n', timeout=1800)
                    ok = r["ok"] and "SAVED" in (r["stdout"] or "")
                    err = r.get("exception") or r.get("stderr") or r.get("stdout")
                except Exception as e:  # noqa: BLE001
                    ok, err = False, str(e)
                if not ok:
                    _log(f"server_stop: guardado falló, servidor sigue vivo: {err}")
                    return {"stopped": False, "saved": None, "save_error": str(err)[:500],
                            "reason": "no se pudo guardar; el servidor sigue vivo (save=False apaga sin guardar)"}
                result["saved"] = st["sim"]
            try:
                r = _inject("sim.kill();\n", timeout=1800)
                result["stdout"] = r["stdout"]
            except Exception as e:  # noqa: BLE001
                result["kill_error"] = str(e)
            for _ in range(60):
                if not _pid_alive(st["pid"]):
                    break
                time.sleep(1)
        if _pid_alive(st["pid"]):
            if _pid_is_ours(st["pid"]):
                _kill_tree(st["pid"])
                result["forced"] = True
            else:  # PID reasignado a otro proceso: no se toca, solo se limpia el estado
                result["pid_reused"] = True
        STATE_FILE.unlink(missing_ok=True)
        _log(f"servidor {st['pid']} apagado {result}")
        return result


@mcp.tool()
def server_status() -> dict:
    """Estado del servidor: pid, puerto, sim, vivo o no, minutos de inactividad."""
    st = _state()
    return {"alive": alive(st), "idle_min": round(idle_seconds() / 60, 1), "run_where": run_where(), **st}


def _jpath(p: str | os.PathLike) -> str:
    return str(p).replace("\\", "/")


def _jstr(s: str) -> str:
    """Escapa texto para un literal Java entre comillas (no se puede cerrar el string ni meter saltos)."""
    return str(s).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "\\r")


@mcp.tool()
def run_java(body: str, imports: str = "", timeout_s: int = 3600) -> dict:
    """Ejecuta el cuerpo de execute() en el servidor. `sim` (Simulation) ya existe. Lo que se imprime
    con sim.println vuelve en stdout. imports: extra separados por coma (p.ej. "star.energy.*").
    Si falla, devuelve exception y trace. Antes de inventar Java: recipe_search y docs_search."""
    with _lock:
        return _inject(body, imports, timeout=timeout_s)


_INSPECT = {
    "regions": """
for (Region r : sim.getRegionManager().getRegions()) {
  sim.println("REGION\\t" + r.getPresentationName() + "\\t" + r.getRegionType().getPresentationName());
  for (Boundary b : r.getBoundaryManager().getBoundaries())
    sim.println("BOUNDARY\\t" + r.getPresentationName() + "/" + b.getPresentationName() + "\\t" + b.getBoundaryType().getPresentationName());
}
for (Interface i : sim.getInterfaceManager().getObjects())
  sim.println("INTERFACE\\t" + i.getPresentationName() + "\\t" + i.getClass().getSimpleName());
""",
    "physics": """
for (Continuum c : sim.getContinuumManager().getObjects()) {
  sim.println("CONTINUUM\\t" + c.getPresentationName() + "\\t" + c.getClass().getSimpleName());
  if (c instanceof PhysicsContinuum)
    for (Model m : ((PhysicsContinuum) c).getModelManager().getObjects())
      sim.println("MODEL\\t" + c.getPresentationName() + "/" + m.getPresentationName() + "\\t" + m.getClass().getSimpleName());
}
""",
    "mesh_ops": """
for (MeshOperation op : sim.get(MeshOperationManager.class).getObjects())
  sim.println("MESH_OP\\t" + op.getPresentationName() + "\\t" + op.getClass().getSimpleName());
""",
    "parts": """
for (GeometryPart p : sim.get(SimulationPartManager.class).getParts()) {
  sim.println("PART\\t" + p.getPresentationName() + "\\t" + p.getClass().getSimpleName());
  for (PartSurface s : p.getPartSurfaces())
    sim.println("SURFACE\\t" + p.getPresentationName() + "/" + s.getPresentationName() + "\\t");
}
""",
    "reports": """
for (Report rep : sim.getReportManager().getObjects()) {
  String v;
  try { v = String.valueOf(rep.getReportMonitorValue()); } catch (Exception e) { v = "n/a"; }
  sim.println("REPORT\\t" + rep.getPresentationName() + "\\t" + rep.getClass().getSimpleName() + "\\t" + v);
}
""",
    "monitors": """
for (Monitor m : sim.getMonitorManager().getObjects())
  sim.println("MONITOR\\t" + m.getPresentationName() + "\\t" + m.getClass().getSimpleName());
""",
    "scenes": """
for (Scene s : sim.getSceneManager().getScenes())
  sim.println("SCENE\\t" + s.getPresentationName() + "\\t");
""",
    "solver": """
sim.println("ITERATION\\t" + sim.getSimulationIterator().getCurrentIteration() + "\\t");
sim.println("SIM\\t" + sim.getPresentationName() + "\\t" + sim.getSessionPath());
for (Solver s : sim.getSolverManager().getObjects())
  sim.println("SOLVER\\t" + s.getPresentationName() + "\\t" + s.getClass().getSimpleName());
""",
}
# Cada sección en su propio try/catch: un gestor ausente (p.ej. MeshOperationManager en una
# simulación vacía) avisa con WARN y no tumba el resto.
_INSPECT = {k: "try {\n" + v + "\n} catch (Exception e) { sim.println(\"WARN\\t" + k
            + "\\t\" + String.valueOf(e.getMessage()).replace('\\n', ' ')); }"
            for k, v in _INSPECT.items()}
_INSPECT["tree"] = "\n".join(_INSPECT[k] for k in ("solver", "parts", "regions", "physics", "mesh_ops", "reports", "monitors", "scenes"))


@mcp.tool()
def inspect(path: str = "tree") -> dict:
    """Lee un nodo del árbol de la simulación: tree (todo), regions, physics, mesh_ops, parts,
    reports, monitors, scenes, solver. JSON con nombres, tipos y valores principales."""
    key = (path or "tree").strip().lower()
    if key not in _INSPECT:
        return {"error": f"nodo desconocido '{path}'", "nodos": sorted(_INSPECT)}
    with _lock:
        r = _inject(_INSPECT[key])
    items: dict[str, list] = {}
    for line in r["stdout"].splitlines():
        parts = line.split("\t")
        if len(parts) >= 2 and parts[0].isupper():
            items.setdefault(parts[0].lower(), []).append(
                {"name": parts[1], "type": parts[2] if len(parts) > 2 else "",
                 **({"value": parts[3]} if len(parts) > 3 else {})})
    return {"ok": r["ok"], "path": key, "seconds": r["seconds"], **items,
            **({"exception": r["exception"], "trace": r["trace"]} if r["exception"] else {})}


@mcp.tool()
def iterate(n: int = 100, timeout_s: int = 7200) -> dict:
    """Corre n iteraciones. Devuelve la última fila de todos los monitores (residuales y reportes)
    leyendo el CSV que exporta el MonitorManager, más el tiempo."""
    # Residuales: exportando el plot "Residuals" a CSV (MonitorManager.export falla en batch 2410:
    # "StarUpdate unexpectedly missing"). Reportes: valor directo de cada Report.
    csv = MACROS / "residuals.csv"
    csv.unlink(missing_ok=True)
    body = f"""
sim.getSimulationIterator().step({int(n)});
sim.println("ITERATION " + sim.getSimulationIterator().getCurrentIteration());
try {{
  StarPlot rp = sim.getPlotManager().getPlot("Residuals");
  rp.export("{_jpath(csv)}", ",");
  sim.println("RESIDUALS_CSV ok");
}} catch (Exception e) {{ sim.println("RESIDUALS_CSV n/a " + e.getMessage()); }}
for (Report rep : sim.getReportManager().getObjects()) {{
  try {{ sim.println("REPORT\\t" + rep.getPresentationName() + "\\t" + rep.getReportMonitorValue()); }}
  catch (Exception e) {{ sim.println("REPORT\\t" + rep.getPresentationName() + "\\tn/a"); }}
}}
"""
    with _lock:
        r = _inject(body, timeout=timeout_s)
    out = {"ok": r["ok"], "seconds": r["seconds"]}
    m = re.search(r"ITERATION (\d+)", r["stdout"])
    if m:
        out["iteration"] = int(m.group(1))
    reports = {}
    for line in r["stdout"].splitlines():
        parts = line.split("\t")
        if parts[0] == "REPORT" and len(parts) == 3:
            try:
                reports[parts[1]] = float(parts[2])
            except ValueError:
                reports[parts[1]] = parts[2]
    out["reports"] = reports
    if r["exception"]:
        out.update(exception=r["exception"], trace=r["trace"])
    if csv.is_file():
        rows = [l.split(",") for l in csv.read_text(encoding="utf-8", errors="replace").splitlines() if l.strip()]
        if len(rows) >= 2:
            hdr, last = [h.strip().strip('"') for h in rows[0]], rows[-1]
            res = {}
            for h, v in zip(hdr, last):
                try:
                    res[h] = float(v)
                except ValueError:
                    res[h] = v.strip()
            out["residuals"] = res
    else:
        out["stdout"] = r["stdout"][-1500:]
    return out


@mcp.tool()
def export_scene(name: str, path: str = "", width: int = 1600, height: int = 1000) -> dict:
    """Exporta la escena `name` a PNG. path vacío = cases/_scenes/<name>.png."""
    out = Path(path) if path else CASES / "_scenes" / f"{_safe(name)}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    nm, outp = _jstr(name), _jstr(_jpath(out))
    # createScene("X") puede dejar la escena como "X 1": se acepta nombre exacto o prefijo.
    body = f"""
Scene sc = null;
for (Scene s : sim.getSceneManager().getScenes())
  if (s.getPresentationName().equals("{nm}")) sc = s;
if (sc == null)
  for (Scene s : sim.getSceneManager().getScenes())
    if (s.getPresentationName().startsWith("{nm}")) {{ sc = s; break; }}
if (sc == null) throw new RuntimeException("No hay escena '{nm}'");
sim.println("SCENE " + sc.getPresentationName());
sc.printAndWait(resolvePath("{outp}"), 1, {int(width)}, {int(height)}, true, false);
sim.println("PNG " + "{outp}");
"""
    with _lock:
        r = _inject(body)
    return {"ok": r["ok"] and out.is_file(), "png": str(out), "seconds": r["seconds"],
            **({"exception": r["exception"], "trace": r["trace"]} if r["exception"] else {})}


@mcp.tool()
def save(path: str = "") -> dict:
    """Guarda el .sim (en sims/ por defecto, o en path). Actualiza .server.json."""
    st = _state()
    target = Path(path) if path else (Path(st["sim"]) if st.get("sim") else SIMS / "nuevo.sim")
    if not target.suffix:
        target = target.with_suffix(".sim")
    if not target.is_absolute():
        target = SIMS / target
    target.parent.mkdir(parents=True, exist_ok=True)
    tj = _jstr(_jpath(target))
    body = f'sim.saveState("{tj}");\nsim.println("SAVED " + "{tj}");\n'
    with _lock:
        r = _inject(body, timeout=1800)
        if r["ok"]:
            st["sim"] = str(target)
            if st.get("where") == "server":
                st["rsim"] = _rpath(target)  # el .sim guardado queda en el servidor
            _write_state(st)
    return {"ok": r["ok"], "sim": str(target), "seconds": r["seconds"],
            **({"remote_sim": st.get("rsim")} if st.get("where") == "server" else {}),
            **({"exception": r["exception"]} if r["exception"] else {})}


def _safe(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "_", s).strip("_") or "x"


# ----------------------------------------------------------------------------- memoria
@mcp.tool()
def recipe_search(query: str = "") -> list[dict]:
    """Busca en recipes/ (snippets Java verificados). Devuelve nombre, cabecera y coincidencias.
    Vacío = lista todas."""
    _touch()
    terms = [t.lower() for t in re.findall(r"\w+", query)]
    hits = []
    for p in sorted(RECIPES.glob("*.java")) + sorted(RECIPES.glob("*.md")):
        text = p.read_text(encoding="utf-8", errors="replace")
        low = (p.name + "\n" + text).lower()
        score = sum(low.count(t) for t in terms) if terms else 1
        if score:
            head = [l.strip() for l in text.splitlines()[:4] if l.strip()]
            hits.append({"name": p.name, "score": score, "head": head,
                         "unverified": "no verificado" in text.lower()})
    hits.sort(key=lambda h: -h["score"])
    return hits[:20]


@mcp.tool()
def recipe_save(name: str, body: str, note: str = "") -> str:
    """Guarda un snippet que funcionó como recipes/<verbo>-<objeto>.java con cabecera QUE/VERSION/FECHA.
    Guardar tras CADA run_java que logre algo nuevo."""
    _touch()
    RECIPES.mkdir(exist_ok=True)
    fname = _safe(name.removesuffix(".java")).lower() + ".java"
    header = f"// QUE: {note or name}\n// VERSION: {_version_tag()}\n// FECHA: {datetime.now():%Y-%m-%d}\n"
    p = RECIPES / fname
    p.write_text(header + body.rstrip() + "\n", encoding="utf-8")
    return str(p)


def _version_tag() -> str:
    return HOME.name.replace("STAR-CCM+", "") if HOME else "?"


_doc_index: list[tuple[str, Path]] | None = None


def _docs() -> list[tuple[str, Path]]:
    global _doc_index
    if _doc_index is None:
        _doc_index = []
        if DOC_DIR and DOC_DIR.is_dir():
            for p in DOC_DIR.rglob("*.html"):
                rel = p.relative_to(DOC_DIR).as_posix()
                if "/" in rel and "class-use/" not in rel and not p.name.startswith(("index", "overview", "package-")):
                    _doc_index.append((rel[:-5].replace("/", "."), p))
    return _doc_index


_member_idx: dict[str, list[str]] | None = None


def _members() -> dict[str, list[str]]:
    """clase calificada -> miembros, de member-search-index.js (0,1 s; sustituye al rastreo de las 22 k páginas)."""
    global _member_idx
    if _member_idx is None:
        _member_idx = {}
        f = DOC_DIR / "member-search-index.js" if DOC_DIR else None
        if f and f.is_file():
            txt = f.read_text(encoding="utf-8", errors="replace")
            for m in json.loads(txt[txt.index("["):txt.rindex("]") + 1]):
                _member_idx.setdefault(f"{m['p']}.{m['c']}", []).append(m["l"])
    return _member_idx


def _html_text(p: Path) -> str:
    t = p.read_text(encoding="utf-8", errors="replace")
    t = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", t, flags=re.S | re.I)
    t = re.sub(r"<[^>]+>", " ", t)
    t = html.unescape(t)
    t = re.sub(r"[ \t\xa0]+", " ", t)
    # firmas con la lista de argumentos partida en varias líneas -> una sola línea
    return re.sub(r"\(\s*([^()]*?)\s*\)", lambda m: "(" + " ".join(m.group(1).split()) + ")", t, flags=re.S)


@mcp.tool()
def docs_search(query: str, max_classes: int = 5) -> dict:
    """Busca en el javadoc de STAR-CCM+ ($STARCCM_HOME/doc/client/html): clases cuyo nombre
    coincide y, dentro, las firmas de métodos que contienen los términos. Fuente de verdad de
    nombres de clases y métodos."""
    _touch()
    terms = [t for t in re.findall(r"\w+", query) if len(t) > 1]
    if not terms:
        return {"error": "query vacía"}
    docs = _docs()
    if not docs:
        return {"error": f"No encuentro el javadoc en {DOC_DIR}"}
    low = [t.lower() for t in terms]
    scored = []
    for fq, p in docs:
        name = fq.rsplit(".", 1)[-1].lower()
        s = sum(3 for t in low if t in name) + sum(1 for t in low if t in fq.lower())
        if s:
            scored.append((s, -len(name), fq, p))
    scored.sort(reverse=True)
    result = {"query": query, "classes": []}
    for s, _, fq, p in scored[:max_classes]:
        text = _html_text(p)
        sigs = []
        for line in re.split(r"\n+", text):
            l = line.strip()
            if ("(" in l and ")" in l and len(l) < 220 and any(t in l.lower() for t in low)) \
                    or l.startswith(("public ", "class ", "interface ")):
                if l not in sigs:
                    sigs.append(l)
        result["classes"].append({"class": fq, "file": str(p), "matches": sigs[:25]})
    if not result["classes"]:
        # ningún nombre de clase coincide: se busca entre los 146 k miembros del índice del javadoc
        hits, members = [], {}
        for fq, ms in _members().items():
            joined = " ".join(ms).lower()
            if all(t in joined for t in low):
                exact = [m for m in ms if all(t in m.lower() for t in low)]
                hits.append((0 if exact else 1, fq))
                members[fq] = (exact or ms)[:5]
        hits.sort()
        result["content_hits"] = [fq for _, fq in hits[:max_classes]]
        result["members"] = {fq: members[fq] for fq in result["content_hits"]}
    return result


# ----------------------------------------------------------------------------- selftest
def _selftest() -> int:
    os.environ["STARCCM_RUN_WHERE"] = "local"  # nunca el servidor remoto (ni licencia) desde el selftest
    global EXE, PORT, SIMS, MACROS, STATE_FILE, AGENT_LOG
    import tempfile
    fake = HERE / "tests" / "fake_starccm.py"
    os.environ["STARCCM_EXE"] = str(fake)
    EXE = str(fake)
    with socket.socket() as sk:  # puerto libre: dos selftests a la vez no se pisan
        sk.bind(("127.0.0.1", 0))
        PORT = sk.getsockname()[1]
    tmp = Path(tempfile.mkdtemp(prefix="starccm-selftest-"))
    # Todo lo que escribe el falso va al temporal: ni sims/, ni macros/, ni el .server.json reales
    # (antes la pestaña Salida de ui/ enseñaba el «FAKE server» como última macro, y un selftest
    # borraba el .server.json de un solver vivo de otra sesión).
    real = (SIMS, MACROS, STATE_FILE)
    _real_files = lambda: {(str(p), p.stat().st_mtime_ns) for d in real for p in ([d] if d.is_file() else d.glob("*") if d.is_dir() else [])}
    real_before = _real_files()
    SIMS, MACROS, STATE_FILE, AGENT_LOG = tmp / "sims", tmp / "macros", tmp / ".server.json", tmp / "agent.log"
    fails = []

    def check(cond, msg):
        print(("  ok   " if cond else "  FAIL ") + msg)
        if not cond:
            fails.append(msg)

    print(f"selftest: starccm+ falso = {fake} · escribe solo en {tmp}")
    r = subprocess.run(_starccm_cmd() + ["-version"], capture_output=True, text=True)
    check("FAKE" in r.stdout, "-version del falso")
    st = server_start()
    check(st.get("pid") and _port_open(PORT), f"server_start -> pid {st.get('pid')} puerto {PORT} en {st.get('startup_seconds')}s")
    st2 = server_start()
    check(st2.get("reused"), "server_start reutiliza el servidor vivo")
    r = run_java('sim.println("OK");')
    check(r["ok"] and r["stdout"].strip() == "OK", f"run_java OK ({r['seconds']}s)")
    r = run_java('sim.println("AGENT_FAKE_FAIL");\nsim.println("no llega");')
    check(not r["ok"] and r["exception"] and "fallo simulado" in r["exception"], "run_java captura excepción")
    r = inspect("regions")
    check(r["ok"] and r["path"] == "regions", "inspect(regions) responde")
    r = inspect("nodo_que_no_existe")
    check("error" in r, "inspect rechaza nodo desconocido")
    p = recipe_save("probar-selftest", 'sim.println("hola");', "receta de prueba del selftest")
    check(Path(p).is_file(), "recipe_save")
    hits = recipe_search("selftest hola")
    check(any(h["name"] == "probar-selftest.java" for h in hits), "recipe_search encuentra la receta")
    Path(p).unlink(missing_ok=True)
    d = docs_search("Simulation saveState")
    check(("classes" in d and d["classes"]) or "error" in d, "docs_search responde (con o sin javadoc)")
    if DOC_DIR and DOC_DIR.is_dir():
        check(any(c["class"].endswith("Simulation") for c in d.get("classes", [])), "docs_search encuentra star.common.Simulation")
    r = save(str(tmp / "prueba.sim"))
    check(r["ok"], "save")
    if DOC_DIR and DOC_DIR.is_dir() and (DOC_DIR / "member-search-index.js").is_file():
        d2 = docs_search("setRelativeToModelLength")
        check(any(c.endswith("GlyphSettings") for c in d2.get("content_hits", [])), "docs_search encuentra un método por el índice de miembros")
    check(_jstr('a"b' + chr(92) + 'c' + chr(10) + 'd') == 'a' + chr(92) + '"b' + chr(92) * 2 + 'c' + chr(92) + 'nd',
          "_jstr escapa comillas, barras y saltos")
    r = export_scene('x"); System.exit(0); //')
    macs = sorted(MACROS.glob("Agent_*.java"), key=lambda q: q.stat().st_mtime)
    check('equals("x\\"); System.exit(0); //")' in macs[-1].read_text(encoding="utf-8"), "export_scene escapa el nombre en el Java")
    check(idle_seconds() < 60, "last_activity en disco ve la actividad reciente")
    # guardado que falla: el servidor sigue vivo y no se da por guardado
    real_sim = _state().get("sim")
    _write_state({**_state(), "sim": str(tmp / "AGENT_FAKE_FAIL.sim")})
    r = server_stop(save=True)
    check(r["stopped"] is False and r.get("save_error") and _port_open(PORT), "server_stop con guardado fallido no apaga ni dice «saved»")
    _write_state({**_state(), "sim": real_sim})
    sstat = server_status()
    check(sstat["alive"], "server_status vivo")
    r = server_stop(save=True)
    check(r["stopped"] and not STATE_FILE.exists(), "server_stop apaga y limpia .server.json")
    check(not _port_open(PORT), "puerto liberado")
    r2 = server_stop()
    check(r2["stopped"] is False, "server_stop sin servidor no falla")
    # otra sesión puede estar usando el solver real mientras tanto: solo miramos que lo nuevo no sea del falso
    new = [Path(p) for p, _ in _real_files() - real_before]
    check(not any(p.suffix in (".log", ".out", ".json") and "FAKE" in p.read_text(encoding="utf-8", errors="replace")[:400] for p in new if p.is_file()),
          "sims/, macros/ y .server.json reales sin rastro del starccm+ falso")
    shutil.rmtree(tmp, ignore_errors=True)
    # modo remoto: solo traducción de rutas y decisión local/servidor (sin red ni licencia)
    loc = _jpath(HERE.resolve())
    tr = _translate(f'a("{loc}/cases/c/images/x.png"); b("{loc.upper()}\\\\macros\\\\r.csv"); c("C:/otra/ruta")')
    check(f'a("{REMOTE_DIR}/cases/c/images/x.png")' in tr and f'b("{REMOTE_DIR}/macros/r.csv")' in tr and 'c("C:/otra/ruta")' in tr,
          "remoto: rutas de starccm/ traducidas a REMOTE_DIR (barras y mayúsculas), las demás intactas")
    check(_rpath(HERE / "sims" / "x.sim") == f"{REMOTE_DIR}/sims/x.sim", "remoto: _rpath de sims/")
    check(run_where() == "local", "STARCCM_RUN_WHERE=local manda sobre la elección de la interfaz (el selftest nunca va al servidor)")
    check(not alive({"where": "server"}), "alive() sin pid remoto = False sin tocar la red")
    print(f"selftest: {len(fails)} fallos" if fails else "selftest: todo en verde")
    return 1 if fails else 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(_selftest())
    start_watchdog()
    mcp.run()
