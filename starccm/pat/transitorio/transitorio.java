// QUE: convierte un .sim estacionario MRF (PAT, G025 en su BEP de turbina) a transitorio con malla deslizante
//      (movimiento de cuerpo rígido del rotor, URANS implícito de 2.º orden) y corre {{NREV}} vueltas a {{GRADOS}}° por paso
//      con {{INNER}} iteraciones internas. Escribe {{OUT}}/transitorio.csv con una fila por paso (t, ángulo, H, M, η…).
//      MODO diag: solo imprime el montaje (frames, motions, regiones, paredes del rotor, modelos); no cambia nada.
//      STAR-CCM+ 2602 (2026-11-16, Sebastián: comparar estacionario frente a transitorio).
import java.util.*;
import java.io.*;
import star.common.*;
import star.base.neo.*;
import star.base.report.*;
import star.motion.*;

public class transitorio extends StarMacro {
  Simulation sim;

  double rep(String n) { try { return sim.getReportManager().getReport(n).getReportMonitorValue(); } catch (Exception e) { return Double.NaN; } }

  public void execute() {
    sim = getActiveSimulation();
    String MODO = "{{MODO}}", OUT = "{{OUT}}";
    int NREV = {{NREV}}, INNER = {{INNER}};
    double GRADOS = {{GRADOS}};
    try {
      PhysicsContinuum pc = null;
      for (Object o : sim.getContinuumManager().getObjects()) if (o instanceof PhysicsContinuum) pc = (PhysicsContinuum) o;
      RotatingReferenceFrame fr = null;
      ReferenceFrameBase lab = null;
      for (Object o : sim.get(ReferenceFrameManager.class).getObjects()) {
        if (o instanceof RotatingReferenceFrame) fr = (RotatingReferenceFrame) o;
        if (o instanceof LabReferenceFrame) lab = (LabReferenceFrame) o;
      }
      sim.println("TR frame " + fr.getPresentationName() + " rate " + fr.getRotationRate().getDefinition() + " = " + fr.getRotationRate().getSIValue()
          + " eje " + fr.getAxisDirection().getSIVector() + " origen " + fr.getOriginVector().getSIVector() + " lab " + (lab == null ? "-" : lab.getPresentationName()));
      for (Object o : sim.get(MotionManager.class).getObjects()) sim.println("TR motion " + ((NamedObject) o).getPresentationName() + " " + o.getClass().getSimpleName());
      for (Region r : sim.getRegionManager().getRegions()) {
        MotionSpecification ms = r.getValues().get(MotionSpecification.class);
        sim.println("TR region " + r.getPresentationName() + " motion=" + ms.getMotion().getPresentationName() + " frame=" + ms.getReferenceFrame().getPresentationName());
        if (!r.getPresentationName().equals("rotor")) continue;
        for (Boundary b : r.getBoundaryManager().getBoundaries()) {
          StringBuilder s = new StringBuilder();
          for (Object c : b.getConditions().getObjects()) {
            s.append(c.getClass().getSimpleName());
            if (c instanceof EnumeratedOption) s.append("=").append(((EnumeratedOption) c).getSelectedElement());
            s.append("; ");
          }
          sim.println("TR pared " + b.getPresentationName() + " [" + b.getBoundaryType().getPresentationName() + "] " + s);
        }
      }
      for (Object o : pc.getModelManager().getObjects()) sim.println("TR modelo " + o.getClass().getSimpleName());
      for (Object o : sim.getSolverStoppingCriterionManager().getObjects()) sim.println("TR criterio " + ((NamedObject) o).getPresentationName() + " " + o.getClass().getSimpleName());
      sim.println(String.format(Locale.ROOT, "TR estacionario H=%.4f M=%.4f eta=%.5f P_eje=%.1f Q_in=%.4f it=%d", rep("H"), rep("M"), rep("eta"), rep("P_eje"),
          rep("Q_in"), sim.getSimulationIterator().getCurrentIteration()));
      if (MODO.equals("diag")) return;

      // 1) transitorio implícito de 2.º orden (antes del movimiento: con el estacionario, STAR rechaza el movimiento de cuerpo rígido)
      pc.disableModel(pc.getModelManager().getModel(SteadyModel.class));
      pc.enable(ImplicitUnsteadyModel.class);
      // 2) rotor con malla deslizante: misma velocidad, eje y origen que el frame MRF; la región pasa al frame de laboratorio
      double w = fr.getRotationRate().getSIValue();
      DoubleVector ax = fr.getAxisDirection().getSIVector(), org = fr.getOriginVector().getSIVector();
      RotatingMotion rm = sim.get(MotionManager.class).createMotion(RotatingMotion.class, "Rotacion_rotor");
      rm.getAxisDirection().setComponents(ax.get(0), ax.get(1), ax.get(2));
      rm.getOriginVector().setComponents(org.get(0), org.get(1), org.get(2));
      ((RotationRate) rm.getRotationSpecification()).getRotationRate().setValueAndUnits(w, sim.getUnitsManager().getUnits("radian/s"));
      Region rot = sim.getRegionManager().getRegion("rotor");
      MotionSpecification ms = rot.getValues().get(MotionSpecification.class);
      ms.setMotion(rm);
      ms.setReferenceFrame(lab);
      sim.println("TR rotor motion=" + ms.getMotion().getPresentationName() + " frame=" + ms.getReferenceFrame().getPresentationName() + " w=" + w);

      ImplicitUnsteadySolver us = sim.getSolverManager().getSolver(ImplicitUnsteadySolver.class);
      double dt = GRADOS * Math.PI / 180 / Math.abs(w);
      us.getTimeStep().setValue(dt);
      us.getTimeDiscretizationOption().setSelected(TimeDiscretizationOption.Type.SECOND_ORDER);
      for (Object o : sim.getSolverStoppingCriterionManager().getObjects()) {
        if (o instanceof InnerIterationStoppingCriterion) ((InnerIterationStoppingCriterion) o).setMaximumNumberInnerIterations(INNER);
        if (o instanceof StepStoppingCriterion) ((SolverStoppingCriterion) o).setIsUsed(false);
        if (o instanceof PhysicalTimeStoppingCriterion) ((PhysicalTimeStoppingCriterion) o).setMaximumTime(10 * NREV * 2 * Math.PI / Math.abs(w));
      }
      int pasosRev = (int) Math.round(360.0 / GRADOS), total = NREV * pasosRev;
      sim.println(String.format(Locale.ROOT, "TR dt=%.6e s, %d pasos/vuelta, %d pasos, %d it internas", dt, pasosRev, total, INNER));

      // 3) un paso de tiempo cada vez; reportes a mano (los monitores van por iteración)
      try (PrintWriter csv = new PrintWriter(new FileWriter(OUT + "/transitorio.csv"))) {
        csv.println("paso,t_s,angulo_deg,vuelta,H,M,eta,P_eje,P_hid,Q_in,Q_out,pt_in,pt_out");
        double sH = 0, sM = 0, sE = 0; int n = 0;
        for (int k = 1; k <= total; k++) {
          sim.getSimulationIterator().step(1);
          double t = sim.getSolution().getPhysicalTime();
          double H = rep("H"), M = rep("M"), eta = rep("eta");
          csv.println(String.format(Locale.ROOT, "%d,%.8e,%.3f,%d,%.6f,%.6f,%.7f,%.4f,%.4f,%.6f,%.6f,%.3f,%.3f", k, t, Math.toDegrees(Math.abs(w) * t),
              (k - 1) / pasosRev + 1, H, M, eta, rep("P_eje"), rep("P_hid"), rep("Q_in"), rep("Q_out"), rep("pt_in"), rep("pt_out")));
          sH += H; sM += M; sE += eta; n++;
          if (k == 1) sim.println(String.format(Locale.ROOT, "TR primer paso t=%.6e it=%d H=%.4f M=%.4f", t, sim.getSimulationIterator().getCurrentIteration(), H, M));
          if (k % pasosRev == 0) {
            csv.flush();
            sim.println(String.format(Locale.ROOT, "TR vuelta %d t=%.5f media H=%.4f M=%.4f eta=%.5f", k / pasosRev, t, sH / n, sM / n, sE / n));
            sH = sM = sE = 0; n = 0;
            if (k / pasosRev == NREV / 2) sim.saveState(OUT + "/transitorio_mitad.sim");
          }
        }
      }
      sim.saveState(OUT + "/transitorio_fin.sim");
      sim.println("TR_OK");
    } catch (Exception e) {
      sim.println("TR_ERROR " + e);
      for (StackTraceElement s : e.getStackTrace()) sim.println("  " + s);
    }
  }
}
