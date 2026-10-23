# starccm — agente que opera Simcenter STAR-CCM+

Agente que opera STAR-CCM+ en lenguaje natural: recibe una geometría de bomba o turbina, la prepara,
malla, configura la física, corre y entrega altura, torque, eficiencia y escenas.
STAR-CCM+ es el solver. Claude es el ingeniero que lo opera. Claude nunca resuelve física a mano.

Proyecto independiente dentro del repo `starccm-agent`: todo vive en `starccm/`. No depende de
`cfturbo/` (el agente hermano de diseño 1D) ni lo toca.

## Entorno (este PC, Windows 11)

- STAR-CCM+ **2410.0001** (build 19.06.009-R8, doble precisión) en
  `C:\Program Files\Siemens\19.06.009-R8\STAR-CCM+19.06.009-R8` (= `STARCCM_HOME`, se detecta solo).
  Lanzador: `star\bin\starccm+.bat`. JDK propio con `javac` en `..\jdk\win64\jdk21.0.2\bin`.
- Licencia Power-on-Demand contra `1999@flex.cd-adapco.com` (`CDLMD_LICENSE_FILE` ya apunta ahí).
  Flags: `-power -podkey $STARCCM_PODKEY -licpath $STARCCM_LICPATH`. La clave vive **solo** en
  `starccm/.env` (ignorado por git) o en `%USERPROFILE%\.starccm-agent.env`. Nunca en código,
  recetas, logs, `.server.json` ni commits; `mcp_server.py` la enmascara en todo lo que escribe.
- Python 3.14 en `starccm/.venv` (paquete `mcp`). Java: el de STAR-CCM+, no instalar otro.
- Javadoc de la API Java: `$STARCCM_HOME\doc\client\html\star\...` (1 595 clases solo en
  `star.common`). Es la fuente de verdad de nombres de clases y métodos → tool `docs_search`.
  La guía de usuario está en `$STARCCM_HOME\doc\UserGuide_19.06.pdf`.
- 12 núcleos; el servidor usa `STARCCM_NP` = núcleos − 2 por defecto.
- La MV Linux del brief original queda para después: `vm/bootstrap.sh` la prepara cuando toque.

## Arquitectura

```
Claude Code ──MCP stdio──> mcp_server.py ──> starccm+ -server -port 47827 (UN servidor vivo, .sim en memoria)
                               │               ▲
                               │  por tool:    │ starccm+ -host localhost:47827 -batch Agent_<ts>.java -noexit
                               │
                               ├── recipes/   snippets Java verificados (memoria del agente)
                               ├── cases/     un directorio por caso: cad, reportes, imágenes, RESUMEN.md
                               ├── sims/      .sim de trabajo y logs del servidor (ignorado por git)
                               ├── macros/    cada macro inyectada + su salida .out (ignorado por git)
                               ├── tests/     starccm+ falso para el selftest
                               ├── ui/        interfaz web local (puerto 8767): chat, casos, solver, escena en vivo
                               └── vm/        bootstrap de la MV Linux (futuro)
```

STAR-CCM+ es cliente-servidor. Se levanta UN servidor con el .sim en memoria y cada tool le inyecta
una macro Java con un cliente batch. No se recarga el .sim entre pasos. La macro imprime entre los
marcadores `AGENT_BEGIN <tag>` / `AGENT_END <tag>` y el MCP recorta esa salida.

Inyección de macros: **verificada el 2026-10-23 contra STAR-CCM+ 2410 real**:
`starccm+ -host localhost:PORT -batch Macro.java -noexit` (el `-noexit` evita que el cliente batch
apague el servidor al terminar la macro). Tiempos medidos en este PC:

| paso | segundos |
|---|---|
| `server_start` (licencia + MPI, sim nueva) | 4,5 |
| inyección de una macro trivial (arranque del cliente Java) | 8–10 |
| primera macro que carga módulos (3D-CAD/Parasolid, malla, física) | 50–75 |
| precompilación con `javac` | 2 |

