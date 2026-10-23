# UX/UI ronda 1 · Controlador CFturbo

Autor: Diseñador UX/UI (Opus) · 2026-10-23 · Base: `ui/index.html` (371 líneas, CSS en línea) y `ui/server.py`.
Entrega adjunta: `ui/style.css` (propuesta completa, aún no enlazada; `index.html` no se tocó).

Evidencia: medidas tomadas con el navegador sobre http://localhost:8765 (8 corridas, 1 versión) emulando
1400×900 y 800×900. Las capturas salieron reducidas por el tamaño del panel, así que las cifras son de
`getBoundingClientRect()`, que es lo que se puede verificar.

---

## 1. Diagnóstico del layout actual

Estructura hoy: cabecera (43 px) + grid de 3 columnas `360px | 1fr | 340px`. Centro = visor (1fr) + chat (340 px fijos).
Izquierda = proyecto + parámetros + opciones + Ejecutar. Derecha = hitos/avisos/guardar + archivos + tabla de corridas.

| # | Problema | Evidencia (1400×900 salvo indicación) | Efecto |
|---|---|---|---|
| D1 | **El visor no es el protagonista.** Ocupa 700×517 px, el 29 % de la pantalla. El chat le quita 340 px fijos aunque no se use. | `#viewer` 700×517, `#chat` 700×340 | La geometría, que es el resultado, se ve pequeña. |
| D2 | **Ejecutar queda bajo el pliegue.** La columna izquierda mide 933 px de contenido en 857 de alto; `#runbtn` está en y=909. | `#runbtn` y=909 > 900 | La acción principal no se ve sin hacer scroll. |
| D3 | **La tabla de parámetros parte las etiquetas.** Filas de 42 px porque «Diám. salida d2» no cabe en 81 px. | `tr` 295×42, `td` etiqueta 81 px | 11 filas × 42 = 462 px para 11 números. |
| D4 | **Las corridas son una tabla de texto al final de la columna derecha** (y=630), sin imagen. La tabla (304 px) desborda su tarjeta (290 px). Versiones y temporales mezcladas, solo distingue una ★. | `#runs` 304 > 290 | Elegir corrida, la acción más repetida, es la menos visible. No hay galería de versiones como tal. |
| D5 | **Estados sin traducir y poco visibles.** La etiqueta muestra `ok`, `warn`, `error`, `running` crudos. No hay tiempo transcurrido mientras corre. | `renderRuns()` | El usuario no sabe si falta poco o si se colgó. |
| D6 | **«Partir de la corrida seleccionada» es una casilla** perdida entre tres opciones; cambia el origen de todo y no se ve qué corrida es. | `#fromrun` | Error típico: correr desde la base creyendo que es desde la corrida. |
| D7 | **Guardar versión vive con los hitos**, lejos del visor y de la corrida que se está viendo. | `#savebtn` en `aside.r` | Poco descubrible; no está claro qué se guarda. |
| D8 | **No hay encuadre manual ni vistas.** `fit()` solo se llama al cargar. Tras orbitar no hay forma de volver. | `fit()` sin botón | Falta una función que la rúbrica pide («encuadre»). |
| D9 | **Selección fijada invisible.** `st.pinned` decide si la vista salta a la última corrida, pero no se muestra. | `poll()` | La vista «salta sola» o «no se actualiza» sin explicación. |
| D10 | **<1100 px se rompe.** `main` mantiene altura fija (857 px) con filas `auto`: la columna izquierda queda en 294 px con scroll interno de 796, y el visor (540 px) desborda su contenedor de 269 px y **se solapa con la columna derecha** (y=606). | 800×900: `aside` 294/796, `#center` 269/920, `aside.r` y=606 | Inservible en pantallas estrechas: hay scrolls anidados y secciones encima de otras. |
| D11 | **Consola sucia:** 9× `ERR_CONNECTION_REFUSED` cuando el servidor se reinicia; el sondeo de 3 s no espera más entre fallos. | `read_console_messages` | Falla el criterio «sin errores en consola». |
| D12 | **Accesibilidad:** sin foco visible propio, filas de corrida solo con clic (sin teclado), 🔧/⚠ como única señal en el chat, sin `aria-live` para estados. | — | Falla en foco y teclado. |
| D13 | **Sondeo pesado:** `/api/runs?limit=40` devuelve eventos, avisos y geometría de cada corrida cada 3 s. | `list_runs()` | Con 20 corridas y versiones crece sin límite. |

Lo que compite con el visor: el chat (340 px fijos), la columna izquierda ancha (360 px) con un formulario
largo, y la tabla de corridas, que obliga a mirar al otro extremo para cambiar de geometría.

---

## 2. Layout objetivo

La idea es copiar cómo se organiza un programa CAE: **explorador a la izquierda** (proyecto → galería de
corridas y versiones), **visor en el centro** con una barra de la corrida activa encima y un **dock con
pestañas abajo** (Chat · Hitos y avisos · Archivos · Comparar), y **propiedades a la derecha** (la nueva
corrida, con Ejecutar siempre visible). La galería toma de Pinterest las tarjetas con miniatura en grid compacto.

