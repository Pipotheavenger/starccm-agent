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

## Instalación (2026-10-23, Sebastián escribió el sudo)

El tar trae un ejecutable ELF `STAR-CCM+2502.0001_008_linux-x86_64-2.28_clang17.0-r8.aol` (7 GB) con
`--help`. Línea usada (modo silencioso, sin licencia configurada: la PoD se pasa al arrancar):

```bash
sudo ./STAR-CCM+2502.0001_008_linux-x86_64-2.28_clang17.0-r8.aol -i silent -DINSTALLMETHOD=custom \
  -DPRODUCTEXCELLENCEPROGRAM=decline -DINSTALLDIR=/opt/Siemens -DINSTALL_CCM=true -DINSTALL_DOC=true \
  -DINSTALL_SVIEW=false -DINSTALL_LICENSING=false -DINSTALL_JDK=true -DADDSYSTEMPATH=true
```

Queda en `/opt/Siemens/20.02.008-R8/STAR-CCM+20.02.008-R8` (lanzador `star/bin/starccm+`, JDK en
`/opt/Siemens/20.02.008-R8/jdk/…`). Variables en `~/.starccm-agent.env` del servidor (chmod 600, sin
copia en el repo): `STARCCM_PODKEY`, `STARCCM_LICPATH`, `STARCCM_HOME`, `STARCCM_NP=14`.

## Decisión: el MCP sigue en el PC; el servidor solo corre STAR-CCM+

Ubuntu 20.04 trae Python 3.8 sin `venv`/`pip`, y el paquete `mcp` pide ≥ 3.10: montar Python en el
servidor exige sudo o `uv`. No hace falta: `mcp_server.py` corre en Windows y, con
`STARCCM_RUN_HOST=server`, lanza por SSH `starccm+ -server` en el servidor, copia cada macro con `scp`,
la inyecta con el cliente batch **del servidor** (misma versión 2502; el cliente 2410 del PC no puede
conectarse a un servidor 2502) y trae de vuelta `.out`, PNG y exportaciones. La UI no cambia: sigue
leyendo `.server.json`, `macros/` y `cases/` locales. Pendiente de implementar y medir.
