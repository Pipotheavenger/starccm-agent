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

1. `python -m venv .venv` y `.venv\Scripts\pip install mcp fastapi uvicorn` (ya hecho en este PC;
   `fastapi` y `uvicorn` solo los usa la interfaz `ui/`).
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
  (`inspect("tree")`: regiones, física, malla, reportes, monitores, escenas; a demanda y cacheado).
  Arriba va el esquema fijo *Simulación* (Geometría, Física, Malla, Solucionadores, Reportes, Monitores,
  Gráficos, Escenas), armado con datos en disco (RESUMEN.md, convergencia.csv, dataset 3D) sin solver;
  al seleccionar un nodo, el panel *Propiedades* del pie muestra su tabla clave/valor.
- **Centro, visor 3D** (three.js): superficies con el campo pintado en los vértices (presión, presión
  total, |velocidad|, y+…), paleta azul→rojo / viridis / gris, rango editable, leyenda, tooltip con el
  valor bajo el ratón, resaltado de la frontera, vistas iso/axial/lateral con transición animada,
  encuadrar, giro automático, malla, botón *Rotor* (anima el giro de álabes y cubo, 0,25 rev/s, eje Z,
  solo visual), plano de corte X/Y/Z con deslizador, tríada de ejes. La barra de acciones va abajo y la
  leyenda en su propia columna a la derecha (sin solaparse; la leyenda se oculta bajo 760 px). Sin
  superficies (caso `cilindro`) la barra se apaga y se vacía. Volar a una superficie tapada por la carcasa
  activa «Carcasa» y avisa. Las marcas de la leyenda usan un único formato. Las escenas
  PNG se abren como pestañas sobre el mismo visor.
- **Abajo, dock** (plegable, arrastrable): *Salida* (la «terminal»: cola del `sims/<sim>.server.log`,
  última macro inyectada y su salida, `agent.log`, cada 3 s), *Gráficos* (`reports/convergencia.csv`:
  H y M frente a iteración, un gráfico por magnitud, tabla y criterio < 0,5 %) y *Resumen* (RESUMEN.md).
- **Derecha, Claude** (bajo 1100 px el chat pasa a ser la pestaña *Claude* del dock; a 800 px ya no queda
  fuera de pantalla): chips «Presión en álabes», «Velocidad» (acciones del visor en el
  cliente, sin solver ni IA; solo con superficies en una bomba); chat (Claude Code CLI con cwd en `starccm/` y el MCP `starccm` del `.mcp.json`
  de la raíz) y *Parámetros* (solo en casos con `pump.py`; plegado por defecto; rpm, caudal, tamaño base de malla, iteraciones) que la página convierte
  en un prompt; la UI nunca edita el .sim. Planos, vectores y escenas nuevas se piden por el chat.
- **Panel de IA modulable** (escritorio, ≥ 1100 px): el botón «»/««» de su cabecera (o la tecla C) lo pliega a una franja de 38 px con el
  título vertical y un punto parpadeante mientras trabaja; se arrastra su borde izquierdo (o ←/→ con el foco, doble clic restablece 330 px;
  260 px a 55 % de la ventana) para cambiar el ancho. Ancho y estado se guardan en localStorage (`scc_chatw`, `scc_chatopen`).
  Bajo 1100 px sigue siendo la pestaña «IA» del dock. Sin duplicados: *Parámetros* viven bajo Propiedades (a la izquierda), los atajos de campo
  junto a Campo/Paleta del visor, las escenas solo en el árbol (la pestaña del visor muestra la abierta) y los triángulos solo en la barra del visor.
- **Arriba**: selector **Local · este PC / Servidor · Linux** (dónde corre la simulación), estado del
  solver (clic: popover con el detalle Local / Servidor), «Apagar solver», «Abrir en STAR-CCM+» (GUI con `sims/<caso>.sim`, solo sin servidor batch
  vivo y solo en local, avisando del coste PoD), tema claro/oscuro.

Dónde corre la simulación (ronda 1 de UX, 2026-10-23): la elección se guarda en `starccm/.ui-settings.json`
(fuera de git; `GET/POST /api/settings`), no en el navegador, para que Claude pueda leerla. El panel
*Solver* muestra el destino: en local, `STAR-CCM+ 2410 · np N`; en servidor, el host y las primeras filas
del inventario de `vm/SERVIDOR.md` (16 vCPU, 62 GiB, 2502) y la etiqueta «servidor · remoto no implementado» (2502 ya está instalado en `/opt/Siemens/20.02.008-R8`) mientras `STARCCM_REMOTE_READY=1` no esté en `.env`. Cada mensaje del chat empieza con
`(Caso … · ejecución: Local …)` o `(… ejecución elegida: Servidor Linux 172.17.76.78 · … remoto aún no
disponible: no arranques nada allí, prepara y avisa)`. La ejecución remota en sí la monta otra sesión
(`STARCCM_RUN_HOST` del MCP, ver `vm/SERVIDOR.md`); la UI solo elige, persiste y muestra.

