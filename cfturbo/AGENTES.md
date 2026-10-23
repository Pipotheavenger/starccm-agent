# Arquitectura agéntica del controlador CFturbo

Pedida por Sebastián el 2026-10-23. Objetivo: iterar el programa (`mcp_server.py`, `ui/`) hasta que
la evaluación end-to-end dé **≥ 9/10 en diseño y ≥ 9/10 en funcionalidad**, dejando una versión
estable y escalable. Todo vive en esta carpeta.

## Roles

| Rol | Modelo | Qué hace | Entrega |
|---|---|---|---|
| Orquestador | Fable (sesión principal de Claude Code) | planifica rondas, lanza agentes, integra, commitea | commits por ronda |
| Director / evaluador E2E | Fable | arranca el servidor, prueba TODAS las funciones con navegador y API, puntúa con la rúbrica, lista defectos con evidencia | `agents/out/eval_<ronda>.md` |
| Diseñador UX/UI | Opus | propone layout y componentes concretos (inspiración: tableros tipo Pinterest para galería de corridas/versiones, módulos de software CAE/CFD: árbol de proyecto, propiedades, visor, consola) | `agents/out/ux_<ronda>.md` (+ CSS/HTML si procede) |
| Programador | Opus | implementa el spec UX y corrige los defectos del evaluador; selftest verde; sin romper el MCP | código + `agents/out/dev_<ronda>.md` |
| Documentador | Opus | CLAUDE.md, PRIMER-PROMPT.md, recetas, README de ui/ al día con lo implementado | docs + `agents/out/docs_<ronda>.md` |
| Explorador (paralelo) | Opus | "bomba/turbina desde cero sin plantilla": experimenta con el XML y CFturbo en carpeta temporal | `recipes/exploracion-desde-cero.md` |

## Bucle

```
ronda k:
  UX(k) y Eval(k-1 o base) en paralelo  ->  Programador(k)  ->  Docs(k) ‖ Eval(k)
  si diseño ≥ 9 y funcionalidad ≥ 9: fin.  si no y k < 4: ronda k+1 con los defectos de Eval(k)
```

## Rúbrica del evaluador (0-10 cada bloque, con evidencia: capturas en agents/out/)

Diseño: jerarquía visual clara · layout sin espacio desperdiciado y sin perder opciones · consistencia
(tipografía, espaciado, color, estados) · descubribilidad (qué hace cada cosa sin leer docs) ·
responsive (≥1100 px tres columnas, <1100 px apilado usable) · visor 3D protagonista y legible ·
retroalimentación de estado (cargando, corriendo, error) · accesibilidad básica (contraste, foco, teclado).

Funcionalidad (todas deben funcionar de verdad, no solo existir): selector de proyecto e info · tabla
de parámetros base/corrida/nuevo con nq en vivo · Ejecutar en CFturbo (corrida real, ~30 s) · partir de
corrida seleccionada · AutoUpdate y ext_outlet · hitos, avisos, correcciones · archivos con descarga y
abrir carpeta · Guardar versión y galería de versiones · visor (piezas, tapas, orbitar, encuadre, cambio de
corrida) · chat con Claude Code real (resumen, variante, regla de corregir avisos) · Detener chat · nueva
conversación · estados de error (CFturbo ocupado, chat ocupado, sin login) · selftest y MCP por stdio ·
sin errores en consola del navegador · comportamiento con 0 corridas y con 20 corridas.

## Reglas para todos los agentes

- Español en la interfaz y en los documentos. Código comentado donde no sea obvio.
- Estilo del proyecto: lo mínimo que funcione, sin frameworks de agentes ni build steps. three.js por
  CDN está bien. Se permite dividir `ui/index.html` en `ui/index.html` + `ui/app.js` + `ui/style.css`.
- No tocar `projects/`. Las corridas van a `%TEMP%\cfturbo-agent`; las versiones a `versions/`.
- Servidor de desarrollo propio en el puerto **8766** (`.venv\Scripts\python -m uvicorn --app-dir . ui.server:app --port 8766`);
  el 8765 lo usa el preview del orquestador. Una corrida de CFturbo a la vez por servidor.
- `python mcp_server.py --selftest` debe pasar antes de entregar. No hacer commits: los hace el orquestador.
- Cada agente escribe su entrega en `agents/out/` con: qué hizo, qué no pudo, qué recomienda.

## Historial

Todo el 2026-10-23. Notas del evaluador (diseño / funcionalidad):

| ronda | entregas | notas | qué cambió |
|---|---|---|---|
| base | `eval_0.md` (+ `eval0/`) | 5 / 7 | línea base: < 1100 px inutilizable, layout sin jerarquía |
| 1 | `ux_1.md`, `dev_1.md`, `docs_1.md`, `eval_1.md` | 7 / 8 | layout CAE, galería con miniaturas, comparar A/B, candado entre procesos |
| 2 | `ux_2.md`, `dev_2.md`, `eval_2.md` | 9 / 9 | galería sin solapes, candado global (`running.lock`), sondeo único, tema claro. **Objetivo alcanzado** |
| 3 | `ronda3_alcance.md`, `dev_3.md` | — | pedido de Sebastián + Explorador: ángulos β y espesor, reporte, curvas, borrar corridas, bomba nueva por semejanza (`cft_new`, «＋ Nueva»), limpieza de letreros, D2-1…D2-8 |
| optimización | `opt_final.md` | — | STL binario con caché `.visor/`, `/api/poll` con ETag/304, fila ligera, caché de `run.json` por mtime, `timing`, errores JSON, cierre limpio de procesos, selftest de bordes y HTTP |
| docs final | `docs_final.md` | — | CLAUDE.md, PRIMER-PROMPT.md, READMEs al día; inconsistencias código/doc para el evaluador |
| eval final | pendiente (en curso) | pendiente | evaluación E2E sobre main con ronda 3 + optimización |

En paralelo: el Explorador dejó `explora/desde_cero.py` y `recipes/exploracion-desde-cero.md` (base de `cft_new`).

### Cómo relanzar una ronda

1. Partir de main limpio y `python mcp_server.py --selftest` en verde.
2. Escribir el alcance en `agents/out/ronda<k>_alcance.md` (pedido del usuario + defectos `D<k-1>-n` del
   último `eval_<k-1>.md`).
3. Lanzar en paralelo UX(k) (si hay diseño que tocar) y, si no existe, Eval(k-1); luego Programador(k) en
   un worktree propio (`isolation: worktree`, servidor en 8766), con el alcance, el eval y esta hoja.
4. El orquestador revisa `dev_<k>.md`, corre el selftest, fusiona a main y commitea.
5. Docs(k) y Eval(k) en paralelo sobre main (el evaluador en 8765 o un puerto libre, con
   `CFTURBO_WORKDIR`/`CFTURBO_VERSIONS` aislados para los casos de 0 y 20 corridas). Una corrida de
   CFturbo a la vez en el PC: el candado global hace esperar a quien llegue segundo.
6. Si diseño ≥ 9 y funcionalidad ≥ 9 y no hay defectos P1: fin. Si no, ronda k+1 con los defectos.
