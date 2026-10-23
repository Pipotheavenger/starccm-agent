# Evaluación E2E · FINAL (main = ronda 3 + pasada de optimización)

Fecha: 2026-10-23 09:24–09:42 · Evaluador: Director E2E (Fable) · Servidor: `http://localhost:8765` (preview del
orquestador, PID 13624 arrancado a las 09:24:12, **después** del merge `63120b5` de las 09:23:57; `app.js` y `style.css`
servidos = md5 del checkout). Servidores propios aislados en **8767** (14 temporales + 6 versiones falsas) y **8768**
(0 corridas) con `CFTURBO_WORKDIR`/`CFTURBO_VERSIONS` en el scratchpad; apagados al terminar. No se tocó código ni se
hizo commit (`git status`: solo `recipes/bitacora.md` con las líneas de mis corridas, `agents/out/eval_final/` y el
`bootstrap.sh` que ya venía modificado).

Cómo se probó: panel Browser de Claude Code (viewport emulado 1400×900, 1150×760, 1920×1080 y 800×900, `localStorage`
vaciado; medidas con `getBoundingClientRect`, `elementFromPoint`, `getComputedStyle`, Performance API con
`responseStatus`/`transferSize`, `renderer.info.memory`); Chrome headless con perfil limpio (`agents/out/eval_final/01_*`);
`curl` para la API; `--selftest`; cliente JSON-RPC mínimo por stdio para el MCP. **Cada cifra de los informes se volvió a medir.**

Corridas reales creadas: `evalF_b2_26_22` (UI, β2 = [26; 22]°, Reporte marcado, 23,2 s), `evalF_api_tmp` (API, nBl 7,
27,7 s), `evalF_nueva_1` (desde «＋ Nueva», 53,2 s, OK), `evalF_stop` (chat, interrumpida con Detener); versión
`evalF_v1`; proyecto `projects/evalF_nueva`. **Todo borrado al final** (DELETE 200 ×3 + `rm projects/evalF_nueva`);
queda `opt_ui_d2_2125` (ajena) y `_report_test`.

Contexto que condicionó la sesión: el `%TEMP%\cfturbo-agent` y el servidor 8765 los usaba a la vez **otra sesión**
(chat con `claude.exe` lanzado por el 8765 a las 09:31:54, corridas `sin_hoyo_hub`/`hoyo_dH5` a las 09:33–09:34, y
borrados de `dev3_b2_26`, `opt_base`, `zz`, `sin_hoyo_hub`, `hoyo_dH5` y de todas las `versions/` previas). Lo anoto
porque explica los 404 de la consola (ver D-F3) y porque el «Claude trabajando» del topbar era real pero ajeno.

## 1. Tabla de verificación

### 1.1 Rúbrica de funcionalidad

