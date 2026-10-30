// QUE: lote 09 · datos finales para la revisión, escritos por el solver en OUT_JSON (sin pasar por el modelo): iteración,
//      celdas por región, valores finales de todos los reportes, balance de masa, Q_out frente a la masa impuesta, pt_in,
//      radios del borde de salida (BladeTE: mín., máx., medio de área), radio máximo de la salida del rotor (todas sus
//      fronteras «Outflow*»: la «Outflow» sola queda vacía tras intersecar la interfaz y daba −1,8e308), momento por grupo
//      de paredes con signo e y+ en los álabes (media y máximo). Valores no finitos o |v| > 1e300 → null: el JSON siempre vale.
// Signo del par (M_signo_ok): MomentReport da el momento que el FLUIDO ejerce sobre las paredes, proyectado sobre AX (05
//      define M así, y P_eje = |M|·|ω|). En una bomba el fluido frena al rodete: ese momento va contra ω. Con
//      ω = sign(rpm)·|ω|·eje_MRF, M·sign(rpm)·sign(eje_MRF·AX) < 0 ⇔ la bomba absorbe potencia. Comprobado con G047
//      (rpm −3000, eje +Z, AX +Z): M = +302 N·m → +302·(−1)·(+1) < 0 → true. Con el par de una turbina sale false.
// Pantalla: solo «LOTE_OK 09 …» con las claves principales (el JSON completo queda en OUT_JSON).
double[] AX = {{{AX}}};
double RPM = {{RPM}}, MASA = {{MASA}};
String OUT_JSON = "{{OUT_JSON}}";
ReportManager rm = sim.getReportManager();
FieldFunctionManager ffm = sim.getFieldFunctionManager();
class J {
  StringBuilder sb = new StringBuilder();
  String num(double v) { return (Double.isNaN(v) || Double.isInfinite(v) || Math.abs(v) > 1e300) ? "null" : String.valueOf(v); }
  String str(String s) { return "\"" + s.replace("\\", "\\\\").replace("\"", "\\\"") + "\""; }
  void raw(String k, String v) { sb.append(sb.length() > 0 ? ",\n" : "").append("  ").append(str(k)).append(": ").append(v); }
  void put(String k, double v) { raw(k, num(v)); }
}
J js = new J();
List<Report> tmp = new ArrayList<Report>();
List<FieldFunction> tmpf = new ArrayList<FieldFunction>();
String linea = "";
try {
  js.raw("iteracion", "" + sim.getSimulationIterator().getCurrentIteration());
  ElementCountReport ec = rm.createReport(ElementCountReport.class); tmp.add(ec);
  long total = 0; StringBuilder cel = new StringBuilder();
  for (Region r : sim.getRegionManager().getRegions()) {
    ec.getParts().setObjects(r); long c = (long) ec.getReportMonitorValue(); total += c;
    cel.append(cel.length() > 0 ? ", " : "").append(js.str(r.getPresentationName())).append(": ").append(c);
  }
  js.raw("celdas", "" + total); js.raw("celdas_region", "{" + cel + "}");
  StringBuilder rs = new StringBuilder();
  for (Report r : rm.getObjects()) {
    if (tmp.contains(r)) continue;
    double v; try { v = r.getReportMonitorValue(); } catch (Exception e) { continue; }
    rs.append(rs.length() > 0 ? ", " : "").append(js.str(r.getPresentationName())).append(": ").append(js.num(v));
  }
  js.raw("reportes", "{" + rs + "}");
  double qi = Double.NaN, qo = Double.NaN, pin = Double.NaN;
  try { qi = rm.getReport("Q_in").getReportMonitorValue(); qo = rm.getReport("Q_out").getReportMonitorValue(); } catch (Exception e) { }
  try { pin = rm.getReport("pt_in").getReportMonitorValue(); } catch (Exception e) { }
  js.put("balance_masa_pct", 100.0 * Math.abs(qi + qo) / Math.max(1e-12, Math.abs(qi)));
  js.put("Q_out_kg_s", qo);
  js.put("masa_bc_kg_s", MASA);
  js.put("Q_out_vs_masa_pct", 100.0 * (Math.abs(qo) - MASA) / Math.max(1e-12, MASA));
  js.put("pt_in_Pa", pin);
  Region rot = sim.getRegionManager().getRegion("rotor");
  UserFieldFunction rad = null;
  try { FieldFunction f0 = ffm.getFunction("tmp_radio"); if (f0 instanceof UserFieldFunction) rad = (UserFieldFunction) f0; } catch (Exception e) { }
  if (rad == null) { rad = ffm.createFieldFunction(); rad.setPresentationName("tmp_radio"); rad.setFunctionName("tmp_radio"); }
  tmpf.add(rad);
  rad.setDefinition("mag($${Position} - dot($${Position}, [" + AX[0] + "," + AX[1] + "," + AX[2] + "]) * [" + AX[0] + "," + AX[1] + "," + AX[2] + "])");
  // borde de salida del álabe: mínimo, máximo y medio de área (flujo mixto: inclinado, el máximo no es D2/2)
  double teMax = Double.NaN;
  if (rot.getBoundaryManager().has("BladeTE")) {
    Boundary te = rot.getBoundaryManager().getBoundary("BladeTE");
    MaxReport mx = rm.createReport(MaxReport.class); tmp.add(mx); mx.setFieldFunction(rad); mx.getParts().setObjects(te);
    MinReport mn = rm.createReport(MinReport.class); tmp.add(mn); mn.setFieldFunction(rad); mn.getParts().setObjects(te);
    AreaAverageReport av = rm.createReport(AreaAverageReport.class); tmp.add(av); av.setFieldFunction(rad); av.getParts().setObjects(te);
    teMax = mx.getReportMonitorValue();
    js.put("r_te_min_m", mn.getReportMonitorValue()); js.put("r_te_max_m", teMax); js.put("r_te_medio_m", av.getReportMonitorValue());
  } else { js.raw("r_te_min_m", "null"); js.raw("r_te_max_m", "null"); js.raw("r_te_medio_m", "null"); }
  js.put("r_salida_alabe_m", teMax);  // = r_te_max_m (compatibilidad)
  List<Boundary> outs = new ArrayList<Boundary>();
  for (Boundary b : rot.getBoundaryManager().getBoundaries()) if (b.getPresentationName().startsWith("Outflow")) outs.add(b);
  double rOut = Double.NaN;
  if (!outs.isEmpty()) {
    MaxReport mo = rm.createReport(MaxReport.class); tmp.add(mo); mo.setFieldFunction(rad); mo.getParts().setObjects(outs);
    rOut = mo.getReportMonitorValue();
  }
  js.put("r_salida_rotor_m", rOut);
  // momento por grupo de paredes, con signo, sobre AX (mismas fronteras que M de 05)
  List<Boundary> gA = new ArrayList<Boundary>(), gC = new ArrayList<Boundary>(), gD = new ArrayList<Boundary>();
  for (Boundary b : rot.getBoundaryManager().getBoundaries()) {
    String nb = b.getPresentationName();
    if (nb.startsWith("Blade")) gA.add(b);
    else if (nb.equals("Hub") || nb.equals("Shroud")) gC.add(b);
    else if (nb.equals("SolidHub") || nb.equals("SolidShroud")) gD.add(b);
  }
  String[] gn = {"M_alabes", "M_cubos", "M_discos"};
  List<List<Boundary>> gl = new ArrayList<List<Boundary>>(); gl.add(gA); gl.add(gC); gl.add(gD);
  double suma = 0;
  for (int i = 0; i < 3; i++) {
    if (gl.get(i).isEmpty()) { js.put(gn[i], 0.0); continue; }
    MomentReport mr = rm.createReport(MomentReport.class); tmp.add(mr);
    mr.getDirection().setComponents(AX[0], AX[1], AX[2]); mr.getOrigin().setComponents(0.0, 0.0, 0.0);
    mr.getParts().setObjects(gl.get(i));
    double v = mr.getReportMonitorValue(); suma += v; js.put(gn[i], v);
  }
  double Mt = Double.NaN;
  try { Mt = rm.getReport("M").getReportMonitorValue(); } catch (Exception e) { Mt = suma; }
  js.put("M_total", Mt);
  js.put("M_suma_grupos", suma);
  // signo: sentido de ω proyectado sobre AX, del marco del rotor si lo hay (si no, del signo de RPM con eje = AX)
  double sw = Math.signum(RPM);
  try {
    Object rf = rot.getValues().get(MotionSpecification.class).getReferenceFrame();
    if (rf instanceof RotatingReferenceFrame) {
      DoubleVector a = ((RotatingReferenceFrame) rf).getAxisDirection().getSIVector();
      sw = Math.signum(((RotatingReferenceFrame) rf).getRotationRate().getSIValue()) * Math.signum(a.get(0) * AX[0] + a.get(1) * AX[1] + a.get(2) * AX[2]);
    }
  } catch (Exception e) { }
  boolean finM = !Double.isNaN(Mt) && !Double.isInfinite(Mt);
  js.raw("M_signo_ok", finM && sw != 0 ? String.valueOf(Mt * sw < 0) : "null");
  List<Boundary> blades = gA;
  FieldFunction yp = ffm.getFunction("WallYplus");
  AreaAverageReport ya = rm.createReport(AreaAverageReport.class); tmp.add(ya); ya.setFieldFunction(yp); ya.getParts().setObjects(blades);
  MaxReport ym = rm.createReport(MaxReport.class); tmp.add(ym); ym.setFieldFunction(yp); ym.getParts().setObjects(blades);
  js.put("yplus_alabes_medio", ya.getReportMonitorValue());
  js.put("yplus_alabes_max", ym.getReportMonitorValue());
  linea = "M " + js.num(Mt) + " signo_ok " + (finM && sw != 0 ? String.valueOf(Mt * sw < 0) : "null") + " r_te_max " + js.num(teMax) + " r_salida_rotor " + js.num(rOut);
} catch (Exception e) {
  js.raw("error_09", js.str(e.toString()));
  linea = "con error: " + e;
} finally {
  try { if (!tmp.isEmpty()) rm.removeObjects(tmp); } catch (Exception e) { }
  try { if (!tmpf.isEmpty()) ffm.removeObjects(tmpf); } catch (Exception e) { }
}
java.nio.file.Files.write(java.nio.file.Paths.get(OUT_JSON), ("{\n" + js.sb + "\n}\n").getBytes("UTF-8"));
sim.println("LOTE_OK 09 " + linea);
