# Cómo usar el agente CFturbo (PC Windows)

Preparado el 2026-10-23. Entorno en `cfturbo\.venv`, MCP registrado en `cfturbo\.mcp.json`,
proyecto base `projects\primera-bomba\primera-bomba.cft` (nq ≈ 37, 227 m³/h, 70 m, 3600 rpm).

## Cada sesión

1. Abre Claude Code en esta carpeta (`starccm-agent` o `cfturbo`). Las tools `cft_*` aparecen solas.
2. Arranca la interfaz: preview `cfturbo-ui`, o en PowerShell desde `starccm-agent`:
   `cfturbo\.venv\Scripts\python -m uvicorn --app-dir cfturbo ui.server:app --port 8765`
   y abre http://localhost:8765.
3. En la interfaz tienes tres formas de trabajar, y las tres actualizan el visor solas:
   - **Ejecutar**: escribe valores en la columna "Nuevo" (d2, b2, nBl, Q, H, n…) y pulsa
     "▶ Ejecutar en CFturbo". Marca "Partir de la corrida seleccionada" para iterar sobre un resultado.
   - **Pedir a Claude**: mismos valores, pero Claude revisa con criterio de turbomáquinas y corre.
   - **Chat**: lenguaje natural ("resumen de la última corrida", "3 variantes de álabes", "compara v1
     y v2"). Lo ejecuta Claude Code por detrás con las tools cft_*. Una sola vez, en una terminal:
     `claude auth login` (si el chat responde "401 OAuth access token is invalid", repítelo).

## Prompt de ejemplo (lo que genera la interfaz)

---

Lee CLAUDE.md. Proyecto base: primera-bomba.
Punto de diseño: Q=227 m³/h, H=70 m, n=3600 rpm, agua 20 °C (nq ≈ 37.4).
Propón las dimensiones con criterio de turbomáquinas.
Corre cft_run con name="v1" y exports [StarCCM, OpenFOAM].
Entrega: tabla pedido vs realizado, correcciones de CFturbo, avisos y rutas de los STEP. Si algo falla, lee cft_log y corrige.

---

## Prompt de variantes

---

Lee CLAUDE.md. Proyecto base: primera-bomba. Quiero 3 variantes para 250 m³/h, 60 m, 3600 rpm,
agua: mueve d2, b2 y número de álabes con criterio de turbomáquinas, corre cada una con
cft_run (nombres v_a, v_b, v_c), y dame una tabla comparativa con pedido, realizado, avisos y
STEP. Recomienda una y explica en 3 líneas.

---

## Cuando haya nuevo proyecto base

Crea la bomba en la GUI de CFturbo (punto de diseño nuevo, 3 componentes), guárdala como
`projects\<nombre>\<nombre>.cft` y aparecerá en la interfaz y en `cft_projects`.