| Función | Estado | Evidencia |
|---|---|---|
| Selector de proyecto e info | OK | «Pump · Stator + Impeller + Volute · Water (20°C)», «nq 37,4» (tipo en `title`); con `evalF_nueva` → «nq 34,5» y la columna Base cambia (d2 216,4, dS 128,7) |
| Tabla base/corrida/nuevo con nq en vivo | OK | 16 filas: Q H n d2 b2 dS dH ψ z dV **β1 cubo/corona, β2 cubo/corona, s** y nq; valores automáticos en cursiva (`td.auto` con `title`); al escribir β2 26/22 → filas `.edited`, «2 cambios · desde la base · sin extensión CFD» |
| **Ángulos β** | OK | `project_info.dims` trae `beta1/2_hub/shroud_deg`, `s_mm`, `beta_auto1/2`. Corrida real `evalF_b2_26_22`: `requested_si beta2_deg=[26.0, 22.0]`, `realized` igual, `corrected {}`. **`_out.cft`: `AutoUpdate2=False`, `AutoUpdate1=True`, `Beta2` índice 0 = 0,453785 rad (26,00°), índice 4 = 0,383972 rad (22,00°)**; Beta1 intacto (20,67/17,24°). Columna Corrida: β2 cubo «26,0» y corona «22,0» en ámbar (`changed`) frente a 32,4/23,0 de la base. Comparar: filas β1/β2 cubo/corona con Δ y Δ % (−2,4 / −10,9 % en β2 corona vs `opt_ui`) |
| Ejecutar en CFturbo (corrida real) | OK | Botón «Corriendo evalF_b2_26_22… 2 s» deshabilitado, header «CFturbo trabajando · … · 2 s», `runmsg` ««evalF_b2_26_22»: βB2 [cubo, corona] ° = [26,0; 22,0] (sin extensión CFD)» (coma decimal, D2-1 cerrado), inputs y nombre vaciados; al terminar, toast y tarjeta «Con avisos ⚠1»; `run.json["timing"]` = preparar 0,01 · cfturbo 23,15 · leer 0,05 · cerrar 0,0 · total 23,21 |
| Partir de corrida seleccionada | OK | `segrun` habilitado con el nombre de la corrida; deshabilitado con `title` para corridas en error («Una corrida con error no tiene .cft de salida») |
| AutoUpdate y ext_outlet | OK | Marcar AutoUpdate → pie «… · **AutoUpdate activo**» (ámbar); «Sin extensión CFD» marcada por defecto desde la base (`cfd_ext_outlet: True`) y `title` «El origen ya no tiene la extensión activa» al partir de una corrida que la quitó; `ext_outlet=False` llegó al servidor (`realized ext_outlet False`) |
| Hitos, avisos, correcciones | OK | 6 hitos con hora (09:29:19 … 09:29:42), aviso «Coupling partially deactivated» deduplicado, badge «1», `#vsummary` «1 aviso → ver» |
| **Reporte** | OK | Casilla «Reporte» (apagada por defecto, `title` con la explicación) → export `Report` → `evalF_b2_26_22.html` (725 648 B, `text/html; charset=utf-8`, en línea). `run.json["report"]` con 17 claves. Hitos: bloque «DISEÑO · Reporte ↗» con βB1 20,7/17,2°, βB2 **26,0/22,0°**, Δφ 90,0°, A garganta 560 mm², w2/w1 0,861/0,810, ηh 92,1 %, ηv 96,6 %, ηm 99,0 %, η etapa 86,6 %, NPSHR 4,8–10,1 m (Gülich), cu2 18,1, cm2 4,5 m/s, P eje 49,9 kW, A lengua 5085 mm² (`05_hitos_reporte_evalF.jpg`). Archivos: grupo «Reporte» con enlace `target=_blank` (lo demás `download`). Comparar: filas del reporte con «–» en la corrida sin reporte |
| **Curvas** | OK | `PerformanceData` siempre: `curves` con 100 puntos Q/H/η/P y `design`. Pestaña: 3 SVG 238×199 (3 columnas en dock de 780 px) «Altura/Rendimiento/Potencia frente a caudal», cada una con `path.ln.a` y punto de diseño (`circle.dp`); cabecera «Diseño: Q 227,0 m³/h · H 70,0 m · η 86,3 % · P 48,0 kW»; puntero → «Q 214 · H 69,9»; con B: `ln a + ln b` en las 3 y lectura doble «Q 240 · H 64,2 · H 67,8». En Comparar: H-Q de A y B junto a la tabla (`grid 428 px + 300 px`, container query) (`04_curvas_evalF.jpg`) |
| Archivos: descarga y Abrir carpeta | OK | `/files/...stp` → `content-disposition: attachment; filename="…"`; STL ASCII 6 753 258 B por `/files/` vs **1 298 784 B** por `/stl/` (`model/stl`, `Cache-Control: private, max-age=3600`); «Abrir carpeta» habilitado con `title` = ruta (no lo pulsé para no abrir ventanas en el PC; verificado en ronda 2) |
| Guardar versión y galería | OK | Clic → input en línea con el nombre; Enter con «evalF_v1» → toast «Guardada en versions/evalF_v1», activa = `evalF_v1` (★ Guardada, ribbon, chip «📌 Fijada»), temporal `dim` «★ como evalF_v1», «Listo · 2 corridas · 1 versión». Disco: `versions/evalF_v1/run.json` `saved=true`, `saved_from=evalF_b2_26_22_…`, evento «Guardada como versión», **`.visor/` copiada con 20 STL binarios**; bitácora «VERSIÓN GUARDADA versions/evalF_v1» |
| **Borrar (🗑 y Supr)** | OK | Versión activa `evalF_v1` con 🗑 (opacidad 0,55 en la activa, `title` «Borrar la versión (Supr)») → «¿Borrar versión? Sí / No» (`role=alertdialog`, foco en «No») → Sí → `DELETE /api/runs/evalF_v1` **200**, toast «Versión borrada: evalF_v1», **la activa pasa a la vecina** `evalF_b2_26_22`, la temporal deja de decir «★ como», bitácora «VERSIÓN BORRADA versions/evalF_v1». Temporal `evalF_api_tmp` con **Supr**: «¿Borrar? Sí / No», `Esc` cancela y devuelve el foco a la tarjeta; Supr → Sí → DELETE 200, toast «Corrida borrada», foco a la tarjeta `tabindex=0`, su geometría sale de `geoCache`. `DELETE` inexistente → 404 con `detail` |
| **«＋ Nueva» (Q 180, H 50, n 2900)** | OK | Diálogo prellenado con el punto de diseño del proyecto (227/70/3600), foco en Q; al escribir 180/50/2900: «nq 34,5 · radial normal · base nq 37,4 (×0,92) · k 1,049», placeholder `bomba_Q180_H50_n2900`, base sugerida «CP nq37 (end-suction) · nq 37,4 (sugerida)» entre 12 opciones. «Crear y correr» → `projects/evalF_nueva/evalF_nueva.cft` en 201 ms, toast «Creada projects/evalF_nueva desde CP nq37 (end-suction) (k 1,049)», **aparece y queda elegida en el selector** (nq 34,5, Base d2 216,4 = 206,3·1,049), lanza `evalF_nueva_1`: **OK, rc 0, 0 avisos, 53,2 s**, 25 STL, d2 216,44 / b2 21,21 / dS 128,73 mm. Proyecto y corrida borrados después |
| Visor | OK | 20 superficies por componente, tapas, Encuadrar, `2` → axial (dirección (0,0,1), `aria-pressed` solo en Axial), `` ` `` pliega (visor 528 → 780 px) y despliega; B en alambre: 11 mallas `wireframe`, opacidad 0,35; `Esc` quita B y `groupB` queda en 0. Render bajo demanda: **0 frames en 3 s de reposo** |
| Chat real (solo lectura) | OK | «Solo lee: resume la última corrida en 3 líneas» → solo `cft_runs{limit:1}`, respuesta con tabla (1 `<table>`, sin `**`/`\_` crudos), menciona los 2 avisos y **ofrece** corregir sin correr nada; «listo · 3 turnos · 13 s»; sesión `af360c89`, modelo `claude-sonnet-4-6[1m]` |
| Detener chat | OK | «Corre una variante … nombre evalF_stop» → tool `cft_run` en 1 s, candado y «CFturbo trabajando · evalF_stop · 1 s» a los 8 s; Detener 4 s después → **0,4 s** hasta «Detenido por el usuario.» / `chatstate` «detenido», Enviar habilitado; 2 s después **sin `CFturbo.exe`, sin `running.lock`, `running:false`**; a los 16 s la corrida pasa a «error · Corrida interrumpida: el proceso que la lanzó terminó» con hito «Corrida interrumpida» (tarjeta roja «✕ Sin geometría») |
| Nueva conversación | OK (código + rondas 1–2) | Doble clic armado («¿Seguro? Pulsa otra vez…», 4 s); no repetido |
| Estados de error | OK | Candado manual con PID vivo (`powershell Start-Sleep`): `/api/status running:true, running_name evalF_candado_externo, running_since`; `POST /api/run` → **409** «CFturbo trabajando (evalF_candado_externo)»; UI: header «CFturbo trabajando · evalF_candado_externo · 82 s», botón «Corriendo evalF_candado_externo… 82 s» deshabilitado con `title` «Una corrida de CFturbo a la vez (una licencia)»; visto igual en 8767/8768 (candado global). Durante una corrida propia, segundo `POST /api/run` → 409 «ya hay una corrida de CFturbo en marcha». 404 proyecto, 400 traversal (`..%5C`), 400 `fields=x`, 400 `Q=inf`, 422 `exports` desconocidos y chat vacío con `detail` de texto. Sin login: solo código (`loginCard`), la CLI está logueada |
| Selftest | OK | `selftest OK` en **4,99 s** |
| MCP por stdio | OK | `initialize` 2024-11-05 → **12 tools**: `cft_projects cft_info cft_params cft_run cft_runs cft_save cft_delete cft_new cft_log cft_nq cft_recipe_search cft_recipe_save`; `cft_nq(180,50,2900)` → nq 34,5; `cft_runs` responde con `timing`; 1,1 s |
| Consola del navegador | **parcial** | 0 errores JS en 18 min (5 anchos, corridas, borrar, versión, comparar, curvas, chat, Detener, Nueva). **48 × 404** de `/stl/dev3_b2_26_…`: la otra sesión borró esa corrida mientras mi visor la cargaba (D-F3). En 8767/8768: 0 mensajes |
| 0 corridas (8768) | OK | «Listo · 0 corridas · 0 versiones», chips a 0, galería «Sin corridas» (`title` con la pista), visor «Sin geometría», «Sin corrida», Guardar/Corrida/Abrir carpeta/Miniatura deshabilitados con `title`, placeholder `primera-bomba_1`, Curvas «–», Comparar con la pista |
| 20 corridas (8767) | OK | «(20) · 6 ★», chips 20/6/14/15/1, galería 2003/608 px con scroll propio, página sin scroll (1400×900), **0 de 34 textos tapados**, 1 solo `tabindex=0`, 3 tarjetas `dim` «★ como fake_vNN», tarjeta de error «✕ Sin geometría» (`03_20_corridas_8767.jpg`) |
| `.visor/` con Guardar versión y poda | OK | `versions/evalF_v1/.visor` (20 archivos) copiada con `copytree`; en el WORKDIR aislado, `prune_tmp(keep=8)` con `.visor/` dentro de 4 temporales borró las 6 más viejas sin error y ninguna `.visor` quedó huérfana; `delete_run` de una versión con `.visor` → carpeta entera fuera |

### 1.2 Letreros (ronda 3, punto 8)

Barrido de todos los elementos con texto propio ≥ 25 caracteres fuera de `#chat`, `#tab-events`, `#help` y el diálogo,
comparando su alto con 1,6 × `line-height`:

