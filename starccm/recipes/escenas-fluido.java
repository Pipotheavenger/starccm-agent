// QUE: escenas del FLUIDO como las de las plantillas NQ25Q159H91: en cada plano (plano_medio, plano_meridional) una
//      escena con TotalHead + líneas de corriente de la velocidad RELATIVA y otra con vectores de velocidad relativa;
//      las paredes van al 12 % de opacidad como referencia.
// VERSION: 19.06.009-R8 · FECHA: 2026-10-24 · ESTADO: verificado con el solver en una copia de cursocfturbo (4 escenas, PNG)
// 2026-10-30 (solo compilado, sin solver): idempotente (borra y recrea fluido_<plano>/vectores_<plano>; ya no «X 2») y
//      cámara según la normal de cada plano: el meridional salía de canto (cámara según el eje con un plano que contiene
//      el eje). Cámara = foco del resetCamera + normal·distancia; vertical = eje de giro en el meridional y una
//      perpendicular al eje en el medio (allí se mira a lo largo del eje). Setters de VisView (javadoc 2410).
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
class Esc {
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
      double d = Math.sqrt(Math.pow(p.get(0) - f.get(0), 2) + Math.pow(p.get(1) - f.get(1), 2) + Math.pow(p.get(2) - f.get(2), 2));
      if (!(d > 0)) d = 1.0;
      v.setPosition(new DoubleVector(new double[] {f.get(0) + d * nn[0], f.get(1) + d * nn[1], f.get(2) + d * nn[2]}));
      v.setViewUp(new DoubleVector(up));
      sim.println("CAMARA\t" + s.getPresentationName() + "\tnormal " + nn[0] + "," + nn[1] + "," + nn[2] + "\tvertical " + up[0] + "," + up[1] + "," + up[2]);
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
