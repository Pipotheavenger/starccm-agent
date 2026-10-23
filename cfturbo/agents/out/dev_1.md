# Programador · ronda 1

Autor: Programador (Opus) · 2026-10-23 · Rama: `worktree-agent-a947e06f7ac75627c` (worktree
`.claude/worktrees/agent-a947e06f7ac75627c`), sin push. Base: spec `agents/out/ux_1.md` + defectos de `agents/out/eval_0.md`.

## Qué se implementó

**Archivos:** `ui/index.html` (solo marcado + importmap), `ui/app.js` (módulo ES, sin build), `ui/style.css`
(la propuesta del diseñador con ajustes al final del archivo), `ui/server.py`, `mcp_server.py`.

### Spec UX
| Punto | Estado |
|---|---|
| P0-1 separar html/js/css; `/app.js` y `/style.css` servidos sin caché | hecho; todos los ids de §2.3 existen |
| P0-2 grid CAE (explorador · runbar/visor/dock · propiedades) | hecho; 1400×900: visor 780×536 (dock abierto) y 780×780 (plegado); la página no hace scroll; nada desborda en horizontal |
| P0-3 propiedades con pie fijo; filas de 28 px con símbolo + unidad y nombre largo en `title` | hecho; `#runbtn` en y=833–865 de 900; columna «Nuevo» de 102 px (input 72 px) |
| P0-4 «Partir de: Proyecto base \| <corrida>» ligado a `#fromrun` oculto | hecho; deshabilitado sin corrida, corriendo o con error (sin `_out.cft`) |
| P0-5 dock con pestañas Chat / Hitos y avisos / Archivos / Comparar, contadores, plegado, pestaña y plegado en `localStorage` | hecho; también alto arrastrable (P1-5) |
| P0-6 runbar: nombre, tag, fecha · duración, chip Siguiendo/Fijada, ★ Guardar con input en línea (Enter/Esc), Abrir carpeta; Encuadrar + Iso/Axial/Lateral | hecho; `F` deja la cámara exactamente igual que tras cargar (Δ=0) |
| P0-7 galería de tarjetas: miniatura, nombre, fecha, d2, z, tag, ★, ⚠ n, filtros, nota de retención, vacío, teclado | hecho (`role=listbox/option`, flechas, Enter = A, Ctrl+Enter = B) |
| P0-8 miniaturas 320×240: el visor renderiza a 4:3 fuera de vista y hace `POST /api/runs/{id}/thumb`; el servidor valida PNG (<500 KB, 400 si no) y lo guarda como `thumb.png`; `GET /files/{id}/thumb.png` sale como `image/png`; `list_runs` da `thumb` (mtime) para `?v=` | hecho; `save_version` lo copia con la carpeta (assert en selftest) |
| P0-9 apilado <1100 px | hecho; a 800×900 sin solapes ni scrolls anidados, visor 504 px, galería en tira horizontal, pie de Ejecutar fijo y el body reserva su alto real (ResizeObserver) para que no tape el chat |
| P0-10 estados en español, contador «Corriendo X… N s» en botón, runbar, tarjeta y topbar, barra indeterminada, toasts `aria-live` | hecho |
| P1-1 comparación A/B (Ctrl+clic o ⇄; tabla Δ y Δ % con color; avisos Solo en A / Solo en B / En ambas; Intercambiar; Quitar B / Esc; «Pedir comparación a Claude» y chip «Comparar A y B») | hecho |
| P1-2 reconexión: un solo request por intento con 3→6→12→30 s, banda «Sin conexión… Reintento en N s» + Reintentar, toast al volver | hecho; 20 s de caída = 4 errores de red en consola |
| P1-3 foco visible, teclado (Ctrl+Enter, F, 1/2/3, Esc, `` ` ``, flechas en galería y pestañas, flechas/+/− en el visor enfocado), `aria-live` | hecho |
| P1-4 tema claro/oscuro (`◐`, `localStorage`, el visor lee `--viewer-bg`) | hecho |
| P1-6 sondeo ligero `/api/runs?fields=summary` (sin eventos, geometría ni archivos; añade `n_stl`, `n_files`) | hecho: 13 KB vs 37 KB con 8 corridas; el detalle sigue en `/api/runs/{id}` |
| P2-4 «Nueva conversación» con doble clic de confirmación y `↑` recupera el último mensaje | hecho |

### Defectos de eval_0
| Defecto | Solución |
|---|---|
| D1 layout <1100 | apilado del spec (arriba) |
| D2 candado solo en memoria | `mcp_server`: `WORKDIR/running.lock` (JSON con pid, nombre, hora) creado de forma atómica en `run_batch` y borrado en `finally`; muerto si el PID no existe (en Windows se consulta con `OpenProcess`, nunca `os.kill(pid,0)`, que mata) o si tiene >40 min. `run_batch` lanza `CFturboBusy`; `/api/run` → 409 «CFturbo trabajando (nombre)»; `/api/status` da `running`, `running_name`, `running_since`; la UI deshabilita Ejecutar y muestra el nombre. Selftest cubre vivo/muerto |
| D3 Detener sin feedback | el servidor marca la parada y emite `stopped`; el chat muestra «Detenido por el usuario.» y restaura botones |
| D4 «Resumen» lanzaba corrección | `CHAT_SYSTEM`: la regla de corregir avisos solo aplica a corridas que Claude lance en esa petición; en resumen/comparación/información solo lee y ofrece corregir. Verificado: el resumen usó solo `cft_runs` |
| D5 visor vacío al abrir | al cargar se elige la última corrida con STL |
| D6 «Nuevo» de 48 px | 102 px |
| D7 selección robada | clic en tarjeta siempre fija; solo se salta a corridas temporales nuevas si se está «Siguiendo»; si está fijada, toast «Nueva corrida: X (sigues viendo Y)» |
| D8 falso «CFturbo corrigió» | `_to_si` normaliza "true"/"false" → "True"/"False" y la comparación no numérica ignora mayúsculas |
| D9 versión duplicada / pierde estado | `save_version` marca la temporal con `saved_as_version` (tarjeta atenuada «★ como X») y la versión con `saved_from`; el tag de estado (OK/Con avisos) se mantiene y ★ va aparte |
| D10 «Nuevo» no se limpia | se vacía al lanzar (los valores quedan en la columna «Corrida») |
| D11 `\_` en el chat | se des-escapan; además títulos `#` → negrita y viñetas `-` → • |
| D12 chatting invisible / ToolSearch | topbar muestra «Claude trabajando» con punto azul y la pestaña Chat un punto; el servidor oculta tools que no empiezan por `cft_` (y sus resultados) |
| D13 sin encuadre ni teclado | ver P0-6 y P1-3 |
| D14 AutoUpdate sin guía | en «Hitos y avisos», si hay errores: caja «Qué hacer» (específica para AutoUpdate) + enlace «pedir a Claude que lo corrija» |
| D15 mensajes repetidos | avisos/errores deduplicados; van en su pestaña, no empujan nada |
| D16 consola al caer el servidor | P1-2 |
| D17 nombre «v2» | por defecto `<proyecto>_<n>` (siguiente n libre), el placeholder muestra lo que se enviará |

## Qué quedó fuera y por qué
- **P2-1** (superponer B en alambre), **P2-2** (recapturar miniatura) y **P2-3** (densidad de galería): no
  imprescindibles para la rúbrica; quedan para la ronda 2.
- «Ver B en el visor» del spec se fusionó con **Intercambiar** (B pasa a ser A y se carga en el visor); tener
  los dos botones hacía lo mismo.
- Vistas Axial/Lateral asumen el eje de la bomba en z (como exporta CFturbo); `camera.up` se deja en +y
  porque OrbitControls fija su orientación al crearse.
- No probado de verdad: galería con 0 corridas (la carpeta temporal es compartida con el checkout principal;
  el estado vacío está en código) y el aviso 401 de login (la CLI está autenticada).
- La consola conserva 4 `ERR_CONNECTION_REFUSED` por una caída de 20 s: el navegador los registra siempre;
  el backoff solo los limita.

## Cómo se verificó
- `python mcp_server.py --selftest` → `selftest OK` (nuevos asserts: `thumb` en `list_runs`, modo `summary`,
  copia de `thumb.png` con la versión, `saved_as_version`/`saved_from`, `_to_si("false")`, candado vivo → `CFturboBusy`,
  candado de PID muerto → se limpia y corre).
- Servidor propio: `cfturbo\.venv\Scripts\python -m uvicorn --app-dir <worktree>\cfturbo ui.server:app --port 8766`
  (con un `.mcp.json` local, ignorado por git, que apunta al `mcp_server.py` del worktree).
- Navegador en http://localhost:8766, medidas con `getBoundingClientRect` (las capturas salen reducidas):
  - 1400×900: medidas de la tabla P0; 11 filas de 28 px; sin scroll de página; 0 errores de consola.
  - Corrida real `dev1_d2_213` (d2 213 mm, desde la base): botón «Corriendo dev1_d2_213… N s», tarjeta
    «Corriendo… N s», runbar con barra; mientras corría `/api/status` dio `running_name` y un segundo
    `POST /api/run` devolvió 409 «CFturbo trabajando (dev1_d2_213)». Terminó en 28 s con 1 aviso: toast
    «dev1_d2_213 terminó con 1 aviso», 20 superficies en el visor y `thumb.png` 320×240 (28 KB) generada sola.
  - Guardar versión `dev1_v1` desde el runbar: toast, tarjeta «★ Guardada» con miniatura, la temporal
    queda «★ como dev1_v1», chip «Fijada».
  - Comparar `dev1_v1` (A) con `v_7alabes` (B): d2 213,0 vs 206,3 → −6,7 / −3,1 %; Intercambiar invierte
    (+6,7 / +3,2 %); Esc limpia B.
  - Pestañas, plegado y pestaña persistentes tras recargar; `F` tras orbitar → Δ cámara = 0; `2` → vista axial.
  - 800×900: sin solapes entre runbar/visor/explorador/propiedades/dock, sin scrolls anidados, visor 504 px,
    Ejecutar siempre visible y el textarea del chat no queda bajo el pie fijo.
  - Chat real: «Dame un resumen de la última corrida» → `cft_runs` y respuesta en 24 s, sin `ToolSearch`
    visible y sin lanzar corridas. Detener a los 7 s → «Detenido por el usuario.», botones restaurados.
  - Caída del servidor 20 s: banda «Sin conexión… Reintento en 12 s», vuelve sola con toast, 4 errores de red.

## Recomendaciones
- Ronda 2: P2-1/P2-2/P2-3; filtro «Versiones» como galería separada si el evaluador lo pide; probar 20+
  corridas y 0 corridas con un `CFTURBO_WORKDIR` propio.
- Documentador: actualizar CLAUDE.md (candado `running.lock`, `fields=summary`, miniaturas, `ui/app.js` y
  `ui/style.css`) y añadir la lección de `os.kill(pid, 0)` en Windows.
