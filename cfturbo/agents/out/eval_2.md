# Evaluación E2E · ronda 2

Fecha: 2026-10-23 07:49–08:08 · Evaluador: Director E2E (Fable) · Servidor probado: `http://localhost:8765` (preview del
orquestador, ya con el merge `a51cd7a`; comprobé que sirve `/api/poll`, `lock_file` global y `app.js`/`style.css` del
checkout). Un segundo servidor en **8767** con `CFTURBO_WORKDIR`/`CFTURBO_VERSIONS` vacíos en el scratchpad para los casos
«0 corridas», «20 corridas» y la caída del servidor (apagado al terminar).

Cómo se probó: navegador real (panel Browser de Claude Code, viewport emulado 1400×900, 1150×760, 1100×760, 1920×1080 y
800×900; `localStorage` vaciado al empezar; medidas con `getBoundingClientRect`/`elementFromPoint`/`getComputedStyle`;
consola leída al principio y al final); Chrome headless 1400×900, 1150×760, 1920×1080 y 800×2000 con perfil limpio
(`agents/out/eval2/01…04`); `curl` e `Invoke-WebRequest` para la API; `--selftest`; handshake MCP stdio con un cliente
JSON-RPC mínimo. **No me fié del informe del programador: cada punto de abajo se reprodujo.**
Corridas creadas: `eval2_bloqueada` (API, 31,2 s), `eval2_d2_2225` (UI, «222,5» con coma, 22,0 s), `eval2_autoupd_H71`
(UI, AutoUpdate, 23,5 s), `eval2_stop` (chat, interrumpida con Detener), versión `versions/eval2_v1`; candado manual
`eval2_candado_externo` (PID vivo de un `powershell -Command Start-Sleep`).

Contexto: el programador de la ronda 3 corrió CFturbo en paralelo (`dev3_b2_26` 08:02, `dev3_base_tmp` 08:03). Esperé a que
el candado se liberara antes de cada corrida mía; el candado global funcionó entre los dos (ver 1.1 D-N2). Además, a las
08:01 el panel Browser (compartido) apareció navegado a `localhost:8766` (su servidor): descarté esa medición y la repetí
en 8765. Nota propia: mi primer candado manual llevaba `t` con un epoch mal calculado (4 h viejo) y el servidor lo descartó
como caducado y lanzó la corrida `eval2_bloqueada`; con `t` correcto el candado se respeta. No es defecto del producto.

## 1. Tabla de verificación

### 1.1 Defectos de eval_1

