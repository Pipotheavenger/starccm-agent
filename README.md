# starccm-agent

Agentes de IA para turbomáquinas hidráulicas que operan software de ingeniería real desde lenguaje
natural, con Claude Code como cerebro y un servidor MCP por herramienta. Dos agentes independientes,
cada uno en su carpeta, con su `CLAUDE.md` (brief que manda), su MCP, su entorno Python y su memoria:

| carpeta | herramienta | qué hace | estado (2026-10-24) |
|---|---|---|---|
| [`starccm/`](starccm/README.md) | Simcenter STAR-CCM+ 2410 (este PC, 4 procesos), licencia PoD | prepara, malla, configura física, corre y entrega altura, torque, eficiencia y escenas de una bomba | MCP verificado contra el solver real, solo local; bomba `cursocfturbo` convergida; interfaz web completa |
| [`cfturbo/`](cfturbo/README.md) | CFturbo 2026.1 (este PC) | diseño 1D por semejanza, variantes de geometría, curvas, exportación a CFD, interfaz web con visor 3D | terminado, evaluado 9/10 |

No comparten código ni se llaman entre sí. CFturbo exporta STEP + `.cfturbo-ccm`; el agente de
STAR-CCM+ los toma como cualquier otro CAD (`starccm/cases/<caso>/cad/`).

## Cómo está construido

```
Claude Code ──MCP stdio──> <agente>/mcp_server.py ──> software (CFturbo.exe en batch | starccm+ -server)
                               │
                               ├── recipes/   snippets que ya funcionaron (memoria del agente)
                               ├── cases/ | projects/   un directorio por caso o proyecto
                               └── tests/    ejecutable falso para `python mcp_server.py --selftest`
```

Principios (de los dos `CLAUDE.md`):
- **Un archivo de MCP, sin frameworks de agentes.** Lo mínimo que funcione.
- **Memoria en archivos**: cada paso que funciona se guarda como receta; cada error que costó más de
  dos intentos deja una línea en «Lecciones» del `CLAUDE.md` correspondiente.
- **Selftest sin licencia**: cada MCP se prueba con un ejecutable falso (`tests/`).
- **Claves de licencia solo en `.env`** ignorados por git. Nunca en código, logs ni commits.
- **Mensajes al usuario en español, cortos, números en tablas.**

## starccm/ en una página

- `mcp_server.py`: 11 tools (`server_start`, `server_stop`, `server_status`, `inspect`, `run_java`,
  `iterate`, `export_scene`, `save`, `recipe_search`, `recipe_save`, `docs_search`). Un servidor de
  STAR-CCM+ vivo con el `.sim` en memoria; cada tool inyecta una macro Java por cliente batch
  (`-host localhost:47827 -batch Macro.java -noexit`), precompilada antes con el `javac` de STAR-CCM+.
  Solo local (2410 en este PC). El servidor Linux (2502) queda como opción manual: Sebastián mueve el `.sim`
  y lo corre allí (`starccm/vm/SERVIDOR.md`).
- Casos: `cases/cilindro/` (prueba de fontanería) y `cases/cursocfturbo/` (bomba centrífuga, 370 k
  celdas, 400 iteraciones, H 78,8 m, M 192,5 N·m, η 89,4 %). Cada caso tiene `RESUMEN.md`, `images/`,
  `reports/` y, el de la bomba, un guion reproducible `pump.py`.
- 25 recetas en `recipes/` (geometría, separar caras por ángulo, regiones, interfaces, malla por parte,
  MRF, fronteras, reportes, escenas, residuales, autosave, exportación de superficies a EnSight).
- `ui/`: interfaz web (FastAPI + three.js, puerto 8767, tema claro) alrededor de UNA simulación: árbol,
  visor 3D con campos, modo Fronteras (el usuario marca entrada, salida, pared…), dock con Salida,
  Gráficos en vivo y Resumen, panel de IA plegable, «＋ Caso nuevo» desde una geometría. Detalle y guía
  de punta a punta en `starccm/README.md`.
- La IA pregunta con opciones cuando duda (bloque `pregunta`, «ver», Fronteras) y el caso nuevo va por
  etapas: preparar, 100 iteraciones de prueba con resultados y confirmación antes de seguir hasta el criterio
  de parada.

