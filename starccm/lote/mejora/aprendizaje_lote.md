## G001_nq10_B  veredicto=OK  remallados=0 base=4.4 relaj_bajada=False graves=[] avisos=[]
motivo: Sin error clave: 1000 iteraciones, 1,60 M celdas, balance de masa 0,2 %, H 1,14 × diseño, eta 0,41 y oscilación de H 3,4 % en 801–1000, todo dentro de límites; D2 coincide (-0,02 %).
- INC: 06-euler: entrada/salida del rotor forzadas por nombre en la macro del caso (radio medio 0 sin solución inicializada)
- INC: reflujo en ext_entrada/inlet hasta la it. ~210
- INC: eta 0,41 con M ~3x P_hid: el momento incluye CasingHub/SolidHub/SolidShroud
- INC: continuidad plana ~3,5e-2 (normal según lecciones G001); H oscila 80,7-86,3 m en 801-1000
- INC: Wall Y+ no disponible en la exportación de superficies
- OBS: H 83,8 m frente a 73,5 m de diseño (+14 %); H_Euler 91,2 m, eta_Euler 0,92, factor de deslizamiento 0,53 con beta2 10,5°.
- OBS: eta 0,41 baja: P_eje 14,0 kW frente a P_hid 5,7 kW. El momento incluye CasingHub/SolidHub/SolidShroud (fricción de discos, importante en nq 10); la eficiencia solo del álabe sería mayor.
- OBS: H oscila ±3 m (80,7–86,3) sin tendencia desde la it. 600, con continuidad plana ~3,5e-2: usar la media, no el último valor.
- OBS: Plano medio coherente: flujo saliendo por el difusor, con recirculaciones en los canales y un desprendimiento a la entrada del difusor (normal a nq bajo).
- OBS: y+ en álabes: medio 8,4, máx. 107 (zona de amortiguamiento, fuera de 30–300 y de <5); aceptable para comparar entre variantes.
- OBS: U2 del reporte 43,8 m/s se mide en el radio de salida del rotor (139,4 mm), no en el del álabe (128,9 mm → 40,5 m/s).
- OBS: 06-euler: entrada/salida del rotor fijadas por nombre en la macro del caso; no afecta a la física.
## G002_nq15_B  veredicto=REVISAR  remallados=0 base=4.4 relaj_bajada=False graves=['oscilación de H % (últimas 200)'] avisos=[]
motivo: sin veredicto del revisor; decidido por los chequeos: oscilación de H % (últimas 200)
- INC: 06-euler: radio medio 0 sin solución; se fijaron entrada y salida del rotor por nombre (eIn/eOut)
- INC: H no asentada: 47,8 m (300 it.), 69,1 (500), 76,3 (800), 78,6 (1000); oscilación 76-86 m en 801-1000
- INC: 09-resultado: r_salida_rotor_m = -1,8e308 (no medido), sin efecto en los resultados
- INC: factor de deslizamiento 0,52 con beta2 14,8 grados
## G003_nq15_V  veredicto=OK  remallados=0 base=4.1 relaj_bajada=False graves=[] avisos=[]
motivo: Todos los chequeos pasan: 1000 iteraciones, 1,70 M celdas, balance de masa 0,09 %, H 70,8 m (0,99 × diseño), η 0,49, oscilación de H 3,7 %, D2 −0,05 %. Las escenas son coherentes.
- INC: 06-euler: radios 0 sin solucion inicial; entrada/salida fijadas por nombre en la macro del caso
- INC: H todavia deriva al alza al final (68,0-73,3 en 801-1000; it. 1000 = 73,0 m): 1000 iteraciones algo cortas
- INC: continuidad plana en ~4e-2 (recirculacion, normal segun lecciones)
- OBS: H sigue subiendo al final (68,5 m en it. 800 → 73,0 m en it. 1000) mientras M baja (68,5 → 66,5 N·m): la media 801–1000 subestima algo la H final y sobrestima M. La η de la it. 1000 es 0,514 frente a 0,490 de media.
- OBS: η baja con η_Euler 0,895: P_eje 21,3 kW frente a ρgQ·H_Euler ≈ 12 kW. Cerca del 40 % del par se va fuera del trabajo de Euler (fricción de disco en las cámaras laterales y fugas), algo esperable en nq 15.
- OBS: U2 y H_Euler se miden en la interfaz de salida del rotor (r 137 mm), no en el borde del álabe (r 121,9 mm). El factor de deslizamiento de 0,49 no se puede comparar con el diseño.
- OBS: y+ en los álabes: media 7,8 y máximo 55. Queda en la zona intermedia, ni de baja Re ni de función de pared; aceptable para el lote.
- OBS: En el plano medio hay recirculación en el difusor de la voluta y en la tubería de salida (dos vórtices). No hay flujo al revés en la frontera de salida.
- OBS: La presión mínima en el ojo del rodete es de −3,4 bar relativa a la entrada de 0 Pa. Aquí no importa (no hay cavitación modelada), pero cuenta para NPSH.
- OBS: La macro 06-euler se corrigió en el caso: entrada y salida fijadas por nombre.
## G004_nq15_V  veredicto=OK  remallados=0 base=3.7 relaj_bajada=False graves=[] avisos=[]
motivo: Tras seguir de 1000 a 1500 iteraciones, H se estabilizó en 52–55 m (2,1 % en 1301–1500, límite 5 %). No hay ningún error clave: 1,99 M celdas, balance de masa 0,08 %, H 0,75 × diseño, η 0,48, D2 −0,05 % y escenas coherentes.
- INC: H llegó a un máximo ~54,8 m en it. 1300 y baja despacio a 52,8 m en 1500; 75 % del diseño (71,3 m)
- INC: 06-euler: elección automática de entrada/salida falló; fijadas Inflow [int_entrada 1] / Outflow [int_salida 1] en la macro del caso
- INC: U2/H_Euler/factor de deslizamiento medidos en la interfaz int_salida (r 137 mm), no en el borde del álabe (r 110 mm)
- INC: Wall Y+ no disponible en el export EnSight
- INC: 09-resultado: r_salida_rotor_m sin valor válido
- INC: servidor con np 14 (STARCCM_NP=4 no aplicado por el MCP)
- OBS: H: 50,9 (1100), 52,0 (1200), máximo 54,8 (1300), 53,7 (1400), 52,8 (1500). Ya no deriva hacia arriba; oscila con una leve bajada.
- OBS: M baja despacio: 54,0 (1100) → 51,6 N·m (1500), ≈ 1 % por cada 100 it. Por eso η sube algo (0,44 → 0,48). Es una tendencia pequeña, no una divergencia.
- OBS: H al 75 % del diseño (71,3 m) y η 0,48: el mismo patrón que G003 en NQ15. La fricción de disco de las cámaras laterales pesa en el par.
- OBS: U2, H_Euler (69,8 m), η_Euler (0,756) y el factor de deslizamiento (0,42) se miden en la interfaz int_salida (r ≈ 137 mm), no en el borde del álabe (r 110 mm). No se pueden comparar con el diseño.
- OBS: Plano medio: recirculación en la garganta del difusor y en la tubería de salida, sin flujo al revés en la frontera de salida. Continuidad residual 1,6e-2, plana como en G001.
- OBS: Malla de 1 988 643 celdas, pegada al límite de 2 M (rotor 1,49 M). y+ en los álabes: media 7,9, máximo 46.
- OBS: El servidor volvió a arrancar con np 14 en vez de 4: el MCP no aplica STARCCM_NP del .env. Hay que revisarlo aparte (≈ 1,55 s/it).
## G005_nq15_V  veredicto=OK  remallados=0 base=3.9 relaj_bajada=False graves=[] avisos=[]
motivo: Ningún error clave: 1000 it., 1,76 M celdas, balance de masa 0,18 %, H 0,88 × diseño, η 0,48, D2 −0,05 % y escenas coherentes. La oscilación de H en 801–1000 (4,6 %) queda justo bajo el 5 %: H tocó su máximo en la it. 950 y ya baja un poco.
- INC: H sigue subiendo en 801-1000 (59,9 a 65,7 m); NQ15 necesita ~1500 it. (lecciones G002/G004)
- INC: 06-euler: radio medio 0 antes de resolver; entrada/salida del rotor fijadas por nombre en la macro del caso
- INC: 09-resultado: r_salida_rotor_m sin valor
- INC: U2 del reporte Euler (43,1 m/s) medido en la interfaz de salida del rotor (r 137 mm), no en el borde del álabe (r 114,8 mm); D2 por BladeTE 229,5 mm = diseño
- INC: eta 0,48 con eta_Euler 0,84: fricción de disco de cámaras laterales (lección G003)
- OBS: H: 60,6 (800), 62,0 (900), máximo 65,4 (950), 64,3 (1000). La media de 801–1000 (62,5 m) se queda algo corta frente al valor final probable, de unos 64–65 m: como mucho un 3–4 %.
- OBS: M baja despacio, de 61,6 a 59,7 N·m entre las it. 800 y 1000 (≈ 1,5 %/100 it.), como en G004. Por eso η sube de 0,46 a 0,50.
- OBS: η 0,48 con η_Euler 0,84: es el mismo patrón NQ15 que en G003 y G004 (la fricción de disco de las cámaras laterales pesa en el par).
- OBS: U2 (43,1 m/s), H_Euler (76,8 m) y el factor de deslizamiento (0,43) se miden en int_salida (r ≈ 137 mm), no en el borde del álabe (r 114,8 mm). No se pueden comparar con el diseño.
- OBS: Plano medio: recirculaciones en la garganta del difusor y en la tubería de salida, sin flujo al revés en la frontera de salida. La presión en los álabes crece de forma limpia del ojo a la periferia.
- OBS: y+ en los álabes: media 7,8, máximo 38. Continuidad plana en ~3e-2, sin divergir.
- OBS: 09-resultado no calculó r_salida_rotor_m (−1,8e308). El D2 se validó con el radio de BladeTE (229,5 mm).
## G006_nq15_V  veredicto=OK  remallados=0 base=4.3 relaj_bajada=False graves=[] avisos=[]
motivo: Sin error clave: 1000 iteraciones, 1,61 M celdas, balance de masa 0,11 %, H 1,22 × diseño, η 0,56 y D2 a −0,05 %. H deja de derivar hacia la it. 700 y oscila 3,7 % (pico a pico) en 801–1000.
- INC: 06-euler.java: entrada/salida del rotor fijadas por nombre (eIn/eOut) porque el radio medio daba 0 antes de resolver
- INC: Wall Y+ no disponible en la exportacion EnSight (la escena y el resumen de y+ si funcionaron)
- INC: H CFD 21,7 % por encima de H de diseno; H sube hasta la it. 700 y luego oscila (patron NQ15 de lecciones)
- OBS: H CFD 86,8 m frente a 71,3 m de CFturbo (+21,7 %), dentro del rango; η_Euler 0,92 y factor de deslizamiento 0,56.
- OBS: η ≈ 0,56 baja por la fricción de disco de las cámaras laterales (como G003); no es error de fronteras.
- OBS: Oscilación de H: chequeos.json da 1,8 % (semiamplitud) y RESUMEN 3,7 % (pico a pico); ambas bajo el 5 %.
- OBS: Continuidad plana en 1,5e-2 y balance de masa 0,11 %: normal en estas bombas.
- OBS: y+ en álabes medio 8,3 (máx. 65,8): ni rango log ni y+≈1; aceptable con all-y+.
- OBS: U2 del reporte Euler (43,1 m/s) se mide en la interfaz de salida del rotor (r 137 mm), no en el borde de salida (r 125,3 mm).
- OBS: Escenas coherentes: presión creciente hacia la periferia en el rodete; recirculación en el difusor/tubo de salida, sin flujo al revés en la frontera.
## G007_nq20_B  veredicto=OK  remallados=0 base=4.3 relaj_bajada=False graves=[] avisos=[]
motivo: Sin error clave tras seguir hasta la it. 1500: oscilación de H 1,5 % (semirrango) en 1301–1500, balance de masa 0,018 %, η 0,715 y H/H_diseño 1,29 dentro de rango, η_Euler 0,93 (< 1, el transitorio de pt_out ya pasó). H aún baja despacio, pero se aplana en las últimas 10 it.
- INC: 06-euler.java: entrada/salida del rotor fijadas por nombre (radio medio 0,0 sin solución inicial)
- INC: intento 2: 1000 -> 1500 it. sin remallar ni cambiar física/relajación; promedios sobre 1301-1500
- INC: H deriva -2,8 % en 1301-1500 (pico 94,1 m en la it. 1180, 87,7 m en la 1500; semirrango 1,5 %): supera el 2 % pedido por el revisor
- INC: H CFD media 89,4 m supera el diseño (69,1 m) un 29 %; eta_Euler 0,93
- INC: escenas 11b-11d no recreadas (ya existían); 12 PNG exportados
- OBS: H no está plano del todo: pico de 94,1 m en la it. ~1180; luego baja de 90,2 m (it. 1300) a 87,7 m (it. 1500), −2,8 %. Se estanca en 87,71 m en las it. 1496–1500. Valor final probable ≈ 87–88 m: la media de 89,4 m puede quedar ~2 % alta.
- OBS: M plano en 99,0–99,6 N·m (en el intento 1 era ~105). P_eje 31,1 kW, P_hid 21,9 kW.
- OBS: H CFD 27–29 % sobre los 69,1 m de diseño: alto pero dentro de 0,5–1,6. Encaja con el H_Euler de 94,5 m; CFturbo parece subestimar la altura en NQ20.
- OBS: Euler (it. 1500): Vu2 21,8 m/s, factor de deslizamiento 0,56 con β2 = 20°. El U2 de 42,5 m/s se mide en r = 135 mm (interfaz); el álabe sale en r = 125 mm.
- OBS: Malla de 1,53 M celdas (76 % en el rotor). D2 249,9 mm (−0,1 %). y+ en álabes: medio 9,1 y máx. 35, zona intermedia, aceptable para el lote.
- OBS: Continuidad en 2,1e-2, plana; como en G001, no invalida el resultado.
- OBS: Escenas: 11b–11d son del intento 1, no se recrearon a la it. 1500; los PNG de fluido corresponden a la it. 1000.
## G008_nq22_B  veredicto=OK  remallados=0 base=4.2 relaj_bajada=False graves=[] avisos=[]
motivo: Sin errores clave: 1500 iteraciones, H asentada en 86,5–89,3 m en 1301–1500 (rango 3,2 %, deriva −2,4 %), η_Euler 0,952 < 1, balance de masa 0,05 %. H +29 % sobre el diseño, dentro de 0,5–1,6.
- INC: 06-euler: autodetección de entrada/salida dio radio 0; forzadas por nombre en la macro del caso (Inflow [int_entrada 1], Outflow [int_salida 1])
- INC: U2 del reporte Euler 42,19 m/s vs 39,0 de CFturbo (frontera de salida del rotor incluye cubierta); radio de salida de álabe 0,1242 m coincide con D2
- INC: 09-resultado: r_salida_rotor_m sin dato (-1.8e308)
- INC: Wall Y+ no disponible en exportación EnSight de superficies
- INC: Intento 2: MAX_IT de 07 a 1800 y it0 de 08 a 1300; escenas borradas y recreadas para no duplicarlas
- OBS: Tendencia de H por tramos: 83,3 (1100) → 88,5 (1200) → 89,0 (1300) → 86,6 (1400) → 86,9 (1500); pico ~90 m en la it. ~1040. M bajó de 118 a 113 N·m entre la 1000 y la 1500.
- OBS: H/H_diseño 1,29 y η 0,728: la η más alta de las NQ ≤ 22 del lote; menos peso relativo de la fricción de disco que en NQ15.
- OBS: Malla 1,56 M celdas (76 % en el rotor), sin remallar. y+ en álabes medio 8,9, máx. 33,6.
- OBS: D2 del álabe 248,3 mm (+0,02 %). El U2 de Euler (42,19 m/s) se mide en r = 134 mm (interfaz de salida del rotor, no el borde del álabe); por eso H_Euler, η_Euler y el factor de deslizamiento 0,54 son aproximados, como en G007.
- OBS: 06-euler necesitó fijar las fronteras de entrada/salida del rotor por nombre (la autodetección dio radio 0).
- OBS: Continuidad plana en ~1,4e-2, normal en estas bombas.
## G009_nq25_B  veredicto=OK  remallados=0 base=4.1 relaj_bajada=False graves=[] avisos=[]
motivo: Sin error clave: 1000 it., 1,47 M celdas, balance de masa 0,01 %, H/H_diseño 1,30 y η 0,76 dentro de rango, oscilación de H 1,6 % en 801–1000 con el pico ya pasado (88,1 m en la 900, 87,7 en la 1000).
- INC: 06-euler: radio medio 0 sin solución; fijados entrada/salida del rotor por nombre (Inflow [int_entrada 1], Outflow [int_salida 1])
- INC: U2 de Euler 41,8 m/s vs 38,6 de diseño; factor de deslizamiento 0,55 no fiable
- INC: H 30 % sobre el diseño con eta_Euler 0,97: revisar
- INC: H pico 88,2 m hacia la it. 900, 87,7 en la 1000; oscilación en 801-1000 de 85,5 a 88,2
- OBS: H 30 % sobre el diseño (66,9 m), igual que G007/G008 (NQ20–22 base asentados en 86–89 m): sesgo sistemático del método o de CFturbo, no un error de este caso.
- OBS: η_Euler 0,97 < 1: pt_out ya no está en el transitorio que dio η_Euler > 1 en G007/G008 a la it. 1000.
- OBS: U2 del reporte Euler 41,8 m/s frente a 38,6 de diseño: la interfaz de salida del rotor llega a radios mayores que el borde del álabe; factor de deslizamiento 0,55 no fiable. D2 por BladeTE 245,9 mm ≈ diseño (0,07 %).
- OBS: y+ en álabes medio 9,1 (máx. 32,8): zona de transición, ni wall-resolved ni log-law; aceptable para el lote.
- OBS: Continuidad plana en ~6–12e-3, como en el resto del lote. Escena fluido_medio limpia: flujo bien orientado hacia la salida, sin reflujo visible.
## G010_nq25_V  veredicto=OK  remallados=0 base=3.4 relaj_bajada=False graves=[] avisos=[]
motivo: Sin error clave: 1000 it., 1,76 M celdas, balance de masa 0,004 %, H 0,66 × diseño y η 0,61 dentro de rango, oscilación de H 1,5 %. La H baja cuadra con el recorte (fD2 0,854) y el β2 −4,9° de la variante, no con un fallo.
- INC: 06-euler: radios medios dieron 0 sin solución; fijé eIn/eOut por nombre en la macro del caso
- INC: resultado_solver.json: r_salida_rotor_m inválido (-1.8e308); r_salida_alabe_m 0.105 m válido
- INC: Wall Y+ no exportado como campo EnSight
- INC: H 44,1 m (801-1000) muy por debajo del diseño 66,9 m; H aún sube ~0,5 m en las últimas 100 it.
- INC: solver arrancó con np 14 en vez de 4
- OBS: H_diseno 66,9 m es el de la bomba base (igual que G009). Por semejanza fD2² · 66,9 = 48,8 m; los 44,1 m quedan un 10 % por debajo, coherente con β2 4,9° menor. G009 base dio 87,3 m: 44,1/87,3 = 0,51.
- OBS: D2 medido 210,0 mm (r de salida del álabe 0,105 m), +0,07 % frente al esperado: la variante es la que dice su nombre.
- OBS: U2 del reporte Euler (41,8 m/s) se mide en la interfaz de salida del rotor (r ≈ 0,133 m), no en el álabe recortado (33,0 m/s). H_Euler 50,6 m y η_Euler 0,886 valen (U·Vu se conserva en el hueco sin álabes); el factor de deslizamiento 0,31 no sirve: usa ese U2 y β2 26,1° de la base.
- OBS: η 0,61 frente a 0,76 en G009: el rodete recortado deja un hueco grande con la voluta original y la fricción de disco pesa más sobre una P_eje menor.
- OBS: H aún sube ~0,5 m en las últimas 100 it. tras un mínimo en la ~850; la media 801–1000 puede quedar ~1 % corta.
- OBS: Escenas sanas: presión creciente con el radio, sin flujo al revés en la salida; recirculación pequeña en el arranque del difusor. y+ álabes medio 8,4 (máx. 33,8). Wall Y+ no salió en el EnSight.
- OBS: r_salida_rotor_m en resultado_solver.json es −1,8e308 (dato inválido del chequeo de radios); no afecta a los resultados.
## G011_nq25_V  veredicto=OK  remallados=0 base=3.9 relaj_bajada=False graves=[] avisos=[]
motivo: Con 1500 it. H se asienta: 91,1–91,9 m en 1301–1500 (±0,4 %), balance de masa 0,005 %, 1,55 M celdas, H 1,37 × diseño y η 0,81, todo dentro de límites. η_Euler 1,014 no es un error clave: el H_Euler se mide en la interfaz del rotor, no en el álabe recortado, así que sale subestimado.
- INC: eta_Euler 1,014 al final (0,97 en la it. 1100); H_Euler subestimado por medirse en la interfaz del rotor
- INC: 06-euler: seleccion automatica de entrada/salida dio radio 0; se forzaron los nombres de interfaz en la macro del caso (intento 1)
- INC: H media 1301-1500 91,47 m vs fD2^2*H_diseno 64,4 m (+42 %)
- INC: escenas duplicadas '... 2' al reabrir; PNG sobrescritos; Wall Y+ no disponible en el export EnSight
- INC: macros editadas: 07 MAX_IT 1500, 08 it0 1300
- OBS: Intento 2 siguió de la it. 1000 a la 1500 sin remallar. H tuvo un pico de ~91,9 m hacia la 1060 y se asentó; frente a la media 801–1000 del intento 1 (88,7 m) sube un 3 %.
- OBS: Variante de la base NQ25 (G009: 87,3 m): por semejanza, fD2² · 87,3 = 84,0 m. Los 91,5 m dan +9 %, coherente con Z 7 y β2 +4,6°. Frente a fD2² · H_diseno = 64,4 m sale +42 %, porque el H_diseno del lote es el de la base.
- OBS: D2 medido 241,24 mm, +0,07 % frente al esperado: la variante es la que dice su nombre.
- OBS: η_Euler 1,014 en la it. 1500, ya con H estable: es un artefacto del reporte (U2 41,8 m/s y Vu2 medidos en la interfaz), no un transitorio. Lo mismo con el factor de deslizamiento de 0,54: no sirve.
- OBS: Plano medio sano: TotalHead crece hacia la voluta y la salida, y no hay flujo al revés en la salida. Se ve una pequeña recirculación en el arranque del difusor de salida.
- OBS: y+ en los álabes: medio 7,8, máximo 32,9 (zona de amortiguamiento, válido con all-y+). Continuidad 2,4e-3.
- OBS: Presión mínima muy negativa en el borde de ataque (entrada a 0 Pa total): habría cavitación en la realidad, y el modelo no la representa.
## G012_nq25_V  veredicto=OK  remallados=0 base=3.8 relaj_bajada=False graves=[] avisos=[]
motivo: Sin error clave: 1500 it., 1,50 M celdas, balance 0,0013 %, H 1,07 × diseño (1,18 × fD2²·H), η 0,76, oscilación 0,7 % en 1301–1500 y D2 +0,07 %. H aún sube despacio (~0,5 m/100 it., ritmo decreciente) con M plano: la media puede quedar ~2–4 % por debajo del valor asintótico, aceptable sin ser estrictos.
- INC: 06-euler: radio medio 0 antes de iterar; fijados eIn/eOut en la macro del caso (Inflow [int_entrada 1], Outflow [int_salida 1])
- INC: Intento 2: .sim reabierto en it. 1000, seguido hasta 1500 sin remallar ni tocar fisica/relajacion; MAX_IT=1500 en 07 y it0=1300 en 08
- INC: H sin estabilizar del todo a la it. 1500 (69,1 en 1000, 70,9 en 1300, 71,9 en 1500) con M plano
- INC: Reversed flow en inlet de ext_entrada al inicio (desaparece hacia la it. 117)
- INC: Wall Y+ no disponible en la exportacion EnSight; y+ de alabes por reporte: medio 8,8, max 32,2
- INC: Escenas viejas borradas del .sim y regeneradas (9 PNG)
- OBS: Evolución de H: 69,08 (1000) → 70,28 (1200) → 70,91 (1300) → 71,44 (1400) → 71,93 m (1500); deriva 0,7 → 0,5 m/100 it. M plano desde la 1000 (112,1 → 111,3 N·m). Si se quiere el valor final, H ≈ 73–74 m y η ≈ 0,78 por extrapolación.
- OBS: H frente a fD2² · 66,9 = 60,8 m: +18 %; frente a la NQ25 base G009 escalada (fD2² · 87,3 = 79,3 m): −10 %, coherente con Z 5.
- OBS: D2 medido 234,36 mm (+0,07 %): la variante es la que dice su nombre.
- OBS: η_Euler 0,933 y factor de deslizamiento 0,46: U2/Vu2 medidos en la interfaz, no en el álabe recortado; no fiables.
- OBS: y+ álabes medio 8,8, máx. 32,2 (zona de transición, no 30–300). Continuidad 1,7e-3. Reflujo en ext_entrada solo hasta la it. ~117.
- OBS: r_salida_rotor_m sin dato (−1,8e308: Outflow del rotor es interfaz); Wall Y+ no exportado a EnSight.
## G013_nq25_V  veredicto=OK  remallados=0 base=3.6 relaj_bajada=False graves=[] avisos=[]
motivo: Sin errores clave tras seguir hasta 1500 it.: 1,70 M celdas, balance 0,0007 %, H 66,8 m (1,00 × diseño), η 0,749, oscilación 0,49 %, D2 +0,07 %. H aún sube ~1 % en 1301–1500, aceptable con el criterio no estricto.
- INC: 06-euler: radio medio de interfaces 0 antes de iterar; eIn/eOut fijados en la macro del caso
- INC: Reversed flow en ext_entrada/inlet al inicio, desaparece hacia la it. 122
- INC: H aun subiendo ~0,3 m/100 it. al final de 1500 it.; media 1301-1500 ~0,4 m bajo el valor final
- INC: Factor de deslizamiento 0,44 no fiable (U2 de la interfaz)
- INC: Wall Y+ no exportado a EnSight; r_salida_rotor_m sin dato (frontera de interfaz)
- INC: Escenas duplicadas en el .sim por reejecutar 11a-11d; PNG regenerados
- OBS: H cada 100 it. de la 1000 a la 1500: 65,1 → 65,4 → 66,2 → 66,6 → 66,7 → 67,2 m. La media de 1301–1500 queda ~0,4 m por debajo del valor final (67,2 m).
- OBS: M bajó de 108,4 a 105,2 N·m (−3 %) y η subió de 0,69 (intento 1) a 0,749 (final 0,756).
- OBS: H frente a fD2² · 66,9 = 55,4 m: +21 %; frente al H del lote base: −0,2 %. Coherente con Z 7 (menos deslizamiento).
- OBS: D2 medido 223,78 mm (+0,07 %): la variante es la que dice su nombre.
- OBS: η_Euler 0,92 y factor de deslizamiento 0,44: U2/Vu2 medidos en la interfaz, no en el álabe recortado; no fiables.
- OBS: y+ álabes medio 8,2, máx. 33,5 (zona de transición). Continuidad 9,2e-4. Reflujo en ext_entrada solo hasta la it. ~122.
- OBS: Escena del plano medio coherente: velocidad relativa ordenada en los canales, TotalHead creciente hacia la voluta y flujo limpio en el difusor de salida.
- OBS: Escenas duplicadas («… 2») en el .sim por el reintento; los PNG se sobrescribieron con los nuevos.
## G014_nq30_B  veredicto=OK  remallados=0 base=3.8 relaj_bajada=False graves=[] avisos=[]
motivo: Sin error clave: 1000 iteraciones, 1,46 M celdas, balance de masa 0,004 %, H 61,8 m (0,955 × diseño) estable ±0,2 %, η 0,806 y D2 medido 237,9 mm (−0,08 %).
- INC: 06-euler: radio medio 0 antes de iterar; fijadas entrada y salida del rotor por nombre en la macro del caso
- INC: U2 del reporte Euler (42,0 m/s) es el de la interfaz, no el del álabe (D2 237,9 mm)
- INC: M baja ~1 % por 100 it. hasta la 1000; H estable
- INC: Wall Y+ no exportado en superficies; PNG de y+ correcto
- OBS: H 4,5 % bajo el diseño (64,7 m); η_Euler 0,908 < 1, sin señal de transitorio en pt_out.
- OBS: M sigue bajando ~1 % por cada 100 it. (125,8 → 123,2 N·m): η final 0,813 frente a la media 0,806; con más iteraciones η subiría algo, H ya está asentada.
- OBS: Continuidad 2,3e-3 (aceptable según criterio del lote).
- OBS: y+ en álabes medio 13, máx. 38: zona buffer, ni bajo-y+ ni log-law limpio.
- OBS: 06-euler falló de primeras (radio medio de interfaces 0 antes de iterar); el ejecutor fijó a mano int_entrada/int_salida. U2 Euler 42,0 m/s es el de la interfaz (r 133,7 mm), no el del álabe (37,4): factor de deslizamiento 0,48 no comparable con diseño.
## G015_nq35_B  veredicto=OK  remallados=0 base=3.5 relaj_bajada=False graves=[] avisos=[]
motivo: Sin error clave: 1000 iteraciones, 1,64 M celdas, balance de masa 0,003 %, H 0,87 × diseño, η 0,82 y H estable (±0,2 % en 801–1000). D2 medido 233,8 mm (+0,08 %).
- INC: 06-euler: fijados eIn/eOut a las interfaces int_entrada/int_salida (radio medio 0 sin solución, lección G014)
- INC: factor de deslizamiento 0,43 no fiable (U2/Vu2 medidos en la interfaz)
- INC: resultado_solver.json: r_salida_rotor_m = -1.8e308 (sin Outflow válido); H, M, eta no afectados
- INC: M baja ~0,5 %/100 it. al final (137,0 N·m en la it. 1000); H estable desde ~it. 640
- INC: H media 13,3 % bajo H de diseño; y+ en álabes medio 13,3 (máx. 36,7)
- OBS: H 54,1 m, un 13 % bajo los 62,4 m de diseño; H_Euler 60,0 m y η_Euler 0,90, coherentes (base, sin señal de transitorio).
- OBS: M todavía baja ~0,5 %/100 it. al final (137,0 N·m en la 1000): η podría subir ~1 punto con más iteraciones; no cambia el veredicto.
- OBS: y+ en álabes medio 13 (máx. 37): en la zona de transición, fuera de 30–300 y de < 5; el SST all-y+ lo tolera, pero la η fina tiene algo de incertidumbre.
- OBS: Factor de deslizamiento 0,43 no fiable: U2/Vu2 se miden en la interfaz, no en el borde de salida.
- OBS: r_salida_rotor_m = −1,8e308 en resultado_solver.json (sin frontera Outflow válida); no afecta a H, M ni η.
- OBS: Plano medio en z = 55,3 mm: rodete y voluta bien cortados, flujo coherente hacia la salida, sin reflujo visible.
## G016_nq35_V  veredicto=OK  remallados=0 base=3.4 relaj_bajada=False graves=[] avisos=[]
motivo: Todos los chequeos graves pasan: 1000 iteraciones, 1,63 M celdas, balance de masa 0,003 %, H 0,82 × diseño con oscilación 0,12 %, η 0,816 y D2 del álabe a 0,08 % del esperado.
- INC: 06-euler: radio medio de interfaces 0; fijados eIn/eOut a mano (leccion G014)
- INC: H CFD 51,4 m vs 61,2 m esperados (fD2^2*62,4): -16 %
- INC: M sigue bajando ~1 %/100 it. al final de 1000 it.
- INC: r_salida_rotor_m de 09-resultado sin valor (-1.8e308)
- OBS: H 51,4 m frente a 62,4 m de diseño (−18 %; −16 % frente a 61,2 m corregido por fD2²): dentro de rango, típico de la serie.
- OBS: M baja ~1 %/100 it. (−2 % en 801–1000) y la continuidad queda en 3e-3: η puede subir algo más con más iteraciones; H ya es estable.
- OBS: D2 medido en el álabe 231,5 mm (r 115,7 mm). La U2 = 41,3 m/s del reporte Euler es la de la interfaz de salida (D ≈ 263 mm), no la del álabe: el factor de deslizamiento 0,39 está calculado con esa U2 y no es representativo.
- OBS: η_Euler 0,895, H_Euler 57,3 m; y+ en álabes medio 12,5 (máx. 32,5), zona de transición: la pérdida por fricción puede estar mal estimada, aceptable para comparar variantes.
- OBS: r_salida_rotor_m no se midió (−1,8e308) en 09-resultado.java; no afecta al veredicto.
## G017_nq35_V  veredicto=OK  remallados=1 base=3.3 relaj_bajada=False graves=[] avisos=[]
motivo: Todos los chequeos graves pasan: 1000 iteraciones, 1,78 M celdas, balance de masa 0,004 %, H 0,68 × diseño (−20 % frente a fD2² · H = 53,0 m) con oscilación 0,97 %, η 0,775 y D2 a 0,08 % del esperado.
- INC: 1.ª malla + extensiones 1,96 M celdas (>0,93×2 M): remallado con base 3,3 mm → 1,78 M
- INC: 06-euler: eIn/eOut fijados a mano en la macro del caso (lección G014)
- INC: Wall Y+ no exportado a EnSight (sin efecto)
- INC: r_salida_rotor_m = -1,8e308 en resultado_solver.json (no calculado)
- OBS: H 42,35 m frente a 53,0 m corregido por fD2² (0,922): −20 %, algo más bajo que G016 (−16 %); dentro de rango para una variante Z 7 con β2 +3,7°.
- OBS: H y M bajan a la par en 801–1000 (H 42,86 → 42,03 m, −1,9 %; M 115,96 → 112,91 N·m, −2,6 %) con η estable en 0,773–0,779: la media de H puede quedar ~1 % alta; no cambia el veredicto.
- OBS: η_Euler 0,847, H_Euler 49,6 m. U2 = 41,3 m/s es la de la interfaz, no la del álabe (D2 215,6 mm → U2 ≈ 33,9 m/s): el factor de deslizamiento 0,33 no es representativo.
- OBS: Remallado con base 3,3 mm porque las extensiones sumaron +21 % de celdas (1,96 M); malla final 1,78 M. Continuidad en 3,3e-3 a la it. 1000.
- OBS: y+ en álabes medio 12,5 (máx. 63,9), zona de transición: fricción poco precisa, aceptable para comparar variantes.
- OBS: r_salida_rotor_m no calculado (−1,8e308); 06-euler necesitó fijar eIn/eOut a mano (lección G014).
## G018_nq35_V  veredicto=REVISAR  remallados=0 base=3.2 relaj_bajada=False graves=['H / H diseño'] avisos=[]
motivo: H 25,3 m = 0,41 × diseño (0,46 × fD2² · H = 55,5 m; CFturbo da 52,5 m en su .cfturbo-ccm): fuera de 0,5–1,6. La corrida es sana (1000 it., H plana ±0,8 %, balance 0,001 %, D2 a 0,08 %, mismo montaje y giro que G016/G017), así que reintentar no lo cambia: una persona debe decidir si la variante Δβ2 −6,2° (β2 13,6°) con Z 6 es válida o está mal generada.
- INC: 06-euler: eIn/eOut fijados a mano (Inflow [int_entrada 1] / Outflow [int_salida 1]), lección G014
- INC: H media 25,29 m frente a 62,4 m del lote (fD2^2*H = 55,5 m); H plana al final, M plana
- INC: salidas de 02 y 07 superan el límite de tokens de la herramienta; datos leídos del archivo
- OBS: Nada numérico apunta a un fallo: M positivo como en el resto de la serie, Q_out = Q_in, continuidad 3,4e-2 plana (normal), y+ álabes medio 13,2 (máx. 60).
- OBS: La H baja viene del rodete: Vu2 7,75 m/s en la interfaz (r ≈ 0,131 m) → ≈ 9,3 m/s en el álabe (r 0,110 m), Vu2/U2 ≈ 0,27 con U2 34,6 m/s. H_Euler 32,6 m, η_Euler 0,78. Con β2 13,6° una estimación 1D (Cm2 ≈ 5 m/s, desliz ~0,75) da Vu2 ≈ 10–11 m/s: el orden de magnitud cuadra con la física, no con un 
- OBS: Pero CFturbo predice 52,5 m (Δpt 514 kPa en las condiciones de salida del .cfturbo-ccm): o el 1D de CFturbo no recoge el β2 tan bajo, o el álabe exportado no es el que dice el nombre. Merece mirar el β2 real del CAD.
- OBS: Escenas coherentes: presión creciente con el radio en los álabes, flujo hacia la salida en la voluta, sin reflujo en la salida. El rodete se ve mucho más envuelto que G016 (álabes largos y planos), consistente con β2 bajo.
- OBS: η 0,64 (G016 0,82, G015 base 0,82): la fricción de disco pesa más sobre una P_eje de 25,9 kW. Factor de deslizamiento 0,26 no fiable (U2 de la interfaz).
- OBS: r_salida_rotor_m = −1,8e308 y 06-euler con eIn/eOut fijados a mano (lección G014); no afectan.
## G019_nq35_V  veredicto=REVISAR  remallados=1 base=3.2 relaj_bajada=False graves=['H / H diseño', 'ejecutor terminó'] avisos=[]
motivo: H 14,5 m = 0,23 × diseño (0,31 × fD2² · H = 47 m; CFturbo da Δpt 504 kPa ≈ 51,5 m en su .cfturbo-ccm): fuera de 0,5–1,6. El montaje es el de G016–G018 (1000 it., balance 0,007 %, D2 a 0,08 %, M positivo, Vu1 ≈ 0) y el rodete solo da H_Euler 24,6 m, así que reintentar no lo arregla: una persona debe mirar si la variante fD2 0,869 + Δβ2 −3,1° está bien generada.
- INC: Tras 03-extensiones el total fue 2,118 M > máximo 2,0 M (las extensiones sumaron 23 %, no 5-8 %): base 2,9 -> 3,2 mm y 02-malla remalló todo (1,815 M)
- INC: 06-euler: radio medio 0 sin solución; se fijaron eIn/eOut a Inflow/Outflow [int_entrada/int_salida 1] (como G014)
- INC: El servidor arrancó con -np 14 (el CLAUDE.md dice 4): no afecta al resultado, revisar .env
- INC: yplus_alabes medio 14,1 / máx 44; r_salida_rotor_m salió -1.8e308 en 09-resultado (chequeo D2 no válido, usar U2 del Euler: 41,3 m/s)
- INC: Sin DIVERGE; continuidad 0,15 -> 0,03-0,07
- OBS: Peor que G018 con la mitad de Δβ2 (−3,1° frente a −6,2°): H 0,31 frente a 0,46 de su diseño escalado y M 58 frente a 82,5 N·m. Ese orden no lo explica β2; apunta al recorte fD2 0,869 o al CAD exportado.
- OBS: El rodete trabaja poco: Vu2 5,8 m/s en la interfaz (r 0,1315 m) → ≈ 7,6 m/s en el álabe (r 0,1016 m), Vu2/U2 ≈ 0,24 con U2 31,9 m/s; H_Euler 24,6 m frente a ~57 m que pide CFturbo. P_eje 18,3 kW (CFturbo implicaría ~40 kW).
- OBS: Pérdidas grandes aguas abajo: η_Euler 0,57. El plano medio muestra una zona separada grande en la garganta de la voluta y el difusor (voluta de la base para un rodete recortado).
- OBS: H no está quieta con M plano: 9,7 / 11,7 / 11,5 / 8,8 / 11,0 / 14,2 / 14,7 / 14,0 m en las it. 300…1000. La oscilación pasa el chequeo (3,7 % en 801–1000) pero la media puede moverse varios metros: tomarla como orden de magnitud.
- OBS: Presión en álabes coherente (crece con el radio), sin reflujo en la salida; y+ álabes medio 14 (máx 44). Continuidad 0,03–0,07 plana (normal en la serie).
- OBS: Incidencias de ejecución sin efecto en el número: solver con -np 14 en vez de 4, eIn/eOut fijados a mano en 06-euler (lección G014), r_salida_rotor_m inválido.
## G020_nq37_B  veredicto=OK  remallados=0 base=3.4 relaj_bajada=False graves=[] avisos=[]
motivo: Sin error clave: 1000 iteraciones, 1,69 M celdas, balance de masa 0,004 %, H 52,1 m = 0,845 × diseño, η 0,823, oscilación de H 0,23 % en 801–1000 y D2 a −0,09 %.
- INC: 06-euler: radio medio de interfaces 0 sin solución; fijados eIn/eOut a 'Inflow [int_entrada 1]' / 'Outflow [int_salida 1]' (lección G014)
- INC: Wall Y+ no disponible en la exportación EnSight de superficies; y+ álabes sí calculado (medio 13,1, máx 34,9)
- INC: U2 del reporte Euler 41,0 m/s es el de la interfaz; el álabe da 36,5 m/s (D2 232,2 mm)
- OBS: H 15 % bajo el diseño de CFturbo (61,6 m), en la línea de las bases anteriores; H_Euler 57,8 m y η_Euler 0,90: el rodete da poco trabajo más que pérdidas grandes.
- OBS: M baja ~1 % y η sube ~1 % a lo largo de 801–1000: la media de η puede quedar ~0,5 punto por debajo del valor asentado (0,829 en la it. 1000).
- OBS: Factor de deslizamiento 0,42 y U2 41,0 m/s están calculados en el radio de la interfaz, no del álabe (U2 álabe 36,5 m/s): no usarlos tal cual.
- OBS: y+ álabes medio 13,1 (máx. 34,9): zona de transición, ni 1 ni 30–300; aceptable para el lote.
- OBS: Residuales: continuidad 1,1e-3, momentos ~1e-3, k/ω 5e-4/7e-5. M positivo con −3000 rpm, igual que el resto de la serie.
- OBS: Incidencias sin efecto en el número: eIn/eOut fijados a mano en 06-euler (lección G014), Wall Y+ no exportado a EnSight, r_salida_rotor_m inválido.
## G021_nq37_V  veredicto=REVISAR  remallados=1 base=3.2 relaj_bajada=False graves=['H / H diseño', 'ejecutor terminó'] avisos=[]
motivo: H 16,2 m = 0,26 × diseño (0,34 × fD2² · H = 48,4 m; el .cfturbo-ccm pide Δpt 519 kPa ≈ 53 m): fuera de 0,5–1,6. La corrida está sana (1000 it., 1,86 M celdas, balance 0,01 %, D2 a −0,09 %, M positivo como toda la serie, H en 16–17 m desde la it. 200) y el rodete solo da H_Euler 26,3 m: reintentar no lo arregla. Una persona debe mirar si la variante (Z 7, Δβ2 −4,2°, fD2 0,886) está bien generada.
- INC: 06-euler: radio medio de interfaces 0; fijado eIn='Inflow [int_entrada 1]', eOut='Outflow [int_salida 1]'
- INC: Remallado 2,9->3,2 mm por 2 162 036 celdas (>2,0 M); final 1 860 875 (0,05 % sobre 0,93 x max, aceptado)
- INC: Wall Y+ no disponible en la exportacion EnSight de superficies
- OBS: Tercera variante NQ35–37 con la misma firma (G018 0,41, G019 0,31, G021 0,34 del diseño escalado): rodete que trabaja poco con corrida plana. La base G020 dio 52,1 m y η 0,82 con el mismo montaje.
- OBS: Vu2 6,3 m/s en la interfaz → Vu2/U2 ≈ 0,15–0,2; H_Euler 26,3 m frente a ~55 m que pediría CFturbo. P_eje 22,3 kW frente a ~145 N·m · 314 rad/s = 45 kW de la base.
- OBS: η_Euler 0,63: pérdidas grandes aguas abajo. El plano medio muestra una zona separada grande en la garganta de la voluta y el difusor (voluta de la base con rodete recortado), como en G019.
- OBS: Presión en álabes coherente (crece con el radio), sin reflujo en la salida ni campo vacío.
- OBS: H muy estable: 16,4 / 16,7 / 17,0 / 16,4 / 16,2 / 16,5 m en las it. 200…1000; oscilación 2,1 % en 801–1000. El número es fiable para esta geometría.
- OBS: y+ álabes medio 13,5 (máx. 60): zona de transición, aceptable para el lote. Continuidad 9e-3 plana.
- OBS: Incidencias sin efecto en el número: un remallado 2,9 → 3,2 mm por celdas, eIn/eOut fijados a mano en 06-euler (lección G014), Wall Y+ no exportado a EnSight, r_salida_rotor_m inválido.
## G022_nq37_V  veredicto=OK  remallados=0 base=3.1 relaj_bajada=False graves=[] avisos=[]
motivo: Corrida sana y completa: 1000 it., 1,83 M celdas, balance de masa 0,009 %, H estable (±0,8 % en 801–1000), D2 medido 217,1 mm (−0,08 %). H 0,58 × diseño base, dentro del rango 0,5–1,6.
- INC: 06-euler: eIn/eOut fijados a mano (radio medio 0 sin solución)
- INC: H baja vs diseño con corrida sana, como G018/G019/G021 (factor de deslizamiento 0,29); para el revisor
- INC: Wall Y+ no disponible en la exportación EnSight de superficies (campo omitido)
- OBS: H 36,0 m = 0,58 × 61,6 m (diseño base) y 0,67 × fD2²·H (53,9 m): cerca del límite inferior, pero coherente con η_Euler 0,86 y H_Euler 41,7 m.
- OBS: M baja ~1 %/100 it. en 801–1000 con η plana (como G017): la media de M y H puede quedar ~1 % alta.
- OBS: Continuidad plana en 1,4e-2, como G001; balance de masa intacto.
- OBS: U2 41,0 m/s y factor de deslizamiento 0,29 se miden en la interfaz (radio mayor que D2/2), no en el borde del álabe: no son comparables con el U2 de diseño 34,1 m/s.
- OBS: y+ álabes medio 12 (máx. 38): zona de transición, ni wall-resolved ni log; aceptable para el lote.
- OBS: Escenas normales: presión creciente hacia la periferia, flujo ordenado en voluta y tubo de salida, sin reflujo visible.
## G023_nq40_B  veredicto=OK  remallados=0 base=3.3 relaj_bajada=False graves=[] avisos=[]
motivo: Todos los chequeos pasan: 1000 iteraciones, 1,72 M celdas, balance de masa 0,002 %, H 0,84 × diseño, η 0,836 y H estable (±0,25 % en 801–1000).
- INC: 06-euler: eIn/eOut fijados a Inflow [int_entrada 1] / Outflow [int_salida 1] (radio medio 0 sin solución)
- INC: resultado_solver.json: r_salida_rotor_m inválido (-1.8e308); sin efecto
- INC: Wall Y+ no disponible en el export EnSight; PNG yplus generado igualmente
- INC: M baja ~0,9 % en 801-1000 (eta media ~0,5 % por debajo del valor final)
- INC: server_start arrancó con np 14 en vez de 4 (.env)
- OBS: H 16 % bajo el diseño (50,5 vs 60,2 m), dentro de lo habitual del lote.
- OBS: D2 medido 229,66 mm vs 229,82 esperado (−0,07 %): la variante base es correcta.
- OBS: M todavía baja ~0,9 % en 801–1000 con η subiendo; la media de η queda ~0,5 % bajo el valor final (0,841).
- OBS: U2 del reporte Euler (40,6 m/s) se toma en la interfaz de salida, no en r2 (ω·r2 = 36,1 m/s): el factor de deslizamiento 0,41 no es comparable; H_Euler y η_Euler 0,90 solo orientativos.
- OBS: y+ en álabes medio 12,6 (máx. 34): zona de transición, aceptable para el lote.
- OBS: r_salida_rotor_m sin valor (−1,8e308) y el servidor arrancó con 14 procesos en vez de 4; no afectan el resultado.
## G024_nq45_B  veredicto=OK  remallados=0 base=3.2 relaj_bajada=False graves=[] avisos=[]
motivo: Todos los chequeos pasan: 1000 iteraciones, 1,74 M celdas, balance de masa 0,002 %, H 0,83 × diseño, η 0,850 y H estable (±0,3 % en 801–1000).
- INC: 06-euler: eIn/eOut fijados a mano (Inflow [int_entrada 1] / Outflow [int_salida 1]) por radio medio 0 sin solución
- INC: 09-resultado: r_salida_rotor_m invalido (-1.8e308), D2 validado con U2/omega
- INC: Wall Y+ no disponible en la exportacion EnSight (PNG yplus si generado)
- OBS: H 17 % bajo el diseño (48,3 vs 58,0 m), en línea con el resto del lote.
- OBS: D2 medido 225,42 mm vs 225,36 esperado (+0,03 %): la variante base es correcta.
- OBS: M baja ~1 % en 801–1000 (177,5 → 174,9 N·m) con η subiendo a 0,853 en la it. 1000: la media de η queda ~0,4 % bajo el valor final.
- OBS: U2 del reporte Euler (39,8 m/s) se toma en la interfaz de salida, no en r2 (ω·r2 = 35,4 m/s, como CFturbo); el RESUMEN dice lo contrario. Factor de deslizamiento 0,41 no comparable; H_Euler 53,8 m y η_Euler 0,894 solo orientativos.
- OBS: y+ en álabes medio 12,1 (máx. 33,5): zona de transición, aceptable para el lote.
- OBS: Plano medio coherente: TotalHead crece del ojo a la voluta y el difusor, sin flujo al revés a la salida.
- OBS: r_salida_rotor_m sin valor (−1,8e308) y 06-euler necesitó fijar a mano las fronteras int_entrada/int_salida (lección G014); no afectan el resultado.
## G025_nq50_B  veredicto=OK  remallados=0 base=3.1 relaj_bajada=False graves=[] avisos=[]
motivo: Todos los chequeos graves pasan: 1000 iteraciones, 1,77 M celdas, balance de masa 0,002 %, H/H_diseño 0,82, η 0,85, H estable (±0,4 % en 801–1000) y D2 del álabe a 0,09 % del esperado.
- INC: 06-euler: eIn/eOut fijados a mano (radio medio 0 sin solución, lección G014)
- INC: 09: r_salida_rotor_m inválido (-1.8e308); D2 validado con el álabe (221,1 mm)
- INC: M baja ~1 %/100 it. en 801-1000 con H estable
- OBS: H 46,0 m frente a 55,8 m de diseño (82 %): dentro del rango, típico de este lote.
- OBS: M baja ~1 %/100 it. al final y η sube despacio: la media de η puede estar ligeramente baja.
- OBS: U2 de Euler 39,05 m/s frente a ω·r2 = 34,7 m/s: el punto de salida del reporte está en un radio mayor que el álabe (≈124 mm), así que H_Euler, η_Euler y el factor de deslizamiento 0,41 no son fiables; H, M y η sí.
- OBS: r_salida_rotor_m inválido (−1,8e308); D2 validado con el álabe (221,1 mm).
- OBS: y+ en álabes medio 11,6, máx. 32,3: zona de transición, aceptable con all-y+.
- OBS: Continuidad 4,7e-4.
## G026_nq50_V  veredicto=OK  remallados=0 base=3.0 relaj_bajada=False graves=[] avisos=[]
motivo: Sin error clave: 1000 iteraciones, 1,96 M celdas, balance de masa 0,002 %, H 0,71 × diseño (0,74 × escalado por fD2²), η 0,83, H estable (±0,3 %) en 801–1000 y D2 a 0,09 % del esperado.
- INC: 06-euler: radio medio de interfaces 0; fijados eIn/eOut en la macro (leccion G014)
- INC: Wall Y+ no disponible en la exportacion de superficies
- INC: H 0,71 x diseno (0,74 x escalado por fD2^2): patron de variantes nq alto como G018/G019/G021; M baja ~0,5 %/100 it. al final
- OBS: H 39,4 m frente a 55,8 m de la base (53,0 m escalado por fD2²): baja, pero en el rango de las variantes sanas (G022 0,67).
- OBS: η_Euler 0,886 y Vu2/U2 ≈ 0,28: corrida coherente; el factor de deslizamiento 0,35 no es fiable porque U2 del reporte es el de la interfaz (39,1 m/s), no el del álabe (33,9 m/s).
- OBS: Malla 1,96 M celdas, al límite de 2 M (objetivo 1,6 M): las extensiones suman ~320 k.
- OBS: M baja ~0,5 %/100 it. al final; no afecta al número.
- OBS: y+ en álabes medio 11,9 (máx. 35): zona buffer, aceptable para SST.
- OBS: Plano medio sin nada raro: flujo ordenado en voluta y difusor de salida.
## G027_nq50_V  veredicto=OK  remallados=1 base=3.0 relaj_bajada=False graves=['H / H diseño'] avisos=[]
motivo: Sin error clave: 1000 it., 1,76 M celdas, balance 0,001 %, η 0,75, H estable (±0,1 % en 801–1000), D2 a 0,09 %. H/H_diseño 0,49 roza el límite solo contra la H de la base; contra el diseño escalado fD2²·H (44,0 m) es 0,62, dentro de rango (lección G010).
- INC: base 2,7 -> 3,0 mm: con extensiones 2 112 452 celdas > max 2 000 000 (extensiones +23 %)
- INC: 06-euler: eIn/eOut fijados a Inflow [int_entrada 1] / Outflow [int_salida 1]
- INC: 09-resultado: r_salida_rotor_m sin valor; Wall Y+ no exportado a EnSight
- OBS: H 27,4 m frente a 55,8 m de la base y 44,0 m escalado por fD2² (0,888): 0,62 del escalado, como G010 (0,66 con fD2 0,854); no es el hundimiento a ≈0,3 de las variantes NQ35–37.
- OBS: η_Euler 0,86, H_Euler 31,8 m, Vu2/U2 ≈ 0,20 en la interfaz: rodete que trabaja poco pero corrida coherente. U2 39,05 m/s es el de la interfaz (r ≈ 124 mm), no ω·r2 = 30,8 m/s; factor de deslizamiento 0,25 no fiable.
- OBS: Escenas sanas: presión en álabes crece con el radio; plano medio con flujo ordenado en voluta y difusor, sin reflujo en la salida.
- OBS: Malla 1,76 M tras remallar 2,7 → 3,0 mm (con 2,7 mm las extensiones daban 2,11 M).
- OBS: y+ álabes medio 11,7 (máx. 93): zona buffer, aceptable para el lote. Continuidad 9e-4.
- OBS: Incidencias sin efecto en el número: eIn/eOut fijados a mano (lección G014), r_salida_rotor_m inválido, Wall Y+ no exportado a EnSight.
## G028_nq50_V  veredicto=OK  remallados=0 base=2.9 relaj_bajada=False graves=[] avisos=[]
motivo: Sin errores clave: 1000 iteraciones, 1,84 M celdas, balance de masa 0,002 %, H 0,67 × diseño con oscilación 0,2 % y η 0,82. D2 medido coincide con el esperado (0,09 %).
- INC: 06-euler: radio medio de interfaces 0; fijados eIn/eOut en la macro del caso (como G014)
- INC: Wall Y+ no disponible en la exportacion EnSight de superficies
- OBS: H 37,2 m frente a 55,8 m de la base (0,67); frente a la base escalada con fD2² (50,9 m) da 0,73, en línea con G026 (0,74) y G027 (0,62).
- OBS: η_Euler 0,880 y H_Euler 42,1 m: la caída de H viene sobre todo de poco Vu2 (10,6 m/s), no de pérdidas.
- OBS: U2 39,05 m/s y factor de deslizamiento 0,32 están calculados en el radio de salida del rotor (124 mm), no en el borde del álabe (105,6 mm, U = 33,2 m/s): el deslizamiento real es mayor que 0,32.
- OBS: Malla 1,84 M celdas, cerca del límite de 2 M (objetivo 1,6 M); rotor 958 k.
- OBS: y+ en álabes medio 10,7 (máx. 31): zona de transición, ni wall-resolved ni log-law; aceptable para el lote.
- OBS: Continuidad 1,9e-3; H plana desde la it. ~700.
## G029_nq50_V  veredicto=REVISAR  remallados=1 base=2.9 relaj_bajada=False graves=['H / H diseño', 'ejecutor terminó'] avisos=[]
motivo: Corrida sana (1000 it., 1,83 M celdas, balance de masa 1e-4 %, H estable ±1,4 %), pero H 9,3 m = 0,17 × diseño base y 0,22 × diseño escalado con fD2² (41,7 m): fuera de 0,5–1,6 por mucho. No es divergencia ni giro al revés (álabes hacia atrás respecto al giro horario y voluta coherente en las escenas); otro intento con la misma receta daría lo mismo: hay que revisar la geometría generada.
- INC: Malla a base 2,7 mm dio 2 073 276 celdas con extensiones (> max 2 000 000): remallado a 2,9 mm, 1 834 685 celdas
- INC: 06-euler.java: eIn/eOut vacios, radio medio 0 sin solucion; fijados a 'Inflow [int_entrada 1]' y 'Outflow [int_salida 1]' (leccion G014)
- INC: H 0,22 x diseño escalado con Vu2/U2 0,086 y corrida estable (no divergencia, M de signo opuesto al giro)
- INC: 09-resultado: r_salida_rotor_m = -1.8e308 (no medido); D2 validado con BladeTE (191,3 mm)
- OBS: Vu2 3,37 m/s en la interfaz (r 124 mm, U 39,05 m/s): Vu2/U2 = 0,086. Llevado al borde del álabe (r 95,6 mm) con r·Vu constante da ≈4,4 m/s frente a U2 30 m/s: el rotor casi no da giro al flujo; con β2 24,6° cabría esperar Vu2 ≈ 13–17 m/s.
- OBS: ψ = 2gH/U2² ≈ 0,20 con U2 del álabe 30 m/s (diseño escalado ≈ 0,91). H_Euler 13,4 m y η_Euler 0,70: la caída viene de poco trabajo del rotor, no de pérdidas.
- OBS: Mucho peor que G027 (NQ50, fD2 0,888, Δβ2 +2,0°: 0,62) y G028 (0,73). Se parece al hundimiento de G019/G021 (fD2 < 0,9, ≈0,3), aquí con Δβ2 −5,8° y Z 5 a la vez.
- OBS: D2 medido 191,25 mm vs esperado 191,08 (0,09 %): el recorte sí se hizo; r_salida_rotor_m no se pudo medir (−1,8e308).
- OBS: Escena de presión en álabes: 5 álabes curvados hacia atrás para el giro −3000 rpm; plano medio sin flujo al revés en la salida.
- OBS: Malla 1,83 M tras remallar a 2,9 mm (2,07 M a 2,7 mm); y+ álabes medio 12,8, máx. 90; continuidad 4e-3.
## G030_nq55_B  veredicto=OK  remallados=0 base=3.0 relaj_bajada=False graves=[] avisos=[]
motivo: Corrida completa y sana: 1000 it., 1,83 M celdas, balance de masa 0,0015 %, H 0,81 × diseño, η 0,84, oscilación de H 0,33 % en 801–1000 y D2 medido 216,7 mm (+0,11 %).
- INC: 06-euler: radio medio de interfaces 0; se fijaron eIn/eOut en la macro (leccion G014)
- INC: 09-resultado: r_salida_rotor_m sin valor (-1.8e308); r_salida_alabe 0,1083 m
- INC: H y M bajan despacio en 801-1000 (~1 % en M); H oscila <1 %
- INC: Wall Y+ no disponible en la exportacion de superficies
- OBS: H 43,6 m frente a 53,6 m de diseño (0,81); η_Euler 0,858 y H_Euler 50,6 m: coherente con una bomba base de NQ55.
- OBS: H y M bajan despacio (~1 % de M entre 801 y 1000) con η plana: la media de H puede quedar ~0,5–1 % alta.
- OBS: Malla 1,83 M celdas, por encima del objetivo de 1,6 M pero dentro del máximo de 2 M (rotor 0,98 M).
- OBS: y+ en álabes medio 11, máx. 31: zona buffer, ni all-y+ fino ni ley de pared plena; aceptable para comparar.
- OBS: U2 del reporte Euler 38,3 m/s (interfaz r ≈ 122 mm), no el del álabe (34,0 m/s): el factor de deslizamiento 0,42 no es representativo.
- OBS: r_salida_rotor_m no se pudo medir (−1,8e308); el radio de salida del álabe sí (108,3 mm).
- OBS: 06-euler necesitó fijar eIn/eOut a mano (lección G014).
## G031_nq57_B  veredicto=OK  remallados=0 base=3.0 relaj_bajada=False graves=[] avisos=[]
motivo: 1000 iteraciones, 1,81 M celdas, balance de masa 0,002 %, H 42,2 m (0,80 × diseño) estable (±0,3 % en 801–1000) y η 0,834: sin error clave.
- INC: 06-euler: eIn/eOut fijados a mano a Inflow [int_entrada 1] / Outflow [int_salida 1] (lección G014)
- INC: 09-resultado: r_salida_rotor_m sin dato (-1.8e308); D2 validado por U2 de la interfaz
- INC: Wall Y+ no disponible en la exportación EnSight de superficies
- OBS: H 20 % bajo el diseño (42,2 frente a 52,8 m); H_Euler 49,8 m, η_Euler 0,845: la altura teórica ya queda corta.
- OBS: D2 medido 214,9 mm (−0,13 %): la geometría es la base esperada.
- OBS: Malla cerca del límite (1,81 M de 2 M); el rotor se lleva 0,97 M.
- OBS: y+ en álabes medio 11,4, máx. 33: zona buffer, ni all-y+ fino ni ley de pared.
- OBS: U2 del reporte Euler (37,96 m/s) es el de la interfaz, no el del álabe (33,8 m/s): H_Euler vale (r·Vu se conserva en el huelgo), pero el factor de deslizamiento 0,42 no es fiable.
- OBS: r_salida_rotor_m sin dato (−1,8e308) en 09-resultado; D2 validado por el radio del álabe.
- OBS: Continuidad final 6,5e-4.
## G032_nq60_B  veredicto=OK  remallados=0 base=3.2 relaj_bajada=False graves=[] avisos=['D2 medido vs esperado %']
motivo: Corrida completa (1000 it.), 1,53 M celdas, balance de masa 5e-5 %, H 0,89 × diseño estable (±0,05 %) y η 0,81. El único aviso (D2 +4,1 %) es de medida: U2 del reporte Euler 36,38 m/s coincide con el diseño (36,4), así que el rodete es el correcto.
- INC: 06-euler: radio medio de interfaces 0 sin solucion; eIn/eOut fijados a mano en la macro del caso (leccion G014)
- INC: 04-fisica: WARN rotor sin CasingHub/CasingShroud; la geometria no trae camaras laterales, M_WALL sin SolidHub/SolidShroud
- INC: 02-malla: salida de run_java_file demasiado grande para el MCP; CELLS_TOTAL leido del archivo guardado
- INC: EnSight: Wall Y+ no disponible en la exportacion; la escena de y+ si se genero
- OBS: D2 por máximo radio de BladeTE 241,3 mm vs 231,7 mm esperado (+4,1 %): borde de salida inclinado (flujo mixto, nq 60); U2/ω da D2 ≈ 231,6 mm, como G047.
- OBS: H 45,75 m (0,89 × 51,4 m), M 260,25 N·m, P_eje 81,8 kW, P_hid 66,1 kW, η 0,808; oscilación de H 0,1 % en 801–1000.
- OBS: H_Euler 56,5 m, η_Euler 0,809 ≈ η; factor de deslizamiento 0,49 con β2 48° (bajo, Vu2/U2 0,42).
- OBS: Giro −3000 rpm con H y M positivas: sentido correcto.
- OBS: y+ álabes medio 13,3 (máx. 104): zona de transición, ni wall-resolved ni log; vale para el lote.
- OBS: Continuidad 2,7e-4 al final; 9 escenas PNG.
## G033_nq65_B  veredicto=OK  remallados=1 base=3.1 relaj_bajada=False graves=[] avisos=['D2 medido vs esperado %']
motivo: Corrida sana de 1000 iteraciones: H 44,10 m (0,90 × diseño), η 0,824, H estable en 801–1000 (0,06 %), balance de masa 1e-5 %, 1,73 M celdas. El aviso de D2 (+4,7 %) es el conocido de nq ≥ 60 (BladeTE inclinado); U2 Euler 36,42 m/s = diseño 36,3.
- INC: Con base 2,9 mm el total con extensiones fue 2 001 702 celdas (> maximo 2 000 000): base 3,1 mm, 1 728 717 celdas
- INC: 06-euler: radio medio de interfaces 0 sin solucion; fijados eIn/eOut a mano (leccion G014)
- INC: D2 por BladeTE 242 mm (+4,9 %), U2 Euler 36,42 m/s = diseno (leccion G032)
- INC: 04-fisica: aviso rotor sin CasingHub/CasingShroud (la geometria no trae camaras laterales)
- OBS: Remallado de 2,9 a 3,1 mm: con 2,9 mm y extensiones daba 2 001 702 celdas (> 2 M).
- OBS: D2 por BladeTE 242 mm vs 231 mm esperado (+4,7 %): mismo patrón que G032/G047; U2 del reporte Euler confirma el diámetro de diseño.
- OBS: η_Euler 0,825 ≈ η 0,824; H_Euler 53,4 m; factor de deslizamiento 0,50 (con β2 38,3°).
- OBS: y+ en álabes medio 13, máx. 62: zona de transición (ni < 5 ni 30–300); aceptable para el lote.
- OBS: 06-euler necesitó fijar eIn/eOut a mano (lección G014).
- OBS: Geometría sin cámaras laterales (sin CasingHub/CasingShroud): sin consecuencia.
## G034_nq65_V  veredicto=REVISAR  remallados=0 base=3.0 relaj_bajada=False graves=['H / H diseño', 'ejecutor terminó'] avisos=['D2 medido vs esperado %']
motivo: Corrida sana (1000 it., 1,77 M celdas, balance de masa 0,001 %, H estable ±0,8 % en 801–1000), pero H 14,1 m = 0,29 × diseño base y 0,39 × diseño escalado con fD2² (36,6 m): fuera de 0,5–1,6. No es divergencia ni giro al revés; es el mismo hundimiento de las variantes con fD2 < 0,9 y Δβ2 negativo (G019/G021/G029): otro intento con la misma receta daría lo mismo, hay que revisar la geometría generada.
- INC: 06-euler: radio medio de interfaces 0 sin solucion; eIn/eOut fijados a Inflow [int_entrada 1] / Outflow [int_salida 1] (leccion G014)
- INC: Wall Y+ no disponible en la exportacion de superficies EnSight; los 9 PNG salieron bien
- INC: H baja de 17 m (it. 300) a 14 m (it. 1000) con M casi plano; oscilacion 0,8 % en 801-1000
- OBS: Vu2 6,73 m/s en la interfaz (U2 36,29 m/s): Vu2/U2 = 0,19; factor de deslizamiento 0,23. H_Euler 24,9 m y η_Euler 0,56: el rotor da poco trabajo y además pierde mucho.
- OBS: H bajó de 17 m (it. 300) a 14 m (it. 1000) con M casi plano; en 801–1000 ya estable.
- OBS: D2 medido 209,1 mm vs esperado 199,2 (+4,95 %, aviso): en NQ ≥ 60 el D2 por BladeTE ya sale ≈ +4 % en las bases (G032), así que no prueba que el recorte falte; fD2 efectivo 0,90–0,86.
- OBS: Escena de presión en álabes: 6 álabes curvados hacia atrás para el giro −3000 rpm; plano medio con la voluta y la salida sin flujo al revés.
- OBS: y+ álabes medio 14,6, máx. 77; continuidad 3e-3 plana. 06-euler necesitó fijar las interfaces a mano (como G014).
## G035_nq65_V  veredicto=OK  remallados=0 base=3.0 relaj_bajada=False graves=[] avisos=['D2 medido vs esperado %']
motivo: Corrida sana: 1000 it., 1,73 M celdas, balance de masa 6e-4 %, H estable (±0,6 % en 801–1000). H 25,3 m = 0,51 × diseño base (dentro de 0,5–1,6, justo) y 0,62 × diseño escalado con fD2² (41,0 m), como G027; η 0,725.
- INC: 06-euler: radio medio de interfaces = 0 antes de iterar; fijados eIn='Inflow [int_entrada 1]' y eOut='Outflow [int_salida 1]' en la macro del caso
- INC: 04-fisica: avisos 'rotor sin CasingHub/CasingShroud' informativos
- INC: servidor arrancó con np 14 en vez de 4
- INC: D2 por BladeTE +4,9 % (221 vs 211 mm); U2 Euler 36,32 m/s = diseño
- OBS: H roza el límite inferior (0,51 × base): con fD2 0,913 y Δβ2 +6,7° el rotor da Vu2/U2 0,26 en la interfaz (Vu2 9,4 m/s, U2 36,3 m/s); H_Euler 34,8 m, η_Euler 0,73, factor de deslizamiento 0,30.
- OBS: D2 por BladeTE 221,5 mm vs esperado 211,0 (+4,96 %, aviso no grave): en NQ ≥ 60 sale ≈ +4–5 % también en bases (G032); no prueba que falte el recorte.
- OBS: Escenas: presión en álabes con 5 álabes y gradiente coherente; plano medio con flujo ordenado hacia la salida de la voluta, sin flujo al revés.
- OBS: y+ álabes medio 14, máx. 77; continuidad 2,7e-3 plana. 06-euler necesitó fijar las interfaces a mano (como G014).
- OBS: El servidor arrancó con np 14 en vez de 4 (132 s/100 it.); no afecta al resultado.
## G036_nq65_V  veredicto=OK  remallados=1 base=3.2 relaj_bajada=False graves=[] avisos=['D2 medido vs esperado %']
motivo: Corrida sana: 1000 it., 1,67 M celdas, balance de masa 2e-4 %, H estable (±0,12 % en 801–1000). H 26,4 m = 0,54 × diseño base y 0,59 × diseño escalado con fD2² (44,8 m), como G027/G035; η 0,745.
- INC: remallado base 3.0 -> 3.2 mm (1.92 M celdas > 0.93 x max)
- INC: 06-euler: eIn/eOut fijados a Inflow [int_entrada 1] / Outflow [int_salida 1] (leccion G014)
- INC: D2 por BladeTE +4.5 % (230.3 vs 220.46 mm); U2 Euler 36.45 m/s = diseno
- INC: H 0.59 x diseno escalado (0.54 x base), roza el chequeo como G027/G035
- OBS: H baja respecto al diseño pero dentro del chequeo: Vu2/U2 0,26 en la interfaz (Vu2 9,5 m/s, U2 36,4 m/s), H_Euler 35,4 m, η_Euler 0,75, factor de deslizamiento 0,34 con β2 31,4°.
- OBS: D2 por BladeTE 230,3 mm vs esperado 220,5 (+4,5 %, aviso no grave). El recorte sí está: radio de salida del álabe 115,2 mm frente a 121,0 mm de la base G033, cociente 0,952 ≈ fD2 0,954. El +4 % es el sesgo de BladeTE en NQ ≥ 60 (G032).
- OBS: En las variantes NQ65 (G034–G036), D2_cfturbo_mm y u2_cfturbo del lote son los de la base (231,09 mm, 36,3 m/s), no los del rodete recortado.
- OBS: Escenas: presión en álabes con 6 álabes y gradiente coherente; plano medio con flujo ordenado hacia la salida de la voluta, sin flujo al revés.
- OBS: y+ álabes medio 15, máx. 59; continuidad 5,9e-4. 1 remallado por celdas (3,0 → 3,2 mm). 06-euler necesitó fijar las interfaces a mano (como G014/G035).
## G037_nq65_V  veredicto=OK  remallados=0 base=3.0 relaj_bajada=False graves=[] avisos=['D2 medido vs esperado %']
motivo: Corrida sana de 1000 iteraciones: H 48,07 m (0,98 × diseño), η 0,833, H estable en 801–1000 (0,11 %), balance de masa 9e-6 %, 1,93 M celdas. El aviso de D2 (+4,8 %) es el conocido de nq ≥ 60 (BladeTE inclinado); r_salida_alabe 120,8 mm frente a 121,0 mm de la base G033 = 0,998 = fD2.
- INC: 06-euler: radio medio de interfaces 0 sin solucion; eIn/eOut fijados a mano (leccion G014)
- INC: Wall Y+ no disponible en la exportacion de superficies
- OBS: Variante Z 7, Δβ2 +2,8°, fD2 0,998: H 1,09 × la base G033 (44,10 m) y M 1,08 ×, con η casi igual (0,833 vs 0,824); coherente con más álabes y β2 mayor.
- OBS: D2 por BladeTE 241,6 mm vs 230,6 mm esperado (+4,8 %): mismo patrón que G032/G033/G047; U2 Euler 36,46 m/s ≈ diseño 36,3.
- OBS: η_Euler 0,834 ≈ η 0,833; H_Euler 57,6 m; factor de deslizamiento 0,53 (β2 41,1°).
- OBS: 1,93 M celdas, cerca del límite de 2 M (rotor 848 k con Z 7).
- OBS: y+ en álabes medio 12,6, máx. 63,7: zona de transición, aceptable para el lote.
- OBS: Continuidad final 3e-4; 06-euler necesitó fijar eIn/eOut a mano (lección G014); sin CasingHub/CasingShroud, sin consecuencia.
## G038_nq70_B  veredicto=OK  remallados=0 base=2.9 relaj_bajada=False graves=[] avisos=['D2 medido vs esperado %']
motivo: Sin errores clave: 1000 iteraciones, H 1,00 × diseño estable (±0,1 %), η 0,853 y balance de masa 0,003 %. El aviso de D2 (+5,5 %) es el conocido del borde de salida inclinado en nq ≥ 60; U2 Euler 35,95 m/s ≈ diseño 36,1.
- INC: 06-euler: eIn/eOut fijados a mano (Inflow [int_entrada 1] / Outflow [int_salida 1]) por radio medio 0, como G014
- INC: D2 por BladeTE +5,5 % (242 vs 229,8 mm), U2 Euler 35,95 m/s coincide con diseño
- OBS: D2 por BladeTE 242,4 mm frente a 229,8 mm (+5,5 %): validado con U2/ω (35,95 vs 36,1 m/s, −0,4 %), como G032/G047.
- OBS: Malla 1 935 670 celdas, a 3 % del límite de 2 M (objetivo 1,6 M): las extensiones suman 491 k.
- OBS: y+ en álabes medio 11,8 (máx. 57,8): zona de amortiguamiento, ni all-y+ fino ni 30–300; aceptable para el lote.
- OBS: η_Euler 0,853 ≈ η 0,853; H_Euler 55,2 m. Factor de deslizamiento 0,49 medido en la interfaz, no en el álabe.
- OBS: Continuidad 5,9e-4 en la última iteración; P_eje 94,9 kW.
## G039_nq72_B  veredicto=OK  remallados=0 base=2.9 relaj_bajada=False graves=[] avisos=['D2 medido vs esperado %']
motivo: Corrida sana: 1000 it., H 0,999 × diseño, η 0,847, balance de masa 3e-4 %, H estable ±0,05 % en 801–1000. El aviso de D2 (+5,5 %) es el borde de salida inclinado de flujo mixto ya conocido (G047/G032); U2 Euler 35,89 m/s ≈ diseño 36,1.
- INC: 06-euler: eIn/eOut fijados a mano (Inflow [int_entrada 1] / Outflow [int_salida 1]) como en G014
- INC: 05-reportes: sin SolidHub/SolidShroud (la geometria no los trae)
- INC: celdas totales 1,966 M tras extensiones (98 % del maximo 2 M; malla base 1,483 M)
- INC: D2 por BladeTE +5,5 % (242,5 vs 229,8 mm); U2 Euler 35,89 m/s = diseno
- OBS: Malla 1 965 773 celdas, a 1,7 % del máximo: las extensiones sumaron +33 % sobre la base (1,48 M).
- OBS: η_Euler 0,848, H_Euler 54,3 m, factor de deslizamiento 0,49 (con β2 49,6°).
- OBS: y+ en álabes medio 11,9, máx. 54: zona de transición, aceptable para el lote.
- OBS: Sin SolidHub/SolidShroud en la geometría: M solo de álabes y cubos mojados del rotor.
## G040_nq75_B  veredicto=OK  remallados=1 base=3.1 relaj_bajada=False graves=[] avisos=['D2 medido vs esperado %']
motivo: Corrida completa y estable (1000 it., H ±0,008 % en 801–1000), 1,77 M celdas, balance de masa 3e-4 %, H 0,99 × diseño y η 0,84. El aviso de D2 (+5,9 %) es el borde de salida inclinado de flujo mixto: U2 Euler 35,76 m/s ≈ 36,0 de diseño.
- INC: base 2,9 mm daba 2,03 M celdas con extensiones (> máx. 2 M): remallado con 3,1 mm → 1,77 M
- INC: 06-euler: eIn/eOut fijados a mano (Inflow [int_entrada 1] / Outflow [int_salida 1]) como en G014
- INC: 04-física: aviso rotor sin CasingHub/CasingShroud (están en estator); M_WALL sin SolidHub/SolidShroud
- INC: Wall Y+ no disponible en la exportación EnSight (PNG yplus sí generado)
- OBS: D2 por BladeTE 242,6 mm vs 229,18 mm (+5,85 %): esperado en nq ≥ 60 (lecciones G047/G032); U2/ω da D2 ≈ 227,6 mm, coherente.
- OBS: η_Euler 0,840, H_Euler 52,9 m; factor de deslizamiento 0,485 con β2 47,6°.
- OBS: y+ en álabes medio 12,7 (máx. 64,7): en la zona de transición, ni all-y+ fino ni 30–300; vale para este lote.
- OBS: Malla remallada con base 3,1 mm (2,9 mm daba 2,03 M con extensiones).
- OBS: Wall Y+ no salió en la exportación EnSight; el PNG de y+ sí.
## G041_nq80_B  veredicto=OK  remallados=1 base=3.2 relaj_bajada=False graves=[] avisos=['D2 medido vs esperado %']
motivo: 1000 iteraciones sin divergencia, 1,70 M celdas, balance de masa 2e-4 %, H 42,61 m = 1,00 × diseño con η 0,844 y oscilación de H 0,03 % en 801–1000. El aviso de D2 (+6,4 % por BladeTE) es el conocido de flujo mixto: U2 Euler 35,55 m/s da D2 ≈ 226 mm ≈ 227,9 esperado.
- INC: base 3,0 mm daba 1,90 M celdas con extensiones (>0,93 x 2 M): remallado con 3,2 mm -> 1,70 M
- INC: 06-euler: eIn/eOut fijados a mano (Inflow [int_entrada 1] / Outflow [int_salida 1]) por radio medio 0 sin solución
- INC: D2 por BladeTE +6 % (flujo mixto); U2 Euler 35,55 m/s ~ diseño 35,8
- INC: avisos 'rotor sin CasingHub/CasingShroud' en 04-fisica: la geometria no trae camaras laterales
- OBS: D2 por BladeTE 242,4 mm (+6,4 %) por borde de salida inclinado (nq 80); U2/ω = 0,1132 m → D2 226,3 mm, coincide con el diseño (lecciones G047/G032).
- OBS: H_Euler 50,4 m, η_Euler 0,845 ≈ η 0,844; Vu1 ≈ 0 (sin prerrotación); factor de deslizamiento 0,48 con β2 44,8°.
- OBS: y+ en álabes medio 13,3 (máx. 70): zona de transición, por debajo de 30–300; no cambia H ni η a este nivel de revisión.
- OBS: Remallado 3,0 → 3,2 mm porque las extensiones sumaban +33 % de celdas (1,90 M → 1,70 M).
- OBS: 06-euler: eIn/eOut fijados a mano por el radio medio 0 de las interfaces (lección G014).
- OBS: Escenas coherentes: presión creciendo hacia la salida del rodete y flujo ordenado en voluta y tubo de salida.
## G042_nq80_V  veredicto=OK  remallados=1 base=3.2 relaj_bajada=False graves=['H / H diseño'] avisos=['D2 medido vs esperado %']
motivo: Corrida sana: 1000 it., 1,73 M celdas, balance de masa 2e-4 %, H oscila 0,3 % en 801–1000. H 19,9 m = 0,47 × H de la base (roza el chequeo) pero 0,58 × el escalado fD2²·H = 34,1 m, como G027/G035; el recorte del álabe cuadra con fD2 (108,1/121,2 mm de G041 = 0,892 ≈ 0,894), así que no es error de montaje y un reintento no la cambiaría.
- INC: malla + extensiones 1,95 M celdas (>0,93 x 2 M): remallado con base 3,2 mm -> 1,73 M
- INC: 06-euler: eIn/eOut fijados a Inflow [int_entrada 1] / Outflow [int_salida 1] (como G014)
- INC: r_salida_alabe +6 % sobre D2 esperado (borde de salida inclinado, nq alto); U2 Euler = omega*r interfaz
- INC: H 0,58 x diseno escalado (fD2^2*H): corrida sana, roza el chequeo de H como G027/G035
- INC: Wall Y+ no disponible en la exportacion EnSight
- OBS: Aviso de D2 (+6,1 %): por el borde de salida inclinado de nq 80 (BladeTE), igual que la base G041 (+6,4 %). Frente a la base, r_salida_alabe 108,1/121,2 mm = 0,892 ≈ fD2 0,894: la variante se generó bien.
- OBS: η 0,683 frente a 0,844 de la base G041 y η_Euler 0,685: el recorte fD2 0,894 con Z 7 pierde mucha eficiencia, no solo altura. Vu2/U2 0,23 y factor de deslizamiento 0,27 (base 0,48).
- OBS: H_Euler 29,1 m; Vu1 ≈ 0 (sin prerrotación).
- OBS: y+ en álabes medio 14,9 (máx. 79): zona de transición, como en la base; no cambia el veredicto.
- OBS: Remallado 3,0 → 3,2 mm porque las extensiones llevaban la malla a 1,95 M (lección G039).
- OBS: Escenas coherentes: presión creciendo hacia la salida del rodete (mínimos locales en los bordes de ataque) y flujo ordenado en voluta y tubo de salida.
## G043_nq80_V  veredicto=REVISAR  remallados=0 base=3.0 relaj_bajada=False graves=['H / H diseño', 'ejecutor terminó'] avisos=['D2 medido vs esperado %']
motivo: Corrida sana (1000 it., 1,93 M celdas, balance de masa 3e-4 %, H oscila 0,14 % en 801–1000), pero H 17,4 m = 0,41 × diseño y 0,47 × el escalado fD2²·H = 36,8 m: fuera de 0,5–1,6 incluso escalado, con Vu2/U2 ≈ 0,20. El recorte cuadra con fD2 (112,6/121,2 mm de G041 = 0,929), así que no es un error de montaje y un reintento no la cambiaría. Como G018/G029/G034, una persona debe confirmar si la variante (Z 5, Δβ2 −6,4°) de verdad da tan poca altura.
- INC: 06-euler: eIn/eOut fijados a mano (Inflow [int_entrada 1] / Outflow [int_salida 1]) por radio medio 0 antes de resolver
- INC: extensiones suman +32 % de celdas: 1,47 M -> 1,93 M (< máximo 2 M), sin remallar
- INC: avisos 04 (rotor sin CasingHub/CasingShroud) y 05 (sin SolidHub/SolidShroud): geometría sin cámaras laterales, sin efecto
- INC: server_start lanzó con np 14
- OBS: Aviso de D2 (+6,4 % frente a 211,7 mm): es el borde de salida inclinado de nq 80 (BladeTE), igual que la base G041 y G042. Frente a la base, r_salida_alabe 112,6/121,2 mm = 0,929 = fD2: la variante tiene el diámetro que dice su nombre.
- OBS: H_Euler 25,4 m, η_Euler 0,686, Vu2 7,04 m/s (Vu2/U2 0,20), factor de deslizamiento 0,25 (con β2 38,4° del lote, poco fiable). Vu1 ≈ 0 (sin prerrotación).
- OBS: η 0,685, igual que G042 (0,683) y frente a 0,84 de la base: las variantes NQ80 recortadas pierden mucha eficiencia.
- OBS: Frente a G042 (fD2 0,894, Δβ2 +0,3°, 0,58 × escalado): aquí, con fD2 0,929 pero Δβ2 −6,4°, H baja a 0,47. Es el Δβ2 negativo el que hunde la altura, como en G029/G034.
- OBS: y+ en álabes medio 14,4 (máx. 76): zona de transición, como en la base; no cambia el veredicto.
- OBS: Escenas coherentes: la presión crece hacia la salida del rodete, con mínimos en los bordes de ataque, y el flujo en la voluta y el tubo de salida está ordenado, sin reflujo.
- OBS: Malla de 1,93 M celdas con base 3,0 mm (las extensiones suman +32 %): cerca del límite de 2 M.
## G044_nq80_V  veredicto=REVISAR  remallados=0 base=3.0 relaj_bajada=False graves=['H / H diseño', 'ejecutor terminó'] avisos=['D2 medido vs esperado %']
motivo: Corrida sana (1000 it., 1,89 M celdas, balance de masa 1e-4 %, H estable ±0,3 %), pero H 13,06 m = 0,31 × diseño base (0,40 × escalado por fD2²), fuera de 0,5–1,6. Es el hundimiento ya visto con Δβ2 negativo y fD2 < 0,9 (G019, G029, G034, G043): física de la variante, no montaje; reintentar no lo cambia.
- INC: 06-euler: eIn/eOut fijados a mano (Inflow [int_entrada 1] / Outflow [int_salida 1]) por radio medio 0 sin solución
- INC: 04-fisica: avisos rotor sin CasingHub/CasingShroud, sin efecto
- INC: H/H_diseno escalado 0,40; Vu2/U2 0,17; eta 0,597; eta_Euler 0,596
- OBS: Vu2/U2 = 0,17 (Vu2 6,1 m/s, U2 35,3 m/s); H_Euler 21,9 m y eta_Euler 0,596: el rotor apenas da trabajo, coherente con la H baja.
- OBS: Recorte verificado frente a la base G041: r salida álabe 105,7/121,2 mm = 0,872 ≈ fD2 0,873. El aviso «D2 medido vs esperado» (6,3 %) viene de comparar con D2 de CFturbo, no de la variante.
- OBS: Escenas coherentes: 6 álabes, presión que crece hacia la salida, flujo por la voluta hacia el difusor sin reflujo visible. Succión local fuerte en los bordes de ataque (p mín. −7e5 Pa): ojo si interesa la cavitación.
- OBS: y+ en álabes medio 14,5 (máx. 80): zona de transición, aceptable para el lote.
- OBS: M positivo con rpm negativas: signo correcto para el giro.
## G045_nq80_V  veredicto=OK  remallados=1 base=3.2 relaj_bajada=False graves=[] avisos=['D2 medido vs esperado %']
motivo: Corrida sana: 1000 it., 1,73 M celdas, balance de masa 0,001 %, H estable (±0,24 % en 801–1000). H 42,17 m = 0,99 × diseño base (1,05 × escalado por fD2²) y η 0,84, dentro de rango.
- INC: 06-euler: eIn/eOut fijados a mano (radios 0)
- INC: 1 remallado por celdas 1,97 M con base 3,0 -> 1,73 M con 3,2
- INC: Wall Y+ no disponible en EnSight (PNG de y+ ok)
- OBS: Recorte verificado frente a la base G041: r salida álabe 117,7/121,2 mm = 0,971 ≈ fD2 0,969. El aviso «D2 medido vs esperado» (6,6 %) es el sesgo de BladeTE en flujo mixto (lección G047), no un error de la variante.
- OBS: Δβ2 +6,3° con fD2 ≈ 0,97 compensa el recorte: H igual a la de la base, sin el hundimiento de G042–G044.
- OBS: H_Euler 50,1 m, η_Euler 0,841; Vu2/U2 0,39. U2 Euler 35,47 m/s (interfaz).
- OBS: y+ en álabes medio 13,5 (máx. 150): zona de transición, aceptable para el lote.
- OBS: M positivo con rpm negativas: signo correcto. Continuidad plana en 2e-3, aceptable.
- OBS: Un remallado (base 3,0 → 3,2 mm) para quedar bajo 2 M celdas.
## G046_nq85_B  veredicto=OK  remallados=0 base=3.3 relaj_bajada=False graves=[] avisos=['D2 medido vs esperado %']
motivo: Corrida sana de 1000 iteraciones: H 0,95 × diseño, η 0,83, balance de masa 4e-5 % y H estable (±0,1 % en 801–1000). El aviso de D2 +7 % es el conocido del borde de salida inclinado en flujo mixto; U2 Euler 35,37 m/s ≈ diseño 35,5.
- INC: 06-euler: eIn/eOut fijados a mano (lección G014)
- INC: rotor sin cámaras laterales: no hay SolidHub/SolidShroud
- INC: D2 por BladeTE +7 % (flujo mixto, U2 Euler 35,37 m/s = diseño)
- INC: Wall Y+ no disponible en el export de superficies
- OBS: D2 por BladeTE 241,8 mm (+7 % sobre 226): borde de salida inclinado (nq 85); U2/ω confirma D2 ≈ 226 mm (lecciones G047/G032).
- OBS: 1,66 M celdas con extensiones (límite 2 M).
- OBS: η_Euler 0,832 y η 0,831, coherentes; H_Euler 46,2 m.
- OBS: Factor de deslizamiento 0,45: bajo, calculado con β2 42,7° en la interfaz; solo informativo.
- OBS: y+ en álabes medio 14 (máx. 73): zona de transición, fuera del rango 30–300 ideal para funciones de pared; aceptable con all-y+.
- OBS: Continuidad 3,6e-4 al final.
## G047_nq90_B  veredicto=OK  remallados=0 base=3.8 relaj_bajada=False graves=[] avisos=['D2 medido vs esperado %']
motivo: sin veredicto del revisor; decidido por los chequeos: todo bien
- INC: 06-euler: radio medio 0 antes de resolver; fijados eIn/eOut por nombre en la macro del caso
- INC: 04-fisica: aviso rotor sin CasingHub/CasingShroud (estan en el estator); sin SolidHub/SolidShroud en esta geometria
- INC: server_start arranco con -np 14 (CLAUDE.md dice 4)
- INC: Wall Y+ no disponible en la exportacion EnSight de superficies; y+ si en escena y resultado_solver.json