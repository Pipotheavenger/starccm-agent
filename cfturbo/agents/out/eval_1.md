# Evaluación E2E · ronda 1

Fecha: 2026-10-23 07:05–07:25 · Evaluador: Director E2E (Fable) · Servidor probado: `http://localhost:8765`
(preview del orquestador, ya con el código nuevo: `ui/index.html` + `ui/app.js` + `ui/style.css` + `ui/server.py` +
`mcp_server.py`, commit `a4ef441`/`e05d722` + cambios sin commit). Un segundo servidor en `8767` solo para la prueba de
reconexión (apagado al terminar).

Cómo se probó: navegador real (panel Browser de Claude Code, viewport emulado 1400×900 y 800×900, medidas con
`getBoundingClientRect`/`elementFromPoint`, consola leída al final); Chrome headless 1400×900, 1150×760, 1920×1080 y
800×2400 para capturas legibles (`agents/out/eval1/01…05`); `curl` para la API; `--selftest`; handshake MCP stdio con
un cliente JSON-RPC mínimo. **No me fié del informe del programador: cada punto de abajo se reprodujo.**
Corridas creadas: `eval1_d2_218` (UI, 30,3 s), `eval1_autoupd_H85` (UI, AutoUpdate, error), `eval1_chat_7al` (chat,
45 s), versión `versions/eval1_v1`, candado externo manual `eval1_candado_externo`.

Contexto: el Explorador seguía corriendo CFturbo en paralelo desde `%TEMP%\cfturbo-explora` (vi su `CFturbo.exe` con
`Get-CimInstance`). Eso destapó el límite del candado nuevo (ver D-N2).

## 1. Tabla de verificación

### 1.1 Defectos de eval_0

