// QUE: lote 04 · física igual para todo el lote: 3D estacionario, líquido de densidad constante (RHO, MU del .cfturbo-ccm),
//      segregado, k-ω SST all-y+, Cell Quality Remediation; MRF en el rotor (RPM con signo sobre el eje del .cfturbo-ccm);
//      CasingHub/CasingShroud del rotor en marco de laboratorio; entrada ext_entrada/inlet = presión total 0 Pa y salida
//      ext_salida/outlet = caudal −${Flujo} (Flujo = MASA kg/s); relajación velocidad URF_V y presión URF_P.
// Base: bomba-fisica, bomba-propiedades-agua, fisica-modelos-turbo, bomba-mrf-rotor, paredes-estaticas-en-rotor,
//       fronteras-presion-total-caudal-salida, bajar-relajacion-segregado (verificadas).
// imports: star.segregatedflow.*, star.motion.*
double RHO = {{RHO}}, MU = {{MU}}, RPM = {{RPM}}, MASA = {{MASA}}, URF_V = {{URF_V}}, URF_P = {{URF_P}};
double[] AX = {{{AX}}};
PhysicsContinuum pc = null;
for (Continuum c : sim.getContinuumManager().getObjects()) if (c instanceof PhysicsContinuum) pc = (PhysicsContinuum) c;
if (pc == null) pc = sim.getContinuumManager().createContinuum(PhysicsContinuum.class);
pc.setPresentationName("agua");
for (Class c : new Class[] {ThreeDimensionalModel.class, SteadyModel.class, SingleComponentLiquidModel.class, SegregatedFlowModel.class, ConstantDensityModel.class,
                            TurbulentModel.class, RansTurbulenceModel.class, KOmegaTurbulence.class, SstKwTurbModel.class, KwAllYplusWallTreatment.class})
  pc.enable(c);
pc.enable(CellQualityRemediationModel.class);
for (Region r : sim.getRegionManager().getRegions()) r.setPhysicsContinuum(pc);
Liquid liq = (Liquid) pc.getModelManager().getModel(SingleComponentLiquidModel.class).getMaterial();
((ConstantMaterialPropertyMethod) liq.getMaterialProperties().getMaterialProperty(ConstantDensityProperty.class).getMethod()).getQuantity().setValue(RHO);
((ConstantMaterialPropertyMethod) liq.getMaterialProperties().getMaterialProperty(DynamicViscosityProperty.class).getMethod()).getQuantity().setValue(MU);
// idempotente: reusa el marco MRF_rotor si ya existe (antes un reintento creaba «MRF_rotor 2»)
ReferenceFrameManager rfm = sim.get(ReferenceFrameManager.class);
RotatingReferenceFrame frame = null;
for (Object o : rfm.getObjects()) if (o instanceof RotatingReferenceFrame && ((RotatingReferenceFrame) o).getPresentationName().matches("MRF_rotor( \\d+)?")) { frame = (RotatingReferenceFrame) o; break; }
if (frame == null) frame = rfm.createReferenceFrame(RotatingReferenceFrame.class, "MRF_rotor");
frame.setPresentationName("MRF_rotor");
frame.getRotationRate().setValueAndUnits(RPM, sim.getUnitsManager().getUnits("rpm"));
frame.getAxisDirection().setComponents(AX[0], AX[1], AX[2]);
frame.getAxisOrigin().setComponents(0.0, 0.0, 0.0);
Region rot = sim.getRegionManager().getRegion("rotor");
rot.getValues().get(MotionSpecification.class).setReferenceFrame(frame);
// carcasas fijas: toda frontera «Casing*» del rotor en marco de laboratorio. En flujo mixto CasingHub/CasingShroud
// están en el estator (ya fijas): eso es INFO, no un aviso.
int nCas = 0;
for (Boundary b : rot.getBoundaryManager().getBoundaries()) {
  if (!b.getPresentationName().startsWith("Casing")) continue;
  b.getConditions().get(WallReferenceFrameOption.class).setSelected(ReferenceFrameOption.Type.LAB_FRAME);
  sim.println("STATIC\t" + b.getPresentationName()); nCas++;
}
if (nCas == 0) {
  StringBuilder donde = new StringBuilder();
  for (Region r : sim.getRegionManager().getRegions()) for (Boundary b : r.getBoundaryManager().getBoundaries())
    if (b.getPresentationName().startsWith("Casing")) donde.append(" ").append(r.getPresentationName()).append("/").append(b.getPresentationName());
  sim.println("INFO\trotor sin fronteras Casing* (fijas en otras regiones:" + (donde.length() > 0 ? donde.toString() : " ninguna") + ")");
}
GlobalParameterManager gpm = sim.get(GlobalParameterManager.class);
ScalarGlobalParameter flujo = gpm.has("Flujo") ? (ScalarGlobalParameter) gpm.getObject("Flujo")
                                               : gpm.createGlobalParameter(ScalarGlobalParameter.class, "Flujo");
flujo.getQuantity().setValue(MASA);
Boundary inlet = sim.getRegionManager().getRegion("ext_entrada").getBoundaryManager().getBoundary("inlet");
Boundary outlet = sim.getRegionManager().getRegion("ext_salida").getBoundaryManager().getBoundary("outlet");
inlet.setBoundaryType(sim.get(ConditionTypeManager.class).get(StagnationBoundary.class));
inlet.getValues().get(TotalPressureProfile.class).getMethod(ConstantScalarProfileMethod.class).getQuantity().setValueAndUnits(0.0, sim.getUnitsManager().getUnits("Pa"));
outlet.setBoundaryType(sim.get(ConditionTypeManager.class).get(MassFlowBoundary.class));
outlet.getValues().get(MassFlowRateProfile.class).getMethod(ConstantScalarProfileMethod.class).getQuantity().setDefinition("-${Flujo}");
SegregatedFlowSolver sfs = (SegregatedFlowSolver) sim.getSolverManager().getSolver(SegregatedFlowSolver.class);
sfs.getVelocitySolver().getUrfQuantity().setValue(URF_V);
sfs.getPressureSolver().getUrfQuantity().setValue(URF_P);
for (Model m : pc.getModelManager().getObjects()) sim.println("MODEL\t" + m.getPresentationName());
for (Region r : sim.getRegionManager().getRegions())
  for (Boundary b : r.getBoundaryManager().getBoundaries())
    sim.println("BC\t" + r.getPresentationName() + "/" + b.getPresentationName() + "\t" + b.getBoundaryType().getPresentationName());
sim.println("MRF\t" + frame.getRotationRate().getRawValue() + " rpm\teje " + AX[0] + "," + AX[1] + "," + AX[2] + "\tFlujo " + MASA + " kg/s");
sim.println("LOTE_OK 04");
