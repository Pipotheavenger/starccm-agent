// QUE: lote 07 · un bloque de BLOQUE iteraciones desde la iteración actual del .sim, sin pasar de MAX_IT en total (no hay
//      que editarla en un reintento: el orquestador rehace MAX_IT). Escribe una fila en CONV_CSV (iteración, reportes y
//      residuales) y el historial de residuales en RES_CSV. A la pantalla SOLO: una línea «ITERACION n H=.. M=.. eta=..
//      cont=..», «DIVERGE …» si la continuidad pasa de 1 o algún valor no es finito (NO seguir iterando) y «LOTE_OK 07 FIN»
//      al llegar a MAX_IT. Antes cada bloque devolvía ~50 KB: la tabla de monitores que el solver imprime en cada
//      iteración (va al stdout de la macro); ahora se vacía la lista de monitores impresos (MonitorManager.setPrintedMonitors).
// Base: tool iterate (export del plot Residuals: MonitorManager.export falla en batch 2410).
int BLOQUE = {{BLOQUE}}, MAX_IT = {{MAX_IT}};
String CONV_CSV = "{{CONV_CSV}}", RES_CSV = "{{RES_CSV}}";
try { sim.getMonitorManager().setPrintedMonitors(new ArrayList<Monitor>()); }
catch (Exception e) {
  try { List<Monitor> uno = new ArrayList<Monitor>(); for (Monitor m : sim.getMonitorManager().getObjects()) if (m.getPresentationName().startsWith("Continuity")) uno.add(m);
        sim.getMonitorManager().setPrintedMonitors(uno); } catch (Exception e2) { }
}
int it0 = sim.getSimulationIterator().getCurrentIteration();
int n = Math.min(BLOQUE, MAX_IT - it0);
if (n > 0) sim.getSimulationIterator().step(n);
int it = sim.getSimulationIterator().getCurrentIteration();
String[] reps = {"H", "M", "eta", "P_eje", "P_hid", "pt_in", "pt_out", "Q_in", "Q_out", "H_Euler", "eta_Euler"};
StringBuilder hdr = new StringBuilder("iteracion"), row = new StringBuilder("" + it);
java.util.Map<String, Double> val = new java.util.HashMap<String, Double>();
boolean malo = false;
for (String r : reps) {
  if (!sim.getReportManager().has(r)) continue;
  double v; try { v = sim.getReportManager().getReport(r).getReportMonitorValue(); } catch (Exception e) { v = Double.NaN; }
  hdr.append(",").append(r); row.append(",").append(v); val.put(r, v);
  if (!r.equals("eta_Euler") && (Double.isNaN(v) || Double.isInfinite(v))) malo = true;
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
    if (nm.toLowerCase().startsWith("continuity")) cont = v;
    if (Double.isNaN(v)) malo = true;
  }
} catch (Exception e) { hdr.append(",aviso"); row.append(",residuales_no_leidos"); }
java.nio.file.Path conv = java.nio.file.Paths.get(CONV_CSV);
if (!java.nio.file.Files.exists(conv)) java.nio.file.Files.write(conv, (hdr + "\n").getBytes("UTF-8"));
java.nio.file.Files.write(conv, (row + "\n").getBytes("UTF-8"), java.nio.file.StandardOpenOption.APPEND);
StringBuilder lin = new StringBuilder("ITERACION " + it);
for (String r : new String[] {"H", "M", "eta"}) lin.append(" ").append(r).append("=").append(val.containsKey(r) ? String.format(java.util.Locale.ROOT, "%.5g", val.get(r)) : "na");
lin.append(" cont=").append(cont < 0 ? "na" : String.format(java.util.Locale.ROOT, "%.3e", cont));
sim.println(lin.toString());
if (malo || cont > 1.0) sim.println("DIVERGE\titeracion " + it + "\tcontinuidad " + cont);
if (it >= MAX_IT) sim.println("LOTE_OK 07 FIN");