### 2.1 ≥ 1100 px (escritorio)

```
┌──────────────────────────────────────────────────────────────────────────────────────────────┐ 44 px
│ CFturbo Controlador   Claude decide, CFturbo construye…          ● Listo · 8 corridas   [◐]  │ topbar
├──────────────────┬───────────────────────────────────────────────────┬───────────────────────┤
│ EXPLORADOR 280   │ v6_7alabes [Con avisos] 06:34 · 5,2 s  [Siguiendo] │ PROPIEDADES 340       │ 40 px runbar
│ Proyecto base    │        [Encuadrar][Iso][Axial][Lateral] [★ Guardar][Carpeta]│ Nueva corrida  │
│ [primera-bomba ▾]├───────────────────────────────────────────────────┤ Partir de:            │
│ radial · nq 37,4 │ [■Impeller][■Volute][■ext][tapas]                 │ [Base | v6_7alabes]   │
│──────────────────│                                                   │ ┌─────┬────┬────┬───┐ │
│ Corridas (8)  1★ │                                                   │ │Q m³/h│Base│Corr│Nuevo│
│ [Todas][★][Temp] │              VISOR 3D  (1fr × 1fr)                │ │H m   │ …  │ …  │[ ]│ │
│ [Con avisos]     │              ≥ 780 × 536 con dock abierto         │ │…  28 px por fila   │ │
│ ┌──────┐┌──────┐ │              ≥ 780 × 780 con dock cerrado         │ └─────┴────┴────┴───┘ │
│ │thumb ││thumb │ │                                                   │ nq nuevo 41,2 radial  │
│ │ 4:3  ││ 4:3  │ │                                                   │ ▸ Opciones (3)        │
│ │v6 OK ││v5 ⚠2 │ │ v6_7alabes · Impeller, Volute · arrastra para orbitar │  AutoUpdate, extensión│
│ └──────┘└──────┘ ├───────────────────────────────────────────────────┤  Exportar STEP/STL    │
│ ┌──────┐┌──────┐ │ [Chat ●][Hitos y avisos 3][Archivos 7][Comparar] ▾│                       │ 36 px tabs
│ │      ││      │ │                                                   │───────────────────────│
│ └──────┘└──────┘ │   contenido de la pestaña activa                  │ Nombre [v7        ]   │ pie fijo
│ (scroll propio)  │   (alto --dock-h = 280 px, 36 px plegado,         │ [▶ Ejecutar en CFturbo]│
│ Las temporales   │    arrastrable 160 px – 60 vh)                    │ [Pedir a Claude]      │
│ se conservan 8…  │                                                   │ 3 cambios · desde base│
└──────────────────┴───────────────────────────────────────────────────┴───────────────────────┘
```

Medidas exactas (también en `ui/style.css`):

| Zona | Valor |
|---|---|
| `body` | `grid-template-rows: 44px 1fr; height: 100vh` |
| `.app` | `grid-template-columns: var(--col-l) minmax(0,1fr) var(--col-r)` |
| `.stage` (centro) | `grid-template-rows: 40px minmax(0,1fr) var(--dock-h)` |
| `--col-l / --col-r` | 1100–1279 px: **240 / 320** · 1280–1599 px: **280 / 340** · ≥1600 px: **320 / 380** |
| `--dock-h` | 280 px por defecto; 36 px plegado; arrastrable entre 160 px y 60 vh; se guarda en `localStorage` |
| Galería | 1100–1279: lista de 1 columna (miniatura 72×54 a la izquierda); ≥1280: grid de 2 columnas; ≥1600: 2 columnas más grandes |
| Propiedades | cuerpo con scroll propio + **pie fijo** (Nombre, Ejecutar, Pedir a Claude, mensaje); el pie nunca sale de pantalla |
| Scroll | solo en tres sitios: galería, cuerpo de propiedades y contenido del dock. La página no hace scroll a ≥1100 px |

Galería: **grid compacto, no masonry**. Masonry (columnas CSS) ordena de arriba abajo y rompe el orden
cronológico, que es como se lee una galería de corridas. Las tarjetas comparten miniatura 4:3; solo cambia
la altura del pie cuando hay chips de avisos (`align-items:start`).

### 2.2 < 1100 px (apilado, scroll de página)

`.stage` pasa a `display:contents` para intercalar zonas. Una sola columna, **sin scrolls anidados ni alturas fijas en `main`**:

```
┌─────────────────────────────────┐
│ topbar (se envuelve, 44+ px)    │
├─────────────────────────────────┤
│ runbar (sticky top, 2 líneas)   │  sticky
├─────────────────────────────────┤
│ VISOR  height: 56vh, min 320 px │
├─────────────────────────────────┤
│ Galería: tira horizontal        │  scroll-x con scroll-snap, tarjetas 160 px
│ [□][□][□][□] →                  │
├─────────────────────────────────┤
│ Proyecto base + Propiedades     │  tabla a ancho completo
├─────────────────────────────────┤
│ Dock con pestañas, alto 420 px  │
├─────────────────────────────────┤
│ [▶ Ejecutar] [Pedir a Claude]   │  pie FIJO abajo (position:fixed), body padding-bottom 64 px
└─────────────────────────────────┘
```

Orden: `runbar → viewer → explorer → props → dock` (via `grid-template-areas`).

### 2.3 Dónde queda cada control de hoy (no se pierde nada)

| Hoy (id) | Ahora |
|---|---|
| `#project`, `#pinfo`, `#pnq` | Explorador › Proyecto base |
| `#params` (Base/Corrida/Nuevo), `#nqnew`, `#nqtipo`, `#clear` | Propiedades › Nueva corrida (filas de 28 px, símbolo + unidad, nombre largo en `title`) |
| `#fromrun` | Control segmentado «Partir de: Base \| <corrida>» en Propiedades (la casilla se mantiene oculta como fuente de verdad) |
| `#autoupd`, `#extoff`, `#exCCM`, `#exSTL` | Propiedades › `<details>` «Opciones», con el número de opciones activas en el resumen |
| `#rname`, `#runbtn`, `#askbtn`, `#runmsg` | Pie fijo de Propiedades |
| `#viewer`, `#vtools`, `#vmsg` | Visor (sin cambios en el comportamiento) + nuevos `#vactions` (Encuadrar, Iso, Axial, Lateral) |
| `#runtitle`, `#savename`, `#savebtn`, `#openfolder` | Runbar sobre el visor |
| `#savemsg` (retención + resultado) | La nota de retención va al pie de la galería; el resultado de guardar, a un aviso flotante (`#toast`) |
| `#events`, `#msgs` | Dock › «Hitos y avisos» (con contador de avisos y errores) |
| `#files` | Dock › «Archivos» (con contador) |
| `#chat`, `#chatlog`, `.quick`, `#chattext`, `#send`, `#chatstate`, `#newchat`, `#stopchat` | Dock › «Chat» (pestaña por defecto) |
| `#runs` (tabla) | **Galería** `#gallery` (nombre, hora, d2, nBl, estado, ★ en cada tarjeta) |
| `st.pinned` (oculto) | Chip «Siguiendo la última» / «Fijada» en el runbar |
| (nuevo) | Pestaña «Comparar», filtros de galería, miniaturas, tema claro, atajos |

---

## 3. Inventario de componentes

Formato: componente → estados → texto exacto en pantalla.

### 3.1 Topbar · indicador de estado `#status`

| Estado | Visual | Texto |
|---|---|---|
| conectando | punto gris | `Conectando…` |
| listo | punto verde | `Listo · 8 corridas · 1 versión` |
| CFturbo corriendo | punto ámbar pulsante | `CFturbo trabajando · v7 · 12 s` |
| chat activo | punto azul (además del anterior) | `Claude trabajando` |
| sin conexión | punto rojo + banda roja de 28 px bajo la topbar | `Sin conexión con el servidor local. Reintento en 6 s.` · botón `Reintentar` |

### 3.2 Explorador › Proyecto base
- **Vacío** (sin `projects/`): select deshabilitado con `Sin proyectos en projects/` y la línea `Crea la bomba base en la GUI de CFturbo y guárdala en projects/<nombre>/<nombre>.cft`.
- **Cargando:** `Leyendo proyecto…` (texto en gris en `#pinfo`).
- **Listo:** `radial · Impeller + Volute · Water` y a la derecha `nq 37,4 · radial normal`.
- **Error 404:** `No pude leer el proyecto: <detalle>` en rojo.

### 3.3 Galería `#gallery` · tarjeta de corrida
Tarjeta = miniatura 4:3 + pie (nombre, hora, `d2 220,0 · z 7`, etiqueta de estado, chips de avisos).

| Estado | Miniatura | Etiqueta | Extra |
|---|---|---|---|
| corriendo | animación de carga + `Corriendo… 12 s` | `Corriendo` (azul) | va primera |
| ok | PNG | `OK` (verde) | — |
| con avisos | PNG | `Con avisos` (ámbar) | chip `⚠ 2` |
| error | icono ✕ sobre fondo rojo tenue, texto `Sin geometría` | `Error` (rojo) | 1.ª línea del error recortada a 2 líneas |
| sin STL | placeholder con iniciales `v5` | según estado | `Sin STL para el visor` |
| guardada | PNG + cinta ★ arriba a la izquierda | `Guardada` (violeta) | nombre de la versión |
| seleccionada (A) | borde azul de 2 px + `A` en esquina | — | `aria-selected=true` |
| comparada (B) | borde discontinuo cian + `B` | — | — |
| sin miniatura todavía | placeholder neutro `Sin miniatura · ábrela para generarla` | — | — |