| # | Defecto ronda 0 | Estado | Evidencia |
|---|---|---|---|
| D1 P1 | Layout roto < 1100 px | **OK** | 800×900: rectángulos runbar/visor/explorador/propiedades/dock sin ningún cruce; `.explorer` 471/471 y `.props` 513/513 (sin scroll anidado); visor 504 px; pie fijo con `#runbtn` en y=837–869 arriba y abajo del scroll; página 785 px de ancho (sin scroll horizontal). `02_inicio_800_completo.png` |
| D2 P1 | Candado no cubre chat/MCP | **OK** (con límite nuevo, D-N2) | Chat lanzó `cft_run eval1_chat_7al`: a los 2 s `/api/status` → `running:true, running_name:"eval1_chat_7al"`, `#runbtn` deshabilitado «Corriendo eval1_chat_7al… 4 s», header «CFturbo trabajando · eval1_chat_7al · 4 s · Claude trabajando». Candado manual con PID vivo → `409 CFturbo trabajando (eval1_candado_externo)` y botón bloqueado; al borrarlo se libera en 1 s |
| D3 P1 | Detener sin feedback | **OK** | «Propón 3 variantes…» + Detener a los 10 s → en 1 s aparece «Detenido por el usuario.», `#chatstate` «detenido», Enviar habilitado, Detener deshabilitado, sin `running.lock` |
| D4 P1 | «Resumen» lanzaba CFturbo | **OK** | Resumen con última corrida en error → solo `cft_runs`, 3 turnos, 26 s, ninguna corrida nueva; la respuesta menciona la causa del error y no corre nada |
| D5 P2 | Visor vacío al abrir | **OK** | Al cargar con última corrida en error (`eval1_autoupd_H85`) se selecciona `eval1_chat_7al`/`dev1_d2_213` (última con STL) y el visor sale con 20 superficies |
| D6 P2 | Columna «Nuevo» de 48 px | **OK** | Inputs de 72 px; «206.3», «3600» completos (`01_inicio_1400.png`) |
| D7 P2 | Selección robada | **OK** | Clic en tarjeta → `pinned=true`, chip «Fijada · volver a la última»; clic en el chip → vuelve a la última y «Siguiendo la última». Lógica de toast para corridas ajenas presente (no se dio el caso con fijada) |
| D8 P2 | Falso «CFturbo corrigió» | **OK** | `eval1_chat_7al` con `Coupled=false` y `ext_outlet=false`: `requested_si` = `realized` = `False`, `corrected: {}`; selftest cubre `_to_si("false")` |
| D9 P2 | Versión + temporal duplicadas | **OK** | Tras guardar `eval1_v1`: la versión «Con avisos ★ Guardada» y la temporal atenuada «Con avisos ★ como eval1_v1»; el tag de estado se conserva |
| D10 P2 | «Nuevo» no se limpia | **OK / parcial** | Los inputs se vacían al lanzar (verificado). Pero **las casillas de Opciones no**: tras la corrida con AutoUpdate, `#autoupd` sigue marcada (ver D-N5) |
| D11 P2 | `\_` en el chat | **OK** | `innerHTML` sin `\_`, 2 tablas, negritas y viñetas renderizadas. Queda el `---` literal (menor) |
| D12 P2 | `chatting` invisible / ToolSearch | **OK** | Header «Claude trabajando» con punto azul, punto en la pestaña Chat; en el log solo tools `cft_*` (`cft_runs`, `cft_recipe_search`, `cft_run`) |
| D13 P2 | Sin Encuadrar ni teclado | **OK** | Encuadrar: tras mover cámara, `F` → Δ posición = 0. Iso/Axial/Lateral: dirección (0,0,+z) y (+x,0,0). Flechas y Enter en la galería, `` ` `` pliega, 1/2/3 vistas |
| D14 P2 | AutoUpdate sin guía | **OK** | H 85 + AutoUpdate → error en 8 s; «Hitos y avisos» abre con caja «Qué hacer: AutoUpdate recalculó d2/b2/dS y el meridiano quedó inválido. Prueba sin AutoUpdate…» + enlace «pedir a Claude que lo corrija»; visor: «La corrida terminó con error; no hay geometría. Mira «Hitos y avisos»» con enlace; resumen flotante «6 errores · 1 aviso → ver»; badge rojo 7 |
| D15 P2 | Columna sin jerarquía con errores | **OK** | Los 6 errores viven en la pestaña; no empujan nada (Guardar/Archivos/galería fijos) |
| D16 P2 | Consola al caer el servidor | **parcial** | Backoff real 3 → 6 → 12 → 30 s con banda «Sin conexión con el servidor local. Reintento en N s.»; la página se recupera sola sin recargar. Pero en 40 s de caída la consola acumuló **10** `ERR_CONNECTION_REFUSED` (criterio del spec: ≤ 4) y el «Reintento en N s» no cuenta atrás |
| D17 P2 | Nombre «v2» | **OK** | Placeholder `primera-bomba_1`, que es lo que se envía |

### 1.2 Spec UX (P0/P1) y rúbrica

| # | Ítem | Estado | Evidencia |
|---|---|---|---|
| P0-1 | Separación html/js/css, ids conservados | OK | `index.html` 145 líneas sin `<style>`/`<script>` salvo importmap; de los 41 ids de §2.3 solo falta `runs` (sustituido por `gallery`, previsto) |
| P0-2 | Grid CAE, visor protagonista | OK | 1400×900: `#viewer` 780×536 abierto, 780×780 plegado; `scrollHeight` 900; ningún panel con `scrollWidth > clientWidth` |
| P0-3 | Pie fijo, filas 28 px | OK | 11 filas de 28 px; `#runbtn` y=833–865 |
| P0-4 | «Partir de» segmentado | OK | Corrida con error → segmento deshabilitado con tooltip «Una corrida con error no tiene .cft de salida»; corriendo → «Espera…»; normal → nombre de la corrida |
| P0-5 | Dock con pestañas y plegado persistentes | OK | Cada pestaña oculta las otras (`hidden`); plegado → visor 780 px; `localStorage` `cft_tab`/`cft_dock_collapsed`; contadores «Hitos 1», «Archivos 26», «7» en rojo con errores |
| P0-6 | Runbar completo | OK / parcial | Nombre, tag, «23 oct 07:10 · 30,3 s», chip, Guardar en línea (Enter/Esc), Abrir carpeta. **Pero el nombre se trunca** («dev1_d2_…» a 1400 px con dos tags; «e…» a 1150 px) — D-N3 |
| P0-7 | Galería de tarjetas con filtros, vacío, teclado | **falla visual** | Hay 11 tarjetas, filtros Todas 11 / ★ Versiones 3 / Temporales 8 / Con avisos 8, flechas + Enter funcionan. **Pero las tarjetas se solapan: cada fila del grid mide 88–110 px y las tarjetas 178–221 px**, así que fecha, d2, z, tag de estado y ⚠ quedan tapados por la tarjeta de abajo en TODAS las anchuras ≥ 1100 px (D-N1). Estado vacío solo revisado en código |
| P0-8 | Miniaturas | OK | `eval1_d2_218/thumb.png` 320×240, 28 KB, generada sola al terminar y visible en la tarjeta (`?v=1792757465`); POST no-PNG → 400; `versions/eval1_v1/thumb.png` existe y la tarjeta ★ la muestra |
| P0-9 | Apilado < 1100 px | OK | Ver D1 |
| P0-10 | Estados en español, contadores, toasts | OK | Tags: «Corriendo», «OK», «Con avisos», «Error», «★ Guardada»; botón «Corriendo eval1_d2_218… 2 s» avanzando; barra indeterminada (`runbar.busy`); toast «eval1_d2_218 terminó con 1 aviso»; tarjeta «Corriendo… 2 s» |
| P1-1 | Comparar A/B | OK | Ctrl+clic en `v_7alabes` → pestaña Comparar: d2 218,0 vs 206,3 → −11,7 / −5,4 % (cian), z 6→7 +16,7 % (ámbar), avisos solo en A (1); Intercambiar → +11,7 / +5,7 % y B pasa al visor; Esc limpia B; elegir la misma que A → toast «Elige como B una corrida distinta»; chip «Comparar A y B» aparece |
| P1-2 | Reconexión con backoff y mensajes | parcial | Ver D16; 409 → «Ya hay una corrida en marcha. Espera a que termine.»; 404 → mensaje con detalle; chat ocupado y login: solo revisados en código (la CLI está logueada) |
| P1-3 | Foco, teclado, aria-live | OK | `:focus-visible` propio; 69 elementos enfocables; `aria-live` en status/runmsg/chatstate/toast; `role=listbox/option`, `role=tablist`. Botones de vista nunca reciben `aria-pressed` aunque hay CSS para ello |
| P1-4 | Tema claro | OK | `◐` → `data-theme=light`, fondo `rgb(244,246,249)`, escena `#e9edf2` sin recargar |
| P1-5 | Dock redimensionable | OK (código + CSS; no arrastrado) | `pointerdown/move/up`, límites 160 px – 60 vh, `cft_dock_h` |
| P1-6 | Sondeo ligero | OK | `fields=summary`: 15,2 KB vs 52 KB con 11 corridas |
| P2-4 | Nueva conversación en dos clics, ↑ | OK | «¿Seguro? Pulsa otra vez para borrar» → segundo clic limpia; ↑ recupera el último mensaje |
| F | Selector de proyecto e info | OK | «Pump · Stator + Impeller + Volute · Water (20°C)», nq 37,4 |
| F | nq en vivo | OK | H 85 → nq nuevo 32,3 radial normal |
| F | Ejecutar real | OK | `eval1_d2_218` 30,3 s, 26 archivos, `realized d2_mm=0.218` |
| F | Archivos: descarga y Abrir carpeta | OK | Lista agrupada STAR-CCM+ (5) + «20 STL para el visor»; `/files/...` validado contra `..` (400) |
| F | Chat real: resumen, variante, regla de avisos | OK | Variante 7 álabes + d2 212: `cft_recipe_search` → `cft_run` con `Coupled=False` y `ext_outlet=False` → rc 0, 0 avisos, 83 s; la vista salta a la corrida nueva y genera miniatura |
| F | Selftest | OK | `selftest OK` (incluye candado vivo/muerto, thumb, summary, saved_from) |
| F | MCP stdio | OK | `initialize` 2024-11-05, 10 tools `cft_*`, `cft_nq` y `cft_runs` responden, 0,9 s |
| F | Consola del navegador | OK | Pestaña principal: 0 mensajes tras 20 min de pruebas (corridas, chat, comparar, tema, resize) |
| F | 0 corridas | no probado | `VERSIONS` es fijo (`HERE/versions`), no hay forma de vaciarlo sin tocar código; el texto de vacío existe en `renderGallery` |
| F | 20 corridas | no aplicable | Poda a 8 + versiones. Con 11 tarjetas la galería tiene scroll propio (687/576) y la cabecera «Corridas (11) · 3 ★» |

