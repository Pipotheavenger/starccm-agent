// Exporta fronteras (malla superficial + campos en los vértices) a EnSight Gold (.case) para el visor 3D de ui/.
// STAR-CCM+ 2410 · 2026-10-23 · ESTADO: compila con javac; por verificar contra el solver real.
// Parámetros del cuerpo: PATTERN (regex sobre "region/frontera"), FUNCS (nombres internos de field functions;
// los vectores se exportan como magnitud), OUT (ruta .case). Firma usada (javadoc 2410):
// ImportManager.export(String, Collection<Region>, Collection<Boundary>, Collection<Part>, Collection<PartSurface>,
//                      Collection<FieldFunction>, boolean appendToFile, boolean dataAtVerts)
java.util.regex.Pattern pat = java.util.regex.Pattern.compile("PATTERN", java.util.regex.Pattern.CASE_INSENSITIVE);
java.util.Vector<Region> regs = new java.util.Vector<Region>();
java.util.Vector<Boundary> bnds = new java.util.Vector<Boundary>();
for (Region r : sim.getRegionManager().getRegions())
  for (Boundary b : r.getBoundaryManager().getBoundaries()) {
    // las fronteras de interfaz (rotor/estator) duplican superficies internas: fuera del visor
    if (b instanceof DirectBoundaryInterfaceBoundary || b.getPresentationName().contains("[")) continue;
    String full = r.getPresentationName() + "/" + b.getPresentationName();
    if (pat.matcher(full).find()) { bnds.add(b); sim.println("BOUNDARY\t" + full); }
  }
if (bnds.isEmpty()) throw new RuntimeException("Ninguna frontera coincide con PATTERN");
java.util.Vector<FieldFunction> ffs = new java.util.Vector<FieldFunction>();
for (String n : "FUNCS".split(",")) {
  n = n.trim(); if (n.isEmpty()) continue;
  FieldFunction f;
  try { f = sim.getFieldFunctionManager().getFunction(n); }
  catch (Exception e) { sim.println("WARN\tno existe la field function " + n); continue; }
  // vector (Velocity, WallShearStress...) -> su magnitud, que es lo que pinta el visor
  try { if (f.getType().toString().toLowerCase().contains("vector")) f = f.getMagnitudeFunction(); }
  catch (Exception e) { }
  ffs.add(f); sim.println("FUNC\t" + f.getPresentationName());
}
sim.getImportManager().export(resolvePath("OUT"), regs, bnds, new java.util.Vector<Part>(), new java.util.Vector<PartSurface>(), ffs, false, true);
sim.println("CASE OUT");