| Ancho | Bloques de más de una línea |
|---|---|
| 1150×760 | **1**: `#runsum` «sin cambios (solo exporta) · desde la base · sin extensión CFD» (34 px, 2 líneas) |
| 1400×900 | **1**: el mismo `#runsum` (34 px) |
| 1920×1080 | **1**: `#runmsg` de error «evalF_stop falló: Corrida interrumpida: el proceso que la lanzó terminó» (34 px, 8 s) |
| 800×900 | 0 |

Lo demás cumple: topbar sin tagline, galería «Sin corridas», Comparar «Ctrl+clic o ⇄ en una tarjeta para elegir B», chat
vacío de una línea, opciones de una palabra con `title`, «▶ Ejecutar», placeholder «Mensaje para Claude», «Proyecto base · nq».

### 1.3 Cifras medidas frente a `opt_final.md`

| Qué | Afirmado | Medido | Veredicto |
|---|---|---|---|
| Bytes de una corrida en el visor (20 STL) | 59 MB → 11,5 MB | `opt_ui`: 20 STL ASCII **60,6 MB → 11,7 MB** en `.visor/` (÷5,2); red: **11 434 080 B transferidos** en 20 peticiones `/stl/` (`transferSize`, no caché) | ✓ |
| Cambiar a otra corrida (primera vez) | 456 ms | **151 ms y 86 ms** (selectRun → geometría cargada, sin B) | ✓ mejor |
| Volver a una corrida ya vista | 58 ms | **29–40 ms** sin B; 117–167 ms con B en alambre y 4 corridas en caché | ✓ |
| Sondeo de 3 s | 1 249 B y después 304 sin cuerpo | `/api/poll` **1 212 B** con 3 corridas (`content-length`), `ETag` «df84…», `If-None-Match` → **304**, `transferSize` 300 B (solo cabeceras), `encodedBodySize` 0; 2 de 2 sondeos observados en 304 | ✓ |
| `/api/runs?fields=summary` vs completo | — | 818 B vs 18 592 B (3 corridas) | ✓ |
| Bucle del visor en reposo | 1 frame en 3 s | **0 frames** en 3 s | ✓ |
| Geometrías al cambiar de corrida | `dispose` | `renderer.info.memory.geometries` 14 → 34 tras cargar 3 corridas → **34 tras 5 cambios más**; con B y 4 corridas: **64 → 64 tras 10 cambios**; `geoCache` ≤ 4 ids y `dev3_b2_26` expulsada al pasar de GEO_KEEP | ✓ sin fuga |
| `run.json["timing"]` | sí | `evalF_b2_26_22`: 0,01 / 23,15 / 0,05 / 0,0 / 23,21 s; `evalF_nueva_1`: 0,01 / 53,22 / 0,07 / 0,0 / 53,29 | ✓ |
| STL a binario tras la corrida | 1,2–1,4 s | `.visor/` de `evalF_b2_26_22` listo (11 MB, 20 archivos) antes de que la página la abriera | ✓ |
| Selftest | 5,0–6,7 s | **4,99 s** | ✓ |
| MCP | 12 tools | 12 tools, con `cft_delete` y `cft_new` | ✓ |

