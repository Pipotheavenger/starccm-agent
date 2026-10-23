# starccm-agent

Agente que opera Simcenter STAR-CCM+ en lenguaje natural: recibe una geometría de bomba o turbina,
la prepara, malla, configura la física, corre y entrega altura, torque, eficiencia y escenas.
STAR-CCM+ es el solver. Claude es el ingeniero que lo opera. Claude nunca resuelve física a mano.

## Entorno

- MV Linux x86_64 (Rocky/RHEL 9). STAR-CCM+ 2606.0002 double en `$STARCCM_HOME`.
- Licencia Power-on-Demand: `-power -podkey $STARCCM_PODKEY -licpath $STARCCM_LICPATH`.
  La clave vive solo en `~/.starccm-agent.env`. Nunca en código, recetas, logs ni commits.
- Python en `.venv` (paquetes `mcp`, `anthropic`). Java viene con STAR-CCM+, no instalar otro.
- Documentación y javadoc de la API: `$STARCCM_HOME/doc`. Es la fuente de verdad de nombres de clases.

## Arquitectura

```
Claude Code ──MCP──> mcp_server.py ──> starccm+ (servidor vivo, puerto $STARCCM_PORT)
                         │
                         ├── recipes/   snippets Java verificados (memoria)
                         ├── cases/     un directorio por caso: cad, macros, reportes, imágenes
                         └── sims/      .sim de trabajo (ignorado por git)
```

STAR-CCM+ es cliente-servidor. Se levanta UN servidor con el .sim en memoria y cada tool le
inyecta una macro Java. No se recarga el .sim entre pasos.

Inyección de macros, en este orden de preferencia; verificar cuál funciona en 2606 el primer día
y anotar el resultado aquí:
1. `starccm+ -host localhost:$STARCCM_PORT -batch Macro.java`
2. `starccm+ -host localhost:$STARCCM_PORT -macro Macro.java` (cliente sin GUI)
3. Plan B: macro residente `Watcher.java` que vigila `cases/<caso>/inbox/` y ejecuta cada
   .java que aparece, escribiendo salida en `outbox/`.

## MCP: `mcp_server.py`

Un solo archivo, FastMCP, stdio. Tools:

| tool | input | output |
|---|---|---|
| `server_start(sim_path?)` | ruta a .sim o vacío | host:port. Si ya hay servidor, lo reutiliza |
| `server_stop(save=true)` | | guarda y apaga |
| `inspect(path?)` | nodo del árbol, p.ej. `regions`, `physics`, `mesh_ops`, `reports` | JSON con nombres, tipos y valores principales |
| `run_java(body, imports?)` | cuerpo del método `execute()` | stdout, stderr, excepción si la hay, tiempo |
| `iterate(n)` | iteraciones | residuales finales, valores de todos los reportes, tiempo |
| `export_scene(name, path)` | | ruta del PNG |
| `save(path?)` | | ruta guardada |
| `recipe_search(query)` | texto | lista de recetas con primera línea |
| `recipe_save(name, body, note)` | | ruta |
| `docs_search(query)` | texto | fragmentos del javadoc en `$STARCCM_HOME/doc` |

`run_java` envuelve el cuerpo así y compila con el javac que trae STAR-CCM+:

```java
import star.common.*;
import star.base.neo.*;
import star.base.report.*;
import star.meshing.*;
import star.flow.*;
import star.kwturb.*;
import star.vis.*;
// + imports extra que pase el agente
public class Agent_<timestamp> extends StarMacro {
  public void execute() {
    Simulation sim = getActiveSimulation();
    try {
      // body
    } catch (Exception e) {
      sim.println("AGENT_ERROR: " + e);
      throw e;
    }
  }
}
```

Reglas del servidor:
- Apagado por inactividad: 30 min sin tools -> `save` + `server_stop`. PoD cobra por hora de sesión.
- Un solo servidor a la vez. Barridos se encadenan en la misma sesión, no se abren varias.
- `server_start` registra el PID y el puerto en `.server.json`. Si el proceso murió, limpiar y relanzar.
- Siempre trabajar sobre una copia en `sims/`, nunca sobre el .sim original del usuario.

## Memoria

- `recipes/<verbo>-<objeto>.java`: snippet que funcionó, con cabecera de 3 líneas: qué hace,
  versión de STAR-CCM+, fecha. Guardar una receta tras CADA `run_java` que logre algo nuevo.
  Antes de escribir Java nuevo: `recipe_search` primero, `docs_search` segundo, inventar tercero.
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

(se llena solo con el uso)
