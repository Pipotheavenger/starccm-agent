// QUE: sobre el .sim transitorio ya periódico (transitorio_fin.sim) avanza {{PASOS}} pasos más y cada {{CADA}} pasos guarda
//      un PNG de las escenas «vectores_medio» (velocidad relativa) y «plano_vectores» (velocidad absoluta) en {{OUT}}/frames.
//      Rango de color fijo para que no parpadee. No guarda el .sim (el de 10 vueltas queda como estaba). STAR-CCM+ 2602.
import java.util.*;
import java.io.*;
import star.common.*;
import star.vis.*;

public class video extends StarMacro {
  public void execute() {
    Simulation sim = getActiveSimulation();
    String OUT = "{{OUT}}";
    int PASOS = {{PASOS}}, CADA = {{CADA}};
    try {
      new File(OUT + "/frames").mkdirs();
      Map<String, Scene> esc = new LinkedHashMap<>();
      for (Scene sc : sim.getSceneManager().getScenes()) {
        String n = sc.getPresentationName().replaceAll("[^A-Za-z0-9_-]", "_");
        if (n.startsWith("vectores_medio") || n.startsWith("plano_vectores")) esc.put(n.replaceAll("_\\d+$", ""), sc);
      }
      double[][] rango = {{0, 35}, {0, 40}};
      int j = 0;
      for (Scene sc : esc.values()) {
        for (Object d : sc.getDisplayerManager().getObjects()) {
          try {
            if (d instanceof VectorDisplayer) { ((VectorDisplayer) d).getVectorDisplayQuantity().setRange(rango[j]); ((VectorDisplayer) d).getVectorDisplayQuantity().setAutoRange(AutoRangeMode.NONE); }
            if (d instanceof ScalarDisplayer) { ((ScalarDisplayer) d).getScalarDisplayQuantity().setRange(rango[j]); ((ScalarDisplayer) d).getScalarDisplayQuantity().setAutoRange(AutoRangeMode.NONE); }
          } catch (Exception e) { sim.println("VID aviso rango " + d + ": " + e); }
        }
        j++;
      }
      sim.println("VID escenas " + esc.keySet());
      int f = 0;
      for (int k = 0; k <= PASOS; k++) {
        if (k > 0) sim.getSimulationIterator().step(1);
        if (k % CADA != 0) continue;
        for (Map.Entry<String, Scene> e : esc.entrySet())
          e.getValue().printAndWait(resolvePath(String.format(Locale.ROOT, "%s/frames/%s_%04d.png", OUT, e.getKey(), f)), 1, 1600, 1000, true, false);
        if (f % 15 == 0) sim.println(String.format(Locale.ROOT, "VID frame %d t=%.5f", f, sim.getSolution().getPhysicalTime()));
        f++;
      }
      sim.println("VID_OK " + f);
    } catch (Exception e) {
      sim.println("VID_ERROR " + e);
      for (StackTraceElement s : e.getStackTrace()) sim.println("  " + s);
    }
  }
}
