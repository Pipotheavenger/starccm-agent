# Evaluación E2E · ronda 0 (línea base)

Fecha: 2026-10-23 06:40–06:55 · Evaluador: Director E2E (Fable) · Servidor probado: `http://localhost:8765`
(preview del orquestador; commit base `99fe32b` + cambios sin commit). Un segundo servidor en `8766` solo para
dos pruebas aisladas (WORKDIR vacío y CLI de Claude inexistente); apagado al terminar.

Cómo se probó: navegador real (panel Browser de Claude Code, viewport emulado 1400×900 y 800×900) para las
acciones; Chrome headless 1400×900/1400×1300/800×2600 para las capturas (el panel es demasiado pequeño para
capturas legibles); `curl` para la API; `--selftest` y handshake MCP por stdio con un cliente JSON-RPC mínimo.
Capturas en `agents/out/eval0/`. Corridas/versiones creadas: `eval0_d2_215`, `eval0_7al_desde_v1`,
`eval0_autoupd_H85`, versión `versions/eval0_v1`; el chat creó `eval0_7al_desde_v1_fixed` y `v_7alabes`.

Nota de contexto: durante la evaluación otro agente (Explorador) lanzaba corridas por MCP en paralelo
(`v5_entrada_continua`, `v4b_dH_minimo`…). Eso descubrió defectos reales de concurrencia (D2, D7) y explica que
la UI me "robara" la selección de corrida un par de veces.

## 1. Tabla de funcionalidades

| # | Función | Estado | Evidencia |
|---|---|---|---|
| F1 | Selector de proyecto e info (tipo, componentes, fluido, nq) | OK | `01_inicio_1400.png`; `/api/project/primera-bomba` → Q 227 m³/h, H 70 m, 3600 rpm, nq 37.4 |
| F2 | Tabla base / corrida / nuevo con nq en vivo | OK (parcial en diseño) | nq nuevo 37.4 al teclear; columna "Nuevo" de 48 px recorta los valores ("70.(", "360(") a 1400 px, ver `05_corriendo_1400.png` |
| F3 | Ejecutar en CFturbo (corrida real) | OK | d2 215 → `eval0_d2_215`, 26.1 s, rc 1, 26 archivos, `realized d2_mm=0.215`; botón se desactiva y el header pasa a "CFturbo trabajando" |
| F4 | Partir de la corrida seleccionada | OK | body enviado: `project=…\versions\eval0_v1\eval0_d2_215_out.cft`, run.json `project` lo confirma; nBl 7 realizado |
| F5 | AutoUpdate | parcial | H 85 + AutoUpdate: CFturbo recalculó d2 227.3 / b2 23.64 / dS 117.5 pero rompió el meridiano ("Shroud material is self-intersecting") → error sin exportes; la UI lo muestra pero no orienta (`09_error_autoupdate_1400.png`) |
| F6 | ext_outlet (casilla "Quitar extensión CFD") | OK | `realized ext_outlet=False`; desaparece el aviso de solapamiento respecto a `v2_d2_220` |
| F7 | Hitos, avisos, correcciones | OK (con falso positivo) | Hitos con hora; avisos en ámbar, errores en rojo; "CFturbo corrigió MeanSurface…/Coupled: pedido false → False" es un falso positivo por mayúsculas (`06_visor_1400.png`) |
| F8 | Archivos: descarga | OK | `GET /files/bomba_d2_220/v2_d2_220_Co2.stp` → 200, `content-disposition: attachment`, 1.66 MB |
| F9 | Archivos: Abrir carpeta | OK | `POST /api/open` → `{"opened": "...versions\eval0_v1"}` (se abrió el Explorador) |
| F10 | Guardar versión | OK | `eval0_v1` creada en `versions/`, fila ★ en la tabla, botón pasa a "★ Guardada", línea en `recipes/bitacora.md`; duplicado → 409 "ya existe versions/bomba_d2_220" |
| F11 | Galería de versiones | parcial | No hay galería: las versiones son filas ★ mezcladas en "Corridas"; la fila de la versión y la de su corrida temporal aparecen las dos (`eval0_v1` y `eval0_d2_215`) |
| F12 | Visor: piezas y tapas | OK | 20 STL cargados; apagar Volute_1: 11 → 8 visibles; tapas: → 12; restaurado 11 |
| F13 | Visor: orbitar / zoom | OK | OrbitControls con damping; cámara encuadrada tras cargar (pos 387,-438,338) |
| F14 | Visor: encuadre | falla | No existe botón/atajo de "Encuadrar"/reset de cámara; solo `window.__cft.fit()` desde consola |
| F15 | Visor: cambio entre corridas | OK | Clic en fila `eval0_d2_215` → `pinned=true`, geometría y tabla cambian; corrida con error → "esta corrida no tiene STL" |
| F16 | Chat: resumen | OK (comportamiento discutible) | "Dame un resumen de la última corrida" → cft_runs + tabla; pero además lanzó un `cft_run` de corrección no pedido (76 s, 4 turnos). `08_chat_volcado.png` |
| F17 | Chat: variante 7 álabes + regla de avisos | OK | `cft_recipe_search` → `cft_run` con `ext_outlet=False` y `Coupled=False` → rc 0, 0 avisos, 61 s |
| F18 | Chat: Detener | parcial | Mata el proceso (botones vuelven, `chatting=false`, sin corrida huérfana), pero el log no muestra ningún mensaje de "detenido"; la sesión tardó >14 s en emitir `init` |
| F19 | Chat: Nueva conversación | OK | `session=null`, `localStorage` limpio, log vacío, estado "nueva conversación" |
| F20 | Estado: CFturbo ocupado | parcial | `/api/run` concurrente → 409 "ya hay una corrida"; pero el candado no ve las corridas del chat ni de otros clientes MCP (ver D2) |
| F21 | Estado: chat ocupado | OK | segundo `/api/chat` → `{"kind":"error","text":"ya hay una conversación en curso; espera o pulsa Detener"}` |
| F22 | Estado: sin CLI / sin login | parcial | CLI inexistente → mensaje claro "no pude lanzar la CLI…". Sin login no se pudo provocar (la sesión está logueada); la detección es un regex sobre el texto `401|OAuth` |
| F23 | Selftest | OK | `selftest OK` en 2.0 s |
| F24 | MCP por stdio | OK | `initialize` → protocolVersion 2024-11-05, `tools/list` → 10 tools `cft_*`, `cft_nq` y `cft_projects` responden; 0.9 s |
| F25 | Consola del navegador | OK con matiz | Sin errores JS. Solo `ERR_CONNECTION_REFUSED` acumulados de cuando el servidor estuvo caído (el poll cada 3 s los genera) y un aviso "Deprecated API for given entry type" |
| F26 | 0 corridas | no probado del todo | Con WORKDIR vacío siguen saliendo las versiones (2 filas); por código, con 0 filas el visor dice "sin geometría" y Hitos "esperando corrida…". No hay estado vacío guiado |
| F27 | 20 corridas | parcial | Imposible por diseño (poda a 8 temporales + versiones). Con 10 filas, la columna derecha ya mide 954 px de contenido en una ventana de 900: la tabla de corridas empieza en y=797 y hay que hacer scroll dentro del aside |
| F28 | Responsive 800 px | falla | Ver D1 y `04_inicio_800_completo.png` |
| F29 | Pedir a Claude (botón) | OK (no ejecutado) | Compone el prompt con los edits y lo envía por el mismo canal del chat; no se probó para no ocupar CFturbo |

