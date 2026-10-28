// QUE: lote 05 · reportes y monitores: pt_in/pt_out (promedio másico de presión total en los extremos de las extensiones),
//      Q_in/Q_out, M (momento de todas las paredes que giran: álabes, fillets, hub, shroud y discos SolidHub/SolidShroud,
//      sobre el eje AX; las carcasas CasingHub/CasingShroud son fijas y no entran), H, P_hid, P_eje (|RPM|), eta.
// Base: bomba-reportes + BombaNQ10 (M con fillets y discos exteriores).
double RHO = {{RHO}}, RPM = {{RPM}};
double[] AX = {{{AX}}};
ReportManager rm = sim.getReportManager();
Region rot = sim.getRegionManager().getRegion("rotor");
Boundary inlet = sim.getRegionManager().getRegion("ext_entrada").getBoundaryManager().getBoundary("inlet");
Boundary outlet = sim.getRegionManager().getRegion("ext_salida").getBoundaryManager().getBoundary("outlet");
FieldFunction ptot = sim.getFieldFunctionManager().getFunction("TotalPressure");
MassFlowAverageReport pin = rm.createReport(MassFlowAverageReport.class);
pin.setPresentationName("pt_in"); pin.setFieldFunction(ptot); pin.getParts().setObjects(inlet);
MassFlowAverageReport pout = rm.createReport(MassFlowAverageReport.class);
pout.setPresentationName("pt_out"); pout.setFieldFunction(ptot); pout.getParts().setObjects(outlet);
MassFlowReport qi = rm.createReport(MassFlowReport.class);
qi.setPresentationName("Q_in"); qi.getParts().setObjects(inlet);
MassFlowReport qo = rm.createReport(MassFlowReport.class);
qo.setPresentationName("Q_out"); qo.getParts().setObjects(outlet);
MomentReport mom = rm.createReport(MomentReport.class);
mom.setPresentationName("M");
mom.getDirection().setComponents(AX[0], AX[1], AX[2]);
mom.getOrigin().setComponents(0.0, 0.0, 0.0);
List<Boundary> walls = new ArrayList<Boundary>();
for (Boundary b : rot.getBoundaryManager().getBoundaries()) {
  String n = b.getPresentationName();
  if (n.startsWith("Blade") || n.equals("Hub") || n.equals("Shroud") || n.equals("SolidHub") || n.equals("SolidShroud")) walls.add(b);
}
mom.getParts().setObjects(walls);
for (Boundary b : walls) sim.println("M_WALL\t" + b.getPresentationName());
String g = "9.80665";
ExpressionReport H = rm.createReport(ExpressionReport.class);
H.setPresentationName("H"); H.setDefinition("(${pt_outReport} - ${pt_inReport}) / (" + RHO + " * " + g + ")");
ExpressionReport Ph = rm.createReport(ExpressionReport.class);
Ph.setPresentationName("P_hid"); Ph.setDefinition("abs(${Q_inReport}) * " + g + " * ${HReport}");
ExpressionReport Pe = rm.createReport(ExpressionReport.class);
Pe.setPresentationName("P_eje"); Pe.setDefinition("abs(${MReport}) * " + Math.abs(RPM) + " * 2 * 3.14159265 / 60");
ExpressionReport eta = rm.createReport(ExpressionReport.class);
eta.setPresentationName("eta"); eta.setDefinition("${P_hidReport} / ${P_ejeReport}");
for (Report r : new Report[] {pin, pout, qi, qo, mom, H, Ph, Pe, eta}) r.createMonitor();
for (Report r : rm.getObjects()) sim.println("REPORT\t" + r.getPresentationName());
sim.println("LOTE_OK 05");
