# recipes (CFturbo)

Memoria del agente. Un `.md` por receta; la primera línea dice qué logra (es lo que devuelve
`cft_recipe_search` como `head`). Se escriben con `cft_recipe_save(name, body)`.

`cft_recipe_search(query)` busca por palabras (> 2 letras) en todos los `.md` de esta carpeta,
incluida la bitácora, y ordena por número de palabras coincidentes (top 10, con `score`, `head` y
`snippet`). Consultarla antes de proponer un diseño; guardar receta cada vez que algo funcione o se
resuelva un aviso nuevo.

## Bitácora automática: `bitacora.md`

No se edita a mano. `mcp_server._bitacora` añade una línea por cada corrida que no termina en
error, por cada versión guardada (`VERSIÓN GUARDADA versions/<nombre>`) y por cada versión borrada
(`VERSIÓN BORRADA versions/<nombre>`):
fecha | nombre | base | pedido (edits) | quedó (d2, b2, nBl, Psi) | estado (n avisos) | correcciones.
Los selftest no escriben en ella.

## Regla de avisos

Los avisos de geometría se corrigen sin que lo pidan, **solo en corridas que Claude lanza**; en
resúmenes y comparaciones solo se mencionan. Detalle en `regla-avisos.md` y en `../CLAUDE.md`.

## Recetas

| archivo | qué resuelve |
|---|---|
| `regla-avisos.md` | qué avisos se corrigen solos y cuáles solo se mencionan |
| `fix-extension-overlap.md` | «Extension is overlapping neighboring component» → `ext_outlet=False` (y cuándo no) |
| `fix-blade-coupling-deactivated.md` | «Coupling partially deactivated» al cambiar nBl (también al fijar β2) → `MeanSurface[Mean surface]/Coupled=False` |
| `batch-minimo-2026.md` | XML de batch mínimo que acepta CFturbo 2026.1.1 (Export + Save) |
| `exploracion-desde-cero.md` | bomba nueva para un (Q, H, n) escalando por semejanza el ejemplo más cercano en nq: procedimiento, nodos que son longitudes, bases probadas y límites. Es lo que usa `cft_new` |
| `bitacora.md` | historial automático de corridas y versiones |
