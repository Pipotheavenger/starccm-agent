// QUE: rotor de CFturbo con cámaras laterales (CasingHub/SolidHub, CasingShroud/SolidShroud): con mínimo 10 % del base el remallador refina los huelgos a 0,45 mm y da 3,43 M celdas; con mínimo 25 % da 1,06 M (BombaNQ10, base 4,5 mm, 324 s). Remalla solo esa operación e interpola la solución. Verificado 2026-10-28
// VERSION: 19.06.009-R8
// FECHA: 2026-10-28
AutoMeshOperation op = (AutoMeshOperation) sim.get(MeshOperationManager.class).getObject("malla_rotor");
op.getDefaultValues().get(PartsMinimumSurfaceSize.class).getRelativeSize().setPercentage(25.0);
long t0 = System.currentTimeMillis();
op.execute();
sim.println("MESH_SECONDS rotor " + (System.currentTimeMillis() - t0) / 1000.0);
ElementCountReport rep = sim.getReportManager().createReport(ElementCountReport.class);
double tot = 0;
for (Region r : sim.getRegionManager().getRegions()) {
  rep.getParts().setObjects(r);
  double c = rep.getReportMonitorValue(); tot += c;
  sim.println("CELLS\t" + r.getPresentationName() + "\t" + c);
}
sim.getReportManager().removeObjects(rep);
sim.println("TOTAL\t" + tot);