- **Vacío (0 corridas):** `Aún no hay corridas. Cambia un parámetro y pulsa «Ejecutar en CFturbo», o pídeselo a Claude en el chat.`
- **Filtro sin resultados:** `Ninguna corrida con este filtro.` + enlace `Ver todas`.
- **Filtros (chips):** `Todas` · `★ Versiones` · `Temporales` · `Con avisos`.
- **Pie de galería:** `Las temporales se borran solas (quedan las 8 últimas). Lo guardado vive en versions/.`
- **20 corridas o más:** el grid tiene scroll propio; cabecera fija con conteo `Corridas (20) · 3 ★`.

### 3.4 Runbar (corrida activa)
- **Sin corrida:** `Ninguna corrida seleccionada`; botones deshabilitados.
- **Normal:** `v6_7alabes` · `OK` · `23 oct 06:34 · 5,2 s` · chip `Siguiendo la última` (o `Fijada · volver a la última`).
- **Corriendo:** barra de progreso indeterminada de 2 px bajo el runbar + `Corriendo · 12 s`.
- **Guardar versión** (botón): al pulsar aparece un input en línea con el nombre de la corrida ya escrito; `Enter` guarda y `Esc` cancela. Deshabilitado con tooltip: corriendo → `Espera a que termine la corrida`; error → `Una corrida con error no se puede guardar`; guardada → texto `★ Guardada` sin acción.
- **Resultado** (`#toast`, 4 s, `aria-live=polite`): `Guardada en versions/v7` · error 409 `Ya existe una versión «v7». Elige otro nombre.`
- `Abrir carpeta` → toast `Carpeta abierta en el Explorador`.

### 3.5 Visor
- **Vacío:** centro `Sin geometría. Ejecuta una corrida con STL o elige una en la galería.`
- **Cargando:** `Cargando 12/24 superficies…`.
- **Corriendo:** `CFturbo trabajando… la geometría aparecerá al terminar`.
- **Sin STL:** `Esta corrida no exportó STL. Vuelve a correrla con «Exportar STL» activado.`
- **Error:** `La corrida terminó con error; no hay geometría. Mira «Hitos y avisos».` (enlace que abre la pestaña).
- **Listo:** `v6_7alabes · Impeller, Volute · arrastra para orbitar, rueda para zoom, F para encuadrar`.
- **Resumen flotante** abajo a la derecha (`#vsummary`) cuando hay avisos: `2 avisos · 1 corrección → ver`.
- **Herramientas:** chips de componente con su color (como hoy), `Tapas in/out`, y a la derecha `Encuadrar` (F), `Iso`, `Axial`, `Lateral`.

### 3.6 Dock · pestañas
- **Chat** (por defecto): punto azul pulsante mientras Claude trabaja.
  - Bienvenida: el texto de hoy, más corto: `Escribe en lenguaje natural: «variante con 7 álabes y d2 215 mm», «resume la última corrida», «compara v1 y v2».`
  - Chips rápidos: `Resumen` · `3 variantes` · `Comparar` (mismos prompts que hoy) + `Comparar A y B` cuando hay B.
  - Estados de `#chatstate`: `Claude Code arrancando…` · `pensando…` · `ejecutando cft_run… 24 s` · `listo · 4 turnos · 38 s` · `nueva conversación` · `sesión 1a2b3c4d (continúa)`.
  - Llamadas a tools: una línea plegable `cft_run · v7 · 3 cambios` con `▸` para ver la entrada; el error lleva prefijo `Error de tool:` en texto, no solo ⚠.
  - Errores: chat ocupado → `Ya hay una conversación en curso. Espera o pulsa Detener.`; sin login → tarjeta `La CLI de Claude Code no tiene sesión. En una terminal ejecuta: claude auth login` con botón `Copiar comando`; conexión perdida → `Se cortó la conexión con el chat. Tu mensaje no se perdió:` + botón `Reenviar`.
  - `Detener` (borde rojo) solo se habilita mientras corre; `Nueva conversación` pide un segundo clic: `¿Seguro? Pulsa otra vez para borrar`.
- **Hitos y avisos:** contador `3` (ámbar si hay avisos, rojo si hay errores). Orden: errores → correcciones (`CFturbo corrigió d2: pedido 0,215 → 0,2063`) → avisos → hitos con hora. Vacío: `Esta corrida no tiene hitos.`
- **Archivos:** contador. Lista agrupada por interfaz (`STAR-CCM+`, `OpenFOAM`), enlaces de descarga, `24 STL para el visor`, botón `Abrir carpeta`. Vacío: `Esta corrida no exportó archivos.`
- **Comparar:** ver §5.3. Vacío: `Elige una segunda corrida con Ctrl+clic (o el botón ⇄ de la tarjeta) para compararla con la activa.`
- **Plegado:** solo se ven las pestañas (36 px); al hacer clic en una se despliega.

