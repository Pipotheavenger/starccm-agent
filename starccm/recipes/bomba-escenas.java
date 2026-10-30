// QUE: escenas: presión en álabes (rango de color robusto) e y+ en paredes; reportes yplus_min/max_alabes
// VERSION: 19.06.009-R8
// FECHA: 2026-10-23 · 2026-10-30 (solo compilado, sin solver): idempotente (borra y recrea sus escenas, nunca «X 2»;
//        reusa los reportes), sin «velocidad_plano» (|v| en plano_medio: la cubren vectores_medio de escenas-fluido y
//        plano_vectores), y la presión con rango fijo [p_in − 0,25Δ, p_out + 0,25Δ] (Δ = p_out − p_in, áreas medias en
//        las fronteras Inflow*/Outflow* del rotor): el pico de succión del borde de ataque ya no aplasta la escala.
Region rot = sim.getRegionManager().getRegion("rotor");
List<Boundary> blades = new ArrayList<Boundary>();
for (String n : new String[] {"BladeSS", "BladePS", "BladeLE", "BladeTE", "Hub"})
  if (rot.getBoundaryManager().has(n)) blades.add(rot.getBoundaryManager().getBoundary(n));
class Esc { Scene nueva(String nm) {
  java.util.Vector<Scene> viejas = new java.util.Vector<Scene>();
  for (Scene s : sim.getSceneManager().getScenes()) if (s.getPresentationName().matches(java.util.regex.Pattern.quote(nm) + "( \\d+)?")) viejas.add(s);
  if (!viejas.isEmpty()) sim.getSceneManager().deleteScenes(viejas);
  Scene s = sim.getSceneManager().createScene(nm); s.setPresentationName(nm); s.initializeAndWait(); return s; } }
Esc esc = new Esc();
FieldFunction pres = sim.getFieldFunctionManager().getFunction("Pressure");
Scene s1 = esc.nueva("presion_alabes");
ScalarDisplayer d1 = s1.getDisplayerManager().createScalarDisplayer("p"); d1.initialize();
d1.setRepresentation(sim.getRepresentationManager().getDefaultFvRepresentation());
d1.getInputParts().setObjects(blades);
d1.getScalarDisplayQuantity().setFieldFunction(pres);
try {
  List<Boundary> bi = new ArrayList<Boundary>(), bo = new ArrayList<Boundary>();
  for (Boundary b : rot.getBoundaryManager().getBoundaries()) {
    if (b.getPresentationName().startsWith("Inflow")) bi.add(b);
    if (b.getPresentationName().startsWith("Outflow")) bo.add(b);
  }
  AreaAverageReport ai = sim.getReportManager().createReport(AreaAverageReport.class); ai.setFieldFunction(pres); ai.getParts().setObjects(bi);
  AreaAverageReport ao = sim.getReportManager().createReport(AreaAverageReport.class); ao.setFieldFunction(pres); ao.getParts().setObjects(bo);
  double pi = ai.getReportMonitorValue(), po = ao.getReportMonitorValue(), dp = po - pi;
  sim.getReportManager().removeObjects(ai, ao);
  if (dp > 0 && !Double.isNaN(dp) && !Double.isInfinite(dp)) {
    ScalarDisplayQuantity q = d1.getScalarDisplayQuantity();
    q.setAutoRange(AutoRangeMode.NONE);
    q.setRange(new DoubleVector(new double[] {pi - 0.25 * dp, po + 0.25 * dp}));
    q.setClip(ClipMode.NONE);
    sim.println("RANGO\tpresion_alabes\t" + (pi - 0.25 * dp) + " .. " + (po + 0.25 * dp) + " Pa");
  } else sim.println("WARN\tsin rango robusto de presión (p_in " + pi + ", p_out " + po + "): automático");
} catch (Exception e) { sim.println("WARN\trango de presión: " + e); }
s1.resetCamera(true);
List<Region> regs = new ArrayList<Region>(sim.getRegionManager().getRegions());
List<Boundary> walls = new ArrayList<Boundary>();
for (Region r : regs) for (Boundary b : r.getBoundaryManager().getBoundaries()) if (b.getBoundaryType() instanceof WallBoundary) walls.add(b);
Scene s3 = esc.nueva("yplus");
ScalarDisplayer d3 = s3.getDisplayerManager().createScalarDisplayer("y+"); d3.initialize();
d3.setRepresentation(sim.getRepresentationManager().getDefaultFvRepresentation());
d3.getInputParts().setObjects(walls);
d3.getScalarDisplayQuantity().setFieldFunction(sim.getFieldFunctionManager().getFunction("WallYplus"));
s3.resetCamera(true);
ReportManager rmE = sim.getReportManager();
MaxReport ymax = rmE.has("yplus_max_alabes") && rmE.getReport("yplus_max_alabes") instanceof MaxReport ? (MaxReport) rmE.getReport("yplus_max_alabes") : rmE.createReport(MaxReport.class);
ymax.setPresentationName("yplus_max_alabes");
ymax.setFieldFunction(sim.getFieldFunctionManager().getFunction("WallYplus")); ymax.getParts().setObjects(blades);
MinReport ymin = rmE.has("yplus_min_alabes") && rmE.getReport("yplus_min_alabes") instanceof MinReport ? (MinReport) rmE.getReport("yplus_min_alabes") : rmE.createReport(MinReport.class);
ymin.setPresentationName("yplus_min_alabes");
ymin.setFieldFunction(sim.getFieldFunctionManager().getFunction("WallYplus")); ymin.getParts().setObjects(blades);
sim.println("YPLUS alabes min " + ymin.getReportMonitorValue() + " max " + ymax.getReportMonitorValue());
for (Scene s : sim.getSceneManager().getScenes()) sim.println("SCENE\t" + s.getPresentationName());
