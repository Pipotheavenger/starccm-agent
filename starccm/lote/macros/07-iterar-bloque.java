// QUE: lote 07 · un bloque de iteraciones (sin pasar de MAX_IT en total). Al terminar escribe una fila en CONV_CSV (iteración,
//      reportes y residuales) y el historial completo de residuales en RES_CSV. Imprime DIVERGE si la continuidad pasa de 1
//      o algún valor no es finito: con eso NO se sigue iterando.
// Base: tool iterate (export del plot Residuals: MonitorManager.export falla en batch 2410).
int BLOQUE = {{BLOQUE}}, MAX_IT = {{MAX_IT}};
String CONV_CSV = "{{CONV_CSV}}", RES_CSV = "{{RES_CSV}}";
int it0 = sim.getSimulationIterator().getCurrentIteration();
int n = Math.min(BLOQUE, MAX_IT - it0);
if (n > 0) sim.getSimulationIterator().step(n);
int it = sim.getSimulationIterator().getCurrentIteration();
String[] reps = {"H", "M", "eta", "P_eje", "P_hid", "pt_in", "pt_out", "Q_in", "Q_out", "H_Euler", "eta_Euler"};
StringBuilder hdr = new StringBuilder("iteracion"), row = new StringBuilder("" + it);
boolean malo = false;
for (String r : reps) {
  if (!sim.getReportManager().has(r)) continue;
  double v = sim.getReportManager().getReport(r).getReportMonitorValue();
  hdr.append(",").append(r); row.append(",").append(v);
  if (!r.equals("eta_Euler") && (Double.isNaN(v) || Double.isInfinite(v))) malo = true;
  sim.println("REPORT\t" + r + "\t" + v);
}
double cont = -1;
try {
  sim.getPlotManager().getPlot("Residuals").export(RES_CSV, ",");
  java.util.List<String> L = java.nio.file.Files.readAllLines(java.nio.file.Paths.get(RES_CSV));
  String[] h = L.get(0).replace("\"", "").split(","), last = L.get(L.size() - 1).split(",");
  for (int j = 1; j < h.length && j < last.length; j++) {
    String nm = h[j].trim();
    double v = Double.parseDouble(last[j].trim());
    hdr.append(",").append(nm.replace(" ", "_")); row.append(",").append(v);
    sim.println("RESIDUAL\t" + nm + "\t" + v);
    if (nm.toLowerCase().startsWith("continuity")) cont = v;
    if (Double.isNaN(v)) malo = true;
  }
} catch (Exception e) { sim.println("WARN\tresiduales: " + e); }
java.nio.file.Path conv = java.nio.file.Paths.get(CONV_CSV);
if (!java.nio.file.Files.exists(conv)) java.nio.file.Files.write(conv, (hdr + "\n").getBytes("UTF-8"));
java.nio.file.Files.write(conv, (row + "\n").getBytes("UTF-8"), java.nio.file.StandardOpenOption.APPEND);
if (malo || cont > 1.0) sim.println("DIVERGE\titeracion " + it + "\tcontinuidad " + cont);
sim.println("ITERACION\t" + it);
sim.println("LOTE_OK 07 it " + it);
