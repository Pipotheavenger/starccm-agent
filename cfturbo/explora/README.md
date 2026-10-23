# explora · bomba nueva por semejanza

`desde_cero.py`: prototipo del Explorador (2026-10-23) que crea una bomba para un punto de diseño
(Q, H, n) sin plantilla de la GUI. Elige el ejemplo de CFturbo (o `projects/*/*.cft` con impulsor) con
nq más cercano, escala todas las longitudes por `k = (n0/n)·√(H/H0)`, corrige la dirección axial con
b2/d2 de Gülich si nq cambia, pone el punto de diseño nuevo con `MainDimensions/AutoUpdate=False` y
deja que CFturbo recalcule ángulos de álabe y voluta. Procedimiento y resultados:
`../recipes/exploracion-desde-cero.md`.

El MCP lo carga con importlib (`mcp_server._desde_cero`, usa `preparar` y `candidatos`): es lo que hay
detrás de `cft_new` y de «＋ Nueva». No se importa como paquete.

## Límites

- Bases: CP nq8, 20, 31, 37, 49 (radial + voluta), MP nq94, 125 (semiaxial + difusor), AP nq120, 172,
  295 (axial), en `C:\Program Files\CFturbo 2026.1.1\Examples\…` (ruta fija). Huecos: nq 55-90 y < 8.
- Probado hasta nq ×0,53…×1,47 de la base; más de ×1,5 → `aviso`.
- Ángulos, carga, cubo, ojo dS/d2 y nº de álabes son los del ejemplo: punto de partida, no diseño
  optimizado. Volutas `GeomBased` (nq49) solo se escalan; las `VeloBased` se rehacen con Q.
- Turbinas Francis/Kaplan sin licencia; PAT solo como bomba en su BEP equivalente (no probado en CFD).

## Uso

```
.venv\Scripts\python explora\desde_cero.py 100 30 2900 C:\ruta\nueva.cft   # escribe y corre CFturbo
.venv\Scripts\python explora\desde_cero.py --selftest
```

El selftest usa **CFturbo real** (licencia; respeta el candado `running.lock`, no correr con otra
corrida en marcha): escalado offline del XML, Q100 H30 n2900 (d2 167,65 mm exacto) y Q60 H50 n3500
(nq ≈ 24, base nq20). Corre en `%TEMP%\cfturbo-explora\selftest` y no escribe en la bitácora. Tarda
~95 s (la primera corrida ~47 s por el arranque de CFturbo). No forma parte de
`python mcp_server.py --selftest`, que prueba `cft_new` con un CFturbo falso.