### 3.7 Propiedades › Nueva corrida
- **Partir de:** control segmentado `Proyecto base` | `<nombre de la corrida activa>`. Si no hay corrida activa, el segundo botón se deshabilita con tooltip `Selecciona una corrida en la galería`.
- **Tabla:** columnas `Parámetro | Base | Corrida | Nuevo`. Una celda «Corrida» distinta de la base va en ámbar. Si escribes en «Nuevo», la fila lleva una franja azul a la izquierda. El placeholder es el valor de origen.
- **nq nuevo:** `nq nuevo 41,2 · radial normal`, o `–` si falta Q/H/n.
- `Limpiar` → `Limpiar cambios`, deshabilitado sin cambios.
- **Opciones** (`<details>`, cerrado; el resumen dice `Opciones · 2 activas`):
  - `Recalcular d2, b2, dS desde Q/H/n (AutoUpdate)` + nota en gris `Puede romper el meridiano si el punto de diseño cambia mucho.`
  - `Quitar extensión CFD de salida (evita el solape con la voluta)` (marcada por defecto, como hoy)
  - `Exportar: [x] STEP para STAR-CCM+ [x] STL para el visor`
- **Pie fijo:** `Nombre [v7]` · `▶ Ejecutar en CFturbo` (Ctrl+Enter) · `Pedir a Claude` · resumen `3 cambios · desde la base` / `Sin cambios: solo exporta`.
  - Corriendo: el botón dice `Corriendo v7… 12 s` y se deshabilita.
  - 409: `Ya hay una corrida en marcha. Espera a que termine.`
  - 404: `No encuentro el proyecto de origen: <detalle>`.
  - Al terminar: `v7 terminó: OK` / `v7 terminó con 2 avisos` / `v7 falló: <1.ª línea>` (6 s, `aria-live`).

---

## 4. Tokens visuales

Todo vive en `ui/style.css` como variables. El modo oscuro actual se queda (mismos tonos) y el claro sale
casi gratis, porque solo cambian las variables. El fondo del visor lo lee el JS de `--viewer-bg`.

### Paleta

| Token | Oscuro | Claro | Uso |
|---|---|---|---|
| `--bg` | `#0f141a` | `#f4f6f9` | fondo de página |
| `--panel` | `#161d26` | `#ffffff` | columnas, dock |
| `--panel-2` | `#1b2430` | `#eef2f6` | tarjetas, cabeceras de tabla |
| `--field` | `#0b1016` | `#ffffff` | inputs |
| `--line` | `#263241` | `#d5dce5` | bordes |
| `--fg` | `#e6edf3` | `#14202c` | texto |
| `--mut` | `#8b9bb0` | `#5a6878` | texto secundario (contraste ≥ 4,5:1 en ambos) |
| `--acc` | `#4cc2ff` | `#0a6fb8` | primario, selección A |
| `--acc-ink` | `#04202e` | `#ffffff` | texto sobre primario |
| `--cmp` | `#2dd4bf` | `#0f8f80` | selección B / comparación |
| `--ok` `--warn` `--err` | `#3fb950` `#d29922` `#f85149` | `#1f883d` `#9a6700` `#cf222e` | estados |
| `--saved` | `#c49bff` | `#7c4dce` | versión guardada |
| `--viewer-bg` | `#0b1016` | `#e9edf2` | escena three.js |

Colores de componente en el visor: los de hoy (Impeller `#ff9e64`, Volute `#9ece6a`, Stator `#7aa2f7`, ext `#565f89`).

### Tipografía
- Sans: `system-ui, "Segoe UI", sans-serif`. Mono: `ui-monospace, Consolas, monospace` con `font-variant-numeric: tabular-nums` en todos los números.
- Escala: 11 (etiquetas, tags) · 12 (tablas, metadatos) · **13 (base)** · 15 (nombre de corrida en el runbar) · 16 (marca).
- Títulos de sección: 11 px, mayúsculas, `letter-spacing:.06em`, `--mut`, como hoy.

### Espaciado, radios, alturas
- Escala de 4: `--s1 4` · `--s2 8` · `--s3 12` · `--s4 16` · `--s5 24`.
- Radios: `--r-sm 4` (inputs, chips del visor) · `--r 6` (botones) · `--r-lg 8` (tarjetas) · `999` (tags y chips).
- Controles: 28 px de alto (`sm` 24); filas de tabla 28; topbar 44; runbar 40; pestañas 36.
- Foco: `outline: 2px solid var(--acc); outline-offset: 2px` en `:focus-visible`, en todo lo interactivo.

### Tags de estado (texto siempre en español; el color nunca va solo)

| Estado interno | Tag | Clase |
|---|---|---|
| `running` | `Corriendo` | `.tag.running` (azul, punto pulsante) |
| `ok` | `OK` | `.tag.ok` |
| `warn` | `Con avisos` | `.tag.warn` |
| `error` | `Error` | `.tag.error` |
| `saved` | `★ Guardada` | `.tag.saved` |

