// QUE: media, mínimo y máximo de monitores en las últimas iteraciones (estudio de malla con residuales planos): plot de monitores nuevo + export CSV en la MISMA macro (re-exportar un plot creado antes salió «EmptyArray»); no incluir eta_Euler (valor no finito en la iteración 0 tumba el export). Verificado BombaNQ10 2026-10-28
// VERSION: 19.06.009-R8
// FECHA: 2026-10-28
// MONS: monitores separados por coma; DESDE: iteración a partir de la cual promediar; CSV: ruta de salida
String csv = "CSV";
java.util.List<Monitor> ms = new java.util.ArrayList<Monitor>();
for (String nme : "MONS".split(",")) ms.add(sim.getMonitorManager().getMonitor(nme.trim()));
StarPlot p = sim.getPlotManager().createMonitorPlot(ms, "promedio_" + System.currentTimeMillis());
p.export(csv, ",");
java.util.List<String> L = java.nio.file.Files.readAllLines(java.nio.file.Paths.get(csv));
String[] h = L.get(0).replace("\"", "").split(",");
int it0 = DESDE, n = 0;
double[] s = new double[h.length], mn = new double[h.length], mx = new double[h.length];
java.util.Arrays.fill(mn, 1e30); java.util.Arrays.fill(mx, -1e30);
for (int k = 1; k < L.size(); k++) {
  String[] c = L.get(k).split(",");
  if (c.length < h.length || Double.parseDouble(c[0]) <= it0) continue;
  for (int j = 1; j < h.length; j++) { double v = Double.parseDouble(c[j]); s[j] += v; mn[j] = Math.min(mn[j], v); mx[j] = Math.max(mx[j], v); }
  n++;
}
for (int j = 1; j < h.length; j++) sim.println("MEDIA\t" + h[j] + "\t" + s[j] / n + "\tmin " + mn[j] + "\tmax " + mx[j] + "\tn " + n);
