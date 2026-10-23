# Cómo usar el agente CFturbo (PC Windows)

Entorno en `cfturbo\.venv`, MCP en `cfturbo\.mcp.json`, proyecto base
`projects\primera-bomba\primera-bomba.cft` (nq ≈ 37, 227 m³/h, 70 m, 3600 rpm, agua).

## Arrancar

1. Una sola vez, en una terminal: `claude auth login` (el chat de la página usa tu suscripción).
2. Interfaz: preview `cfturbo-ui` en Claude Code, o en PowerShell desde `starccm-agent`:
   `cfturbo\.venv\Scripts\python -m uvicorn --app-dir cfturbo ui.server:app --port 8765`
   y abre http://localhost:8765.
3. Al abrir, el visor carga la última corrida con geometría. Izquierda: proyecto base y galería de
   corridas. Centro: visor y panel inferior (Chat · Hitos y avisos · Archivos · Comparar).
   Derecha: «Nueva corrida».

## Tres formas de trabajar (las tres actualizan galería y visor solas)

| Forma | Cómo | Cuándo |
|---|---|---|
| **Ejecutar** | escribe valores en la columna «Nuevo» (Q, H, n, d2, b2, dS, dH, ψ, z, dV), elige «Partir de: Proyecto base / Corrida» y pulsa **▶ Ejecutar en CFturbo** (o Ctrl+Enter) | sabes qué quieres; ~30 s, sin Claude |
| **Pedir a Claude** | mismos valores, botón **Pedir a Claude** | quieres que revise con criterio de turbomáquinas y corrija avisos |
| **Chat** | lenguaje natural: «resumen de la última corrida», «3 variantes de álabes», «compara v1 y v2» | exploración, explicaciones, varias corridas |

- «Opciones»: AutoUpdate (recalcula d2/b2/dS desde Q/H/n; puede romper el meridiano) y «Quitar
  extensión CFD de salida» (marcada por defecto; desmárcala si exportas solo el rotor).
- Solo una corrida de CFturbo a la vez en todo el PC (UI, chat o Claude Code). Si está ocupado,
  Ejecutar se deshabilita y dice qué corre.
- Si pides un resumen o comparación, Claude solo lee. Si le pides diseñar, corrige solo los avisos
  de geometría (hasta 3 intentos).

## Guardar versiones

Las corridas son temporales (quedan las 8 últimas). Para conservar una: selecciónala y pulsa
**★ Guardar versión**, escribe el nombre y Enter. Queda en `versions\<nombre>\` con su miniatura;
en la galería sale con ★ y la temporal se atenúa («★ como …»). En el chat: «guarda esta como v1».

## Comparar

Clic en una tarjeta = corrida activa (A). **Ctrl+clic** o el botón **⇄** de otra tarjeta = B. La
pestaña Comparar muestra cada parámetro con Δ y Δ %, y los avisos solo en A / solo en B / en ambas.
Intercambiar pone B en el visor; Esc o «Quitar B» la quita; «Pedir comparación a Claude» la explica.

## Atajos de teclado

| Tecla | Hace |
|---|---|
| Ctrl+Enter | ejecutar (fuera del chat) |
| F · 1 · 2 · 3 | encuadrar · iso · axial · lateral |
| ` | plegar/desplegar el panel inferior |
| Esc | cancelar nombre de versión / quitar B |
| Flechas, Enter, Ctrl+Enter en la galería | moverse, ver (A), comparar (B) |
| Enter · Shift+Enter · ↑ en el chat | enviar · salto de línea · recuperar el último |

## Si el chat dice 401

«401 OAuth access token is invalid» o «not logged in»: la sesión de la CLI caducó. En una terminal
ejecuta `claude auth login` (la tarjeta del chat tiene «Copiar comando») y reenvía el mensaje.
«Ya hay una conversación en curso»: espera o pulsa **Detener**. «Nueva conversación» (doble clic)
olvida el contexto.

## Dónde quedan los archivos

| Qué | Dónde |
|---|---|
| Corridas temporales | `%TEMP%\cfturbo-agent\<nombre>_<fecha>\` (botón «Abrir carpeta») |
| Versiones guardadas | `cfturbo\versions\<nombre>\` (STEP, `.cfturbo-ccm`, `.java`, STL, `_out.cft`) |
| Proyectos base | `cfturbo\projects\<nombre>\<nombre>.cft` (nunca se modifican) |
| Bitácora y recetas | `cfturbo\recipes\` |

Lo que va a la MV de STAR-CCM+: los `.stp`, el `.cfturbo-ccm` y el `.java` de la versión.

## Nuevo proyecto base

Crea la bomba en la GUI de CFturbo (punto de diseño nuevo, 3 componentes), guárdala como
`projects\<nombre>\<nombre>.cft` y aparecerá en el selector y en `cft_projects`.
