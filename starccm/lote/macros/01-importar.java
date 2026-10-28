// QUE: lote 01 · importa los 3 STEP de CFturbo (caras con nombre), una región por parte (estator/rotor/voluta), fronteras
//      renombradas por el sufijo tras el último '-', interfaces int_entrada (estator→rotor) e int_salida (rotor→voluta).
// Base: bomba-importar + bomba-regiones + bomba-interfaces (verificadas en cursocfturbo y BombaNQ10).
PartImportManager pim = sim.get(PartImportManager.class);
for (String f : new String[] {"{{CO1}}", "{{CO2}}", "{{CO3}}"})
  pim.importCadPart(f, "SharpEdges", 30.0, 2, 1.0E-5);
Collection<GeometryPart> parts = sim.get(SimulationPartManager.class).getParts();
sim.getRegionManager().newRegionsFromParts(new ArrayList<GeometryPart>(parts), "OneRegionPerPart", null, "OneBoundaryPerPartSurface", null, false);
for (Region r : sim.getRegionManager().getRegions()) {
  String n = r.getPresentationName();
  if (n.contains("Stator")) r.setPresentationName("estator");
  else if (n.contains("Impeller")) r.setPresentationName("rotor");
  else if (n.contains("Volute")) r.setPresentationName("voluta");
  for (Boundary b : new ArrayList<Boundary>(r.getBoundaryManager().getBoundaries())) {
    String bn = b.getPresentationName();
    int i = bn.lastIndexOf('-');
    if (i >= 0) b.setPresentationName(bn.substring(i + 1));
  }
}
Region est = sim.getRegionManager().getRegion("estator"), rot = sim.getRegionManager().getRegion("rotor"), vol = sim.getRegionManager().getRegion("voluta");
sim.getInterfaceManager().createBoundaryInterface(est.getBoundaryManager().getBoundary("Outflow"), rot.getBoundaryManager().getBoundary("Inflow"), "int_entrada");
sim.getInterfaceManager().createBoundaryInterface(rot.getBoundaryManager().getBoundary("Outflow"), vol.getBoundaryManager().getBoundary("Inflow"), "int_salida");
for (Region r : sim.getRegionManager().getRegions())
  for (Boundary b : r.getBoundaryManager().getBoundaries()) sim.println("BOUNDARY\t" + r.getPresentationName() + "/" + b.getPresentationName());
for (Interface i : sim.getInterfaceManager().getObjects()) sim.println("INTERFACE\t" + i.getPresentationName());
sim.println("LOTE_OK 01 " + sim.getRegionManager().getRegions().size() + " regiones");
