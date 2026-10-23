# cfturbo-agent

Agente que diseña impulsores y volutas de bombas con CFturbo en lenguaje natural.
CFturbo es el generador paramétrico de geometría. Claude decide qué parámetros mover y lee
qué pasó. La evaluación CFD la hace el agente hermano de STAR-CCM+ (carpeta `..`, en la MV Linux).
No hay API de Anthropic en este PC: el cerebro es Claude Code vía MCP, ya sea en esta sesión o
lanzado por la interfaz controladora (`ui/`), que además corre CFturbo directamente, muestra
geometría, curvas y reporte, guarda y borra versiones y crea bombas nuevas por semejanza.
Guía de uso: `PRIMER-PROMPT.md`. Arquitectura de la UI: `ui/README.md`. Prototipo de bomba nueva:
`explora/README.md`. Rondas de desarrollo: `AGENTES.md`.

## Cómo se opera CFturbo (verificado 2026-10-23, CFturbo 2026.1.1.128)

- Solo modo batch: `CFturbo.exe -batch archivo.cft-batch -log archivo.log`. Sin GUI. rc=0 limpio,
  1 con avisos, 2 con errores. Primera corrida ~30-70 s (arranque), siguientes ~5-10 s; desde la UI
  una corrida completa son ~20-40 s.
- El `.cft` es XML plano. **Se edita directamente** (d2, b2, dS, dH, Psi, nBl, Q, H, n, β, …) sobre
  una copia en la carpeta temporal, y CFturbo regenera la geometría al abrirlo en batch. Probado:
  d2 0.2063→0.215 m y nBl 6→7 se conservan en el `.cft` guardado y el STL del impulsor crece.
- El bloque `<Updates>` del batch solo lo acepta CFturbo si la plantilla salió de la GUI
  (PROJECT > Batch mode/Optimization). No se usa.
- Export en batch: `<BatchAction Name="Export">` con hijos `WorkingDir`, `BaseFileName`,
  `ExportInterface Type="Enum"` y `ExportComponents Type="Array1"` cuyos `<Value>` **deben traer
  `Caption="[Nombre]"`** y valor = `Index`+1 del componente. Sin `Caption` solo exporta el primero.
  - `StarCCM` → `<base>_Co1..3.stp` (+ `_Co3_Extension.stp`), `<base>.cfturbo-ccm` (condiciones de
    frontera, rpm, caudal másico) y `CFturbo2StarCCM.java`. Esto es lo que va a la MV.
  - `OpenFOAM` → un STL ASCII por superficie (`BladePS`, `Hub`, `Shroud`, `Spiral`…). Es lo que
    pinta el visor. Granularidad en `Export_Interfaces/TOpenFOAMInterface/STLData` del `.cft`.
  - `General` → `.geo-xml` (solo puntos hub/shroud); STEP/IGES requieren configurarlo en la GUI.
  - `PerformanceData` → `<base>.cft-pp`: curvas «Δpt - ṁ» (bar vs kg/s) y «η - ṁ» (%); sin NPSH.
  - `Report` → `<base>.html` (~730 KB, una tabla con todos los valores de diseño).
- `Save` → `<OutputFile>`; el `.cft-res` se escribe junto al `.cft` de entrada. Los hints
  (acoplamientos, extensiones, licencia) van al `<nombre>.log` que CFturbo crea solo, no al `-log`.
- Cambiar el punto de diseño (Q, H, n) con `AutoUpdate=True` recalcula d2/b2/dS pero puede romper
  el meridiano ("Secondary flow path intersects hub solid"). Para un punto de diseño distinto al de
  la base: `cft_new` (escalado por semejanza, ver Flujo estándar) o una base hecha en la GUI y
  guardada en `projects/<nombre>/<nombre>.cft`.
