# Programador · ronda 3

Autor: Programador · 2026-10-23 · Rama `worktree-agent-af193d822c2ef6a52`, un commit, sin push. Base: main con
rondas 1 y 2, `ronda3_alcance.md`, `eval_2.md` (D2-1…D2-8), `recipes/exploracion-desde-cero.md`, `explora/desde_cero.py`.

## Hecho

### Alcance ronda 3
| # | Qué | Dónde |
|---|---|---|
| 8 | **Limpieza de letreros**: fuera la tagline del topbar, la nota de AutoUpdate, la leyenda de la galería («quedan las 8…» → `title` de `#gcount` con la ruta de WORKDIR), la ruta de Archivos (→ `title` de «Abrir carpeta»), textos largos del visor vacío, de la galería vacía, de Comparar y del chat (una línea + `title`); opciones en una palabra (AutoUpdate · Sin extensión CFD · Exportar: STEP · STL · Reporte) con la explicación en `title`; «▶ Ejecutar» (antes «… en CFturbo»); placeholder del chat «Mensaje para Claude»; cabecera del proyecto solo «nq 37,4» (tipo en `title`) | `index.html`, `app.js` |
| 1 | **Ángulos β y espesor**: `project_info().dims` trae `beta1_hub_deg`, `beta1_shroud_deg`, `beta2_hub_deg`, `beta2_shroud_deg`, `s_mm`, `beta_auto1/2` (de `BladePropsML[Main blade]/Beta1|Beta2|s1|s2`, índices 0 y Count-1). `edits` especiales `beta1_deg`/`beta2_deg` (número o `[cubo, corona]`, grados → rad, índices intermedios interpolados, **AutoUpdate1/2=False**), `beta_auto=True`, `s_mm` (LE y TE). `realized` se lee del `_out.cft`; `_differs` compara listas con 0,01°. Tabla: filas β1/β2 cubo/corona y s (valores automáticos en cursiva con `title`); las dos filas de un β se envían juntas, el span vacío toma el valor del origen. Comparar las incluye solas | `mcp_server.py` (`blade_info`, `SPECIAL`), `app.js` (`PARAMS`, `edits()`) |
| 3 | **Borrar**: `delete_run(id)` (temporal o versión; 409/`CFturboBusy` si está corriendo; línea «VERSIÓN BORRADA» en la bitácora), `DELETE /api/runs/{id}`, tool `cft_delete`. Galería: 🗑 por tarjeta (tenue en la activa, visible al pasar/enfocar), confirmación en la tarjeta «¿Borrar? Sí / No» (6 s, Esc o No cancela), tecla **Supr**; si era la activa pasa a la vecina; si era B, se quita B | `mcp_server.py`, `server.py`, `app.js` |
| 7 | **Curvas**: `PerformanceData` se exporta siempre; `parse_perf` lee `<Curve Name Desc>` (2026.1.1 da «Δpt - ṁ» en bar vs kg/s y «η - ṁ» en %) → `run.json["curves"]` = `Q_m3h`, `H_m`, `eta_pct`, `P_kW` (= ρgQH/η), `design`, `names` (todas las curvas listadas). La unidad de Δpt se elige reproduciendo H de diseño. Pestaña **Curvas**: SVG propio H-Q (punto de diseño), η-Q, P-Q a tamaño real (texto 12 px, se repinta al cambiar el dock), puntero con lectura de A y B; A continua, B discontinua; en Comparar, H-Q de A y B junto a la tabla (container query). No hay curva NPSH en el `.cft-pp` de 2026.1.1 (si aparece, `NPSH_m`) | `mcp_server.py`, `app.js`, `style.css` |
| 2 | **Reporte**: casilla «Reporte» (apagada por defecto) añade el export `Report` → `<name>.html`; `parse_report` recorre la tabla (profundidad por celdas `&nbsp;`) → `run.json["report"]`: βB1/βB2 [cubo, corona], Δφ, área de garganta del impulsor (la de «Blade edges»), w2/w1 [cubo, corona], ηh/ηv/ηm/η etapa, NPSHR por correlación (rangos) y NPSHA, cu2/cm2/u2, P eje y par, área de garganta de la voluta. Hitos: bloque «Diseño» con esos valores y enlace «Reporte ↗» (pestaña nueva, servido en línea como text/html); Archivos: grupo «Reporte»; Comparar: filas con Δ (cubo/corona separados, NPSHR por su máximo) | igual |
| 4 | **Bomba nueva**: `new_project(Q,H,n,name,base)` usa `explora/desde_cero.preparar` (cargado con importlib, `ROOT` = carpeta de `PROJECTS`) y crea `projects/<name>/<name>.cft` (409 si existe); `suggest_base` da base, nq, k, ratio y aviso > ×1,5 (bases cacheadas por mtime); tool `cft_new(..., run=True)`; `GET /api/new/suggest`, `POST /api/new`. UI: «＋ Nueva» junto al selector → diálogo (Q, H, n, nombre, base sugerida con su nq, línea nq/tipo/k y ⚠ si salto > ×1,5) → «Crear y correr»: crea, la elige en el selector y lanza `<name>_1` | `mcp_server.py`, `server.py`, `index.html`, `app.js` |
| 5 | **`_STL_RX`**: acepta `Flowdomain(virtual)` y captions sin corchetes (`Impeller`, `RadialImpeller`, `Stator_1`); 6 casos en el selftest | `mcp_server.py` |
| 6 | Tema claro por defecto: ya venía de la ronda 2 | — |

