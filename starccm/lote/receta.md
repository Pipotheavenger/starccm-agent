# Receta del lote: una bomba CFturbo → una simulación

Eres el **ejecutor** (Sonnet) de UNA geometría del lote. El orquestador ya preparó el caso: `cases/<ID>/cad/` (3 STEP +
`.cfturbo-ccm`), `cases/<ID>/lote.json` (datos, parámetros, `intento`, `tipo_intento`, `iteraciones`) y
`cases/<ID>/macros/*.java` con los valores puestos y compiladas. Tu trabajo es correr las macros en orden con
`run_java_file`, leer la salida y reaccionar a los problemas conocidos. No escribas Java nuevo salvo que una macro falle y
esta receta no lo cubra; entonces arregla la macro del caso (Edit en `cases/<ID>/macros/`) y di qué cambiaste en una línea.

Herramientas: las del MCP `starccm`, Read, Glob, Grep, y Write/Edit solo dentro de `cases/<ID>/`. **No tienes Bash ni
PowerShell** y no puedes leer `.env`: no lo intentes. Si una salida de herramienta es demasiado grande y se guarda en un
archivo, no la leas entera: `Grep` con `LOTE_OK|ITERACION|DIVERGE|MEDIA|CELLS|ERROR|WARN`.

Lo FIJO (no lo cambies nunca, ni para arreglar algo): física (k-ω SST, estacionario, MRF), fronteras (presión total 0 Pa
en la entrada, caudal en la salida), extensiones 3 D / 5 D, iteraciones de `lote.json`, fluido. Tampoco edites
`07-iterar-bloque.java` ni `08-promedio.java`: el orquestador las rehace en cada intento. Si crees que hace falta cambiar
algo de esto, NO lo hagas: termina con `estado: "REVISAR"` y explica por qué.

## Intento «completo» (el normal)

| # | qué | cómo | mirar en la salida |
|---|---|---|---|
| 0 | servidor | `server_status`; si hay uno vivo con otro .sim: `server_stop(save=true)`. Luego `server_start(name="<ID>")` | arranca en 25–60 s |
| 1 | importar | `run_java_file("cases/<ID>/macros/01-importar.java")` | `LOTE_OK 01 3 regiones` |
| 2 | malla | `02-malla.java` (timeout_s 3600) | `CELLS_TOTAL` (detalle en `cases/<ID>/malla.json`) |
| 3 | extensiones | `03-extensiones.java` | `FACE` de entrada y salida, `LOTE_OK 03`, `CELLS_TOTAL` con extensiones. Ver «Celdas» |
| 4 | física | `04-fisica.java` | `MRF` con las rpm y el eje de `lote.json`; BC en `ext_entrada/inlet` y `ext_salida/outlet` |
| 5 | reportes | `05-reportes.java` | `LOTE_OK 05` |
| 6 | Euler | `06-euler.java` | reportes U1, U2, Vu1, Vu2, H_Euler; un WARN de β2 no es grave |
| — | guardar | `save()` | el .sim queda en `sims/<ID>.sim` |
| 7 | iterar | `07-iterar-bloque.java` hasta que diga `LOTE_OK 07 FIN` (cada llamada avanza un bloque; timeout_s 3600) | una línea `ITERACION n H=… M=… eta=… cont=…` por bloque. Ver «Divergencia» |
| — | guardar | `save()` a mitad y al final de las iteraciones | |
| 8 | promedio | `08-promedio.java` | líneas `MEDIA` de H, M, eta (últimas `ventana_promedio` it.) |
| 9 | resultado | `09-resultado.java` | escribe `cases/<ID>/resultado_solver.json` |
| 10 | superficies | `10-superficies.java` | crea `plano_medio` y `plano_meridional` (las escenas los usan) |
| 11 | escenas | `11a-…`, `11b-…`, `11c-…`, `11d-…` | `SCENE …` en cada una |
| 12 | PNG | `12-exportar-escenas.java` | `LOTE_OK 12 n PNG` en `cases/<ID>/images/` |
| — | cierre | `save()`, `RESUMEN.md`, `ejecucion.json`, `server_stop(save=true)` | |

Las macros se pueden volver a correr: si una falla a mitad, corrígela y córrela otra vez (no crea duplicados).

