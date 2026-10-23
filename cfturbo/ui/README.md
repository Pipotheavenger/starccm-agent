# ui/ · interfaz controladora

Página local para ver, ejecutar, comparar y borrar corridas de CFturbo, crear bombas nuevas y hablar
con Claude Code. Sin build: FastAPI sirve tres archivos estáticos; three.js llega por CDN (importmap,
con `modulepreload`).

| archivo | qué tiene |
|---|---|
| `server.py` | FastAPI: página, API `/api/*`, archivos (`/files`, `/stl`), chat (lanza `claude -p` y traduce a SSE), validación y errores JSON, cierre de procesos al apagar |
| `index.html` | solo marcado, importmap, popover `?` y diálogo «＋ Nueva»; cada control tiene `id` fijo |
| `app.js` | módulo ES: estado `st`, sondeo con ETag, galería, tabla (`PARAMS`), bomba nueva, comparar, curvas SVG, dock, chat, visor three.js con caché de STL, miniaturas, teclado |
| `style.css` | tokens (`--col-l`, `--col-r`, `--dock-h`, `--viewer-bg`…), tema claro/oscuro, apilado < 1100 px |

La lógica de CFturbo no vive aquí: `server.py` importa `../mcp_server.py` (`run_batch`, `list_runs`,
`save_version`, `delete_run`, `suggest_base`, `new_project`, `stl_binary`, `run_lock_info`…). Es el
mismo código que usan las tools `cft_*`.

## Flujo de datos

```
run_batch (UI o chat/MCP) ──escribe──> %TEMP%\cfturbo-agent\<id>\run.json  (en cada hito, atómico)
                                       + running.lock mientras corre
app.js cada 3 s ──> GET /api/poll  (fila ligera de galería + status, UNA petición, límite 8 s,
   │                                  If-None-Match: 304 sin cuerpo si nada cambió → no se repinta)
   ├─ galería, topbar, botón Ejecutar
   └─ si cambia la corrida activa (o B) ──> GET /api/runs/{id} (run.json completo)
          ├─ tabla «Corrida», hitos/avisos/«Diseño», archivos, curvas, comparar
          └─ visor: GET /stl/{id}/<stl> (binario; caché .visor/ en el servidor y 1 h en el navegador;
                    geometrías en memoria para A, B y las 3 últimas vistas, el resto con dispose)
                    sin miniatura ──> POST /api/runs/{id}/thumb (requestIdleCallback)
```

- Servidor: `list_runs` relee un `run.json` solo si cambió su mtime/tamaño (caché en memoria).
- `/api/run` corre en un hilo; al terminar convierte los STL a binario (~1,3 s, fuera del candado),
  así la página los encuentra listos. Las corridas del chat se convierten la primera vez que se abren.
- Caché `.visor/`: `<corrida>/.visor/<archivo>.stl` binario (≈ 5× menos bytes). Se crea una vez con un
  candado por archivo, viaja con la versión al guardar y se borra con la poda o al borrar la corrida.
  Si el STL ya es binario o está vacío se sirve tal cual.
- Visor: render bajo demanda (sin bucle en reposo); `setTimeout` de respaldo si la pestaña está oculta.
- Versiones: `versions/<nombre>/run.json` aparece en el mismo listado con `saved=true`.
- Si el sondeo falla: banda «Sin conexión» con cuenta atrás y reintentos a 4 → 8 → 16 → 30 s; si el
  servidor responde con error (500…), «El servidor local respondió con error…».

## Endpoints

Errores siempre `{"detail": "texto"}` (también 422 de validación y 500 inesperados). Ids y nombres de
archivo sin `/ \ :` ni `..` (400).

| método y ruta | qué hace |
|---|---|
| `GET /` · `/app.js` · `/style.css` | página (js/css con `Cache-Control: no-cache`) |
| `GET /api/projects` · `/api/project/{name}` | proyectos base e info (`project_info`; 404, 422 si el `.cft` no es XML) |
| `GET /api/poll?limit=40` | `{runs, status}` con ETag (304 si no cambió): lo único que sondea la página |
| `GET /api/runs?limit=50&fields=summary` | listado con ETag; `limit` acotado a 1…500. `summary` = fila de galería: `id name started status seconds d2_mm nBl n_warn error autoupdate n_stl n_files saved_as_version saved thumb`. Sin `fields`: claves de `cft_runs` |
| `GET /api/runs/{id}` | `run.json` completo (`curves`, `report`, `timing`…); 500 «run.json ilegible» si está roto |
| `DELETE /api/runs/{id}` | borra temporal o versión; 409 si está corriendo, 404 si no existe |
| `POST /api/run` `{project, edits, name, exports, save}` | toma el candado global ANTES de responder (409 si otro lo tiene, 404 si no existe el proyecto) y corre en un hilo. `exports` ⊂ `StarCCM OpenFOAM General Report PerformanceData`; `edits` ≤ 50 claves, valores número finito, texto ≤ 200, booleano o `[cubo, corona]` (422 si no) |
| `GET /api/status` | `running`, `running_name`, `running_since`, `chatting`, `claude`, `workdir`, `versions`, `lock_file`, `keep_tmp` |
| `POST /api/save` `{run_id, name, note}` | guarda versión; 404 / 409 si el nombre existe |
| `POST /api/open` `{run_id}` | abre la carpeta en el Explorador |
| `POST /api/runs/{id}/thumb` (cuerpo PNG) | guarda `thumb.png`; 400 si no es PNG o > 500 KB |
| `GET /api/new/suggest?Q&H&n[&base]` | base más cercana en nq (o la pedida): `nq tipo base base_name nq_base ratio k aviso bases[]`; 400 si Q, H o n no son > 0 |
| `POST /api/new` `{Q_m3h, H_m, n_rpm, name, base}` | crea `projects/<name>/<name>.cft` por semejanza (no corre: la página lanza `<name>_1` con `/api/run`); 409 si existe |
| `GET /files/{id}/{archivo}` | descarga (STL, STEP…); `thumb.png` y el reporte `.html` se sirven en línea |
| `GET /stl/{id}/{archivo}.stl` | STL binario para el visor (`Cache-Control: private, max-age=3600`) |
| `POST /api/chat` `{message, session_id, project}` | SSE (ver abajo); un chat a la vez |
| `POST /api/chat/stop` | mata la CLI del chat y sus hijos (`taskkill /T /F`); una corrida a medias queda «interrumpida» |

