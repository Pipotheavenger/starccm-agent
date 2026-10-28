// QUE: lote 12 · exporta TODAS las escenas de la simulación a PNG en IMG_DIR (nombre sin el « 1» que añade STAR-CCM+).
// Base: tool export_scene (printAndWait verificado en batch).
String IMG_DIR = "{{IMG_DIR}}";
new java.io.File(IMG_DIR).mkdirs();
int k = 0;
for (Scene sc : sim.getSceneManager().getScenes()) {
  String n = sc.getPresentationName().replaceAll(" \\d+$", "").replaceAll("[^A-Za-z0-9_-]", "_");
  try {
    sc.printAndWait(resolvePath(IMG_DIR + "/" + n + ".png"), 1, 1600, 1000, true, false);
    sim.println("PNG\t" + n); k++;
  } catch (Exception e) { sim.println("WARN\tescena " + n + ": " + e); }
}
sim.println("LOTE_OK 12 " + k + " PNG");
