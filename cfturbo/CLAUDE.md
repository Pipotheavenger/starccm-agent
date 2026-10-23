# cfturbo-agent

Agente que diseña impulsores y volutas de bombas con CFturbo en lenguaje natural.
CFturbo es el generador paramétrico de geometría. Claude decide qué parámetros mover y lee
qué pasó. La evaluación CFD la hace el agente hermano de STAR-CCM+ (carpeta `..`, en la MV Linux).
No hay API de Anthropic en este PC: el cerebro es Claude Code (esta sesión) vía MCP, y la
interfaz controladora (`ui/`) solo muestra estado, hitos y geometría, y genera el prompt que el
usuario pega aquí.

## Cómo se opera CFturbo (verificado 2026-10-23, CFturbo 2026.1.1.128)

- Solo modo batch: `CFturbo.exe -batch archivo.cft-batch -log archivo.log`. Sin GUI. rc=0 limpio,
  1 con avisos, 2 con errores. Primera corrida ~30-70 s (arranque), siguientes ~5-10 s.
- El `.cft` es XML plano. **Se edita directamente** (d2, b2, dS, dH, Psi, nBl, Q, H, n, …) sobre
  una copia en `work/`, y CFturbo regenera la geometría al abrirlo en batch. Probado: d2
  0.2063→0.215 m y nBl 6→7 se conservan en el `.cft` guardado y el STL del impulsor crece.
- El bloque `<Updates>` del batch solo lo acepta CFturbo si la plantilla salió de la GUI
  (PROJECT > Batch mode/Optimization). No se usa. Si algún día hay plantilla, se puede añadir.
- Export en batch: `<BatchAction Name="Export">` con hijos `WorkingDir`, `BaseFileName`,
  `ExportInterface Type="Enum"` y `ExportComponents Type="Array1"` cuyos `<Value>` **deben traer
  `Caption="[Nombre]"`** y valor = `Index`+1 del componente. Sin `Caption` solo exporta el primero.
  - `StarCCM` → `<base>_Co1..3.stp` (+ `_Co3_Extension.stp`), `<base>.cfturbo-ccm` (condiciones de
    frontera, rpm, caudal másico) y `CFturbo2StarCCM.java`. Esto es lo que va a la MV.
  - `OpenFOAM` → un STL ASCII por superficie (`BladePS`, `Hub`, `Shroud`, `Spiral`…). Es lo que
    pinta el visor. Granularidad en `Export_Interfaces/TOpenFOAMInterface/STLData` del `.cft`.
  - `General` → `.geo-xml` (solo puntos hub/shroud); STEP/IGES requieren configurarlo en la GUI.
- `Save` → `<OutputFile>`; el `.cft-res` se escribe junto al `.cft` de entrada. Los hints
  (acoplamientos, extensiones, licencia) van al `<nombre>.log` que CFturbo crea solo, no al `-log`.
- Cambiar el punto de diseño (Q, H, n) con `AutoUpdate=True` recalcula d2/b2/dS pero puede romper
  el meridiano ("Secondary flow path intersects hub solid"). Para puntos de diseño muy distintos
  al proyecto base, mejor que el usuario cree la bomba base en la GUI (5 min) y se guarde en
  `projects/<nombre>/<nombre>.cft`.
