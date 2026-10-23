# starccm-agent

Agentes de IA para turbomáquinas hidráulicas que operan software de ingeniería real desde lenguaje
natural, con Claude Code como cerebro y un servidor MCP por herramienta. Dos agentes independientes,
cada uno en su carpeta, con su `CLAUDE.md` (brief que manda), su MCP, su entorno Python y su memoria:

| carpeta | herramienta | qué hace | estado (2026-10-23) |
|---|---|---|---|
| [`starccm/`](starccm/README.md) | Simcenter STAR-CCM+ 2410 (este PC, licencia PoD) | prepara, malla, configura física, corre y entrega altura, torque, eficiencia y escenas de una bomba | MCP verificado contra el solver real; bomba `cursocfturbo` convergida |
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
- Tiempos medidos: arranque 4,5 s; macro 8–10 s; primera macro de CAD/física 60–75 s (módulos).
- Casos: `cases/cilindro/` (prueba de fontanería) y `cases/cursocfturbo/` (bomba centrífuga, 370 k
  celdas, 400 iteraciones, H 78,8 m, M 192,5 N·m, η 89,4 %). Cada caso tiene `RESUMEN.md`, `images/`,
  `reports/` y, el de la bomba, un guion reproducible `pump.py` paso a paso.
- 22 recetas en `recipes/` (geometría, regiones, interfaces, malla por parte, MRF, fronteras,
  reportes, escenas, residuales, autosave, exportación de superficies con campo a EnSight).
- `ui/`: interfaz web (FastAPI + three.js, puerto 8767, tema claro) que imita el cliente de
  STAR-CCM+ pero asistido por IA, alrededor de UNA simulación: árbol de la simulación, visor 3D con
  los campos pintados en las superficies (presión, velocidad, y+…), escenas PNG como pestañas, dock
  con Salida (log y macros en vivo), Gráficos de convergencia y Resumen, chat con Claude Code y
  parámetros que se convierten en prompt. Detalle en `starccm/README.md`.

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

1. **Interfaz web de `starccm/`** (`starccm/ui/`, puerto 8767): construida el 2026-10-23 alrededor de
   UNA simulación (chat, árbol, visor 3D con campos, escenas, progreso en vivo, parámetros, salto a la
   GUI de STAR-CCM+). Falta exportar las superficies reales de la bomba al visor con el solver vivo
   (`POST /api/surface`; cuesta licencia PoD) y pedir por el chat planos de corte y vectores.
2. Perfeccionar esa simulación: malla y y+, comparación con la predicción 1D de CFturbo (84,4 m
   frente a 78,8 m del CFD), monitores de parada automáticos.
3. Después, varias simulaciones: curva H-Q de 5 caudales reusando la malla (`PRIMER-PROMPT.md`,
   tercer prompt), comparación entre variantes de geometría.
4. MV Linux con STAR-CCM+ 2606 (`starccm/vm/bootstrap.sh`), cuando haga falta más potencia.

## Historia

- 2026-10-23: `cfturbo/` terminado y evaluado 9/10 (rondas UX → programador → docs → evaluador).
- 2026-10-23: `starccm/` creado en carpeta propia, MCP verificado contra STAR-CCM+ 2410 real, caso
  cilindro y bomba `cursocfturbo` convergida en el mismo día.
- 2026-10-23: `starccm/ui/` en cuatro hitos: página base (chat, casos, solver, escena en vivo);
  progreso tipo terminal, árbol del .sim, parámetros → chat, abrir en la GUI; rediseño estilo cliente
  de STAR-CCM+ con visor 3D three.js y tema claro; confirmaciones dentro de la página. Endpoints
  verificados contra el solver real salvo la exportación de superficies.
