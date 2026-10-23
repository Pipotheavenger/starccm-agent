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
| `ui/server.py` | FastAPI: página, casos, estado del solver, escena en vivo, chat SSE; `--selftest` (HTTP, sin solver ni CLI, ~3 s) |
| `ui/index.html` · `ui/app.js` · `ui/style.css` | marcado, lógica (módulo ES, sin build) y estilos (mismos tokens que cfturbo/ui) |

La página gira en torno a UNA simulación (el caso elegido a la izquierda; por defecto `cursocfturbo`).
Pestañas: **Resumen** (RESUMEN.md renderizado), **Escenas** (PNG de `images/`, zoom y «↻» que
re-exporta esa escena desde el solver vivo), **Convergencia** (`reports/convergencia.csv`: H y M
frente a iteración, un gráfico por magnitud, tabla y criterio < 0,5 %), **En vivo** (escena grande:
STAR-CCM+ en modo servidor no tiene ventana; se exporta un PNG a demanda, ~10 s, con auto cada 60 s),
**Árbol** (`inspect("tree")`: regiones, física, malla, reportes, monitores, escenas, como el panel
izquierdo de STAR-CCM+; se lee a demanda y se cachea) y **Progreso** (la «terminal»: cola del
`sims/<sim>.server.log`, última macro inyectada con su salida y `agent.log`, cada 3 s).
Además: **Solver** (`.server.json`, inactividad, botón «Apagar solver»), **Abrir en STAR-CCM+** (lanza
la GUI con `sims/<caso>.sim`, solo sin servidor batch vivo, avisando del coste PoD), **Chat** (Claude
Code CLI con cwd en `starccm/` y el MCP `starccm` del `.mcp.json` de la raíz) y **Parámetros**
(rpm, caudal, tamaño base de malla, iteraciones): la página los convierte en un prompt y Claude los
cambia vía MCP; la UI nunca edita el .sim. Planos de corte, vectores y escenas nuevas se piden por el chat.

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
| `POST /api/chat {message, session_id, case}` | SSE: `status init text tool tool_result ping raw result error stopped done`; un chat a la vez |
| `POST /api/chat/stop` | mata la CLI y sus hijos |

Reglas: la UI nunca arranca el solver (lo hace Claude con `server_start` desde el chat); un solo chat
a la vez; mientras el chat trabaja no se inyectan macros desde la UI (el candado del MCP es por
proceso). Errores siempre `{"detail": "texto"}`.

## Primera comprobación con el solver real

En Claude Code: `server_start()` → `run_java('sim.println("PING");')` → `server_stop()`.
Anotar en CLAUDE.md > Lecciones el tiempo de arranque y si la inyección `-host … -batch … -noexit`
funciona en 2410.