Ronda 3: franja de resultados (H, M, η, continuidad con semáforo, iteración) sobre el visor, leída de
`convergencia.csv` y con el formato numérico único de la leyenda; transición de color de 400 ms al cambiar
de campo; en modo «(geometría)» Mín/Máx/Paleta/auto se deshabilitan; Propiedades ya no se aplasta en casos
sin superficies; sin `tree.json` el árbol del .sim se reconstruye del disco (fronteras del manifest,
reportes, monitores, escenas; `derived: true` en `/api/tree`, sin regiones ni modelos) hasta que haya una
lectura real con el solver vivo.

Otros detalles de la ronda 2: el árbol del .sim se guarda en `cases/<caso>/tree.json` y se sirve
con `GET /api/tree?case=` aunque la UI se reinicie o el solver esté apagado («leído a las HH:MM ·
guardado»); tras un chat la página no recarga el dataset del visor si no cambió (nombre y fecha) y, si
cambió, conserva cámara, corte y superficies ocultas; los parámetros del panel derecho muestran los
valores actuales del `RESUMEN.md` (rpm, kg/s, base, iteraciones) y marcan lo editado; el criterio de
convergencia de *Gráficos* compara la última fila con la de ≥ 100 iteraciones antes (CLAUDE.md);
`/api/progress` ignora los logs y macros del starccm+ falso del selftest (que ahora escribe solo en un
temporal); en pantallas < 1100 px la rueda desplaza la página hasta tocar el modelo.

Superficies con campo: `POST /api/surface` inyecta la receta (`ImportManager.export(.case, regiones=[],
fronteras, parts=[], partsurfaces=[], funciones, append=false, dataAtVerts=true)`), convierte el EnSight
con `surfaces.py` y deja el dataset en `cases/<caso>/surfaces/<nombre>/` (no va a git). Las fronteras
de interfaz quedan fuera (duplican discos internos). Medido con la bomba `cursocfturbo` (370 k celdas),
patrón `.`: 17 fronteras (impulsor, voluta, tubo de entrada), 187 400 triángulos y 4 campos en 10,7 s de
solver más 0,3 s de conversión. El botón «Carcasa» deja voluta, shroud y casing al 25 % para ver los
álabes; también sirven las casillas del árbol y el plano de corte.

Botón «Rotor» (animación del visor, 0,25 rev/s): cada marco rotatorio gira las superficies de su región
sobre **su** eje y **su** origen. Al exportar superficies, la receta lee de STAR-CCM+ los marcos
rotatorios (`ROTFRAME región, eje, origen, rpm`) y quedan en `manifest.rotation`, así que vale para
bombas, turbinas, ventiladores o compresores sin suponer nada. Sin ese dato, gira las regiones con
nombre de rotor (rotor, impeller, runner, rodete…) sobre el centro de su propia caja y el eje de menor
espesor (Z si la caja es casi cúbica). El sentido sigue el signo de las rpm.

Salida en vivo: el MCP escribe el stdout del cliente batch en `macros/<macro>.out` mientras corre, así
que la pestaña *Salida* muestra las iteraciones (residuales y reportes) en tiempo real y marca la macro
«en marcha» hasta que aparece `AGENT_END`.

Recorrido completo verificado el 2026-10-23 con el solver real: exportar superficies, regenerar escenas
(`plano_vectores`, `malla`, recetas `escena-plano-vectores.java` y `escena-malla-rotor.java`), iterar
viendo la Salida, chat con `inspect`, apagar con guardado desde el botón.

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
| `GET /api/tree[?refresh=1&case=]` | árbol cacheado (memoria o `cases/<caso>/tree.json`); con `refresh` lee del solver (`inspect("tree")`, ~10 s; 409 sin solver o con el chat trabajando) y lo guarda |
| `GET /api/settings` · `POST /api/settings {run_where}` | dónde corre la simulación (`local` \| `server`), `local {np version}`, `server {host user label rows ready version}` de `vm/SERVIDOR.md`; persiste en `.ui-settings.json` |
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
