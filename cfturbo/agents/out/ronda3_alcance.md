# Alcance de la ronda 3 (lo pide Sebastián + hallazgos del explorador)

Además de los defectos que salgan en eval_2.md:

1. **Ángulos de álabe visibles y editables.** Fuente en el `.cft`: `CFturboDesign_RadialImpeller/BladeProperties/
   BladePropsArray[BladeValues]/BladePropsML[Main blade]/Beta1` y `Beta2` (arrays Count=5, solo se guardan los
   índices 0=cubo y 4=corona, en radianes; interpolación lineal) y `s1`/`s2` (espesor en m). `BladeProperties/
   AutoUpdate1` y `AutoUpdate2` = True significa "ángulos automáticos": para fijar un ángulo hay que ponerlos en False.
   - `mcp_server.project_info().dims`: añadir `beta1_hub_deg`, `beta1_shroud_deg`, `beta2_hub_deg`, `beta2_shroud_deg`,
     `s_mm` (espesor), y `wrap`/otros si aparecen en el reporte.
   - `edits` especiales: `beta1_deg` y `beta2_deg` (número → todos los spans; o lista [cubo, corona]) que convierten a
     radianes, escriben los Value y ponen AutoUpdate1/2=False; `beta_auto=True` vuelve al automático. Detectar en
     `corrected` si CFturbo los cambió.
   - UI: filas "β1 cubo/corona", "β2 cubo/corona", "espesor" en la tabla de parámetros (base / corrida / nuevo), en
     grados con una decimal, y en Comparar.
2. **Reporte de diseño.** El export `Report` del batch genera `<base>.html` (~730 KB, 1 tabla, texto plano con todos
   los valores calculados) y `PerformanceData` genera `<base>.cft-pp`. Añadir casilla "Reporte" en exportar
   (desactivada por defecto), enlace en Archivos que abra el HTML en pestaña nueva, y parsear del HTML los valores
   clave (ángulos, ángulo de envolvente, garganta, rendimiento estimado) a `run.json["report"]` para mostrarlos en
   Hitos/Comparar.
3. **Borrar corridas desde la galería.** Botón 🗑 en cada tarjeta (temporal o versión) con confirmación en la propia
   tarjeta (dos clics o "¿Borrar? Sí / No"), `DELETE /api/runs/{id}` que borra la carpeta (versión incluida) y
   anota en bitácora si era versión; tool MCP `cft_delete(run_id)`; si era la corrida activa, seleccionar la siguiente;
   teclado: Supr con confirmación.
4. **Nueva bomba por semejanza.** Integrar `explora/desde_cero.py` (`nueva_bomba(Q_m3h, H_m, n_rpm, destino_cft)`)
   como tool `cft_new(Q_m3h, H_m, n_rpm, name, base=None)` que crea `projects/<name>/<name>.cft` (y aparece en
   `cft_projects`), y en la UI un diálogo "＋ Nueva bomba" junto al selector de proyecto (Q, H, n, nombre, base
   sugerida con su nq y aviso si el salto de nq > ×1.5). Leer `recipes/exploracion-desde-cero.md` para los límites.
5. **Bug `_STL_RX`** en mcp_server: no reconoce `-Flowdomain(virtual)-` ni captions sin corchetes (ejemplos CP nq8/20/31,
   MP, AP): esos STL quedan sin componente en `geometry`. Arreglar y cubrir en selftest.
6. **Tema claro por defecto** si la ronda 2 no lo dejó.
7. **Curvas características.** El export `PerformanceData` genera `<base>.cft-pp` (XML: `<Characteristic><Curve Name="Δpt - ṁ" …><Points Count=100>` con pares x,y; hay varias `Curve`: listar sus `Name`/`Desc` y mapear a H-Q, η-Q, P-Q, NPSH-Q). Exportarlo siempre (es ligero, 28 KB), parsearlo a `run.json["curves"]` y mostrar una pestaña "Curvas" con SVG propio (sin librerías): H-Q con el punto de diseño marcado, η-Q y P-Q; en Comparar superponer A y B.
   Del reporte HTML (`Report`) parsear a `run.json["report"]` al menos: βB1/βB2 [°] por span, ángulo de envolvente Δφ, área de garganta, w2/w1, ηh/ηv/ηm, NPSHR, cu2/cm2, y mostrarlos en Hitos y en Comparar (en Comparar, con Δ).
8. **Limpiar letreros.** Petición del usuario: quitar textos explicativos y etiquetas redundantes de la UI (frases tipo "Claude decide, CFturbo construye…", notas bajo botones, placeholders largos, leyendas repetidas); dejar una sola palabra por control, ayuda en `title`/tooltip y la lista de atajos en `?`. Criterio: ningún bloque de texto de más de una línea fuera del chat y de Hitos; el contador de corridas conservadas y rutas pasan a tooltip.
