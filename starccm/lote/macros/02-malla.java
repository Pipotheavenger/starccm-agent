// QUE: lote 02 · malla: UNA operación por parte (las 3 juntas fallan en las caras coincidentes), remallador + reparación +
//      poliédrica + prismas; álabes al ALABES_PCT del base; mínimo del rotor al MIN_ROTOR_PCT (huelgos de las cámaras
//      laterales: con 10 % G001 dio 3,8 M celdas, con 25 % 1,46 M). Idempotente: si las operaciones existen (remallado)
//      les pone el base nuevo y las vuelve a ejecutar, también las de las extensiones malla_ext_* (de 03), que quedan con
//      base = 2 × BASE_MM y el MISMO espesor absoluto de prismas que la bomba (relativo 10 % de BASE_MM en la bomba =
//      5 % de su base doble en la extensión). REMALLAR = editar solo BASE_MM aquí y volver a correr 02.
//      Pantalla: CELLS (una línea), CELLS_TOTAL (con extensiones si existen) y LOTE_OK; el detalle (segundos por operación,
//      celdas por región, fronteras) va a MALLA_JSON bajo «malla_02», conservando el bloque «extensiones» que escribió 03.
// Base: bomba-malla + mallar-rotor-minimo-huelgos (verificadas en BombaNQ10).
double BASE_MM = {{BASE_MM}}, MIN_ROTOR_PCT = {{MIN_ROTOR_PCT}}, ALABES_PCT = {{ALABES_PCT}};
int PRISMAS = {{PRISMAS}};
double PRISMA_PCT = 10.0;               // espesor de la capa de prismas de la bomba, % de BASE_MM
double BASE_EXT = 2 * BASE_MM;           // extensiones: base doble, mismo espesor absoluto de prismas
String MALLA_JSON = "{{MALLA_JSON}}";
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
StringBuilder js = new StringBuilder("{\n    \"base_mm\": " + BASE_MM + ",\n    \"prismas_pct_base\": " + PRISMA_PCT + ",\n    \"segundos\": {");
int nOp = 0, nExt = 0;
for (Object o : mom.getObjects()) {
  if (!(o instanceof AutoMeshOperation)) continue;
  AutoMeshOperation op = (AutoMeshOperation) o;
  String n = op.getPresentationName();
  if (!n.startsWith("malla_")) continue;
  boolean ext = n.startsWith("malla_ext_");
  double base = ext ? BASE_EXT : BASE_MM;
  op.getDefaultValues().get(BaseSize.class).setValueAndUnits(base, mm);
  op.getDefaultValues().get(NumPrismLayers.class).setNumLayers(PRISMAS);
  op.getDefaultValues().get(PrismLayerStretching.class).setStretching(1.3);
  op.getDefaultValues().get(PrismThickness.class).setRelativeSize(PRISMA_PCT * BASE_MM / base);  // mismo espesor absoluto
  if (ext) nExt++;
  if (n.equals("malla_rotor")) {
    op.getDefaultValues().get(PartsMinimumSurfaceSize.class).getRelativeSize().setPercentage(MIN_ROTOR_PCT);
    SurfaceCustomMeshControl sc = (SurfaceCustomMeshControl) op.getCustomMeshControls().getObject("alabes");
    sc.getCustomValues().get(PartsTargetSurfaceSize.class).getRelativeSize().setPercentage(ALABES_PCT);
  }
  long t0 = System.currentTimeMillis();
  op.execute();
  js.append(nOp++ > 0 ? ", " : "").append("\"").append(n).append("\": ").append((System.currentTimeMillis() - t0) / 1000.0);
}
js.append("},\n    \"base_ext_mm\": ").append(nExt > 0 ? String.valueOf(BASE_EXT) : "null").append(",\n    \"celdas_region\": {");
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
js.append("},\n    \"celdas_total\": ").append(total).append(",\n    \"fronteras\": [");
int nb = 0;
for (Region r : sim.getRegionManager().getRegions())
  for (Boundary b : r.getBoundaryManager().getBoundaries())
    js.append(nb++ > 0 ? ", " : "").append("\"").append(r.getPresentationName()).append("/").append(b.getPresentationName().replace("\"", "'")).append("\"");
js.append("]\n  }");
// MALLA_JSON = {"malla_02": {...}, "celdas_total": N, "extensiones": {...de 03, si existe}}: se conserva lo de 03
class J {
  // valor objeto de "clave" (primera aparición) en s, con llaves emparejadas fuera de cadenas; null si no hay objeto
  String bloque(String s, String clave) {
    int i = s.indexOf("\"" + clave + "\":");
    if (i < 0) return null;
    int a = i + clave.length() + 3;
    while (a < s.length() && Character.isWhitespace(s.charAt(a))) a++;
    if (a >= s.length() || s.charAt(a) != '{') return null;
    int prof = 0; boolean cad = false;
    for (int k = a; k < s.length(); k++) {
      char ch = s.charAt(k);
      if (cad) { if (ch == '\\') k++; else if (ch == '"') cad = false; continue; }
      if (ch == '"') cad = true;
      else if (ch == '{') prof++;
      else if (ch == '}' && --prof == 0) return s.substring(a, k + 1);
    }
    return null;
  }
}
String extPrev = null;
try { extPrev = new J().bloque(new String(java.nio.file.Files.readAllBytes(java.nio.file.Paths.get(MALLA_JSON)), "UTF-8"), "extensiones"); }
catch (Exception e) { }
if (nExt == 0) extPrev = null;   // sin operaciones malla_ext_*: un bloque viejo de extensiones ya no vale
java.nio.file.Files.write(java.nio.file.Paths.get(MALLA_JSON), ("{\n  \"malla_02\": " + js + ",\n  \"celdas_total\": " + total
    + (extPrev != null ? ",\n  \"extensiones\": " + extPrev : "") + "\n}\n").getBytes("UTF-8"));
sim.println("CELLS" + cel);
sim.println("CELLS_TOTAL\t" + total + "\tBASE_MM\t" + BASE_MM + (nExt > 0 ? "\tBASE_EXT_MM\t" + BASE_EXT : ""));
sim.println("LOTE_OK 02 " + total + " celdas" + (nExt > 0 ? " (con " + nExt + " extensiones remalladas a base " + BASE_EXT + " mm)" : ""));