| # | Defecto ronda 1 | Estado | Evidencia |
|---|---|---|---|
| D-N1 P1 | Galería solapada ≥ 1100 px | **OK** | `elementFromPoint` sobre nombre, fecha, d2, z, tag y ⚠ de cada tarjeta visible: **0 tapadas** a 1100 (19 puntos), 1150 (19), 1400 (34), 1920 (38) y con 20 corridas a 1400 (34). Filas del grid = alto de tarjeta (1400: 188/188, 186/186, 211/211…; `grid-auto-rows:max-content`, `overflow:clip`). `01_inicio_1400.png`, `03_inicio_1920.png` |
| D-N2 P2 | Candado por `WORKDIR` | **OK** | `lock_file` = `%TEMP%\cfturbo-agent\running.lock` en los dos servidores (8765 y 8767 con otro `WORKDIR`); la pestaña del 8767 decía «CFturbo trabajando · eval2_d2_2225» mientras corría la del 8765. Con el candado manual (PID vivo, `t` correcto): `/api/status` → `running:true, running_name:"eval2_candado_externo", running_since`; `POST /api/run` → **409**; header «CFturbo trabajando · eval2_candado_externo · 12 s», botón «Corriendo eval2_candado_externo… 12 s» deshabilitado con tooltip. Al borrar el candado, «Listo» en el siguiente sondeo |
| D-N3 P2 | Nombre truncado en el runbar | **OK** | `#runtitle` `scrollWidth == clientWidth` (86/86 y 99/99) a 1100, 1150, 1400 y 1920 con dos tags («Con avisos» + «★» con `title="Guardada como versions/eval2_v1"`); runbar 40 px, `scrollWidth−clientWidth = 0`. Cede `#runmeta` (139 → 125 a 1400, 55 a 1150, **5 a 1100** con chip «Fijada», ver D2-4) |
| D-N4 P2 | Contador falso con candado externo | **OK** | Candado creado a las 07:56:42,681; a las 07:56:54 la UI decía «12 s» y `Date.now()−running_since` = 12 s |
| D-N5 P2 | AutoUpdate queda armada | **OK** | Antes de lanzar, pie «1 cambio · desde la base · sin extensión CFD · **AutoUpdate activo**» (`b.warn`, ámbar). Al lanzar `eval2_autoupd_H71`: `#autoupd.checked === false` y toast ámbar «AutoUpdate desactivado tras usarlo…»; la corrida terminó con avisos (H 71 con AutoUpdate no rompió el meridiano) |
| D-N6 P2 | «★ como X» colgante | **OK** | `list_runs` anula `saved_as_version` si no existe `versions/X/run.json`; en la UI solo hay «★ como eval1_v1» / «★ como eval2_v1» (versiones que existen); en el 8767 con `fake_v00…02` presentes se muestran, y la temporal queda `dim`. `dev1_d2_213` ya no lo anuncia |
| D-N7 P3 | aria-pressed, cuenta atrás, coma, filtros, `---`, runmsg verde | **OK** (salvo D2-1) | Tecla `2` → solo `axial=true`; `3` → `lateral`; `F` mantiene la vista; orbitar lo limpia. Cuenta atrás real (9 → «Reintentando…» → 30 → 20 → 10). 0 números con punto en tabla, placeholders, galería, runmeta y comparar («222,5», «0,908», «30,9 s», «−12,5 / −5,6 %»). Chips «Avisos 6 · Error 3» separados. `---` → `<hr>` (2 en la respuesta real, 0 literales). `#runmsg.warn` ámbar en «eval2_autoupd_H71 terminó con 1 aviso» |
| D16 P2 | Consola al caer el servidor | **OK** | 8767 apagado a las 07:59:55; a los 60 s **4** `ERR_CONNECTION_REFUSED`, `failures:4`, banda «Sin conexión con el servidor local. Reintento en N s.» con cuenta atrás a 1 s, `#status` «Sin conexión»; un solo `/api/poll` por intento |
| P3 ronda 1 | Pendientes P2-1/2/3 | **OK** | Ver 1.2 |

### 1.2 Spec ux_2 (P0/P1/P2)

