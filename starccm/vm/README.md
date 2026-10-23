# vm

Plan original: correr el agente en una MV Linux (Rocky/RHEL 9) con STAR-CCM+ 2606 y licencia PoD.
Quedó aparcado el 2026-10-23 porque STAR-CCM+ 2410 ya está instalado en el PC Windows y el MCP
corre ahí. `bootstrap.sh` deja la MV lista (paquetes, STAR-CCM+, prueba de licencia, venv, `.env`)
cuando toque; el `mcp_server.py` es el mismo, solo cambian `STARCCM_HOME` y el lanzador
(`star/bin/starccm+` sin `.bat`).