## 2. Defectos

### Nuevos

**D-N1 · P1 · Las tarjetas de la galería se solapan (≥ 1100 px).** El grid calcula filas de 88–110 px (lista a
1150: ~37 px) pero cada tarjeta mide 178–221 px porque la miniatura usa `aspect-ratio:4/3` con `width:100%` y su
alto no entra en el cálculo de la pista. Resultado: fecha, d2, z, tag de estado y ⚠ de cada tarjeta quedan **debajo
de la siguiente**; `elementFromPoint` sobre el tag de las 6 primeras tarjetas devuelve otra tarjeta («TAPADO»). Solo la
última fila se ve entera. El usuario no puede saber el estado de una corrida desde la galería, que es justo lo que la
galería debía resolver. Reproducir: abrir `/` a 1400 o 1920 px con ≥ 4 corridas. Evidencia: `03_corriendo_1400.png`,
`04_inicio_1150.png`, `05_inicio_1920.png`. Pista: dar alto explícito a la miniatura (`height:auto` + `aspect-ratio`
no basta en pistas `auto`; usar `grid-auto-rows:max-content` + `aspect-ratio` en un `::before`/padding-top, o
`contain-intrinsic-size`), o renderizar en flex-wrap. A 800 px (flex) no pasa.

**D-N2 · P2 · El candado es por `WORKDIR`, no por máquina.** `running.lock` vive en `%TEMP%\cfturbo-agent`; el
Explorador usa `CFTURBO_WORKDIR=%TEMP%\cfturbo-explora` y a las 07:15:40 y 07:15:45 había **dos `CFturbo.exe`
simultáneos** (uno suyo, otro de `eval1_chat_7al`) con la UI diciendo «CFturbo trabajando · eval1_chat_7al». Con una
licencia es exactamente lo que D2 quería evitar. Reproducir: `CFTURBO_WORKDIR=otra python mcp_server.py` + `cft_run`
mientras la UI corre. Pista: candado en una ruta fija (`%TEMP%\cfturbo-agent.lock` o `%LOCALAPPDATA%`) independiente
de `WORKDIR`.

