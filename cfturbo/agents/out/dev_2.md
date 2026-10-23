# Programador · ronda 2

Autor: Programador (Opus) · 2026-10-23 · Rama `worktree-agent-afb88ab464829d569` (worktree
`.claude/worktrees/agent-afb88ab464829d569`), un commit, sin push. Base: `eval_1.md`, `docs_1.md`, `dev_1.md` (P2-1/2/3),
`ux_2.md` (llegó a mitad de ronda y está incorporado entero) y la petición del usuario de tema claro por defecto.

## Hecho

### P1
| Defecto | Solución | Verificado |
|---|---|---|
| D-N1 galería solapada | `.gallery{grid-auto-rows:max-content;align-items:stretch}` + `.card-run{overflow:clip}` (la causa era `overflow:hidden`: contenedor de scroll con alto mínimo 0), miniatura 16:10, meta de alto fijo, error en 1 línea; a 1100–1279 lista con `minmax(0,1fr)` (antes desbordaba en horizontal) | `elementFromPoint` sobre nombre, fecha, d2, z, tag y ⚠ de cada tarjeta: **0 tapadas** a 1150 (45 puntos), 1400 (45) y 1920 (45), y con 20 corridas (114 puntos en tarjetas, 94 en lista). Filas iguales (186/186, 187/187…) |
| D-N3 nombre truncado | nombre `flex:0 0 auto` (máx. 32ch), tags `nowrap`, cede `#runmeta` con «…»; `<span class="long">` oculta «la última», «Abrir », «Miniatura» entre 1100 y 1279; en el runbar «★ como X» pasa a «★» con `title` | `#runtitle` 94/94 a 1150, 1400 y 1920; runbar 40 px, `scrollWidth−clientWidth = 0` |
| D-N2 candado por WORKDIR | `LOCK_FILE = %TEMP%\cfturbo-agent\running.lock` fijo para todos los procesos; `CFTURBO_VERSIONS` aísla `versions/`; `acquire_lock()` público | Con una corrida real en marcha, un proceso con `CFTURBO_WORKDIR=%TEMP%\cfturbo-otro` → `CFturboBusy … dev2_d2_216`. Selftest: otro WORKDIR queda bloqueado |

### P2 / P3 y ux_2
- **D-N4**: «Corriendo X… N s» usa la fila `running` > `running_since` del candado > esta pestaña. Candado externo creado 3 s antes → el contador coincidía con el reloj (13 s a las 07:39:12 para `started` 07:38:59).
- **D-N5**: pie con `#runsum` («1 cambio · desde la base · sin extensión CFD · **AutoUpdate activo**» en ámbar); al lanzar con AutoUpdate se desmarca y avisa con toast; si una corrida falla con AutoUpdate y sigue marcada, se desmarca.
- **D-N6**: `list_runs` anula `saved_as_version` si `versions/<X>/run.json` no existe, y la UI solo pinta «★ como X» si hay una tarjeta ★ X (assert en selftest).
- **D16**: un solo endpoint `GET /api/poll` (runs summary + status), `AbortController` de 8 s, nunca dos peticiones a la vez, backoff 4 → 8 → 16 → 30 s con cuenta atrás real («Reintento en 16 s… 12… 7… 2»). Caída de ~50 s: **4** `ERR_CONNECTION_REFUSED` en consola; vuelve sola con toast.
- **Quitar extensión CFD**: `project_info` da `cfd_ext_outlet` (None/True/False). Marcada por defecto solo si el origen la tiene activa; deshabilitada (con `title`) si no hay `CFDSetup_RotSym`, y entonces no se envía. Partiendo de una corrida que ya la quitó, sale desmarcada.
- **Pedir a Claude**: incluye origen (ruta del `_out.cft` si «Partir de» es una corrida), cambios, AutoUpdate/ext_outlet y `exports` reales. Comprobado capturando el cuerpo de `/api/chat`.
- **«8» de la nota**: viene de `status.keep_tmp`.
- **P2-1** chip «Superponer B» (Comparar) y casilla «B en alambre» (visor): B en alambre cian `opacity .35`, sin extensiones ni tapas; el encuadre abarca A y B; preferencia en `localStorage`. Verificado: 11 superficies de B sobre `dev2_v1`.
- **P2-2** botón «↻ Miniatura» en el runbar: guarda la vista actual como `thumb.png` (toast; la tarjeta cambia de `?v=`).
- **P2-3** densidad «Lista / Tarjetas» en la cabecera de la galería, persistente (`cft_density`).
- **P3 y ux_2**: `aria-pressed` solo en la vista activa (se limpia al orbitar); coma decimal en toda la UI (el diseñador eligió coma; los inputs son texto `inputmode=decimal` y aceptan coma o punto, valor no numérico → borde rojo y no se envía); `runmsg` ok/warn/err; filtros «Avisos» y «Error» separados con contador; `---` → `<hr>`; popover de atajos con botón `?` y tecla `?` (Esc o clic fuera cierra); ⇄ visible (55 %) en todas las tarjetas y al 100 % con foco; «Sin miniatura · se crea al abrirla»; nota de galería en dos líneas; Opciones abiertas si `innerHeight ≥ 820` (y ≥ 1100 de ancho; solo se recuerda si el usuario las toca); chat vacío con ayuda centrada y los botones rápidos dentro; `vmsg` corto y ayuda de ratón en el `title` del visor; mínimo 12 px en todo texto visible (medido: 0 nodos < 12 px); roving tabindex en la galería (+ Home/End); `#vsummary` con `aria-label`; a < 1100: dock antes de propiedades y explorador, tira de 140 px, visor 48vh → página **1843 px** a 800×900, dock en y=516, sin scroll horizontal. Con pantalla alta el pie de Ejecutar sube bajo las Opciones (sin hueco muerto en medio).
- **Tema claro por defecto** (petición del usuario): sin `cft_theme` se aplica `light`; ◐ cambia y se guarda. Tokens claros oscurecidos para contraste ≥ 4,5 sobre su fondo: `--ok #18712f` (5,2), `--warn #875a00` (5,3), `--err #b4232c` (5,3), `--acc #0862a5` (5,3 sobre `--acc-bg`, 6,4 con texto blanco), `--saved #6c3fbf` (5,6), `--cmp #0b7368` (5,7), `--mut #526070` (5,5–5,7).
- **Estado vacío del visor** tapado por el lienzo (no se veía nunca): `z-index:1`.

