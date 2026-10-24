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

## Verificación del servidor (2026-10-24, solver real, sin sudo)

Comprobable en cualquier momento y sin licencia: `bash starccm/vm/remote_check.sh` (13 comprobaciones,
no arranca el solver; enmascara la clave).

| comprobación | resultado |
|---|---|
| instalador | terminó (sin `install.aol` vivo); `/opt/Siemens` = 18 GB; disco libre 173 GB |
| versión | Simcenter STAR-CCM+ 2502.0001 Build 20.02.008, doble precisión (linux-x86_64-2.28/clang17.0-r8) |
| `javac` | `/opt/Siemens/20.02.008-R8/jdk/linux-x86_64/jdk21.0.4/bin/javac` (JDK 21.0.4) |
| javadoc | `$STARCCM_HOME/doc/client/html/star/…` |
| licencia PoD | `ccmppower` obtenida de `1999@flex.cd-adapco.com`; expira en 135 días |
| MPI | Open MPI 4.1.5 propio, 14 rangos en 1 host |
| dependencias de sistema | ninguna que instalar: `libgfortran`, `libGLEW`, `libjpeg.so.62`, `libhwloc`, `libtbb`, `libhdf5`, Boost, Poco… vienen en el árbol de la instalación; las del sistema (`libGL`, `libGLU`, `libX11`, `libxcb`, `libfontconfig`, `libnuma`) ya están. glibc 2.31 ≥ 2.28 requerido. `check_dependencies` no corre (pide `python` sin versión; irrelevante) |

Tiempos medidos (`-np 14`, sim nueva vacía, comandos de `~/.starccm-agent.env`):

| paso | segundos |
|---|---|
| `starccm+ -server …` hasta `Server::start` | 16,6 |
| inyección de macro trivial (`-host localhost:47827 -batch Ping.java -noexit`), imprime `PING` | 5,0 |
| apagado con macro `sim.kill();` | ~5, sin procesos starccm restantes (0) |
| `scp` de `cursocfturbo.sim` (158 MB) PC → servidor | **694** (≈0,24 MB/s, hash idéntico) |

Consecuencias para el MCP remoto:
- El `scp` de un .sim grande es el cuello de botella (11,6 min): subir el .sim UNA vez y dejarlo en
  `~/starccm-agent/sims/` (ya está `cursocfturbo.sim`); no copiarlo en cada `server_start`.
  Macros (KB), PNG y CSV viajan en segundos. Traer el .sim de vuelta tardaría lo mismo o más: guardar en
  el servidor y bajar solo bajo demanda.
- `Server::start` anuncia el host como `server-inv-001332.uniandes.edu.co:47827`; el cliente batch se
  inyecta con `localhost:47827` dentro del servidor, sin abrir puertos al PC.
- Carpetas creadas: `~/starccm-agent/{sims,macros,cases}`. Log de la prueba: `sims/prueba.server.log`.
- Sin sudo no falta nada: no hay pasos pendientes para Sebastián.