**D-N3 · P2 · El nombre de la corrida activa se trunca en el runbar.** `.runname` es el único hijo con
`overflow:hidden`, así que flex lo encoge primero: a 1400 px con dos tags («Con avisos ★ como dev1_v1», que además
se parte en dos líneas) sale «dev1_d2_…» (94 px); a 1150 px sale **«e…»** (`04_inicio_1150.png`). Pista: `flex-shrink:0`
en el nombre o `min-width:12ch`, y los tags en una sola línea con `white-space:nowrap`.

**D-N4 · P2 · Contador de «Corriendo…» incorrecto con candado externo.** Con el candado manual la UI decía
«Corriendo eval1_candado_externo… 119 s» a los 3 s de crearlo: usa `st.runStart` (la última corrida lanzada desde esta
pestaña) en vez de `running_since` que ya viene en `/api/status`. Lo mismo pasa si el chat/otro cliente corre y la
corrida aún no aparece en el sondeo.

**D-N5 · P2 · Las Opciones no se restauran tras lanzar.** AutoUpdate quedó marcada después de la corrida
`eval1_autoupd_H85` (que falló por ella). El siguiente «Ejecutar» con un cambio en H volvería a romper el meridiano
sin que el usuario lo vea (el resumen «Opciones · 4 activas» está plegado). Pista: desmarcar AutoUpdate al lanzar, o
mostrar «AutoUpdate» en el pie junto a «N cambios».

**D-N6 · P2 · `saved_as_version` colgante.** `dev1_d2_213` dice «★ como dev1_v1» pero `versions/dev1_v1` no existe
(la versión se guardó en el worktree del programador). `list_runs` debería comprobar que la versión existe antes de
anunciarla, o la UI mostrar el tag solo si hay una tarjeta ★ con ese id.

**D-N7 · P3 · Detalles de pulido.** Botones Iso/Axial/Lateral sin `aria-pressed` (el CSS lo espera); «Reintento en
30 s» no cuenta atrás; placeholders de «Nuevo» con punto («206.3») y el resto de la tabla con coma («206,3»); el
filtro «Con avisos» incluye tarjetas en «Error» (tienen avisos además de errores); «---» del markdown se muestra
literal; el `runmsg` de una corrida con avisos se pinta en verde (`ok`).

### Persistentes

**D16 · P2 (parcial).** 10 errores de red en consola en 40 s de caída (criterio ≤ 4); el backoff funciona y la
recuperación es automática. El primer fallo dispara dos peticiones (`runs` + `status`) y cada reintento otra; el
navegador registra todas.