### 1.4 Diseño por ancho (navegador real + headless)

| Ancho | Medidas |
|---|---|
| 1400×900 | columnas 280 / 780 / 340; visor 780×528; dock 287 px (clamp 32vh); Opciones abiertas; sin scroll de página; `runsum` a 2 líneas (D-F1) |
| 1150×760 | columnas 240 / 590 / 320; runbar 40 px; nombre entero (104/104); `runmeta` «23 oct 09:29 · 23,2 s» sin recorte (79/79, `.dur` oculta); chip solo icono ⟳; `.long` ocultos; galería 1 columna en fila; `#pinfo` con elipsis (317/215); Opciones plegadas (< 820 px); `runsum` a 2 líneas (D-F1) |
| 1920×1080 | columnas 320 / 1220 / 380; visor 1220×650; dock 345; pie pegado a Opciones (12 px) y **156 px vacíos** bajo el pie (eran 214 en ronda 2); `runsum` 1 línea |
| 800×900 | página **1807 px** (≤ 1850, D2-2 cerrado), ancho 785 (sin scroll horizontal), orden runbar · visor (378) · dock (300) · propiedades · explorador; pie fijo de 65 px con `padding-bottom` reservado (112 px); runbar 40 px en una línea; tira de tarjetas de 140 px sin `.sub`; «Lista» oculto |

