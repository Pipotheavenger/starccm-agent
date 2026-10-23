# cfturbo-agent

Agente que diseña impulsores y volutas de bombas con CFturbo en lenguaje natural.
CFturbo es el generador paramétrico de geometría. Claude decide qué parámetros mover y lee
qué pasó. La evaluación CFD la hace el agente hermano de STAR-CCM+ (carpeta `..`, en la MV Linux).
No hay API de Anthropic en este PC: el cerebro es Claude Code vía MCP, ya sea en esta sesión o
lanzado por la interfaz controladora (`ui/`), que además corre CFturbo directamente, muestra la
geometría y guarda versiones. Guía de uso: `PRIMER-PROMPT.md`. Arquitectura de la UI: `ui/README.md`.

## Cómo se opera CFturbo (verificado 2026-10-23, CFturbo 2026.1.1.128)

- Solo modo batch: `CFturbo.exe -batch archivo.cft-batch -log archivo.log`. Sin GUI. rc=0 limpio,
  1 con avisos, 2 con errores. Primera corrida ~30-70 s (arranque), siguientes ~5-10 s.
- El `.cft` es XML plano. **Se edita directamente** (d2, b2, dS, dH, Psi, nBl, Q, H, n, …) sobre
  una copia en la carpeta temporal, y CFturbo regenera la geometría al abrirlo en batch. Probado:
  d2 0.2063→0.215 m y nBl 6→7 se conservan en el `.cft` guardado y el STL del impulsor crece.
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
| `cft_info(project)` | punto de diseño (Q m³/h, H m, n rpm, nq), fluido, componentes, d2/b2/dS/dH/Psi/nBl/volute_d_out/AutoUpdate. `project` = nombre o ruta a un `.cft` (vale el `_out.cft` de una corrida) |
| `cft_params(project, filter, limit)` | alias con valor actual + hojas del XML que cumplan el regex (para parámetros sin alias) |
| `cft_run(project, edits, name, exports, save)` | copia a `%TEMP%\cfturbo-agent\<name>_<ts>\`, edita, corre, exporta; devuelve `requested_si`, `realized`, `corrected`, `warnings`, `errors`, `exports`, `geometry`, `run_dir`. Falla con «CFturbo ocupado» si hay otra corrida |
| `cft_runs(limit=20)` | últimas corridas, temporales y guardadas (`saved`), más reciente primero |
| `cft_save(run_id, name, note)` | copia una corrida a `versions/<name>/` y la anota en la bitácora |
| `cft_log(run_dir, tail)` | cola de `cfturbo.log` (ruta o id de corrida) |
| `cft_nq(Q_m3h, H_m, n_rpm)` | nq y tipo de máquina orientativo |
| `cft_recipe_search(query)` / `cft_recipe_save(name, body)` | memoria: recetas + bitácora (ranking por palabras coincidentes, top 10) |

Claves de `edits`:
- alias SI: `Q` m³/s, `H` m, `n` 1/s, `rho`, `d2` `b2` `dS` `dH` m, `Psi`, `b2_d2`, `EtaH`, `nBl`,
  `AutoUpdate`, `volute_d_out` m;
- con unidad: `Q_m3h`, `H_m`, `n_rpm`, `d2_mm`, `b2_mm`, `dS_mm`, `dH_mm`, `volute_d_out_mm`;
- especial `ext_outlet` (bool): `False` apaga la extensión CFD de salida del impulsor **y borra el
  objeto** `CFDSetup_RotSym_Extension_Outlet` (solo la bandera no basta: CFturbo la reactiva). Si el
  proyecto no tiene `CFDSetup_RotSym`, la corrida sale con error «parámetro no encontrado»;
- cualquier sufijo o regex de ruta del XML tal como lo lista `cft_params`; debe dar una sola hoja.
  Conocida: `MeanSurface[Mean surface]/Coupled: False` (desacopla líneas medias; quita «Coupling
  partially deactivated» al cambiar nBl). Booleanos como texto («false») se normalizan a `False`.

Corridas y versiones:
- Temporales en `%TEMP%\cfturbo-agent\<name>_<ts>\` (`CFTURBO_WORKDIR` lo cambia). Se podan solas:
  quedan las 8 últimas (`KEEP_TMP`). Cada una trae `<name>.cft` editado, `.cft-batch`, `.cft-res`,
  `<name>_out.cft`, `*.log`, STEP/`.cfturbo-ccm`/`.java`, STL, `run.json` y `thumb.png` (miniatura).
- `cft_save` / «Guardar versión» copia la carpeta entera (con `thumb.png`) a `versions/<nombre>/`
  (no va a git; error si el nombre ya existe). La temporal queda marcada `saved_as_version` y la
  versión lleva `saved_from`.
- Candado entre procesos: `%TEMP%\cfturbo-agent\running.lock` (JSON con pid, name, t, started),
  creado de forma atómica en `run_batch` y borrado al terminar. Se descarta si el PID murió o tiene
  > 40 min. Cubre UI, chat y otras sesiones de Claude Code: una corrida de CFturbo a la vez en el PC.
- Bitácora: cada corrida no fallida y cada versión guardada añaden una línea a `recipes/bitacora.md`
  (pedido, dims resultantes, estado, correcciones). `cft_recipe_search` la indexa.
- **Regla:** antes de proponer, `cft_recipe_search`; después de algo que funcionó, `cft_recipe_save`
  con el porqué.

`python mcp_server.py --selftest` debe pasar siempre antes de un commit (CFturbo falso, sin licencia).

## Interfaz controladora: `ui/`

`ui/server.py` (FastAPI) + `ui/index.html` (marcado) + `ui/app.js` (módulo ES, three.js por CDN,
sin build) + `ui/style.css`. Arranque: preview `cfturbo-ui` (`.claude/launch.json` de la raíz, puerto
8765) o `cfturbo\.venv\Scripts\python -m uvicorn --app-dir cfturbo ui.server:app --port 8765`.
Detalle técnico y cómo extenderla: `ui/README.md`.

Layout (≥ 1100 px tres columnas; < 1100 px apilado, galería en tira y pie de Ejecutar fijo):
- **Topbar**: estado («Listo · N corridas · M versiones», «CFturbo trabajando · nombre · N s»,
  «Claude trabajando»), tema claro/oscuro `◐`. Si el servidor cae: banda «Sin conexión… Reintento
  en N s» (3 → 6 → 12 → 30 s) con botón Reintentar.
- **Explorador** (izq.): proyecto base con nq; **galería** de tarjetas (miniatura, nombre, fecha, d2,
  z, estado, ★, ⚠ n avisos) con filtros Todas / ★ Versiones / Temporales / Con avisos.
- **Centro**: runbar (corrida activa, estado, fecha · duración, chip «Siguiendo la última» /
  «Fijada», ★ Guardar versión con nombre en línea, Abrir carpeta); visor 3D (piezas por componente,
  tapas in/out, Encuadrar, Iso/Axial/Lateral); **dock** con pestañas Chat · Hitos y avisos ·
  Archivos · Comparar, plegable y de alto arrastrable (pestaña, plegado y alto quedan en
  `localStorage`).
- **Propiedades** (der.): «Partir de: Proyecto base | Corrida» (la corrida usa su `_out.cft`; no
  disponible si está corriendo o con error), tabla Base / Corrida / Nuevo con nq en vivo, Opciones
  (AutoUpdate; «Quitar extensión CFD de salida» = `ext_outlet=False`, **marcada por defecto**;
  exportar STEP y STL), nombre (por defecto `<proyecto>_<n>`), **▶ Ejecutar** y **Pedir a Claude**.

Comportamiento:
- Ejecutar → `POST /api/run` (409 si hay candado). La columna Nuevo se vacía al lanzar. La vista
  salta sola a cada corrida nueva salvo que se haya fijado otra (clic en tarjeta = fijar; entonces
  solo avisa con un toast).
- Miniaturas: al abrir en el visor una corrida OK/con avisos sin miniatura, se renderiza 320×240 en
  vista iso y se sube a `POST /api/runs/{id}/thumb` (PNG < 500 KB) → `thumb.png`.
- Comparar A/B: Ctrl+clic o `⇄` en una tarjeta elige B; tabla con Δ y Δ % (color si |Δ %| ≥ 1),
  avisos solo en A / solo en B / en ambas; Intercambiar, Quitar B, Pedir comparación a Claude.
- Hitos y avisos: errores (con caja «Qué hacer» y enlace para pedir a Claude que lo corrija),
  correcciones de CFturbo, avisos deduplicados, hitos con hora.
- Archivos: STEP/ccm/java descargables, nº de STL, ruta de la corrida, Abrir carpeta.

Atajos: `Ctrl+Enter` ejecuta (fuera del chat) · `F` encuadra · `1`/`2`/`3` iso/axial/lateral ·
`` ` `` pliega el dock · `Esc` cierra el nombre de versión o quita B · galería: flechas, `Enter` = A,
`Ctrl+Enter` = B · pestañas: ←/→ · visor enfocado: flechas orbitan, `+`/`-` zoom · chat: `Enter`
envía, `Shift+Enter` salto, `↑` recupera el último mensaje.

