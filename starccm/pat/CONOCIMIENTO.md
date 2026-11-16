# Base de conocimiento — DOE PAT (modo turbina)

Todo lo nuevo del DOE en modo PAT va aquí; lo del modo bomba sigue en `../doe/CONOCIMIENTO.md` (máquinas, SSH,
licencia, lecciones de Design Manager, poda, re-extracción: todo vale igual).

## Decisiones

| fecha | decisión |
|---|---|
| 2026-11-10 | Proyecto aparte (`starccm/pat/`, `C:\trabajo\PAT-2026-11_PAT1`, `<bomba>\PAT\`, `PAT_PAT1_resultados\`); no se mezcla con bomba. Arranca cuando termine el modo bomba (Sebastián). |
| 2026-11-10 | MRF como en bomba, giro al revés; nueva variable rpm (parámetro global `rpm`). El embalamiento se detecta por el cambio de signo de M_turb (Sebastián). |
| 2026-11-10 | Igual que en bomba: una sola simulación guardada por geometría; el resto en JSON, imágenes y Excel. |
| 2026-11-11 | Embalamiento (Sebastián): se deja el barrido de 32 casos tal cual para las 47; **al final** se corren puntos extra (rpm altas o caudal bajo) solo en las bombas donde M_turb no cambió de signo. Hará falta una tabla de casos nueva en el base.sim (`pat_fisica.java` con los casos extra) y un estudio aparte por bomba. |
| 2026-11-10 | Barrido (Sebastián): **rpm 500, 1000, 1500 y 3000** × **8 caudales entre 0,8 y 2,4 Q_BEP** (Q_BEP = Qn de bomba a 3000 rpm) = 32 puntos por bomba, 1504 en total (~5 días en 4 workers). Por defecto, sin respuesta aún: se guarda el .sim del BEP de turbina a 3000 rpm y las nq 10–25 van al final. |

## Investigación de reportes (2026-11-10)

- Los reportes del base.sim salen de `lote/macros/05-reportes.java` (pt_in/pt_out promedio másico de presión total en los
  extremos de las extensiones; M = momento de las paredes que giran sobre el eje; H, P_hid, P_eje, eta) y de
  `recipes/reportes-euler-triangulos.java` (U, Vu, Vr, UVu en entrada y salida del rotor, H_Euler, eta_Euler, Vu2_inf,
  factor_deslizamiento). Esa receta ya tiene `MODO turbina` (1 = radio mayor; H_Euler = (U1Vu1 − U2Vu2)/g).
- En bomba P_eje = |M|·|RPM| y los campos agente_U/agente_Vu/agente_UVu llevan |ω| y el signo del giro **como números**:
  con rpm variable hay que redefinirlos con `${rpm}` (lo hace `pat_fisica.java`).
- El signo se pierde en bomba (P_eje con abs): en PAT P_eje = M·ω con signo es lo que delata el embalamiento.
- `despues.java` (v2) lee todos los reportes por nombre: sirve sin cambios, salvo la carpeta del punto (Q y rpm).
- La bomba gira a −3000 rpm sobre el eje del .cfturbo-ccm; la PAT a +rpm.
- El Excel de geometrías trae los barridos previstos: turbina 0,8–2,4 × Q_BEP (hoja Parametros, `fQ_turb_min/max`).

## Cómo está montado (2026-11-10)

- `pat.py` importa `../doe/doe.py` y le cambia carpetas (`AQUI`, `PLAN`, `REMOTO`) y funciones (`geo`, `preparar`,
  `traer`, `podar`, `rango`): estado, ciclo, relanzamientos, render y tablero son los del modo bomba. Tablero en 8771.
- DM barre un solo parámetro, **caso** (1…32); `Flujo` y `rpm` son expresiones del caso en el .sim
  (`(${caso} < k + 0,5) ? valor : (…)`, para que el truco de repetir un punto suelto con k + 1e-6 siga funcionando).
  doe.py empareja puntos por `doe.CLAVE_JSON` = "caso"; en plan.json `Flujo_kg_s` guarda el caso (ponytail).
- Orden de casos: 3000 rpm de 0,8 a 2,4 Qn, 1500 de 2,4 a 0,8, 1000 subiendo, 500 bajando (zigzag para el reuso).
- Puntos en `puntos\Q…_m3h_n…_rpm\`; el JSON lleva `caso`, `rpm` y `modo: PAT`.
- Conversión (`preparar`): base.sim de bomba desde la .72 → `pat_fisica.java` en batch → guarda encima, borra la
  solución y deja `pat_ok.txt`. G014: 25 reportes, giro −314 → +314 rad/s, entrada «outlet» caudal +Flujo, salida «inlet» 0 Pa.
- Se guarda solo el .sim del BEP de turbina a 3000 rpm (máxima eta con P_eje > 0); Excel `<bomba>\PAT\<id>_PAT.xlsx`
  con hojas Puntos (régimen turbina / freno / bomba inversa) y Embalamiento.

## Síntesis de lo aprendido (2026-11-16, DOE PAT1 terminado)

Corrida: barrido 2026-11-10 19:39 → 11-15 10:09 (1504 casos, 4,6 días, 4 → 7 workers); embalamiento 11-15 06:15 → 17:43
(148 casos). Resultado: `Geometrias_Prueba\PAT_PAT1_resultados\` (base `PAT_PAT1_modo_turbina.xlsx`, `REVISION.md`).

### Parámetros de CFD que funcionaron (no tocar sin motivo)

| parámetro | valor | por qué / evidencia |
|---|---|---|
| malla, modelos | los del base.sim de bomba (k-ω SST, All y+, MRF, agua 998,2, Cell Quality Remediation) | sin remallar: misma malla que bomba, datos comparables uno a uno |
| fronteras | brida de la voluta = caudal másico **+${Flujo}**; boca de la bomba = **presión estática 0 Pa** | estable en las 1652 simulaciones, ninguna divergió |
| giro | MRF al revés que en bomba, `s·${rpm}·π/30` con `rpm` parámetro global | un solo .sim sirve para las 4 rpm |
| barrido | DM barre solo `caso` (1…N); Flujo y rpm son expresiones de `${caso}` (`< k+0,5`) | reusa relanzamientos, estado y tablero del modo bomba sin cambios |
| URF | p 0,2 / v 0,5 (k-ω 0,8) | las de bomba; no hizo falta bajarlas |
| iteraciones | 1500 por caso, con reuso de la solución del caso vecino (orden en zigzag) | H y M estables (deriva < 2 %/100 it) en el 97 % de los casos |
| criterio de convergencia | **H y M estables**, no los residuales | continuidad 0,03–0,3 sin bajar en muchos casos (como bomba nq 10–25); H, M y η no cambian |
| tiempo por caso | 15–17 min nq ≥ 30; 16–27 min nq 10–25; ~42 min en la .230 (VM lenta) | 44 núcleos por worker |
| render de escenas | 55–95 min por bomba (32 casos), fuera de DM | en DM tumbaba el solver (lección del modo bomba) |
| disco | ~70–80 GB por bomba mientras corre (32 .sim + `_cache`); la poda deja 1 .sim | podar en cuanto se entrega el Excel |

### Qué dicen los resultados (sentido físico, verificado)

| magnitud | nq 10–25 | nq 30–57 | nq 60–90 |
|---|---|---|---|
| Q_BEP turbina / Qn (3000 rpm) | 1,5–2,4 (med 1,94) | 0,8–1,26 (1,03) | 1,03–1,26 (1,26) |
| η máx turbina | 0,60–0,76 | 0,75–0,83 | 0,60–0,82 |
| Q_t/Q_b (BEP turbina / BEP bomba) | 2,12 | 1,20 | 1,38 |
| H_t/H_b | 2,25 | 1,34 | 1,71 |
| η_t/η_b | 0,97 | 0,96 | 0,93 |
| Q_embalamiento / Qn a 3000 rpm | 0,39–0,59 (G001 2,41) | 0,33–0,49 | 0,54–0,72 |

- **Semejanza**: H₃₀₀₀ frente a 4·H₁₅₀₀ al mismo Q·3000/n difiere ≤ 3,1 % y η ≤ 0,03 en las 47: los efectos de Reynolds
  entre 1500 y 3000 rpm son despreciables; con una rpm y las leyes de semejanza basta para las otras (dentro del rango).
- Q_t/Q_b y H_t/H_b de nq ≥ 30 caen en el rango de las correlaciones clásicas de PAT; las nq 10–25 (η de bomba baja) dan
  relaciones mucho mayores, como predicen esas correlaciones para η bajas.
- **Embalamiento**: a rpm fija, se llega **bajando el caudal**. Con rpm ≤ 3000 y Q ≥ 0,8 Qn solo embalan G001 (nq 10) y G002
  (nq 15); el resto necesita 0,33–0,72 Qn a 3000 rpm. G001 es al revés: a 3000 rpm todo el barrido (≤ 2,4 Qn) es freno.
- Cerca del embalamiento (η < 0,2) la solución es mala: balance de masa hasta 2,6 %, H con deriva de hasta 15 %/100 it, H no
  monótona con Q y cambios de signo múltiples (G003: 0,49 / 0,67 / 0,72 Qn). El caudal de embalamiento vale ± un paso de la
  malla de caudales; la H justo en el embalamiento, no.
- G001: puntos en freno con reuso de solución y puntos nuevos en frío caen en ramas distintas (H 83 m frente a 131 m entre
  2,4 y 2,6 Qn): en freno el estacionario MRF puede tener varias soluciones.
- BEP en el borde del barrido (2,4 Qn) en G002, G003 y G006: para nq ≤ 15 el barrido debería llegar más alto.

### Para el próximo DOE PAT (recomendaciones)

- Escalar el barrido con nq: nq ≤ 25 → 1,2–3,5 Qn; nq ≥ 30 → 0,4–2,0 Qn. Así BEP y embalamiento quedan dentro.
- Para el embalamiento basta una rpm (3000) y semejanza; incluir 0,3–0,7 Qn desde el principio en vez de una ronda aparte.
- Puntos cerca del embalamiento: más iteraciones (2500–3000) o transitorio si interesa la H ahí; no fiarse de un solo punto.
- Guardar la lista `solo` antes de archivar un intento (ya corregido en `doe.ciclo_paso`).

### Resolución de problemas (lo que pasó y cómo se resolvió)

| síntoma | causa | solución |
|---|---|---|
| VM sin ping/SSH minutos u horas, STAR vivo al volver | congelamiento de la VM (sospecha: datastore de VMware lleno; cada bomba escribe ~70 GB) | el admin reinició y amplió la .207 a 500 GB; `excluir` en plan.json hasta que esté estable; el ciclo relanza lo perdido |
| .230 parpadea (ping 400 ms, SSH sin banner) y va 3× más lenta | VM con problemas de host | usarla solo con vigilancia; nunca para la última bomba de una cola |
| «Failed to get all licenses… ccmppower», rc 8, en ráfaga | corte del servidor PoD (11-14 11:35–11:45) | nada que hacer: DM sigue con el resto y el ciclo relanza los diseños que fallaron (`incompleta`) |
| bomba «corriendo» con 0/32 y no se relanza | `estado.ps1` tarda 105 s en una bomba PAT y `doe.estado` cortaba a 90 s | timeout 240 s |
| DM colgado lanzando un diseño (CPU 2 %) | — | el ciclo relanza también `sin_progreso` (log de DM > 1 h quieto) |
| relanzamiento corrió los 32 casos en vez de los que faltaban | `preparar(solo=…)` falló a medias (scp) y «retomar» creó el estudio sin `solo` | `solo` se guarda antes de `reiniciar`; «retomar» rehace `preparar` con ese `solo` |
| poda guardó un caso de freno (G001) | regla «BEP a 3000 rpm» sin turbina a 3000 | BEP de turbina a la rpm más alta con P_eje > 0 |
| tablero muerto cada hora | la app cierra la vista previa | tablero como proceso en segundo plano de la sesión, no como preview |
| ediciones de plan.json perdidas | el tablero reescribe plan.json en cada vuelta | editar, esperar 70 s y comprobar (reintentar); o `pausa: true` mientras se toca a mano |
| `Vu2_inf` no se puede borrar | lo usa un field function del reporte | se deja en 0 (no tiene sentido en turbina) |
| chequeo de semejanza con H_BEP(1500)/H_BEP(3000) daba avisos falsos | los caudales del barrido son los mismos a todas las rpm | comparar al mismo caudal reducido Q·3000/n |
| RDP «no se puede contactar el controlador de dominio» | el cliente intenta la cuenta de dominio (NLA), no los scripts | entrar con `DESKTOP-xxxx\starccm` o `.\starccm` |

## Lecciones

- 2026-11-10 · `pat_fisica.java` no puede borrar `Vu2_inf` («is being used by PrimitiveFieldFunction Report: Vu2_inf»):
  Vu2_inf y factor_deslizamiento se dejan en 0.
- 2026-11-10 · `doe.estado()` llamaba a `C:\trabajo\estado.ps1` sin raíz (siempre la del modo bomba): ahora pasa `-Raiz REMOTO`.
- 2026-11-10 · DM no corre los casos en el orden de la lista (G014: 1, 32, 2, 31, 3, 21, 12, 22, 11…): alterna extremos.
  No afecta a los datos; el reuso de solución es peor (varios casos con continuidad 0,25–0,7 y otros 1e-3).
- 2026-11-10 · Primeros 9 puntos de G014: a 3000 rpm H 56 → 86 m y η 0,65 → 0,78 al subir Q (coherente). M_turb > 0 en
  todos (también a 500 rpm y 0,8 Qn): con rpm ≤ 3000 y Q ≥ 0,8 Qn **no se llega al embalamiento**, que pide rpm mayores
  a ese caudal (≈ 1,5–2 × la rpm del BEP de turbina) o caudales menores. Preguntado a Sebastián.
- 2026-11-10 · La app cerró el tablero PAT (preview) a la hora de lanzarlo; relanzado a las 21:56.
- 2026-11-11 · G014 se colgó ~23:25 lanzando el diseño 13 («Launching process…», CPU 2 %, 12/32 hechos) hasta las
  00:57: reiniciado a mano con los 20 casos que faltaban. El ciclo solo relanzaba «incompleta»; ahora también
  «sin_progreso» (log de DM > 1 h quieto) en `doe.ciclo_paso`.
- 2026-11-11 · Primera entrega PAT (G015, 06:00): 32/32 en régimen turbina (M_turb > 0 en todos, sin embalamiento),
  BEP a 3000 rpm en Q = 304 m³/h (1,26 Qn) con η 0,808 y H 86,9 m; Excel `<bomba>\PAT\G015_nq35_B_PAT.xlsx` bien.
  Poda: queda el .sim del BEP (Q0303.977_m3h_n3000_rpm) y se liberan **69,8 GB**: una bomba PAT ocupa ~70 GB en el worker
  mientras corre (32 .sim + _cache), 7 veces una de bomba. Ojo con el datastore de VMware (lección del 2026-11-09).
- 2026-11-11 · **3 workers más solo para PAT**: .207 (DESKTOP-IIKQEJC, 109 GB libres), .218 (DESKTOP-F2DD0U8) y .230
  (DESKTOP-FT9TJDB), 48 núcleos y 128 GB como los otros. Sebastián montó OpenSSH con una lista de comandos (al principio
  el 22 no respondía: faltaba la regla del firewall en todos los perfiles, `-Profile Any`); primera conexión con
  `StrictHostKeyChecking=accept-new`. `.env` copiado del .244 por scp sin mostrarlo (el de la .72 es viejo); `lic_test.ps1`
  OK en los 3 (39–51 s, «expires in 117 days»). Alta: `doe.WORKERS` ampliado en `pat.py` (el modo bomba no los usa).
  Sebastián: no borrar lo que ya hubiera en esas máquinas (C:\trabajo estaba vacío).
- 2026-11-11 · La .207 dejó de responder (ping y SSH) de 17:59 a ~18:25 con G022 en 16/32 y 56 GB libres; volvió sola,
  sin reiniciar (arranque del 13-oct) y con STAR vivo: la VM se congeló, como las del 11-09 (¿datastore lleno?). Avisado
  a Sebastián.
- 2026-11-11/12 · Congelamientos (ping y SSH se pierden minutos u horas, sin eventos de disco 153/129 ni saltos de reloj
  ni reinicios en Windows, STAR sigue vivo al volver): .207 desde 17:59 (intermitente), .222 20:11 y 00:23, .230 00:07,
  00:56 y 04:51, .218 03:16. A las 04:52 las 3 nuevas (.207, .218, .230) caídas a la vez y las 4 originales bien. Casos
  perdidos los relanza el ciclo (G020 5, G024 4). Las 3 nuevas fuera del reparto (`excluir`); quedan .244 .245 .77.9 .222.
  Sospecha: servidor/almacenamiento VMware de las nuevas; cada bomba PAT escribe ~70 GB. Avisado a Sebastián.
- 2026-11-12 09:08–09:10 · El administrador reinició la .207 (disco ampliado a **500 GB**, 301 libres) y la .218. Datos
  intactos (G022 18/32, G023 31/32). `excluir` vaciado y tablero relanzado (proceso de la sesión anterior muerto a las
  09:03); el ciclo relanzó G022 con sus 14 casos a las 09:27. G023 no se relanzaba: `estado.ps1` tarda 105 s en la .218
  (97 .sim y 31 puntos de una bomba PAT) y `doe.estado` cortaba a los 90 s → la .218 sin datos, G023 «corriendo» con 0/32.
  Timeout subido a 240 s.
- 2026-11-12 · Error NLA de Sebastián al entrar por RDP vía Citrix («no se puede contactar el controlador de dominio»):
  no es de nuestros scripts (NLA=1 y certificado RDP de agosto sin cambios en todas); es el cliente intentando la cuenta de
  dominio. Usar `DESKTOP-xxxx\starccm` o `.\starccm`.
- 2026-11-11 · La app cierra la vista previa del tablero a la hora de abrirla (3 veces seguidas). Desde las 02:10 el
  tablero corre como proceso en segundo plano de la sesión (`python -u pat/pat.py tablero`), no como preview; sigue
  dependiendo de que la sesión esté viva. La vigilancia avisa si estado.json pasa 10 min sin actualizarse.
- 2026-11-13 · Primer cambio de signo (embalamiento) en **G001_nq10_B**: a 3000 rpm y 0,8 Qn (20,2 m³/h) η = −0,56
  (H 75,8 m, P_eje < 0: freno); a 49 m³/h η = +0,60. Las nq bajas embalan dentro del barrido; las nq ≥ 30 no.
- 2026-11-13 · La .230 volvió al reparto a las 09:00 tras 25 min estable: no se ha vuelto a caer, pero va a ~44 min por
  caso (los demás 15–17 min).
- 2026-11-14 · **G001_nq10_B a 3000 rpm: los 8 caudales (0,8–2,4 Qn) en freno** (P_eje < 0; casi 0 en 2,4 Qn, −945 W):
  el embalamiento a 3000 rpm está por encima de 60 m³/h. A 1500 rpm embala en 31,9 m³/h; 1000 y 500 todo turbina.
  La poda guardó el .sim de un punto de freno a 3000 rpm (Q0060.480, η −0,07). Corregido `podar`: BEP de turbina a la
  rpm más alta con P_eje > 0 (1500 en G001). El .sim de G001 no se puede recuperar sin re-correr. Para los puntos extra
  del final: en nq bajas faltan caudales > 2,4 Qn a 3000 rpm (el lado opuesto que en nq altas).
- 2026-11-14 11:35–11:45 · Corte de licencia PoD («Failed to get all licenses… ccmppower|ccmppowerplus», rc 8): los diseños
  que arrancaron en esos 10 min fallaron en .207 (G003, 4), .218 (G006, 15), .245 (G007, 9) y .230 (G008, 5); .222,
  .77.9 y .244 sin fallos (no lanzaron diseños en ese rato). DM sigue con el resto y el ciclo relanza los que faltan al
  terminar el estudio («incompleta»); el reintento de G003 a las 11:52 ya tuvo licencia.
- 2026-11-15 04:34 · Relanzamiento de G008 (5 casos del corte de licencia) con la .230 parpadeando: `reiniciar` archivó el
  intento y `preparar(solo=…)` falló en un scp → plan sin `solo` y fase «preparada» → la rama «retomar» del ciclo creó
  y lanzó un estudio con los **32 casos** (~22 h en la .230). Parado a las 04:50 y relanzado a mano con solo 10–14
  (ciclo en `pausa`). Corregido en `doe.ciclo_paso`: `solo` se guarda antes de `reiniciar`, y «retomar» rehace
  `preparar` con ese `solo` antes de `crear`.
- 2026-11-15 · **Puntos extra de embalamiento (opción B, Sebastián)**: `emb.py` (estudio aparte, tablero 8772, plan/estado/
  eventos/_traido en `pat/emb/`, workers en `C:\trabajo\PAT-2026-11_PAT1_emb`). A 3000 rpm: 0,7 · 0,55 · 0,4 Qn (G001:
  2,6 · 3,0 · 3,4 Qn); G002 no va (ya cruza). 46 bombas × 3 = 138 casos. Sin .sim; Excel: hojas «Puntos embalamiento» y
  «Embalamiento» (rehecha con los de 3000 rpm del barrido + extra) en el mismo `<id>_PAT.xlsx`. Prueba G014 en la .244:
  conversión OK (3 casos), 0,7 Qn → H 49,6 m, η 0,50 (aún turbina). `excluir` .222/.230 hasta que acaben G012/G008.
- 2026-11-15 17:43 · **Embalamiento cerrado en las 47**: ronda 1 (`emb.py`, 46 bombas × 3, 06:15–17:14) y ronda 2 (`emb2.py`,
  0,35 y 0,3 Qn en G004, G010, G019, G027, G029, 16:46–17:43, tablero 8773). Q_emb a 3000 rpm: G001 2,41 Qn; nq 15–57
  0,33–0,49 Qn (G007 0,59); nq 60–90 0,55–0,57 Qn; G002 dentro del barrido. El Excel de cada bomba junta las rondas
  (`emb.excel_bomba` lee todas las `emb*/_traido`). G001: entre 2,4 y 2,6 Qn la H salta de 83 a 131 m (puntos del barrido
  en freno con reuso de solución vs. nuevos en frío): el cruce vale, la H justo en el embalamiento es dudosa.
- 2026-11-16 · **Repositorio unificado y base de datos** (`consolidar_pat.py`): `Desktop\Geometrias_Prueba\PAT_PAT1_resultados\`
  con `PAT_PAT1_modo_turbina.xlsx` (Leeme, Geometrias = fila del modo bomba + resumen PAT_, Simulaciones 1652 =
  1504 barrido + 148 embalamiento, BEP_por_rpm, Embalamiento 50, Paredes, Fronteras, Malla_regiones), `PAT_PAT1_puntos.csv`,
  `REVISION.md`, `datos\<id>\barrido|embalamiento\Q…\` y `excels\`. Imágenes aparte: `consolidar_pat.py imagenes` (~64 MB/bomba).
  Sentido físico: semejanza 1500↔3000 rpm al mismo Q·3000/n con H ≤ 3,1 % y η ≤ 0,03 en las 47; BEP turbina/bomba a 3000 rpm
  Qt/Qb 1,20 y Ht/Hb 1,34 (nq 30–57), 1,38 y 1,71 (nq 60–90), 2,1 y 2,3 (nq 10–25); ηt/ηb 0,93–0,97. Avisos: balance
  > 0,5 % (54 casos, máx. 2,6 %) y deriva de H > 2 % (52) casi todos a 3000 rpm cerca del embalamiento (η baja); H no
  monótona cerca del embalamiento en 7 bombas; BEP en 2,4 Qn (borde) en G002, G003, G006. El chequeo H_BEP(1500)/H_BEP(3000)
  no vale (los caudales son los mismos a todas las rpm): se cambió por la semejanza al mismo caudal reducido.
- 2026-11-16 · Imágenes bajadas al repositorio (4,9 GB en total, sin errores): 9 escenas por caso (25 en las nq 10–15 más
  antiguas); a G018 le faltan escenas en algunos casos (224 de 288 en el barrido). Hoja Embalamiento: 50 filas = 47 bombas a
  3000 rpm + G001 a 1500 rpm + 2 cruces de más en **G003** (M_turb cambia de signo en 0,49, 0,67 y 0,72 Qn: el caso de
  0,7 Qn sale en freno entre dos de turbina, con H sin estabilizar): su embalamiento queda entre 0,49 y 0,72 Qn, no fiable.
- 2026-11-16 · **Sensibilidad** (`sensibilidad_pat.py` → `PAT_PAT1_resultados\sensibilidad\`): BEP de turbina a 3000 rpm
  afinado con parábola; variantes frente a la base de su nq; regresión Δy = a(Z−6) + bΔβ2 + c(1−f_D2) por familia.
  Bases: η_t máx 0,82–0,83 en nq 35–50, cae a 0,66 (nq 15) y 0,64 (nq 90); Q_t/Qn ≈ 2–2,4 (nq ≤ 25), 1,09–1,15 (nq 35–57),
  ≈ 1,3 (nq 60–90); Q_emb/Qn ≈ 0,46 (nq 25–57) → 0,6–0,72 (nq 60–90). Variantes: el recorte (1−f_D2) es lo más fuerte y
  estable (baja Q_t/Qn, sube H_t/Hn, baja η_b y η_t en nq medias); Z importa en nq altas (+1 álabe ≈ +0,04 de η_t; G043
  Z5 Δβ2 −6,4° da η_t 0,60 frente a 0,75 de la base, curva limpia: es física, no numérica); Δβ2 > 0 mejora η_t en nq bajas.
  Q_emb/Qn apenas depende de las variables (R² 0,2–0,5) salvo Z en nq altas. Límites: 8–10 variantes por familia, lineal,
  sin interacciones; BEP fuera del barrido en G002, G003, G006 (> 2,4 Qn) y en G019, G021, G029 (< 0,8 Qn, recortes
  f_D2 0,87–0,89): su η_t está subestimada.
- 2026-11-16 · **Transitorio de referencia** (`transitorio/`: macro, lanzador y `transitorio.py`): G025 en su BEP de turbina a
  3000 rpm, malla deslizante, URANS 2.º orden, 2°/paso, 8 it internas, 10 vueltas (~27 min/vuelta en 44 núcleos, 4,5 h).
  Periódico desde la vuelta ~7. Medias vueltas 8–10 frente al estacionario MRF: **H −11,9 %, M −11,7 %, η +0,2 puntos**;
  oscilación ±2,8 % en H y ±1,2 % en M a 300 Hz (Z·n). El rotor congelado sobreestima H y par en la misma proporción: η del
  DOE es fiable, H y M absolutos ~12 % altos (al menos en el BEP de nq 50). Montaje: el rotor estaba con frame MRF y paredes
  REGION_FRAME (las de carcasa LAB_FRAME) → basta asignar RotatingMotion con frame Lab; activar el modelo transitorio
  ANTES de asignar el movimiento (con estacionario STAR lo rechaza con «Server Error», aunque lo deja puesto). El .sim queda
  en la .245 (`C:\trabajo\TRANSITORIO_G025\transitorio_fin.sim`, 1,8 GB). Resultados en `PAT_PAT1_resultados\transitorio_G025\`.
- 2026-11-16 · **Video del transitorio** (`transitorio/video.java` + `armar_video.py`): 1 vuelta más desde transitorio_fin.sim
  (180 pasos, fotograma cada 4°, ~35 min) con las escenas «vectores_medio» (velocidad relativa) y «plano_vectores» (absoluta),
  rango de color fijo (0–35 y 0–40 m/s); el .sim no se guarda. GIF con Pillow (no hay ffmpeg en la .72):
  `PAT_PAT1_resultados\transitorio_G025\G025_transitorio_vectores.gif` (91 cuadros, 7,5 MB). Lecciones: en Java,
  `getDisplayerManager().getObjects()` devuelve DisplayerBase (iterar como Object); un lanzador con macro que no compila deja
  STAR vivo y su `Stop-Process` final mata la siguiente corrida: matar todo antes de relanzar.
