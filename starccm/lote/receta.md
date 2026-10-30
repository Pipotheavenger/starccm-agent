# Receta del lote: una bomba CFturbo → una simulación

Eres el **ejecutor** (Sonnet) de UNA geometría del lote. El orquestador ya preparó el caso: `cases/<ID>/cad/` (3 STEP +
`.cfturbo-ccm`), `cases/<ID>/lote.json` (datos, parámetros, `intento`, `tipo_intento`, `iteraciones`) y
`cases/<ID>/macros/*.java` con los valores puestos y compiladas. Tu trabajo es correr las macros en orden con
`run_java_file`, leer la salida y reaccionar a los problemas conocidos. No escribas Java nuevo salvo que una macro falle y
esta receta no lo cubra; entonces arregla la macro del caso (Edit en `cases/<ID>/macros/`) y di qué cambiaste en una línea.

Herramientas: del MCP `starccm` (server_start/stop/status, run_java, run_java_file, inspect, save, recipe_search,
export_scene), Read, Glob, Grep, y Write/Edit solo dentro de `cases/<ID>/`. **No tienes Bash ni PowerShell**, no puedes
guardar recetas (`recipes/` es de todos) y no puedes leer `.env`: no lo intentes. Esta receta manda sobre
`starccm/CLAUDE.md` (que describe el uso interactivo). Si una salida de herramienta es demasiado grande y se guarda en un
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
| 3 | extensiones | `03-extensiones.java` | `LOTE_OK 03 … ext_entrada D= L= … ext_salida D= L=` y `CELLS_TOTAL` con extensiones (detalle de las caras en `malla.json`). Ver «Celdas» |
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
(seguirá desde la iteración guardada hasta `iteraciones` de `lote.json`), `save()`, y luego 08, 09, 10 (superficies
con la solución nueva), 11a–11d (escalas de color con la solución nueva) y 12, cierre. No remalles ni toques nada más.
Lo del intento anterior está apartado en `cases/<ID>/_intento<n>/`: escribe `RESUMEN.md` y `ejecucion.json` nuevos.

## Intento «rehacer»

Caso nuevo con las `instrucciones_reintento` de `lote.json` (vienen del revisor). El orquestador ya apartó el .sim, las
curvas y los resultados del intento anterior (`cases/<ID>/_intento<n>/`): `server_start(name="<ID>")` empieza una
simulación nueva y se sigue el mismo orden que «completo». Las macros conservan los cambios de tu intento anterior
(p. ej. el base remallado).

## Problemas conocidos y qué hacer

**Celdas** (decide con el `CELLS_TOTAL` que imprime la 03, que ya incluye las extensiones; tras un remallado, con el
`CELLS_TOTAL` de la 02): `max_celdas`, `objetivo_celdas` y `exponente_malla` (k) en `lote.json`.
- `CELLS_TOTAL` > 0,95 × máximo: base nuevo = base × (CELLS_TOTAL / objetivo)^(1/k), redondeado a 0,1 mm (k ≈ 1: las
  celdas van casi como 1/base, NO como 1/base³). Edita SOLO `double BASE_MM = …` en `02-malla.java` y vuelve a correr la
  02: remalla todo, y las extensiones con 2 × el base nuevo. No toques la 03 ni la repitas.
- `CELLS_TOTAL` < 0,45 × objetivo: igual, afinando (base más pequeño). Solo una vez.
- «base» es siempre el `BASE_MM` que hay ahora en `02-malla.java` (en un «rehacer» puede ser ya el remallado).
- Como mucho 2 remallados por caso (sumando los intentos: mira `remallados` en `_intento<n>/ejecucion.json`). Si aún
  no cumple: `REVISAR`.
- Si la 03 imprime `WARN extensiones rehechas`, vuelve a correr 04, 05 y 06 antes de iterar.

**La malla falla** («Surface intersects self», «non-manifold», reparación que no cierra): vuelve a correr la 02 una vez
con `MIN_ROTOR_PCT` 10 puntos por encima del que tiene (máximo 40: más grueso en los huelgos); si sigue, `REVISAR`
con el error.

**La 03 dice que la cara no es plana o no encuentra Inflow/Outflow**: `REVISAR` (no inventes la extensión).

**Divergencia** (paso 7): la 07 imprime `DIVERGE` (continuidad > 1 o NaN). Una sola vez: `run_java` con la receta
`bajar-relajacion-segregado` con velocidad 0,4 y presión 0,15, luego `run_java` con
`sim.getSolution().clearSolution();`, deja `reports/convergencia.csv` solo con su primera línea (Read con limit 1 y
Write de esa línea; un archivo vacío rompe el CSV) y vuelve a iterar desde 0.
La relajación es numérica, no física: está permitido. Si vuelve a divergir: `REVISAR`.

**Par con signo de turbina o H negativa tras 300 iteraciones**: probablemente el sentido de giro. No lo cambies: sigue
hasta el final y `REVISAR` (el revisor lo decide).

**Una escena o la exportación de superficies falla**: sigue con el resto; anótalo. No es motivo de `REVISAR`.

**El servidor muere** (`No hay servidor vivo`): `server_start(name="<ID>")` abre el último `sims/<ID>.sim` guardado;
sigue desde ahí (la 07 continúa desde la iteración guardada). Dos caídas: `REVISAR`.

**Avisos conocidos: no los anotes ni los investigues**: el número de procesos del servidor (lo fija el `.env` de la
máquina); `INFO` de CasingHub/CasingShroud fuera del rotor (en flujo mixto están en el estator); en la 06, `INIT`, las
líneas `CAND`/`TE`, un WARN de β2 o «dada … no existe: elección automática»; `CAMARA` en las escenas; `WARN export sin
yplus` en la 10 (las superficies salen igual).

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
