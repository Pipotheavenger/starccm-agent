// QUE: exportar la geometría recién importada (partes CAD, SIN malla) a STL para el visor 3D: un .stl por parte
// VERSION: 19.06.009-R8 · FECHA: 2026-10-24 · ESTADO: compila con javac; por verificar con el solver (ver CLAUDE.md)
// OUT: carpeta destino (cases/<caso>/surfaces/_raw/geometria). El visor la convierte sola (cada «solid» = una cara).
// ImportManager.export (EnSight) NO sirve antes de mallar: «There is no volume mesh». MeshPart.exportStlPart sí.
String out = resolvePath("OUT");
new java.io.File(out).mkdirs();
for (java.io.File f : new java.io.File(out).listFiles()) if (f.getName().endsWith(".stl")) f.delete();  // sin restos de otra exportación
StringBuilder meta = new StringBuilder();
int i = 0, tris = 0;
for (GeometryPart gp : sim.get(SimulationPartManager.class).getLeafParts()) {
  if (!(gp instanceof MeshPart)) { sim.println("WARN\tparte sin teselado: " + gp.getPresentationName()); continue; }
  MeshPart mp = (MeshPart) gp;
  String safe = gp.getPresentationName().replaceAll("[^A-Za-z0-9_\\-]+", "_");
  String fn = String.format("%02d_%s.stl", i++, safe);
  mp.exportStlPart(out + java.io.File.separator + fn, false);  // ASCII: un «solid <cara>» por superficie de la parte
  tris += mp.getTriangleCount();
  meta.append("STLPART\t" + fn + "\t" + gp.getPresentationName() + "\n");
  sim.println("STLPART\t" + fn + "\t" + gp.getPresentationName() + "\t" + mp.getTriangleCount() + " triángulos\t" + gp.getPartSurfaces().size() + " superficies");
}
for (Region r : sim.getRegionManager().getRegions()) {  // si ya hay marcos rotatorios, el visor gira esas partes sobre su eje
  try {
    Object rf = r.getValues().get(MotionSpecification.class).getReferenceFrame();
    if (rf instanceof RotatingReferenceFrame) {
      RotatingReferenceFrame f = (RotatingReferenceFrame) rf;
      DoubleVector ax = f.getAxisDirection().getSIVector(), og = f.getAxisOrigin().getSIVector();
      meta.append("ROTFRAME\t" + r.getPresentationName() + "\t" + ax.get(0) + "," + ax.get(1) + "," + ax.get(2) + "\t" + og.get(0) + "," + og.get(1) + "," + og.get(2) + "\t" + (f.getRotationRate().getSIValue() * 60.0 / (2.0 * Math.PI)) + "\n");
    }
  } catch (Exception e) { }
}
java.nio.file.Files.write(java.nio.file.Paths.get(out, "geometria.meta"), meta.toString().getBytes("UTF-8"));
sim.println("STL_OK\t" + i + " partes\t" + tris + " triángulos\t" + out);
