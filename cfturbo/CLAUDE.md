# cfturbo-agent

Agente que diseña impulsores y volutas de bombas y turbinas con CFturbo en lenguaje natural.
CFturbo es el generador paramétrico de geometría. Claude decide qué parámetros mover y lee
qué pasó. La evaluación CFD la hace el agente hermano de STAR-CCM+ (carpeta `..`, en la MV Linux).

## Cómo se opera CFturbo (no hay API)

- Solo modo batch: `cfturbo.exe -batch archivo.cft-batch [-verbose] [-log archivo.log]`.
- El `.cft-batch` es XML: `<CFturboFile><CFturboBatchProject InputFile="bomba.cft"><Updates>…</Updates>
  <Output>…</Output><BatchAction Name="Export"/><BatchAction Name="Save"/>`.
- `Updates` lleva los parámetros a cambiar. Solo se pueden cambiar los que en la GUI están
  editables (p.ej. dimensiones principales requieren desactivar el cálculo automático).
  Si pides un valor fuera de rango, CFturbo lo corrige solo; el `.cft-res` trae el valor realizado.
- `Output` trae valores derivados (área de garganta mínima, ángulos calculados). Sirven de restricción.
- Export: interfaz `General` (STEP/IGES según lo configurado en el proyecto), `StarCCM`, `OpenFOAM`,
  `Report`, `PerformanceData`. La configuración de cada interfaz se guarda en el `.cft`, no en el batch.
- La plantilla `.cft-batch` se genera UNA vez desde la GUI (PROJECT > Batch mode/Optimization) con
  los parámetros activados y con alias. Es el "esquema" que el agente lee con `cft_params`.
- Crear una bomba desde cero (punto de diseño nuevo) no se puede en batch. Eso lo hace el usuario
  en la GUI en 5 minutos, o el agente edita el `.cft` directamente (es XML) bajo su responsabilidad.

## MCP: `mcp_server.py` (ya escrito, selftest incluido)

| tool | qué hace |
|---|---|
| `cft_params(batch_template)` | lista parámetros: ruta, alias, valor, rango, unidad |
| `cft_run(batch_template, updates, name, export_interface, save_cft)` | corre batch, devuelve realizados, correcciones, Output, exportados |
| `cft_log(run_dir)` | cola del log de CFturbo |
| `cft_recipe_search` / `cft_recipe_save` | memoria |

Cada corrida vive en `work/<name>_<timestamp>/` con su batch, res, log, .cft y exportes.
`python mcp_server.py --selftest` debe pasar siempre antes de un commit.

## Flujo estándar

1. Usuario da punto de diseño: Q, H, n, fluido, tipo (centrífuga, mixta, turbina).
2. Si no hay `projects/<bomba>/<bomba>.cft-batch`, pedir al usuario que lo cree en la GUI
   (bomba base + Batch mode/Optimization + aliases). No intentar sustituirlo.
3. `cft_params` para ver qué hay. Resumir al usuario en una tabla: alias, valor, rango.
4. Diseño: proponer cambios con criterio de turbomáquinas (Euler, ángulos, número de álabes,
   b2/d2, área de garganta) y correr `cft_run` con export `General` (STEP) o `StarCCM`.
5. Reportar: realizados vs pedidos, correcciones de CFturbo, Output, ruta del export.
6. Si hay MV con STAR-CCM+: entregar el STEP o el caso al agente CFD y cerrar el loop con sus
   resultados (H, eficiencia). Hasta entonces, usar `PerformanceData` y `Report` de CFturbo
   como estimación 1D.
7. Guardar receta por cada combinación que funcionó o lección aprendida.

## Reglas

- Nunca editar el `.cft` original del usuario; `cft_run` guarda copias en `work/`.
- Si CFturbo corrige un valor, decirlo explícitamente; no asumir que se aplicó lo pedido.
- Rutas de Windows con `\\` o raw strings; la plantilla referencia el `.cft` en relativo, el
  servidor lo resuelve a absoluto.
- Español, corto, números en tablas. Estilo mínimo: un archivo, sin clases de más.

## Lecciones

(se llena con el uso)
