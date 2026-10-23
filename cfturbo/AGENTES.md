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
