# Lecciones para el ejecutor

Reglas cortas que salen de 47 corridas (oct. 2026). Las mantiene una persona; las del revisor van a
`lecciones_revisor.md`. Si algo de aquí choca con `receta.md`, manda la receta.

- Malla: el mínimo del rotor al 25 % del base (no menos): al 10 % los huelgos de las cámaras laterales llevan a 3,8 M celdas.
- Malla: el tamaño base ya viene calculado del historial (error típico ~8 %). Remalla solo con la regla de la receta.
- Iteraciones: en nq ≤ 25 H suele seguir subiendo a la it. 1000. No lo arregles tú: el orquestador lo detecta y pide un
  intento «extender». Tú termina las iteraciones de `lote.json` y cierra.
- Continuidad plana en ~1e-2 con H oscilando ±1–2 % es normal en estas bombas (recirculación), no es divergencia.
- η baja en nq 10–15 (0,41–0,49) es válida: el par incluye la fricción de disco de las cámaras laterales.
- H muy por debajo del diseño en una variante es física de la variante: `ejecucion.json` va COMPLETO igual.
