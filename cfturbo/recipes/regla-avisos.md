# Regla: los avisos y errores de geometría se corrigen siempre, sin que el usuario lo pida

Pedido por Sebastián el 2026-10-23. Tras cada `cft_run`, leer `warnings`/`errors`:
- solapamientos, intersecciones, extensiones, "flow path intersects", "component incomplete" ->
  buscar receta (`cft_recipe_search`), corregir y volver a correr (máx. 3 intentos), luego reportar.
- avisos informativos (automatic blade angles, automated contour update) -> solo mencionarlos.
- "Coupling partially deactivated" (líneas medias) -> ver receta `fix-meanline-coupling` si existe.
Guardar receta nueva cada vez que un aviso se resuelva de una forma no documentada.
