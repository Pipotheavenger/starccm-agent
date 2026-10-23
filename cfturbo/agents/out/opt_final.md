# Pasada final de optimización

Autor: Programador · 2026-10-23 · rama `worktree-agent-a555ca024b8e3731e`, un commit, sin push. Base: main con las rondas 1–3.
Archivos: `mcp_server.py`, `ui/server.py`, `ui/app.js`, `ui/index.html`, `ui/README.md`, este informe.
Comportamiento visible igual (mismo diseño, mismas funciones); solo más rápido, más robusto o más simple.

## Cifras antes / después

Medido en este PC. «Antes» = el código de main servido desde una copia aparte en el puerto 8767; «después» = el worktree en 8766.
Las dos versiones leían las mismas corridas reales (`opt_base`, `opt_d2_215`: 20 STL cada una). Navegador a 1400×900.

| qué | antes | después |
|---|---|---|
| Bytes de una corrida en el visor (20 STL) | 59 MB ASCII (`/files`) · 133 MB con 25 STL | **11,5 MB binario** (`/stl`, ÷5) |
| Cambiar a otra corrida (primera vez) | 2 223 ms | **456 ms** |
| Volver a una corrida ya vista | 2 375 ms | **58 ms** (caché en memoria) |
| Repetir A → B → B | 2 342 ms | **49 ms** |
| Sondeo de 3 s, cuerpo con 3–4 corridas | 5 070 B en cada sondeo | 1 249 B y después **304 sin cuerpo** (3 de 5 en 15 s) |
| `/api/poll` con 7 corridas (curl) | 8 823 B | 1 257 B |
| `list_runs(40, summary)` con 8 / 30 / 300 corridas | 2,5 / 8,8 / 89 ms | **0,6 / 2,0 / 22 ms** |
| JSON de la galería con 300 corridas | 66 KB | **10 KB** |
| Bucle del visor en reposo | rAF a 60 Hz + intervalo de 30 Hz siempre activos (47 `controls.update` en 3 s con la pestaña en segundo plano) | **1** en 3 s: sin bucle si nada se mueve |
| Geometrías al cambiar de corrida | `group.clear()` sin `dispose`: la GPU acumulaba cada corrida vista | `dispose` de materiales al quitar y de geometrías al salir de la caché (A, B y 3 últimas) |
| Fases de `run_batch` | no se medían | `run.json["timing"]`: corrida real `opt_ui_d2_2125` preparar 0,02 s · cfturbo 30,1 s · leer 0,02 s · cerrar 0 s |
| Convertir los 20 STL a binario | — | 1,2–1,4 s en el hilo de la UI tras la corrida, fuera del candado (la página los encuentra listos) |
| `python mcp_server.py --selftest` | 3,3 s | 5,0–6,7 s con unas 40 aserciones nuevas y una prueba HTTP real (límite: < 10 s) |
| `app.js` | 86 440 B | 88 267 B (+2 %: caché STL, ETag y errores; ver «Qué no») |

La carga inicial de la página ya era rápida (DOMContentLoaded unos 70–100 ms con caché; `app.js` 12 ms). Ahora `index.html` hace
`modulepreload` de `app.js` y de three.js: con la caché fría se ahorra una ida y vuelta, porque three.js ya no espera a que `app.js` lo pida.

## Qué optimicé

### Cliente (`ui/app.js`, `index.html`)
- **Sondeo con ETag**: `request()` (fetch con tiempo límite, `detail` de texto y 304 que no cuenta como error) y `api()` encima.
  `poll()` manda `If-None-Match`; si recibe 304 no toca nada (`onRuns`, `renderStatus`, galería). Los contadores siguen
  con `tickClock`. Si el servidor responde con error (500…), la banda lo dice («El servidor local respondió con error…») en vez de «Sin conexión».
- **Fila ligera**: la galería usa `d2_mm`, `nBl`, `n_warn`, `error` y `autoupdate` de la fila del sondeo. El detalle sigue llegando
  de `/api/runs/{id}` y solo al cambiar de corrida.
