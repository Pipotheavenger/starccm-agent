# Regla: los avisos y errores de geometría de las corridas que lanza Claude se corrigen sin que el usuario lo pida

Pedido por Sebastián el 2026-10-23. Aplica **solo a las corridas que Claude lanza** en esa petición
(diseñar o variar). Si piden resumen, comparación o información, solo leer, mencionar los avisos y
ofrecer corregirlos, sin `cft_run` ni `cft_save`. Tras cada `cft_run` propio, leer `warnings`/`errors`:
- solapamientos, intersecciones, extensiones, "flow path intersects", "component incomplete" ->
  buscar receta (`cft_recipe_search`), corregir y volver a correr (máx. 3 intentos), luego reportar.
- avisos informativos (automatic blade angles, automated contour update) -> solo mencionarlos.
- "Coupling partially deactivated" (líneas medias) -> receta `fix-blade-coupling-deactivated`
  (`MeanSurface[Mean surface]/Coupled=False`).
- "Extension is overlapping neighboring component" -> receta `fix-extension-overlap` (`ext_outlet=False`).
Guardar receta nueva cada vez que un aviso se resuelva de una forma no documentada.