Accesibilidad: **0 textos < 12 px** a 1400; contraste placeholder 6,43, gris `--mut` 6,43, `tag.warn` 5,26 (D2-6 cerrado);
popover `?` (12 atajos, foco en ✕, `Esc` devuelve el foco a `?`, `aria-expanded`); `aria-pressed` en filtros, vistas,
segmento y chip; confirmación de borrado con `role=alertdialog`; roving tabindex (1 solo `tabindex=0` con 20 tarjetas).
Capturas: `agents/out/eval_final/01_inicio_{1150,1400,1920,800}.png` (headless), `02_inicio_1400_navegador.jpg`,
`03_20_corridas_8767.jpg`, `04_curvas_evalF.jpg`, `05_hitos_reporte_evalF.jpg`, `06_800x900_navegador.jpg`.

## 2. Defectos

Ningún P1 ni P2. Todo lo nuevo es de pulido o robustez.

**D-F1 · P3 · El resumen del pie (`#runsum`) ocupa dos líneas a 1150 y 1400 px.** «sin cambios (solo exporta) · desde la
base · sin extensión CFD» mide 34 px en columnas de 320–340 px (una línea solo a partir de ~1600 px). También `#runmsg`
de error parte en dos («evalF_stop falló: Corrida interrumpida: …») durante 8 s. Es el único bloque de más de una línea
fuera del chat y de Hitos. Reproducir: 1400×900, sin cambios en la tabla. Pista: acortar («solo exporta · base · sin
ext. CFD») o `white-space:nowrap; text-overflow:ellipsis` con el texto completo en `title`, como ya se hace < 1100.

