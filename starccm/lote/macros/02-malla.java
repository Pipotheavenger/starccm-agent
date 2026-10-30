// QUE: lote 02 · malla: UNA operación por parte (las 3 juntas fallan en las caras coincidentes), remallador + reparación +
//      poliédrica + prismas; álabes al ALABES_PCT del base; mínimo del rotor al MIN_ROTOR_PCT (huelgos de las cámaras
//      laterales: con 10 % G001 dio 3,8 M celdas, con 25 % 1,46 M). Idempotente: si las operaciones existen (remallado,
//      también las de las extensiones malla_ext_*, que conservan su propio base de 03) les pone el base nuevo y las
//      vuelve a ejecutar. Pantalla: CELLS (una línea), CELLS_TOTAL y LOTE_OK; el detalle (segundos por operación,
//      celdas por región, fronteras) va a MALLA_JSON (03 lo amplía con las extensiones).
// Base: bomba-malla + mallar-rotor-minimo-huelgos (verificadas en BombaNQ10).
double BASE_MM = {{BASE_MM}}, MIN_ROTOR_PCT = {{MIN_ROTOR_PCT}}, ALABES_PCT = {{ALABES_PCT}};
int PRISMAS = {{PRISMAS}};
Units mm = sim.getUnitsManager().getUnits("mm");
MeshOperationManager mom = sim.get(MeshOperationManager.class);
for (GeometryPart part : sim.get(SimulationPartManager.class).getParts()) {
  String pn = part.getPresentationName();
  String n = pn.contains("Stator") ? "estator" : pn.contains("Impeller") ? "rotor" : pn.contains("Volute") ? "voluta" : null;
  if (n == null || mom.has("malla_" + n)) continue;
  AutoMeshOperation op = mom.createAutoMeshOperation(
      Arrays.asList("star.resurfacer.ResurfacerAutoMesher", "star.resurfacer.AutomaticSurfaceRepairAutoMesher", "star.dualmesher.DualAutoMesher", "star.prismmesher.PrismAutoMesher"),
      new ArrayList<GeometryPart>(Arrays.asList(part)));
  op.setPresentationName("malla_" + n);
  if (n.equals("rotor")) {
    SurfaceCustomMeshControl sc = op.getCustomMeshControls().createSurfaceControl();
    sc.setPresentationName("alabes");
    List<GeometryObject> blades = new ArrayList<GeometryObject>();
    for (PartSurface s : part.getPartSurfaces()) if (s.getPresentationName().contains("Blade")) blades.add(s);
    sc.getGeometryObjects().setObjects(blades);
    sc.getCustomConditions().get(PartsTargetSurfaceSizeOption.class).setSelected(PartsTargetSurfaceSizeOption.Type.CUSTOM);
  }
}
StringBuilder js = new StringBuilder("{\n  \"base_mm\": " + BASE_MM + ",\n  \"segundos\": {");
int nOp = 0;
for (Object o : mom.getObjects()) {
  if (!(o instanceof AutoMeshOperation)) continue;
  AutoMeshOperation op = (AutoMeshOperation) o;
  String n = op.getPresentationName();
  if (!n.startsWith("malla_")) continue;
  // las extensiones (malla_ext_*) tienen su base propio (BASE_EXT_MM de 03): se re-ejecutan sin tocarlo
  if (!n.startsWith("malla_ext_")) op.getDefaultValues().get(BaseSize.class).setValueAndUnits(BASE_MM, mm);
  op.getDefaultValues().get(NumPrismLayers.class).setNumLayers(PRISMAS);
  op.getDefaultValues().get(PrismLayerStretching.class).setStretching(1.3);
  op.getDefaultValues().get(PrismThickness.class).setRelativeSize(10.0);
  if (n.equals("malla_rotor")) {
    op.getDefaultValues().get(PartsMinimumSurfaceSize.class).getRelativeSize().setPercentage(MIN_ROTOR_PCT);
    SurfaceCustomMeshControl sc = (SurfaceCustomMeshControl) op.getCustomMeshControls().getObject("alabes");
    sc.getCustomValues().get(PartsTargetSurfaceSize.class).getRelativeSize().setPercentage(ALABES_PCT);
  }
  long t0 = System.currentTimeMillis();
  op.execute();
  js.append(nOp++ > 0 ? ", " : "").append("\"").append(n).append("\": ").append((System.currentTimeMillis() - t0) / 1000.0);
}
js.append("},\n  \"celdas_region\": {");
ReportManager rm = sim.getReportManager();
ElementCountReport ec = rm.createReport(ElementCountReport.class);
long total = 0;
StringBuilder cel = new StringBuilder();
try {
  int i = 0;
  for (Region r : sim.getRegionManager().getRegions()) {
    ec.getParts().setObjects(r);
    long c = (long) ec.getReportMonitorValue(); total += c;
    js.append(i++ > 0 ? ", " : "").append("\"").append(r.getPresentationName()).append("\": ").append(c);
    cel.append(" ").append(r.getPresentationName()).append("=").append(c);
  }
} finally { rm.removeObjects(ec); }
js.append("},\n  \"celdas_total\": ").append(total).append(",\n  \"fronteras\": [");
int nb = 0;
for (Region r : sim.getRegionManager().getRegions())
  for (Boundary b : r.getBoundaryManager().getBoundaries())
    js.append(nb++ > 0 ? ", " : "").append("\"").append(r.getPresentationName()).append("/").append(b.getPresentationName().replace("\"", "'")).append("\"");
js.append("]\n}\n");
java.nio.file.Files.write(java.nio.file.Paths.get("{{MALLA_JSON}}"), js.toString().getBytes("UTF-8"));
sim.println("CELLS" + cel);
sim.println("CELLS_TOTAL\t" + total + "\tBASE_MM\t" + BASE_MM);
sim.println("LOTE_OK 02 " + total + " celdas");