- **STL**: los pide de `/stl/` en binario. Caché LRU por corrida (`geoCache`: A, B y las 3 últimas vistas). Las promesas se comparten,
  así que A y B en alambre usan la misma geometría. `dispose` al expulsar y `dropGeo` al borrar; los materiales se liberan con
  `clearGroup` y el material del alambre al recargarlo.
- **Render bajo demanda**: `render()` pide un frame; mientras `controls.update()` amortigua se piden más, y quieto no hay bucle.
  Si el rAF no corre (pestaña oculta), un `setTimeout` de 100 ms pinta igual (respeta la lección de la cámara sin orientar).
- **Miniatura automática** con `requestIdleCallback`: primero se ve la geometría. Las `<img>` de la galería llevan `decoding="async"`.
- **Curvas**: `curveCtx` por zona (`tab`/`cmp`), que se vacía al repintar esa zona. Antes era un array global que se truncaba a 200
  y podía dejar sin puntero a la gráfica de Comparar.
- **Helpers unificados**: `safeName` (mismo criterio que `mcp_server.safe_name`), `thumbUrl` (antes la URL se escribía en dos sitios)
  y `fmtIn` sobre `fmt`. Cabecera del archivo al día.

### Servidor (`ui/server.py`)
- **Errores coherentes**: siempre `{"detail": "texto"}`. Hay manejadores para 422 (validación, antes `detail` era una lista y el
  cliente mostraba `[object Object]`) y para 500 inesperados. Un `run.json` ilegible da 500 «run.json ilegible» y un `.cft` roto, 422.
- **Validación** en todos los endpoints:
  - `RunReq`: `exports` ⊂ `EXPORTS_KNOWN` sin repetidos; `edits` hasta 50 claves, con valores número finito, texto ≤ 200, booleano o [cubo, corona].
  - `SaveReq`, `NewReq`, `OpenReq` y `ChatReq` con longitudes acotadas; `session_id` con patrón.
  - `Q`, `H` y `n` finitos y > 0 (`inf` ya no pasa).
  - Miniatura: se mira `Content-Length` antes de leer el cuerpo.
  - `fields` de `/api/runs` validado; `limit` sigue acotado y no rechazado.
  - Ids sin `/ \ : ..`.
- **ETag** (`_json_etag`, blake2b del cuerpo) en `/api/poll` y `/api/runs`.
- **`/stl/{id}/{archivo}`**: STL binario para el visor, `Cache-Control: private, max-age=3600`.
- **Logs útiles sin ruido**:
  - Un filtro quita del log de acceso los 200/304 de `/api/poll`, `/api/status`, `/stl/` y las miniaturas.
  - El logger `cfturbo-ui` registra: corrida lanzada, fin con estado y tiempos por fase, STL convertidos, versión guardada,
    borrado, bomba nueva, y el chat lanzado, terminado o detenido.
- **Cierre limpio**: en el `lifespan` de apagado se mata el árbol de la CLI del chat y los CFturbo propios (`cft.kill_children()`).
  Si el navegador corta el SSE a medias, el `finally` del generador mata la CLI y sus hijos (antes seguía viva con el candado del chat tomado).
- **Candados**: `RUN_LOCK` se libera con `BaseException`; `_work` lo libera en `finally` y convierte los STL después.
  El candado de disco ahora lo libera `run_batch` también si falla `acquire_lock` o cualquier fase.

### MCP / CFturbo (`mcp_server.py`)
- **`run_batch` por fases** (`_run_phases`) con `run.json["timing"]` = preparar · cfturbo · leer · cerrar · total.
  Cualquier excepción (sin `CFturbo.exe`, `.cft` roto, disco) deja la corrida en `error` con el mensaje. Antes el hilo moría con
  `run.json` en «running» y a los 15 s salía «interrumpida», que era engañoso.
- **Sin trabajo repetido**:
  - El `_out.cft` se parsea una vez para realizados e info (`_project_info(cft, root, leaves)`); antes se leía dos veces.
  - `_leaves` del `.cft` de entrada solo se calcula si hay edits por alias o ruta.
  - Un solo `os.listdir` sirve para log, exports, geometría y reporte; antes había 5–9 globs.
  - `list_projects` contaba las corridas una vez por proyecto; ahora una vez en total.
