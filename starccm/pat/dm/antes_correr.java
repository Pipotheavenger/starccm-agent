// PAT (2026-11-10): copia de ../../doe/dm/antes_correr.java; «Flujo=» en progreso.txt es el caso de DM (doe.estado empareja por él).
// QUE: macro de Design Manager (BEFORE_RUNNING) de cada diseño: Maximum Steps = ITS, sin otros criterios de parada, y
//      deja en <carpeta del diseño>/progreso.txt la meta para el tablero. STAR-CCM+ 2602, 2026-11-04.
// OJO: DM borra el historial DESPUÉS de esta macro (Clear History del estudio, activo): el contador vuelve a 0 y se
//      conservan los campos (de la base o del diseño reusado). Con «it0 + ITS» el Design 1 de G002 iba a 3500.
import java.util.*;
import star.common.*;
import star.base.report.*;

public class antes_correr extends StarMacro {
  public void execute() {
    Simulation sim = getActiveSimulation();
    int ITS = {{ITS}};
    int itSim = sim.getSimulationIterator().getCurrentIteration(), it0 = 0;
    for (Object o : sim.getSolverStoppingCriterionManager().getObjects()) {
      SolverStoppingCriterion c = (SolverStoppingCriterion) o;
      if (c instanceof StepStoppingCriterion) { ((StepStoppingCriterion) c).setMaximumNumberSteps(ITS); c.setIsUsed(true); }
      else c.setIsUsed(false);
    }
    // el lote vació los monitores impresos (07): sin esto el log del diseño no trae la tabla de iteraciones que lee el tablero
    try {
      List<Monitor> imp = new ArrayList<Monitor>();
      for (Monitor m : sim.getMonitorManager().getObjects()) {
        String n = m.getPresentationName();
        if (m instanceof ResidualMonitor || n.matches("(H|M|eta|P_eje)( Monitor)?")) imp.add(m);
      }
      sim.getMonitorManager().setPrintedMonitors(imp);
      sim.println("DOE_MONITORES " + imp.size());
    } catch (Exception e) { sim.println("WARN monitores impresos " + e); }
    double flujo = Double.NaN;
    double rpm = Double.NaN, q = Double.NaN;
    try { flujo = ((ScalarGlobalParameter) sim.get(GlobalParameterManager.class).getObject("caso")).getQuantity().getRawValue(); } catch (Exception e) { }   // PAT: «Flujo=» lleva el caso
    try { rpm = ((ScalarGlobalParameter) sim.get(GlobalParameterManager.class).getObject("rpm")).getQuantity().getRawValue(); } catch (Exception e) { }
    try { q = ((ScalarGlobalParameter) sim.get(GlobalParameterManager.class).getObject("Flujo")).getQuantity().getRawValue(); } catch (Exception e) { }
    String dir = new java.io.File(sim.getSessionPath()).getParent();
    try {
      java.nio.file.Files.write(java.nio.file.Paths.get(dir, "progreso.txt"),
          ("it0=" + it0 + "\nmeta=" + ITS + "\nit_sim=" + itSim + "\nFlujo=" + flujo + "\nrpm=" + rpm + "\nmasa=" + q + "\ninicio=" + new java.util.Date() + "\n").getBytes("UTF-8"));
    } catch (Exception e) { sim.println("WARN progreso.txt " + e); }
    sim.println("DOE_ANTES it_sim=" + itSim + " meta=" + ITS + " Flujo=" + flujo);
  }
}
