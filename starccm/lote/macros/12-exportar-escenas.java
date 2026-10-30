// QUE: lote 12 · exporta TODAS las escenas de la simulación a PNG en IMG_DIR. Nombre = el de la escena; el « N» final
//      que añade STAR-CCM+ solo se quita si no choca con otra escena (antes «X 1» y «X 2» se pisaban en X.png).
// Base: tool export_scene (printAndWait verificado en batch).
String IMG_DIR = "{{IMG_DIR}}";
new java.io.File(IMG_DIR).mkdirs();
java.util.List<Scene> escenas = new java.util.ArrayList<Scene>(sim.getSceneManager().getScenes());
java.util.Map<String, Integer> cuenta = new java.util.HashMap<String, Integer>();
for (Scene sc : escenas) { String b = sc.getPresentationName().replaceAll(" \\d+$", ""); cuenta.put(b, cuenta.containsKey(b) ? cuenta.get(b) + 1 : 1); }
java.util.Set<String> usados = new java.util.HashSet<String>();
int k = 0;
for (Scene sc : escenas) {
  String full = sc.getPresentationName(), b = full.replaceAll(" \\d+$", "");
  String n = (cuenta.get(b) == 1 ? b : full).replaceAll("[^A-Za-z0-9_-]", "_");
  for (int j = 2; usados.contains(n); j++) n = n.replaceAll("__\\d+$", "") + "__" + j;
  usados.add(n);
  try {
    sc.printAndWait(resolvePath(IMG_DIR + "/" + n + ".png"), 1, 1600, 1000, true, false);
    sim.println("PNG\t" + n); k++;
  } catch (Exception e) { sim.println("WARN\tescena " + n + ": " + e); }
}
sim.println("LOTE_OK 12 " + k + " PNG");