- **Exports**: PerformanceData siempre (28 KB, sin tiempo apreciable: la fase «leer» entera son 0,02 s), Report solo si se pide.
  `_EXPORT_PATS` y `EXPORTS_KNOWN` quedan como constantes.
- **CFturbo con `Popen`** registrado en `_CHILDREN`, con salida a DEVNULL (antes `capture_output` guardaba en memoria una salida que
  no se usaba) y tiempo límite que mata el proceso. `kill_children()` sirve para el apagado.
- **XML del batch escapado** (`quoteattr`/`escape`): una carpeta con «&» (p. ej. `R&D`) rompía el batch.
- **`list_runs`**:
  - Caché por (mtime_ns, tamaño) de cada `run.json` (`_read_run`), que se invalida al borrar o podar.
  - Fila `summary` mínima (`_summary`).
  - Versiones existentes desde el mismo listado, sin un `is_file` por fila.
  - `_mark_orphan` no muta la caché.
- **`find_run`** busca en dos rutas directas en vez de recorrer todas las carpetas, y rechaza ids con `/ \ : ..`.
- **`save_version`**: el nombre «..» ya no sale de `versions/` (antes `re.sub` permitía `..`).
- **`write_json` atómico** (temporal + `os.replace`): el sondeo nunca lee medio `run.json`. Lo usan `run_batch`, `save_version` y `_mark_orphan`.
- **`prune_tmp`** ordena por la hora del nombre (`_AAAAMMDD-HHMMSS`). Abrir una corrida (miniatura, `.visor/`) cambiaba el mtime de
  la carpeta y la salvaba de la poda.
- **`stl_binary`**: convierte una vez, con un candado por archivo; las peticiones simultáneas esperan, no repiten. Guarda en
  `<corrida>/.visor/`, que se copia con la versión y se borra con la poda. Si el STL ya es binario o no tiene facetas, se sirve tal cual.
- **`safe_name` único** para corrida, candado, versión y proyecto (antes había tres `re.sub` distintos). Se arregló un `if/else`
  partido en `suggest_base` (había quedado `else         min(...)` en una línea).

### Selftest (`_selftest_bordes`, `_selftest_ui`)
- Proyecto **sin voluta y sin CFDSetup** en una carpeta con espacios y acentos («sin voluta ñandú»):
  - `cfd_ext_outlet=None`, sin `volute_d_out`, dos componentes.
  - La corrida «café con leche» → `caf_con_leche`, en un **WORKDIR con «&»**: el XML escapado funciona.
  - `timing` completo en el resultado y en el `run.json`.
  - `ext_outlet` da error claro.
- **Excepción dentro de la corrida** (sin CFturbo.exe): `error` con `FileNotFoundError` en `run.json` y el candado liberado.
- **`run.json` corrupto**: la galería lo ignora, `find_run` lo encuentra y se puede borrar. Ids inválidos (`""`, `..`, `a/b`, `a\b`, `c:x`) dan error.
- **Versión borrada** mientras la temporal la anuncia: `find_run` no la encuentra y «★ como» desaparece. Nombre «ver sión/../ñ» → `ver_si_n_`.
- **Candado huérfano**: JSON corrupto o demasiado viejo se descarta y se borra.
- **Procesos**: `_cfturbo` con tiempo límite devuelve −1 en < 5 s; `kill_children` mata un proceso vivo.
- **STL ASCII → binario**: tamaños, coordenadas y CRLF; binario o vacío se sirve tal cual; la caché en disco no reconvierte.
- **0 y 30 corridas** en una galería aislada:
  - Orden y claves exactas de la fila ligera.
  - La caché no relee si nada cambió y sí relee tras un cambio.
  - La poda por nombre deja 7 aunque la más vieja tenga miniatura nueva.
- **HTTP real** (uvicorn en un hilo, puerto libre; se salta si no hay fastapi):
  - ETag → 304.
  - 404/400/422 con `detail` de texto; `exports` y `edits` inválidos → 422.
  - Chat vacío → 422; `run.json` roto → 500 «ilegible».
  - `/stl/` con `Cache-Control`.

