# Servidor Linux para correr STAR-CCM+ (inventario 2026-10-23)

Acceso: `ssh investigacion@172.17.76.78` con la llave `~/.ssh/id_ed25519` del PC de Sebastián
(instalada en `authorized_keys` el 2026-10-23). Sin contraseñas en este repo ni en ningún archivo.

| dato | valor |
|---|---|
| hostname | server-inv-001332 |
| sistema | Ubuntu 20.04.3 LTS, kernel 5.4.0-81, máquina virtual VMware (escritorio xrdp) |
| CPU | 16 vCPU Intel Xeon Gold 6230R @ 2,10 GHz (1 hilo por núcleo) |
| RAM | 62 GiB (61 libres) + 4 GiB swap |
| disco | 245 GB en `/`, 226 GB libres |
| GPU | ninguna (VMware SVGA): sin render por GPU; las escenas en batch van por software |
| usuario | `investigacion` (uid 1003), en el grupo `sudo`, sudo pide contraseña |
| herramientas | wget, curl, tar, python3; **sin** java, mpirun ni gcc (STAR-CCM+ trae JDK y MPI propios) |
| red | sale a Dropbox (HTTP 200) |

Comparación con el PC Windows (i5-1245U, 2P+8E, `STARCCM_NP=4`): el servidor tiene 16 núcleos reales
de servidor y 4× la RAM: bomba de 370 k celdas debería ir claramente más rápido con `-np 12…16`.

## Instalador

`~/installers/STAR-CCM-2502.0001_008_linux-x86_64-r8.tar.gz` (descargado desde Dropbox el
2026-10-23; log en `~/installers/wget.log`). Versión 2502 (en el PC hay 2410): las recetas Java y el
MCP valen igual, pero medir de nuevo tiempos y revisar que la API no cambió en lo que usan las recetas.

## Siguiente paso (no hecho)

1. Descomprimir e instalar **sin sudo** en `~/Siemens` (el instalador `.sh` acepta `-i silent
   -DINSTALLDIR=$HOME/Siemens -DINSTALLFLEX=false`), o en `/opt/Siemens` con sudo escrito por Sebastián.
2. Licencia PoD: misma clave que en el PC, en `~/.starccm-agent.env` del servidor (`STARCCM_PODKEY`,
   `STARCCM_LICPATH=1999@flex.cd-adapco.com`); el servidor necesita salida al puerto 1999 de
   `flex.cd-adapco.com`.
3. `vm/bootstrap.sh` adaptado a este host (python3 + venv + `mcp`, `STARCCM_HOME`, `STARCCM_NP=14`).
4. Opciones para el agente: MCP remoto por SSH (`mcp_server.py` corriendo en el servidor y Claude Code
   en una sesión SSH), o el MCP local lanzando `starccm+` remoto. La UI (`ui/`) sirve igual con el
   `.server.json`, `macros/` y `cases/` del host donde corra el MCP.
