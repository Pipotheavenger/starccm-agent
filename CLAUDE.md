# starccm-agent

Agente que opera Simcenter STAR-CCM+ para turbomáquinas. Todo vive en [`starccm/`](starccm/CLAUDE.md), con su
`CLAUDE.md`, su MCP, su venv y su memoria. Al trabajar aquí, leer **ese** `CLAUDE.md` entero primero; manda sobre
este archivo.

| carpeta | qué es | estado |
|---|---|---|
| [`starccm/`](starccm/CLAUDE.md) | Agente que opera Simcenter STAR-CCM+ (2410, solo en este PC, 4 procesos): malla, física, corrida, altura, torque, eficiencia; interfaz web `starccm/ui/` (puerto 8767) con visor 3D, Fronteras, convergencia en vivo y chat | MCP verificado con el solver real, solo local (remoto retirado el 2026-10-24; el servidor Linux es opción manual: `starccm/vm/SERVIDOR.md`); bomba cursocfturbo convergida; caso nuevo por etapas desde la página, con preguntas de la IA con opciones |

El agente hermano de diseño 1D con CFturbo está en su propio repositorio desde el 2026-10-24:
[`cfturbo-agent`](https://github.com/Pipotheavenger/cfturbo-agent), clonado en `Documentos\cfturbo-agent`
(entorno con su `bootstrap.ps1`, interfaz en el puerto 8765). No comparten código ni se llaman entre sí. El
historial de la antigua carpeta `cfturbo/` sigue en este repositorio: `git log -- cfturbo/`.

Reglas:
- Claves de licencia solo en archivos `.env` ignorados por git. Nunca en código, logs ni commits.
- Mensajes al usuario en español, cortos, números en tablas. Lo mínimo que funcione.
- Check ejecutable: `starccm\.venv\Scripts\python starccm\mcp_server.py --selftest`.
- El MCP se registra en el `.mcp.json` de esta raíz (ignorado por git; ver `starccm/README.md`).

Estado al 2026-10-24:

| tema | estado |
|---|---|
| solver local | 2410, 4 procesos; 100 iteraciones de la bomba ~82 s |
| servidor Linux | 2502, solo a mano (`starccm/vm/SERVIDOR.md`); 100 iteraciones 41,6 s |
| interfaz | «＋ Caso nuevo», geometría 3D al importar, Fronteras, 3D y gráficos en vivo, informe PDF, archivo .sim, mensajes a la IA mientras trabaja |
| licencia PoD | por periodo y de una sola copia (Sebastián): un solo solver a la vez |
| por probar | `/api/open_gui` |
