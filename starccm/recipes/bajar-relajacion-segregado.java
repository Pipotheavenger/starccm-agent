// QUE: baja la sub-relajación del flujo segregado (velocidad 0.7→0.5, presión 0.3→0.2) para residuales planos altos; verificado en cursoBomba 2026-10-27 (imports star.segregatedflow.*)
// VERSION: 19.06.009-R8
// FECHA: 2026-10-27
// imports: star.segregatedflow.*
SegregatedFlowSolver sfs = (SegregatedFlowSolver) sim.getSolverManager().getSolver(SegregatedFlowSolver.class);
sim.println("ANTES vel " + sfs.getVelocitySolver().getUrfQuantity().getRawValue() + " p " + sfs.getPressureSolver().getUrfQuantity().getRawValue());
sfs.getVelocitySolver().getUrfQuantity().setValue(0.5);
sfs.getPressureSolver().getUrfQuantity().setValue(0.2);
sim.println("DESPUES vel " + sfs.getVelocitySolver().getUrfQuantity().getRawValue() + " p " + sfs.getPressureSolver().getUrfQuantity().getRawValue());