Plan B (macro residente que vigila un `inbox/`) no hizo falta; solo si el cliente batch deja de
funcionar en otra versión.

## MCP: `mcp_server.py`

Un solo archivo, FastMCP, stdio. `python mcp_server.py --selftest` (starccm+ falso de `tests/`,
sin licencia, ~20 s) debe pasar antes de entregar. Tools:

| tool | input | output |
|---|---|---|
| `server_start(sim_path?, name?)` | .sim a abrir (se copia a `sims/`) o vacío | pid, host:port, sim, segundos. Reutiliza el vivo |
| `server_stop(save=true)` | | guarda, `sim.kill()`, limpia `.server.json` |
| `server_status()` | | vivo o no, minutos de inactividad |
| `inspect(path?)` | `tree`, `regions`, `physics`, `mesh_ops`, `parts`, `reports`, `monitors`, `scenes`, `solver` | JSON con nombres, tipos y valores |
| `run_java(body, imports?, timeout_s?)` | cuerpo de `execute()`; `sim` ya existe | stdout, exception, trace, segundos, ruta de la macro |
| `iterate(n)` | iteraciones | iteración actual, última fila de todos los monitores (residuales + reportes) |
| `export_scene(name, path?)` | escena | ruta del PNG (`cases/_scenes/` por defecto) |
| `save(path?)` | | ruta guardada |
| `recipe_search(query)` | texto | recetas con cabecera y puntuación |
| `recipe_save(name, body, note)` | | ruta en `recipes/` |
| `docs_search(query)` | texto | clases del javadoc y firmas que coinciden |

`run_java` envuelve el cuerpo así; antes de inyectar lo compila con el `javac` de STAR-CCM+
(classpath `star\lib\java\platform\modules\ext\*` …): un error de sintaxis o de nombre de clase
vuelve en ~2 s sin tocar el servidor (`STARCCM_PRECOMPILE=0` lo desactiva).

```java
import star.common.*; import star.base.neo.*; import star.base.report.*; import star.meshing.*;
import star.flow.*; import star.kwturb.*; import star.vis.*; import star.cadmodeler.*; ... // + imports extra
public class Agent_<timestamp> extends StarMacro {
  public void execute() {
    Simulation sim = getActiveSimulation();
    sim.println("AGENT_BEGIN <tag>");
    try {
      // body
    } catch (Exception e) {
      sim.println("AGENT_ERROR: " + e);   // + stack trace
    }
    sim.println("AGENT_END <tag>");
  }
}
```

Reglas del servidor:
- Apagado por inactividad: 30 min sin tools → `save` + `server_stop`. PoD cobra por hora de sesión.
- Un solo servidor a la vez. Barridos se encadenan en la misma sesión, no se abren varias.
- `server_start` registra PID, puerto, sim y log en `.server.json`. Si el proceso murió, limpia y relanza.
- Siempre trabajar sobre una copia en `sims/`, nunca sobre el .sim original del usuario.
- Config por env o por `starccm/.env` (ver `.env.example`): `STARCCM_PODKEY`, `STARCCM_LICPATH`,
  `STARCCM_PORT`, `STARCCM_NP`, `STARCCM_IDLE_MIN`, `STARCCM_HOME`, `STARCCM_EXE`.

## Interfaz web: `ui/`

