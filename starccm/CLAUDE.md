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
                               └── vm/        bootstrap de la MV Linux (futuro)
```

STAR-CCM+ es cliente-servidor. Se levanta UN servidor con el .sim en memoria y cada tool le inyecta
una macro Java con un cliente batch. No se recarga el .sim entre pasos. La macro imprime entre los
marcadores `AGENT_BEGIN <tag>` / `AGENT_END <tag>` y el MCP recorta esa salida.

Inyección de macros (orden de preferencia; marcar aquí cuál quedó verificada contra el solver real):
1. `starccm+ -host localhost:PORT -batch Macro.java -noexit` ← implementado; **pendiente de verificar
   con licencia** (el `-noexit` evita que el cliente batch apague el servidor al terminar la macro).
2. Plan B: macro residente `Watcher.java` que vigila `cases/<caso>/inbox/` y ejecuta cada .java que
   aparece, escribiendo la salida en `outbox/`. Solo si 1 falla en 2410.

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
- 2026-10-23 · En 2410 `MonitorManager.export` es `(String, String, Collection<PlotableMonitor>)`;
  la versión de dos argumentos no existe. La precompilación con `javac` lo detecta en 2 s sin licencia:
  usarla para validar nombres de API antes de tener el servidor.
