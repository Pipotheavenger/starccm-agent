# Documentador · documentación final

Autor: Documentador (Opus) · 2026-10-23 · sin commits. Base: main en `63120b5` (ronda 3 + optimización).
Leídos `dev_3.md`, `opt_final.md`, `recipes/exploracion-desde-cero.md`; cada afirmación se comprobó en
`mcp_server.py`, `ui/server.py`, `ui/app.js`, `ui/index.html`, `explora/desde_cero.py`.
`python mcp_server.py --selftest` → **OK** antes y después de tocar los docstrings.

## Qué cambié

| archivo | cambio |
|---|---|
| `CLAUDE.md` | tabla de 12 tools con firmas reales (`cft_delete(run_id)`, `cft_new(Q_m3h, H_m, n_rpm, name, base=None, run=True)`); `cft_info` con β/s/`beta_auto1/2`/`cfd_ext_outlet`; edits especiales `beta1_deg`, `beta2_deg`, `beta_auto`, `s_mm` y la clave `MeanSurface[Mean surface]/Coupled`; exports (PerformanceData siempre, Report); sección `run.json` (`curves`, `report`/`report_file`, `timing`, versiones; `thumb` es del listado, no de run.json); `.visor/`, poda por nombre, `safe_name`, errores dentro de la corrida; UI (＋ Nueva, β en la tabla, borrar, Curvas, Reporte, ↻ Miniatura, Superponer B, Lista, filtros Avisos/Error, popover `?`, backoff 4-8-16-30); endpoints nuevos; chat (disallowedTools completos, cierre al cortar SSE); Flujo con paso «bomba nueva por semejanza» (bases, ×1,5, huecos); Reglas (β fijo apaga automático, ext_outlet cuándo no y casilla deshabilitada, `cft_new` solo crea en projects/, `cft_delete` no en lecturas); 13 lecciones nuevas de dev_3, opt_final y la exploración |
| `PRIMER-PROMPT.md` | guía de una página: arrancar, tres formas de trabajar, bomba nueva, ángulos y espesor, curvas y reporte, guardar/borrar/comparar, atajos actuales, fallos, rutas |
| `ui/README.md` | archivos, flujo de datos (ETag/304, caché de run.json, `.visor/`, render bajo demanda), endpoints completos con códigos y validación, eventos SSE (incluye `raw`), log, cómo añadir parámetro (incl. `SPECIAL`, `auto`), pestaña (ResizeObserver), tool MCP, cómo probar |
| `recipes/README.md` | bitácora con «VERSIÓN BORRADA», receta `exploracion-desde-cero.md` en la tabla, coupling también al fijar β2 |
| `recipes/exploracion-desde-cero.md` | límite de `_STL_RX` marcado como arreglado; recomendación 1 marcada como hecha (`cft_new` usa `preparar` + `run_batch`, no `nueva_bomba`) |
| `projects/README.md` | origen GUI o `cft_new`; los existentes no se modifican, `cft_new` solo crea |
| `explora/README.md` (nuevo) | qué es, cómo lo usa el MCP, límites, uso y selftest (CFturbo real, ~95 s) |
| `AGENTES.md` | sección «Historial» (base 5/7, r1 7/8, r2 9/9, r3, optimización, docs final, eval final pendiente) y «Cómo relanzar una ronda» |
| `mcp_server.py` (docstring) | exports PerformanceData/Report, lista de 12 tools, edits especiales, `cft_new`→`explora/desde_cero.py`, `.cft-pp` y `.visor/`, poda por nombre, `cft_delete`, bitácora al borrar, `curves`/`report`/`timing`, tiempo del selftest |
| `ui/server.py` (docstring) | `POST /api/new` no corre CFturbo; tipos de evento SSE |

No toqué `app.js`, `index.html`, `style.css` ni lógica.

## Inconsistencias código / doc (para el evaluador)

1. **Backoff de reconexión**: el CLAUDE.md anterior decía 3 → 6 → 12 → 30 s; el código (`BACKOFF = [4, 8, 16, 30]`) y `ui/README.md` dicen 4 → 8 → 16 → 30. Corregido en CLAUDE.md.
2. **«Quitar extensión CFD de salida, marcada por defecto»** (doc vieja): ahora la casilla se llama «Sin extensión CFD», se marca solo si el origen tiene la extensión activa y se deshabilita si no hay `CFDSetup_RotSym` (`applyExtDefault`). Corregido.
3. **Filtro «Con avisos»** (doc vieja): ahora son «Avisos» y además «Error»; hay vista «Lista» compacta, «↻ Miniatura» y «Superponer B» que no estaban documentados. Corregido.
4. **`thumb` no es campo de `run.json`**: lo añade `list_runs` (mtime de `thumb.png`, 0 si no hay). El encargo lo listaba como campo de run.json; documentado como del listado.
5. **No existe «GET report»**: el reporte se sirve por `GET /files/{id}/<name>.html` en línea (`text/html`); no hay endpoint propio.
6. **Tiempo del selftest de `explora/desde_cero.py`**: su docstring dice «~40-70 s»; la receta dice ~95 s (47 s la primera corrida). No lo corrí (usa CFturbo real y el evaluador corre en paralelo). En `explora/README.md` puse ~95 s, citando la receta.
7. **`cft_run` docstring** lista `exports` ⊂ `["StarCCM","OpenFOAM","General","Report"]`, pero `EXPORTS_KNOWN` y `/api/run` aceptan también `PerformanceData` (redundante: se añade siempre). Sin efecto práctico.
8. **`new_project` escribe en `projects/`** mientras AGENTES.md dice a los agentes «No tocar `projects/`» y el CLAUDE.md viejo «Nunca editar el `.cft` de `projects/`». No es contradicción (solo crea carpetas nuevas, 409 si existen), pero el evaluador debe borrar a mano los `projects/<prueba>` que cree (no hay borrado de proyectos ni en MCP ni en UI). Además una bomba creada así pasa a ser **candidata de base** para la siguiente `cft_new` (`candidatos()` lee `projects/*/*.cft`), aunque sea un escalado.
9. **Bases de `cft_new` dependen de la ruta fija** `C:\Program Files\CFturbo 2026.1.1\Examples\…` (`explora/desde_cero.py`); si se actualiza CFturbo, `pump_bases()` solo verá `projects/`. No documentado antes; añadido a `explora/README.md`.
10. **`beta_auto`**: sin control en la UI (lo dice dev_3); documentado. Fijar un solo span de β en la tabla manda también el otro con el valor del origen, así que ese span también queda «fijo» (AutoUpdate=False aplica al ángulo entero).
11. **`s_mm` tiene dos lecturas**: `dims.s_mm` (tabla, `blade_info`) es un solo número, la media de todos los valores de `s1` y `s2`; `realized["s_mm"]` (`_get_thickness`) es `[cubo, corona]` de `s1` solo. Como el setter escribe lo mismo en `s1` y `s2` no da falsos «corrigió», pero un proyecto base con LE ≠ TE muestra en la tabla un espesor que no es ninguno de los dos. Menor.
12. **`/api/runs` sin `fields`** no trae `curves` (por diseño, `_LIST_KEYS`), y `cft_runs` tampoco: para curvas hay que leer `GET /api/runs/{id}` o el `run.json`. Documentado.
13. `recipes/bitacora.md` aparece modificado en el árbol de trabajo: no fui yo (corridas del evaluador en paralelo). `agents/out/eval_final/` también es suyo.

## Qué no hice
- No corrí CFturbo real ni el selftest de `explora/` (licencia y candado compartido con el evaluador).
- No verifiqué en navegador; la parte de UI sale de leer `app.js`/`index.html`.