`ui/server.py` (FastAPI) + `ui/surfaces.py` (EnSight/STL → dataset) + `ui/index.html` + `ui/app.js`
(three.js por CDN) + `ui/style.css`, sin build, tema claro por defecto. Preview `starccm-ui`
(`.claude/launch.json` de la raíz, puerto 8767). Paneles y endpoints: `README.md`.
Comprobación: `python ui/server.py --selftest` (HTTP contra los casos + conversión de un EnSight
mínimo, sin solver ni CLI).
Imita el cliente de STAR-CCM+ asistido por IA, alrededor de UNA simulación (Sebastián, 2026-10-23:
«primero a 1 simulación», «todo animado tipo 3D, como el cliente de ccm pero IA driven, tema claro»):
árbol a la izquierda (superficies 3D, escenas, árbol del .sim, solver), visor three.js en el centro
(campo en los vértices, leyenda, tooltip, corte, vistas animadas; las escenas PNG como pestañas),
dock abajo (Salida = terminal, Gráficos, Resumen), Claude a la derecha (chat + parámetros → prompt).
Reglas: la UI solo **lee** (casos, `.server.json`, logs, `macros/`, `surfaces/`) y pide al MCP importado
como módulo: `server_stop`, `export_scene`, `inspect`, `run_java` (solo la receta de exportación).
Nunca arranca el solver batch, nunca edita el .sim, nunca inyecta macros mientras el chat trabaja
(el candado del MCP es por proceso). El chat lanza `claude -p` con cwd `starccm/` y solo las tools
`mcp__starccm__*`, Read, Glob, Grep. Cuando el agente termine un bloque de trabajo debe dejar lo que
la página muestra: `images/*.png`, `reports/convergencia.csv` y las superficies (receta
`exportar-superficies-ensight.java` o `POST /api/surface`).
Verificado el 2026-10-23 en el preview sin solver: visor con un dataset sintético (colores, leyenda,
volar a una frontera, pestañas de escena, corte), chat con `server_status` (10 s), Salida con la última
macro real, 409 correctos. Verificados contra el solver real el 2026-10-23 12:02 (otra sesión, servidor
con `cursocfturbo.sim`): `/api/status` vivo, `/api/tree?refresh=1` (9,9 s, regiones estator/rotor/voluta),
`POST /api/scene` (9,1 s, PNG regenerado), `/api/scenes` (3 escenas), `/api/progress` con la macro y su
`.out`, `POST /api/server/stop` (guardó 158 MB y apagó). Por probar con el solver real: `/api/surface`
(la receta compila con javac) y `/api/open_gui`. Los `confirm()` del navegador no aparecen en el panel
embebido de la app: toda confirmación va dentro de la página (segundo clic «¿Seguro?»).

## Memoria

- `recipes/<verbo>-<objeto>.java`: snippet que funcionó, con cabecera de 3 líneas: qué hace,
  versión de STAR-CCM+, fecha. Guardar una receta tras CADA `run_java` que logre algo nuevo.
  Antes de escribir Java nuevo: `recipe_search` primero, `docs_search` segundo, inventar tercero.
  Las recetas con `// ESTADO: no verificado` son de memoria de Claude: probarlas antes de confiar.
- Este archivo: tras cualquier error que costara más de dos intentos, añadir una línea en
  "Lecciones" abajo con la causa y la solución. Corto, una línea.
- `cases/<caso>/RESUMEN.md`: al terminar un caso, geometría, malla, parámetros, resultados, tiempo.

## Flujo estándar: bomba centrífuga, estado estacionario

1. Importar CAD (STEP/Parasolid) como parte de geometría. Listar superficies y renombrar:
   `inlet`, `outlet`, `blades`, `hub`, `shroud`, `volute`, `walls`.
2. Surface wrapper si el CAD trae huecos. Extraer volumen de fluido interno. Leak detection
   entre inlet y outlet. Diagnóstico de superficie debe dar 0 bordes libres y 0 caras perforadas.
3. Partir en dos regiones: `rotor` (impulsor) y `stator` (voluta + tubos). Interfaz interna entre ambas.
4. Malla: poliédrica, prism layers (5 capas, estiramiento 1.3, espesor total 10 % del tamaño base),
   refinamiento en álabes y huelgo. Tamaño base inicial: diámetro del impulsor / 60.
