# PAT — DOE en modo turbina (bomba como turbina)

Proyecto separado del DOE en modo bomba (`../doe/`): mismas 47 geometrías y misma malla, pero otro sentido de flujo, giro
al revés, una variable más (rpm) y reportes con convención de turbina. **Nada de este proyecto escribe en las carpetas del
modo bomba.** Estado al 2026-11-16: **terminado**. Barrido de 32 casos en las 47 bombas, embalamiento a 3000 rpm medido en
las 47 (`emb.py`, `emb2.py`), repositorio unificado y base de datos `PAT_PAT1_modo_turbina.xlsx` (`consolidar_pat.py`).
Detalle y lecciones en `CONOCIMIENTO.md`.

## Dónde vive cada cosa

| qué | modo bomba (no tocar) | modo PAT |
|---|---|---|
| código y plan | `starccm/doe/` (`plan.json`) | `starccm/pat/` (`plan.json` propio) |
| workers | `C:\trabajo\DOE-2026-11_PAT1\<id>\` | `C:\trabajo\PAT-2026-11_PAT1\<id>\` |
| entregables por bomba | `<carpeta de la bomba>\DOE\` | `<carpeta de la bomba>\PAT\` |
| repositorio unificado | `Geometrias_Prueba\DOE_PAT1_resultados\` | `Geometrias_Prueba\PAT_PAT1_resultados\` |
| tablero | puerto 8770 | puerto 8771 (embalamiento: 8772 `emb.py`, 8773 `emb2.py`) |
| base de datos | `DOE_PAT1_modo_bomba.xlsx` (`doe/base_datos.py`) | `PAT_PAT1_modo_turbina.xlsx` (`consolidar_pat.py`) |

## Física (dm/pat_fisica.java, sobre una copia del base.sim de bomba)

| | bomba | PAT |
|---|---|---|
| entrada | `ext_entrada/inlet` presión total 0 Pa | `ext_salida/outlet` (brida de la voluta) caudal **+${Flujo}** kg/s |
| salida | `ext_salida/outlet` caudal −${Flujo} | `ext_entrada/inlet` (succión) **presión estática 0 Pa** |
| giro MRF | −3000 rpm fijo | **signo contrario** · `${rpm}` (parámetro global nuevo) |
| modelo | k-ω SST, All y+, MRF, estacionario | igual |

## Reportes (mismos nombres, otra convención)

| reporte | bomba | PAT |
|---|---|---|
| pt_in / Q_in | succión | brida de la voluta (entrada PAT) |
| pt_out / Q_out | brida de la voluta | succión (salida PAT) |
| H | (pt_out − pt_in)/(ρg) | (pt_in − pt_out)/(ρg): altura que cede el fluido |
| P_hid | \|Q\| g H (entregada al fluido) | \|Q_in\| g H (disponible) |
| P_eje | \|M\|·\|ω\| (siempre > 0) | **M·ω con signo**: > 0 la PAT entrega potencia |
| eta | P_hid / P_eje | P_eje / P_hid |
| M_turb (nuevo) | — | P_eje/\|ω\|: par en el sentido de giro (> 0 turbina, < 0 freno) |
| omega (nuevo) | — | ω con signo (rad/s) |
| U, Vu, Vr, UVu 1/2 | 1 = entrada rotor (radio menor) | 1 = entrada rotor PAT (radio mayor) |
| H_Euler | (U2Vu2 − U1Vu1)/g | (U1Vu1 − U2Vu2)/g |
| eta_Euler | H/H_Euler | H_Euler/H |
| Vu2_inf, factor_deslizamiento | sí | se borran (son de bomba) |

## Embalamiento (runaway)

Con MRF no hay rpm libre: se barre (Q, rpm) y el embalamiento sale de los datos donde **M_turb cambia de signo**.
- Por cada rpm: Q_runaway = caudal con M_turb = 0 (interpolación lineal entre los dos puntos que cambian de signo).
- Por cada Q: n_runaway = rpm con M_turb = 0.
- Además, magnitudes unitarias para comparar geometrías: n11 = n·D2/√H, Q11 = Q/(D2²·√H), P11 = P/(D2²·H^1,5),
  y curva de embalamiento n11_R(Q11).
- Régimen de cada punto: `turbina` (P_eje > 0), `freno` (P_eje ≤ 0 con H > 0) o `bomba inversa` (H < 0).

## Flujo de trabajo (como el modo bomba)

1. `preparar`: copia base.sim al worker (`C:\trabajo\PAT-…\<id>\base_bomba.sim`), corre `pat_fisica.java` y guarda `base.sim` PAT.
2. Estudio de Design Manager con **dos parámetros DISCRETE: Flujo × rpm** (barrido completo), mismo `antes_correr` y
   `despues.java` (versión 2: JSON completo por punto, carpeta `puntos\Q…_n…\`).
3. Al terminar: escenas, Excel por bomba, informe, y **solo queda el .sim del BEP de turbina a la rpm nominal**; el resto
   en JSON, CSV, imágenes y Excel.
4. Repositorio unificado y base de datos `PAT_PAT1_modo_turbina.xlsx` (Geometrias, Simulaciones, Embalamiento…).

## Barrido (decidido 2026-11-10)

rpm 500, 1000, 1500 y 3000 × 8 caudales entre 0,8 y 2,4 Q_BEP (Q_BEP = Qn de bomba a 3000 rpm): 32 puntos por bomba,
1504 en total, ~5 días en 4 workers. Con rpm fijas a caudal alto la PAT trabaja como turbina; el cambio de signo de
M_turb (embalamiento) se espera sobre todo a 1500–3000 rpm y caudal bajo. Por defecto: se guarda el .sim del BEP de
turbina a 3000 rpm y las nq 10–25 van al final.