## 2. Defectos

**D1 · P1 · Layout roto por debajo de 1100 px.** A 800×900 `main` reparte 293/269/293 px entre las tres
filas porque `body` es `grid auto 1fr` con `height:100%` y las filas no pueden crecer; `#center`
(60vh + 380 px = 920 px) desborda su fila de 269 px y el chat queda pintado encima de la columna derecha
("Detener" sobre la tabla de corridas, "Guardar versión" flotando), y cada aside se convierte en una caja de
293 px con scroll interno (contenido 796/937 px). Reproducir: ventana de 800 px, cargar `/`, bajar.
Evidencia: `04_inicio_800_completo.png`, medidas en §1-F28.

**D2 · P1 · El candado "una corrida a la vez" no cubre al chat ni a otros clientes MCP.** `RUN_LOCK` vive en
`ui/server.py`; el chat corre `cft_run` en otro proceso (`claude -p` → `mcp_server.py`). Mientras Claude corría
`v_7alabes`, `runbtn.disabled=false` y el header decía "listo": un clic en Ejecutar habría lanzado un segundo
CFturbo.exe con una sola licencia. Reproducir: pedir "Haz una variante" al chat y, durante la corrida, mirar
el botón Ejecutar / `GET /api/status` (`running:false`).

**D3 · P1 · Detener no da ninguna retroalimentación.** Tras pulsar Detener, el log no cambia (el evento
`done`/`rc` se ignora en el cliente) y el usuario no sabe si se paró, si llegó a correr CFturbo o si debe
volver a escribir. Reproducir: enviar "Propón 3 variantes…", pulsar Detener a los 10 s.

