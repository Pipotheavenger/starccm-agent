# Documentador · ronda 1

Autor: Documentador (Opus) · 2026-10-23 · sin commits. Cada afirmación nueva se comprobó en el
código (`mcp_server.py`, `ui/server.py`, `ui/app.js`, `ui/index.html`, `ui/style.css`) y, para la
clave de acoplamiento, resolviéndola contra `projects/primera-bomba/primera-bomba.cft` (1 sola hoja,
valor `True`). `python mcp_server.py --selftest` → `selftest OK` y `ui.server` importa tras los
cambios de docstrings.

## Qué cambié

| archivo | cambio |
|---|---|
| `CLAUDE.md` | intro (la UI ya no «genera el prompt que se pega»: corre CFturbo y tiene chat); «MCP» reescrita: tabla de tools con firmas reales, todas las claves de `edits` (alias que faltaban: `rho`, `b2_d2`, `EtaH`, `volute_d_out_mm`), `ext_outlet` (borra el objeto; error si no hay `CFDSetup_RotSym`), `MeanSurface[Mean surface]/Coupled`, carpeta temporal, poda a 8, `versions/` con `saved_as_version`/`saved_from`, `running.lock`, `thumb.png`, bitácora. «Interfaz controladora» reescrita: archivos, layout de 3 columnas/apilado, pestañas, galería y filtros, Partir de, opciones, miniaturas, Comparar A/B, atajos, endpoints `/api/*`, chat (flags reales, tools ocultas, Detener, tarjeta 401). «Flujo estándar»: recipe_search primero, iterar desde `_out.cft`, guardar con `cft_save`, entregar `versions/` (no `work/`). «Reglas»: corregir avisos solo en corridas que Claude lanza; cuándo NO usar `ext_outlet`; reintento único si CFturbo ocupado. «Lecciones»: se conservan las 6 y se añaden 5 (os.kill en Windows, candado en disco, booleanos false/False, regla que lanzaba corridas en un resumen, desacople de líneas medias) |
| `PRIMER-PROMPT.md` | reescrito como guía de 1 página: arrancar, tabla de las tres formas, guardar versiones, comparar, atajos, 401, dónde quedan los archivos, nuevo proyecto base. Quité los prompts de ejemplo (la UI ya no los genera) |
| `ui/README.md` | nuevo: archivos, diagrama run.json → página, tabla de endpoints y eventos SSE, cómo añadir un parámetro (`ALIASES`/`PARAMS`) y una pestaña (`openTab`), cómo probar, `window.__cft` |
| `recipes/README.md` | qué indexa `cft_recipe_search` y cómo ordena, formato de la bitácora, regla de avisos, tabla de recetas existentes |
| `recipes/regla-avisos.md` | título y cuerpo con el alcance «solo corridas que Claude lanza»; referencia rota `fix-meanline-coupling` → `fix-blade-coupling-deactivated`; añadida la de `fix-extension-overlap` |
| `mcp_server.py` | solo texto: docstring de cabecera (WORKDIR por defecto `%TEMP%/cfturbo-agent`, no `./work`; thumb, poda, versions, running.lock, bitácora), docstring de `run_batch` y de la tool `cft_run` (carpeta temporal, `_out.cft` como `project`, alias que faltaban, cuándo no usar `ext_outlet`, clave de acoplamiento, regla limitada a corridas propias, «CFturbo ocupado») |
| `ui/server.py` | solo texto: docstring de cabecera con todos los endpoints (faltaban projects, runs, status, save, files, chat/stop) y el candado en disco |

## Inconsistencias código ↔ docs (para el evaluador)

Corregidas en docs:
1. `mcp_server.py` decía `CFTURBO_WORKDIR` default `./work`; el código usa `%TEMP%\cfturbo-agent`. CLAUDE.md (flujo paso 5) también mandaba entregar `work/<corrida>/`.
2. `regla-avisos.md` apuntaba a la receta `fix-meanline-coupling`, que no existe; la real es `fix-blade-coupling-deactivated.md`.
3. La regla de avisos en CLAUDE.md y en `regla-avisos.md` decía «siempre»; `CHAT_SYSTEM` (server.py) y dev_1 la limitan a corridas que Claude lanza. La docstring de `cft_run` seguía diciendo «siempre».
4. CLAUDE.md decía que la UI «genera el prompt que el usuario pega aquí» y que se refresca «leyendo `work/*/run.json`»: ya no.
5. Docstring de `ui/server.py` listaba 4 endpoints de 13.

Pendientes (código o datos; no los toqué):
6. **`ext_outlet` marcado por defecto en la UI** (`#extoff checked`): toda corrida desde la UI quita la extensión, también si el proyecto no tiene voluta (contradice «cuándo NO aplicarla»), y en un proyecto sin `CFDSetup_RotSym` la corrida falla con «parámetro no encontrado: ext_outlet». Sugerencia: marcarla solo si `components` incluye voluta/estator aguas abajo.
7. «Pedir a Claude» (`askbtn`) ignora las casillas de exportar; y si solo hay `ext_outlet`/AutoUpdate sin parámetros, manda el texto genérico «Revisa el proyecto base…» aunque «Partir de» sea una corrida.
8. `index.html` fija «quedan las 8 últimas» en la nota de la galería; `/api/status` ya da `keep_tmp` y no se usa.
9. `list_projects()["runs_total"]` cuenta todas las corridas temporales, no las del proyecto (no se usa en la UI).
10. `CFTURBO_WORKDIR` no aísla `versions/` (ruta fija en el repo): probar «0 corridas» con WORKDIR vacío seguirá mostrando las versiones.
11. `projects/README.md` dice que `cft_run` copia a `work/<corrida>/`; no lo edité porque AGENTES.md dice «No tocar `projects/`». Cambiar a `%TEMP%\cfturbo-agent\<corrida>\`.
12. `recipes/fix-blade-coupling-deactivated.md`: la primera línea no es un título `#` y el archivo no termina en salto de línea (inofensivo para `recipe_search`, pero distinto del resto).
13. `AGENTES.md` y `ui/README.md` dan el servidor de desarrollo con `--app-dir .` (desde `cfturbo`), CLAUDE.md con `--app-dir cfturbo` (desde la raíz); los dos son correctos, cada uno desde su carpeta.

## No verificado en vivo
Docs escritas leyendo el código; no abrí la página ni corrí CFturbo. Los atajos, eventos SSE y
endpoints se tomaron de `app.js`/`server.py` línea por línea.
