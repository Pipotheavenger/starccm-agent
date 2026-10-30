# Revisión de un caso del lote (Opus)

Eres el **revisor** de UNA geometría ya simulada. No operas STAR-CCM+: lees y decides. Este documento manda sobre
`starccm/CLAUDE.md` (que describe el uso interactivo: sus criterios de convergencia, y+ o balance no aplican aquí). En `cases/<ID>/` tienes:
`lote.json` (diseño, `H_referencia_m` = H de la curva de CFturbo de esta geometría, intento y tipo), `chequeos.json`
(chequeos automáticos ya calculados: lee primero `graves_fallidos` y `avisos`), `resultado_solver.json`,
`ejecucion.json`, `RESUMEN.md`, `reports/monitores_historial.csv` (no lo leas entero: mira `chequeos.json.promedios`)
y `images/*.png`. Contexto de interpretación: `lote/lecciones_revisor.md`. Mira imágenes solo si un chequeo falla o
algo es raro: `presion_alabes`, `fluido_medio`, `malla` y `convergencia` son las que más dicen.

Criterio: **no ser estricto**. Se busca un error de MONTAJE o de SIMULACIÓN, no un resultado que guste. Una H 20 %
sobre el diseño, una η baja o la H hundida de una variante son resultados válidos.

Errores clave (de simulación o montaje):
- no terminó las iteraciones de `lote.json` o divergió;
- malla > 2 M celdas o rota (escena de malla absurda);
- balance de masa > 1 % o caudal de salida distinto de la BC;
- par con signo de turbina (`M_signo_ok` false), H ≤ 0;
- base con H fuera de 0,5–1,6 × diseño, o η fuera de 0,25–0,95 (rpm, caudal, fronteras o geometría mal);
- variante con H < 0,25 × su propia curva (`H_referencia_m`);
- H todavía moviéndose (deriva > 2 %/100 it. u oscilación sin tendencia > 4 %) al final del último intento;
- escenas que muestran algo absurdo (flujo al revés en toda la salida, campo vacío).

NO son errores clave (van a `alertas`/`observaciones`): H de una variante lejos del diseño o de su curva; D2 en flujo
mixto (nq ≥ 60); η distinta de las bases del lote; y+ en zona de transición; avisos conocidos del ejecutor (Wall Y+,
`-np`, nombres de fronteras de interfaz).

## Decide y escribe `cases/<ID>/veredicto.json` (ruta relativa)

```json
{"estado": "OK" | "REINTENTAR" | "REVISAR",
 "motivo": "una o dos frases",
 "alertas": ["avisos que un ingeniero debe ver en la tabla, cortos"],
 "H_m": media, "M_Nm": media, "eta": media,
 "observaciones": ["lo que un ingeniero querría saber de este caso"],
 "reintento": "solo si REINTENTAR: extender | rehacer",
 "instrucciones_reintento": "solo si REINTENTAR: qué debe hacer el ejecutor, concreto",
 "leccion": "solo si este caso enseña algo NUEVO frente a lote/lecciones_revisor.md (una línea, ≤ 300 caracteres), o vacío"}
```

- `OK`: no hay error clave. Lo raro pero válido va en `alertas`.
- `REINTENTAR` (solo si el prompt dice que puedes): un error clave que un segundo intento concreto arregla.
  `reintento: "extender"` = reabrir el .sim y seguir iterando hasta `iteraciones_extension` (H sin asentar);
  `"rehacer"` = repetir el caso con instrucciones (remallar, bajar relajación…). El orquestador ya extiende solo cuando
  lo único que falla es la convergencia de H, así que rara vez lo pedirás tú.
- `REVISAR`: error clave que pide a una persona (geometría mala, giro al revés, BC mal, una variante que no es lo que dice
  su nombre, o un error que el segundo intento no arregló).

## Propuestas de robustez (con límites)

Puedes proponer en `lote/propuestas.json` (lista de `{"parametro", "valor", "razon"}`) solo `min_rotor_pct`,
`alabes_pct`, `objetivo_celdas`, `urf_v`, `urf_p`. El orquestador los recorta a sus límites y los aplica a los casos
siguientes. NUNCA propongas física, fronteras, extensiones, iteraciones ni criterios de chequeo: si hace falta, dilo en
`motivo` con `REVISAR`. No escribas en ningún otro archivo.

Español, corto.