**Pendientes del spec (ronda 2, aceptado por el programador):** P2-1 superponer B, P2-2 recapturar miniatura,
P2-3 densidad de galería. «Ver B en el visor» se fusionó con Intercambiar (razonable).

## 3. Escalabilidad y estabilidad del código

- **`ui/app.js` (693 líneas, módulo ES).** Estado único `st`, secciones comentadas, `api()` común con `detail` del
  error, `LS` tolerante a `localStorage` roto. Puntos débiles: `renderActive()` hace cinco cosas (galería, segmento,
  tabla, hitos, archivos, guardar) y se llama en cada cambio de estado; `renderGallery()` con firma `gallerySig`
  evita repintados, bien. `selectRun()` descarga el `run.json` completo (con `events`/`geometry`) en cada cambio de
  estado; aceptable con 11 corridas. Errores: `selectRun` y `loadProjects` tragan excepciones en silencio (si
  `/api/runs/{id}` falla el panel se queda con la corrida anterior sin aviso). Sin tests de JS.
- **Fugas.** No encontré ninguna: `setInterval(tickClock)` único; el reloj del chat se limpia en todos los caminos;
  `pointermove/up` del dock se quitan en `up`; los inputs de la tabla se recrean con `innerHTML` (los viejos se
  recolectan); `onclick` en vez de `addEventListener` en tarjetas y pestañas evita duplicados; `ResizeObserver` ×2
  permanentes por diseño. El bucle rAF + `setInterval` de 33 ms de respaldo corre siempre (CPU baja, pero constante).
- **`ui/server.py` (313 líneas).** Rutas con validación: `_run_dir` rechaza `/ \ ..` (probado → 400), `files()`
  idem, `api_thumb` exige firma PNG y ≤ 500 KB (probado → 400). `limit` sin tope (`-1` devuelve 9) y `project` acepta
  cualquier ruta `.cft` (por diseño; local). `api_run` traga `CFturboBusy` en el hilo y ya ha devuelto `started:true`:
  si se pierde la carrera, el usuario ve «Corriendo…» hasta el siguiente sondeo sin explicación. El chat lee `stderr`
  solo al final (`p.stderr.read()`): con mucha salida de error la tubería puede bloquear a la CLI. `p.kill()` mata
  `claude.exe` pero no sus hijos (`mcp_server.py` → `CFturbo.exe`); el candado lo tiene el PID del MCP, así que no
  queda inconsistente, pero una corrida en curso termina huérfana. Un chat por servidor (`CHAT_LOCK`), coherente.
- **`mcp_server.py`.** Candado atómico (`open("x")`), PID vivo con `OpenProcess` (bien evitado `os.kill`), caducidad
  40 min, limpieza de candados muertos; selftest cubre vivo/muerto, miniatura, summary y `saved_from`. Límite: ver D-N2.
  `list_runs` relee todos los `run.json` cada 3 s (11 archivos, fino; con cientos de versiones habría que cachear por
  mtime).

## 4. Observaciones de diseño (rúbrica)

- **Jerarquía visual (8/10).** Ahora sí: visor 780×536 protagonista, runbar que nombra la corrida activa, propiedades a
  la derecha con Ejecutar siempre a la vista, dock debajo. El nombre truncado del runbar (D-N3) resta.
- **Layout sin desperdicio (8/10).** Sin scroll de página a 1400×900; solo galería, propiedades y dock hacen scroll.
  A 1920 la columna de propiedades deja 350 px vacíos bajo Opciones (podría subir el pie o mostrar ahí los hitos).
- **Consistencia (7/10).** Tokens, tags y chips coherentes; tipografía mono para números. Inconsistencias: punto vs
  coma decimal, `runmsg` verde con avisos, tags del runbar partidos en dos líneas, mensajes de CFturbo en inglés
  (inevitable) pero ahora con prefijo «Error:/Aviso:» en español.
- **Descubribilidad (7/10).** «Partir de» segmentado con el nombre, Opciones con contador, tooltips en todo lo
  deshabilitado, texto de ayuda en el visor con atajos, «Qué hacer» ante errores. Falta: nada indica que la miniatura
  se genera «al abrir» salvo el texto gris; el chip ⇄ solo aparece al pasar el ratón; AutoUpdate persistente (D-N5).
