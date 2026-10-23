// QUE: escenas: presión en álabes, velocidad en plano z = 30 mm, y+ en paredes del rotor
// VERSION: 19.06.009-R8
// FECHA: 2026-10-23

Region rot = sim.getRegionManager().getRegion("rotor");
List<Boundary> blades = new ArrayList<Boundary>();
for (String n : new String[] {"BladeSS", "BladePS", "BladeLE", "BladeTE", "Hub"}) blades.add(rot.getBoundaryManager().getBoundary(n));
Scene s1 = sim.getSceneManager().createScene("presion_alabes"); s1.initializeAndWait();
ScalarDisplayer d1 = s1.getDisplayerManager().createScalarDisplayer("p"); d1.initialize();
d1.setRepresentation(sim.getRepresentationManager().getDefaultFvRepresentation());
d1.getInputParts().setObjects(blades);
d1.getScalarDisplayQuantity().setFieldFunction(sim.getFieldFunctionManager().getFunction("Pressure"));
s1.resetCamera(true);
List<Region> regs = new ArrayList<Region>(sim.getRegionManager().getRegions());
PlaneSection plane = sim.getPartManager().createImplicitPart(new NeoObjectVector(regs.toArray()), new DoubleVector(new double[] {0.0, 0.0, 1.0}), new DoubleVector(new double[] {0.0, 0.0, 0.030}), 0, 1, new DoubleVector(new double[] {0.0}));
plane.setPresentationName("plano_medio");
Scene s2 = sim.getSceneManager().createScene("velocidad_plano"); s2.initializeAndWait();
ScalarDisplayer d2 = s2.getDisplayerManager().createScalarDisplayer("v"); d2.initialize();
d2.setRepresentation(sim.getRepresentationManager().getDefaultFvRepresentation());
d2.getInputParts().setObjects(plane);
d2.getScalarDisplayQuantity().setFieldFunction(((PrimitiveFieldFunction) sim.getFieldFunctionManager().getFunction("Velocity")).getMagnitudeFunction());
s2.resetCamera(true);
List<Boundary> walls = new ArrayList<Boundary>();
for (Region r : regs) for (Boundary b : r.getBoundaryManager().getBoundaries()) if (b.getBoundaryType() instanceof WallBoundary) walls.add(b);
Scene s3 = sim.getSceneManager().createScene("yplus"); s3.initializeAndWait();
ScalarDisplayer d3 = s3.getDisplayerManager().createScalarDisplayer("y+"); d3.initialize();
d3.setRepresentation(sim.getRepresentationManager().getDefaultFvRepresentation());
d3.getInputParts().setObjects(walls);
d3.getScalarDisplayQuantity().setFieldFunction(sim.getFieldFunctionManager().getFunction("WallYplus"));
s3.resetCamera(true);
MaxReport ymax = sim.getReportManager().createReport(MaxReport.class); ymax.setPresentationName("yplus_max_alabes");
ymax.setFieldFunction(sim.getFieldFunctionManager().getFunction("WallYplus")); ymax.getParts().setObjects(blades);
MinReport ymin = sim.getReportManager().createReport(MinReport.class); ymin.setPresentationName("yplus_min_alabes");
ymin.setFieldFunction(sim.getFieldFunctionManager().getFunction("WallYplus")); ymin.getParts().setObjects(blades);
sim.println("YPLUS alabes min " + ymin.getReportMonitorValue() + " max " + ymax.getReportMonitorValue());
for (Scene s : sim.getSceneManager().getScenes()) sim.println("SCENE\t" + s.getPresentationName());
