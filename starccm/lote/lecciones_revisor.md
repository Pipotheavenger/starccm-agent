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

## Nuevas
