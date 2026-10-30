// QUE: lote 05 · reportes y monitores: pt_in/pt_out (promedio másico de presión total en los extremos de las extensiones),
//      Q_in/Q_out, M (momento de todas las paredes que giran: álabes, fillets, hub, shroud y discos SolidHub/SolidShroud,
//      sobre el eje AX; las carcasas CasingHub/CasingShroud son fijas y no entran), H, P_hid, P_eje (|RPM|), eta.
//      Idempotente: si un reporte o su monitor ya existen se reusan (se reajustan), nunca «X 2».
// Base: bomba-reportes + BombaNQ10 (M con fillets y discos exteriores).
double RHO = {{RHO}}, RPM = {{RPM}};
double[] AX = {{{AX}}};
ReportManager rm = sim.getReportManager();
class Rep { <T extends Report> T get(Class<T> c, String nm) {
  if (rm.has(nm)) { Report r = rm.getReport(nm); if (c.isInstance(r)) return c.cast(r); rm.removeObjects(r); }
  T r = rm.createReport(c); r.setPresentationName(nm); return r; } }
Rep R = new Rep();
Region rot = sim.getRegionManager().getRegion("rotor");
Boundary inlet = sim.getRegionManager().getRegion("ext_entrada").getBoundaryManager().getBoundary("inlet");
Boundary outlet = sim.getRegionManager().getRegion("ext_salida").getBoundaryManager().getBoundary("outlet");
FieldFunction ptot = sim.getFieldFunctionManager().getFunction("TotalPressure");
MassFlowAverageReport pin = R.get(MassFlowAverageReport.class, "pt_in"); pin.setFieldFunction(ptot); pin.getParts().setObjects(inlet);
MassFlowAverageReport pout = R.get(MassFlowAverageReport.class, "pt_out"); pout.setFieldFunction(ptot); pout.getParts().setObjects(outlet);
MassFlowReport qi = R.get(MassFlowReport.class, "Q_in"); qi.getParts().setObjects(inlet);
MassFlowReport qo = R.get(MassFlowReport.class, "Q_out"); qo.getParts().setObjects(outlet);
MomentReport mom = R.get(MomentReport.class, "M");
mom.getDirection().setComponents(AX[0], AX[1], AX[2]);
mom.getOrigin().setComponents(0.0, 0.0, 0.0);
List<Boundary> walls = new ArrayList<Boundary>();
for (Boundary b : rot.getBoundaryManager().getBoundaries()) {
  String n = b.getPresentationName();
  if (n.startsWith("Blade") || n.equals("Hub") || n.equals("Shroud") || n.equals("SolidHub") || n.equals("SolidShroud")) walls.add(b);
}
mom.getParts().setObjects(walls);
StringBuilder mw = new StringBuilder();
for (Boundary b : walls) mw.append(mw.length() > 0 ? "," : "").append(b.getPresentationName());
sim.println("M_WALL\t" + mw);
String g = "9.80665";
ExpressionReport H = R.get(ExpressionReport.class, "H"); H.setDefinition("(${pt_outReport} - ${pt_inReport}) / (" + RHO + " * " + g + ")");
ExpressionReport Ph = R.get(ExpressionReport.class, "P_hid"); Ph.setDefinition("abs(${Q_inReport}) * " + g + " * ${HReport}");
ExpressionReport Pe = R.get(ExpressionReport.class, "P_eje"); Pe.setDefinition("abs(${MReport}) * " + Math.abs(RPM) + " * 2 * 3.14159265 / 60");
ExpressionReport eta = R.get(ExpressionReport.class, "eta"); eta.setDefinition("${P_hidReport} / ${P_ejeReport}");
int nuevos = 0;
for (Report r : new Report[] {pin, pout, qi, qo, mom, H, Ph, Pe, eta}) {
  boolean hay = false;
  try { hay = sim.getMonitorManager().has(r.getPresentationName() + " Monitor"); } catch (Exception e) { }
  if (!hay) { r.createMonitor(); nuevos++; }
}
sim.println("LOTE_OK 05 " + rm.getObjects().size() + " reportes, " + nuevos + " monitores nuevos");