**D-F2 · P3 · `POST /api/run` acepta texto no numérico en una clave numérica.** `{"edits":{"d2_mm":"x"}}` → 200
`{"started":true}`: toma el candado, crea la carpeta `zz_…` y la deja en «error · parámetro no encontrado o valor
inválido: could not convert string to float: 'x'». Desde la UI no pasa (`paramEdits` filtra), pero por API/MCP produce
una corrida basura en la galería. Pista: en `RunReq._edits`, si la clave está en `CONV`/`ALIASES` (salvo `AutoUpdate`)
exigir número; o en `_run_phases` validar antes de `acquire_lock`.

**D-F3 · P3 · Corrida borrada por otro proceso mientras se visualiza: 404 silenciosos.** Al cargar `dev3_b2_26` justo
cuando otra sesión la borró, el visor pidió sus 20 STL (dos y media veces: la promesa fallida se quita de la caché y se
reintenta) → **48 errores 404 en consola**, visor vacío y `#vmsg` «dev3_b2_26 · Stator_1, Impeller_1…» como si hubiera
cargado; el sondeo la quitó de la galería a los 3 s. Pista: en `loadGeometry`, si `n === 0` al terminar, `vEmpty('La
corrida ya no existe')` + `pollNow()`, y no reintentar un archivo que dio 404.

**D-F4 · P3 · Dos cifras distintas de «rendimiento de diseño».** Cabecera de Curvas: «η 86,3 %» (interpolación de la
curva 1D en Q de diseño); bloque Diseño del reporte: «η etapa 86,6 %». Un ingeniero preguntará cuál vale. Pista: etiquetar
la de Curvas como «η curva» o tomar la del reporte cuando exista.

**D-F5 · P3 · La columna Base sigue al selector de proyecto, no al origen de la corrida activa.** Tras crear
`evalF_nueva`, la columna Corrida de `evalF_b2_26_22` (de `primera-bomba`) marca en ámbar d2, dS, β… frente a la base
de otra bomba (`04_curvas_evalF.jpg`, columna central). Pista: `changed` solo si `st.run.project` apunta al proyecto
seleccionado, o mostrar el nombre del proyecto de la corrida en la cabecera de la columna.

**D-F6 · P3 · Detener es global.** `CHAT_PROC` es único: con dos pestañas (o dos clientes) del mismo servidor, Detener
en una mata el chat de la otra (lo evité a propósito al ver «Claude trabajando» ajeno). Coherente con «un chat a la
vez», pero conviene que `/api/chat/stop` reciba el `session_id` y solo pare el suyo, o que la UI avise «hay otra
conversación en curso desde otra pestaña».

**D-F7 · P3 · `d2_mm` sin redondear en la fila ligera.** `/api/poll` da `216.441090310957`; la UI lo formatea, pero el
JSON (y `cft_runs`) crece y el modelo lo repite tal cual. Pista: `round(…, 3)` en `_summary`/`_project_info`.

Menores sin número: `_STL_LOCKS` crece un `Lock` por archivo y nunca se vacía (irrelevante salvo servidores de días);
`captureThumb` automática usa fondo neutro, pero la miniatura de `evalF_nueva_1` se tomó con la extensión oculta y la
voluta tapando el rodete (es la vista iso por defecto; «↻ Miniatura» lo resuelve); el 800 px headless con ventana de 1900
px deja el visor de 42vh = 800 px (solo pasa en capturas, no en pantallas reales).

## 3. Observaciones por criterio de la rúbrica

**Diseño**
- Jerarquía visual (9): visor 780×528 / 1220×650 protagonista, runbar con nombre entero + tags + fecha/duración, pie con
  Ejecutar siempre visible y resumen de lo que se lanza. Resta `runsum` partido (D-F1).
- Layout sin desperdicio (9): sin scroll de página en 1150/1400/1920; 800 px en 1807 px con pie fijo; dock clamp(280, 32vh,
  420) deja chat legible (287 px a 900 de alto, 345 a 1080). Resta 156 px vacíos bajo el pie a 1920.
- Consistencia (9): coma decimal en tabla, galería, runmeta, comparar, curvas y `runmsg` (D2-1 cerrado); tags/toast/badge
  por estado; el mismo chip-patrón para A/B, Superponer y filtros. Resta la doble η (D-F4).
