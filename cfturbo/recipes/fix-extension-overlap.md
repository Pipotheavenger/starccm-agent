# Arregla "CFD setup: Extension is overlapping neighboring component" (impulsor + voluta), verificado 2026-10-23

Causa: el impulsor tiene activa la extensión CFD de salida (`CFDSetup_RotSym_Extension_Outlet_Active=True`,
1 mm tangencial) y la voluta está pegada a la salida, así que la extensión invade la voluta.

Solución: `cft_run(project, {"ext_outlet": False}, ...)`. Pone la bandera en False **y borra el objeto**
`CFDSetup_RotSym_Extension_Outlet`; si solo se cambia la bandera, CFturbo la vuelve a True (probado).
Acortar la extensión (0.1 mm) tampoco quita el aviso. El ejemplo original "CP nq37" viene sin extensión.

Cuándo NO aplicarla: si el impulsor no tiene componente aguas abajo (export solo del rotor), la
extensión es la que da el dominio de salida para CFD; ahí se deja activa.
