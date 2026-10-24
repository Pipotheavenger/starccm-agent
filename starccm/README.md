# starccm

Agente que opera Simcenter STAR-CCM+ desde Claude Code vía MCP, con una interfaz web local.
Corre en este PC (2410) o en el servidor Linux (2502), a elección por simulación.
El brief del agente, el flujo de bomba y las lecciones están en [CLAUDE.md](CLAUDE.md); el servidor
Linux, sus tiempos y riesgos en [vm/SERVIDOR.md](vm/SERVIDOR.md).

```
starccm/
├── CLAUDE.md          brief del agente (manda sobre todo lo demás)
├── PRIMER-PROMPT.md   prompts para arrancar las sesiones de trabajo
├── mcp_server.py      el MCP (11 tools, local y remoto) + --selftest
├── ui/                interfaz web local (FastAPI + una página, puerto 8767) + --selftest
├── .env.example       variables: clave PoD, puerto, núcleos (copiar a .env, que no va a git)
├── .mcp.json          registro del MCP para Claude Code si se abre esta carpeta sola
├── recipes/           snippets Java que ya funcionaron (25; memoria del agente)
├── cases/             un directorio por caso: cad/, reportes, imágenes, RESUMEN.md
├── sims/              .sim de trabajo y logs del servidor (no va a git)
├── macros/            macros inyectadas con su salida (no va a git)
├── tests/             fake_starccm.py y fake_claude.py: los falsos de los selftests
└── vm/                SERVIDOR.md, remote_check.sh (servidor Linux) y bootstrap.sh (plan aparcado)
```

## Puesta en marcha

1. `python -m venv .venv` y `.venv\Scripts\pip install mcp fastapi uvicorn` (ya hecho en este PC).
2. Copiar `.env.example` a `.env` y poner la clave Power-on-Demand en `STARCCM_PODKEY`.
3. Selftests (sin licencia, sin solver): ver «Selftests» abajo.
4. El MCP está registrado en el `.mcp.json` de la raíz del repo (servidor `starccm`). Reiniciar la
   sesión de Claude Code para que aparezcan las tools.
5. Interfaz: preview `starccm-ui` de `.claude/launch.json` de la raíz, o a mano (puerto 8767; 8765 es la de cfturbo):

```bash
starccm\.venv\Scripts\python -m uvicorn --app-dir starccm ui.server:app --port 8767
```

Ejecutar el solver fuera del sandbox del tool Bash (desde el MCP, la UI o la terminal del PC).
Servidor Linux: llave SSH del usuario y clave PoD en `~/.starccm-agent.env` del servidor (ya hecho); `bash vm/remote_check.sh` lo comprueba sin licencia.

## Selftests

| comando (desde `starccm/`) | qué comprueba | duración |
|---|---|---|
| `.venv\Scripts\python mcp_server.py --selftest` | las 11 tools contra `tests/fake_starccm.py`, traducción de rutas remotas; en un temporal, sin tocar `sims/` ni `.server.json` | 5–20 s |
| `.venv\Scripts\python ui\server.py --selftest` | HTTP contra los casos, caso nuevo + subida de CAD, `fronteras.json`, conversión de un EnSight mínimo, chat con `tests/fake_claude.py` (cortar la conexión no lo detiene) | ~3 s |
| `bash vm/remote_check.sh` | 13 comprobaciones del servidor Linux por SSH (instalación, JDK, licencia, MPI, dependencias); no arranca el solver | segundos |

## La interfaz por zonas

Imita el cliente de STAR-CCM+, asistido por IA, alrededor de UNA simulación. Sin build; tema claro por defecto.