### Estabilidad
- `renderActive` dividido en `renderRunbar/renderEvents/renderFiles/renderSaveBtn`; `onRuns` en `notifyFinished` + `autoSelect`; el chat en `onChatEvent`.
- `selectRun` ya no calla errores: banda roja en el visor «No pude abrir la corrida X: …» con Reintentar + toast; runbar `.busy` mientras carga.
- `api_run` toma el candado en disco ANTES de responder: 409 «CFturbo trabajando (X)» en vez de `started` + `CFturboBusy` tragado. Probado: segundo `POST /api/run` durante la corrida → 409.
- `stderr` del chat se lee en un hilo (cola de 40 líneas).
- Detener mata el árbol (`taskkill /PID … /T /F`). Probado con el chat corriendo `cft_run dev2_stop`: en 2 s no queda `CFturbo.exe` ni candado. La corrida a medias queda `running` sin candado y `list_runs` la marca **error «Corrida interrumpida»** a los 15 s (antes quedaba «Corriendo…» para siempre). Selftest cubre el caso.
- Sesión de chat guardada que la CLI ya no conoce («No conversation found», p.ej. creada desde otra carpeta): se borra y el mensaje se reenvía UNA vez en una conversación nueva (antes: error y nada más).
- `limit` de `/api/runs` y `/api/poll` acotado a 1–500.

## Fuera (y por qué)
- Recapturar miniatura está en el runbar, no en un menú de la tarjeta (ux_2 lo sugería en la tarjeta; el runbar es donde está la vista que se captura).
- Las miniaturas ya capturadas con el tema oscuro conservan su fondo oscuro; las nuevas salen con el fondo del tema activo. No se regeneran solas (se puede con ↻).
- `list_projects()["runs_total"]` (docs_1 #9) y `projects/README.md` (#11, no se toca `projects/`) siguen igual.
- Comparar sigue usando la tabla de parámetros; la superposición no alinea ejes si A y B tuvieran orígenes distintos (en CFturbo comparten origen).

## Verificación
- `python mcp_server.py --selftest` → `selftest OK` (nuevos asserts: `cfd_ext_outlet` True/False, candado global con otro WORKDIR, `acquire_lock` + `run_batch(lock=…)` lo libera, corrida huérfana → interrumpida, `saved_as_version` colgante → None).
- MCP stdio: `initialize` + `tools/list` → 10 tools `cft_*`.
- Servidor propio `uvicorn --app-dir <worktree>\cfturbo ui.server:app --port 8766` (con `.mcp.json` local, ignorado por git, apuntando al `mcp_server.py` del worktree). Medidas con `getBoundingClientRect`/`elementFromPoint` a 1150×760, 1400×900, 1920×1080 y 800×900 (arriba).
- Corrida real **`dev2_d2_216`** desde la UI (d2 escrito «216,0»): botón, topbar y tarjeta «Corriendo… N s», 409 a un segundo POST, terminó en 30,9 s con 1 aviso (toast + `runmsg` ámbar), `realized d2_mm=0.216`, `ext_outlet=False`, miniatura automática.
- Versión **`dev2_v1`** con Enter en el nombre en línea: toast, tarjeta «★ Guardada», temporal «★ como dev2_v1», contadores Todas 9 / ★ 1.
- Comparar `dev2_v1` (A) con `eval1_chat_7al` (B): d2 216,0 vs 212,0 → −4,0 / −1,9 %; superposición en alambre.
- Chat: «Resumen» con sesión caducada → reintento automático, `cft_runs`, respuesta con tablas y `<hr>` en 29 s, 3 turnos. Detener durante `cft_run` (arriba).
- Galería aislada (`CFTURBO_WORKDIR` + `CFTURBO_VERSIONS` en el scratchpad, puerto 8768): **0 corridas** → «Aún no hay corridas…», contadores a 0, visor con su mensaje de vacío; **20 corridas** (14 temporales + 6 versiones, `run.json` falsos) → chips 20 / 6 / 14 / 8 / 4, scroll propio de la galería, página sin scroll, 0 tapadas, un solo `tabindex=0`.
- Consola: 0 mensajes en las pestañas de prueba salvo los 4 `ERR_CONNECTION_REFUSED` de la caída provocada.
- Servidores 8766 y 8768 apagados al terminar.

## Rama
`worktree-agent-afb88ab464829d569`, commit «ronda 2 del programador…». Archivos: `mcp_server.py`, `ui/server.py`, `ui/app.js`,
`ui/index.html`, `ui/style.css`, `ui/README.md`, `agents/out/ux_2.md` (copia del checkout principal), `agents/out/dev_2.md`.
`bootstrap.sh` (raíz) ya venía modificado y no se incluyó.
