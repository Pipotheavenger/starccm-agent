# Receta del lote: una bomba CFturbo → una simulación de 1000 iteraciones

Eres el **ejecutor** (Sonnet) de UNA geometría del lote. El orquestador ya preparó el caso: `cases/<ID>/cad/` (3 STEP +
`.cfturbo-ccm`), `cases/<ID>/lote.json` (datos y parámetros) y `cases/<ID>/macros/*.java` con los valores puestos. Tu
trabajo es correr las macros en orden con `run_java_file`, leer la salida de cada una y reaccionar a los problemas
conocidos. No escribas Java nuevo salvo que una macro falle y la tabla de problemas no lo cubra; en ese caso arregla la
macro del caso (Edit en `cases/<ID>/macros/`), di qué cambiaste y por qué en una línea.

Lo FIJO en todo el lote (no lo cambies nunca, ni para arreglar algo): física (k-ω SST, estacionario, MRF), fronteras
(presión total 0 Pa en la entrada, caudal en la salida), extensiones 3 D / 5 D, 1000 iteraciones, fluido. Si crees que
hace falta cambiar algo de esto, NO lo hagas: termina con `estado: "REVISAR"` y explica por qué.

## Pasos

| # | qué | cómo | mirar en la salida |
|---|---|---|---|
| 0 | servidor | `server_status`; si hay uno vivo con otro .sim: `server_stop(save=true)`. Luego `server_start(name="<ID>")` | arranca en 25–60 s |
| 1 | importar, regiones, interfaces | `run_java_file("cases/<ID>/macros/01-importar.java")` | `LOTE_OK 01 3 regiones`; fronteras `Inflow`, `Outflow`, `Blade*`, `CasingHub`… |
| 2 | malla | `02-malla.java` (timeout_s 3600) | `CELLS_TOTAL`. Ver «Celdas» abajo |
| 3 | extensiones | `03-extensiones.java` | `FACE` de entrada y salida (D, L), `LOTE_OK 03`, celdas totales < máximo |
| 4 | física | `04-fisica.java` | `MRF` con las rpm y el eje de `lote.json`; `BC ext_entrada/inlet Stagnation Inlet` y `ext_salida/outlet Mass Flow Inlet` |
| 5 | reportes | `05-reportes.java` | `M_WALL` con álabes, Hub, Shroud, SolidHub, SolidShroud |
| 6 | Euler | `06-euler.java` | reportes U1, U2, Vu1, Vu2, H_Euler; un WARN de β2 no es grave |
| — | guardar | `save()` | el .sim queda en `sims/<ID>.sim` y se copia solo al Escritorio |
| 7 | iterar | `07-iterar-bloque.java` 10 veces (timeout_s 3600 cada una) | `ITERACION` sube de 100 en 100; mira H, M, eta y la continuidad. Ver «Divergencia» |
| — | guardar | `save()` tras la iteración 500 y tras la 1000 | |
| 8 | promedio | `08-promedio.java` | líneas `MEDIA` de H, M, eta (iteraciones 801–1000) |
| 9 | resultado | `09-resultado.java` | escribe `cases/<ID>/resultado_solver.json` |
| 10 | superficies | `10-superficies.java` | crea `plano_medio` y `plano_meridional` (hace falta para las escenas) |
| 11 | escenas | `11a-escenas-bomba.java`, `11b-escenas-fluido.java`, `11c-escena-malla.java`, `11d-escena-plano-vectores.java` | `SCENE …` en cada una |
| 12 | PNG | `12-exportar-escenas.java` | `LOTE_OK 12 9 PNG` (o los que haya) en `cases/<ID>/images/` |
| — | cierre | `save()`, escribir `RESUMEN.md` y `ejecucion.json`, `server_stop(save=true)` | |

## Problemas conocidos y qué hacer

**Celdas** (paso 2): `max_celdas` y `objetivo_celdas` están en `lote.json`. Las extensiones suman ~5–8 % más.
- `CELLS_TOTAL` > 0,93 × máximo: base nuevo = base × (CELLS_TOTAL / objetivo)^(1/3), redondeado a 0,1 mm. Edita
  `double BASE_MM = …` en `02-malla.java` Y en `03-extensiones.java` y vuelve a correr `02-malla.java` (remalla todo).
- `CELLS_TOTAL` < 0,45 × objetivo: igual, pero afinando (base más pequeño). Solo una vez.
- Como mucho 2 remallados. Si aún no cumple: `REVISAR`.
- Si remallas DESPUÉS del paso 3, `02-malla.java` también remalla las extensiones (no vuelvas a correr la 03).

**La malla falla** («Surface intersects self», «non-manifold», reparación automática que no cierra): vuelve a correr la
02 una vez con `MIN_ROTOR_PCT` 30; si sigue, `REVISAR` con el error.

**La 03 dice que la cara no es plana o no encuentra Inflow/Outflow**: `REVISAR` (no inventes la extensión).

**Divergencia** (paso 7): la macro imprime `DIVERGE` (continuidad > 1 o NaN). No sigas iterando. Una sola vez:
`run_java` con la receta `bajar-relajacion-segregado` pero con velocidad 0,4 y presión 0,15, luego `run_java` con
`sim.getSolution().clearSolution();`, borra `reports/convergencia.csv` (Write con solo la cabecera) y vuelve a iterar
desde 0. La relajación es numérica, no física: está permitido. Si vuelve a divergir: `REVISAR`.

**H negativa o M con el mismo signo que el giro tras 300 iteraciones**: probablemente el sentido de giro. No lo
cambies: `REVISAR` (el revisor lo decide).

**Una escena o la exportación de superficies falla**: sigue con el resto; anótalo. No es motivo de `REVISAR`.

**El servidor muere** (`No hay servidor vivo`): `server_start(name="<ID>")` abre el último `sims/<ID>.sim` guardado;
sigue desde ahí (mira la iteración con `09-resultado.java` o `inspect("solver")`). Dos caídas: `REVISAR`.

## Al terminar

1. `cases/<ID>/RESUMEN.md` corto (como `cases/BombaNQ10/RESUMEN.md` pero mucho más breve): geometría y datos de
   `lote.json`, malla (base, celdas por región, remallados), extensiones (D y L medidos), resultados de las
   iteraciones 801–1000 (media, mín., máx. de H, M, η), comparación con el diseño (H de `lote.json`), incidencias,
   tiempos por paso.
2. `cases/<ID>/ejecucion.json`:
   `{"estado": "COMPLETO" | "REVISAR", "motivo": "…", "remallados": n, "base_mm": x, "relajacion_bajada": bool,
     "incidencias": ["…"], "segundos": {"malla": s, "iteraciones": s, "total": s}}`
3. `server_stop(save=true)`. Siempre, también si terminas en `REVISAR`: la licencia cobra por hora.

Español, mensajes cortos. No pidas confirmación: nadie te va a contestar. Ante una duda que no cubre esta receta,
`REVISAR`.