---

## 5. Interacciones clave

### 5.1 Cambiar parámetro → ejecutar → ver → guardar
1. El usuario escribe `d2 = 215` en «Nuevo». La fila se marca, `nq nuevo` se recalcula en vivo y el pie dice `1 cambio · desde la base`.
2. `Ctrl+Enter` o clic en **Ejecutar**. Se hace `POST /api/run` con el mismo cuerpo de hoy. El botón pasa a `Corriendo v7… 0 s` (contador local desde `started`), la galería pone primero una tarjeta `Corriendo` y el runbar salta a v7 si está «Siguiendo la última».
3. En cada sondeo, al cambiar el estado: carga el STL, encuadra, **captura la miniatura** (§5.4) y aparece el toast `v7 terminó con 2 avisos`. La pestaña «Hitos y avisos» muestra el contador; el dock **no cambia de pestaña solo** (no se le quita el chat al usuario) y el resumen flotante del visor enlaza a ella.
4. **Guardar:** clic en `★ Guardar versión` en el runbar, input en línea con `v7`, Enter. Se hace `POST /api/save` y sale el toast `Guardada en versions/v7`. La tarjeta pasa a `★ Guardada` y aparece en el filtro `Versiones`. La selección queda fijada en la versión, como hoy.

### 5.2 Chat
- `Pedir a Claude` (en Propiedades) despliega el dock si está plegado, activa la pestaña Chat y envía el prompt que ya se arma hoy.
- Mientras Claude trabaja: punto pulsante en la pestaña, `#chatstate` con la tool en curso y `Detener` habilitado. Cada `tool` con `cft_run` pone `st.pinned=false` (como hoy) y la galería muestra la tarjeta nueva.
- `Enter` envía y `Shift+Enter` hace salto de línea (como hoy). Con `↑` en el textarea vacío se recupera el último mensaje.
- Las tablas markdown de las respuestas usan el estilo de tabla del sistema, con scroll-x propio.

### 5.3 Selección y comparación (nuevo)
- **Clic** en una tarjeta = corrida activa **A** (carga el visor, la tabla y el dock). Fija la selección salvo que sea la más reciente (lógica de hoy).
- **Ctrl/⌘+clic** o el botón `⇄` que aparece al pasar el ratón (y al enfocar con teclado) = corrida **B**. Con `Esc` se quita B.
- Al elegir B, la pestaña «Comparar» muestra `A ⇄ B` y contiene:
  - Cabecera: `A v6_7alabes [OK]  ⇄  B v5 [Con avisos]` + botones `Intercambiar`, `Ver B en el visor`, `Pedir a Claude que las compare` (envía `Compara las corridas A (<id A>) y B (<id B>): parámetros, avisos y qué cambió en la geometría. Dime cuál conviene y por qué.`).
  - Tabla `Parámetro | A | B | Δ | Δ %` con los 10 parámetros, nq, duración, nº de avisos y estado. Si |Δ %| ≥ 1 se resalta (ámbar si sube, cian si baja).
  - Avisos agrupados: `Solo en A`, `Solo en B`, `En ambas`.
- P2: superponer B en el visor como malla de alambre cian semitransparente (`MeshBasicMaterial({wireframe:true, opacity:.35})` en un segundo `Group`), con el chip `Superponer B`.

### 5.4 Miniaturas por corrida
**Cliente** (después de `loadGeometry()` + `fit()`, antes de que el usuario orbite, una vez por corrida):
```js
async function captureThumb(r) {
  if (r.thumb || !st.meshes.size || !['ok', 'warn'].includes(r.status)) return;
  fit(); renderer.render(scene, camera);                       // preserveDrawingBuffer ya está en true
  const src = renderer.domElement, c = document.createElement('canvas'); c.width = 320; c.height = 240;
  const s = Math.max(320 / src.width, 240 / src.height), w = src.width * s, h = src.height * s;
  c.getContext('2d').drawImage(src, (320 - w) / 2, (240 - h) / 2, w, h);   // recorte tipo "cover" a 4:3
  const blob = await new Promise(res => c.toBlob(res, 'image/png'));
  await fetch(`/api/runs/${encodeURIComponent(r.id)}/thumb`, { method: 'POST', headers: { 'content-type': 'image/png' }, body: blob });
}
```
Se captura con la visibilidad por defecto (sin tapas ni `ext`), para que todas las miniaturas sean comparables.
Las corridas antiguas sin miniatura la generan la primera vez que se abren. Botón opcional (P2) `Recapturar miniatura` en el runbar.

