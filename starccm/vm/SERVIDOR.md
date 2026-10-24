# Servidor Linux para correr STAR-CCM+ (estado 2026-10-24)

**El agente ya no usa este servidor** (ejecución remota retirada el 2026-10-24; el código sigue en los
commits `038629d`…`e163e33`). El servidor existe y tiene STAR-CCM+ 2502 instalado, pero solo se usa a mano:
para una corrida grande, Sebastián mueve el `.sim` y lo corre allí (ver «Correr a mano un .sim grande»).
El resto del archivo (inventario, instalación, medidas, riesgos) es histórico y sigue siendo válido.

Acceso: `ssh investigacion@172.17.76.78` con la llave `~/.ssh/id_ed25519` del PC de Sebastián
(instalada en `authorized_keys` el 2026-10-23). Sin contraseñas ni claves en este repo.

## Inventario

| dato | valor |
|---|---|
| hostname | server-inv-001332 |
| sistema | Ubuntu 20.04.3 LTS, kernel 5.4.0-81, máquina virtual VMware (escritorio xrdp) |
| CPU | 16 vCPU Intel Xeon Gold 6230R @ 2,10 GHz (1 hilo por vCPU) |
| RAM | 62 GiB (61 libres) + 4 GiB swap |
| disco | 245 GB en `/`; 173 GB libres tras instalar |
| GPU | ninguna (VMware SVGA): las escenas en batch van por software |
| usuario | `investigacion` (uid 1003), en el grupo `sudo`, sudo pide contraseña |
| herramientas | wget, curl, tar, python3 (3.8, sin `venv`/`pip`); **sin** java, mpirun ni gcc (STAR-CCM+ trae JDK y MPI propios) |
| solver | STAR-CCM+ **2502.0001** (build 20.02.008, doble precisión) en `/opt/Siemens/20.02.008-R8` (18 GB), `STARCCM_NP=14` |

Frente al PC Windows (i5-1245U, 2P+8E, `STARCCM_NP=4`) el servidor tiene 16 vCPU (el solver usa 14
procesos, dejando 2 al sistema) y 4× la RAM.

## Instalación (2026-10-23, Sebastián escribió el sudo)

Instalador `~/installers/STAR-CCM-2502.0001_008_linux-x86_64-r8.tar.gz` (Dropbox). El tar trae un
ELF `.aol` de 7 GB con `--help`. Línea usada (silencioso, sin licencia: la PoD se pasa al arrancar):

```bash
sudo ./STAR-CCM+2502.0001_008_linux-x86_64-2.28_clang17.0-r8.aol -i silent -DINSTALLMETHOD=custom \
  -DPRODUCTEXCELLENCEPROGRAM=decline -DINSTALLDIR=/opt/Siemens -DINSTALL_CCM=true -DINSTALL_DOC=true \
  -DINSTALL_SVIEW=false -DINSTALL_LICENSING=false -DINSTALL_JDK=true -DADDSYSTEMPATH=true
```

Lanzador `star/bin/starccm+`; JDK 21.0.4 en `/opt/Siemens/20.02.008-R8/jdk/linux-x86_64/jdk21.0.4`.
Variables en `~/.starccm-agent.env` del servidor (chmod 600, sin copia en el repo): `STARCCM_PODKEY`,
`STARCCM_LICPATH`, `STARCCM_HOME`, `STARCCM_NP=14`. No hay pasos pendientes para Sebastián.

## Decisión histórica: el MCP seguía en el PC

Ubuntu 20.04 trae Python 3.8 y el paquete `mcp` pide ≥ 3.10. `mcp_server.py` corre en Windows y, con
`where="server"`, lanza por SSH `starccm+ -server`, inyecta cada macro (por stdin) con el cliente batch
**del servidor** (el 2410 del PC no conecta a un 2502), trae `.out`, PNG y exportaciones con un `tar` y
guarda el `.sim` en el servidor. La UI no cambia: lee `.server.json`, `macros/` y `cases/` locales.
`Server::start` anuncia el host del servidor, pero el cliente batch se inyecta con `localhost:47827`
dentro de él: no se abren puertos al PC. Carpetas en el servidor: `~/starccm-agent/{sims,macros,cases}`.

## Correr a mano un .sim grande

Para corridas largas (por ejemplo la bomba, ~2× más rápido por iteración: 41,6 s frente a ~82 s por 100).
Todo lo hace Sebastián; el agente no interviene.

Antes de empezar:
- **Licencia de una sola copia**: mientras corre el solver en el servidor no se puede usar el solver del PC
  (ni el agente). Apagar antes el solver local (`server_stop`).
- **2502 abre los .sim de 2410, pero no al revés**: un `.sim` guardado en el servidor no se abre en 2410.
  Trabajar en el PC sobre otra copia o dejar el resultado solo para leerlo allí.
- Subir 158 MB tarda ~11 min (`scp` ≈0,24 MB/s): se sube una vez.

Pasos:

```bash
# 1. En el PC: subir el .sim (desde starccm/)
scp sims/<caso>.sim investigacion@172.17.76.78:~/starccm-agent/sims/

# 2. En el servidor: cargar la clave y la licencia (viven en ~/.starccm-agent.env, no en el repo)
ssh investigacion@172.17.76.78
cd ~/starccm-agent/sims
set -a; . ~/.starccm-agent.env; set +a

# 3. Lanzar y dejarlo corriendo aunque se cierre la sesión
nohup "$STARCCM_HOME/star/bin/starccm+" -batch run -np 14 -power -podkey "$STARCCM_PODKEY"   -licpath "$STARCCM_LICPATH" <caso>.sim > corrida.log 2>&1 &
tail -f corrida.log        # Ctrl+C no detiene la corrida

# 4. Al terminar, traer resultados al PC
scp investigacion@172.17.76.78:~/starccm-agent/sims/corrida.log sims/
scp investigacion@172.17.76.78:~/starccm-agent/sims/<caso>.sim sims/<caso>_servidor.sim
```