| # | Ítem | Estado | Evidencia |
|---|---|---|---|
| P0-A | Galería sin solapes, filas iguales, ≥ 3 filas a 1400×900 | OK | 0 tapadas; 3 filas completas visibles (tarjetas 188/186/211 px en galería de 562 px) |
| P0-B | Nombre entero, runbar 40 px, `.long` oculto 1100–1279 | OK | A 1150: «Siguiendo», «carpeta», «↻» (`02_inicio_1150.png`); a 1400: «Siguiendo la última», «Abrir carpeta», «↻ Miniatura» |
| P1 espacio | Opciones abiertas si alto ≥ 820; pie con resumen; chat vacío centrado | OK | 1400×900 y 1920×1080: `#opts.open`; `#runsum` presente; `.chat-empty` con `#quick` dentro y `hidden` al primer mensaje (los botones pasan al pie). A 1920 el pie sube bajo Opciones (hueco 0 px) y quedan **214 px vacíos bajo el pie** (ver observaciones) |
| P1 consistencia | coma, runmsg por estado, filtros, `<hr>`, escala tipográfica | OK (salvo D2-1) | Ver D-N7 |
| P1 descubribilidad | popover `?`, ⇄ visible, textos de miniatura y nota | OK | Tecla `?` → popover (440×384, 10 atajos), foco en ✕; `Esc` cierra y devuelve el foco a `#helpbtn`; clic fuera cierra; botón `?` con `aria-expanded`. `.cmpbtn` opacidad 0,55 en reposo, 1 con foco/hover. «Sin miniatura · se crea al abrirla». Nota en dos líneas |
| P1 responsive < 1100 | tira 140 px, dock antes de propiedades, `scrollHeight ≤ 1850` | **parcial** | Orden runbar · visor · dock · propiedades · explorador ✓; tarjetas 140×185 sin `.sub` ✓; dock en y=545 ✓; sin scroll horizontal (785/785) ✓; `#density` oculto ✓. **Página 1909 px** con corrida seleccionada (runbar a dos líneas de 69 px + pie fijo de 105 px) — D2-2 |
| P1 feedback | `running_since`, cuenta atrás, error de `selectRun`, runbar `.busy` | OK | D-N4/D16 ✓; `.busy` durante «Cargando corrida…» y durante la corrida; banda `#selerr` con Reintentar presente en código (no se pudo provocar un 404 sin tocar datos) |
| P1 visor | `aria-pressed` solo en la vista activa, `vmsg` corto, ayuda en `title` | OK | `vmsg` «eval2_d2_2225 · Stator_1, Impeller_1, Volute_1, Volute_1 ext»; `#viewer[title]` con la ayuda de ratón |
| P1 accesibilidad | 0 textos < 12 px, roving tabindex, foco visible, `aria-label` en `#vsummary` | OK | Recorrido de todos los nodos de texto visibles: **0** por debajo de 12 px a 800/1150/1400/1920. Un solo `tabindex=0` en la galería (12 y 20 tarjetas); Home/End. `#vsummary[aria-label]`="1 aviso, ver detalles" |
| P2-1 | Superponer B en alambre | OK | Ctrl+clic en `dev3_b2_26` → pestaña «Comparar A⇄B», d2 222,5 vs 206,3 → −16,2 / −7,3 % (cian), chip «Superponer B» + casilla «B en alambre» en el visor; `groupB` 11 mallas `wireframe:true`, `opacity:0.35`, color `--cmp` del tema (#0b7368); sin extensiones ni tapas; `cft_overlay_b` guardado. `Esc` → B=null, `groupB` 0, chip y casilla desaparecen |
| P2-2 | Recapturar miniatura | OK | «↻ Miniatura» → `thumb` 1792760342 → 1792760508 → 1792760554, toast «Miniatura actualizada con la vista actual», la tarjeta cambia `?v=` |
| P2-3 | Densidad Lista/Tarjetas | OK | «Lista» → `.gallery.compact`, filas 69–72 px, 7 tarjetas visibles (vs 3 filas), fecha en `title`, `aria-pressed`, `cft_density=list` persistente; «Tarjetas» vuelve |
| Usuario | Tema claro por defecto | OK | Sin `cft_theme` y con `prefers-color-scheme: dark` emulado → `data-theme="light"`, fondo `rgb(244,246,249)`; `◐` → `dark` (`cft_theme=dark`, escena `#0b1016`) y vuelve |

### 1.3 Contraste (WCAG, texto sobre su fondo real, calculado con `getComputedStyle`)

| Elemento | Claro | Oscuro |
|---|---|---|
| `.tag.ok` / `.warn` / `.error` / `.saved` | 5,22 / 5,26 / 5,33 / 5,56 | 5,62 / 5,62 / 4,66 / 6,96 |
| Texto gris `--mut` (sec-h, hint, pinfo, status, runmeta, nqline, optsum, runsum, pestaña inactiva, chat vacío) | 6,43 | 5,99 |
| Galería: `.sub`, `.chipw`, `.errline`, badge de filtro, chip activo | 5,72 / 5,34 / 5,80 / 5,33 / 5,27 | 5,53 / 6,20 / 4,67 / 4,69 / 6,62 |
| Tarjeta `.dim` (opacidad 0,85): tag / `.sub` | **3,91 / 4,12** | **3,76** |
| Chat: `.m.bot`, `.m.user`, placeholder del textarea | 16,5 (texto) / 4,61 (placeholder) | — |
| Tabla: `th`, `td.num`, unidad gris, placeholder del input | 5,72 / 16,5 / 6,43 / 4,61 | 5,53 / 14,4 / — / **4,14** |
| Visor: `#vmsg`, `#vactions`, vista activa, `#vsummary` | 6,28 / 16,1 / 6,21 / 5,87 | 6,11 / 14,7 |
| Botón primario, chip «Siguiendo», `kbd`, popover `dt` | 6,36 / 5,27 / — | 8,37 / 6,62 / 13,3 / 5,99 |

Todo ≥ 4,5 salvo la tarjeta atenuada `.dim` y el placeholder del tema oscuro (D2-6).

### 1.4 Rúbrica de funcionalidad

| Función | Estado | Evidencia |
|---|---|---|
| Selector de proyecto e info | OK | «Pump · Stator + Impeller + Volute · Water (20°C)», «nq 37,4 · radial normal» |
| Tabla base/corrida/nuevo, nq en vivo | OK | H 71 → «nq nuevo 37,0 · radial normal»; «Partir de» corrida → columna `eval2_d2_2225` con d2 222,5 en ámbar; valor «222,5» con coma aceptado (`parseNum`), fila `.edited`, «Limpiar cambios» habilitado |
| Ejecutar real | OK | `eval2_d2_2225` 22,0 s, `realized d2_mm=0.2225`, `ext_outlet=False`, 26 archivos, 20 STL, miniatura automática; botón/header/tarjeta «Corriendo… 4 s»; «Nuevo» y nombre vaciados; `segrun` y Guardar deshabilitados con tooltip mientras corre; toast + `runmsg` al terminar |
| Partir de corrida | OK | Cuerpo de «Pedir a Claude» capturado (fetch interceptado): `project = "…\eval2_d2_2225_20261023-075837\eval2_d2_2225_out.cft"`, «Número de álabes = 7», `exports=["StarCCM","OpenFOAM"]`, sin `ext_outlet` porque el origen ya la quitó (casilla desmarcada) |
| AutoUpdate y ext_outlet | OK | D-N5; `ext_outlet=False` por defecto desde la base (`cfd_ext_outlet:true`) |
| Hitos, avisos, correcciones | OK | «Aviso: BatchMode: … Coupling partially deactivated…» deduplicado, badge «1» ámbar, `#vsummary` «1 aviso → ver» abre la pestaña |
| Archivos: descarga y Abrir carpeta | OK | `bfiles` 26; `/files/{id}/..%5Crun.json` → 400; `/api/runs/..%5C..%5Cx` → 400 |
| Guardar versión y galería | OK | Enter en el nombre en línea → «Guardada en versions/eval2_v1», tarjeta ★ «Con avisos, ★ Guardada», temporal «★ como eval2_v1» atenuada, chip «Fijada · volver a la última», «Listo · 7 corridas · 4 versiones»; `versions/eval2_v1/{run.json,thumb.png}` con `saved_from`; nombre repetido → 409 «ya existe versions/eval1_v1» |
| Visor | OK | 20 superficies, piezas por componente, tapas, Encuadrar (`F` tras mover la cámara 50 unidades), Iso/Axial/Lateral (dirección (0,0,1) y (1,0,0)), `` ` `` pliega (visor 536 → 780) y se recuerda |
| Chat real: resumen | OK | «Resumen» → solo `cft_runs{limit:1}`, 3 turnos, 27 s, 3 tablas y 2 `<hr>`, sin `\_` ni `---`; header «Claude trabajando», punto azul en la pestaña, `chatstate` «ejecutando cft_runs… 12 s» → «listo · 3 turnos · 27 s» |
| Detener chat | **OK** | Chat lanzó `cft_run eval2_stop` (candado 08:04:09, `CFturbo.exe` PID 13388). Detener a las 08:04:22 → en 2,5 s «Detenido por el usuario.», `chatstate` «detenido», Enviar habilitado; a las 08:04:28 **sin `CFturbo.exe`, sin candado, `running:false`** y `eval2_stop` ya marcada «error · Corrida interrumpida: el proceso que la lanzó terminó» (hito «Corrida interrumpida»); tarjeta roja «✕ Sin geometría» |
| Nueva conversación | OK (código + ronda 1) | Doble clic armado; no repetido |
| Estados de error | OK | 409 → «CFturbo está ocupado (X). Espera a que termine.» (código) y botón bloqueado (verificado); 404 proyecto → `No encuentro el proyecto 'noexiste' …`; thumb no-PNG → 400; `limit` acotado (−1 → 1, 9999 → todas); sin login: solo código (`loginCard`), la CLI está logueada |
| Selftest | OK | `selftest OK` en 2,2 s (candado global con otro WORKDIR, huérfana → interrumpida, `saved_as_version` colgante, `cfd_ext_outlet`) |
| MCP stdio | OK | `initialize` 2024-11-05, 10 tools `cft_*`, `cft_nq(120,30,1450)` → nq 20,7, `cft_runs` responde; 0,9 s |
| Consola | OK | Pestaña principal: 0 mensajes nuevos en 20 min (corridas, chat, comparar, tema, 5 anchos); solo quedaban 2 `ERR_CONNECTION_REFUSED` anteriores a mi sesión |
| 0 corridas | OK | 8767 vacío: «Listo · 0 corridas · 0 versiones», chips a 0, «Aún no hay corridas. Cambia un parámetro y pulsa «Ejecutar en CFturbo», o pídeselo a Claude en el chat.», visor «Sin geometría…», «Ninguna corrida seleccionada», Guardar/Corrida deshabilitados, placeholder `primera-bomba_1` |
| 20 corridas | OK | 14 temporales + 6 versiones falsas: «(20) · 6 ★», chips 20/6/14/9/2, galería con scroll propio (1984/562), página sin scroll, 0 tapadas, 1 `tabindex=0`, 3 tarjetas `dim` con «★ como fake_vNN» |
| Sondeo | OK | `/api/poll` 16,8 KB vs `/api/runs` completo 58 KB; una petición cada 3 s |

## 2. Defectos

No queda ningún P1 ni P2. Todos los nuevos son de pulido.

**D2-1 · P3 · Punto decimal en el mensaje de lanzamiento.** `runmsg` dice ««eval2_d2_2225»: Diámetro de salida d2 mm = 222.5»
aunque el usuario escribió «222,5» y toda la UI usa coma. `describeEdits` concatena el número crudo. Pista: `fmt(v, p.d)`.

**D2-2 · P3 · A 800×900 la página mide 1909 px (spec ≤ 1850).** Con una corrida seleccionada el runbar pasa a dos
líneas (69 px: «Abrir carpeta» baja) y el pie fijo mide 105 px más 12 de reserva. Reproducir: viewport 800×900, recargar.
Pista: ocultar `.long` también < 1100 y poner Nombre y botones del pie en una fila.

**D2-3 · P3 · Cabecera «PROYECTO BASE» en dos líneas a 1400.** «nq 37,4 · radial normal» no cabe junto al título en 280 px
(`01_inicio_1400.png`); a 1920 la línea «Pump · Stator + Impeller + Volute · Water (20°C)» también parte. Pista: nq en
la línea de `#pinfo` o `white-space:nowrap` + `text-overflow`.

**D2-4 · P3 · Fecha y duración invisibles en el runbar a 1100–1150 con «Fijada».** `#runmeta` queda en 5 px (1100) y 55 px
(1150): «…». La información está en el `title`, pero el usuario no ve cuándo corrió. Pista: ocultar la duración antes que
la fecha, o pasar `#runmeta` bajo el nombre en una segunda línea solo en ese rango.

**D2-5 · P3 · Miniaturas mezcladas (fondo oscuro y claro).** Las capturadas antes del tema claro por defecto siguen
oscuras y las nuevas salen claras (`03_inicio_1920.png`: `eval2_bloqueada` clara junto a `dev2_d2_216` oscura). Pista:
renderizar la miniatura con un fondo fijo independiente del tema, o un botón «regenerar todas».

**D2-6 · P3 · Contraste < 4,5 en dos sitios.** Tarjeta atenuada `.card-run.dim` (opacidad 0,85): tag 3,91 y `.sub` 4,12 en
claro, 3,76 en oscuro. Placeholder de los inputs en tema oscuro 4,14 (color por defecto del navegador). Pista: en vez de
opacidad, color `--mut` en la tarjeta; `::placeholder{color:var(--mut)}`.

**D2-7 · P3 · `api_run` puede dejar `RUN_LOCK` tomado para siempre.** Solo libera ante `FileNotFoundError` y `CFturboBusy`;
si `acquire_lock` lanza otra cosa (p.ej. `OSError` al crear `%TEMP%\cfturbo-agent`), todos los `POST /api/run` siguientes
devuelven 409 «ya hay una corrida…» hasta reiniciar. Pista: `except Exception: RUN_LOCK.release(); raise`.

**D2-8 · P3 · El dock por defecto (280 px) deja 114–144 px de chat.** Una respuesta con tres tablas se lee a trozos en un
monitor de 1080 px de alto. Pista: `--dock-h: clamp(280px, 32vh, 420px)` cuando no hay valor guardado.

## 3. Escalabilidad y estabilidad del código

- **`ui/app.js` (891 líneas).** `renderActive` partido en `renderRunbar/renderEvents/renderFiles/renderSaveBtn`; `onRuns`
  separa `notifyFinished` y `autoSelect`; `selectRun` con secuencia (`selectSeq`) y banda de error con Reintentar; sondeo
  único con `AbortController` (8 s) y `pollBusy` (nunca dos a la vez). Sin fugas nuevas: `clock` del chat se limpia,
  `pointermove/up` se quitan, `onclick` en tarjetas. `captureThumb` restaura tamaño, cámara y visibilidad en el mismo
  tick. Debilidad: `poll()` trata cualquier error (incluido un 500) como «sin conexión».
- **`ui/server.py` (348 líneas).** `api_run` toma el candado de disco antes de responder (409 real, verificado);
  `stderr` del chat en hilo con `deque(40)`; `_kill_tree` con `taskkill /T /F` (verificado: muere `CFturbo.exe`);
  `limit` acotado 1–500. Ver D2-7.
- **`mcp_server.py` (941 líneas).** `LOCK_FILE` fijo en `%TEMP%\cfturbo-agent` independiente de `WORKDIR`;
  `acquire_lock` público y atómico; `_mark_orphan` marca «interrumpida» a los 15 s sin candado (verificado en 19 s);
  `list_runs` descarta `saved_as_version` sin versión. Selftest aísla el candado (`tmp/lock`). `list_runs` sigue releyendo
  todos los `run.json` cada 3 s (11 archivos; con cientos de versiones habría que cachear por mtime).

## 4. Observaciones de diseño (rúbrica)

- **Jerarquía visual (9/10).** Visor 780×536 / 1220×716 protagonista, runbar con nombre entero y tags, propiedades con
  Ejecutar siempre a la vista y una línea que dice qué se va a lanzar. Resta la cabecera «PROYECTO BASE» partida (D2-3).
- **Layout sin desperdicio (8/10).** Sin scroll de página a 1150, 1400 y 1920; galería, propiedades y dock con scroll
  propio. A 1920 el pie sube bajo Opciones y deja 214 px vacíos al final de la columna; el chat por defecto es pequeño
  (D2-8). A 800 la página es 59 px más larga que el objetivo (D2-2).
- **Consistencia (9/10).** Coma decimal en todo lo medido salvo `runmsg` (D2-1); `runmsg`/toast/tag/badge con el mismo
  color por estado; escala 12/13/15; tags en una línea. Miniaturas de dos fondos (D2-5).
- **Descubribilidad (9/10).** `?` con todos los atajos, ⇄ visible en reposo, «Sin miniatura · se crea al abrirla»,
  «Partir de» con el nombre, resumen del pie con «AutoUpdate activo», tooltips en todo lo deshabilitado, «Qué hacer» ante
  errores. Un ingeniero nuevo no necesita el README para lanzar, comparar y guardar.
- **Responsive (9/10).** 1100/1150/1400/1920 sin solapes ni truncados; < 1100 apilado con el dock antes que la galería, tira
  compacta y pie fijo. Resta D2-2 y D2-4.
- **Visor protagonista (10/10).** Encuadre, vistas con `aria-pressed`, B en alambre, recaptura de miniatura, estados vacíos
  con enlace, resumen de avisos, ayuda en `title`.
- **Retroalimentación (9/10).** Botón, header, runbar, tarjeta y toasts cuentan los mismos segundos desde `running_since`;
  cuenta atrás de reconexión; «Detenido por el usuario» y corrida «interrumpida»; `.busy` al cargar. Sin fallos medidos.
- **Accesibilidad (9/10).** 0 textos < 12 px, contraste ≥ 4,5 en claro y oscuro salvo D2-6, roving tabindex, foco visible,
  `aria-live`, `aria-pressed` en vistas/filtros/densidad/segmento, popover con gestión de foco y `Esc`.

## 5. Notas

**DISEÑO: 9/10.** Los dos tropiezos de la ronda 1 (galería solapada, nombre «e…») están resueltos y medidos a cinco
anchos; el tema claro por defecto cumple contraste en lo que importa (tags, gris, chat, galería, tabla, visor); 12 px
mínimo, atajos descubribles con `?`, densidad, B en alambre y recaptura. Lo que queda son ocho detalles P3 (punto en un
mensaje, 59 px de más a 800, cabecera partida, meta oculta a 1100, miniaturas de dos fondos, `.dim` a 3,9, chat
pequeño) que un ingeniero nuevo nota pero no le impiden usarlo sin ayuda. No es 10 porque se notan.

**FUNCIONALIDAD: 9/10.** Todo lo de la rúbrica funciona de verdad y se reprodujo: candado global entre servidores y
agentes (409, header, contador correcto, liberación), Detener que mata `CFturbo.exe` y marca la corrida interrumpida en
≤ 19 s, AutoUpdate que se desarma con aviso, «★ como X» solo con versión real, reconexión con 4 errores y cuenta atrás,
0 y 20 corridas, corrida real con coma, versión con miniatura, chat de solo lectura y chat que lanza, comparar con
alambre, recaptura, selftest, MCP y consola a cero. Falta un punto por D2-7 (un fallo raro puede dejar el servidor en 409
permanente), por el placeholder/`.dim` y porque «sin login» y el 404 de `selectRun` siguen verificados solo en código.

## 6. Resumen en 10 líneas

1. Probado end-to-end en 8765 con navegador real (1100/1150/1400/1920/800), Chrome headless (4 capturas en `agents/out/eval2/`), curl, selftest y MCP stdio; 8767 aislado para 0/20 corridas y la caída. No se tocó código.
2. D-N1 cerrado: 0 tarjetas tapadas en los cinco anchos y con 20 corridas; filas iguales por fila.
3. D-N3 cerrado: nombre entero (99/99) con dos tags a 1100–1920; cede la fecha (a 1100 con «Fijada» queda en 5 px, D2-4 P3).
4. D-N2 cerrado: candado en `%TEMP%\cfturbo-agent\running.lock` visto por dos servidores y por el programador de la ronda 3; candado manual con PID vivo → `running:true`, 409, botón bloqueado, contador 12 s = reloj (D-N4).
5. Detener en mitad de `cft_run eval2_stop`: en 6 s sin `CFturbo.exe` ni candado, «Detenido por el usuario», corrida «error · Corrida interrumpida».
6. D-N5/D-N6/D16/P3 cerrados: AutoUpdate se desmarca con toast, «★ como X» solo si existe, 4 errores de consola en 60 s de caída con cuenta atrás, `aria-pressed`, coma, `<hr>`, filtros Avisos/Error.
7. ux_2 completo: tema claro por defecto con contraste ≥ 4,5 (tags 5,2–5,6, gris 6,4, visor 6,3), 0 textos < 12 px, popover `?`, densidad Lista, B en alambre (11 mallas cian 0,35), recaptura, roving tabindex, chat vacío centrado.
8. Corridas reales `eval2_d2_2225` (22 s, «222,5» con coma) y `eval2_autoupd_H71`; versión `eval2_v1`; chat «Resumen» solo `cft_runs` en 27 s con 3 tablas.
9. Nuevos defectos, todos P3: punto en `runmsg`, 1909 px a 800, cabecera «PROYECTO BASE» partida, meta oculta a 1100, miniaturas de dos fondos, `.dim`/placeholder < 4,5, `RUN_LOCK` sin liberar ante excepción rara, chat de 114 px por defecto.
10. Notas: DISEÑO 9/10 · FUNCIONALIDAD 9/10. Objetivo alcanzado; para una ronda 3 de pulido: D2-1…D2-8.