Endpoints: `GET /api/projects`, `GET /api/project/{name}`, `GET /api/runs?limit&fields=summary`
(ligero para el sondeo de 3 s: sin eventos, geometría ni exports; añade `n_stl`, `n_files`; `thumb`
siempre), `GET /api/runs/{id}` (run.json completo), `POST /api/run`, `GET /api/status` (`running`,
`running_name`, `running_since`, `chatting`, rutas), `POST /api/save` (404/409), `POST /api/open`,
`POST /api/runs/{id}/thumb`, `GET /files/{id}/{archivo}`, `POST /api/chat` (SSE), `POST /api/chat/stop`.

**Chat con Claude Code** (`POST /api/chat`, SSE): el servidor lanza `claude -p <msg> --output-format
stream-json --verbose --mcp-config .mcp.json --strict-mcp-config --allowedTools
"mcp__cfturbo__*,Read,Glob,Grep" --disallowedTools "Bash,Write,Edit,…" --append-system-prompt
CHAT_SYSTEM --max-turns 30 [--resume <sesión>]` con el entorno limpio de variables `CLAUDE*` (usa su
propio login, no la sesión anidada). Suscripción del usuario, sin API key. Un chat a la vez. Solo se
muestran las tools `cft_*` (ToolSearch, Read… quedan ocultas). Detener mata el proceso y emite
`stopped`. Requiere `claude auth login` una vez en una terminal; si el token caducó la CLI responde
«401 OAuth access token is invalid» y la página muestra una tarjeta con el comando. Sin `--bare`
(desactiva el llavero). `CFT_CLAUDE_BIN` apunta a una CLI simulada para probar el panel.