| zona | qué hay |
|---|---|
| **Barra superior** | Selector **Local · este PC / Servidor · Linux** (dónde corre; se guarda en `.ui-settings.json`, no en el navegador, para que la IA lo lea) · **«＋ Caso nuevo»** · estado del solver (clic: popover con el detalle de ambos) · «Apagar solver» (guarda y apaga; segundo clic confirma) · «Abrir en STAR-CCM+» (GUI con `sims/<caso>.sim`; solo en local y sin solver batch vivo; avisa del coste PoD) · tema claro/oscuro |
| **Árbol (izquierda, plegable: botón « o tecla T)** | Selector de caso. Esquema *Simulación* (Geometría, Física, Malla, Solucionadores, Reportes, Monitores, Gráficos, Escenas) armado con datos en disco; *Superficies 3D* (datasets exportados, casilla de visibilidad, color, triángulos; clic = volar a la frontera; «↓ solver» exporta del solver vivo; la etiqueta del papel si se marcó en Fronteras); *Escenas* (PNG de `images/`, «↻» regenera desde el solver); *Árbol del .sim* (`inspect("tree")`, ~10 s, cacheado en `cases/<caso>/tree.json`; sin él se reconstruye del disco). Abajo: *Propiedades* del nodo y *Parámetros* (solo en casos con `pump.py`: rpm, caudal, base de malla, iteraciones → prompt) |
| **Visor 3D (centro)** | Campos pintados en los vértices (presión, presión total, \|velocidad\|, y+…), paleta, rango editable, leyenda, tooltip con el valor, vistas iso/axial/lateral (teclas 1·2·3, `F` encuadra), giro automático, malla, tríada. Franja de resultados (H, M, η, continuidad, iteración). Las escenas PNG se abren como pestañas sobre el mismo visor. Botones abajo: **Fronteras**, **Carcasa**, **Rotor**, **plano de corte** X/Y/Z |
| **Fronteras** (tecla B) | Todo opaco y gris; clic en una cara → menú: entrada, salida, pared, interfaz, simetría. Colores por papel y contador; se guarda en `cases/<caso>/fronteras.json`. «Aplicar con la IA» (pide al menos una entrada y una salida) le encarga poner esos tipos tal cual, reiniciar la solución e iterar. Doble clic sigue volando a la cara |
| **Carcasa** | Voluta, shroud y casing al 25 % para ver los álabes |
| **Rotor** | Anima el giro (0,25 rev/s) de cada marco rotatorio de STAR-CCM+ sobre **su** eje y origen (se lee al exportar: `manifest.rotation`); vale para cualquier turbomáquina; solo visual |
| **Dock (abajo, plegable: tecla \`)** | *Salida* (la «terminal»: cola del log del servidor, última macro y su `.out` en vivo, `agent.log`; marca «en marcha» hasta `AGENT_END`) · *Gráficos* (convergencia **en vivo**: residuales en escala log y H, M, η… por iteración, leídos de la salida del solver sin coste extra, con aviso de posible divergencia; en reposo, `reports/convergencia.csv` con el criterio < 0,5 % a 100 iteraciones) · *Resumen* (`RESUMEN.md`) |
| **Panel de IA (derecha)** | Chat con Claude Code (`claude -p`, cwd `starccm/`, MCP `starccm`; narra cada paso y cada herramienta aparece como «▶ Importando la geometría … 12 s ✓»). Sobrevive a recargar la pestaña. Se pliega (botón »/« o tecla C) a una franja de 38 px con un punto que parpadea mientras trabaja; el borde izquierdo se arrastra (←/→ con el foco; doble clic = 330 px); ancho y estado se guardan en el navegador. Bajo 1100 px es la pestaña «IA» del dock |

Reglas: la UI nunca arranca el solver (lo hace la IA con `server_start`), nunca edita el .sim y no inyecta
macros mientras el chat trabaja; un solo chat a la vez. Las confirmaciones van dentro de la página.

## De una geometría nueva a resultados

1. **Crear el caso**: «＋ Caso nuevo» (arriba). Nombre (letras, números, `_`, `-`).
2. **Subir el CAD**: STEP, Parasolid, IGES, STL, `.cfturbo-ccm`… Se pueden elegir o arrastrar varios archivos (se suman; hasta 2 GB cada uno). Quedan en `cases/<caso>/cad/`.
3. **Elegir dónde corre**: Local (2410 en este PC, 4 procesos) o Servidor (2502, 14 procesos). Conviene el servidor para iterar; local para tareas cortas (ver `vm/SERVIDOR.md`). Con Servidor el CAD se sube solo.
4. **Encargo a la IA**: máquina, fluido, rpm (el signo es el sentido), caudal másico, eje de giro, iteraciones máximas y notas libres. Con la casilla marcada la IA prepara y corre la simulación completa.
5. **Caras sin nombre**: si la geometría trae las caras agrupadas o con nombres genéricos, la IA las separa por ángulo, exporta la geometría al visor y **se detiene** pidiendo que marques entrada y salida.
6. **Marcar en Fronteras** (tecla B): clic en cada cara → entrada, salida, pared, interfaz o simetría. Mínimo una entrada y una salida.
7. **«Aplicar con la IA»**: pone esos tipos tal cual y reinicia la solución.
   **Preguntas de la IA**: cuando duda (qué cara es entrada o salida, modelo de turbulencia, fluido, condiciones,
   si seguir) no adivina. Muestra en el chat una **tarjeta con opciones** (su recomendación primero) y una casilla
   para otra respuesta, y te **enseña lo que no tiene claro**: abre Fronteras con las caras dudosas marcadas en el
   árbol, una escena PNG, el visor o los gráficos. Un clic responde y la conversación sigue.
   **Por etapas**: tras montar el caso corre **100 iteraciones de prueba** y entrega resultados completos (escenas,
   superficies con campo, tabla de reportes, convergencia, `RESUMEN.md` provisional). Luego **pregunta** si seguir
   hasta el criterio de parada, cambiar algo o parar; solo sigue si lo confirmas.
8. **Seguir la convergencia en vivo**: dock → *Gráficos* (residuales y H, M, η por iteración) y *Salida*. Si aparece el aviso de divergencia, detener el chat y revisar fronteras y malla.
9. **Resultados**: franja de resultados sobre el visor, campos en superficies (el visor convierte solo las superficies nuevas), escenas PNG, *Resumen* con `RESUMEN.md`; «Apagar solver» guarda el .sim y libera la licencia.

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

## Archivos de `ui/`

| archivo | qué tiene |
|---|---|
| `server.py` | FastAPI: página, casos, superficies 3D, escenas, árbol, progreso, estado del solver, chat SSE; `--selftest` |
| `surfaces.py` | EnSight Gold (ASCII o C Binary) o STL → dataset binario del visor (`positions.f32`, `indices.u32`, `<campo>.f32`, `manifest.json`); sin numpy |
| `index.html` · `app.js` · `style.css` | marcado, lógica (módulo ES, three.js por CDN) y estilos |
| `recipes/exportar-superficies-ensight.java` | fronteras que casan con un regex + field functions → `.case` con datos en los vértices (más `.meta` con fronteras y marcos rotatorios). Las de interfaz quedan fuera |

Superficies: `POST /api/surface` inyecta la receta, convierte con `surfaces.py` y deja el dataset en
`cases/<caso>/surfaces/<nombre>/` (no va a git). Medido con `cursocfturbo` (370 k celdas), patrón `.`:
17 fronteras, 187 400 triángulos y 4 campos en 10,7 s de solver más 0,3 s de conversión.

## Endpoints

Errores siempre `{"detail": "texto"}`. Los `409` son «solver no vivo» o «la IA está usando el solver».

| método y ruta | qué hace |
|---|---|
| `GET /` · `/app.js` · `/style.css` | la página |
| `GET /api/cases` · `/api/cases/{caso}` | lista (título, fecha, escenas, última fila de convergencia) y detalle (RESUMEN.md, escenas, csv, `pump`) |
| `POST /api/cases/new {name}` | crea `cases/<caso>/{cad,images,reports}`; 409 si existe |
| `PUT /api/cases/{caso}/cad/{archivo}` | sube un archivo de geometría (cuerpo = el archivo; extensiones CAD; máx. 2 GB) |
| `GET /api/cases/{caso}/cad` | archivos subidos |
| `GET/POST /api/cases/{caso}/roles {roles}` | `fronteras.json`: «región/frontera» → `inlet\|outlet\|wall\|interface\|symmetry` (422 con otro papel) |
| `GET /files/{caso}/images/{png}` · `/scenes/{png}` | escenas de un caso y de `cases/_scenes/` |
| `GET /api/live?case=` | PNG exportados, los más nuevos primero |
| `POST /api/scene {name, case}` | `export_scene` al `images/` del caso; 409 sin solver o con el chat trabajando |
| `GET /api/scenes` | nombres de escenas del .sim (`inspect("scenes")`) |
| `GET /api/status` | `alive pid port host sim where rsim started np startup_seconds idle_min idle_limit_min stale stopping chatting remote_error log[]` |
| `POST /api/server/stop {save}` | `server_stop` del MCP importado; 409 mientras el chat trabaja |
| `GET /api/progress` | `server_log {file size mtime tail[]}`, `agent_log[]`, `macro {file started running finished body out[]}` |
| `GET /api/tree[?refresh=1&case=]` | árbol cacheado; con `refresh` lee del solver (~10 s) y lo guarda; `derived: true` si se reconstruyó del disco |
| `GET /api/settings` · `POST /api/settings {run_where}` | dónde corre (`local` \| `server`), datos de ambos; persiste en `.ui-settings.json` |
| `POST /api/open_gui {case}` | lanza la GUI de STAR-CCM+ con `sims/<caso>.sim`; 404 sin .sim, 409 con solver batch vivo |
| `GET /api/surfaces?case=` | datasets del visor, el más nuevo primero (convierte los EnSight nuevos de `surfaces/_raw/`) |
| `GET /surfaces/{caso}/{dataset}/{archivo}` | `positions.f32`, `indices.u32`, `<campo>.f32`, `manifest.json` (caché 1 h) |
| `POST /api/surface {case, name, pattern, funcs}` | exporta fronteras (regex sobre «región/frontera») con campos desde el solver vivo y convierte |
| `POST /api/chat {message, session_id, case}` | SSE: `status init text tool tool_result ping raw result error stopped done`; un chat a la vez; corre en un hilo del servidor |
| `GET /api/chat/current` | la conversación en curso o la última (`id running n message case started`) |
| `GET /api/chat/stream?id=&frm=` | reengancha el SSE desde el evento `frm`; 404 si ya no está en memoria |
| `POST /api/chat/stop` | mata la CLI y sus hijos |

## Primera comprobación con el solver real

En Claude Code: `server_start()` → `run_java('sim.println("PING");')` → `server_stop()`. Hecho el 2026-10-23
en 2410 (ver tiempos en CLAUDE.md).