- **Responsive (8/10).** ≥ 1100 tres columnas con breakpoints reales (240/320, 280/340, 320/380); < 1100 apilado
  limpio y usable. Resta por el solape de la galería en ambos modos de escritorio (D-N1) y «e…» a 1150.
- **Visor protagonista (9/10).** Grande, encuadre y vistas, ayuda contextual, estados vacíos específicos con enlace,
  resumen flotante de avisos. Falta solo `aria-pressed` en las vistas.
- **Retroalimentación (8/10).** Botón, header, runbar, tarjeta y toasts hablan el mismo idioma y cuentan segundos;
  Detener confirma; «Claude trabajando» visible. Contador erróneo con candado externo (D-N4) y «Reintento en N s» estático.
- **Accesibilidad (8/10).** Foco visible propio, roles ARIA, `aria-live`, teclado completo en galería, pestañas,
  visor y atajos globales. 11 px en tags y hints se mantiene; cards todas con `tabindex=0` (sin roving) pero funcional.

## 5. Notas

**DISEÑO: 7/10.** El salto respecto a la línea base es grande: layout CAE sin scroll de página, visor protagonista
con encuadre y vistas, apilado correcto a 800 px, estados en español con contadores, tema claro, foco y teclado.
No llega a 9 porque la galería —la pieza nueva central— está rota en escritorio: las tarjetas se solapan y ocultan
estado, fecha y avisos (D-N1), y el nombre de la corrida activa se trunca hasta una letra a 1150 px (D-N3). Un
ingeniero nuevo tropieza con las dos en el primer minuto.

**FUNCIONALIDAD: 8/10.** Todo lo esencial funciona de verdad y se verificó: corrida real, candado compartido con el
chat (409 y botón bloqueado), Detener con mensaje, Resumen sin corridas, miniaturas automáticas que viajan con la
versión, Comparar con Δ/Δ % correctas e intercambio, guía ante AutoUpdate, reconexión con backoff, chat con recetas y
0 avisos, selftest y MCP limpios, consola a cero. Falta un punto largo por el candado que no ve otros `WORKDIR` (dos
CFturbo reales simultáneos durante la prueba, D-N2), el contador falso con candado externo (D-N4), AutoUpdate que
queda armada (D-N5) y el marcador de versión colgante (D-N6); y medio por la consola (10 errores en la caída) y los
estados 0/20 corridas que siguen sin poder probarse.

## 6. Resumen en 10 líneas

1. Probado end-to-end en 8765 con navegador real (1400 y 800), Chrome headless (5 capturas en `agents/out/eval1/`), curl, selftest y MCP stdio; no se tocó código.
2. Los 4 P1 de la ronda 0 están resueltos: layout < 1100 limpio, candado visible desde el chat (409 + botón bloqueado), Detener con «Detenido por el usuario», Resumen solo lee.
3. De los 13 P2 de la ronda 0, 12 resueltos; D16 (consola al caer) queda parcial: backoff real pero 10 errores en 40 s.
4. P0 del spec: 9 de 10 verdes; P0-7 (galería) falla visualmente: las tarjetas se solapan y tapan estado/fecha/avisos en todo escritorio (D-N1, P1).
5. P1 del spec: comparar A/B, reconexión, teclado, tema claro, dock arrastrable y sondeo ligero funcionan; P2-1/2/3 quedan para la ronda 2.
6. Corrida real 30,3 s con miniatura automática 320×240; versión `eval1_v1` con miniatura; chat creó `eval1_chat_7al` con 0 avisos en 83 s.
7. Nuevo P2 serio: el candado es por `WORKDIR`; el Explorador corrió un segundo CFturbo.exe a la vez (D-N2).
8. Otros nuevos P2: nombre del runbar truncado («e…» a 1150), contador «119 s» con candado externo, AutoUpdate queda marcada, «★ como dev1_v1» sin versión.
9. Código: sin fugas detectadas, rutas validadas, selftest amplio; debilidades en `renderActive` monolítico, errores silenciados en `selectRun`, `stderr` leído al final y `kill` sin hijos.
10. Notas: DISEÑO 7/10 · FUNCIONALIDAD 8/10. Para la ronda 2: arreglar D-N1 y D-N3 (CSS), candado global (D-N2), D-N4/5/6 y reducir el ruido de consola.