## Flujo estándar

1. Usuario da punto de diseño: Q, H, n, fluido, uso (bomba o PAT). `cft_nq` para clasificar.
2. `cft_recipe_search` (recetas + bitácora) y `cft_projects` + `cft_info` del proyecto base más
   cercano en nq. Si no hay ninguno razonable, pedir al usuario que cree la bomba base en la GUI y
   la guarde en `projects/`.
3. Proponer cambios con criterio de turbomáquinas (Euler, b2/d2, Psi, número de álabes, ángulos)
   y correr `cft_run` con nombre descriptivo. Varias variantes = varias corridas (una a la vez).
   Para iterar sobre un resultado, `project` = ruta al `_out.cft` de esa corrida.
4. Revisar avisos/errores y corregir los de geometría (ver Reglas). Reportar en tabla: pedido vs
   realizado, correcciones de CFturbo, avisos, rutas de los STEP. Si CFturbo corrige un valor,
   decirlo; no asumir que se aplicó lo pedido.
5. Cuando el usuario diga que un diseño le sirve: `cft_save` (nombre corto, `note` con el porqué) y
   `cft_recipe_save` con el aprendizaje.
6. Entregar `versions/<nombre>/` (STEP + `.cfturbo-ccm` + `.java`) al agente CFD de la MV y cerrar el
   loop con H y eficiencia. Hasta entonces, estimación 1D con las dimensiones.

## Reglas

- **Avisos y errores de geometría se corrigen sin que lo pidan, pero solo en corridas que Claude
  lanza** (diseñar o variar): solapamientos, intersecciones, extensiones, «flow path intersects»,
  acoplamiento de líneas medias → `cft_recipe_search`, corregir en una corrida nueva (máx. 3
  intentos) y reportar qué quedó. Si piden resumen, comparación o información: **solo leer** y
  ofrecer la corrección, sin `cft_run` ni `cft_save`. Avisos informativos (ángulos automáticos,
  contorno actualizado): solo mencionarlos. Ver `recipes/regla-avisos.md`.
- Recetas conocidas: extensión que invade la voluta → `ext_outlet=False`
  (`recipes/fix-extension-overlap.md`); «Coupling partially deactivated» al cambiar nBl →
  `MeanSurface[Mean surface]/Coupled=False` (`recipes/fix-blade-coupling-deactivated.md`).
- **No aplicar `ext_outlet=False`** si el impulsor no tiene componente aguas abajo (export solo del
  rotor): ahí la extensión da el dominio de salida para CFD. En la UI, desmarcar la opción.
- Si `cft_run` dice que CFturbo está ocupado: esperar y reintentar una vez; no insistir.
- Nunca editar el `.cft` de `projects/`; `cft_run` siempre trabaja sobre la copia temporal.
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
- 2026-10-23: en Windows `os.kill(pid, 0)` no comprueba: **mata** el proceso. Para saber si un PID
  vive: `OpenProcess` + `GetExitCodeProcess` (== 259, STILL_ACTIVE) vía ctypes.
- 2026-10-23: un candado en memoria del servidor web no ve las corridas del chat (otro proceso, vía
  MCP). El candado va en disco (`running.lock`, creación atómica con `open("x")`).
- 2026-10-23: CFturbo guarda booleanos como `True`/`False`; pedir «false» daba un falso «CFturbo
  corrigió». `_to_si` capitaliza y la comparación de texto ignora mayúsculas.
- 2026-10-23: con «corrige siempre los avisos» en el prompt del chat, un simple «resumen» lanzaba
  corridas. La regla se limita a corridas que Claude lanza en esa petición.
- 2026-10-23: cambiar nBl deja «Coupling partially deactivated»; `MeanSurface[Mean surface]/Coupled=False`
  lo quita (rc=0) sin tocar d2, b2 ni el punto de diseño.
