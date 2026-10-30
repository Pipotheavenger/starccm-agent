// QUE: escenas del FLUIDO como las de las plantillas NQ25Q159H91: en cada plano (plano_medio, plano_meridional) una
//      escena con TotalHead + líneas de corriente de la velocidad RELATIVA y otra con vectores de velocidad relativa;
//      las paredes van al 12 % de opacidad como referencia.
// VERSION: 19.06.009-R8 · FECHA: 2026-10-24 · ESTADO: verificado con el solver en una copia de cursocfturbo (4 escenas, PNG)
// 2026-10-30 (solo compilado, sin solver): idempotente (borra y recrea fluido_<plano>/vectores_<plano>; ya no «X 2») y
//      cámara según la normal de cada plano: el meridional salía de canto (cámara según el eje con un plano que contiene
//      el eje). Cámara = foco del resetCamera + normal·distancia; vertical = eje de giro en el meridional y una
//      perpendicular al eje en el medio (allí se mira a lo largo del eje). Setters de VisView (javadoc 2410).
// Ronda 2 (solo compilado): el encuadre ya no lo fijan las extensiones ext_* (la de salida mide 5 D y dejaba el rotor
//      diminuto): foco = origen del plano y distancia = 1,05·R/tan(ángulo/2), con R = máx. distancia de las fronteras
//      de la bomba (regiones no ext_*) a ese origen (MaxReport temporal tmp_cam_r, siempre borrado).
// Antes: exportar-superficies-ensight con PLANOS «auto» (crea los planos en su sitio) y reportes-euler-triangulos (crea
// TotalHead). Velocidad relativa = la que ve el rodete que gira (en las regiones fijas es la absoluta): es la que
// enseña cómo entra el agua a los álabes; la absoluta en el rotor está dominada por el giro (ω·r).
// Escenas: fluido_<plano> y vectores_<plano> (nombre exacto, sin « 1»). PNG: export_scene.
FieldFunctionManager ffm = sim.getFieldFunctionManager();
FieldFunction th = null, vrel = null;
for (String nm : new String[] {"TotalHead", "TotalPressure"}) { if (th == null) try { th = ffm.getFunction(nm); } catch (Exception e) { } }
for (String nm : new String[] {"RelativeVelocity", "CellRelativeVelocity", "Velocity"}) { if (vrel == null) try { vrel = ffm.getFunction(nm); } catch (Exception e) { } }
sim.println("CAMPOS\t" + th.getPresentationName() + "\t" + vrel.getPresentationName());
java.util.List<Boundary> walls = new java.util.ArrayList<Boundary>();
for (Region r : sim.getRegionManager().getRegions()) for (Boundary b : r.getBoundaryManager().getBoundaries()) if (b.getBoundaryType() instanceof WallBoundary) walls.add(b);
double[] axE = {0, 0, 1};
for (Region r : sim.getRegionManager().getRegions()) {
  try { Object rf = r.getValues().get(MotionSpecification.class).getReferenceFrame();
    if (rf instanceof RotatingReferenceFrame) { DoubleVector a = ((RotatingReferenceFrame) rf).getAxisDirection().getSIVector();
      double n = Math.sqrt(a.get(0) * a.get(0) + a.get(1) * a.get(1) + a.get(2) * a.get(2)); axE = new double[] {a.get(0) / n, a.get(1) / n, a.get(2) / n}; break; } }
  catch (Exception e) { }
}
final double[] AXE = axE;
// fronteras de la BOMBA (sin regiones ext_*): con ellas se mide el radio del encuadre (la extensión de salida mide 5 D)
final java.util.List<Boundary> BOMBA = new java.util.ArrayList<Boundary>();
for (Region r : sim.getRegionManager().getRegions()) if (!r.getPresentationName().startsWith("ext_")) BOMBA.addAll(r.getBoundaryManager().getBoundaries());
class Esc {
  // máxima distancia de las fronteras de la bomba al punto o (m); NaN si no se puede medir
  double radio(double[] o) {
    UserFieldFunction uf = null; MaxReport mx = null; double R = Double.NaN;
    try {
      for (FieldFunction f : ffm.getObjects()) if (f instanceof UserFieldFunction && f.getPresentationName().equals("tmp_cam_r")) uf = (UserFieldFunction) f;
      if (uf == null) { uf = ffm.createFieldFunction(); uf.setPresentationName("tmp_cam_r"); uf.setFunctionName("tmp_cam_r"); }
      uf.setDefinition("mag($$Position - [" + o[0] + ", " + o[1] + ", " + o[2] + "])");
      mx = sim.getReportManager().createReport(MaxReport.class); mx.setPresentationName("tmp_cam_r"); mx.setFieldFunction(uf); mx.getParts().setObjects(BOMBA);
      R = mx.getReportMonitorValue();
    } catch (Exception e) { sim.println("WARN\tradio del encuadre: " + e.getMessage()); }
    finally {
      try { if (mx != null) sim.getReportManager().removeObjects(mx); } catch (Exception e) { }
      try { if (uf != null) ffm.removeObjects(uf); } catch (Exception e) { }
    }
    return R;
  }
  Scene nueva(String nm) {
    java.util.Vector<Scene> viejas = new java.util.Vector<Scene>();
    for (Scene s : sim.getSceneManager().getScenes()) if (s.getPresentationName().matches(java.util.regex.Pattern.quote(nm) + "( \\d+)?")) viejas.add(s);
    if (!viejas.isEmpty()) sim.getSceneManager().deleteScenes(viejas);
    Scene s = sim.getSceneManager().createScene(nm); s.setPresentationName(nm); s.initializeAndWait(); return s; }
  // mira el plano de frente: posición = foco + normal·distancia; vertical = eje (o ⊥ al eje si la normal es el eje)
  void deFrente(Scene s, PlaneSection pl) {
    s.resetCamera(true);
    try {
      DoubleVector o = pl.getOrientation();
      double[] nn = {o.get(0), o.get(1), o.get(2)}; double m = Math.sqrt(nn[0] * nn[0] + nn[1] * nn[1] + nn[2] * nn[2]);
      for (int i = 0; i < 3; i++) nn[i] /= m;
      double c = nn[0] * AXE[0] + nn[1] * AXE[1] + nn[2] * AXE[2];
      double[] up;
      if (Math.abs(c) < 0.9) {  // plano que contiene el eje (meridional): el eje vertical, quitándole la parte según la normal
        up = new double[] {AXE[0] - c * nn[0], AXE[1] - c * nn[1], AXE[2] - c * nn[2]};
      } else {                  // plano ⊥ al eje (medio): vertical cualquiera ⊥ al eje
        double[] e = Math.abs(AXE[0]) < 0.9 ? new double[] {1, 0, 0} : new double[] {0, 1, 0};
        up = new double[] {AXE[1] * e[2] - AXE[2] * e[1], AXE[2] * e[0] - AXE[0] * e[2], AXE[0] * e[1] - AXE[1] * e[0]};
      }
      CurrentView v = s.getCurrentView();
      DoubleVector f = v.getFocalPoint(), p = v.getPosition();
      double[] fo = {f.get(0), f.get(1), f.get(2)};
      double d = Math.sqrt(Math.pow(p.get(0) - f.get(0), 2) + Math.pow(p.get(1) - f.get(1), 2) + Math.pow(p.get(2) - f.get(2), 2));
      // encuadre SIN extensiones: foco en el origen del plano (sobre el eje) y distancia para que quepa la esfera que
      // envuelve la bomba (rotor, voluta, estator); el resetCamera solo queda de reserva si no se puede medir
      String como = "resetCamera";
      try {
        DoubleVector og = pl.getOriginCoordinate().getSIValue();
        double[] o3 = {og.get(0), og.get(1), og.get(2)};
        double R = radio(o3), ang = 30.0;
        try { ang = v.getViewAngle().getValue(); } catch (Exception e) { }
        if (!(ang > 1 && ang < 170)) ang = 30.0;
        if (R > 0 && !Double.isInfinite(R)) { fo = o3; d = 1.05 * R / Math.tan(Math.toRadians(ang / 2)); como = "bomba R=" + R + " m"; }
      } catch (Exception e) { sim.println("WARN\tencuadre de " + s.getPresentationName() + ": " + e.getMessage()); }
      if (!(d > 0)) d = 1.0;
      v.setFocalPoint(new DoubleVector(fo));
      v.setPosition(new DoubleVector(new double[] {fo[0] + d * nn[0], fo[1] + d * nn[1], fo[2] + d * nn[2]}));
      v.setViewUp(new DoubleVector(up));
      sim.println("CAMARA\t" + s.getPresentationName() + "\tnormal " + nn[0] + "," + nn[1] + "," + nn[2] + "\tvertical " + up[0] + "," + up[1] + "," + up[2] + "\t" + como);
    } catch (Exception e) { sim.println("WARN\tcámara de " + s.getPresentationName() + ": " + e); }
  } }
