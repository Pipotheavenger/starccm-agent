# starccm-agent

Dos agentes independientes para turbomáquinas, cada uno en su carpeta con su propio `CLAUDE.md`,
su MCP, su venv y su memoria. No comparten código ni se llaman entre sí.

| carpeta | qué es | estado |
|---|---|---|
| [`starccm/`](starccm/CLAUDE.md) | Agente que opera Simcenter STAR-CCM+ (2410, en este PC): malla, física, corrida, altura, torque, eficiencia | MCP + selftest listos; pendiente clave PoD para probar contra el solver real |
| [`cfturbo/`](cfturbo/CLAUDE.md) | Agente de diseño 1D con CFturbo 2026 + interfaz web controladora con visor 3D | terminado, evaluado 9/10 |

Reglas comunes:
- Al trabajar en uno, leer **su** `CLAUDE.md` entero primero; manda sobre este archivo.
- Claves de licencia solo en archivos `.env` ignorados por git. Nunca en código, logs ni commits.
- Mensajes al usuario en español, cortos, números en tablas. Lo mínimo que funcione.
- Cada carpeta deja un check ejecutable: `python mcp_server.py --selftest`.
- Los MCP de ambos se registran en el `.mcp.json` de esta raíz (ignorado por git; ver cada README).
