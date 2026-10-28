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