**Servidor** (`ui/server.py`):
```python
from fastapi import Request

@app.post("/api/runs/{rid}/thumb")
async def api_thumb(rid: str, request: Request) -> dict:
    data = await request.body()
    if not data.startswith(b"\x89PNG\r\n\x1a\n") or len(data) > 512_000:
        raise HTTPException(400, "se espera un PNG de menos de 500 KB")
    d = _run_dir(rid)
    (d / "thumb.png").write_bytes(data)
    return {"thumb": f"/files/{rid}/thumb.png"}
```
En `mcp_server.list_runs` hay que añadir `row["thumb"] = int((d / "thumb.png").stat().st_mtime) if (d / "thumb.png").is_file() else 0`. La tarjeta pide `/files/<id>/thumb.png?v=<thumb>` (el `?v=` evita la caché). `/files/` ya sirve el archivo, pero con tipo `application/octet-stream`: hay que añadir `.png → image/png` en `files()`. `save_version` copia la carpeta, así que la miniatura viaja con la versión. Conviene añadir un assert al `--selftest`: si escribes `thumb.png` en una corrida de prueba, `list_runs` devuelve `thumb > 0`.

### 5.5 Teclado
| Tecla | Acción |
|---|---|
| `Ctrl+Enter` (fuera del chat) | Ejecutar |
| `F` (con el foco fuera de inputs) | Encuadrar |
| `1` / `2` / `3` | Vista Iso / Axial / Lateral |
| `←` `→` en la galería | mover el foco entre tarjetas; `Enter` = A, `Ctrl+Enter` = B |
| `Esc` | quitar B / cerrar el input de guardar |
| `` ` `` | plegar o desplegar el dock |

---

## 6. Lista priorizada para el programador

Se permite separar `index.html` + `app.js` + `style.css` (AGENTES.md). Hay que **conservar todos los `id` actuales**,
porque el evaluador y `window.__cft` los usan. Medir en el puerto 8766.

### P0 (esta ronda)

| # | Cambio | Criterio de aceptación verificable |
|---|---|---|
| P0-1 | Separar `ui/index.html` en `index.html` + `app.js` + `style.css` (partir del `style.css` propuesto). `server.py` sirve `/style.css` y `/app.js` (o un `StaticFiles` en `/ui`). | `index.html` no tiene `<style>` ni `<script>` en línea salvo el importmap. Todos los ids de §2.3 existen (`document.getElementById` ≠ null). `python mcp_server.py --selftest` pasa. |
| P0-2 | Grid de §2.1: topbar 44, columnas `--col-l / 1fr / --col-r` por breakpoint, `.stage` con filas `40 / 1fr / --dock-h`. | A 1400×900: `#viewer` mide ≥ 760×520 con el dock abierto y ≥ 760×760 plegado; `document.documentElement.scrollHeight ≤ 900` (la página no hace scroll); ningún panel tiene `scrollWidth > clientWidth`. |
| P0-3 | Propiedades con pie fijo. La tabla usa filas de 28 px con símbolo + unidad (`Q m³/h`, `d2 mm`, `z álabes`…) y el nombre largo va en `title`. | A 1400×900 y a 1100×700, `#runbtn.getBoundingClientRect().bottom ≤ innerHeight`. Todas las filas de `#params` miden ≤ 30 px. |
| P0-4 | Control segmentado «Partir de» ligado a `#fromrun` (la casilla queda oculta). Muestra el nombre de la corrida activa. | Al pulsar el segmento de la corrida, `#fromrun.checked === true` y el cuerpo de `/api/run` lleva `project` = `<run_dir>\<name>_out.cft`. Sin corrida activa, el segmento está deshabilitado. |
| P0-5 | Dock con pestañas Chat / Hitos y avisos / Archivos (+ Comparar vacía), plegable, con pestaña y estado guardados en `localStorage`. Contadores en las pestañas. | Clic en cada pestaña muestra solo su panel (`hidden` en los demás). Tras recargar se recuperan la pestaña y el plegado. Una corrida con 2 avisos y 1 error muestra `3` en «Hitos y avisos». |
| P0-6 | Runbar: nombre, tag en español, hora · duración, chip Siguiendo/Fijada, `★ Guardar versión` con input en línea, `Abrir carpeta`. `Encuadrar` + `Iso/Axial/Lateral` en el visor. | Guardar desde el runbar crea `versions/<nombre>/` y la tarjeta muestra `★ Guardada`. El chip cambia a `Fijada` al hacer clic en una corrida que no es la última, y al pulsarlo vuelve a seguir la última. Tras orbitar, `F` deja la cámara igual que tras la carga (mismo `camera.position` con tolerancia 1e-6). |
| P0-7 | Galería de tarjetas que sustituye a la tabla `#runs`: miniatura o placeholder, nombre, hora, d2, nBl, tag, ★, chips de avisos, filtros `Todas / Versiones / Temporales / Con avisos`, nota de retención y estado vacío. Tarjetas como `button`/`role=option` navegables con teclado. | Con 0 corridas se ve el texto de vacío. Con las 8 corridas actuales + 1 versión hay 9 tarjetas; el filtro `Versiones` deja 1 y `Con avisos` deja solo las `warn`. `Tab` llega a las tarjetas y `Enter` selecciona. |
| P0-8 | Miniaturas: `POST /api/runs/{id}/thumb`, `thumb` en `list_runs`, `image/png` en `/files`, captura en el cliente (§5.4). | Tras abrir una corrida `ok`/`warn` con STL existe `<run_dir>/thumb.png` (320×240, < 500 KB) y en el siguiente sondeo su tarjeta muestra la imagen. Un POST con bytes que no son PNG devuelve 400. Tras guardar como versión, `versions/<n>/thumb.png` existe. |
| P0-9 | Apilado < 1100 px (§2.2) sin scrolls anidados: `.stage{display:contents}`, áreas `runbar / viewer / explorer / props / dock`, pie de ejecución fijo. | A 800×900: ninguna pareja de `.runbar, #viewer, .explorer, .props, .dock` se solapa (sus rectángulos no se cruzan); `.explorer` y `.props` no tienen `scrollHeight > clientHeight`; `#viewer` mide ≥ 320 px de alto; `#runbtn` es visible en cualquier posición de scroll. |
| P0-10 | Estados en español y feedback de corrida: tags de §4, contador en el botón Ejecutar y en la tarjeta, barra de progreso indeterminada en el runbar, toasts `aria-live` al terminar. | Con una corrida en marcha, `#runbtn` dice `Corriendo <nombre>… N s` y N avanza; ninguna etiqueta visible contiene `ok`/`warn`/`running` en inglés; al terminar aparece un toast con el resultado. |

