// QUE: media, mínimo y máximo de monitores en las últimas iteraciones (estudio de malla con residuales planos): plot de monitores nuevo + export CSV en la MISMA macro (re-exportar un plot creado antes salió «EmptyArray»); no incluir eta_Euler (valor no finito en la iteración 0 tumba el export). Verificado BombaNQ10 2026-10-28
// VERSION: 19.06.009-R8
// FECHA: 2026-10-28 · 2026-10-30 (solo compilado, sin solver): ventana relativa a la última iteración, pendiente lineal y
//        oscilación sin tendencia por monitor, y el plot temporal se borra al terminar (antes quedaba un promedio_<ms> por llamada)
// MONS: monitores separados por coma; CSV: ruta de salida (historial completo: iteración y un monitor por columna).
// VENTANA: nº de iteraciones a promediar contando hacia atrás desde la última (defecto 200): se promedian las iteraciones
//          > última − VENTANA, así un reintento con más iteraciones no hay que editarlo.
// DESDE (compatibilidad, opcional): iteración fija a partir de la cual promediar; solo se usa si no se da VENTANA.
// Salida por monitor: MEDIA <monitor> <media> min <..> max <..> n <..> desde <it> pendiente_100it <..> deriva_pct_100it <..>
//          oscilacion_pct <..>  (pendiente por mínimos cuadrados en unidades/100 it; deriva = pendiente en % de la media
//          por 100 it; oscilación = 2·σ del residuo sin tendencia en % de la media, como historial() del orquestador).
String csv = "CSV", sVen = "VENTANA", sDes = "DESDE";
java.util.List<Monitor> ms = new java.util.ArrayList<Monitor>();
for (String nme : "MONS".split(",")) {
  try { Monitor m = sim.getMonitorManager().getMonitor(nme.trim()); if (m != null) ms.add(m); else sim.println("WARN\tno existe el monitor " + nme.trim()); }
  catch (Exception e) { sim.println("WARN\tno existe el monitor " + nme.trim()); }
}
StarPlot p = sim.getPlotManager().createMonitorPlot(ms, "promedio_" + System.currentTimeMillis());
p.export(csv, ",");
try { sim.getPlotManager().deletePlots(new java.util.ArrayList<StarPlot>(java.util.Arrays.asList(p))); } catch (Exception e) { sim.println("WARN\tno pude borrar el plot temporal: " + e); }
java.util.List<String> L = java.nio.file.Files.readAllLines(java.nio.file.Paths.get(csv));
String[] h = L.get(0).replace("\"", "").split(",");
java.util.List<double[]> filas = new java.util.ArrayList<double[]>();
for (int k = 1; k < L.size(); k++) {
  String[] c = L.get(k).split(",");
  if (c.length < h.length) continue;
  double[] f = new double[h.length];
  try { for (int j = 0; j < h.length; j++) f[j] = Double.parseDouble(c[j].trim()); } catch (Exception e) { continue; }
  filas.add(f);
}
if (filas.isEmpty()) throw new RuntimeException("historial vacío en " + csv);
double itUlt = filas.get(filas.size() - 1)[0];
double it0;
if (!sVen.equals("VENT" + "ANA") && !sVen.trim().isEmpty()) it0 = itUlt - Double.parseDouble(sVen.trim());
else if (!sDes.equals("DES" + "DE") && !sDes.trim().isEmpty()) it0 = Double.parseDouble(sDes.trim());
else it0 = itUlt - 200;
for (int j = 1; j < h.length; j++) {
  double s = 0, mn = 1e300, mx = -1e300, sx = 0; int n = 0;
  for (double[] f : filas) {
    double v = f[j];
    if (f[0] <= it0 || Double.isNaN(v) || Double.isInfinite(v)) continue;
    s += v; sx += f[0]; mn = Math.min(mn, v); mx = Math.max(mx, v); n++;
  }
  if (n == 0) { sim.println("MEDIA\t" + h[j] + "\tnan\tn 0\tdesde " + (long) it0); continue; }
  double m = s / n, xm = sx / n, sxx = 0, sxy = 0;
  for (double[] f : filas) {
    double v = f[j];
    if (f[0] <= it0 || Double.isNaN(v) || Double.isInfinite(v)) continue;
    sxx += (f[0] - xm) * (f[0] - xm); sxy += (f[0] - xm) * (v - m);
  }
  double b = sxx > 0 ? sxy / sxx : 0, ss = 0;
  for (double[] f : filas) {
    double v = f[j];
    if (f[0] <= it0 || Double.isNaN(v) || Double.isInfinite(v)) continue;
    double r = v - (m + b * (f[0] - xm)); ss += r * r;
  }
  double sigma = Math.sqrt(ss / n), am = Math.abs(m);
  String der = am > 1e-12 ? String.valueOf(b * 100 / am * 100) : "nan", osc = am > 1e-12 ? String.valueOf(2 * sigma / am * 100) : "nan";
  sim.println("MEDIA\t" + h[j] + "\t" + m + "\tmin " + mn + "\tmax " + mx + "\tn " + n + "\tdesde " + (long) it0
              + "\tpendiente_100it " + b * 100 + "\tderiva_pct_100it " + der + "\toscilacion_pct " + osc);
}
