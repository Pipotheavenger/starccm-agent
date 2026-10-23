# UX/UI · ronda 2

Autor: Diseñador UX/UI (Opus) · 2026-10-23 · Base: `eval_1.md` (DISEÑO 7/10), capturas `eval1/01…05`, código
actual de `ui/` y medidas en vivo en `http://localhost:8765` (1400×800, 1150×760, 800×900) con
`getBoundingClientRect`/`elementFromPoint`. Las dos correcciones CSS de P0 **se probaron inyectando el estilo en la
página y quitándolo después**; no se tocó código.

Prioridad: P0 = sin esto no hay 9; P1 = sube nota en su criterio; P2 = pulido. Todo es CSS/HTML/JS pequeño.

## P0-A · Galería solapada (D-N1) · consistencia, responsive, jerarquía

**Hoy:** a 1400 px `grid-template-rows` = `74 72 72 72…` px, tarjetas de 178–221 px; el tag de las 6 primeras queda
tapado por la tarjeta de abajo. **Causa:** `.card-run{overflow:hidden}` la vuelve contenedor de scroll, su altura
mínima automática pasa a 0 y, como `.gallery` tiene alto definido (flex:1) y el contenido no cabe, las pistas `auto`
se quedan en esa base. **Probado:** con lo de abajo las filas pasan a 177–221 px y `elementFromPoint` da 0 tapadas.

```css
.gallery{grid-auto-rows:max-content}
.card-run{overflow:clip}                 /* recorta igual, pero no es contenedor de scroll */
/* alturas iguales por fila: meta de 3 líneas fijas, error en 1 línea */
.card-run .meta{min-height:64px}
.card-run .errline{-webkit-line-clamp:1}
.card-run .thumb{aspect-ratio:16/10}     /* 4:3 → 16:10: tarjeta ~25 px más baja, 3 filas visibles a 800 px de alto */
```
**Acepta si:** a 1150, 1400 y 1920 px, para cada tarjeta `elementFromPoint` en el centro de su tag, fecha y ⚠
devuelve esa misma tarjeta (0 tapadas); las tarjetas de una misma fila miden igual (±1 px); ≥ 3 filas completas
visibles a 1400×900.

## P0-B · Nombre truncado en el runbar (D-N3) · jerarquía

**Hoy:** a 1150 px `#runtitle` mide 22 px con `scrollWidth` 94 («e…»): es el único hijo que flex encoge.
**Probado:** con el CSS de abajo mide 94/94 y lo que cede es `#runmeta` (139 → 66 px con «…»).

```css
.runbar .runname{flex:0 0 auto;max-width:32ch}
.runbar #runtag{display:inline-flex;gap:4px;flex:none;white-space:nowrap}
.runbar #runmeta{flex:0 1 auto;min-width:0;overflow:hidden;text-overflow:ellipsis}
.runbar #followchip,.runbar .savegrp,.runbar #openfolder{flex:none}
@media (min-width:1100px) and (max-width:1279px){
  .runbar .long{display:none}            /* «Siguiendo la última» → «Siguiendo», «Abrir carpeta» → «Carpeta» */
}
```
HTML/JS: envolver la parte larga en `<span class="long">`: `Siguiendo<span class="long"> la última</span>`,
`<span class="long">Abrir </span>carpeta`. El tag «★ como dev1_v1» pasa a «★» con `title="Guardada como dev1_v1"`
(el nombre ya está en la tarjeta ★).
**Acepta si:** a 1100, 1150 y 1400 px, con dos tags, un nombre de ≤ 24 caracteres sale entero
(`scrollWidth == clientWidth`) y el runbar sigue en una línea de 40 px.

## P1 · Espacio y jerarquía (columna de propiedades y chat vacíos)

**Hoy (05_inicio_1920):** ~430 px vacíos bajo «Opciones · 3 activas» (plegado) y ~90 px muertos en el chat vacío;
AutoUpdate queda armada sin verse (D-N5).
- `#opts` abierto por defecto si `innerHeight ≥ 820` (recordar en `localStorage` `cft_opts_open`).
- Pie de propiedades, encima del botón, una línea de resumen de lo que se va a lanzar:
  `2 cambios · desde eval1_v1 · <b class="warn">AutoUpdate activo</b>` (`#runsum`, 12 px, `--mut`; AutoUpdate
  en `--warn`). Tras lanzar, AutoUpdate se desmarca y toast «AutoUpdate desactivado tras usarlo».
- Chat vacío: el texto de ayuda centrado verticalmente y los tres botones rápidos dentro de él (no al pie).
**Acepta si:** a 1920×1080 el hueco bajo el último control de `.props-scroll` es < 120 px; con AutoUpdate marcada
el pie lo dice sin abrir Opciones; tras una corrida `#autoupd.checked === false`.

## P1 · Consistencia

| Hoy | Cambio | Acepta si |
|---|---|---|
| Placeholders «206.3», tabla «206,3» | placeholders con `toLocaleString('es-ES',{maximumFractionDigits:3})`; el input acepta coma y punto | 0 números con punto en `#params` |
| `#runmsg` verde con avisos | clases `ok/warn/err` según estado | corrida con avisos → color `--warn` |
| Filtro «Con avisos» incluye errores | chips: `Todas 11 · ★ Versiones 3 · Temporales 8 · Avisos 5 · Error 3` (cuenta dentro del chip, `.badge`) | suma de Avisos+Error+OK = Temporales+Versiones |
| `---` literal en el chat | `md()` → `<hr>` | 0 `---` en `#chatlog` |
| Tamaños 11/12/13/15/16 px mezclados | escala de 3: 12 (meta, tags, th, hints), 13 (cuerpo), 15 (runname, brand) | ver accesibilidad |

