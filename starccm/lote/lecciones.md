# Lecciones del lote

Una línea por lección, con fecha y caso. Las escribe el revisor (Opus) y las lee el ejecutor al empezar cada caso.

- 2026-10-28 · G001 · Con el mínimo del rotor al 10 % del base el remallador refina los huelgos de las cámaras laterales
  (CasingHub/SolidHub) a 0,45 mm: 3,8 M celdas. Al 25 %: 1,46 M. Usar 25 % desde el principio.
- 2026-10-28 · G001 · Sin extensiones la presión total de entrada salía 3,4 kPa y H un 7 % más alta: las extensiones
  (3 D entrada, 5 D salida) son parte fija del método.
- 2026-10-28 · G001 · Con relajación 0,5/0,2 desde el inicio la continuidad se queda plana en ~2e-2 y H oscila ±1–2 %
  en 801–1000: es normal en estas bombas (recirculación); no es divergencia.
- 2026-10-28 · G047 · En rodetes de flujo mixto (nq ≳ 70) el chequeo de D2 por máximo radio de BladeTE sale +5–8 %
  (borde de salida inclinado, lado cubierta más afuera); validar D2 con U2/ω del reporte Euler (G047: 35,02 m/s ≈ diseño).
- 2026-10-28 · G002 · En NQ15 base, H seguía subiendo a la it. 800 (48 m a 300, 76 a 800) con M ya estable: 1000
  iteraciones pueden quedarse cortas; vigilar la deriva de H, no solo la de M.
- 2026-10-28 · G003 · En NQ15 la η sale ≈ 0,49 con η_Euler ≈ 0,9: el par incluye la fricción de disco de las cámaras
  laterales (~40 % de P_eje). Es una η baja válida, no un error de fronteras.
- 2026-10-28 · G004 · NQ15 variante (fD2 0,867): H sube ~4 m/100 it. hasta la it. 1000 (28,7 → 50,3 m) con M plano;
  oscilación 8,6 % en 801–1000. En NQ15, 1000 iteraciones no bastan para H: reabrir y seguir sin remallar.
- 2026-10-28 · G004 · Intento 2: seguir de 1000 a 1500 it. bastó. H se estabilizó en 52–55 m (máximo en la 1300, 2,1 % en
  1301–1500) y M bajó ~1 %/100 it. En NQ15, presupuestar ~1500 iteraciones.
- 2026-10-28 · G005 · NQ15 variante fD2 0,904: H llegó a su máximo en la it. 950 (oscilación 4,6 % en 801–1000, al borde
  del límite); con fD2 más alto que G004 estabiliza antes, pero 1000 it. siguen siendo justas en NQ15.
- 2026-10-28 · G006 · NQ15 variante con fD2 0,987: H se estabiliza hacia la it. 700 (oscilación 3,7 % en 801–1000); con fD2
  cercano a 1, 1000 iteraciones bastan.
- 2026-10-29 · G007 · NQ20 base: H sube de forma monótona hasta la it. 1000 (82 → 91 m en 600–1000) con M plano y
  η_Euler > 1 (señal de que pt_out sigue en transitorio); como en NQ15, en NQ ≤ 20 presupuestar ~1500 iteraciones.
- 2026-10-29 · G007 (intento 2) · NQ20 base, 1000 → 1500 it.: H pasa por un pico (94 m en la it. ~1180) y baja hasta
  ~87,7 m en la 1500, con M plano desde la 1000. En NQ ≤ 20, mejor 1500–1800 iteraciones y promediar las últimas 200.
- 2026-10-29 · G008 · NQ22 base: igual que NQ15–20, H sigue subiendo a la it. 1000 (78 → 87 m en 780–1000) con M plano y
  η_Euler 1,03; la regla de ~1500 iteraciones vale al menos hasta NQ22. El chequeo de oscilación usa semirrango: un 4 %
  puede esconder una deriva del 8 %.
- 2026-10-29 · G008 (intento 2) · NQ22 base, 1000 → 1500 it.: H pico ~90 m en la 1040, se asienta en 86,5–89 m desde la
  1300 y η_Euler baja de ~1,03 a 0,95; 1500 it. bastan hasta NQ22.