5. Física: 3D, estacionario, líquido agua, flujo segregado, densidad constante, turbulento,
   k-omega SST, gravedad opcional.
6. Rotor en Moving Reference Frame con rpm del usuario, eje según el CAD.
7. Fronteras: inlet = mass flow inlet (o velocity inlet), outlet = pressure outlet 0 Pa relativa,
   resto walls. En rotor, walls giran con el marco; shroud estática si aplica.
8. Reportes: presión total masa-ponderada en inlet y outlet, caudal másico en inlet y outlet,
   momento en `blades`+`hub` respecto al eje. Expresiones: altura `H = (p_out - p_in)/(rho*g)`,
   potencia hidráulica `rho*g*Q*H`, potencia eje `M*omega`, eficiencia.
9. Monitores de todo lo anterior y de residuales. Criterio de parada: residuales < 1e-4 y
   variación de H y M < 0.5 % en 100 iteraciones. Máximo 2000 iteraciones.
10. Correr. Al terminar: balance de masa inlet vs outlet < 0.5 %, y+ en álabes entre 30 y 300
    (o < 5 si all-y+ con malla fina), escenas: presión en álabes, velocidad en plano medio,
    y+ en paredes.
11. Curva: repetir con 5 caudales entre 0.6 y 1.3 del nominal, reusando la malla.

Turbina: mismo flujo, cambia el signo del momento y el objetivo es potencia extraída.

## Criterios de "no sirve"

- Desbalance de masa > 1 %: revisar interfaz rotor/estator y leaks.
- Residuales planos altos: bajar under-relaxation de presión a 0.2 y velocidad a 0.5, 300 iter, reevaluar.
- H oscila: malla gruesa en la lengua de la voluta o el caso es realmente transitorio. Refinar primero.
- Celdas malas > 0.1 %: mesh repair o subir prism layer shrink.

## Estilo

- Lo mínimo que funcione. Un archivo de MCP, sin clases de más. Sin frameworks de agentes.
- Toda lógica no trivial deja un check ejecutable: `python mcp_server.py --selftest`.
- Marcar atajos deliberados con `# ponytail:` y su límite conocido.
- Mensajes al usuario en español, cortos, números en tablas.

## Lecciones

- 2026-10-23 · El sandbox del tool Bash de Claude Code bloquea las DLL de STAR-CCM+ («Una directiva
  de Control de aplicaciones bloqueó este archivo», `DynamicLoader: couldn't load StarProfile`).
  El solver solo arranca fuera del sandbox: desde el MCP (que Claude Code lanza sin sandbox) o con
  el tool Bash sin sandbox. No es una política de Windows.
- 2026-10-23 · Sin `-podkey`, `starccm+` pide `ccmpsuite` a `1999@flex.cd-adapco.com` y aborta
  (`Failed to get all licenses`, rc 8, ~60 s). No hay ninguna clave guardada en el PC: va en `.env`.
- 2026-10-23 · `doc/api` de la instalación es la API de co-simulación (C), no el javadoc. El javadoc
  Java está en `doc/client/html`. `StarMacro` y `Simulation` viven en
  `star/lib/java/platform/modules/ext/starbase.jar`; `MeshOperationManager` en `meshing.jar`.
- 2026-10-23 · El cliente batch por defecto apaga el servidor al acabar la macro: siempre `-noexit`.
- 2026-10-23 · La precompilación con `javac` detecta nombres de API equivocados en 2 s sin licencia:
  usarla antes de inyectar. Ejemplos cazados: `MonitorManager.export` necesita 3 argumentos;
  `ThreeDimensionalModel` vive en `star.metrics` (ya en los imports por defecto).
- 2026-10-23 · `MonitorManager.export` falla en batch («StarUpdate unexpectedly missing»). Residuales:
  exportar el plot `Residuals` (`sim.getPlotManager().getPlot("Residuals").export(csv, ",")`); valores
  de reportes: `getReportMonitorValue()` directo. Así lo hace `iterate`.
