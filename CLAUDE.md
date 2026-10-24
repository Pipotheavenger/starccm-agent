# starccm-agent

Dos agentes independientes para turbomáquinas, cada uno en su carpeta con su propio `CLAUDE.md`,
su MCP, su venv y su memoria. No comparten código ni se llaman entre sí.

| carpeta | qué es | estado |
|---|---|---|
| [`starccm/`](starccm/CLAUDE.md) | Agente que opera Simcenter STAR-CCM+ (2410 en este PC o 2502 en el servidor Linux, a elección): malla, física, corrida, altura, torque, eficiencia; interfaz web `starccm/ui/` (puerto 8767) con visor 3D, Fronteras, convergencia en vivo y chat | MCP verificado con el solver real, local y remoto; bomba cursocfturbo convergida; caso nuevo desde la página hasta la simulación |
| [`cfturbo/`](cfturbo/CLAUDE.md) | Agente de diseño 1D con CFturbo 2026 + interfaz web controladora con visor 3D | terminado, evaluado 9/10 |

Reglas comunes:
- Al trabajar en uno, leer **su** `CLAUDE.md` entero primero; manda sobre este archivo.
- Claves de licencia solo en archivos `.env` ignorados por git. Nunca en código, logs ni commits.
- Mensajes al usuario en español, cortos, números en tablas. Lo mínimo que funcione.
- Cada carpeta deja un check ejecutable: `python mcp_server.py --selftest`.
- Los MCP de ambos se registran en el `.mcp.json` de esta raíz (ignorado por git; ver cada README).

Estado al 2026-10-24 (starccm):

| tema | estado |
|---|---|
| solver local | 2410, 4 procesos; 100 iteraciones de la bomba ~82 s |
| solver remoto | 2502 en el servidor Linux, 14 procesos, por SSH; 100 iteraciones 41,6 s (`starccm/vm/SERVIDOR.md`) |
| interfaz | Local/Servidor, «＋ Caso nuevo», Fronteras, Gráficos en vivo, chat que sobrevive a recargar |
| licencia PoD | por periodo y de una sola copia (Sebastián): un solo solver a la vez, local o remoto |
| por probar | `/api/open_gui`; flujo completo desde una geometría nueva sin nombres de cara |
