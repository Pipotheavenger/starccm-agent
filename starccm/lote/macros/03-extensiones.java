// QUE: lote 03 · extensiones de entrada y salida creadas EN la simulación (sin CAD importado): mide la cara de entrada
//      (estator/Inflow) y la de salida (voluta/Outflow) con reportes (centro, normal hacia fuera, radio equivalente) y
//      levanta un cilindro coaxial a cada una: L_IN_D diámetros aguas arriba y L_OUT_D aguas abajo. Cada cilindro es
//      una región con su malla e interfaz con su vecina. Nombres: ext_entrada/{inlet,Wall,Outflow}
//      y ext_salida/{Inflow,Wall,outlet}. Requiere la malla de 02 (los reportes de cara necesitan malla).
//      Malla de las extensiones más gruesa: base BASE_EXT_MM (el orquestador pasa 2×BASE_MM) con los MISMOS prismas
//      en pared que 02 (mismas capas y estiramiento, y el mismo espesor absoluto: 10 % de BASE_MM).
//      Idempotente: si las extensiones ya están completas solo les pone el base y las vuelve a mallar; si quedaron a
//      medias (o con nombres «X 2») las borra y las rehace. Reportes y funciones tmp_* siempre se borran (finally).
//      Pantalla: CELLS, CELLS_TOTAL (con extensiones) y LOTE_OK; el detalle (caras, D, L, celdas) va a MALLA_JSON.
// Base: macros de BombaNQ10 del 2026-10-28 (medir caras + cilindros + interfaces), verificadas con el solver.
double BASE_MM = {{BASE_MM}}, L_IN_D = {{L_IN_D}}, L_OUT_D = {{L_OUT_D}};
double BASE_EXT_MM = {{BASE_EXT_MM}};
int PRISMAS = {{PRISMAS}};
String MALLA_JSON = "{{MALLA_JSON}}";
Units um = sim.getUnitsManager().getUnits("m"), mm = sim.getUnitsManager().getUnits("mm");
ReportManager rm = sim.getReportManager();
FieldFunctionManager ffm = sim.getFieldFunctionManager();
RegionManager rgm = sim.getRegionManager();
MeshOperationManager mom = sim.get(MeshOperationManager.class);
SimulationPartManager spm = sim.get(SimulationPartManager.class);
String[] caras = {"estator/Inflow", "voluta/Outflow"};
String[] nombres = {"ext_entrada", "ext_salida"};
String[][] nuevosNombres = {{"Outflow", "Wall", "inlet"}, {"Inflow", "Wall", "outlet"}};
double[] largoD = {L_IN_D, L_OUT_D};
List<Report> tmpR = new ArrayList<Report>();
List<FieldFunction> tmpF = new ArrayList<FieldFunction>();
class T {
  UserFieldFunction ff(String nm, String def) {
    UserFieldFunction f = ffm.createFieldFunction(); f.setPresentationName(nm); f.setFunctionName(nm); f.setDefinition(def); tmpF.add(f); return f; }
  double avg(FieldFunction f, Boundary b) {
    AreaAverageReport a = rm.createReport(AreaAverageReport.class); tmpR.add(a); a.setFieldFunction(f); a.getParts().setObjects(b); return a.getReportMonitorValue(); }
  double integ(FieldFunction f, Boundary b) {
    SurfaceIntegralReport a = rm.createReport(SurfaceIntegralReport.class); tmpR.add(a); a.setFieldFunction(f); a.getParts().setObjects(b); return a.getReportMonitorValue(); }
  void malla(AutoMeshOperation op) {
    op.getDefaultValues().get(BaseSize.class).setValueAndUnits(BASE_EXT_MM, mm);
    op.getDefaultValues().get(NumPrismLayers.class).setNumLayers(PRISMAS);
    op.getDefaultValues().get(PrismLayerStretching.class).setStretching(1.3);
    op.getDefaultValues().get(PrismThickness.class).setRelativeSize(10.0 * BASE_MM / BASE_EXT_MM);  // = 10 % de BASE_MM
  }
}
T t = new T();
StringBuilder js = new StringBuilder("{\n  \"base_ext_mm\": " + BASE_EXT_MM + ",\n  \"caras\": {");
StringBuilder resumen = new StringBuilder();
long total = 0;
try {
  // restos de una corrida cortada: funciones tmp_* sueltas
  List<FieldFunction> viejas = new ArrayList<FieldFunction>();
  for (FieldFunction f : ffm.getObjects()) if (f instanceof UserFieldFunction && f.getPresentationName().startsWith("tmp_")) viejas.add(f);
  if (!viejas.isEmpty()) ffm.removeObjects(viejas);
  // ¿extensiones completas de una corrida anterior?
  boolean completas = true;
  for (int k = 0; k < 2; k++) {
    if (!rgm.has(nombres[k]) || !mom.has("malla_" + nombres[k])) { completas = false; break; }
    for (String bn : nuevosNombres[k]) if (!rgm.getRegion(nombres[k]).getBoundaryManager().has(bn)) completas = false;
  }
  if (completas) {
    for (int k = 0; k < 2; k++) {
      AutoMeshOperation op = (AutoMeshOperation) mom.getObject("malla_" + nombres[k]);
      t.malla(op); op.execute();
    }
    js.append("\"reusadas\": true");
    resumen.append(" reusadas");
  } else {
    // limpiar lo que haya a medias: interfaces, operaciones, regiones y partes ext_*
    java.util.Vector<Interface> vi = new java.util.Vector<Interface>();
    for (Interface i : sim.getInterfaceManager().getObjects()) if (i.getPresentationName().startsWith("int_ext_")) vi.add(i);
    if (!vi.isEmpty()) sim.getInterfaceManager().deleteInterfaces(vi);
    List<MeshOperation> vo = new ArrayList<MeshOperation>();
    for (MeshOperation o : mom.getObjects()) if (o.getPresentationName().startsWith("malla_ext_")) vo.add(o);
    if (!vo.isEmpty()) mom.removeObjects(vo);
    List<Region> vr = new ArrayList<Region>();
    for (Region r : rgm.getRegions()) if (r.getPresentationName().startsWith("ext_")) vr.add(r);
    if (!vr.isEmpty()) rgm.removeRegions(vr);
    List<GeometryPart> vp = new ArrayList<GeometryPart>();
    for (GeometryPart p : spm.getParts()) if (p.getPresentationName().startsWith("ext_")) vp.add(p);
    if (!vp.isEmpty()) spm.removeParts(vp);
    double[][] spec = new double[2][];
    for (int k = 0; k < 2; k++) {
      String[] p = caras[k].split("/");
      Boundary b = rgm.getRegion(p[0]).getBoundaryManager().getBoundary(p[1]);
      double[] c = new double[3], n = new double[3];
      for (int i = 0; i < 3; i++) {
        c[i] = t.avg(t.ff("tmp_c" + k + i, "$${Position}[" + i + "]"), b);
        n[i] = t.avg(t.ff("tmp_n" + k + i, "$${Area}[" + i + "]/mag($${Area})"), b);
      }
      double area = t.integ(t.ff("tmp_one" + k, "1"), b);
      double nn = Math.sqrt(n[0]*n[0] + n[1]*n[1] + n[2]*n[2]);
      if (nn < 0.9) throw new RuntimeException("la cara " + caras[k] + " no es plana (|normal media| = " + nn + "): revisar a mano");
      double r = Math.sqrt(area / Math.PI), L = largoD[k] * 2 * r;
      spec[k] = new double[] {c[0], c[1], c[2], n[0]/nn, n[1]/nn, n[2]/nn, r, L};
      js.append(k > 0 ? ", " : "").append("\"").append(caras[k]).append("\": {\"c\": [").append(c[0]).append(", ").append(c[1]).append(", ").append(c[2])
        .append("], \"n\": [").append(n[0]/nn).append(", ").append(n[1]/nn).append(", ").append(n[2]/nn).append("], \"area\": ").append(area)
        .append(", \"D\": ").append(2 * r).append(", \"L\": ").append(L).append("}");
      resumen.append(" ").append(nombres[k]).append(" D=").append(String.format(java.util.Locale.ROOT, "%.4f", 2 * r)).append(" L=").append(String.format(java.util.Locale.ROOT, "%.3f", L));
    }
    MeshPartFactory mpf = sim.get(MeshPartFactory.class);
    List<GeometryPart> nuevas = new ArrayList<GeometryPart>();
    for (int k = 0; k < 2; k++) {
      double[] s = spec[k];
      SimpleCylinderPart cyl = mpf.createNewCylinderPart(spm);
      cyl.setCoordinateSystem(sim.getCoordinateSystemManager().getLabCoordinateSystem());
      cyl.getStartCoordinate().setCoordinate(um, um, um, new DoubleVector(new double[] {s[0], s[1], s[2]}));
      cyl.getEndCoordinate().setCoordinate(um, um, um, new DoubleVector(new double[] {s[0] + s[7]*s[3], s[1] + s[7]*s[4], s[2] + s[7]*s[5]}));
      cyl.getRadius().setValueAndUnits(s[6], um);
      cyl.getTessellationDensityOption().setSelected(TessellationDensityOption.Type.FINE);
      cyl.rebuildSimpleShapePart();
      cyl.setPresentationName(nombres[k]);
      cyl.getPartSurfaceManager().splitPartSurfacesByAngle(new ArrayList<PartSurface>(cyl.getPartSurfaces()), 89.0);
      nuevas.add(cyl);
    }
    rgm.newRegionsFromParts(nuevas, "OneRegionPerPart", null, "OneBoundaryPerPartSurface", null, false);
    for (GeometryPart part : nuevas) {
      AutoMeshOperation op = mom.createAutoMeshOperation(
          Arrays.asList("star.resurfacer.ResurfacerAutoMesher", "star.resurfacer.AutomaticSurfaceRepairAutoMesher", "star.dualmesher.DualAutoMesher", "star.prismmesher.PrismAutoMesher"),
          new ArrayList<GeometryPart>(Arrays.asList(part)));
      op.setPresentationName("malla_" + part.getPresentationName());
      t.malla(op);
      op.execute();
    }
    // Tapas por distancia al punto de arranque (no por el nombre «Cylinder Surface N»): ~0 = la que toca la bomba,
    // ~L/2 = la pared lateral, ~L = el extremo libre (inlet / outlet).
    for (int k = 0; k < 2; k++) {
      Region reg = rgm.getRegion(nombres[k]);
      List<Boundary> bs = new ArrayList<Boundary>(reg.getBoundaryManager().getBoundaries());
      if (bs.size() != 3) throw new RuntimeException(nombres[k] + " tiene " + bs.size() + " fronteras (se esperaban 3)");
      final double[] dist = new double[3];
      for (int j = 0; j < 3; j++)
        dist[j] = t.avg(t.ff("tmp_d" + k + j, "mag($${Position} - [" + spec[k][0] + "," + spec[k][1] + "," + spec[k][2] + "])"), bs.get(j));
      Integer[] idx = {0, 1, 2};
      Arrays.sort(idx, new Comparator<Integer>() { public int compare(Integer x, Integer y) { return Double.compare(dist[x], dist[y]); } });
      for (int j = 0; j < 3; j++) bs.get(idx[j]).setPresentationName(nuevosNombres[k][j]);
    }
  }
  js.append("},\n");
  // interfaces (solo si faltan)
  boolean hayE = false, hayS = false;
  for (Interface i : sim.getInterfaceManager().getObjects()) {
    if (i.getPresentationName().matches("int_ext_entrada( \\d+)?")) hayE = true;
    if (i.getPresentationName().matches("int_ext_salida( \\d+)?")) hayS = true;
  }
  Region est = rgm.getRegion("estator"), vol = rgm.getRegion("voluta"), ee = rgm.getRegion("ext_entrada"), es = rgm.getRegion("ext_salida");
  if (!hayE) sim.getInterfaceManager().createBoundaryInterface(ee.getBoundaryManager().getBoundary("Outflow"), est.getBoundaryManager().getBoundary("Inflow"), "int_ext_entrada");
  if (!hayS) sim.getInterfaceManager().createBoundaryInterface(vol.getBoundaryManager().getBoundary("Outflow"), es.getBoundaryManager().getBoundary("Inflow"), "int_ext_salida");
  ElementCountReport ec = rm.createReport(ElementCountReport.class); tmpR.add(ec);
  StringBuilder cel = new StringBuilder(), celj = new StringBuilder();
  for (Region r : rgm.getRegions()) {
    ec.getParts().setObjects(r);
    long c = (long) ec.getReportMonitorValue(); total += c;
    cel.append(" ").append(r.getPresentationName()).append("=").append(c);
    celj.append(celj.length() > 0 ? ", " : "").append("\"").append(r.getPresentationName()).append("\": ").append(c);
  }
  js.append("  \"celdas_region\": {").append(celj).append("},\n  \"celdas_total\": ").append(total).append(",\n  \"fronteras_ext\": [");
  int nb = 0;
  for (Region r : rgm.getRegions()) if (r.getPresentationName().startsWith("ext_"))
    for (Boundary b : r.getBoundaryManager().getBoundaries()) js.append(nb++ > 0 ? ", " : "").append("\"").append(r.getPresentationName()).append("/").append(b.getPresentationName()).append("\"");
  js.append("]");
  sim.println("CELLS" + cel);
} finally {
  try { if (!tmpR.isEmpty()) rm.removeObjects(tmpR); } catch (Exception e) { }
  try { if (!tmpF.isEmpty()) ffm.removeObjects(tmpF); } catch (Exception e) { }
}
// malla.json: el detalle de 02 queda dentro como «malla_02»
String previo = "null";
try { String s0 = new String(java.nio.file.Files.readAllBytes(java.nio.file.Paths.get(MALLA_JSON)), "UTF-8").trim();
      if (s0.startsWith("{") && s0.endsWith("}") && !s0.contains("\"extensiones\"")) previo = s0;
      else if (s0.contains("\"malla_02\": {")) previo = s0.substring(s0.indexOf("\"malla_02\": ") + 12, s0.lastIndexOf("}")).trim(); } catch (Exception e) { }
java.nio.file.Files.write(java.nio.file.Paths.get(MALLA_JSON), ("{\n  \"extensiones\": " + js.toString().replace("\n", "\n  ") + "\n  },\n  \"celdas_total\": " + total + ",\n  \"malla_02\": " + previo + "\n}\n").getBytes("UTF-8"));
sim.println("CELLS_TOTAL\t" + total);
sim.println("LOTE_OK 03 " + total + " celdas" + resumen);
