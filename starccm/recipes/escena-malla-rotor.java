// QUE: escena de malla superficial del impulsor (fronteras del rotor sin interfaces ni shroud, para ver álabes y hub), PNG en batch
// VERSION: 19.06.009-R8
// FECHA: 2026-10-23 · VERIFICADO contra el solver real (cases/cursocfturbo/images/malla.png)
// Idempotente: si ya existe una escena «malla…» la reutiliza. Las fronteras de interfaz son DirectBoundaryInterfaceBoundary.
// 2026-10-30: la escena nueva se llama «malla» exacto (antes «malla 1»; el PNG sale igual: malla.png).
Region r = sim.getRegionManager().getRegion("rotor");
Scene sc = null;
for (Scene s : sim.getSceneManager().getScenes()) if (s.getPresentationName().startsWith("malla")) sc = s;
if (sc == null) {
  sc = sim.getSceneManager().createScene("malla");
  sc.setPresentationName("malla");
  sc.initializeAndWait();
  PartDisplayer pd = sc.getDisplayerManager().createPartDisplayer("Malla", -1, 1);
  pd.initialize();
  pd.setRepresentation(sim.getRepresentationManager().getDefaultFvRepresentation());
  List<Boundary> bl = new ArrayList<Boundary>();
  for (Boundary b : r.getBoundaryManager().getBoundaries()) if (!(b instanceof DirectBoundaryInterfaceBoundary) && !b.getPresentationName().equals("Shroud")) bl.add(b);
  pd.getInputParts().setObjects(bl);
  pd.setMesh(true); pd.setSurface(true);
  sc.resetCamera(true);
}
sim.println("SCENE " + sc.getPresentationName());