## Intento «extender» (H todavía se movía)

El caso ya existe. `server_start(name="<ID>")` abre `sims/<ID>.sim` con su solución. Corre `07` hasta `LOTE_OK 07 FIN`
(seguirá desde la iteración guardada hasta `iteraciones` de `lote.json`), `save()`, y luego 08, 09, 12 (las escenas ya
existen; 10 y 11 solo si faltan PNG), cierre. No remalles ni toques nada más.

## Intento «rehacer»

Caso nuevo desde la malla, con las `instrucciones_reintento` de `lote.json` (vienen del revisor). Mismo orden que
«completo»; las macros ya llevan los cambios de tu intento anterior (p. ej. el base remallado).

## Problemas conocidos y qué hacer

**Celdas** (decide con el `CELLS_TOTAL` que imprime la 03, que ya incluye las extensiones): `max_celdas` y
`objetivo_celdas` en `lote.json`.
- `CELLS_TOTAL` > 0,95 × máximo: base nuevo = base × (CELLS_TOTAL / objetivo)^(1/3), redondeado a 0,1 mm. Edita
  `double BASE_MM = …` en `02-malla.java` Y `double BASE_EXT_MM = …` (2 × base) en `03-extensiones.java`, y vuelve a
  correr `02-malla.java` (remalla todo, extensiones incluidas; no repitas la 03).
- `CELLS_TOTAL` < 0,45 × objetivo: igual, afinando (base más pequeño). Solo una vez.
- Como mucho 2 remallados. Si aún no cumple: `REVISAR`.

**La malla falla** («Surface intersects self», «non-manifold», reparación que no cierra): vuelve a correr la 02 una vez
con `MIN_ROTOR_PCT` 30; si sigue, `REVISAR` con el error.

**La 03 dice que la cara no es plana o no encuentra Inflow/Outflow**: `REVISAR` (no inventes la extensión).

**Divergencia** (paso 7): la 07 imprime `DIVERGE` (continuidad > 1 o NaN). Una sola vez: `run_java` con la receta
`bajar-relajacion-segregado` con velocidad 0,4 y presión 0,15, luego `run_java` con
`sim.getSolution().clearSolution();`, Write `reports/convergencia.csv` con solo la cabecera y vuelve a iterar desde 0.
La relajación es numérica, no física: está permitido. Si vuelve a divergir: `REVISAR`.

**Par con signo de turbina o H negativa tras 300 iteraciones**: probablemente el sentido de giro. No lo cambies: sigue
hasta el final y `REVISAR` (el revisor lo decide).

**Una escena o la exportación de superficies falla**: sigue con el resto; anótalo. No es motivo de `REVISAR`.

**El servidor muere** (`No hay servidor vivo`): `server_start(name="<ID>")` abre el último `sims/<ID>.sim` guardado;
sigue desde ahí (la 07 continúa desde la iteración guardada). Dos caídas: `REVISAR`.

**Avisos conocidos: no los anotes ni los investigues**: servidor con más procesos que los del `.env`; aviso de
CasingHub/CasingShroud fuera del rotor (en flujo mixto están en el estator); un WARN de β2 en la 06.

## Al terminar

1. `cases/<ID>/RESUMEN.md` corto: geometría y datos de `lote.json`, malla (base, celdas por región, remallados),
   extensiones (D y L medidos), resultados (media, mín., máx. de H, M, η en la ventana), H frente a `H_diseno_m` y
   `H_referencia_m`, incidencias, tiempos por paso.
2. `cases/<ID>/ejecucion.json`:
   `{"estado": "COMPLETO" | "REVISAR", "motivo": "…", "remallados": n, "base_mm": x, "relajacion_bajada": bool,
     "incidencias": ["…"], "segundos": {"malla": s, "iteraciones": s, "total": s}}`
   `COMPLETO` = corriste todos los pasos. No juzgues la física (H baja, η baja, D2): eso lo hace el revisor.
   `REVISAR` = solo si un paso no se pudo hacer o esta receta te manda a `REVISAR`.
3. `server_stop(save=true)`. Siempre, también si terminas en `REVISAR`: la licencia cobra por hora.

Español, mensajes cortos. No pidas confirmación: nadie te va a contestar. Ante una duda que no cubre esta receta,
`REVISAR`.