- Descubribilidad (10): β y s en la tabla con cursiva + `title` para «automático»; `?` con 12 atajos (incluye Supr y ＋);
  🗑 visible al pasar y tenue en la activa; «Reporte» explicado en `title`; «＋ Nueva» con sugerencia de base, nq, k y aviso
  de salto; diálogo prellenado; «Reporte ↗» junto al bloque Diseño.
- Responsive (9): 1150 con chip-icono y fecha visible (D2-4 cerrado), 1100–1279 galería en fila, 800 en 1807 px (D2-2
  cerrado). Resta D-F1 (es un problema de ancho de columna).
- Visor (10): cambio de corrida 86–151 ms la primera vez y 29–40 ms después, 0 frames en reposo, B en alambre, sin fuga.
- Retroalimentación (9): contadores coherentes (botón/header/tarjeta) también con candado ajeno; Detener en 0,4 s;
  «Corrida interrumpida» en 16 s; toasts de borrar/guardar/crear. Resta D-F3 (visor vacío sin decir por qué).
- Accesibilidad (9): 0 textos < 12 px, contraste ≥ 5,2 en lo medido, `alertdialog` para borrar, roving tabindex, foco
  gestionado en popover y en el borrado. Sin regresiones respecto a la ronda 2.

**Funcionalidad**
- Todo lo de la rúbrica y lo nuevo de la ronda 3 funciona de verdad: β2 editado llega al `.cft` en radianes con
  `AutoUpdate2=False` y CFturbo lo respeta (`corrected {}`); borrar con 🗑/Supr pasa a la vecina, DELETE 200, bitácora;
  Curvas y Reporte con valores correctos; «＋ Nueva» crea, selecciona y corre OK; candado global y Detener verificados
  con procesos reales; 0 y 20 corridas; selftest y MCP con 12 tools.
- Robustez: validación 422 con `detail` de texto, traversal bloqueado, ETag/304, `write_json` atómico, `.visor/` viaja
  con la versión y se poda con la corrida. Restan D-F2 (texto en clave numérica) y D-F3.
- La interfaz aguantó sin un solo error JS que otra sesión borrara corridas y versiones debajo de ella y usara el chat
  a la vez; lo único visible fueron los 404 de STL.

## 4. Notas

**DISEÑO: 9/10.** Los ocho P3 de la ronda 2 están cerrados y medidos (coma en `runmsg`, 1807 px a 800, cabecera en una
línea, fecha visible a 1150, miniaturas de fondo neutro, `.dim` y placeholder ≥ 4,5, `RUN_LOCK`, dock más alto). Los
letreros quedaron en una línea salvo el resumen del pie a 1150–1400 (D-F1), que es exactamente el tipo de detalle que
pedía el punto 8 de la ronda 3, y la doble η (D-F4). No es 10 por eso y por los 156 px vacíos a 1920.

**FUNCIONALIDAD: 9/10.** Todo funciona y se reprodujo con corridas reales, candado real, Detener real y MCP real; las
cifras de rendimiento de `opt_final.md` se confirman o se superan (86–151 ms frente a 456 ms, 11,43 MB frente a 11,5,
304 de 300 B, 0 frames en reposo, geometrías estables en 34 y 64). Falta un punto por D-F2 (una corrida basura por API
con texto en clave numérica), D-F3 (404 silenciosos y visor vacío si la corrida desaparece) y porque «sin login» y «Nueva
conversación» siguen verificados solo en código o en rondas anteriores.

**Listo para uso: sí**, para un ingeniero en este PC con la licencia local.
- Porque el flujo completo (proyecto → tabla con β → Ejecutar → visor/curvas/reporte → comparar → versión → entregar
  STEP/ccm) se hizo de principio a fin sin tocar nada a mano y con cifras verificables en el `_out.cft`.
- Porque los estados que rompen el trabajo (CFturbo ocupado, chat ocupado, servidor caído, corrida interrumpida) se
  muestran y se recuperan solos; una corrida a la vez queda garantizada entre UI, chat y otras sesiones.
- Porque el coste de uso es bajo: 11 MB por corrida vista, sondeo de 300 B, selftest de 5 s, MCP de 12 tools con
  `cft_delete`/`cft_new`.
- Con la condición de aplicar D-F1 y D-F2 en una pasada corta (son dos líneas cada uno) y tener presentes los riesgos de abajo.

