// QUE: lote 09 · datos finales para la revisión, escritos por el solver en OUT_JSON (sin pasar por el modelo): iteración,
//      celdas por región, valores finales de todos los reportes, balance de masa, radio de salida de los álabes medido
//      (BladeTE, para comprobar el D2 de la variante), radio máximo del rotor e y+ en los álabes (media y máximo).
double[] AX = {{{AX}}};
String OUT_JSON = "{{OUT_JSON}}";
ReportManager rm = sim.getReportManager();
FieldFunctionManager ffm = sim.getFieldFunctionManager();
StringBuilder js = new StringBuilder("{\n");
js.append("  \"iteracion\": ").append(sim.getSimulationIterator().getCurrentIteration()).append(",\n");
ElementCountReport ec = rm.createReport(ElementCountReport.class);
long total = 0; StringBuilder cel = new StringBuilder();
for (Region r : sim.getRegionManager().getRegions()) {
  ec.getParts().setObjects(r); long c = (long) ec.getReportMonitorValue(); total += c;
  cel.append(cel.length() > 0 ? ", " : "").append("\"").append(r.getPresentationName()).append("\": ").append(c);
}
rm.removeObjects(ec);
js.append("  \"celdas\": ").append(total).append(",\n  \"celdas_region\": {").append(cel).append("},\n");
StringBuilder rs = new StringBuilder();
for (Report r : rm.getObjects()) {
  double v; try { v = r.getReportMonitorValue(); } catch (Exception e) { continue; }
  if (Double.isNaN(v) || Double.isInfinite(v)) continue;
  rs.append(rs.length() > 0 ? ", " : "").append("\"").append(r.getPresentationName()).append("\": ").append(v);
}
js.append("  \"reportes\": {").append(rs).append("},\n");
double qi = rm.getReport("Q_in").getReportMonitorValue(), qo = rm.getReport("Q_out").getReportMonitorValue();
js.append("  \"balance_masa_pct\": ").append(100.0 * Math.abs(qi + qo) / Math.max(1e-12, Math.abs(qi))).append(",\n");
Region rot = sim.getRegionManager().getRegion("rotor");
UserFieldFunction rad = ffm.createFieldFunction(); rad.setFunctionName("tmp_radio");
rad.setDefinition("mag($${Position} - dot($${Position}, [" + AX[0] + "," + AX[1] + "," + AX[2] + "]) * [" + AX[0] + "," + AX[1] + "," + AX[2] + "])");
String[][] medir = {{"BladeTE", "r_salida_alabe_m"}, {"Outflow", "r_salida_rotor_m"}};
for (String[] m : medir) {
  if (!rot.getBoundaryManager().has(m[0])) continue;
  MaxReport mx = rm.createReport(MaxReport.class); mx.setFieldFunction(rad); mx.getParts().setObjects(rot.getBoundaryManager().getBoundary(m[0]));
  js.append("  \"").append(m[1]).append("\": ").append(mx.getReportMonitorValue()).append(",\n");
  rm.removeObjects(mx);
}
ffm.removeObjects(rad);
List<Boundary> blades = new ArrayList<Boundary>();
for (Boundary b : rot.getBoundaryManager().getBoundaries()) if (b.getPresentationName().startsWith("Blade")) blades.add(b);
FieldFunction yp = ffm.getFunction("WallYplus");
AreaAverageReport ya = rm.createReport(AreaAverageReport.class); ya.setFieldFunction(yp); ya.getParts().setObjects(blades);
MaxReport ym = rm.createReport(MaxReport.class); ym.setFieldFunction(yp); ym.getParts().setObjects(blades);
js.append("  \"yplus_alabes_medio\": ").append(ya.getReportMonitorValue()).append(",\n");
js.append("  \"yplus_alabes_max\": ").append(ym.getReportMonitorValue()).append("\n}\n");
rm.removeObjects(ya, ym);
java.nio.file.Files.write(java.nio.file.Paths.get(OUT_JSON), js.toString().getBytes("UTF-8"));
sim.println(js.toString());
sim.println("LOTE_OK 09");
