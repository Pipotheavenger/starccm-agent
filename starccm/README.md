# starccm

Agente que opera Simcenter STAR-CCM+ (2410, instalado en este PC) desde Claude Code vía MCP.
El brief completo, el flujo de bomba y las lecciones están en [CLAUDE.md](CLAUDE.md).

```
starccm/
├── CLAUDE.md          brief del proyecto (manda sobre todo lo demás)
├── PRIMER-PROMPT.md   prompts para arrancar las sesiones de trabajo
├── mcp_server.py      el MCP (11 tools) + --selftest
├── ui/                interfaz web local (FastAPI + una página): chat, galería de casos, solver, escena en vivo
├── .env.example       variables: clave PoD, puerto, núcleos (copiar a .env, que no va a git)
├── .mcp.json          registro del MCP para Claude Code si se abre esta carpeta sola
├── recipes/           snippets Java que ya funcionaron (memoria del agente)
├── cases/             un directorio por caso: cad/, reportes, imágenes, RESUMEN.md
├── sims/              .sim de trabajo y logs del servidor (no va a git)
├── macros/            macros inyectadas con su salida (no va a git)
├── tests/             fake_starccm.py: starccm+ falso del selftest
└── vm/                bootstrap.sh para la MV Linux (futuro)
```

## Puesta en marcha

1. `python -m venv .venv` y `.venv\Scripts\pip install mcp` (ya hecho en este PC).
2. Copiar `.env.example` a `.env` y poner la clave Power-on-Demand en `STARCCM_PODKEY`.
3. `.venv\Scripts\python mcp_server.py --selftest` → «todo en verde» (no necesita licencia).
4. El MCP está registrado en el `.mcp.json` de la raíz del repo (servidor `starccm`). Reiniciar la
   sesión de Claude Code para que aparezcan las tools `server_start`, `run_java`, etc.

## Casos

- `cases/cilindro/`: tubo de prueba de la fontanería (RESUMEN.md, imagen de la malla).
- `cases/cursocfturbo/`: bomba centrífuga exportada por CFturbo (3 STEP + `.cfturbo-ccm` en `cad/`).
  `pump.py` es el guion del caso: cada paso es un cuerpo Java que se precompila con `javac`, se
  inyecta con `run_java` y se guarda como receta `recipes/bomba-<paso>.java` cuando funciona.

```bash
.venv\Scripts\python cases\cursocfturbo\pump.py --compile      # solo javac de todos los pasos
.venv\Scripts\python cases\cursocfturbo\pump.py --steps all    # importar … malla contra el solver
.venv\Scripts\python cases\cursocfturbo\pump.py --run 2000     # itera en bloques de 100 hasta converger
.venv\Scripts\python cases\cursocfturbo\pump.py --scenes       # presión en álabes, velocidad, y+ → images/
```

Ejecutar fuera del sandbox del tool Bash (desde la terminal del PC o con el MCP).

## Interfaz web: `ui/`

Puerto 8767 (8765 es la de cfturbo). Arranque: preview `starccm-ui` de `.claude/launch.json` de la
raíz, o a mano:

```bash
starccm\.venv\Scripts\python -m uvicorn --app-dir starccm ui.server:app --port 8767
```

| archivo | qué tiene |
|---|---|
| `ui/server.py` | FastAPI: página, caso, superficies 3D, escenas, árbol, progreso, estado del solver, chat SSE; `--selftest` (HTTP, sin solver ni CLI, ~3 s) |
| `ui/surfaces.py` | EnSight Gold (ASCII o C Binary) o STL → dataset binario del visor (`positions.f32`, `indices.u32`, `<campo>.f32`, `manifest.json`); sin numpy |
| `ui/index.html` · `ui/app.js` · `ui/style.css` | marcado, lógica (módulo ES, three.js por CDN, sin build) y estilos; tema claro por defecto |
| `recipes/exportar-superficies-ensight.java` | macro: fronteras que casan con un regex + field functions → `.case` con datos en los vértices |

Imita el cliente de STAR-CCM+, pero asistido por IA, alrededor de UNA simulación (selector de caso
mínimo arriba a la izquierda; por defecto `cursocfturbo`):

- **Izquierda, árbol de la simulación**: *Superficies 3D* (datasets exportados, una fila por frontera
  con casilla de visibilidad, color y nº de triángulos; clic = volar a ella; «↓ solver» abre el diálogo
  de exportación), *Escenas* (PNG de `images/`, «↻» re-exporta desde el solver), *Árbol del .sim*
  (`inspect("tree")`: regiones, física, malla, reportes, monitores, escenas; a demanda y cacheado) y
  el panel *Solver* (`.server.json`, inactividad).