### P1 (siguiente ronda si P0 está verde)

| # | Cambio | Criterio |
|---|---|---|
| P1-1 | Comparación A/B (§5.3): Ctrl+clic / `⇄`, pestaña Comparar con tabla Δ y Δ %, avisos agrupados, Intercambiar, Pedir a Claude. | Con A=v6 y B=v5, la tabla muestra la diferencia de d2 correcta; `Intercambiar` invierte los signos; `Esc` limpia B y la pestaña vuelve al estado vacío. |
| P1-2 | Errores de conexión: sondeo con backoff (3 → 6 → 12 → 30 s) y banda `Sin conexión…` con `Reintentar`. Mensajes de 409/404 de §3.7, chat ocupado y sin login (con `Copiar comando`). | Al parar el servidor 20 s y volver a arrancarlo: ≤ 4 errores de red en consola, la banda aparece y desaparece sola y la página se recupera sin recargar. |
| P1-3 | Foco visible, teclado (§5.5), `aria-live` en `#status`, `#runmsg`, `#chatstate` y el toast; las tools del chat con prefijo textual. | Se puede elegir corrida, ejecutar y guardar solo con teclado; todo lo enfocable muestra el anillo de foco. |
| P1-4 | Tema claro: `[data-theme]` + `prefers-color-scheme`, botón `◐` en la topbar guardado en `localStorage`; el visor lee `--viewer-bg`. | Al cambiar de tema cambian la página y el fondo del visor sin recargar; el texto `--mut` tiene contraste ≥ 4,5:1 en ambos temas. |
| P1-5 | Dock redimensionable arrastrando su borde superior (160 px – 60 vh). | Al arrastrar cambia `--dock-h` y se conserva tras recargar. |
| P1-6 | `/api/runs` ligero para el sondeo: sin `events` ni `geometry` (`?fields=summary`); el detalle sigue en `/api/runs/{id}`. | Con 20 corridas, la respuesta del sondeo pesa < 30 KB. |

### P2

| # | Cambio | Criterio |
|---|---|---|
| P2-1 | Superponer B en el visor como alambre cian. | Con el chip activo se ven las dos geometrías y el encuadre las abarca. |
| P2-2 | `Recapturar miniatura` en el runbar (con la vista actual). | Reemplaza `thumb.png` y la tarjeta se actualiza (`?v=` nuevo). |
| P2-3 | Densidad de la galería (tarjetas / lista) a elección del usuario. | Se alterna y se guarda en `localStorage`. |
| P2-4 | `Nueva conversación` con confirmación en dos clics y `↑` para recuperar el último mensaje. | El primer clic cambia el texto y el segundo borra; con `↑` en el textarea vacío vuelve el último mensaje. |

---

## 7. Qué no se hizo / riesgos
- No se tocó `index.html` ni se implementó nada; `ui/style.css` es una propuesta que todavía nada enlaza.
- Las capturas a 1400/800 salieron reducidas por el tamaño del panel del navegador. Las medidas del diagnóstico son de `getBoundingClientRect` y se pueden reproducir con el mismo script.
- `.stage{display:contents}` quita el elemento del árbol de accesibilidad en navegadores antiguos. Aquí no importa (es un `section` sin rol), pero no hay que ponerle `role`.
- La miniatura depende de `preserveDrawingBuffer:true`, que ya está activo. Si se quitara por rendimiento, hay que capturar justo después de `renderer.render()` en el mismo tick.
