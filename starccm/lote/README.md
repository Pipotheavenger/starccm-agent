# lote/: muchas geometrías de CFturbo → una simulación de bomba cada una

`orquestador.py` recorre `Desktop\Geometrias_Prueba\G0xx_*`, una geometría a la vez (licencia PoD de una copia):

| paso | quién | qué |
|---|---|---|
| preparar | orquestador | `cases/<ID>/`: CAD (3 STEP; la extensión de CFturbo NO), `lote.json`, macros de `lote/macros/` con los valores puestos, compiladas con javac |
| ejecutar | Sonnet (`claude -p`) | `lote/receta.md`: corre las macros con `run_java_file`, remalla si se pasa de celdas, itera 1000, escenas, `RESUMEN.md` |
| chequear | orquestador | `chequeos.json`: iteraciones, celdas, balance, H/H diseño, η, oscilación de H, D2 medido vs esperado, escenas |
| revisar | Opus (`claude -p`) | `lote/revision.md`: `veredicto.json` OK / REINTENTAR (una vez) / REVISAR; lección y propuestas de robustez |
| entregar | orquestador | `<geometría>\CFD\`: `.sim`, `images\`, `reports\`, `surfaces\`, RESUMEN y JSON |
| aprender | orquestador | historial de celdas por base (tamaño base del caso siguiente) y propuestas dentro de límites; commit en git |

Fijo en todo el lote: física, fronteras, extensiones creadas en la simulación (3 D entrada, 5 D salida), 1000
iteraciones, < 2 M celdas. Lo que aprende: tamaño base, mínimo del rotor, álabes, relajación.

```
lote\iniciar_lote.cmd --solo G002,G047      piloto
lote\iniciar_lote.cmd                       todas las pendientes
.venv\Scripts\python lote\orquestador.py --estado
.venv\Scripts\python lote\orquestador.py --seco        prueba en seco (sin licencia ni modelos)
```

Avance: `lote\eventos.log` (una línea JSON por evento, la lee la sesión monitora), `lote\estado.json` y
`Geometrias_Prueba\_lote_simulacion.csv`. Parar con calma: crear `lote\PARAR`. Mientras corre, no usar el chat de la
interfaz web: hay un solo solver.
