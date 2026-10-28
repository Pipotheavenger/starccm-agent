// QUE: lote 03 · extensiones de entrada y salida creadas EN la simulación (sin CAD importado): mide la cara de entrada
//      (estator/Inflow) y la de salida (voluta/Outflow) con reportes (centro, normal hacia fuera, radio equivalente) y
//      levanta un cilindro coaxial a cada una: L_IN_D diámetros aguas arriba y L_OUT_D aguas abajo. Cada cilindro es
//      una región con su malla (mismos valores que 02) e interfaz con su vecina. Nombres: ext_entrada/{inlet,Wall,Outflow}
//      y ext_salida/{Inflow,Wall,outlet}. Requiere la malla de 02 (los reportes de cara necesitan malla).
// Base: macros de BombaNQ10 del 2026-10-28 (medir caras + cilindros + interfaces), verificadas con el solver.
double BASE_MM = {{BASE_MM}}, L_IN_D = {{L_IN_D}}, L_OUT_D = {{L_OUT_D}};
int PRISMAS = {{PRISMAS}};
Units um = sim.getUnitsManager().getUnits("m"), mm = sim.getUnitsManager().getUnits("mm");
ReportManager rm = sim.getReportManager();
FieldFunctionManager ffm = sim.getFieldFunctionManager();
RegionManager rgm = sim.getRegionManager();
String[] caras = {"estator/Inflow", "voluta/Outflow"};
String[] nombres = {"ext_entrada", "ext_salida"};
double[] largoD = {L_IN_D, L_OUT_D};
double[][] spec = new double[2][];
for (int k = 0; k < 2; k++) {
  String[] p = caras[k].split("/");
  Boundary b = rgm.getRegion(p[0]).getBoundaryManager().getBoundary(p[1]);
  double[] c = new double[3], n = new double[3];
  for (int i = 0; i < 3; i++) {
    UserFieldFunction f = ffm.createFieldFunction(); f.setFunctionName("tmp_c" + i); f.setDefinition("$${Position}[" + i + "]");
    AreaAverageReport a = rm.createReport(AreaAverageReport.class); a.setFieldFunction(f); a.getParts().setObjects(b);
    c[i] = a.getReportMonitorValue(); rm.removeObjects(a); ffm.removeObjects(f);
    UserFieldFunction g = ffm.createFieldFunction(); g.setFunctionName("tmp_n" + i); g.setDefinition("$${Area}[" + i + "]/mag($${Area})");
    AreaAverageReport a2 = rm.createReport(AreaAverageReport.class); a2.setFieldFunction(g); a2.getParts().setObjects(b);
    n[i] = a2.getReportMonitorValue(); rm.removeObjects(a2); ffm.removeObjects(g);
  }
  UserFieldFunction one = ffm.createFieldFunction(); one.setFunctionName("tmp_one"); one.setDefinition("1");
  SurfaceIntegralReport ar = rm.createReport(SurfaceIntegralReport.class); ar.setFieldFunction(one); ar.getParts().setObjects(b);
  double area = ar.getReportMonitorValue(); rm.removeObjects(ar); ffm.removeObjects(one);
  double nn = Math.sqrt(n[0]*n[0] + n[1]*n[1] + n[2]*n[2]);
  if (nn < 0.9) throw new RuntimeException("la cara " + caras[k] + " no es plana (|normal media| = " + nn + "): revisar a mano");
  double r = Math.sqrt(area / Math.PI), L = largoD[k] * 2 * r;
  spec[k] = new double[] {c[0], c[1], c[2], n[0]/nn, n[1]/nn, n[2]/nn, r, L};
  sim.println("FACE\t" + caras[k] + "\tc=" + c[0] + "," + c[1] + "," + c[2] + "\tn=" + n[0]/nn + "," + n[1]/nn + "," + n[2]/nn
              + "\tarea=" + area + "\tD=" + 2 * r + "\tL=" + L);
}
MeshPartFactory mpf = sim.get(MeshPartFactory.class);
List<GeometryPart> nuevas = new ArrayList<GeometryPart>();
for (int k = 0; k < 2; k++) {
  double[] s = spec[k];
  SimpleCylinderPart cyl = mpf.createNewCylinderPart(sim.get(SimulationPartManager.class));
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
MeshOperationManager mom = sim.get(MeshOperationManager.class);
for (GeometryPart part : nuevas) {
  AutoMeshOperation op = mom.createAutoMeshOperation(
      Arrays.asList("star.resurfacer.ResurfacerAutoMesher", "star.resurfacer.AutomaticSurfaceRepairAutoMesher", "star.dualmesher.DualAutoMesher", "star.prismmesher.PrismAutoMesher"),
      new ArrayList<GeometryPart>(Arrays.asList(part)));
  op.setPresentationName("malla_" + part.getPresentationName());
  op.getDefaultValues().get(BaseSize.class).setValueAndUnits(BASE_MM, mm);
  op.getDefaultValues().get(NumPrismLayers.class).setNumLayers(PRISMAS);
  op.getDefaultValues().get(PrismLayerStretching.class).setStretching(1.3);
  op.getDefaultValues().get(PrismThickness.class).setRelativeSize(10.0);
  long t0 = System.currentTimeMillis();
  op.execute();
  sim.println("MESH_SECONDS\tmalla_" + part.getPresentationName() + "\t" + (System.currentTimeMillis() - t0) / 1000.0);
}
// Tapas por distancia al punto de arranque (no por el nombre «Cylinder Surface N»): ~0 = la que toca la bomba,
// ~L/2 = la pared lateral, ~L = el extremo libre (inlet / outlet).
String[][] nuevosNombres = {{"Outflow", "Wall", "inlet"}, {"Inflow", "Wall", "outlet"}};
for (int k = 0; k < 2; k++) {
  Region reg = rgm.getRegion(nombres[k]);
  List<Boundary> bs = new ArrayList<Boundary>(reg.getBoundaryManager().getBoundaries());
  if (bs.size() != 3) throw new RuntimeException(nombres[k] + " tiene " + bs.size() + " fronteras (se esperaban 3)");
  final double[] dist = new double[3];
  for (int j = 0; j < 3; j++) {
    UserFieldFunction d = ffm.createFieldFunction(); d.setFunctionName("tmp_d");
    d.setDefinition("mag($${Position} - [" + spec[k][0] + "," + spec[k][1] + "," + spec[k][2] + "])");
    AreaAverageReport a = rm.createReport(AreaAverageReport.class); a.setFieldFunction(d); a.getParts().setObjects(bs.get(j));
    dist[j] = a.getReportMonitorValue(); rm.removeObjects(a); ffm.removeObjects(d);
  }
  Integer[] idx = {0, 1, 2};
  Arrays.sort(idx, new Comparator<Integer>() { public int compare(Integer x, Integer y) { return Double.compare(dist[x], dist[y]); } });
  for (int j = 0; j < 3; j++) bs.get(idx[j]).setPresentationName(nuevosNombres[k][j]);
}
Region est = rgm.getRegion("estator"), vol = rgm.getRegion("voluta"), ee = rgm.getRegion("ext_entrada"), es = rgm.getRegion("ext_salida");
sim.getInterfaceManager().createBoundaryInterface(ee.getBoundaryManager().getBoundary("Outflow"), est.getBoundaryManager().getBoundary("Inflow"), "int_ext_entrada");
sim.getInterfaceManager().createBoundaryInterface(vol.getBoundaryManager().getBoundary("Outflow"), es.getBoundaryManager().getBoundary("Inflow"), "int_ext_salida");
ElementCountReport ec = rm.createReport(ElementCountReport.class);
long total = 0;
for (Region r : rgm.getRegions()) {
  ec.getParts().setObjects(r);
  double c = ec.getReportMonitorValue(); total += (long) c;
  sim.println("CELLS\t" + r.getPresentationName() + "\t" + (long) c);
}
rm.removeObjects(ec);
for (Region r : rgm.getRegions()) if (r.getPresentationName().startsWith("ext_"))
  for (Boundary b : r.getBoundaryManager().getBoundaries()) sim.println("BOUNDARY\t" + r.getPresentationName() + "/" + b.getPresentationName());
sim.println("CELLS_TOTAL\t" + total);
sim.println("LOTE_OK 03 " + total + " celdas");