## P1 · Descubribilidad

- Botón `?` en la topbar (junto a `◐`, `aria-label="Atajos de teclado"`) que abre un popover con la lista de atajos
  de CLAUDE.md; también con la tecla `?`. Cerrar con `Esc` o clic fuera.
- `⇄` de la tarjeta: visible siempre en la tarjeta activa y con foco (hoy solo al hover), con `title="Comparar
  con la activa (Ctrl+clic)"`.
- Miniatura vacía: «Sin miniatura · se crea al abrirla» (hoy «ábrela para generarla», más ambiguo).
- Nota de la galería en dos líneas: «Temporales: quedan las 8 últimas. ★ Guardar las conserva en versions/.»
  (Ctrl+clic pasa al popover de atajos.)
**Acepta si:** un usuario nuevo encuentra Comparar y los atajos sin pasar el ratón por las tarjetas.

## P1 · Responsive < 1100

**Hoy (800×900):** página de 2077 px; el chat empieza en y=1573; tarjetas de la tira de 213 px de alto.
- Tira de galería compacta: `.card-run{flex:0 0 140px}` + `.card-run .sub{display:none}` (queda miniatura 16:10,
  nombre y tag) → ~140 px de alto.
- Orden: runbar · visor · **dock** · propiedades · explorador (el chat y los hitos antes que la galería larga);
  `.dock{height:360px}`.
**Acepta si:** a 800×900 `scrollHeight ≤ 1850`, el dock empieza antes de y=1000 y no hay scroll horizontal.

## P1 · Retroalimentación

- D-N4: «Corriendo X… N s» usa `running_since` de `/api/status` (no `st.runStart`).
- Banda offline con cuenta atrás real cada segundo: «Reintento en 12 s… 11 s…».
- `selectRun` fallido → toast «No pude abrir la corrida X: <detalle>» y la tarjeta vuelve a su estado (hoy silencio).
- Mientras llega `/api/runs/{id}`: `#runbar` con `.busy` y el visor con `vmsg` «Cargando geometría…».
**Acepta si:** con candado externo creado hace 3 s el contador dice 3–4 s; caída de 30 s muestra la cuenta bajando.

## P1 · Visor

- `aria-pressed="true"` en la vista activa de `#vactions` (hoy `null` en los 4 botones, medido) y en «Encuadrar» nunca.
- `vmsg` más corto: nombre de la corrida a la izquierda; la ayuda de ratón como `title` del visor y en el popover `?`.
**Acepta si:** tras pulsar `2` solo «Axial» tiene `aria-pressed=true`.

## P1 · Accesibilidad

- **Hoy:** 89 textos visibles < 12 px (tags, badges, hints, `th`, `.files-group`, `.cmp-sec`). Subir todos a 12 px
  (`.tag,.badge,.hint,th,.files-group,.cmp-sec,.card-run .sub,.opts .note{font-size:12px}`).
- Galería con *roving tabindex*: solo la tarjeta activa `tabindex=0`, el resto `-1` (las flechas ya mueven el foco).
- Foco visible en tarjetas: `.card-run:focus-visible{outline:2px solid var(--acc);outline-offset:2px}`.
- `#vsummary` con `aria-label="1 aviso, ver detalles"`.
**Acepta si:** 0 textos < 12 px; Tab entra a la galería y sale con una sola pulsación; contraste `--mut` sobre
`--panel-2` ≥ 4,5:1 en ambos temas (hoy cumple según mi cálculo: ~5,7 y ~5,0; no medido con herramienta).

## P2

Superponer B en alambre (P2-1), botón «Recapturar miniatura» en el menú de la tarjeta (P2-2), `D-N6` mostrar
«★ como X» solo si existe la tarjeta X.

## Resumen en 8 líneas

1. Medí la UI real a 1400, 1150 y 800 px; la causa del solape de la galería es `overflow:hidden` en la tarjeta.
2. D-N1: `grid-auto-rows:max-content` + `overflow:clip` (probado en vivo: 0 tarjetas tapadas) y meta de alto fijo.
3. D-N3: nombre `flex:0 0 auto`, cede `#runmeta`; textos largos ocultos entre 1100 y 1279 (probado: «e…» → nombre entero).
4. Espacio: Opciones abiertas si hay alto, línea de resumen en el pie con «AutoUpdate activo» (cierra D-N5).
5. Consistencia: coma decimal en todo, `runmsg` por estado, filtros Avisos/Error separados con contador, `<hr>`.
6. Descubribilidad: popover `?` de atajos, `⇄` visible en la activa, textos de miniatura y nota más claros.
7. Responsive y feedback: tira compacta y dock antes del explorador a < 1100; `running_since`, cuenta atrás, error de selectRun.
8. Accesibilidad: mínimo 12 px (hoy 89 textos menores), roving tabindex, `aria-pressed` en vistas.
