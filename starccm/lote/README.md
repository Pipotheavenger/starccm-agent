# lote/: muchas geometrías de CFturbo → una simulación de bomba cada una

`orquestador.py` recorre `Desktop\Geometrias_Prueba\G0xx_*`, una geometría a la vez (licencia PoD de una copia; `lote\.lock`
impide dos orquestadores):

| paso | quién | qué |
|---|---|---|
| preparar | orquestador | `cases/<ID>/`: CAD (3 STEP; la extensión de CFturbo NO), `lote.json` (incl. `H_referencia_m` de la curva de CFturbo), macros de `lote/macros/` con los valores puestos, compiladas con javac. Tamaño base por regresión sobre el historial de malla |
| ejecutar | Sonnet (`claude -p`) | `lote/receta.md` + `lote/lecciones.md`: corre las macros con `run_java_file`, remalla si se pasa de celdas, itera, escenas, `RESUMEN.md` |
| chequear | orquestador | `chequeos.json`: iteraciones, celdas, balance, caudal = BC, signo del par, H (base: vs diseño; variante: vs su curva), η, deriva y oscilación de H, recorte r_TE variante/base, y+, par de discos, escenas |
| extender | orquestador | si lo único que falla es que H aún se mueve: segundo intento «extender» hasta `iteraciones_extension` sin pasar por el revisor |
| revisar | Opus (`claude -p`) | `lote/revision.md`: `veredicto.json` OK (con `alertas`) / REINTENTAR (extender o rehacer, una vez) / REVISAR; lección y propuestas |
| entregar | orquestador | `<geometría>\CFD\`: `.sim`, `images\` (incl. `convergencia.png`), `reports\`, `surfaces\`, RESUMEN y JSON; borra `sims\<ID>.sim~` |
| aprender | orquestador | historial de malla, propuestas dentro de `LIMITES`, lección validada a `lecciones_revisor.md`; un commit al final del lote |

Fijo en todo el lote: física, fronteras, extensiones creadas en la simulación (3 D entrada, 5 D salida, malladas con base
doble), `iteraciones` (1000) y `iteraciones_extension` (1500, solo si H deriva) de `parametros.json`, < 2 M celdas.

```
lote\iniciar_lote.cmd --solo G002,G047                 esas, desde cero
lote\iniciar_lote.cmd                                  todas las pendientes (un caso «en curso» se retoma)
lote\iniciar_lote.cmd --estados REVISAR,ERROR_INFRA    re-correr las que estén en esos estados
lote\iniciar_lote.cmd --extender G002 --hasta 1600     reabrir el .sim y seguir iterando
.venv\Scripts\python lote\orquestador.py --consolidar        estado, CSV, _resultados_CFD.xlsx, _indice_CFD.html y curvas
.venv\Scripts\python lote\orquestador.py --limpiar-backups   borra sims\*.sim~ de los casos entregados
.venv\Scripts\python lote\orquestador.py --estado
.venv\Scripts\python lote\orquestador.py --seco              prueba en seco (sin licencia ni modelos)
```

Avance: `lote\eventos.log` (una línea JSON por evento, la lee la sesión monitora), `lote\estado.json`,
`Geometrias_Prueba\_lote_simulacion.csv`; al final `_resultados_CFD.xlsx` (resultados, base vs variantes, chequeos) e
`_indice_CFD.html`. Parar con calma: crear `lote\PARAR` (termina el intento en curso). Dos fallos de infraestructura
seguidos (cuota, red, sesión de `claude`) paran el lote solos. Mientras corre, no usar el chat de la interfaz web: hay un
solo solver.
