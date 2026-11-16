// QUE: prueba de convergencia sobre UN .sim resuelto (nq 10–25 no convergen, 2026-11-10). MODO:
//      diag  → operaciones de malla, celdas malas por región, solvers; no itera
//      urf   → relajación presión URF_P y velocidad URF_V, ITS iteraciones más desde la solución actual
//      malla → base de la malla × FACTOR en todas las operaciones automáticas, remalla e itera ITS desde cero (con URF_P/URF_V)
//      Imprime «PRUEBA it=… H=… M=… cont=… maxres=…» cada 100 iteraciones. No guarda el .sim. STAR-CCM+ 2602.
import java.util.*;
import java.nio.file.*;
import star.common.*;
import star.base.report.*;
import star.base.neo.*;
import star.meshing.*;
import star.segregatedflow.*;

public class prueba extends StarMacro {
  Simulation sim;

  double rep(String n) { try { return sim.getReportManager().getReport(n).getReportMonitorValue(); } catch (Exception e) { return Double.NaN; } }

  double[] residuales(String csv) {   // última fila del plot Residuals: [continuidad, máximo]
    try {
      sim.getPlotManager().getPlot("Residuals").export(csv, ",");
      List<String> l = Files.readAllLines(Paths.get(csv));
      String[] h = l.get(0).split(","), v = l.get(l.size() - 1).split(",");
      double c = Double.NaN, m = 0;
      for (int i = 1; i < h.length && i < v.length; i++) {
        double x = Double.parseDouble(v[i]);
        if (h[i].contains("Continuity")) c = x;
        m = Math.max(m, x);
      }
      return new double[]{c, m};
    } catch (Exception e) { return new double[]{Double.NaN, Double.NaN}; }
  }

  void iterar(int its, String dir) {
    for (int k = 0; k < its; k += 100) {
      sim.getSimulationIterator().step(Math.min(100, its - k));
      double[] r = residuales(dir + "/res.csv");
      sim.println(String.format(Locale.ROOT, "PRUEBA it=%d H=%.4f M=%.4f eta=%.5f cont=%.3e maxres=%.3e",
          sim.getSimulationIterator().getCurrentIteration(), rep("H"), rep("M"), rep("eta"), r[0], r[1]));
    }
  }

  public void execute() {
    sim = getActiveSimulation();
    String MODO = "{{MODO}}", dir = "{{DIR}}";
    int ITS = {{ITS}};
    double URF_P = {{URF_P}}, URF_V = {{URF_V}}, FACTOR = {{FACTOR}};
    for (Object o : sim.getSolverStoppingCriterionManager().getObjects()) ((SolverStoppingCriterion) o).setIsUsed(false);
    // malla: operaciones y tamaño base
    for (Object o : sim.get(MeshOperationManager.class).getObjects()) {
      String s = "PRUEBA malla_op " + ((NamedObject) o).getPresentationName() + " " + o.getClass().getSimpleName();
      try {
        BaseSize b = ((AutoMeshOperation) o).getDefaultValues().get(BaseSize.class);
        s += " base=" + b.getRawValue();
        if (MODO.equals("malla")) { b.setValue(b.getRawValue() * FACTOR); s += " -> " + b.getRawValue(); }
      } catch (Exception e) { }
      sim.println(s);
    }
    // celdas de mala calidad por región (CellQuality < 1e-2)
    try {
      UserFieldFunction u = sim.getFieldFunctionManager().createFieldFunction();
      u.getTypeOption().setSelected(FieldFunctionTypeOption.Type.SCALAR);
      u.setFunctionName("prueba_mala"); u.setDefinition("${CellQuality} < 0.01 ? 1 : 0");
      for (Region r : sim.getRegionManager().getRegions()) {
        SumReport s = sim.getReportManager().createReport(SumReport.class);
        s.setFieldFunction(u); s.getParts().setObjects(r);
        ElementCountReport n = sim.getReportManager().createReport(ElementCountReport.class);
        n.getParts().setObjects(r);
        sim.println("PRUEBA region " + r.getPresentationName() + " celdas=" + (long) n.getReportMonitorValue() + " malas=" + (long) s.getReportMonitorValue());
        sim.getReportManager().removeObjects(s, n);
      }
    } catch (Exception e) { sim.println("PRUEBA error_regiones " + e); }
    SegregatedFlowSolver sf = sim.getSolverManager().getSolver(SegregatedFlowSolver.class);
    sim.println("PRUEBA urf p=" + sf.getPressureSolver().getUrf() + " v=" + sf.getVelocitySolver().getUrf());
    double[] r0 = residuales(dir + "/res.csv");
    sim.println(String.format(Locale.ROOT, "PRUEBA inicio it=%d H=%.4f M=%.4f cont=%.3e maxres=%.3e",
        sim.getSimulationIterator().getCurrentIteration(), rep("H"), rep("M"), r0[0], r0[1]));
    if (MODO.equals("urf")) {
      sf.getPressureSolver().setUrf(URF_P); sf.getVelocitySolver().setUrf(URF_V);
      iterar(ITS, dir);
    } else if (MODO.equals("malla")) {   // con URF_P/URF_V (por defecto 0,2/0,5, las de siempre)
      sf.getPressureSolver().setUrf(URF_P); sf.getVelocitySolver().setUrf(URF_V);
      sim.get(MeshPipelineController.class).generateVolumeMesh();
      ElementCountReport n = sim.getReportManager().createReport(ElementCountReport.class);
      n.getParts().setObjects(sim.getRegionManager().getRegions());
      sim.println("PRUEBA celdas_nuevas " + (long) n.getReportMonitorValue());
      sim.getReportManager().removeObjects(n);
      sim.getSolution().initializeSolution();
      iterar(ITS, dir);
    }
    sim.println("PRUEBA fin");
  }
}