**Riesgos conocidos**
1. **`%TEMP%\cfturbo-agent` compartido entre sesiones**: cualquier agente con `cft_delete` (o un `rmtree`) borra corridas
   ajenas sin rastro en la bitácora (las temporales no se anotan); hoy ocurrió tres veces. Mitigar: línea de bitácora
   también al borrar temporales y un aviso en la UI cuando la activa desaparece (D-F3).
2. **Detener/CHAT global** (D-F6): dos pestañas del mismo servidor se pisan el chat.
3. **Fijar β2 deja «Coupling partially deactivated»** (documentado): desde Ejecutar no se corrige; solo el chat aplica
   `MeanSurface[Mean surface]/Coupled=False`.
4. **«＋ Nueva» fuera de ×1,5 en nq** solo avisa; la geometría escalada puede salir con errores de meridiano y la primera
   corrida de un proyecto nuevo tarda el doble (53 s).
5. **Caché del navegador de `/stl/` (1 h)**: si una corrida se borra y se recrea con el mismo id (mismo segundo), el visor
   podría mostrar STL viejos; improbable por el sufijo de hora.
6. **`cft_runs` por MCP devuelve `report` y `timing` de todas las corridas**: con decenas de corridas con reporte el JSON
   que lee el modelo crece (hoy 18,6 KB con 3 corridas).
7. **Sin login de la CLI** sigue sin probarse en vivo (la tarjeta `claude auth login` existe en código).

## 5. Resumen en 10 líneas

1. Probado end-to-end en 8765 (código = main `63120b5`) con navegador real a 1150/1400/1920/800, Chrome headless (9 capturas en `agents/out/eval_final/`), curl, selftest (4,99 s) y MCP stdio (12 tools con `cft_delete` y `cft_new`). Sin tocar código.
2. β2 editado desde la tabla llega al `_out.cft`: `AutoUpdate2=False`, Beta2 = 0,4538/0,3840 rad (26/22°), `realized` igual, sin correcciones; β1/β2/s en tabla y en Comparar con Δ.
3. Borrar: versión con 🗑 y temporal con Supr, confirmación en la tarjeta, Esc cancela, DELETE 200, la activa pasa a la vecina, «★ como» desaparece, bitácora «VERSIÓN BORRADA».
4. Curvas (H-Q con punto de diseño, η-Q, P-Q, puntero, A+B superpuestas también en Comparar) y Reporte (HTML 725 KB en pestaña, bloque Diseño con βB2 26/22°, ηh 92,1 %, NPSHR 4,8–10,1 m) verificados contra el `run.json`.
5. «＋ Nueva» Q 180 / H 50 / n 2900: nq 34,5, base CP nq37 (k 1,049), proyecto creado y elegido, `evalF_nueva_1` OK sin avisos en 53 s (d2 216,4); proyecto y corridas borrados al final.
6. Cifras de `opt_final.md` confirmadas o superadas: 20 STL 60,6 → 11,7 MB (11,43 MB en red), cambio de corrida 86–151 ms (29–40 ms en caché), poll 1 212 B y 304 de 300 B, 0 frames en reposo, geometrías 34→34 y 64→64 tras 5 y 10 cambios (sin fuga).
7. Candado global con PID externo → 409 + botón bloqueado + contador; Detener en 0,4 s mata `CFturbo.exe`, libera el candado y la corrida queda «interrumpida» en 16 s; chat de solo lectura responde en 13 s con tabla y ofrece corregir sin correr.
8. `.visor/` no rompe nada: se copia con la versión (20 STL) y se poda con la corrida; 0 y 20 corridas correctas; 800×900 en 1807 px; 0 textos < 12 px.
9. Defectos, todos P3: `runsum` a dos líneas a 1150–1400, API acepta texto en clave numérica (corrida basura), 404 silenciosos si otra sesión borra la corrida en pantalla, doble η, columna Base sigue al selector, Detener global, d2 sin redondear.
10. Notas: **DISEÑO 9/10 · FUNCIONALIDAD 9/10**. Listo para uso con una pasada corta sobre D-F1/D-F2; riesgo principal: `%TEMP%` compartido entre sesiones que borran sin rastro.
