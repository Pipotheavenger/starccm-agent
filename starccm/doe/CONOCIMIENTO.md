# doe/: base de conocimiento del DOE distribuido

DOE de STAR-CCM+ con Design Manager: una geometría por worker y ese worker corre todos sus caudales. Esta máquina
(172.17.77.72) orquesta. Todo conocimiento nuevo del DOE va aquí: una línea por lección, con fecha. Lo general de
STAR-CCM+ (API Java, malla, física) sigue en `../CLAUDE.md` y en `../recipes/`.

## Máquinas (inventario del 2026-11-04)

| IP | host | papel | núcleos | RAM | C: libre | STAR-CCM+ |
|---|---|---|---|---|---|---|
| 172.17.77.72 | SERVER-INV-0013 | orquestador (no corre el DOE) | 16 | 64 GB | 70 GB | 2410 (19.06.009-R8), sin entrada en Uninstall |
| 172.17.76.244 | DESKTOP-DLGAQ3O | worker | 48 | 128 GB | 155 GB | 2602 (21.02.007-R8) |
| 172.17.76.245 | DESKTOP-4NADU3O | worker | 48 | 128 GB | 155 GB | 2602 |
| 172.17.77.9 | DESKTOP-EI9O12J | worker | 48 | 128 GB | 147 GB | 2602 |
| 172.17.76.222 | DESKTOP-8TOHOAC | worker | 48 | 128 GB | 155 GB | 2602 |

Todas Xeon Gold 6230R y llegan a `flex.cd-adapco.com:1999`. D: de los workers: 5 GB llenos, no sirve.

## Decisiones (Sebastián)

| fecha | decisión |
|---|---|
| 2026-11-04 | Workers con la 2602 que ya tienen (`C:\Program Files\Siemens\21.02.007-R8`); no instalar ni desinstalar. Un `.sim` de 2602 no abre en la 2410 de la .72. |
| 2026-11-04 | Disco de trabajo `C:\trabajo`; 46 procesos por job; 1 job por worker. |
| 2026-11-09 | **Solo se guarda el `.sim` de Qn** (opción 3; las VM se congelaban, sospecha: datastore lleno). Los otros 9 puntos se borran al entregar; queda todo en `resultados.json` v2, el Excel y `<id>_informe.txt`. Un punto se reproduce corriendo base.sim (en la .72) con su Flujo. Las 28 entregadas antes se re-extraen (`extraer.ps1`) y luego se podan. |
| 2026-11-04 | 44 procesos desde la bomba 5 (G001–G004 siguen con 46). `explorer.exe` matado en los 4 workers (sesión RDP desconectada de `starccm`; no se reinicia solo: al entrar por RDP, Ctrl+Alt+Fin → Administrador de tareas → Ejecutar `explorer`, o cerrar sesión y volver a entrar). |

## Convenciones

- SSH: `ssh -o BatchMode=yes starccm@IP` (llave, usuario administrador, Windows en inglés). La consola remota es
  `cmd`: mandar PowerShell siempre con `-EncodedCommand` (base64 UTF-16LE) o subir un `.ps1` con `scp` y
  `-File`. Llave pública de admin en `C:\ProgramData\ssh\administrators_authorized_keys`.
- Lanzador: `C:\Program Files\Siemens\21.02.007-R8\STAR-CCM+21.02.007-R8\star\bin\starccm+.bat`.
- Licencia: `C:\trabajo\.env` en cada worker (copia del `.env` de `Desktop\Geometrias_Prueba` con `STARCCM_NP=46`).
  Los scripts la leen ahí; nunca imprimirla. Comprobar con `Select-String -SimpleMatch` que no quedó en los logs.
- Apagar el solver = matar los procesos con `ExecutablePath` bajo `STAR-CCM+*`, **excepto `hydra_service.exe`**
  (servicio MPI de Windows, siempre vivo). Un servidor de 46 procesos son ~97 procesos.

## Flujo de una geometría (`doe.py`, en la .72)

