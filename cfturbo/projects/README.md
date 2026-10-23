# projects

Un directorio por bomba base: `projects/<nombre>/<nombre>.cft`. Aparecen en el selector de la UI, en
`cft_projects` y como candidatas de `cft_new` (si tienen impulsor).

- Hechos en la GUI de CFturbo y copiados aquí, o creados por `cft_new` / «＋ Nueva» (escalado por
  semejanza de un ejemplo de CFturbo; ver `../recipes/exploracion-desde-cero.md`).
- Un `.cft` existente nunca se modifica: `cft_run` lo copia a `%TEMP%\cfturbo-agent\<corrida>\` y
  edita la copia. `cft_new` solo crea carpetas nuevas (error 409 si el nombre ya existe).
- `primera-bomba`: copia de "primera bomba.cft" (nq ≈ 37, 227 m³/h, 70 m, 3600 rpm, agua).