- Licencia local Uniandes (hasta 2027-02-10): impulsor radial y axial de bomba, impulsor radial de
  compresor, estator, voluta, bladerunner. **Turbinas Francis/Kaplan sin licencia** ("Runner: No
  running license available"). Turbinas solo como bomba-como-turbina (PAT) hasta tener el módulo.

## MCP: `mcp_server.py` (stdio, registrado en `.mcp.json`; selftest incluido)

12 tools:

| tool | qué hace |
|---|---|
| `cft_projects()` | proyectos base en `projects/<nombre>/<nombre>.cft` |
| `cft_info(project)` | punto de diseño (Q m³/h, H m, n rpm, nq), fluido, componentes, `dims` (d2/b2/dS/dH mm, Psi, nBl, b2_d2, EtaH, volute_d_out_mm, AutoUpdate, `beta1/2_hub/shroud_deg`, `s_mm`, `beta_auto1/2`) y `cfd_ext_outlet` (None = sin CFDSetup). `project` = nombre o ruta a un `.cft` (vale el `_out.cft` de una corrida) |
| `cft_params(project, filter="", limit=300)` | alias con valor actual + hojas del XML que cumplan el regex (para parámetros sin alias) |
| `cft_run(project, edits=None, name="design", exports=None, save=True)` | copia a `%TEMP%\cfturbo-agent\<name>_<ts>\`, edita, corre, exporta; devuelve el `run.json` (abajo). Falla con «CFturbo ocupado» si hay otra corrida |
| `cft_runs(limit=20)` | últimas corridas, temporales y guardadas (`saved`), más reciente primero (con `report` y `timing`; sin `curves`) |
| `cft_save(run_id, name=None, note="")` | copia una corrida a `versions/<name>/` y la anota en la bitácora |
| `cft_delete(run_id)` | borra una corrida temporal o una versión (carpeta entera, sin deshacer). Solo si el usuario lo pide. No borra la que está corriendo; una versión borrada deja «VERSIÓN BORRADA» en la bitácora |
| `cft_new(Q_m3h, H_m, n_rpm, name, base=None, run=True)` | bomba nueva por semejanza: crea `projects/<name>/<name>.cft` desde la base más cercana en nq (o `base`, nombre o ruta); con `run` corre `<name>_1`. Devuelve `base`, `base_name`, `nq`, `nq_base`, `ratio`, `k`, `c_axial`, `d2_mm` esperado, `aviso` (> ×1,5) y, si corrió, `run_id`, `status`, `warnings`, `errors`, `d2_mm_cfturbo`, `run_dir` |
| `cft_log(run_dir, tail=80)` | cola de `cfturbo.log` (ruta o id de corrida) |
| `cft_nq(Q_m3h, H_m, n_rpm)` | nq y tipo de máquina orientativo |
| `cft_recipe_search(query)` / `cft_recipe_save(name, body)` | memoria: recetas + bitácora (ranking por palabras coincidentes, top 10) |

Claves de `edits`:
- alias SI: `Q` m³/s, `H` m, `n` 1/s, `rho`, `d2` `b2` `dS` `dH` m, `Psi`, `b2_d2`, `EtaH`, `nBl`,
  `AutoUpdate`, `volute_d_out` m;
- con unidad: `Q_m3h`, `H_m`, `n_rpm`, `d2_mm`, `b2_mm`, `dS_mm`, `dH_mm`, `volute_d_out_mm`;
- especiales (`SPECIAL`: actúan sobre el XML; lo realizado se lee del `_out.cft`):
  - `ext_outlet` (bool): `False` apaga la extensión CFD de salida del impulsor **y borra el objeto**
    `CFDSetup_RotSym_Extension_Outlet` (solo la bandera no basta: CFturbo la reactiva). Sin
    `CFDSetup_RotSym` la corrida sale con error «parámetro no encontrado».
  - `beta1_deg` / `beta2_deg`: número (todos los spans) o `[cubo, corona]` en grados. Escribe
    `BladePropsML/Beta1|Beta2` en rad (índices intermedios interpolados) en todos los álabes del
    impulsor (principal y divisores) y pone `BladeProperties/AutoUpdate1|2=False`.
  - `beta_auto=True`: vuelve a ángulos automáticos (AutoUpdate1 y 2).
  - `s_mm`: espesor de álabe, número o `[cubo, corona]`, en `s1` (borde de ataque) y `s2` (salida).
  - `corrected` compara listas con tolerancia 0,01 y booleanos sin distinguir mayúsculas.
- cualquier sufijo o regex de ruta del XML tal como lo lista `cft_params`; debe dar una sola hoja.
  Clave de acoplamiento: `MeanSurface[Mean surface]/Coupled: False` (desacopla líneas medias; quita
  «Coupling partially deactivated» al cambiar nBl o fijar β2). Booleanos como texto se normalizan.

`exports`: por defecto `StarCCM` + `OpenFOAM`; también `General` y `Report`. `PerformanceData` se
añade **siempre** (curvas, 28 KB, sin coste de tiempo).

`run.json` (lo escribe `run_batch` en cada hito, de forma atómica): `id name project started status
seconds returncode edits requested_si realized corrected exports geometry warnings errors events
actions info run_dir saved` y además:
- `curves`: `Q_m3h`, `H_m`, `eta_pct`, `P_kW` (= ρgQH/η), `design` (punto de diseño), `names` (curvas
  del `.cft-pp`); `NPSH_m` solo si CFturbo la diera (2026.1.1 no). Predicción 1D, no CFD.
- `report` y `report_file` (solo con export `Report`): `beta1_deg`/`beta2_deg` [cubo, corona],
  `wrap_deg`, `throat_mm2`, `w2_w1` [cubo, corona], `eta_h_pct`/`eta_v_pct`/`eta_m_pct`/`eta_st_pct`,
  `cu2` `cm2` `u2`, `P_kW`, `torque_Nm`, `npsha_m`, `npshr_m` (por correlación), `volute_throat_mm2`.
- `timing`: segundos de `preparar`, `cfturbo`, `leer`, `cerrar` y `total`.
- versiones: `saved`, `saved_as`, `saved_from`, `note`; la temporal guardada lleva `saved_as_version`.
- La miniatura no va en `run.json`: es `thumb.png` en la carpeta; el listado añade `thumb` = su mtime
  (0 si no hay).

Corridas y versiones:
- Temporales en `%TEMP%\cfturbo-agent\<name>_<ts>\` (`CFTURBO_WORKDIR` lo cambia). Se podan solas:
  quedan las 8 últimas (`KEEP_TMP`), por la hora del nombre (abrirlas no las rejuvenece). Cada una
  trae `<name>.cft` editado, `.cft-batch`, `.cft-res`, `.cft-pp`, `<name>_out.cft`, `*.log`,
  STEP/`.cfturbo-ccm`/`.java`, STL, `run.json`, `thumb.png` y `.visor/` (STL binarios del visor,
  ~11 MB por corrida abierta en la UI).
- `cft_save` / «Guardar versión» copia la carpeta entera (con `thumb.png` y `.visor/`) a
  `versions/<nombre>/` (no va a git; error si el nombre ya existe). La temporal queda marcada
  `saved_as_version` (deja de anunciarse si la versión se borra) y la versión lleva `saved_from`.
- Nombres de corrida, versión y proyecto pasan por `safe_name` (`[A-Za-z0-9_-]`, el resto «_»).
- Candado entre procesos: `%TEMP%\cfturbo-agent\running.lock` (JSON con pid, name, t, started),
  creado de forma atómica en `run_batch` y borrado al terminar o fallar. Se descarta si el PID murió o
  tiene > 40 min. Cubre UI, chat y otras sesiones: una corrida de CFturbo a la vez en el PC.
- Una excepción dentro de la corrida (sin `CFturbo.exe`, `.cft` roto…) deja `status: error` con el
  mensaje. Una corrida «running» sin candado (su proceso murió) pasa a «Corrida interrumpida».
- Bitácora: cada corrida no fallida, cada versión guardada y cada versión borrada añaden una línea a
  `recipes/bitacora.md`. `cft_recipe_search` la indexa.
- **Regla:** antes de proponer, `cft_recipe_search`; después de algo que funcionó, `cft_recipe_save`
  con el porqué.

`python mcp_server.py --selftest` debe pasar siempre antes de un commit (CFturbo falso, sin licencia,
~5-7 s; incluye casos de borde y una prueba HTTP real del servidor web si hay fastapi).

## Interfaz controladora: `ui/`

`ui/server.py` (FastAPI) + `ui/index.html` (marcado) + `ui/app.js` (módulo ES, three.js por CDN,
sin build) + `ui/style.css`. Arranque: preview `cfturbo-ui` (`.claude/launch.json` de la raíz, puerto
8765) o `cfturbo\.venv\Scripts\python -m uvicorn --app-dir cfturbo ui.server:app --port 8765`.
Endpoints, eventos SSE, caché y cómo extenderla: `ui/README.md`.

Layout (≥ 1100 px tres columnas; < 1100 px apilado, galería en tira y pie de Ejecutar fijo):
- **Topbar**: estado («Listo · …», «CFturbo trabajando · nombre · N s», «Claude trabajando»), `?`
  (popover de atajos) y tema `◐`. Si el servidor cae: banda «Sin conexión… Reintento en N s»
  (4 → 8 → 16 → 30 s) con Reintentar; si responde con error, «El servidor local respondió con error…».
- **Explorador** (izq.): selector de proyecto base con nq y **＋ Nueva** (bomba por semejanza);
  **galería** (miniatura, nombre, fecha, d2, z, estado, ★, ⚠ avisos, 🗑) en tarjetas o «Lista»
  compacta, filtros Todas / ★ Versiones / Temporales / Avisos / Error.
- **Centro**: runbar (corrida activa, estado, fecha · duración, chip ⟳ siguiendo / 📌 fijada,
  ★ Guardar versión con nombre en línea, ↻ Miniatura, Abrir carpeta); visor 3D (piezas por componente,
  tapas, Encuadrar, Iso/Axial/Lateral, B en alambre); **dock** con pestañas Chat · Hitos y avisos ·
  Curvas · Archivos · Comparar, plegable y de alto arrastrable (estado en `localStorage`).
- **Propiedades** (der.): «Partir de: Proyecto base | Corrida» (la corrida usa su `_out.cft`), tabla
  Base / Corrida / Nuevo (Q, H, n, d2, b2, dS, dH, ψ, z, dV, β1 y β2 cubo/corona, s; nq en vivo; los β
  automáticos en cursiva), Opciones (AutoUpdate · Sin extensión CFD · Exportar: STEP · STL · Reporte),
  nombre (por defecto `<proyecto>_<n>`), **▶ Ejecutar** y **Pedir a Claude**. Explicaciones en `title`
  (tooltips), no en letreros.

Comportamiento:
- Ejecutar → `POST /api/run` (409 si hay candado). La vista salta a cada corrida nueva salvo que se
  haya fijado otra (clic en tarjeta); entonces solo avisa con un toast.
- β en la tabla: las dos filas de un ángulo se envían juntas como `beta{1,2}_deg=[cubo, corona]`; el
  span vacío toma el valor del origen. No hay control para `beta_auto=True` (solo MCP/chat).
- «Sin extensión CFD» se marca sola si el origen tiene la extensión activa y se deshabilita si el
  proyecto no tiene `CFDSetup_RotSym`.
- Borrar: 🗑 en la tarjeta o `Supr` → «¿Borrar? Sí / No» en la propia tarjeta (6 s; Esc o No cancela).
  Si era la activa pasa a la vecina; si era B, se quita B. La que está corriendo no se puede borrar.
- ＋ Nueva: diálogo con Q, H, n, nombre (por defecto `bomba_Q…_H…_n…`) y base (sugerida, con su nq);
  línea nq · tipo · base · ×ratio · k y ⚠ si el salto de nq es > ×1,5. «Crear y correr» crea el
  proyecto, lo elige en el selector y lanza `<nombre>_1`.
- Curvas: H-Q (con punto de diseño), η-Q y P-Q en SVG, lectura con el puntero; A continua, B discontinua.
- Reporte: con la casilla, bloque «Diseño» en Hitos y enlace «Reporte ↗» (HTML en pestaña nueva),
  grupo «Reporte» en Archivos y filas con Δ en Comparar.
- Miniaturas: al abrir una corrida OK/con avisos sin miniatura se renderiza 320×240 iso sobre fondo
  neutro cuando el navegador está libre y se sube a `POST /api/runs/{id}/thumb`; ↻ Miniatura la rehace
  con la vista actual.
- Comparar A/B: Ctrl+clic o `⇄` elige B; tabla con Δ y Δ % (incluye β, s y reporte), avisos solo en A /
  solo en B / en ambas, H-Q de A y B, Superponer B, Intercambiar, Quitar B, Pedir comparación a Claude.
- Hitos y avisos: errores con «Qué hacer», correcciones de CFturbo, avisos deduplicados, hitos con hora.

Atajos: `Ctrl+Enter` ejecuta (fuera del chat) · `F` encuadra · `1`/`2`/`3` iso/axial/lateral ·
`` ` `` pliega el dock · `?` atajos · `Esc` cierra el popover o el nombre de versión, o quita B ·
galería: flechas, Inicio/Fin, `Enter` = A, `Ctrl+Enter` = B, `Supr` borra · pestañas: ←/→ · visor
enfocado: flechas orbitan, `+`/`-` zoom · chat: `Enter` envía, `Shift+Enter` salto, `↑` recupera el
último.

Endpoints: `GET /api/projects`, `GET /api/project/{name}`, `GET /api/poll` (galería + estado, ETag/304:
lo único que sondea la página cada 3 s), `GET /api/runs?limit&fields=summary` (ETag),
`GET|DELETE /api/runs/{id}`, `POST /api/run`, `GET /api/status`, `POST /api/save`, `POST /api/open`,
`POST /api/runs/{id}/thumb`, `GET /api/new/suggest?Q&H&n[&base]`, `POST /api/new`,
`GET /files/{id}/{archivo}` (descarga; PNG y reporte HTML en línea), `GET /stl/{id}/{archivo}` (STL
binario, caché en `<corrida>/.visor/`), `POST /api/chat` (SSE), `POST /api/chat/stop`. Errores
siempre `{"detail": "texto"}`.

**Chat con Claude Code** (`POST /api/chat`, SSE): el servidor lanza `claude -p <msg> --output-format
stream-json --verbose --mcp-config .mcp.json --strict-mcp-config --allowedTools
"mcp__cfturbo__*,Read,Glob,Grep" --disallowedTools "Bash,Write,Edit,NotebookEdit,WebFetch,WebSearch"
--append-system-prompt CHAT_SYSTEM --max-turns 30 [--resume <sesión>]` con el entorno limpio de
variables `CLAUDE*`. Suscripción del usuario, sin API key. Un chat a la vez. Solo se muestran las tools
`cft_*`. Detener, cerrar la página a media respuesta o apagar el servidor matan la CLI y sus hijos.
Requiere `claude auth login` una vez; con el token caducado («401 OAuth…») la página muestra una
tarjeta con el comando. Sin `--bare` (desactiva el llavero). `CFT_CLAUDE_BIN` apunta a una CLI
simulada para pruebas.

## Flujo estándar

1. Usuario da punto de diseño: Q, H, n, fluido, uso (bomba o PAT). `cft_nq` para clasificar.
2. `cft_recipe_search` (recetas + bitácora) y `cft_projects` + `cft_info` del proyecto base más
   cercano en nq.
3. **Bomba nueva por semejanza** si ninguna base de `projects/` está cerca: `cft_new(Q, H, n, name)`
   (o «＋ Nueva» en la UI). Escala el ejemplo de CFturbo (o proyecto) con nq más cercano y corre
   `<name>_1`. Límites: probado hasta nq ×0,53…×1,47 de la base; fuera de ×1,5 devuelve `aviso`
   (mejor crear una base en la GUI para esa banda). Bases: CP nq8, 20, 31, 37, 49 (radial con voluta),
   MP nq94, 125 (semiaxial con difusor), AP nq120, 172, 295 (axial) y todo `projects/*/*.cft` con
   impulsor. Huecos: nq 55-90 y < 8. Ángulos, cubo, ojo y nº de álabes son los del ejemplo: punto de
   partida, no diseño optimizado. Detalle: `recipes/exploracion-desde-cero.md`.
4. Proponer cambios con criterio de turbomáquinas (Euler, b2/d2, Psi, número de álabes, β1/β2,
   espesor) y correr `cft_run` con nombre descriptivo. Varias variantes = varias corridas (una a la
   vez). Para iterar sobre un resultado, `project` = ruta al `_out.cft` de esa corrida. Añadir
   `Report` cuando hagan falta ángulos, garganta, rendimientos o NPSHR.
5. Revisar avisos/errores y corregir los de geometría (ver Reglas). Reportar en tabla: pedido vs
   realizado, correcciones de CFturbo, avisos, rutas de los STEP. Si CFturbo corrige un valor,
   decirlo; no asumir que se aplicó lo pedido.
6. Cuando el usuario diga que un diseño le sirve: `cft_save` (nombre corto, `note` con el porqué) y
   `cft_recipe_save` con el aprendizaje. `cft_delete` solo si lo pide.
7. Entregar `versions/<nombre>/` (STEP + `.cfturbo-ccm` + `.java`) al agente CFD de la MV y cerrar el
   loop con H y eficiencia. Hasta entonces, curvas 1D de CFturbo (`curves`) y reporte.

## Reglas

- **Avisos y errores de geometría se corrigen sin que lo pidan, pero solo en corridas que Claude
  lanza** (diseñar o variar): solapamientos, intersecciones, extensiones, «flow path intersects»,
  acoplamiento de líneas medias → `cft_recipe_search`, corregir en una corrida nueva (máx. 3
  intentos) y reportar qué quedó. Si piden resumen, comparación o información: **solo leer** y
  ofrecer la corrección, sin `cft_run`, `cft_save` ni `cft_delete`. Avisos informativos (ángulos
  automáticos, contorno actualizado): solo mencionarlos. Ver `recipes/regla-avisos.md`.
- Recetas conocidas: extensión que invade la voluta → `ext_outlet=False`
  (`recipes/fix-extension-overlap.md`); «Coupling partially deactivated» al cambiar nBl o fijar β2 →
  `MeanSurface[Mean surface]/Coupled=False` (`recipes/fix-blade-coupling-deactivated.md`). Ejecutar
  desde la UI no lo corrige solo; el chat sí.
- **β fijo desactiva el automático**: `beta1_deg`/`beta2_deg` ponen AutoUpdate1/2=False y CFturbo ya
  no recalcula ese ángulo al cambiar Q, H, n o d2. Para volver: `beta_auto=True`.
- **No aplicar `ext_outlet=False`** si el impulsor no tiene componente aguas abajo (export solo del
  rotor): ahí la extensión da el dominio de salida para CFD. En la UI, desmarcar «Sin extensión CFD».
  Si el proyecto no tiene `CFDSetup_RotSym` la casilla sale deshabilitada y la clave da error.
- Para mover mucho el punto de diseño, `cft_new` (semejanza), no `AutoUpdate=True` (rompe el
  meridiano cuando dS crece).
- Si `cft_run` dice que CFturbo está ocupado: esperar y reintentar una vez; no insistir.
- Nunca editar un `.cft` existente de `projects/`; `cft_run` trabaja sobre la copia temporal.
  `cft_new` solo **crea** carpetas nuevas en `projects/` (409 / error si ya existe).
- Rutas de Windows absolutas en el batch (escapadas: una carpeta con «&» funciona). Unidades del
  `.cft`: SI (m, m³/s, 1/s, rad).
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
  llamar `controls.update()` y renderizar una vez tras cargar (con render bajo demanda: `setTimeout`
  de respaldo).
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
- 2026-10-23: fijar β exige `BladeProperties/AutoUpdate1|2=False`; con True CFturbo pisa el ángulo
  pedido. Fijar β2 deja «Coupling partially deactivated», igual que cambiar nBl.
- 2026-10-23: el `.cft-pp` de 2026.1.1 da Δpt en bar contra ṁ en kg/s y η en %; no trae NPSH. La
  unidad de Δpt se elige reproduciendo la H de diseño.
- 2026-10-23: el reporte HTML es una sola tabla; la jerarquía la dan las celdas `&nbsp;` iniciales.
- 2026-10-23: los STL de los ejemplos de CFturbo se llaman `…-Flowdomain(virtual)-…` y con captions
  sin corchetes; `_STL_RX` acepta ambos (antes salían sin componente).
- 2026-10-23: semejanza: `H6` y `ExtensionLength` son metros (se escalan); la `x` de
  `SpiralCasing/BezierProgr` es un ángulo (no); en axiales hay que escalar la cu de `CuCmDefinition`.
- 2026-10-23: podar por mtime de carpeta salvaba corridas viejas al abrirlas (miniatura, `.visor/`).
  Se poda por la hora del nombre.
- 2026-10-23: un hilo que moría dejaba `run.json` en «running» y a los 15 s salía «interrumpida»
  (engañoso). `run_batch` por fases captura todo y deja `status: error` con el mensaje.
- 2026-10-23: el sondeo podía leer medio `run.json`: `write_json` escribe a un temporal y `os.replace`.
- 2026-10-23: una carpeta con «&» rompía el XML del batch: rutas y captions con `escape`/`quoteattr`.
- 2026-10-23: el 422 de FastAPI trae `detail` como lista y la página mostraba `[object Object]`;
  manejadores propios devuelven siempre `{"detail": "texto"}`.
- 2026-10-23: si el navegador cortaba el SSE a medias, la CLI del chat seguía viva con el candado del
  chat tomado. El `finally` del generador la mata con sus hijos (`taskkill /T /F`).
- 2026-10-23: 20 STL ASCII = 59 MB por corrida; en binario 11,5 MB (`/stl/`, caché `.visor/`): cambiar
  de corrida pasó de ~2,2 s a ~0,46 s. `If-None-Match` puesto a mano en `fetch` sí da 304 en Chrome.
