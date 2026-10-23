# Cómo usar el agente CFturbo (PC Windows)

Entorno en `cfturbo\.venv`, MCP en `cfturbo\.mcp.json`, proyecto base
`projects\primera-bomba\primera-bomba.cft` (nq ≈ 37, 227 m³/h, 70 m, 3600 rpm, agua).

## Arrancar

1. Una sola vez, en una terminal: `claude auth login` (el chat de la página usa tu suscripción).
2. Interfaz: preview `cfturbo-ui` en Claude Code, o en PowerShell desde `starccm-agent`:
   `cfturbo\.venv\Scripts\python -m uvicorn --app-dir cfturbo ui.server:app --port 8765`
   y abre http://localhost:8765.
3. Izquierda: proyecto base (con **＋ Nueva**) y galería. Centro: visor y panel inferior (Chat ·
   Hitos y avisos · Curvas · Archivos · Comparar). Derecha: «Nueva corrida». Pasa el ratón por
   cualquier control para ver qué hace; `?` muestra los atajos.

## Trabajar

| Forma | Cómo | Cuándo |
|---|---|---|
| **▶ Ejecutar** | valores en la columna «Nuevo», «Partir de: Proyecto base / Corrida», botón o Ctrl+Enter | sabes qué quieres; ~30 s, sin Claude |
| **Pedir a Claude** | mismos valores, otro botón | que revise con criterio y corrija avisos |
| **Chat** | «resumen de la última», «3 variantes de álabes», «compara v1 y v2» | explorar, explicar, varias corridas |

- Opciones: **AutoUpdate** (recalcula d2/b2/dS desde Q/H/n; puede romper el meridiano), **Sin
  extensión CFD** (marcada sola si el origen la tiene; desmárcala si exportas solo el rotor),
  Exportar **STEP · STL · Reporte**.
- Una corrida de CFturbo a la vez en todo el PC (UI, chat o Claude Code). Si está ocupado, Ejecutar
  se deshabilita y dice qué corre.
- Resumen o comparación: Claude solo lee. Diseñar: corrige solo los avisos de geometría (≤ 3 intentos).

## Bomba nueva (sin la GUI de CFturbo)

**＋ Nueva** → Q (m³/h), H (m), n (rpm) y nombre. Sugiere la base más cercana en nq (ejemplos de
CFturbo: radiales nq 8-49 con voluta, semiaxiales nq 94-125, axiales nq 120-295, más tus `projects/`)
y la escala por semejanza. «Crear y correr» crea `projects\<nombre>\` y lanza `<nombre>_1`.
Si sale ⚠ (nq a más de ×1,5 de la base) el resultado es dudoso: crea una base en la GUI para esa
banda. Ángulos y nº de álabes son los del ejemplo: es un punto de partida. En el chat: «bomba nueva
de 150 m³/h, 40 m, 2900 rpm».

## Ángulos de álabe y espesor

Filas **β1 cubo/corona**, **β2 cubo/corona** y **s** en la tabla. En cursiva = automático (CFturbo lo
recalcula). Escribir un β lo **fija** (deja de ser automático); si escribes solo cubo, la corona
queda como en el origen. Fijar β2 suele dejar el aviso «Coupling partially deactivated»: pídele a
Claude que lo corrija. Volver a automático: por chat («β automáticos»).

## Curvas y reporte

- **Curvas**: H-Q (con punto de diseño), η-Q y P-Q de cada corrida, predicción 1D de CFturbo (no CFD).
  El puntero lee los valores; con B elegida se superpone en discontinua.
- **Reporte**: marca la casilla antes de ejecutar. Hitos muestra «Diseño» (βB1/βB2, Δφ, garganta,
  w2/w1, η, NPSHR, cu2/cm2/u2) con enlace «Reporte ↗» al HTML completo; Comparar añade esas filas.

## Guardar, borrar, comparar

- **★ Guardar versión** → nombre → Enter. Queda en `versions\<nombre>\` con ★; la temporal dice «★ como …».
  Las temporales se podan solas (quedan las 8 últimas).
- **Borrar**: 🗑 en la tarjeta o `Supr` → «¿Borrar? Sí». Sirve para temporales y versiones; no se puede
  deshacer ni borrar la que está corriendo.
- **Comparar**: clic = A; Ctrl+clic o ⇄ = B. Δ y Δ % por parámetro, avisos solo en A/B/ambas, H-Q de las
  dos, «Superponer B» en alambre, Intercambiar, Esc quita B, «Pedir comparación a Claude».

## Atajos

| Tecla | Hace |
|---|---|
| Ctrl+Enter | ejecutar (fuera del chat) |
| F · 1 · 2 · 3 | encuadrar · iso · axial · lateral |
| ` · ? | plegar el panel inferior · ver atajos |
| Esc | cerrar atajos / nombre de versión, quitar B |
| Galería: flechas, Inicio/Fin, Enter, Ctrl+Enter, Supr | moverse, ver (A), comparar (B), borrar |
| Pestañas ←/→ · visor: flechas, + / - | cambiar pestaña · orbitar, zoom |
| Chat: Enter · Shift+Enter · ↑ | enviar · salto de línea · recuperar el último |

## Si algo falla

- Chat «401 OAuth access token is invalid» o «not logged in»: `claude auth login` en una terminal
  (la tarjeta tiene «Copiar comando») y reenvía. «Ya hay una conversación en curso»: espera o
  **Detener**. «Nueva conversación» pide confirmar con un segundo clic.
- Banda «Sin conexión»: el servidor está caído; reintenta solo (4, 8, 16, 30 s) o con Reintentar.

## Dónde quedan los archivos

| Qué | Dónde |
|---|---|
| Corridas temporales | `%TEMP%\cfturbo-agent\<nombre>_<fecha>\` (botón «Abrir carpeta») |
| Versiones guardadas | `cfturbo\versions\<nombre>\` (STEP, `.cfturbo-ccm`, `.java`, STL, `_out.cft`, reporte) |
| Proyectos base | `cfturbo\projects\<nombre>\<nombre>.cft` (los existentes nunca se modifican) |
| Bitácora y recetas | `cfturbo\recipes\` |

A la MV de STAR-CCM+ van los `.stp`, el `.cfturbo-ccm` y el `.java` de la versión.
