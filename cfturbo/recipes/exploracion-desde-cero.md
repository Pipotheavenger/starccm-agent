# Bomba nueva para un punto de diseño (Q, H, n) sin plantilla de la GUI — exploración 2026-10-23

CFturbo 2026.1.1.128, solo batch. Corridas en `%TEMP%\cfturbo-explora\` (nada en `projects/`).
Prototipo: `explora/desde_cero.py` → `nueva_bomba(Q_m3h, H_m, n_rpm, destino_cft)`.

**Respuesta corta: sí, se puede.** No se puede crear el proyecto desde cero (no hay modo automático
del meridiano), pero sí **escalar por semejanza el ejemplo de CFturbo con nq más cercano** y dejar
que CFturbo recalcule ángulos de álabe y voluta al abrirlo. Sale rc=0, sin avisos, d2 exacto y el
STL cambia de tamaño en la proporción esperada. Probado con 10 bases (radial, semiaxial, axial),
k de 0.81 a 1.53 y nq hasta ±45 % del de la base.

## Procedimiento que funciona

1. `nq = n·√Q / H^0.75` (rpm, m³/s, m). Elegir la base con `|ln(nq/nq_base)|` mínimo.
2. `k = (n_base/n)·√(H/H_base)` (mantiene Psi; d2 nuevo = k·d2_base exacto).
3. Multiplicar por `k` **todas las longitudes absolutas** del `.cft` (lista abajo). No tocar ángulos,
   coeficientes (Psi, b2_d2, Eps, Eta…), posiciones relativas (`xRel`, `yRel`, `Rel`, `PointOnWire`)
   ni `SkeletonLines` (ángulos/coordenadas conformes).
4. Si nq ≠ nq_base (solo radial y semiaxial): multiplicar además las longitudes **axiales** (x del
   meridiano, `xVal`, `dxVal`, `Distance`, `b2`, `Width`) por
   `c = (b2/d2)_Gülich(nq) / (b2/d2)_Gülich(nq_base)`, con
   `(b2/d2)_Gülich = 0.017 + 0.262x − 0.08x² + 0.0093x³`, `x = nq/100` (reproduce los ejemplos:
   nq20 0.066, nq37 0.103, nq49 0.126). `b2_d2 *= c`. Recorte 0.6 ≤ c ≤ 1.5.
5. Velocidades guardadas en la base (`k_v = k·n/n_base`): `x` de `CuCmDefinition` (cu en m/s de los
   axiales). En modo carga de álabe (`dmXdSwirl`), `TMeanSurfSet/nRot` = n nuevo.
6. Punto de diseño (`QFlow`, `Head`, `nRot`) nuevo y `MainDimensions/AutoUpdate = False`.
7. Correr en batch. CFturbo recalcula solo: ángulos de álabe (`BladeProperties/AutoUpdate1/2=True`),
   voluta (`SpiralCasing/AutoUpdate=True`, regla `VeloBased`: cu 17.04 → 11.16 m/s y secciones
   nuevas) y lengua (`SpiralCasingCutwater/AutoUpdate`).

Nodos que son longitudes (m): `d2 b2 dS dH dH2 dS2 xVal yVal dxVal dyVal Distance Width Diameter
Fillet LinLength LinRadius HeightOffset DistTolerance H6 ExtensionLength Thickness xTipInlet
xTipOutlet`, `x`/`y` de todo `Position`/`Hub`/`Shr`/`Offset*` (meridiano: `MerFlowPath`, puntos de
interfaz, curvas Bezier y `LineSegment`, `TMer2ndaryFlowPath`, `TMerSolid`, `MerData` de estator y
voluta), `s1`/`s2` (espesor de álabe). En distribuciones `…/Points/Value/{x,y}` la `x` es relativa o
ángulo y solo la `y` es longitud (espesor `BezierNProf`, filetes `ValueDistrib`, progresión de altura
de voluta `BezierProgr`; en `CuCmDefinition` x = cu). Comprobado: `H6` (largo del difusor de voluta) y
`ExtensionLength` (extensión CFD) son metros: sin escalarlos la voluta medía 430 mm en vez de 374.

## Resultados

### H1 — escalado puro, mismo nq (base CP nq37: 227 m³/h, 70 m, 3600 rpm, d2 206.3)

Pedido 100 m³/h, 30 m, 2900 rpm (nq 37.7), k = 0.8127.

| corrida | rc | avisos | d2 mm (esp.) | b2 mm | dS mm | bbox impulsor mm | bbox voluta X mm |
|---|---|---|---|---|---|---|---|
| base sin cambios | 0 | 0 | 206.3 | 21.46 | 122.7 | 232.0 | 460.2 |
| escalado sin H6/ExtensionLength | 0 | 0 | 167.65 (167.65) | 17.44 | 99.7 | 188.54 (=0.8127·232) | 430.0 (mal) |
| escalado completo | 0 | 0 | 167.65 (167.65) | 17.44 | 99.7 | 188.54 | 374.5 (=0.814·460) |

### H2 — solo automatismos, sin escalar (mismo pedido sobre nq37)

Banderas buscadas en el XML y en el ejecutable: `MainDimensions/AutoUpdate`, `ParaEffAutoUpdate`,
`FreeStyle`, `BladeProperties/AutoUpdate1/2`, `SpiralCasing/AutoUpdate`, `Cutwater/AutoUpdate`,
`Coupled`, `FlowDomainDesignMode` (solo `dmHubShr|dmMid`), `ProgMode` (solo `pmUndefined|pmManual|pmLoaded`),
`MeanSurface/DesignMode` (`dmTM|dmXBeta|dmXY|dmZRPhi|dmXdSwirl…`). **No existe modo automático del
meridiano ni de las líneas medias**: lo que en la GUI es "inicializar" no está en el XML.

| variante | rc | resultado |
|---|---|---|
| AutoUpdate=True | 2 | "Secondary flow path intersects hub solid", sin export (d2 167.6 ok, meridiano viejo) |
| AutoUpdate=True + borrar `TMer2ndaryFlowPath` y `TMerSolid` | 1 | exporta, pero "Stator outlet does not match next inlet", "Volute inlet does not match previous outlet", curvatura alta |
| AutoUpdate=True + borrar `Meridian` entero | — | EAccessViolation al cargar, proyecto corrupto |

### H3 — escalar + AutoUpdate=True

Funciona si nq ≈ nq_base (nq37→37.7: rc 0, CFturbo pone dS 100.6 vs 99.7 escalado). Si nq cambia,
AutoUpdate recalcula dS con `Eps` y el meridiano no lo sigue: **dS que baja** pasa, **dS que sube** rompe.

| nq pedido (base nq37, H30 n2900) | dS auto mm | auto | fijo (AutoUpdate=False) |
|---|---|---|---|
| 30 | 82.1 | rc 0 | rc 0 |
| 33 | 89.3 | rc 0 | rc 0 |
| 41 | 108.6 | rc 2 "Shroud material is self-intersecting", "Secondary flow path intersects shroud/inlet" | rc 0 |
| 45 | 118.4 | rc 2 (igual) | rc 0 |
| 20 / 49 | — | rc 2 | rc 1 βB2 fuera de rango (nq20, sin corrección axial) |

Conclusión: **AutoUpdate=False** siempre; la geometría escalada manda.

### Corrección axial `c` para nq distinto del de la base (base CP nq37, H 30 m, n 2900 rpm)

| nq pedido | c | rc | avisos | b2/d2 resultante |
|---|---|---|---|---|
| 20 | 0.636 | 0 | 0 | 0.066 |
| 25 | 0.745 | 0 | 0 | 0.077 |
| 30 | 0.850 | 0 | 0 | 0.088 |
| 45 | 1.146 | 0 | 0 | 0.119 |
| 55 | 1.328 | 0 | 0 | 0.138 |

La voluta (VeloBased) se rehace sola con el Q nuevo (Y de la voluta 231 → 320 mm de nq20 a nq55).

Intento extra, remapeo radial del ojo (dS ∝ (Q/n)^⅓ por debajo de dS, transición hasta 0.95·d2):
nq30 rc 0, nq45 rc 1 (curvatura alta en TE), nq20 rc 2 ("Solid geometry could not be created").
No se adoptó: el ojo queda en la proporción de la base.

### Matriz de bases (H = 1.5·H_base, n = 0.8·n_base → k = 1.531; y nq ×1.15–1.45)

| base | tipo | nq base → pedido | rc | avisos | d2 (o d_punta) esp. = CFturbo |
|---|---|---|---|---|---|
| CP nq8 (Barske) | radial + voluta | 8.4 → 8.4 / 10.1 | 0 / 0 | 0 | 339.10 |
| CP nq20 (trimmable) | radial + voluta | 19.9 → 19.9 / 23.9 | 0 / 0 | 0 | 336.80 |
| CP nq31 (const TE angle) | radial + voluta | 31.5 → 31.5 / 37.8 | 0 / 0 | 0 | 476.12 |
| CP nq37 (end-suction) | radial + voluta | 37.4 → 20…55 | 0 | 0 | ver arriba |
| CP nq38 (wastewater) | radial + voluta | 38.3 → 38.3 / 46.0 | 0 / 0 | 0 | 244.95 (fuera de la lista: diseño para sólidos) |
| CP nq49 (blade loading) | radial + voluta | 49 → 49 | 0 | 0 | 440.91 |
| MP nq94 (bowl diffuser) | semiaxial + difusor | 94.2 → 94.2 / 109.8 | 0 / 0 | 0 | 185.24 |
| MP nq125 (bowl diffuser) | semiaxial + difusor | 124.6 → 124.6 / 140.4 | 0 / 0 | 0 | 206.68 |
| AP nq120 (meanline) | axial + estatores | 119.7 → 119.7 / 143.7 | 0 / 0 | 0 | 734.85 (STL 734.84) |
| AP nq172 (hydrofoil) | axial | 172.1 → 172.1 | 0 | 0 | 612.37 (STL 612.37) |
| AP nq295 (meanline) | axial | 294.6 → 294.6 | 0 | 0 | 920.09 (STL 920.02) |

Errores de método que costaron una corrida (ya corregidos en el prototipo):
- Escalar la `x` de `SpiralCasing/BezierProgr` (es el ángulo 0…2π, no longitud) daba en nq49 "Very high
  tangential leading edge sweep angle" y "Overlapping of adjacent blades". Con solo la `y`: rc 0.
- Axiales sin escalar la cu de `CuCmDefinition`: "Swirl gradient violates Euler equation" y
  "Coupling partially deactivated". Con `x·k_v`: rc 0.

## Prototipo `explora/desde_cero.py`

- `preparar(Q, H, n, destino, base=None)` escribe el `.cft`; `nueva_bomba(...)` además corre CFturbo con
  `mcp_server.run_batch` (misma carpeta temporal, candado y bitácora) y devuelve `base, nq, k, c_axial,
  d2_mm` esperado vs `d2_mm_cfturbo`, `d2_mm_stl` (STL `Outflow` del rotor), `returncode`, avisos, errores,
  `out_cft`, `run_dir` y `aviso` si nq se aleja más de ×1.5 de la base.
- Bases: 5 CP + 2 MP + 3 AP de los ejemplos y cualquier `projects/*/*.cft` con impulsor.
- `python explora/desde_cero.py 100 30 2900 C:\ruta\nueva.cft` — exporta StarCCM (3 STEP + `.cfturbo-ccm`
  + `.java`) y OpenFOAM. Verificado 150 m³/h, 25 m, 1450 rpm → base nq31, c 0.88, rc 0, 3 STEP.
- `--selftest` (CFturbo real, **~95 s**: 47 s la primera corrida): escalado offline del XML; Q100 H30 n2900
  → rc 0, 0 avisos, d2 167.65 exacto, STL `Outflow`/d2 = 1.1246 como la base (232.0/206.3); y Q60 H50 n3500
  (nq 24, base nq20, c 1.14) → rc 0. Corre en `%TEMP%\cfturbo-explora\selftest`, no toca la bitácora.

## Límites

- La forma (ángulos, carga, relación de cubo, ojo dS/d2, número de álabes) es la del ejemplo base.
  Es un buen punto de partida, no un diseño optimizado: Psi y eta del ejemplo se heredan.
- Probado hasta nq ×0.53…×1.47 respecto a la base (nq37 → 20…55). Fuera de ×1.5 el prototipo avisa.
  Hueco real de bases: **nq 55–90** (entre CP nq49/nq52 y MP nq94) y nq < 8.
- Volutas `GeomBased` (nq49) no se rehacen con Q: solo se escalan por k; con c ≠ 1 quedan algo
  desajustadas en área. Las `VeloBased` (nq37, nq31, nq20…) sí se recalculan.
- La corrección axial `c` es un ajuste 1D (b2), no cambia el ojo ni los ángulos de entrada (estos los
  recalcula CFturbo con AutoUpdate1/2).
- MP/AP no llevan voluta; el ejemplo trae sus estatores/difusores escalados igual.
- Turbinas Francis/Kaplan: sin licencia. **PAT**: CFturbo no tiene modo turbina para bombas; se diseña
  la bomba en su BEP equivalente (p. ej. Q_b ≈ Q_t·η^0.8, H_b ≈ H_t·η^1.2, Sharma) y la evaluación como
  turbina la hace el CFD con el rotor girando al revés. No probado en CFD.
- `mcp_server._STL_RX` no reconoce nombres con `-Flowdomain(virtual)-` ni captions sin corchetes
  (p. ej. `_Co2_Impeller-Flowdomain(virtual)-Hub.stl`): esas piezas salen sin componente en `geometry`
  (visible en nq8, nq20, nq31, MP, AP). Arreglarlo en el MCP (no tocado aquí).

## Recomendación

1. Usar este flujo como `cft_new(Q_m3h, H_m, n_rpm, name)` en el MCP (envolver `desde_cero.nueva_bomba`) y
   en la UI como "Nueva bomba desde punto de diseño". Después, el flujo normal de `cft_run` (d2, b2, nBl,
   Psi…) sobre el `_out.cft` resultante.
2. GUI solo para cubrir huecos de nq: crear **una bomba base por banda** que falte (nq 55–90 radial
   rápida/semiaxial con voluta; nq < 8 si hace falta; una PAT si se quiere forma de turbina) y guardarla
   en `projects/<nombre>/`; el prototipo ya la toma como candidata y la escala por código.
3. No usar `MainDimensions/AutoUpdate=True` para cambiar el punto de diseño: rompe el meridiano cuando
   dS crece.