## Verificación
- `python mcp_server.py --selftest` → **selftest OK** en 5,0 s. MCP stdio: `tools/list` → 12 tools `cft_*`.
- Servidor propio en **8766**, navegador a **1400×900** y **800×900**:
  - **Corrida real desde la UI** `opt_ui_d2_2125`: d2 «212,5» con coma, `realized d2_mm 0.2125`, 30,1 s.
    El botón, el header y la tarjeta mostraron «Corriendo… N s»; al terminar, toast «terminó con 1 aviso» y visor con 20 superficies.
  - Antes, por API: `opt_base` (23,6 s) y `opt_d2_215` con Reporte (22,7 s).
  - **Curvas**: 3 SVG; el puntero lee «Q 214 · H 73,8».
  - **Comparar**: Ctrl+clic en `opt_base` → fila d2 «212,5 / 206,3 / −6,2 / −2,9 %»; H-Q con A y B (puntero «H 71,8 · H 73,8»);
    alambre B con 11 mallas; Intercambiar; Esc quita B y el alambre.
  - **Guardar** `opt_v1` (Enter): toast, la temporal queda «★ como opt_v1».
  - **Borrar** `opt_v1` estando seleccionada (🗑 → «¿Borrar? Sí»): pasa a la vecina y la temporal deja de anunciarla.
    `opt_d2_215` se borró con Supr → Sí; su geometría salió de la caché.
  - **Chat corto** «Solo lee…»: `cft_runs` y una línea de respuesta, 3 turnos, 15 s.
  - **800×900**: 1 807 px de alto (≤ 1 850), sin scroll horizontal; curvas y comparar correctos.
  - **Consola**: entre dos marcas, recargando, abriendo las 5 pestañas, comparando, con alambre y cambiando de corrida, **0 errores JS**.
    Solo hubo 404 de STL de `dev3_b2_26`: alguien (otra sesión) borró a las 09:04 parte de sus archivos y las corridas o versiones
    anteriores del `%TEMP%` compartido; no fue este código.
- Servidores 8766 y 8767 (copia de main para medir) apagados. `recipes/bitacora.md` dejada como en main (las corridas `opt_*` no se commitean).

## Qué no toqué y por qué
- **Diseño y CSS**: nada visual (`style.css` intacto).
- **`app.js` no bajó de tamaño** (+1,8 KB): no encontré funciones muertas; todas las de nivel superior tienen uso y los ids del HTML
  se usan o son destino de `aria-labelledby`. El peso nuevo es la caché de STL, el ETag y el manejo de errores.
- **Tipo de máquina por nq** duplicado en `nqNew()` (JS) y `nq_calc` (Python): se deja en el cliente para el «nq nuevo» en vivo sin
  petición. Si cambian las bandas, hay que cambiar los dos (comentado).
- **Normales del STL**: el visor sigue llamando a `computeVertexNormals` como antes, para no cambiar el sombreado.
- **Conversión STL en el MCP**: las corridas del chat se convierten la primera vez que se abren (~1,3 s, una vez), no al correr,
  para no alargar `cft_run`.
- **El chat sigue en una petición SSE aparte**: no se movió al sondeo.
- **`explora/desde_cero.py`**: solo se lee; no hacía falta tocarlo.

## Riesgos
- La **fila de `/api/poll` cambió de forma**: sin `info`, `warnings`, `errors` ni `edits`, y con `d2_mm`, `nBl`, `n_warn`, `error`
  y `autoupdate`. `app.js` está adaptado. Si alguna herramienta externa leía `/api/runs?fields=summary`, debe usar los campos nuevos.
  `cft_runs` (MCP) no cambia y además trae `timing`.
- **`.visor/`** añade unos 11 MB por corrida vista. Se poda con la corrida y viaja con la versión.
- El **304** depende de que el navegador pase el 304 al fetch cuando la página pone `If-None-Match` a mano. Chrome lo hace (medido);
  si otro navegador no, ve 200 como antes.
- **Nombres**: `safe_name` también recorta «_» al principio y al final («_x_» → «x»), de modo que corrida, candado y versión coinciden.
- **Selftest**: si hay fastapi y uvicorn levanta un servidor en un puerto libre de 127.0.0.1; sube a ~5–7 s, por debajo de 10.
