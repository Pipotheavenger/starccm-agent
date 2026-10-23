# Primer prompt para Claude Code en el PC Windows con CFturbo

Antes: corre `bootstrap.ps1`, y en CFturbo crea la plantilla batch de una bomba
(PROJECT > Batch mode/Optimization, activa parámetros, Add aliases..., guarda en
`projects\<bomba>\<bomba>.cft-batch`).

---

Lee CLAUDE.md completo.

Hoy validamos el MCP contra CFturbo real. Orden:

1. Confirma que las tools `cft_*` aparecen en esta sesión y que `$env:CFTURBO_EXE` existe.
2. `cft_params` sobre `projects\<bomba>\<bomba>.cft-batch`. Muéstrame la tabla de parámetros.
3. `cft_run` sin cambios (updates vacío) con export `General`. Debe producir un STEP y un
   `.cft-res`. Si falla, lee `cft_log` y arregla `mcp_server.py` hasta que pase. Anota en
   CLAUDE.md > Lecciones cualquier diferencia entre el XML real y lo que asume el servidor.
4. Cambia un parámetro pequeño (p.ej. número de álabes +1) y corre otra vez. Confirma que el
   STEP cambió y que `realized` refleja el cambio.
5. Pide un valor fuera de rango a propósito y confirma que `corrected` lo reporta.
6. Exporta una vez con `StarCCM` y dime qué archivos genera; esos son los que irán a la MV.
7. Guarda una receta con lo que aprendiste del formato del batch de esta versión.

Reglas de hoy: antes de tocar código corre el selftest; cada paso termina con dos líneas de
estado; no me preguntes salvo bloqueo.

---

# Segundo prompt: primer diseño guiado

---

Lee CLAUDE.md. Plantilla: `projects\<bomba>\<bomba>.cft-batch`.
Quiero esta bomba para <Q> m3/h, <H> m, <n> rpm, agua. Propón 3 variantes moviendo ángulo de
salida, número de álabes y ancho de salida con criterio de turbomáquinas, córrelas, y dame una
tabla con pedidos, realizados, Output y el STEP de cada una. Recomienda una y explica en 3 líneas.