**D4 · P1 · "Resumen" ejecuta CFturbo sin que se lo pidan.** La REGLA FIJA del system prompt hace que una
pregunta de solo lectura dispare `cft_run` (corrida `eval0_7al_desde_v1_fixed`, 30 s extra, la corrida
"activa" del panel cambia bajo los pies del usuario). La regla debería aplicarse a corridas que Claude crea,
no a consultas. Reproducir: botón "Resumen" con una última corrida que tenga avisos.

**D5 · P2 · Con la última corrida en error, el visor (protagonista) arranca vacío.** Al abrir la página se
selecciona la corrida más reciente aunque no tenga STL; se ve una caja negra de 700×517 px con el texto "esta
corrida no tiene STL". Debería caer a la última con geometría o mostrar un estado vacío con acción.
Evidencia: `01_inicio_1400.png`.

**D6 · P2 · Columna "Nuevo" de 48 px.** A 1400 px los inputs recortan "70.0" → "70.(", "3600" → "360(". La
tabla tiene 4 columnas en 336 px de aside. Evidencia: `05_corriendo_1400.png`.

**D7 · P2 · La selección de corrida se pierde al aparecer corridas ajenas.** `poll()` salta a `runs[0]` si no
está "pinned"; una corrida del chat o de otro cliente MCP reemplaza lo que el usuario estaba mirando (me pasó
con `v5_entrada_continua` mientras evaluaba `eval0_d2_215`). Fijar siempre que el usuario haya hecho clic, o
avisar con un toast "nueva corrida: X".

**D8 · P2 · Falso "CFturbo corrigió".** La comparación de `realized` vs `requested_si` es por texto cuando
no es numérico: `false` vs `False` se reporta como corrección en ámbar (`06_visor_1400.png`, chat).
Normalizar booleanos en `_to_si` o comparar en minúsculas.

**D9 · P2 · Versión y corrida origen duplicadas en "Corridas"; la versión pierde su estado.** Tras guardar,
aparecen `★ eval0_v1 · guardada` y `eval0_d2_215 · warn` como dos filas; la fila ★ sustituye el estado
(ok/warn/error) por "guardada". No hay galería de versiones separada (rúbrica).

**D10 · P2 · Los campos "Nuevo" no se limpian ni se marcan tras Ejecutar.** El d2=215 tecleado para la primera
corrida se envió otra vez en la segunda ("Partir de la corrida…" + nBl 7 → edits `{d2_mm:215, nBl:7}`). No
rompe nada hoy, pero con AutoUpdate o partiendo de otra corrida puede sobreescribir en silencio.

**D11 · P2 · Markdown del chat: escapes `\_` visibles.** "eval0\_7al\_desde\_v1" se muestra con barras; tampoco
hay listas ni encabezados. Evidencia: `08_chat_volcado.png`.

**D12 · P2 · Estado "chatting" invisible en el header; `ToolSearch` expuesto.** `/api/status` ya devuelve
`chatting` pero el header solo pinta `running`; la primera burbuja de herramienta es "ToolSearch
select:mcp__cfturbo__cft_runs", ruido interno para el usuario.

**D13 · P2 · No hay botón "Encuadrar" ni vista por defecto; sin teclado en el visor ni en la tabla de
corridas.** Las filas `tr.run` no tienen `tabindex`/`role=button`; el canvas tiene `tabindex=-1`.
Contraste correcto (texto atenuado 6.0:1, tags 4.7–5.6:1) pero tipografía mínima de 11 px en hitos y tags.

**D14 · P2 · AutoUpdate casi siempre termina en error sin orientación.** CFturbo recalcula d2/b2/dS y el
meridiano se autointersecta (ya documentado en CLAUDE.md). La UI muestra 7 cajas rojas en inglés y nada más:
falta "qué hago ahora" (p.ej. sugerir editar d2/b2 a mano o pedir a Claude la corrección).

**D15 · P2 · Columna derecha sin jerarquía con errores.** 6–7 cajas de error empujan "Guardar versión",
"Archivos" y "Corridas" fuera de pantalla (tabla en y=797 de 900). Los mensajes de CFturbo salen crudos y
repetidos (STAR-CCM+ y OpenFOAM dicen lo mismo dos veces).

**D16 · P2 · Errores de consola cuando el servidor cae.** El poll cada 3 s acumula `ERR_CONNECTION_REFUSED`
sin límite; el header sí dice "sin conexión". Hacer backoff.

**D17 · P2 · Nombre por defecto `v2` siempre.** `placeholder` es "v2" pero el valor real que se envía es
`v<n+1>` según el número de corridas; el usuario ve "v2" y recibe "v11".

