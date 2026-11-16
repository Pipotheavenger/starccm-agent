// QUE: exporta TODAS las escenas del .sim abierto a PNG en la carpeta que dice render_destino.txt (junto al .sim; la
//      escribe scripts/render.ps1). Fuera de Design Manager: si el render por software se cae, solo se pierde este paso.
//      Base: lote 12 (escenas). STAR-CCM+ 2602, 2026-11-05.
import java.util.*;
import java.nio.file.*;
import star.common.*;
import star.vis.*;

public class escenas extends StarMacro {
  public void execute() {
    Simulation sim = getActiveSimulation();
    String img;
    try {
      img = new String(Files.readAllBytes(Paths.get(new java.io.File(sim.getSessionPath()).getParent(), "render_destino.txt")), "UTF-8").trim();
    } catch (Exception e) { sim.println("DOE_ESCENAS_ERROR sin render_destino.txt " + e); return; }
    new java.io.File(img).mkdirs();
    int k = 0;
    Set<String> usados = new HashSet<String>();
    for (Scene sc : sim.getSceneManager().getScenes()) {
      String n = sc.getPresentationName().replaceAll("[^A-Za-z0-9_-]", "_");
      for (int j = 2; usados.contains(n); j++) n = n.replaceAll("__\\d+$", "") + "__" + j;
      usados.add(n);
      try { sc.printAndWait(resolvePath(img + "/" + n + ".png"), 1, 1600, 1000, true, false); k++; }
      catch (Exception e) { sim.println("WARN escena " + n + ": " + e); }
    }
    try { Files.write(Paths.get(img, "_ok.txt"), ("" + k + "\n").getBytes("UTF-8")); } catch (Exception e) { }
    sim.println("DOE_ESCENAS " + img + " " + k);
  }
}
