# starccm

Agente que opera Simcenter STAR-CCM+ (2410, instalado en este PC) desde Claude Code vía MCP.
El brief completo, el flujo de bomba y las lecciones están en [CLAUDE.md](CLAUDE.md).

```
starccm/
├── CLAUDE.md          brief del proyecto (manda sobre todo lo demás)
├── PRIMER-PROMPT.md   prompts para arrancar las sesiones de trabajo
├── mcp_server.py      el MCP (11 tools) + --selftest
├── .env.example       variables: clave PoD, puerto, núcleos (copiar a .env, que no va a git)
├── .mcp.json          registro del MCP para Claude Code si se abre esta carpeta sola
├── recipes/           snippets Java que ya funcionaron (memoria del agente)
├── cases/             un directorio por caso: cad/, reportes, imágenes, RESUMEN.md
├── sims/              .sim de trabajo y logs del servidor (no va a git)
├── macros/            macros inyectadas con su salida (no va a git)
├── tests/             fake_starccm.py: starccm+ falso del selftest
└── vm/                bootstrap.sh para la MV Linux (futuro)
```

## Puesta en marcha

1. `python -m venv .venv` y `.venv\Scripts\pip install mcp` (ya hecho en este PC).
2. Copiar `.env.example` a `.env` y poner la clave Power-on-Demand en `STARCCM_PODKEY`.
3. `.venv\Scripts\python mcp_server.py --selftest` → «todo en verde» (no necesita licencia).
4. El MCP está registrado en el `.mcp.json` de la raíz del repo (servidor `starccm`). Reiniciar la
   sesión de Claude Code para que aparezcan las tools `server_start`, `run_java`, etc.

## Primera comprobación con el solver real

En Claude Code: `server_start()` → `run_java('sim.println("PING");')` → `server_stop()`.
Anotar en CLAUDE.md > Lecciones el tiempo de arranque y si la inyección `-host … -batch … -noexit`
funciona en 2410.