## 3. Observaciones de diseño (según la rúbrica)

- **Jerarquía visual (6/10).** Tres columnas iguales en peso; el visor es grande pero vacío al arrancar si la
  última corrida falló (D5). Las cabeceras en mayúsculas pequeñas funcionan; falta un nivel intermedio
  (título de la corrida activa) que una visor + hitos + archivos como "la corrida seleccionada".
- **Layout sin desperdicio (5/10).** A 1400×900 la columna izquierda necesita scroll para llegar a Ejecutar
  (botón en y≈930) y la derecha para llegar a Corridas; el chat ocupa 340 px fijos aunque esté vacío. A 800 px
  está roto (D1).
- **Consistencia (7/10).** Tokens de color coherentes, mono para números, tags ok/warn/error/guardada.
  Inconsistencias: botón "★ Guardar versión" en primario pero "Ejecutar" también; "Pedir a Claude" sin icono;
  mensajes de CFturbo en inglés mezclados con UI en español.
- **Descubribilidad (6/10).** La casilla "Partir de la corrida seleccionada" y la de extensión CFD exigen
  leer la frase completa; la columna "Corrida" cambia de nombre según la selección (bien) pero nadie explica que
  los inputs vacíos heredan el placeholder. Nada indica que las corridas se eligen haciendo clic en la fila.
- **Responsive (3/10).** ≥1100 px correcto; <1100 px inutilizable (D1).
- **Visor protagonista (7/10).** Cuando hay geometría se ve bien (colores por componente, transparencia del
  estator/voluta, impulsor opaco, ejes). Faltan encuadre, vistas (frontal/meridional), fondo con rejilla o
  escala, y un estado vacío útil.
- **Retroalimentación (6/10).** Corrida: buena (botón, header, hitos con hora, vmsg). Chat: estados de texto
  pequeños en la cabecera, sin spinner; Detener mudo (D3); CFturbo trabajando por el chat no se refleja (D2/D12).
- **Accesibilidad (6/10).** Contraste suficiente, `lang=es`, inputs etiquetados; filas y visor sin teclado,
  11 px en varias partes, foco solo con el anillo por defecto del navegador.

## 4. Notas

**DISEÑO: 5/10.** A escritorio ancho la interfaz es legible, coherente en color y tipografía y el visor
luce bien cuando hay geometría, pero el arranque típico (última corrida con error) deja la zona principal
vacía y hay scroll obligatorio en ambas columnas a 1400×900. Por debajo de 1100 px el layout se solapa y es
inutilizable, y faltan piezas de descubribilidad (encuadre, estado vacío, galería de versiones, feedback de
Detener) que un usuario nuevo echaría en falta sin ayuda.

**FUNCIONALIDAD: 7/10.** Todo lo esencial funciona de verdad y rápido: corrida real en ~26 s, partir de una
versión, exportes descargables, guardar versión con bitácora, visor con piezas/tapas, chat real con Claude
Code que busca recetas, corrige avisos y responde en tablas, selftest y MCP por stdio limpios. Resta un punto
largo por la concurrencia (el candado de CFturbo no ve al chat ni a otros MCP), otro por "Resumen" que ejecuta
CFturbo sin pedirlo y Detener sin confirmación, y medio por falsos "corrigió", duplicados en la lista y AutoUpdate
que falla sin guía.

## 5. Resumen en 10 líneas

1. Probado end-to-end en 8765 con navegador real, Chrome headless para capturas, curl, selftest y MCP stdio.
2. Corrida real OK (d2 215 → 26 s, 26 archivos), partir de versión OK, ext_outlet OK, descarga y Abrir carpeta OK.
3. Guardar versión OK (`eval0_v1`), poda a 8 temporales verificada, bitácora actualizada.
4. Visor OK: 20 STL, piezas/tapas conmutables, orbitar; sin botón de encuadre y vacío si la última corrida falló.
5. Chat real OK: resumen con tabla y variante de 7 álabes con recetas y 0 avisos (61–76 s); Nueva conversación OK.
6. P1: layout roto <1100 px (solapamiento del chat sobre la columna derecha).
7. P1: el candado de CFturbo no cubre las corridas del chat/MCP → dos CFturbo posibles con una licencia.
8. P1: Detener sin feedback; "Resumen" lanza una corrida de corrección no pedida.
9. P2: columna "Nuevo" recortada, falso "CFturbo corrigió" (false/False), duplicado versión+corrida, `\_` en el chat, AutoUpdate falla sin guía.
10. Notas: DISEÑO 5/10 · FUNCIONALIDAD 7/10. Selftest OK, MCP OK, sin errores JS en consola.