- 2026-10-23 · `createScene("X")` deja la escena como «X 1». Para que el PNG no salga en blanco en batch:
  `PartDisplayer` con las **fronteras** como entrada (no la región), `initialize()`,
  `setRepresentation(getDefaultFvRepresentation())` y `resetCamera(true)`. Receta `escena-malla.java`.
- 2026-10-23 · `newRegionsFromParts` crea solo un continuo «Physics 1»; crear otro deja dos. Reusarlo.
- 2026-10-23 · Autoguardado «batch» activo por defecto: deja `<sim>@meshed.sim` y `<sim>@00050.sim`.
  `server_start` lo apaga al arrancar (`AutoSave.setAutoSaveBatch(false)`).
- 2026-10-23 · CPU i5-1245U: 2 núcleos P + 8 E. Con `-np 10` el solver avisa de sobresuscripción;
  `STARCCM_NP=4` en `.env`. El selftest y el cilindro no notan la diferencia; medir en una bomba.
- 2026-10-23 · Export de CFturbo (3 STEP con caras coincidentes en las interfaces): una sola
  operación de malla con las 3 partes falla en el remallador («Surface intersects self» en r = D2/2).
  Cada parte por separado se remalla limpia. Regla: **una operación de malla por parte** y añadir
  `star.resurfacer.AutomaticSurfaceRepairAutoMesher` a la lista de malladores.
- 2026-10-23 · `importCadPart(ruta, "SharpEdges", 30.0, 2, 1e-5)` conserva los nombres de cara de
  CFturbo como superficies de parte (`[Impeller_1]-Flow domain-BladePS`…); `newRegionsFromParts`
  con `OneBoundaryPerPartSurface` las convierte en fronteras con el mismo nombre (renombrar por sufijo).
- 2026-10-23 · MRF en 2410: `ReferenceFrameManager.createReferenceFrame(RotatingReferenceFrame.class, n)`
  + `getRotationRate().setValueAndUnits(rpm, "rpm")` + `getAxisDirection/Origin`; se asigna con
  `region.getValues().get(MotionSpecification.class).setReferenceFrame(frame)`. `RotatingMotion` no
  expone la velocidad directamente.
- 2026-10-23 · Expresiones entre reportes: `${{nombreReport}}` (p.ej. `${{pt_outReport}}`).
- 2026-10-23 · Caso cursocfturbo (bomba CFturbo, D2 270 mm, 250 m³/h, 2980 rpm): 370 k celdas,
  converge en 400 iteraciones (82 s/100 con 4 procesos): H 78,8 m, M 192,5 N·m, η 89,4 %, balance
  de masa 0 %. Guion reproducible `cases/cursocfturbo/pump.py`; recetas `bomba-*.java`.
- 2026-10-23 · Exportar superficies con campo para el visor: `ImportManager.export(String, Collection<Region>,
  Collection<Boundary>, Collection<Part>, Collection<PartSurface>, Collection<FieldFunction>, boolean append,
  boolean dataAtVerts)` con un `.case` escribe EnSight Gold (javadoc 2410; `docs_search` no lo encuentra
  porque indexa mal `ImportManager`: grep en `doc/client/html/star/common/ImportManager.html`). Las
  constantes de opciones viven en `AutoExport` (`OptionDataAtVerts`, `OptionTriangulatePoly`…).
  Vectores → `getMagnitudeFunction()`. `ui/surfaces.py` lee ASCII y C Binary, `tria3/quad4/nsided`.
- 2026-10-23 · Caso cilindro (r 50 mm, L 0,5 m, 11 463 celdas poliédricas + prismas, agua 1 m/s,
  SST): 100 iteraciones, residuales 1e-6, Q_in = −Q_out = 7,755 kg/s. Recetas de cada paso guardadas.
  `cases/cilindro/RESUMEN.md`.