- 2026-10-29 · G009 · NQ25 base: H pasa por su pico hacia la it. 900 y se asienta en 87–88 m antes de la 1000 (1,6 % en
  801–1000, η_Euler 0,97); desde NQ25, 1000 iteraciones bastan.
- 2026-10-29 · G010 · En variantes, H_diseno_m del lote es el de la bomba base: comparar con fD2² · H_diseno (G004 0,75 ≈
  0,867²; G010 0,66 con fD2 0,854 y β2 −4,9°). El U2 del reporte Euler es el de la interfaz, no el del álabe recortado.
- 2026-10-29 · G011 · NQ25 variante Z 7, β2 +4,6°: a diferencia de G009 base, H sigue subiendo a la it. 1000 (87,6 → 90,1 m
  en 801–1000) con η_Euler 0,998; en variantes con más álabes o β2 mayor, presupuestar ~1500 iteraciones también en NQ25.
- 2026-10-29 · G011 (intento 2) · En variantes con fD2 < 1, η_Euler puede quedar > 1 (1,014) con H ya estable (±0,4 % en
  1301–1500): U2 y Vu2 se miden en la interfaz, no en el álabe recortado. Como señal de transitorio, solo en bombas base.
- 2026-10-29 · G012 · NQ25 variante Z 5, fD2 0,953: H sigue subiendo a la it. 1000 (67,4 → 69,1 m en 801–1000) con M bajando
  despacio. Igual que G011: en todas las variantes NQ25, presupuestar ~1500 iteraciones desde el principio.
- 2026-10-29 · G012 (intento 2) · NQ25 variante Z 5: a diferencia de G011 (Z 7, estable en 1301–1500), H sigue subiendo
  ~0,5 m/100 it. a la it. 1500 con M plano; con menos álabes H converge más lento y 1500 it. dejan la media ~2–4 % baja.
- 2026-10-29 · G013 (intento 2) · NQ25 variante Z 7, fD2 0,910: con Z 7 H también sigue subiendo a la 1500 (66,6 → 67,2 m
  en 1301–1500, ~1 %), aunque menos que con Z 5; M bajó 3 % de la 1000 a la 1500. La regla de Z vs. convergencia no es fija.
- 2026-10-29 · G014 · 06-euler puede fallar antes de iterar: el radio medio de las interfaces sale 0 sin solución. Fijar
  eIn = «Inflow [int_entrada 1]» y eOut = «Outflow [int_salida 1]» (entrada = menor radio en bomba). NQ30 base: 1000 it. bastan.
- 2026-10-29 · G015 · NQ35 base: H estable desde la it. ~640 (±0,2 % en 801–1000) con η_Euler 0,90; 1000 it. bastan, como en
  NQ25–30 base.
- 2026-10-29 · G017 · NQ35 variante Z 7 (fD2 0,922): H y M bajan juntos ~1 %/100 it. en 801–1000 con η plana; 1000 it.
  bastan para η, la media de H queda ~1 % alta.
- 2026-10-29 · G018 · NQ35 variante Δβ2 −6,2° (β2 13,6°), Z 6: H 0,41 × diseño con corrida sana (Vu2/U2 ≈ 0,27, η_Euler
  0,78, H plana); con Δβ2 ≲ −6° la H puede salir del rango 0,5–1,6 por física, no por montaje: REVISAR, no reintentar.
- 2026-10-29 · G019 · NQ35 variante Z 6, Δβ2 −3,1°, fD2 0,869: H 0,31 × diseño escalado (peor que G018 con Δβ2 −6,2°) y
  Vu2/U2 ≈ 0,24 con corrida sana; la H baja no sigue solo a Δβ2, el recorte fD2 fuerte también la hunde: REVISAR.
- 2026-10-29 · G021 · NQ37 variante Z 7, Δβ2 −4,2°, fD2 0,886: H 0,34 × diseño escalado con corrida sana, como G018/G019; en
  NQ35–37 las variantes con fD2 < 0,9 dan H ≈ 0,3 (G010 NQ25 con fD2 0,854 daba 0,66): sospechar de la generación, REVISAR.