- **Centro, visor 3D** (three.js): superficies con el campo pintado en los vértices (presión, presión
  total, |velocidad|, y+…), paleta azul→rojo / viridis / gris, rango editable, leyenda, tooltip con el
  valor bajo el ratón, resaltado de la frontera, vistas iso/axial/lateral con transición animada,
  encuadrar, giro automático, malla, plano de corte X/Y/Z con deslizador, tríada de ejes. Las escenas
  PNG se abren como pestañas sobre el mismo visor.
- **Abajo, dock** (plegable, arrastrable): *Salida* (la «terminal»: cola del `sims/<sim>.server.log`,
  última macro inyectada y su salida, `agent.log`, cada 3 s), *Gráficos* (`reports/convergencia.csv`:
  H y M frente a iteración, un gráfico por magnitud, tabla y criterio < 0,5 %) y *Resumen* (RESUMEN.md).
- **Derecha, Claude**: chat (Claude Code CLI con cwd en `starccm/` y el MCP `starccm` del `.mcp.json`
  de la raíz) y *Parámetros* (rpm, caudal, tamaño base de malla, iteraciones) que la página convierte
  en un prompt; la UI nunca edita el .sim. Planos, vectores y escenas nuevas se piden por el chat.
- **Arriba**: estado del solver, «Apagar solver», «Abrir en STAR-CCM+» (GUI con `sims/<caso>.sim`,
  solo sin servidor batch vivo, avisando del coste PoD), tema claro/oscuro.

Superficies con campo: `POST /api/surface` inyecta la receta (`ImportManager.export(.case, regiones=[],
fronteras, parts=[], partsurfaces=[], funciones, append=false, dataAtVerts=true)`), convierte el EnSight
con `surfaces.py` y deja el dataset en `cases/<caso>/surfaces/<nombre>/` (no va a git). Una bomba de
370 k celdas da unos cientos de miles de triángulos: el visor los pinta sin problema.

| método y ruta | qué hace |
|---|---|
| `GET /api/cases` · `/api/cases/{caso}` | lista de casos (título, fecha, escenas, última fila de convergencia) y detalle (RESUMEN.md, escenas, csv) |
| `GET /files/{caso}/images/{png}` · `/scenes/{png}` | escenas de un caso y de `cases/_scenes/` (destino por defecto de `export_scene`) |
| `GET /api/status` | `alive pid port sim started np idle_min idle_limit_min stale stopping chatting log[]` |
| `POST /api/server/stop {save}` | `server_stop` del MCP importado como módulo (este proceso corre fuera del sandbox del tool Bash) |
| `GET /api/live?case=` | PNG exportados, los más nuevos primero |
| `POST /api/scene {name, case}` | `export_scene` al `images/` del caso; 409 sin solver vivo o mientras el chat trabaja |
| `GET /api/scenes` | nombres de escenas del .sim (`inspect("scenes")`) |
| `GET /api/progress` | `server_log {file size mtime tail[]}`, `agent_log[]`, `macro {file started running finished body out[]}` |
| `GET /api/tree[?refresh=1]` | árbol cacheado; con `refresh` lee del solver (`inspect("tree")`, ~10 s; 409 sin solver o con el chat trabajando) |
| `POST /api/open_gui {case}` | lanza la GUI de STAR-CCM+ con `sims/<caso>.sim` y la licencia de `.env`; 404 sin .sim, 409 con servidor batch vivo |
| `GET /api/surfaces?case=` | datasets del visor (`cases/<caso>/surfaces/*/manifest.json`), el más nuevo primero |
| `GET /surfaces/{caso}/{dataset}/{archivo}` | `positions.f32`, `indices.u32`, `<campo>.f32`, `manifest.json` (caché 1 h) |
| `POST /api/surface {case, name, pattern, funcs}` | exporta fronteras (regex sobre «región/frontera») con field functions desde el solver vivo y convierte; 409 sin solver o con el chat trabajando |
| `POST /api/chat {message, session_id, case}` | SSE: `status init text tool tool_result ping raw result error stopped done`; un chat a la vez |
| `POST /api/chat/stop` | mata la CLI y sus hijos |

Reglas: la UI nunca arranca el solver (lo hace Claude con `server_start` desde el chat); un solo chat
a la vez; mientras el chat trabaja no se inyectan macros desde la UI (el candado del MCP es por
proceso). Errores siempre `{"detail": "texto"}`.

## Primera comprobación con el solver real

En Claude Code: `server_start()` → `run_java('sim.println("PING");')` → `server_stop()`.
Anotar en CLAUDE.md > Lecciones el tiempo de arranque y si la inyección `-host … -batch … -noexit`
funciona en 2410.