| paso | comando | qué hace |
|---|---|---|
| rango | `python doe/rango.py` | 10 caudales de 0,1 m³/h a Q(H_CFturbo = 25 % de H en Qn), Qn exacto incluido; orden Qn → bajos → altos |
| preparar | `doe.py preparar G001 --worker IP` | `C:\trabajo\DOE-2026-11_PAT1\<id>\`: base.sim (el `CFD\<nombre>.sim` del lote), macros con valores, compila con javac |
| crear | `doe.py crear G001` | `starccm+ -dmproject -batch crear_estudio.java` → `<id>.dmprj` (Sweep, Flujo DISCRETE, respuestas, 46 procesos, reuso) |
| lanzar | `doe.py lanzar G001` | `-batch run <id>.dmprj -dmnoshare -passtodesign` con `Win32_Process.Create` (sobrevive al SSH) |
| estado | `doe.py estado` / `doe.py tablero` | `scripts/estado.ps1` en cada worker → `doe/estado.json`, `doe/eventos.log`; tablero en http://localhost:8770/tablero.html |
| traer | `doe.py traer G001` | resultados.json + reports/ de cada diseño → `<carpeta bomba>\DOE\<id>_barrido.xlsx` y `<id>_informe.txt` (estado OK/AVISO/FALLA por punto); imágenes quedan en el worker |
| podar | `doe.py podar G001` | tras entregar: borra todos los `.sim` salvo el de Qn (y `_cache`, `*.sim~`); se niega si no encuentra el de Qn |
| re-extraer | automático (fase `extraer`) | entregadas con `resultados.json` v1: `scripts/extraer.ps1` abre cada .sim con `despues.java` (GUARDAR=false), luego traer + podar; `v2: true` en plan.json. Va antes que la cola en cada worker |

Por diseño (macros de DM): `antes_correr.java` (BEFORE_RUNNING) pone Maximum Steps = iteración actual + 1500 y apaga los
demás criterios; `despues.java` (BEFORE_RESULTS) deja `resultados.json`, `reports/*.csv` e `images/*.png` en la carpeta
del diseño (`.mdxruntime\<proyecto>_<fecha>\Barrido\Design_N\`).

## Scripts (`scripts/`)

| script | qué hace | uso |
|---|---|---|
| `inv.ps1` | inventario JSON: CPU, RAM, C:/D:, STAR-CCM+ del registro Uninstall, flex:1999 | `powershell -EncodedCommand` por SSH |
| `lic_test.ps1` | servidor vacío con PoD, espera `Server::start`, apaga solo el solver, enmascara la clave en el log | `scp` a `C:\trabajo\` y `-File … [-Hold s]` |
| `star.ps1` | lanza starccm+ con la licencia del `.env` (`-Design` añade `-dmnoshare -passtodesign`); al terminar enmascara | por `doe.py` |
| `compilar.ps1` | javac de la 2602 contra `star\lib\java\platform\modules\ext\*` | por `doe.py preparar` |
| `estado.ps1` | JSON del worker: procesos, CPU, disco, log de DM, cada diseño (iteración, H/M/η, resultados) | `C:\trabajo\estado.ps1` |
| `render.ps1` | escenas de cada punto desde su .sim (fuera de DM, tiempo límite) → `render_fin.txt` | `doe.py` fase `render` |
| `extraer.ps1` | re-extrae resultados.json v2 de cada punto (np 8, 900 s, 2 intentos) → `extraer_fin.txt` | `doe.py` fase `extraer` |
| `enmascarar.ps1` | quita la clave de los logs bajo una carpeta | lo llaman `star.ps1` y `estado.ps1` |

## Lecciones

- 2026-11-04 · Licencia PoD: **una copia por máquina**, no una sola copia global. .244 y .245 a la vez: cada uno
  `1 copy of ccmppower checked out`, ~80 s solapados. Arranque de servidor vacío de 46 procesos: 51–63 s.
- 2026-11-04 · La PoD actual dice `Feature ccmppower expires in 9 days` (vence ≈ 2026-11-13): renovarla antes de un DOE largo.
  2026-11-11: ya renovada, los logs PAT de la .245 dicen `expires in 117 days` (≈ 2027-03-08).
- 2026-11-04 · Los workers solo abrían RDP (sin ping, 22 ni 445) hasta que Sebastián montó OpenSSH.
- 2026-11-04 · Un comando PowerShell con `|` mandado por SSH lo parte `cmd` («'Out-Null' is not recognized»): usar `-EncodedCommand`.
- 2026-11-04 · Los workers tienen ExecutionPolicy Restricted: `& script.ps1` no hace nada en silencio. Siempre `-ExecutionPolicy Bypass`.
- 2026-11-04 · DM 2602: el parámetro global no entra solo al estudio («Named object "Flujo" does not exist»). Está dentro
  de la carpeta `Simulation Parameters` de `ref.getReferenceParameterManager()`: recorrer `getChildren()` y
  `pm.addReferenceParameter(refQ)`. Las respuestas igual: `rm.addReferenceReport` por cada `MdxReferenceReport`.
- 2026-11-04 · DM: sin `refQ.setSimulationEffect(SimulationEffect.SOLVER)` el parámetro queda «Unknown», DM supone que
  afecta a la malla y no reusa malla entre diseños. Aun con SOLVER, el Design 1 remalla (ConservativeMapping de la solución).
- 2026-11-04 · **DM escribe la clave PoD en claro en cada `Design_N.log`** (la línea de lanzamiento del diseño).
  `enmascarar.ps1` la quita (al terminar y en cada lectura de estado, logs quietos ≥ 60 s).
- 2026-11-04 · DM borra el historial del diseño DESPUÉS de la macro BEFORE_RUNNING (Clear History): el contador vuelve
  a 0 y los campos se conservan (interpolados de la base). Con Maximum Steps = it_sim + 1500 el Design 1 iba a 3500.
  Ahora Maximum Steps = 1500 absoluto y `setClearHistoryEnabled(true)` explícito.
- 2026-11-04 · Velocidad en un worker (46 procesos, ~1,5 M celdas): ~0,66 s/iteración → 1500 it ≈ 17 min por punto.
  En el Design 1 DM solo remalla las extensiones (las operaciones de malla del lote) y mapea la solución.
- 2026-11-04 · **DM borra la carpeta de cada diseño al terminar** («Cleaning up temporary files»): solo deja
  `<proyecto>\<proyecto>\Barrido\Design_N\Design_N.log`. Se perdieron así los resultados y escenas del punto 1 de G002
  (intento 1). SaveOption: `getSaveOption().setSelected(ALL_DESIGNS)` y `setSaveOptionInput` no cambian el NONE en 2602.
  Solución: `p.setKeepTemporaryArtifacts(true)`, `despues.java` escribe en `<geometría>\puntos\Q…_m3h\` y guarda el .sim
  resuelto en su `Design_N` (`sim.saveState(sim.getSessionPath())`).
- 2026-11-04 · DM no corre los diseños en el orden de la tabla: tras Design 1 lanzó el Design 4. Con reuso por distancia
  da igual mientras haya un diseño resuelto cerca; comprobar en `progreso.txt` (`it_sim`: 1500 = reusó un diseño, 2000 = la base).
- 2026-11-04 · Reinicio de una geometría: `doe.py reiniciar G00x` (para el solver, archiva en `_intentoN`) y luego preparar, crear, lanzar.
- 2026-11-04 · Al reescribir un .java con `Set-Content -Encoding utf8` de PowerShell 5 entra un BOM y javac falla («illegal character '﻿'»).
- 2026-11-04 · Disco: con KeepTemporaryArtifacts cada diseño deja ~3 GB (`base.sim` resuelto, `base.sim~`, `_cache\1|2\`
  y `Barrido\_cache\`). `doe.py podar` (lo llama el ciclo tras entregar) borra solo `_cache` y `*.sim~`: ~650 MB por punto.
  Las carpetas de DM son ocultas: sin `-Force` en `Get-ChildItem` la poda no borraba nada (G002 quedó en 19 GB; corregido
  el 2026-11-04 14:40). Tras podar: 6–8 GB por bomba entregada; la bomba en curso llega a ~30 GB antes de podar.
- 2026-11-04 · Primer punto válido (G002, Qn): 1500 it en 18 min, H 91,3 m, η 0,628, balance 0,14 %, continuidad 7,8e-2,
  H de la it. 1 = 91,9 m (parte de la solución de la base, no de cero). Escenas: 10 PNG con sufijo «_1» (nombres del lote).
- 2026-11-04 · `explorer.exe` de la sesión RDP desconectada de `starccm` come 1,3–2,4 núcleos: con 46 procesos en 48
  núcleos hay sobresuscripción y MPI va al ritmo del más lento (.77.9: 2,9 s/it frente a 0,7–0,9).
- 2026-11-04 · Tras matar explorer.exe: .77.9 2,9 → 1,3 s/it; .222 1,18 → 0,98; .244 0,87 → 0,72; .245 0,71 → 0,59.
- 2026-11-04 · **El reuso de DM no se activa** (SaveOption sigue en NONE): todos los diseños cargan la base (`it_sim=2000`,
  la solución nominal convergida) y hacen 1500 it al nuevo caudal. El orden de corrida (1, 4, …) deja de importar.
- 2026-11-04 · El tablero (que despacha) carga `doe.py` al arrancar: tras cambiar NP, ITS o una plantilla, **reiniciar
  el tablero** o la siguiente bomba sale con lo viejo (G005 salió con 46 procesos; reiniciada con 44).
- 2026-11-04 · `print` del log de STAR-CCM+ («dise�os») tumbaba el despacho en la consola cp1252: stdout en UTF-8 con
  `errors="replace"`. El ciclo retoma solo las geometrías «preparada»/«creada» que quedaron a medias.
- 2026-11-04 · Primera bomba completa (G002): 10 puntos en 3 h 10 min, Excel + 230 escenas. 5/10 puntos «convergió»;
  peor 62,8 m³/h (oscila 8,7 %). A 0,1 m³/h el balance de masa en % no sirve (caudal casi nulo).
- 2026-11-04 · A veces el servidor de un diseño terminado queda vivo y ocioso (G004 en el .222: 46 procesos de las
  10:02 a 0,3 núcleos junto al diseño en curso). Se ve como ~200 procesos STAR en el tablero. Se cierra por hora de
  arranque sin tocar el diseño activo.
- 2026-11-04 · **G012: 4 puntos perdidos.** Un diseño se cayó dentro de `despues.java` («LLVM ERROR:
  IMAGE_REL_AMD64_ADDR32NB relocation requires an ordered section layout») y su servidor quedó colgado con la licencia
  PoD de la IP: los diseños siguientes fallaron con «Failed to get all licenses» y DM cerró el estudio con −1e+99 en
  esos diseños. El tablero no lo veía (el huérfano contaba como «corriendo»). Ahora: `estado.ps1` cierra grupos de
  servidores de diseño (`-xmpidriver`, por `tmpdir`) más viejos que el actual y con > 10 min; `dm_vivo` (vive el
  `star.ps1` de esa carpeta); estado «incompleta» si DM salió con puntos pendientes → el ciclo relanza solo los que
  faltan (`preparar(solo=…)`, `puntos\` no se archiva) hasta 2 veces y luego entrega lo que haya. «Terminado» exige
  además que DM haya cerrado; al entregar se cierran todos los procesos STAR del worker.
- 2026-11-05 · G019 repitió lo de G012 (LLVM ERROR en el Design 2 → servidor colgado con la licencia → 6 diseños
  «job aborted»). El cierre de huérfanos no lo cubría (el colgado era el único grupo). Ahora `estado.ps1` cierra los
  servidores de diseño si el log de diseño más reciente trae «LLVM ERROR», y `despues.java` guarda el .sim y los
  resultados ANTES de las escenas (el LLVM ERROR sale al renderizar: llvmpipe por software). Sospecha: intermitente,
  ~1 de cada 10 bombas.
- 2026-11-05 · Tercera vez (G027, 8 puntos perdidos en 12 min): el detector por «último log con LLVM ERROR» no
  saltaba porque los diseños abortados escriben logs más nuevos. **Arreglo de raíz: DM ya no renderiza.**
  `despues.java` solo deja resultados + .sim; al terminar la bomba el ciclo lanza `scripts/render.ps1` (fase «render»):
  abre cada .sim con `dm/escenas.java`, un punto a la vez, 15 min de límite, cierra todo STAR tras cada punto y
  reintenta una vez; escribe `render_fin.txt` y entonces se entrega. Se quitó el cierre por LLVM de `estado.ps1`.
- 2026-11-05 · **DM copia las macros del proyecto al ARRANCAR el barrido**, no al preparar cada diseño: cambiar
  `despues.java` en la carpeta de una bomba en marcha no tiene efecto (G026, lanzada antes del cambio, siguió
  renderizando en DM). Los cambios de macros solo valen para bombas lanzadas después. `render.ps1` salta los puntos
  que ya tienen PNG (G026: ok=10 sin renderizar nada).
- 2026-11-05 · Cortes de red: el .244 sin SSH ~5 min (sin reinicio); el .77.9 sin SSH ni RDP desde ~08:00 (G025 en
  7/10). Sin datos del worker el tablero no relanza ni da por fallida la bomba: espera.
- 2026-11-05 · Cortes intermitentes de red en capa 2 (VMware, MAC 00-50-56-…): a las 19:15 el .245 respondía desde el
  .222 pero no desde la .72; en la .72 no había entrada ARP para .244/.245/.77.9, y el .244 y el .77.9 tampoco
  respondían desde el .222. Las VM no se apagan (el .244 volvió con LastBootUpTime del 13-10): es la red virtual.
  Los jobs siguen en local; el tablero los recoge cuando vuelve la conexión. Revisar el vSwitch/host de VMware.
- 2026-11-06 · Los cortes de red SÍ cuestan puntos: G032 (.222) quedó con 5/10. DM abortó el estudio con «Error from
  Resource Manager command: jobs/1» (HTTP 500 del job manager local, 127.0.0.1:8332) mientras el Design 5 corría, y
  canceló los diseños pendientes. Probable causa: la licencia PoD (flex.cd-adapco.com por internet) se pierde con la red.
  El ciclo lo trata como «incompleta» y relanza los que faltan (máx. 2 veces).
- 2026-11-06 · Con la red cayéndose, un `ssh` abierto se quedaba colgado y paraba TODO el ciclo del tablero (30 min sin
  vueltas). Ahora ssh/scp llevan `ServerAliveInterval=15 ServerAliveCountMax=4` (≈1 min y corta). Reintentos de
  «incompleta» subidos de 2 a 6 para no entregar incompletas por cortes de red.
- 2026-11-06 · G032: 4 reintentos sin un solo punto. El Design 1 del reintento tardó 2 h (lo normal ~20 min: el solver
  espera la licencia cuando cae la red) y luego «Resource Manager client cannot connect to url
  http://127.0.0.1:8209». **Pausa**: `plan.json` `"pausa": true` → el ciclo solo lee estado (no relanza, ni entrega,
  ni reparte). Quitar la pausa cuando la red de las VM esté estable. G032 quedó «preparada» (3 reintentos usados).
- 2026-11-09 · Relanzar UN solo punto falla al instante: «Discrete Parameter Type must have at least 2 Values» y DM sale
  sin correr nada (G025, 2 reintentos gastados). `preparar` repite el caudal con +1e-6 kg/s (misma carpeta Q…_m3h;
  cuesta un punto más). El tablero tiene el código en memoria: reiniciarlo tras cambiar `doe.py`.
- 2026-11-09 · Pausa quitada a las 04:44 (.245 apagada en VMware, `excluir`). El .222 cayó a las ~04:56, justo tras
  lanzar G032: también a `excluir` (solo bloquea bombas nuevas; G032 se relanza en él cuando vuelva).
- 2026-11-09 · Pista de las caídas (en el .244, sin reinicio desde el 15-oct): 90 avisos `disk 153` (E/S reintentada:
  el almacenamiento no respondió a tiempo) desde el 11-05 11h, justo cuando empezaron los cortes; nada de energía ni
  de la tarjeta de red; durante el corte no hay ningún evento (la VM parece congelada, no desconectada) y el reloj
  quedó 14 h sin sincronizar. Sospecha: el datastore de VMware (¿discos thin y sin espacio?) pausa las VM. C: del
  .244: 249 GB, 66 libres, 90 GB de C:\trabajo. Pedido a Sebastián revisar el datastore en vSphere.
- 2026-11-09 · Confirmado por el administrador: se llenó el almacenamiento LOCAL del servidor ESXi donde están las 4 VM
  (no el almacenamiento compartido). Las 4 se reiniciaron a lo bruto entre 09:01 y 09:28 (evento 41). Cada VM: disco
  250 GB (300 la .245), 128 GB de RAM (→ `.vswp` de hasta 128 GB en el datastore si no hay reserva), TRIM activo en
  Windows. El DOE escribió 84–107 GB por VM desde el 11-05, que es cuando empiezan los `disk 153`: con discos thin,
  eso hace crecer el datastore. Borrar en Windows solo devuelve espacio si ESXi hace UNMAP (VMFS6, thin).
- 2026-11-09 · Primer `resultados.json` v2 real (G031, Q 708 m³/h, 14,6 kB): todo bien salvo `error_modelos` y
  `error_solvers` (ThreeDimensionalModel y PartitioningSolver no son NamedObject: nombre por reflexión) y que las caras
  Inflow/Outflow unidas por interfaz salían como paredes (ahora se excluyen con getBoundary0/1 de cada interfaz).
  G025, G027 y G032 (relanzadas antes del arreglo) llevarán esos dos errores; no afecta a H, η ni y+.
- 2026-11-09 · La primera poda automática (G025, G031) no borró nada: `NO_PODADO`. `sim_origen.txt` guarda la ruta
  original y `reiniciar` mueve ese `.mdxruntime` a `_intentoN\`. Ahora podar, extraer.ps1 y render.ps1 buscan la misma
  ruta relativa dentro de cada `_intento*`. Podadas a mano: G025 −37,6 GB, G031 −34,6 GB (el Qn queda en `_intento1`).
  La re-extracción de G003 se relanzó con el script corregido. Tras cambiar doe.py, reiniciar el tablero.
  G003 re-extraída y podada: 10/10 puntos v2, ~55 s por punto, de ~10 GB a 0,8 GB.
- 2026-11-09 · Editar plan.json mientras el tablero relanza una bomba se pierde: el ciclo tenía el plan leído de antes
  y lo guardó encima (`excluir` volvió a [.245, .222] y la .245 quedó ociosa 10 min). Comprobar tras editar.
- 2026-11-09 · El tablero (preview de la sesión de Claude) murió a las 13:03 al cerrarse la sesión: nadie entregó ni
  repartió hasta las 16:34; G030, G033, G034 y G035 ya habían acabado y las 4 máquinas quedaron ociosas ~3 h.
  Reanudado a mano. El orquestador depende de que la sesión siga viva.
- 2026-11-10 04:18 · **DOE terminado**: 47/47 bombas entregadas con 10/10 puntos, todas con resultados.json v2,
  Excel e informe en su carpeta DOE\ y solo el .sim de Qn en el worker (0,8 GB cada una). Libre al final:
  122–148 GB por worker. La última tanda (G040–G047) fue a ~15–20 min por punto, sin caídas.
- 2026-11-10 · Revisión final (`consolidar.py` → `Desktop\Geometrias_Prueba\DOE_PAT1_resultados\`, con LEEME.md):
  nq ≤ 25 no convergen (continuidad 0,1–2, H +24 % sobre CFturbo, η_Euler > 1); nq 35–57 base −14…−29 % de H frente a
  CFturbo con buena convergencia; variantes fD2 < 0,9 coherentes con semejanza en su BEP pero el barrido anclado a Qn
  les queda desplazado. 33 puntos quedaron en v1 y 19 sin imágenes: eran de G025/G027/G031/G032 (en curso al pasar a
  v2) y sus .sim se podaron sin re-extraer. Lección: re-extraer **antes** de marcar v2=True y podar, y comprobar que
  todos los puntos tienen `version_json`. `marcos_rpm` sale × 60/2π de más: getRawValue ya está en rpm.
- 2026-11-10 · Rehacer (Sebastián): G001–G013 completas a 2000 iteraciones y los puntos v1 de G019 (1), G025 (9),
  G027 (7), G031 (9) y G032 (5) a 1500. plan.json `"rehacer": {"solo", "its"}`; el ciclo lo despacha en su worker
  (sueltos primero) con `rehacer()`: aparta los puntos viejos a `_intento_rehacer\puntos\`, reinicia, prepara con `its`
  (queda en plan.json y lo usan los relanzamientos) y lanza. Primero a mano con G019 para validar.
  G032: el primer `crear` falló («Unable to create or communicate with reference simulation server», justo tras
  recopiar base.sim: la poda también borra base.sim y preparar lo vuelve a subir desde la .72) y `lanzar` salió al
  instante sin .dmprj → estado error. Reintento de crear a mano bien. Ahora rehacer() no lanza si crear no dejó el .dmprj.
- 2026-11-10 · 2000 iteraciones no mejoran nq 10–25 (G004: continuidad 0,05–0,38, igual que con 1500; H en Qn +6 %
  y oscila 3 %). Sebastián: probar otra estrategia. Se pausan G005–G013 (`rehacer_pausado` en plan.json); G001–G004
  terminan a 2000. Pistas de la malla (v2): en nq 10–25 la región «estator» tiene 15 k celdas (72 k en nq 30–60,
  158 k en nq ≥ 65) y hay 722 celdas con calidad < 0,01 (200 y 145). Pruebas en un punto con `prueba.py`
  (dm/prueba.java + scripts/prueba.ps1, sobre una copia del .sim de Qn): `urf` (p 0,1 / v 0,3) y `malla` (base × factor).
- 2026-11-10 · Resultado de las pruebas (Qn de G001 y G002): relajación baja → continuidad 5× menor pero se estanca en
  3e-2; malla × 0,75 (1,6 → 2,6 M celdas) → igual (1e-1); malla + relajación → 6e-2. H y M cambian < 1,2 % y < 2 %:
  el resultado es robusto, el residual es de flujo inestable (rotor–voluta) que el estacionario no asienta. Sebastián:
  G005–G013 se quedan con sus datos de 1500 (`rehacer_descartado`). Un G012 (199 m³/h, v1) se rehízo suelto.
- 2026-11-10 · Base de datos modo bomba: `base_datos.py` → `DOE_PAT1_modo_bomba.xlsx` (Geometrias con DOE + run.json de
  CFturbo: D2, b2, Ds, Dh, β1/β2, espesor, abrazado, gargantas, η y NPSH 1D; Simulaciones con entradas, salidas,
  ψ, φ, Euler, calidad; Paredes, Fronteras, Malla_regiones, Curvas_CFturbo). Las fórmulas del Excel de geometrías no
  traen valor guardado (openpyxl data_only da None): el punto de diseño sale de run.json, no de esa hoja.
- 2026-11-10 · **Auditoría final del modo bomba** (`auditar.py`): 47/47 entregadas, 470 puntos v2 con sus iteraciones
  (2000 en G001–G004), H finita, sin errores de extracción, unificado = local (md5), imágenes en todos, Excel por bomba
  al día y copiado, base de datos = JSON; en los workers 1 .sim por bomba (0,56–0,84 GB), 10 puntos con imágenes, ningún
  STAR vivo, 139–148 GB libres. Encontró que G016 y G028 corrieron con la lista de caudales de antes del tope de 1,6 Qn:
  el Excel y el repositorio cruzaban la referencia de CFturbo con la lista nueva. `rango.aplicar_plan` usa ahora los
  caudales de plan.json; regenerados sus Excel, el repositorio y la base de datos. Sin fallas tras el arreglo.
- 2026-11-04 · El orden de la lista DISCRETE se respeta (Qn primero). `MdxStudyParameter.getDiscreteQuantity().setArray(DoubleVector)`.
- 2026-11-04 · Copia .72 → worker por scp: 78 MB/s (sim de 650 MB en 8 s).

## Validación de referencia (pasada por Sebastián el 2026-11-04)

G025_nq50_B en el nominal: simulación a mano de Pini (7,5 M celdas) frente a la del lote (1,77 M celdas).

| magnitud | Pini | lote G025 | diferencia |
|---|---|---|---|
| Q | 115,83 kg/s | 115,69 kg/s | +0,1 % |
| H | 47,33 m | 45,98 m | +2,9 % |
| M | 194,9 N·m | 195,1 N·m | −0,1 % |
| P_eje | 61,2 kW | 61,3 kW | −0,1 % |
| η | 0,874 | 0,851 | +2,3 puntos |
| H / H_diseño (55,8 m) | 0,85 | 0,82 | |

El par coincide; la malla del lote (4,3 veces menos celdas) da ~3 % menos de H y ~2,3 puntos menos de η. Es la
malla que usa este DOE (el `.sim` base de cada bomba es el del lote).

| 2026-11-05 | Si la curva de CFturbo se acaba antes de que H baje al 25 % (G016, G025, G028, G030, G031), Q_max = 1,6 Qn: con 2,0 Qn CFD daba H negativa (G025 −36 m; G028 −17 m ya a 1,78 Qn). Aplicado a G030 (reiniciada) y G031; G016/G025/G028 se quedan como salieron. |

## Pendiente

| fase | estado |
|---|---|
| 0 inventario | ✅ |
| 1 licencia | ✅ .244 y .245; falta .77.9 y .222 (`lic_test.ps1`) |
| 2 piloto Design Manager | sin `PilotoDM`: hecho desde cero con la API 2602 (`dm/`). G001 lanzado en el .244 el 2026-11-04 06:28 |
| carpeta compartida | `\\172.17.77.72\cluster` aún no existe; la .72 tiene solo 70 GB libres |