- Licencia local Uniandes (hasta 2027-02-10): impulsor radial y axial de bomba, impulsor radial de
  compresor, estator, voluta, bladerunner. **Turbinas Francis/Kaplan sin licencia** ("Runner: No
  running license available"). Turbinas solo como bomba-como-turbina (PAT) hasta tener el módulo.

## MCP: `mcp_server.py` (stdio, registrado en `.mcp.json`; selftest incluido)

| tool | qué hace |
|---|---|
| `cft_projects()` | proyectos base en `projects/<nombre>/<nombre>.cft` |
| `cft_info(project)` | punto de diseño (Q m³/h, H m, n rpm, nq), fluido, componentes, d2/b2/dS/dH/Psi/nBl |
| `cft_params(project, filter)` | alias con valor actual + hojas del XML que cumplan el regex (para parámetros sin alias) |
| `cft_run(project, edits, name, exports, save)` | copia a `work/<name>_<ts>/`, edita, corre, exporta; devuelve `realized`, `corrected`, `warnings`, `errors`, archivos |
| `cft_runs(limit)` | últimas corridas, temporales y guardadas (`saved`) |
| `cft_save(run_id, name, note)` | guarda una corrida como versión en `versions/` y la anota en la bitácora |
| `cft_log(run_dir)` | cola del log |
| `cft_nq(Q_m3h, H_m, n_rpm)` | nq y tipo de máquina orientativo |
| `cft_recipe_search` / `cft_recipe_save` | memoria |

Dónde viven las cosas: las corridas van a `%TEMP%\cfturbo-agent\<name>_<ts>\` y se podan solas
(quedan las 8 últimas). Lo que el usuario quiere conservar se guarda con `cft_save` (o el botón
"Guardar versión") en `versions/<nombre>/`. Cada corrida que sale bien y cada versión guardada
dejan una línea en `recipes/bitacora.md`, que `cft_recipe_search` indexa: esa es la biblioteca
del agente junto con las recetas. **Regla:** antes de proponer, `cft_recipe_search`; después de
algo que funcionó, `cft_recipe_save` con el porqué.

Claves de `edits`: alias SI (`Q` m³/s, `H` m, `n` 1/s, `d2` `b2` `dS` `dH` m, `Psi`, `nBl`,
`AutoUpdate`, `volute_d_out`), con unidad (`Q_m3h`, `H_m`, `n_rpm`, `d2_mm`, `b2_mm`, `dS_mm`,
`dH_mm`), o un sufijo/regex de ruta del XML tal como lo lista `cft_params`.
`python mcp_server.py --selftest` debe pasar siempre antes de un commit.

## Interfaz controladora: `ui/`

`ui/server.py` (FastAPI) + `ui/index.html` (three.js). Arranque: preview `cfturbo-ui`
(`.claude/launch.json` en la raíz) o
`cfturbo\.venv\Scripts\python -m uvicorn --app-dir cfturbo ui.server:app --port 8765`.
Muestra: tabla de parámetros (base vs corrida seleccionada vs nuevo) con nq en vivo; botón
**Ejecutar** que corre CFturbo directamente (`POST /api/run` → `run_batch` en un hilo, una corrida a
la vez), partiendo del proyecto base o del `_out.cft` de la corrida seleccionada; hitos, avisos y
correcciones; archivos exportados con descarga y "Abrir carpeta"; visor 3D de los STL (por
componente, tapas ocultables); tabla de corridas. Se refresca sola cada 3 s leyendo `work/*/run.json`.
**Chat con Claude Code** (`POST /api/chat`, SSE): el servidor lanza `claude -p <msg> --output-format
stream-json --mcp-config .mcp.json --strict-mcp-config --allowedTools "mcp__cfturbo__*,Read,Glob,Grep"
--append-system-prompt … --resume <sesión>` con el entorno limpio de variables `CLAUDE*` (para que
use su propio login, no la sesión anidada). Usa la suscripción del usuario, sin API key. Requiere
`claude auth login` hecho una vez en una terminal; si el token caducó la CLI responde "401 OAuth
access token is invalid". Sin `--bare` (desactiva el llavero). `CFT_CLAUDE_BIN` permite apuntar a una
CLI simulada para probar el panel.

## Flujo estándar

1. Usuario da punto de diseño: Q, H, n, fluido, uso (bomba o PAT). `cft_nq` para clasificar.
2. `cft_projects` + `cft_info` del proyecto base más cercano en nq. Si no hay ninguno razonable,
   pedir al usuario que cree la bomba base en la GUI y la guarde en `projects/`.
3. Proponer cambios con criterio de turbomáquinas (Euler, b2/d2, Psi, número de álabes, ángulos)
   y correr `cft_run` con nombre descriptivo. Varias variantes = varias corridas.
4. Reportar en tabla: pedido vs realizado, correcciones de CFturbo, avisos, rutas de los STEP.
   Si CFturbo corrige un valor, decirlo; no asumir que se aplicó lo pedido.
5. Entregar `work/<corrida>/` (STEP + `.cfturbo-ccm` + `.java`) al agente CFD de la MV y cerrar el
   loop con H y eficiencia. Hasta entonces, estimación 1D con las dimensiones.
6. Guardar receta por cada combinación que funcionó o lección aprendida.

## Reglas

- Nunca editar el `.cft` de `projects/`; `cft_run` siempre trabaja sobre la copia en `work/`.
- Rutas de Windows absolutas en el batch. Unidades del `.cft`: SI (m, m³/s, 1/s).
- Español, corto, números en tablas. Estilo mínimo: un archivo de MCP, sin clases de más.

## Lecciones

- 2026-10-23: `CFturbo.exe -batch` funciona sin GUI; rc 0/1/2 = limpio/avisos/errores.
- 2026-10-23: `ExportComponents` sin `Caption` en cada `<Value>` exporta solo el primer componente,
  pidas lo que pidas. Con `Caption` salen todos. Formato de atributos de la doc de optiSLang
  (Version 9) falla con "Parsing batch action nodes failed".
- 2026-10-23: `<Updates>` escrito a mano se descarta ("Only batchprojects from the current version
  support updating a project"). Solución: editar el `.cft` copiado, no el batch.
- 2026-10-23: los avisos del proyecto no van al archivo de `-log` sino al `<nombre>.log` que
  CFturbo crea junto al batch. Leer todos los `.log` de la corrida.
- 2026-10-23: `pip install mcp` trae la 2.x, donde `mcp.server.fastmcp.FastMCP` ya no existe; es
  `mcp.server.mcpserver.MCPServer` (misma API). El servidor importa una u otra. Aplica también al
  `mcp_server.py` de la MV.
- 2026-10-23: el visor three.js no orienta la cámara si la pestaña está oculta (sin rAF); hay que
  llamar `controls.update()` y renderizar una vez tras cargar.