Notas:
- Línea base: `starccm+ -batch run -np 14 -power -podkey "$STARCCM_PODKEY" -licpath "$STARCCM_LICPATH" <sim>`.
  Si `starccm+` no está en el PATH, usar la ruta completa `$STARCCM_HOME/star/bin/starccm+` (como arriba).
- Qué hace `run` (iteraciones, si guarda el `.sim` al terminar) lo decide el `.sim`; comprobarlo en
  `corrida.log` antes de dar por buena la corrida.
- La clave va en la línea de comandos: la ve cualquier usuario del servidor con `ps`.
- Si hay que cortarla: `pkill -f starccm`. La PoD cobra por hora de sesión.

## Verificación (sin licencia): `bash starccm/vm/remote_check.sh`

13 comprobaciones, no arranca el solver, enmascara la clave.

| comprobación | resultado |
|---|---|
| versión | Simcenter STAR-CCM+ 2502.0001 Build 20.02.008, doble precisión |
| `javac` y javadoc | JDK 21.0.4; `$STARCCM_HOME/doc/client/html/star/…` |
| licencia PoD | `ccmppower` obtenida de `1999@flex.cd-adapco.com`; expiraba en 135 días a 2026-10-24 |
| MPI | Open MPI 4.1.5 propio, 14 rangos en 1 host |
| dependencias de sistema | nada que instalar: las bibliotecas vienen en el árbol de la instalación y las del sistema ya están; glibc 2.31 ≥ 2.28 |

## Tiempos medidos

Sim nueva vacía, `-np 14` (2026-10-24):

| paso | segundos |
|---|---|
| `starccm+ -server …` hasta `Server::start` | 16,6 |
| inyección de macro trivial (`-batch Ping.java -noexit`) | 5,0 |
| apagado con macro `sim.kill();` | ~5, sin procesos restantes |
| `scp` de `cursocfturbo.sim` (158 MB) PC → servidor | **694** (≈0,24 MB/s, hash idéntico) |

Bomba `cursocfturbo` con el `.sim` ya en el servidor, contra el PC (np 4):

| paso | servidor (np 14) | PC (np 4) |
|---|---|---|
| `server_start` hasta `Server::start` + autosave off | 26 s | 32 s en frío |
| `inspect("regions")` (primera macro: carga módulos) | 18 s | 50–75 s |
| 100 iteraciones de la bomba (tras calentar) | **41,6 s** | ~82 s |
| `export_scene` (PNG traído al PC por tar/SSH) | 25 s | ~11 s |
| guardar 158 MB y apagar | 50 s | ~15 s |

## Cuándo conviene Local o Servidor (histórico)

| tarea | elegir | por qué |
|---|---|---|
| iterar, mallar, curvas H-Q, cualquier corrida larga | **Servidor** | ~2× más rápido por iteración (41,6 s frente a ~82 s por 100) |
| escenas, `inspect`, consultas y arreglos cortos | **Local** | el servidor paga ~5 s extra por macro (SSH + cliente remoto) y el PNG viaja de vuelta |
| caso nuevo con un `.sim` grande que aún no está en el servidor | Local, o aceptar la subida | 158 MB = ~11 min de `scp` (se hace una vez) |
| GUI de STAR-CCM+ | **Local** | «Abrir en STAR-CCM+» solo existe en el PC |

## Reglas de la ejecución remota (retirada)

- El `.sim` se sube SOLO si falta en el servidor o si el del PC es más nuevo (con copia `.antes` del
  remoto). Las entradas que una macro cita (CAD en `cases/<caso>/cad/`) se suben solas si faltan o cambiaron.
- Macros (KB), PNG y CSV viajan en segundos. Traer el `.sim` de vuelta tardaría lo mismo o más: se guarda
  en el servidor y se baja solo bajo demanda.
- Apagado por inactividad a los 30 min (también remoto); un solo solver vivo a la vez.

## Licencia PoD

Es por periodo y de una sola copia (según Sebastián): solo cabe un solver con licencia a la vez, así que
no se puede correr una simulación local y otra en el servidor al mismo tiempo, ni dejar una sesión vieja
viva mientras se arranca otra. PoD cobra por hora de sesión: apagar el solver al terminar.

## Riesgos conocidos

| riesgo | detalle |
|---|---|
| clave PoD visible | va en `-podkey` en la línea de comandos: en el servidor la ve cualquier usuario con `ps`. Es igual en Windows; tenerlo en cuenta si el servidor es compartido |
| `.sim` pisado | la primera versión comparaba solo el tamaño y pisó un `.sim` guardado en el servidor con el del PC (20 iteraciones perdidas). Ya solo sube si el del PC es más nuevo, con copia `.antes` |
| subida lenta | ≈0,24 MB/s PC → servidor: 158 MB = 694 s |
| solver huérfano | si el chat se desconecta, una macro en curso (p. ej. una malla) sigue en el solver y cobra; `server_stop()` lo apaga. Desde f953f56 el chat sobrevive a cerrar la pestaña |
| SSH sin `HOME` o con stdin | el servidor de la UI no tiene `HOME` y `ssh` buscaba la llave en `$HOME/.ssh`: fallaba en silencio y la UI daba el solver por muerto. Corregido (`_ssh_env()`, stdin vacío) |
| 2410 vs 2502 | el PC y el servidor usan versiones distintas: recetas y MCP valen igual, pero una receta nueva debe probarse en la versión donde va a correr |
| fallo transitorio de MPI | tras apagar otra sesión sin guardar, `server_start` puede fallar con `MPI_Init_thread`; reintentar |
