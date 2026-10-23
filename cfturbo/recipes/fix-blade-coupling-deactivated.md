Elimina el warning "Coupling partially deactivated. Blade surface deformation can occur." al cambiar nBl.

## Síntoma
CFturbo batch devuelve rc=1 con aviso:
"Blade mean lines: N: [Impeller_1]: Coupling partially deactivated. Blade surface deformation can occur."
Aparece al cambiar el número de álabes (p.ej. 6→7) en un proyecto existente; las líneas medias
hub/shroud no pueden satisfacer simultáneamente las restricciones de acoplamiento originales.

## Fix
Agregar a `edits`: `"MeanSurface[Mean surface]/Coupled": false`

Esto desacopla las líneas medias de hub, media y shroud, permitiendo que CFturbo calcule los
ángulos de álabe de forma independiente por superficie de corriente. Resultado: rc=0, sin avisos.

## Nota
No afecta d2, b2 ni el punto de diseño. Puede variar ligeramente la distribución de ángulo β
entre hub y shroud respecto al diseño acoplado original — aceptable para la mayoría de los casos.
Verificado: primera-bomba, nBl 6→7, d2=212 mm, 2026-10-23.