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
        out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True).stdout
        return str(pid) in out
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


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


def _touch() -> None:
    global _last_tool
    _last_tool = time.time()


def _idle_watchdog() -> None:
    """Apagado por inactividad: PoD cobra por hora de sesión."""
    while True:
        time.sleep(60)
        st = _state()
        if st.get("pid") and (time.time() - _last_tool) > IDLE_MIN * 60 and _pid_alive(st["pid"]):
            try:
                server_stop(save=True)
            except Exception as e:  # noqa: BLE001
                _log(f"watchdog: {e}")


def _log(msg: str) -> None:
    with open(HERE / "agent.log", "a", encoding="utf-8") as f:
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
    if not st.get("pid") or not _pid_alive(st["pid"]):
        raise RuntimeError("No hay servidor de STAR-CCM+ vivo. Usa server_start primero.")
    MACROS.mkdir(exist_ok=True)
    tag = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
    src = MACROS / f"Agent_{tag}.java"
    src.write_text(_wrap(body, imports, tag), encoding="utf-8")
    t0 = time.time()
    err_c = _precompile(src)
    if err_c:
        _touch()
        return {"ok": False, "stdout": "", "stderr": "", "exception": "javac: no compila",
                "trace": err_c, "seconds": round(time.time() - t0, 2), "macro": str(src), "returncode": 1}
    cmd = _starccm_cmd() + ["-host", f"localhost:{st['port']}", "-batch", str(src), "-noexit"] + _lic_flags()
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=str(MACROS),
                           encoding="utf-8", errors="replace")
        rc, out, err = r.returncode, r.stdout, r.stderr
    except subprocess.TimeoutExpired as e:
        rc, out, err = -1, (e.stdout or ""), f"timeout {timeout}s"
        if isinstance(out, bytes):
            out = out.decode("utf-8", "replace")
    secs = round(time.time() - t0, 2)
    # Salida de la macro: entre marcadores, del stdout del cliente; si no, del log del servidor.
    text = _between(out, tag)
    if text is None:
        text = _between(_tail_log(st), tag)
    err_match = re.search(r"AGENT_ERROR: (.*)", text or out)
    (src.with_suffix(".out")).write_text(_redact(out + ("\n--- stderr\n" + err if err else "")), encoding="utf-8")
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
    }


def _between(out: str, tag: str) -> str | None:
    m = re.search(rf"AGENT_BEGIN {tag}\r?\n(.*?)AGENT_END {tag}", out or "", re.S)
    return m.group(1).strip() if m else None


def _trace(text: str) -> str:
    m = re.search(r"AGENT_ERROR: .*?\n(.*)", text or "", re.S)
    return (m.group(1).strip()[:3000]) if m else ""


def _tail_log(st: dict, n: int = 200_000) -> str:
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
def server_start(sim_path: str = "", name: str = "") -> dict:
    """Levanta el servidor de STAR-CCM+ (o reutiliza el vivo). sim_path: .sim a abrir; se copia a
    sims/<name>.sim y se trabaja sobre la copia, nunca sobre el original. Vacío = simulación nueva.
    Devuelve host:port, pid, sim y segundos de arranque. Un solo servidor a la vez."""
    with _lock:
        _touch()
        st = _state()
        if st.get("pid") and _pid_alive(st["pid"]) and _port_open(st["port"]):
            return {"reused": True, **st}
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


@mcp.tool()
def server_stop(save: bool = True) -> dict:
    """Guarda (si save) y apaga el servidor. Limpia .server.json."""
    with _lock:
        _touch()
        st = _state()
        if not st.get("pid"):
            return {"stopped": False, "reason": "no había servidor"}
        result = {"stopped": True, "saved": None}
        if _pid_alive(st["pid"]) and _port_open(st["port"]):
            body = ""
            if save and st.get("sim"):
                body += f'sim.saveState("{_jpath(st["sim"])}");\nsim.println("SAVED {_jpath(st["sim"])}");\n'
                result["saved"] = st["sim"]
            body += "sim.kill();\n"
            try:
                r = _inject(body, timeout=1800)
                result["stdout"] = r["stdout"]
            except Exception as e:  # noqa: BLE001
                result["kill_error"] = str(e)
            for _ in range(60):
                if not _pid_alive(st["pid"]):
                    break
                time.sleep(1)
        if _pid_alive(st["pid"]):
            _kill_tree(st["pid"])
            result["forced"] = True
        STATE_FILE.unlink(missing_ok=True)
        _log(f"servidor {st['pid']} apagado {result}")
        return result


@mcp.tool()
def server_status() -> dict:
    """Estado del servidor: pid, puerto, sim, vivo o no, minutos de inactividad."""
    st = _state()
    alive = bool(st.get("pid")) and _pid_alive(st["pid"]) and _port_open(st.get("port", 0))
    return {"alive": alive, "idle_min": round((time.time() - _last_tool) / 60, 1), **st}


def _jpath(p: str | os.PathLike) -> str:
    return str(p).replace("\\", "/")


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
    # createScene("X") puede dejar la escena como "X 1": se acepta nombre exacto o prefijo.
    body = f"""
Scene sc = null;
for (Scene s : sim.getSceneManager().getScenes())
  if (s.getPresentationName().equals("{name}")) sc = s;
if (sc == null)
  for (Scene s : sim.getSceneManager().getScenes())
    if (s.getPresentationName().startsWith("{name}")) {{ sc = s; break; }}
if (sc == null) throw new RuntimeException("No hay escena '{name}'");
sim.println("SCENE " + sc.getPresentationName());
sc.printAndWait(resolvePath("{_jpath(out)}"), 1, {int(width)}, {int(height)}, true, false);
sim.println("PNG {_jpath(out)}");
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
    body = f'sim.saveState("{_jpath(target)}");\nsim.println("SAVED {_jpath(target)}");\n'
    with _lock:
        r = _inject(body, timeout=1800)
        if r["ok"]:
            st["sim"] = str(target)
            _write_state(st)
    return {"ok": r["ok"], "sim": str(target), "seconds": r["seconds"],
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
        hits = []
        for fq, p in docs[:4000]:
            try:
                if all(t in p.read_text(encoding="utf-8", errors="replace").lower() for t in low):
                    hits.append(fq)
            except OSError:
                pass
            if len(hits) >= max_classes:
                break
        result["content_hits"] = hits
    return result


# ----------------------------------------------------------------------------- selftest
def _selftest() -> int:
    global EXE, PORT
    import tempfile
    fake = HERE / "tests" / "fake_starccm.py"
    os.environ["STARCCM_EXE"] = str(fake)
    EXE = str(fake)
    PORT = 47999
    tmp = Path(tempfile.mkdtemp(prefix="starccm-selftest-"))
    STATE_FILE.unlink(missing_ok=True)
    fails = []

    def check(cond, msg):
        print(("  ok   " if cond else "  FAIL ") + msg)
        if not cond:
            fails.append(msg)

    print(f"selftest: starccm+ falso = {fake}")
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
    sstat = server_status()
    check(sstat["alive"], "server_status vivo")
    r = server_stop(save=True)
    check(r["stopped"] and not STATE_FILE.exists(), "server_stop apaga y limpia .server.json")
    check(not _port_open(PORT), "puerto liberado")
    r2 = server_stop()
    check(r2["stopped"] is False, "server_stop sin servidor no falla")
    shutil.rmtree(tmp, ignore_errors=True)
    print(f"selftest: {len(fails)} fallos" if fails else "selftest: todo en verde")
    return 1 if fails else 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(_selftest())
    threading.Thread(target=_idle_watchdog, daemon=True).start()
    mcp.run()