### eval_2 (D2-1…D2-8)
- **D2-1** `describeEdits` con coma decimal (decimales de la fila; listas con «;»).
- **D2-2** < 1100: runbar en una línea (`.long` y texto del chip fuera), pie de 66 px (resumen en una línea, sin etiqueta «Nombre», `#runmsg` vacío oculto), visor 42vh, filas de tabla 25 px, dock 300 px → **1825 px** a 800×900 con corrida (antes 1909, y eso que ahora hay 5 filas más).
- **D2-3** cabecera «Proyecto base · nq 37,4» en una línea (17 px); `#pinfo` con elipsis.
- **D2-4** chip seguir/fijada con icono (⟳ / 📌) y, entre 1100 y 1279, solo icono; la duración cede antes que la fecha: a 1100 con «Fijada» se ve «23 oct 08:02» (79 px, sin recorte).
- **D2-5** miniatura automática siempre sobre fondo neutro `#e9edf2` (probado con tema oscuro: esquina 233,233,…); las viejas oscuras se rehacen solas al abrir la corrida (`thumbIsDark`, esquina < 110).
- **D2-6** `.card-run.dim` sin opacidad (nombre en `--mut`); `::placeholder{color:var(--mut)}`.
- **D2-7** `api_run`: cualquier excepción al tomar el candado libera `RUN_LOCK` (500) y el hilo se lanza en `try`.
- **D2-8** dock por defecto `clamp(280px, 32vh, 420px)` (el alto arrastrado y guardado manda).

## Fuera (y por qué)
- No hay control en la UI para `beta_auto=True` (volver a ángulos automáticos): está en el MCP/chat; en la tabla basta con no escribir β.
- Fijar β2 deja el aviso «Coupling partially deactivated» (como al cambiar nBl). No se corrige solo desde Ejecutar; la receta es `MeanSurface[Mean surface]/Coupled=False` (el chat lo hace).
- `s_mm` escribe `s1/s2` (LE/TE); el perfil «Blade profiles» de algunos ejemplos tiene su propia distribución (`BezierNProf`) que no se toca.
- Las corridas anteriores a esta ronda no tienen curvas ni β en `info` («Sin curvas en esta corrida», «–»).
- La bitácora del worktree se dejó como en main (las líneas de prueba no se commitean); `projects/dev3_nueva` (prueba) borrado.

## Verificación
- `python mcp_server.py --selftest` → **selftest OK** (nuevo: β/s en info, edits β (número y lista), `beta_auto`, valor inválido → error, `_differs`, curvas y reporte con el CFturbo falso, `curves` fuera de `list_runs`, `_STL_RX` 6 casos, borrar temporal/versión/en marcha/inexistente, `suggest_base` + aviso, `new_project` (d2 = 1,1·206,3, espesor escalado, 409 al repetir, corre)).
- MCP stdio: `tools/list` → 12 tools (`cft_delete`, `cft_new` nuevas).
- Servidor propio 8766 (tab propia del navegador; ojo: la pestaña compartida del pane la usaba también el evaluador en 8765). 1400×900, 1100×760 y 800×900; consola sin errores.
- **Corrida real `dev3_b2_26`** desde la UI (β2 = 26 en cubo y corona, Reporte marcado): 22,6 s, 1 aviso (Coupling). `_out.cft`: `AutoUpdate2=False`, `Beta2` índices 0 y 4 = 0.4538 rad (26,0°), `AutoUpdate1=True`; `realized` = `[26.0, 26.0]`, sin correcciones; reporte βB2 [26, 26], cu2 19,3 → 18,9 m/s, w2/w1 [0,861; 0,744]. STL frente a una corrida igual sin β (`dev3_base_tmp`): `BladePS` 77 688 → 78 552 vértices, `BladeTE` 3 222 → 2 556, `Hub` idéntico (0,00 mm), `Spiral` rehecha.
- Curvas visibles (H-Q con punto de diseño, η-Q, P-Q, lectura con el puntero); reporte abierto (`text/html`, 725 KB, pestaña nueva); Hitos con el bloque «Diseño».
- Borrado desde la galería: `dev3_base_tmp` (Supr → «¿Borrar? Sí») y la versión `dev3_vprueba` (🗑 → Sí): toasts, la activa pasa a la vecina, la temporal deja de decir «★ como dev3_vprueba».
- **Bomba nueva** Q 150 m³/h, H 40 m, n 2900 rpm desde el diálogo: nq 37,2, base «CP nq37 (end-suction)» (×1,00, k 0,938) → `projects/dev3_nueva` en el selector, `dev3_nueva_1` corrida en 39,8 s, OK sin avisos, d2 193,6 mm.
- Comparar `dev3_nueva_1` (A) y `dev3_b2_26` (B): tabla con β, reporte y Δ; H-Q superpuesta; pestaña Curvas con A y B.
- Chat: «Solo lee: ¿qué βB2 … dev3_b2_26?» → sesión caducada reintentada, `cft_runs`, respuesta con tabla y el aviso de acoplamiento ofrecido sin correr nada (3 turnos, 28 s).
- Servidor 8766 apagado.

## Rama
`worktree-agent-af193d822c2ef6a52`, commit «ronda 3 del programador…». Archivos: `mcp_server.py`, `ui/server.py`,
`ui/app.js`, `ui/index.html`, `ui/style.css`, `agents/out/dev_3.md`. `bootstrap.sh` (raíz) ya venía modificado y no se
incluyó; `.mcp.json` local del worktree (ignorado) apunta al `mcp_server.py` del worktree. Docs (CLAUDE.md, ui/README.md,
PRIMER-PROMPT.md) quedan para el Documentador: tools `cft_delete`/`cft_new`, edits `beta1_deg`/`beta2_deg`/`beta_auto`/`s_mm`,
`run.json["curves"|"report"|"report_file"]`, endpoints `DELETE /api/runs/{id}`, `GET /api/new/suggest`, `POST /api/new`.
