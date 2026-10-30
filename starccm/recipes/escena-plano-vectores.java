// QUE: escena de plano de corte (plano_medio, a media salida del rotor) con |velocidad| y vectores encima, exportable a PNG en batch
// VERSION: 19.06.009-R8
// FECHA: 2026-10-23 · VERIFICADO contra el solver real (cases/cursocfturbo/images/plano_vectores.png)
// 2026-10-30 (solo compilado, sin solver): idempotente (borra y recrea «plano_vectores», nombre exacto) con la cámara
//      según la normal del plano; y si ya existe «vectores_medio» (escenas-fluido: vectores de velocidad relativa en el
//      mismo plano) no crea otra escena de vectores en el plano medio: deja una sola (la del lote) y lo dice con OMITIDA.
// Ronda 2 (solo compilado): encuadre sin las extensiones ext_* (foco = origen del plano, distancia con el radio de la
//      bomba medido con un MaxReport temporal tmp_cam_r, siempre borrado); resetCamera solo de reserva.
// Reusa el plano «plano_medio» si existe (lo crea bomba-escenas.java); si no, lo crea sobre todas las regiones.
// Vectores: longitud relativa al modelo en % (1.0 = invisible; 6.0 se ve bien), espaciado GEOMETRIC (setSpacingMode(0);
// 1 = UNIFORM) con onRatio 6 (una flecha de cada 6 celdas). PartManager no tiene getParts(): usar getObjects().
Scene yaHay = null;
for (Scene s : sim.getSceneManager().getScenes()) if (s.getPresentationName().matches("vectores_medio( \\d+)?")) yaHay = s;
if (yaHay != null) {
  java.util.Vector<Scene> viejas = new java.util.Vector<Scene>();
  for (Scene s : sim.getSceneManager().getScenes()) if (s.getPresentationName().matches("plano_vectores( \\d+)?")) viejas.add(s);
  if (!viejas.isEmpty()) sim.getSceneManager().deleteScenes(viejas);
  sim.println("SCENE " + yaHay.getPresentationName() + "\tOMITIDA plano_vectores (duplicaría los vectores del plano medio)");
} else {
List<Region> regs = new ArrayList<Region>(sim.getRegionManager().getRegions());
PlaneSection plane = null;
for (Object o : sim.getPartManager().getObjects()) if (o instanceof PlaneSection && ((PlaneSection) o).getPresentationName().equals("plano_medio")) plane = (PlaneSection) o;
if (plane == null) throw new RuntimeException("falta plano_medio: corre antes exportar-superficies-ensight con PLANOS auto (la cota fija de cursocfturbo corta mal otras bombas)");
java.util.Vector<Scene> viejas = new java.util.Vector<Scene>();
for (Scene s : sim.getSceneManager().getScenes()) if (s.getPresentationName().matches("plano_vectores( \\d+)?")) viejas.add(s);
if (!viejas.isEmpty()) sim.getSceneManager().deleteScenes(viejas);
Scene sc = sim.getSceneManager().createScene("plano_vectores"); sc.setPresentationName("plano_vectores"); sc.initializeAndWait();
ScalarDisplayer sd = sc.getDisplayerManager().createScalarDisplayer("v"); sd.initialize();
sd.setRepresentation(sim.getRepresentationManager().getDefaultFvRepresentation());
sd.getInputParts().setObjects(plane);
sd.getScalarDisplayQuantity().setFieldFunction(((PrimitiveFieldFunction) sim.getFieldFunctionManager().getFunction("Velocity")).getMagnitudeFunction());
VectorDisplayer vd = sc.getDisplayerManager().createVectorDisplayer("vectores"); vd.initialize();
vd.setRepresentation(sim.getRepresentationManager().getDefaultFvRepresentation());
vd.getInputParts().setObjects(plane);
vd.getVectorDisplayQuantity().setFieldFunction(sim.getFieldFunctionManager().getFunction("Velocity"));
vd.setColorMode(VectorDisplayer.COLOR_USER_DEFINED);
vd.setSpacingMode(0);                                   // GEOMETRIC
GlyphSettings g = vd.getGlyphSettings();
g.setRelativeToModelLength(6.0);                        // % del tamaño del modelo
g.getGeometricSpacing().setOnRatio(6);
sc.resetCamera(true);
try {  // de frente al plano (normal = eje en el plano medio); vertical ⊥ a la normal
  DoubleVector o = plane.getOrientation();
  double[] nn = {o.get(0), o.get(1), o.get(2)}; double m = Math.sqrt(nn[0] * nn[0] + nn[1] * nn[1] + nn[2] * nn[2]);
  for (int i = 0; i < 3; i++) nn[i] /= m;
  double[] e = Math.abs(nn[0]) < 0.9 ? new double[] {1, 0, 0} : new double[] {0, 1, 0};
  double[] up = {nn[1] * e[2] - nn[2] * e[1], nn[2] * e[0] - nn[0] * e[2], nn[0] * e[1] - nn[1] * e[0]};
  CurrentView v = sc.getCurrentView();
  DoubleVector f = v.getFocalPoint(), p = v.getPosition();
  double[] fo = {f.get(0), f.get(1), f.get(2)};
  double d = Math.sqrt(Math.pow(p.get(0) - f.get(0), 2) + Math.pow(p.get(1) - f.get(1), 2) + Math.pow(p.get(2) - f.get(2), 2));
  // encuadre SIN extensiones ext_* (la de salida mide 5 D): foco = origen del plano, distancia para que quepa la esfera
  // que envuelve las fronteras de la bomba alrededor de ese origen (MaxReport temporal, siempre borrado)
  String como = "resetCamera";
  UserFieldFunction uf = null; MaxReport mx = null;
  try {
    DoubleVector og = plane.getOriginCoordinate().getSIValue();
    double[] o3 = {og.get(0), og.get(1), og.get(2)};
    List<Boundary> bomba = new ArrayList<Boundary>();
    for (Region r : regs) if (!r.getPresentationName().startsWith("ext_")) bomba.addAll(r.getBoundaryManager().getBoundaries());
    FieldFunctionManager ffmC = sim.getFieldFunctionManager();
    for (FieldFunction ff : ffmC.getObjects()) if (ff instanceof UserFieldFunction && ff.getPresentationName().equals("tmp_cam_r")) uf = (UserFieldFunction) ff;
    if (uf == null) { uf = ffmC.createFieldFunction(); uf.setPresentationName("tmp_cam_r"); uf.setFunctionName("tmp_cam_r"); }
    uf.setDefinition("mag($$Position - [" + o3[0] + ", " + o3[1] + ", " + o3[2] + "])");
    mx = sim.getReportManager().createReport(MaxReport.class); mx.setPresentationName("tmp_cam_r"); mx.setFieldFunction(uf); mx.getParts().setObjects(bomba);
    double R = mx.getReportMonitorValue(), ang = 30.0;
    try { ang = v.getViewAngle().getValue(); } catch (Exception e2) { }
    if (!(ang > 1 && ang < 170)) ang = 30.0;
    if (R > 0 && !Double.isInfinite(R)) { fo = o3; d = 1.05 * R / Math.tan(Math.toRadians(ang / 2)); como = "bomba R=" + R + " m"; }
  } catch (Exception e2) { sim.println("WARN\tencuadre: " + e2.getMessage()); }
  finally {
    try { if (mx != null) sim.getReportManager().removeObjects(mx); } catch (Exception e2) { }
    try { if (uf != null) sim.getFieldFunctionManager().removeObjects(uf); } catch (Exception e2) { }
  }
  if (!(d > 0)) d = 1.0;
  v.setFocalPoint(new DoubleVector(fo));
  v.setPosition(new DoubleVector(new double[] {fo[0] + d * nn[0], fo[1] + d * nn[1], fo[2] + d * nn[2]}));
  v.setViewUp(new DoubleVector(up));
  sim.println("CAMARA\tplano_vectores\t" + como);
} catch (Exception ex) { sim.println("WARN\tcámara: " + ex.getMessage()); }
sim.println("SCENE " + sc.getPresentationName() + " vectores " + vd.getPresentationName() + " " + g.getSpacingModeEnum() + " rel " + g.getRelativeToModelLength());
}
