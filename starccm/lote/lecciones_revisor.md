# Lecciones del revisor

Para interpretar resultados, no para el ejecutor. Las nuevas las añade el orquestador desde el campo `leccion` de
`veredicto.json` (una línea, sin repetir). Consolidadas a mano el 2026-10-30 desde 40 lecciones de 47 corridas.

## Consolidado (oct. 2026, receta v1)

- Convergencia de H: en nq ≤ 25 (bases y variantes) H sigue subiendo a la it. 1000 con M ya plano (G002, G004, G007,
  G008, G011–G013) y se asienta entre 1300 y 1500; desde nq 30 las bases estabilizan antes de 800. La deriva (pendiente)
  es la señal, no el semirrango: un 4 % de semirrango puede esconder un 8 % de deriva.
- η baja en nq 10–15 (0,41–0,49) con η_Euler ≈ 0,9: casi la mitad del par va a fricción de disco en las cámaras
  laterales. Es válida pero no comparable con nq altas; mira `M_discos` si está.
- η_Euler > 1 en una base indica que pt_out sigue en transitorio; en variantes con fD2 < 1 no sirve como señal porque U2
  y Vu2 se miden en la interfaz, no en el álabe recortado.
- H de variantes: la referencia es su propia curva de CFturbo (`H_referencia_m`), no el diseño de la base. Variantes con
  fD2 < 0,9 y/o Δβ2 ≲ −3° dan H 0,2–0,5 × diseño con corridas sanas (G018, G019, G021, G029, G034, G043, G044): es física
  de la variante. OK con alerta, no REVISAR, salvo que haya un indicio de montaje (par al revés, caudal ≠ BC, malla rota).
- D2: en flujo mixto (nq ≥ 60) el radio máximo del borde de salida sale +4–8 % sobre D2 (borde inclinado). El recorte de
  una variante se valida como r_TE(variante)/r_TE(base) ≈ fD2 (G036: 115,2/121,0 = 0,952; G042, G043 igual). En nq 65 y
  80 el u2 de `_estado.json` de la variante es el de la base: CFturbo no aplicó el recorte al informe.
- Malla: las extensiones con el mismo base que la bomba sumaban 7 % (nq ≤ 25) a 33 % (nq ≥ 70) de celdas; desde la
  receta v2 se mallan con base doble.
- Z 7 con base 3,0 mm en nq 65 deja ~1,93 M celdas (rotor 848 k): cerca del límite.
- H frente a la curva de CFturbo: ~0,95 de media en las variantes nq 15–50, pero ~0,69 en nq 65/80 (G034 0,43, G035 0,52,
  G044 0,52) aun escalando por fD2²; en flujo mixto el f² no basta. Un aviso de «H fuera de lo que predice CFturbo» en
  esas variantes no es un error de montaje.

## Nuevas
- 2026-10-31 · G001_nq10_B · G001 nq 10: H aún sube y M aún baja a la it. 1500 (H +11 % entre 1100 y 1500, M −3 %); en nq 10 la convergencia puede pasar de 1500 it., no solo la de H: también M deriva lento.
- 2026-10-31 · G002_nq15_B · 2026-10-31 · G002 · nq 15 base: entre 1000 y 1500 it. M sigue bajando (78→70 N·m) y η pasa de 0,48 a 0,60; en nq ≤ 15 la η a 1000 it. subestima mucho y 500 it. más no bastan para asentar M.
- 2026-10-31 · G003_nq15_V · 2026-10-31 · G003 · nq 15 variante: igual que la base G002, M sigue bajando y η subiendo a 1500 it. (0,51→0,61 entre 1000 y 1500); en nq ≤ 15 bases y variantes necesitan > 1500 it. Variante/base a igual iteración (H 0,84) sí es comparable.
- 2026-10-31 · G006_nq15_V · G006 nq 15 variante fD2≈1: H ≈ 1,28 × su curva CFturbo, igual que la base G002 (H/diseño 1,27); en nq 15 la curva de CFturbo subestima H un ~28 % a 1500 it., no es error de montaje.
- 2026-10-31 · G004_nq15_V · G004 · nq 15 variante, 1500→2000 it.: H se asienta, pero M baja y η sube ~1,3 %/100 it., y los residuales suben ×3 (continuidad 1,4e-2→5e-2) sin divergir. En nq 15 los residuales al alza con H plana no indican divergencia.
- 2026-10-31 · G001_nq10_B · G001 nq 10 base: H y M se asientan entre 1500 y 2000 it. (deriva H 2,2 → 0,3 %/100 it.); en nq 10 hacen falta ~2000 it., y η final (0,475) apenas cambia desde 1500.
- 2026-10-31 · G002_nq15_B · 2026-10-31 · G002 · nq 15 base: M y η se asientan entre 1500 y 2000 it. (M 70,5→68,3 N·m, η 0,60→0,63, deriva de H 0,36 %/100 it.); en nq 15, como en nq 10, hacen falta ~2000 it.
- 2026-10-31 · G003_nq15_V · 2026-10-31 · G003 · nq 15 variante, 1500→2000 it.: la media de H se asienta (deriva 2,3→1,6 %/100 it.), pero la oscilación de H crece (4,9→7,1 %). En nq 15, una amplitud que crece con la media plana no es divergencia.