Tiempos medidos (100 iteraciones de la bomba):

| dónde | segundos |
|---|---|
| Local (2410, 4 procesos) | ~82 |
| Servidor a mano (2502, 14 procesos; medido con el agente antes de retirarlo) | 41,6 |

Arranque local 4,5 s; macro 8–10 s; primera macro de CAD/física 50–75 s.

## cfturbo/ en una página

- `mcp_server.py`: 12 tools sobre `CFturbo.exe -batch` editando el `.cft` (XML) copiado.
- `ui/`: interfaz web (FastAPI + three.js, puerto 8765) con galería de corridas, visor 3D de STL,
  tabla de parámetros, chat con Claude Code por SSE, curvas, reporte y comparación.
- `projects/` (bombas base), `versions/` (corridas guardadas), `recipes/` (recetas y bitácora).

## Puesta en marcha

```bash
# STAR-CCM+ (requiere starccm/.env con STARCCM_PODKEY; ver starccm/.env.example)
starccm\.venv\Scripts\python starccm\mcp_server.py --selftest
```

```bash
# CFturbo
cfturbo\.venv\Scripts\python cfturbo\mcp_server.py --selftest
```

Los dos MCP se registran en el `.mcp.json` de esta raíz (ignorado por git; plantilla en cada
carpeta). Reiniciar la sesión de Claude Code para que aparezcan las tools.

## Hoja de ruta

1. ~~Interfaz web de `starccm/`~~ hecha (2026-10-23/24), con caso nuevo, preguntas con opciones y etapas. La ejecución remota se probó y se retiró el 2026-10-24: el agente es solo local.
2. Probar el flujo completo desde una geometría nueva (caras sin nombre → Fronteras → «Aplicar con la IA»)
   y el salto a la GUI (`/api/open_gui`).
3. Perfeccionar la bomba: malla y y+, reflujo en la salida de la voluta, comparación con la predicción 1D
   de CFturbo (84,4 m frente a 78,8 m del CFD), monitores de parada automáticos.
4. Varias simulaciones: curva H-Q de 5 caudales reusando la malla (`PRIMER-PROMPT.md`, tercer prompt) en local,
   comparación entre variantes de geometría. La PoD de una sola copia obliga a hacerlas en serie.
5. Corridas grandes: a mano en el servidor Linux (2502 abre los `.sim` de 2410; al revés no). Pasos en
   `starccm/vm/SERVIDOR.md`.

## Historia

- 2026-10-23: `cfturbo/` terminado y evaluado 9/10 (rondas UX → programador → docs → evaluador).
- 2026-10-23: `starccm/` creado en carpeta propia, MCP verificado contra STAR-CCM+ 2410 real, caso
  cilindro y bomba `cursocfturbo` convergida en el mismo día.
- 2026-10-23: `starccm/ui/` en cuatro hitos: página base (chat, casos, solver, escena en vivo);
  progreso tipo terminal, árbol del .sim, parámetros → chat, abrir en la GUI; rediseño estilo cliente
  de STAR-CCM+ con visor 3D three.js y tema claro; confirmaciones dentro de la página. Por la tarde,
  recorrido completo del caso `cursocfturbo` desde la página con el solver real: superficies con campo
  de todas las fronteras, escenas de plano con vectores y de malla, iteraciones con la Salida en vivo,
  chat y apagado. Solo queda sin probar el salto a la GUI de STAR-CCM+.
- 2026-10-24: ejecución remota en el servidor Linux (2502 por SSH; 41,6 s por 100 iteraciones frente a ~82 s
  local), caso nuevo desde la página hasta la simulación, modo Fronteras, convergencia en vivo y chat que
  sobrevive a recargar la pestaña. Preguntas de la IA con opciones y caso nuevo por etapas.
- 2026-10-24 (tarde): se quitó la ejecución remota (commit be0df78; era lo más frágil: 7 fallos solo por ser
  remoto, dos versiones de STAR-CCM+, solvers huérfanos). El agente es solo local; el servidor queda como
  opción manual. Recuperable en los commits `038629d`…`e163e33`.