Eventos SSE de `/api/chat` (`data: {"kind": …}`): `status` (arrancando), `init` (`session_id`,
`model`), `text`, `tool` (`name`, `input`; solo `cft_*`), `tool_result` (`text` ≤ 600, `is_error`),
`ping` (cada 15 s sin salida, `t`), `raw` (línea que no es JSON), `result` (`subtype`, `session_id`…),
`error` (incluye «ya hay una conversación en curso» y la cola de stderr), `stopped`, `done` (`rc`).

Log del servidor (`cfturbo-ui`): corrida lanzada y terminada con tiempos por fase, STL convertidos,
versión guardada, borrado, bomba nueva y chat lanzado/terminado/detenido. El log de acceso omite los
200/304 de `/api/poll`, `/api/status`, `/stl/` y miniaturas.

## Añadir un parámetro a la tabla

1. Si no tiene alias, añádelo en `ALIASES` (y en `CONV` si lleva unidad) de `mcp_server.py`, y
   devuélvelo en `_project_info()["dims"]` o `["design_point"]`. Si necesita lógica (como los β),
   una pareja `(aplicar, leer)` en `SPECIAL`.
2. En `app.js`, añade una fila a `PARAMS`: `{ key, sym, label, unit, from: i => i?.dims?.x, d }`
   (`auto: i => …` la pinta en cursiva como automática). `key` es la clave que se envía en `edits`.
   Comparar y «Pedir a Claude» la toman solos.
3. Añade un assert al selftest si tocaste `mcp_server.py`.

## Añadir un panel (pestaña del dock)

1. `index.html`: un `<button role="tab" data-tab="x" aria-controls="tab-x">` en `.dock-tabs` y una
   `<section class="tabpane" id="tab-x" role="tabpanel" hidden>` en `.dock-body`.
2. `app.js`: añade `'tab-x'` a la lista de `openTab()` y `'x'` a la de arranque (final del archivo);
   pinta su contenido desde `renderActive()` (se llama al cambiar de corrida). Si depende del alto del
   dock, repíntalo también en el `ResizeObserver` del dock (como `renderCurves`).
3. Si necesita datos nuevos, un campo en `run.json` (desde `_run_phases`) o un endpoint en `server.py`
   que llame a una función de `mcp_server.py`. Si es pesado, no lo metas en `_summary` (el sondeo).

## Añadir una tool MCP

1. Función en `mcp_server.py` (lógica) y envoltorio `@mcp.tool()` dentro de `serve()` con docstring
   claro: es lo que lee Claude.
2. Si la UI la necesita, endpoint en `server.py` que llame a la misma función; errores con
   `HTTPException(código, "texto")`.
3. Mencionarla en `CHAT_SYSTEM` si el chat debe saber cuándo usarla; tabla de tools en `../CLAUDE.md`;
   assert en el selftest.

## Cómo probar

- `python mcp_server.py --selftest` (CFturbo falso, sin licencia, ~5-7 s; levanta uvicorn en un
  puerto libre para la prueba HTTP si hay fastapi).
- Servidor de desarrollo en otro puerto:
  `.venv\Scripts\python -m uvicorn --app-dir . ui.server:app --port 8766` (desde `cfturbo`).
- Galería aislada (0 o 20 corridas): `CFTURBO_WORKDIR=<carpeta>` y `CFTURBO_VERSIONS=<carpeta>`. El
  candado (`%TEMP%\cfturbo-agent\running.lock`) NO cambia con ellas: sigue siendo uno por PC.
- Chat sin la CLI real: `CFT_CLAUDE_BIN=<script que imprime stream-json>`.
- En el navegador: 0 errores de consola, 1400×900 sin scroll de página, 800×900 apilado (≤ ~1850 px).
- Depuración: `window.__cft` expone `st`, `camera`, `fit`, `selectRun`, `setB`, `deleteRun`,
  `geoCache`, `renders()`…
