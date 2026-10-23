# ui/ · interfaz controladora

Página local para ver, ejecutar y comparar corridas de CFturbo y hablar con Claude Code.
Sin build: FastAPI sirve tres archivos estáticos; three.js llega por CDN (importmap).

| archivo | qué tiene |
|---|---|
| `server.py` | FastAPI: página, API `/api/*`, archivos de corrida, chat (lanza `claude -p` y traduce a SSE) |
| `index.html` | solo marcado e importmap; cada control tiene `id` fijo |
| `app.js` | módulo ES: estado `st`, sondeo, galería, tabla, comparar, dock, chat, visor three.js, teclado |
| `style.css` | tokens (`--col-l`, `--col-r`, `--dock-h`, `--viewer-bg`…), tema claro/oscuro, apilado < 1100 px |

La lógica de CFturbo no vive aquí: `server.py` importa `../mcp_server.py` (`run_batch`, `list_runs`,
`save_version`, `run_lock_info`…). Es el mismo código que usan las tools `cft_*`.

## Flujo de datos

```
run_batch (UI o chat/MCP) ──escribe──> %TEMP%\cfturbo-agent\<id>\run.json  (en cada hito)
                                       + running.lock mientras corre
app.js cada 3 s ──> GET /api/runs?fields=summary + GET /api/status
   ├─ galería, topbar, botón Ejecutar
   └─ si cambia la corrida activa ──> GET /api/runs/{id} (run.json completo)
          ├─ hitos/avisos, archivos, tabla «Corrida», comparar
          └─ visor: GET /files/{id}/<stl> ; si no hay thumb ──> POST /api/runs/{id}/thumb
```

Versiones: `versions/<nombre>/run.json` aparece en el mismo listado con `saved=true`.
Si el sondeo falla: banda «Sin conexión» y reintentos a 3 → 6 → 12 → 30 s.

## Endpoints

| método y ruta | qué hace |
|---|---|
| `GET /` · `/app.js` · `/style.css` | página (js/css con `Cache-Control: no-cache`) |
| `GET /api/projects` · `/api/project/{name}` | proyectos base e info (`project_info`) |
| `GET /api/runs?limit=50&fields=summary` | listado; `summary` quita eventos/geometría/exports y añade `n_stl`, `n_files` |
| `GET /api/runs/{id}` | `run.json` completo |
| `POST /api/run` `{project, edits, name, exports, save}` | corre en un hilo; 409 si hay candado, 404 si no existe el proyecto |
| `GET /api/status` | `running`, `running_name`, `running_since`, `chatting`, `workdir`, `versions`, `keep_tmp` |
| `POST /api/save` `{run_id, name, note}` | guarda versión; 404 / 409 si el nombre existe |
| `POST /api/open` `{run_id}` | abre la carpeta en el Explorador |
| `POST /api/runs/{id}/thumb` (cuerpo PNG) | guarda `thumb.png`; 400 si no es PNG o > 500 KB |
| `GET /files/{id}/{archivo}` | descarga (STL, STEP…); los PNG se sirven en línea |
| `POST /api/chat` `{message, session_id, project}` | SSE: `init`, `status`, `text`, `tool`, `tool_result`, `ping`, `result`, `error`, `stopped`, `done` |
| `POST /api/chat/stop` | mata la CLI del chat en curso |

## Añadir un parámetro a la tabla

1. Si no tiene alias, añádelo en `ALIASES` (y en `CONV` si lleva unidad) de `mcp_server.py`, y
   devuélvelo en `project_info()["dims"]` o `["design_point"]`.
2. En `app.js`, añade una fila a `PARAMS`: `{ key, sym, label, unit, from: i => i?.dims?.x, d }`.
   `key` es la clave que se envía en `edits`. Comparar y «Pedir a Claude» la toman solos.
3. Añade un assert al selftest si tocaste `mcp_server.py`.

## Añadir un panel (pestaña del dock)

1. `index.html`: un `<button role="tab" data-tab="x" aria-controls="tab-x">` en `.dock-tabs` y una
   `<section class="tabpane" id="tab-x" role="tabpanel" hidden>` en `.dock-body`.
2. `app.js`: añade `'tab-x'` a la lista de `openTab()` y `'x'` a la de arranque; pinta su contenido
   en `renderActive()` (se llama al cambiar de corrida).
3. Si necesita datos nuevos, un endpoint en `server.py` que llame a una función de `mcp_server.py`.

## Cómo probar

- `python mcp_server.py --selftest` (CFturbo falso, sin licencia).
- Servidor de desarrollo en otro puerto:
  `.venv\Scripts\python -m uvicorn --app-dir . ui.server:app --port 8766` (desde `cfturbo`).
- Sin tocar las corridas reales: `CFTURBO_WORKDIR=<carpeta vacía>` (sin temporales; las versiones
  de `versions/` siguen apareciendo porque esa ruta es fija).
- Chat sin la CLI real: `CFT_CLAUDE_BIN=<script que imprime stream-json>`.
- En el navegador: 0 errores de consola, 1400×900 sin scroll de página, 800×900 apilado.
- Depuración: `window.__cft` expone `st`, `camera`, `fit`, `selectRun`, `setB`…