Esc esc = new Esc();
int hechos = 0;
for (String pn : new String[] {"plano_medio", "plano_meridional"}) {
  PlaneSection pl = null;
  for (Object o : sim.getPartManager().getObjects()) if (o instanceof PlaneSection && ((PlaneSection) o).getPresentationName().equals(pn)) pl = (PlaneSection) o;
  if (pl == null) { sim.println("WARN\tfalta " + pn + ": corre antes exportar-superficies-ensight con PLANOS auto"); continue; }
  String tag = pn.replace("plano_", "");
  ConstrainedStreamPart sp = null;
  for (Object o : sim.getPartManager().getObjects()) if (o instanceof ConstrainedStreamPart && ((ConstrainedStreamPart) o).getPresentationName().equals("lineas_" + tag)) sp = (ConstrainedStreamPart) o;
  if (sp == null) {
    // 12×12 semillas: con 25×25 las líneas tapaban el color de TotalHead (verificado en cursocfturbo)
    sp = sim.getPartManager().createConstrainedStreamPart(new java.util.Vector<Object>(java.util.Arrays.asList(pl)), pl, vrel, 12, 12);
    sp.setPresentationName("lineas_" + tag);
  }
  Scene s1 = esc.nueva("fluido_" + tag);
  PartDisplayer pd = s1.getDisplayerManager().createPartDisplayer("paredes", -1, 4); pd.initialize();
  pd.setRepresentation(sim.getRepresentationManager().getDefaultFvRepresentation()); pd.getInputParts().setObjects(walls); pd.setOpacity(0.12);
  ScalarDisplayer sd = s1.getDisplayerManager().createScalarDisplayer("altura"); sd.initialize();
  sd.setRepresentation(sim.getRepresentationManager().getDefaultFvRepresentation()); sd.getInputParts().setObjects(pl); sd.getScalarDisplayQuantity().setFieldFunction(th);
  StreamDisplayer st = s1.getDisplayerManager().createStreamDisplayer("lineas"); st.initialize();
  st.getInputParts().setObjects(sp);
  try { st.getScalarDisplayQuantity().setFieldFunction(((PrimitiveFieldFunction) vrel).getMagnitudeFunction()); } catch (Exception e) { }  // color = |v relativa|
  esc.deFrente(s1, pl);
  Scene s2 = esc.nueva("vectores_" + tag);
  PartDisplayer pd2 = s2.getDisplayerManager().createPartDisplayer("paredes", -1, 4); pd2.initialize();
  pd2.setRepresentation(sim.getRepresentationManager().getDefaultFvRepresentation()); pd2.getInputParts().setObjects(walls); pd2.setOpacity(0.12);
  VectorDisplayer vd = s2.getDisplayerManager().createVectorDisplayer("vrel"); vd.initialize();
  vd.setRepresentation(sim.getRepresentationManager().getDefaultFvRepresentation()); vd.getInputParts().setObjects(pl);
  vd.getVectorDisplayQuantity().setFieldFunction(vrel);
  vd.getGlyphSettings().setRelativeToModelLength(6.0); vd.getGlyphSettings().setSpacingMode(0); vd.getGlyphSettings().getGeometricSpacing().setOnRatio(6);
  esc.deFrente(s2, pl);
  hechos++;
}
for (Scene s : sim.getSceneManager().getScenes()) sim.println("SCENE\t" + s.getPresentationName());
sim.println("ESCENAS_FLUIDO\t" + hechos + " planos");
