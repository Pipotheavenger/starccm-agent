// PAT (2026-11-10): copia de ../../doe/dm/despues.java; la carpeta del punto lleva Q y rpm y el JSON el caso y las rpm.
// QUE: macro de Design Manager (BEFORE_RESULTS) de cada diseño, ya iterado. En PUNTOS/Q<caudal>_m3h/ (fuera de la
//      carpeta del diseño: DM la borra al terminar y solo guarda el log) deja: resultados.json (entradas, malla y calidad,
//      TODOS los reportes, convergencia de cada monitor, balance de masa, residuales, y+ y cortante de cada pared,
//      caudal y presiones de cada entrada/salida) y reports/<plot>.csv (historial de cada gráfico). Con GUARDAR guarda
//      el .sim resuelto en la carpeta del diseño. Desde el 2026-11-09 los .sim de los puntos que no son Qn se borran al
//      entregar: este JSON es lo que queda de cada punto, por eso lleva todo. Cada bloque va en su try: un nombre que no
//      exista en el .sim deja «error_<bloque>» y sigue. Base: lote 09 (resultado). STAR-CCM+ 2602, 2026-11-09.
//      Sin DM (re-extraer un .sim ya resuelto): GUARDAR=false y `starccm+ -batch despues.java <sim>`.
import java.util.*;
import java.nio.file.*;
import star.common.*;
import star.base.report.*;
import star.base.neo.*;
import star.meshing.*;
import star.flow.*;
import star.motion.*;

public class despues extends StarMacro {
  StringBuilder sb = new StringBuilder();
  Simulation sim;
  ReportManager rm;
  List<Report> tmp = new ArrayList<Report>();
  List<UserFieldFunction> tmpff = new ArrayList<UserFieldFunction>();

  String num(double v) { return (Double.isNaN(v) || Double.isInfinite(v) || Math.abs(v) > 1e300) ? "null" : String.valueOf(v); }
  String str(String s) { return "\"" + s.replace("\\", "\\\\").replace("\"", "\\\"").replace("\n", " ").replace("\r", "") + "\""; }
  void raw(String k, String v) { sb.append(sb.length() > 0 ? ",\n" : "").append("  ").append(str(k)).append(": ").append(v); }
  void err(String bloque, Exception e) { raw("error_" + bloque, str(e.toString())); }
  static String obj(List<String> kv) { return "{" + String.join(", ", kv) + "}"; }

  // reporte temporal de un campo sobre unas partes (se borran todos al final)
  double rep(Class<? extends Report> c, FieldFunction ff, Collection<? extends NamedObject> partes) {
    try {
      Report r = rm.createReport((Class) c); tmp.add(r);
      if (ff != null) r.getClass().getMethod("setFieldFunction", FieldFunction.class).invoke(r, ff);
      Object pm = r.getClass().getMethod("getParts").invoke(r);
      pm.getClass().getMethod("setObjects", Collection.class).invoke(pm, partes);
      return r.getReportMonitorValue();
    } catch (Exception e) { return Double.NaN; }
  }
  FieldFunction ff(String n) { try { return sim.getFieldFunctionManager().getFunction(n); } catch (Exception e) { return null; } }
  FieldFunction mag(String n) { FieldFunction f = ff(n); try { return f == null ? null : f.getMagnitudeFunction(); } catch (Exception e) { return f; } }
  FieldFunction user(String def) {
    UserFieldFunction u = sim.getFieldFunctionManager().createFieldFunction(); tmpff.add(u);
    u.getTypeOption().setSelected(FieldFunctionTypeOption.Type.SCALAR);
    u.setFunctionName("doe_tmp_" + tmpff.size()); u.setDefinition(def);
    return u;
  }
  // modelos y solvers no siempre son NamedObject (ThreeDimensionalModel, PartitioningSolver: ClassCastException en G031)
  static String nombre(Object o) { try { return (String) o.getClass().getMethod("getPresentationName").invoke(o); } catch (Exception e) { return o.getClass().getSimpleName(); } }
  Set<Boundary> enInterfaz = new HashSet<Boundary>();   // caras unidas por una interfaz (Inflow/Outflow internos): no son paredes
  boolean interfaz(Boundary b) { return enInterfaz.contains(b) || b instanceof DirectBoundaryInterfaceBoundary || b.getPresentationName().contains("[int_"); }

  public void execute() {
    sim = getActiveSimulation();
    rm = sim.getReportManager();
    String PUNTOS = "{{PUNTOS}}";
    double RHO = {{RHO}};
    boolean GUARDAR = {{GUARDAR}};
    double fl = Double.NaN;
    try { fl = ((ScalarGlobalParameter) sim.get(GlobalParameterManager.class).getObject("Flujo")).getQuantity().getRawValue(); } catch (Exception e) { }
    double rpm = Double.NaN, caso = Double.NaN;   // PAT: cada punto es una combinación caudal × rpm («caso» de DM)
    try { rpm = ((ScalarGlobalParameter) sim.get(GlobalParameterManager.class).getObject("rpm")).getQuantity().getRawValue(); } catch (Exception e) { }
    try { caso = ((ScalarGlobalParameter) sim.get(GlobalParameterManager.class).getObject("caso")).getQuantity().getRawValue(); } catch (Exception e) { }
    String dir = PUNTOS + "/" + String.format(java.util.Locale.ROOT, "Q%08.3f_m3h_n%04.0f_rpm", fl * 3600.0 / RHO, rpm);
    new java.io.File(dir).mkdirs();
    List<Region> regiones = new ArrayList<Region>(sim.getRegionManager().getRegions());

    // --- entradas ---
    raw("version_json", "2");
    raw("extraido", str(new java.text.SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss").format(new Date())));
    raw("iteracion", "" + sim.getSimulationIterator().getCurrentIteration());
    raw("Flujo_kg_s", num(fl));
    raw("Q_m3h", num(fl * 3600.0 / RHO));
    raw("rpm", num(rpm));
    raw("caso", num(Math.rint(caso)));
    raw("modo", str("PAT"));
    raw("rho", num(RHO));
    raw("sim", str(sim.getSessionPath()));
    try {
      List<String> gp = new ArrayList<String>();
      for (Object o : sim.get(GlobalParameterManager.class).getObjects())
        if (o instanceof ScalarGlobalParameter) { ScalarGlobalParameter s = (ScalarGlobalParameter) o; gp.add(str(s.getPresentationName()) + ": " + num(s.getQuantity().getRawValue())); }
      raw("parametros", obj(gp));
    } catch (Exception e) { err("parametros", e); }
    try {
      List<String> fr = new ArrayList<String>();
      for (Object o : sim.get(ReferenceFrameManager.class).getObjects())
        if (o instanceof RotatingReferenceFrame) {
          RotatingReferenceFrame f = (RotatingReferenceFrame) o;
          fr.add(str(f.getPresentationName()) + ": " + num(f.getRotationRate().getRawValue() * 60.0 / (2 * Math.PI)));
        }
      raw("marcos_rpm", obj(fr));
    } catch (Exception e) { err("marcos", e); }
    try {
      List<String> fis = new ArrayList<String>();
      for (Object o : sim.getContinuumManager().getObjects())
        if (o instanceof PhysicsContinuum) {
          List<String> m = new ArrayList<String>();
          for (Object x : ((PhysicsContinuum) o).getModelManager().getObjects()) m.add(str(nombre(x)));
          fis.add(str(nombre(o)) + ": [" + String.join(", ", m) + "]");
        }
      raw("modelos", obj(fis));
    } catch (Exception e) { err("modelos", e); }
    try {
      List<String> sv = new ArrayList<String>();
      for (Object o : sim.getSolverManager().getObjects()) {
        String n = nombre(o); List<String> u = new ArrayList<String>();
        for (String g : new String[]{"getVelocitySolver", "getPressureSolver"})
          try { Object s = o.getClass().getMethod(g).invoke(o); u.add(str(g.substring(3)) + ": " + num((Double) s.getClass().getMethod("getUrf").invoke(s))); } catch (Exception e) { }
        try { u.add("\"urf\": " + num((Double) o.getClass().getMethod("getUrf").invoke(o))); } catch (Exception e) { }
        sv.add(str(n) + ": " + obj(u));
      }
      raw("solvers", obj(sv));
    } catch (Exception e) { err("solvers", e); }
    try {
      List<String> sc = new ArrayList<String>();
      for (Object o : sim.getSolverStoppingCriterionManager().getObjects()) {
        SolverStoppingCriterion c = (SolverStoppingCriterion) o; String v = "null";
        if (c instanceof StepStoppingCriterion) v = "" + ((StepStoppingCriterion) c).getMaximumNumberSteps();
        sc.add(str(c.getPresentationName()) + ": {\"activo\": " + c.getIsUsed() + ", \"valor\": " + v + "}");
      }
      raw("criterios_parada", obj(sc));
    } catch (Exception e) { err("criterios", e); }

    // --- fronteras: tipo de cada una; caudal y presiones en las que no son pared ni interfaz ---
    List<Boundary> paredes = new ArrayList<Boundary>(), abiertas = new ArrayList<Boundary>();
    for (Object i : sim.getInterfaceManager().getObjects())
      for (String g : new String[]{"getBoundary0", "getBoundary1"})
        try { Object b = i.getClass().getMethod(g).invoke(i); if (b instanceof Boundary) enInterfaz.add((Boundary) b); } catch (Exception e) { }
    try {
      List<String> tb = new ArrayList<String>();
      for (Region r : regiones)
        for (Boundary b : r.getBoundaryManager().getBoundaries()) {
          String t = b.getBoundaryType().getPresentationName();
          tb.add(str(r.getPresentationName() + "/" + b.getPresentationName()) + ": " + str(t));
          if (interfaz(b)) continue;
          if (b.getBoundaryType() instanceof WallBoundary) paredes.add(b); else abiertas.add(b);
        }
      raw("fronteras_tipo", obj(tb));
    } catch (Exception e) { err("fronteras", e); }
    try {
      List<String> ab = new ArrayList<String>();
      FieldFunction p = ff("Pressure"), pt = ff("TotalPressure");
      for (Boundary b : abiertas) {
        List<Boundary> L = Collections.singletonList(b);
        ab.add(str(b.getRegion().getPresentationName() + "/" + b.getPresentationName()) + ": {\"caudal_kg_s\": " + num(rep(MassFlowReport.class, null, L))
          + ", \"p_media_Pa\": " + num(rep(AreaAverageReport.class, p, L)) + ", \"pt_masa_Pa\": " + num(rep(MassFlowAverageReport.class, pt, L))
          + ", \"area_m2\": " + num(rep(SurfaceIntegralReport.class, user("1"), L)) + "}");
      }
      raw("entradas_salidas", obj(ab));
    } catch (Exception e) { err("entradas_salidas", e); }

    // --- malla: celdas por región y calidad ---
    long total = 0;
    try {
      List<String> cr = new ArrayList<String>();
      for (Region r : regiones) {
        long n = (long) rep(ElementCountReport.class, null, Collections.singletonList(r)); total += n;
        cr.add(str(r.getPresentationName()) + ": " + n);
      }
      raw("celdas", "" + total);
      raw("celdas_region", obj(cr));
    } catch (Exception e) { err("celdas", e); }
    try {
      List<String> q = new ArrayList<String>();
      for (String n : new String[]{"CellQuality", "SkewnessAngle", "VolumeChange", "Volume"}) {
        FieldFunction f = ff(n); if (f == null) continue;
        q.add(str(n) + ": {\"min\": " + num(rep(MinReport.class, f, regiones)) + ", \"max\": " + num(rep(MaxReport.class, f, regiones)) + "}");
      }
      // celdas malas (criterio de «no sirve» del CLAUDE.md: > 0,1 % es para reparar)
      q.add("\"malas_calidad_lt_1e-2\": " + num(rep(SumReport.class, user("($CellQuality < 0.01) ? 1 : 0"), regiones)));
      q.add("\"malas_skew_gt_85\": " + num(rep(SumReport.class, user("($SkewnessAngle > 85) ? 1 : 0"), regiones)));
      q.add("\"malas_volchange_lt_1e-3\": " + num(rep(SumReport.class, user("($VolumeChange < 0.001) ? 1 : 0"), regiones)));
      raw("calidad_malla", obj(q));
    } catch (Exception e) { err("calidad_malla", e); }

    // --- paredes: y+ y cortante de cada una ---
    try {
      FieldFunction yp = ff("WallYplus"), tau = mag("WallShearStress");
      FieldFunction alto = user("($WallYplus > 300) ? 1 : 0"), bajo = user("($WallYplus < 1) ? 1 : 0"), medio = user("($WallYplus >= 30 && $WallYplus <= 300) ? 1 : 0");
      List<String> pw = new ArrayList<String>(); List<Boundary> alabes = new ArrayList<Boundary>();
      for (Boundary b : paredes) {
        List<Boundary> L = Collections.singletonList(b);
        if (b.getPresentationName().startsWith("Blade")) alabes.add(b);
        pw.add(str(b.getRegion().getPresentationName() + "/" + b.getPresentationName()) + ": {\"yplus_medio\": " + num(rep(AreaAverageReport.class, yp, L))
          + ", \"yplus_min\": " + num(rep(MinReport.class, yp, L)) + ", \"yplus_max\": " + num(rep(MaxReport.class, yp, L))
          + ", \"frac_area_30_300\": " + num(rep(AreaAverageReport.class, medio, L)) + ", \"frac_area_gt_300\": " + num(rep(AreaAverageReport.class, alto, L))
          + ", \"frac_area_lt_1\": " + num(rep(AreaAverageReport.class, bajo, L)) + ", \"tau_media_Pa\": " + num(rep(AreaAverageReport.class, tau, L)) + "}");
      }
      raw("paredes", obj(pw));
      if (!alabes.isEmpty()) {
        raw("yplus_alabes_medio", num(rep(AreaAverageReport.class, yp, alabes)));
        raw("yplus_alabes_max", num(rep(MaxReport.class, yp, alabes)));
      }
    } catch (Exception e) { err("paredes", e); }

    // --- todos los reportes del .sim ---
    try {
      List<String> rs = new ArrayList<String>();
      for (Report r : rm.getObjects()) {
        if (tmp.contains(r)) continue;
        double v; try { v = r.getReportMonitorValue(); } catch (Exception e) { continue; }
        rs.add(str(r.getPresentationName()) + ": " + num(v));
      }
      raw("reportes", obj(rs));
      double qi = rm.getReport("Q_in").getReportMonitorValue(), qo = rm.getReport("Q_out").getReportMonitorValue();
      raw("balance_masa_pct", num(100.0 * Math.abs(qi + qo) / Math.max(1e-12, Math.abs(qi))));
    } catch (Exception e) { err("reportes", e); }

    // --- convergencia de cada monitor de reporte: últimas 100 iteraciones ---
    try {
      List<String> cv = new ArrayList<String>();
      for (Object o : sim.getMonitorManager().getObjects()) {
        if (!(o instanceof ReportMonitor)) continue;
        double[] y = ((ReportMonitor) o).getAllYValues(); int n = y.length; if (n == 0) continue;
        int k = Math.min(100, n); double s = 0, s2 = 0, mn = Double.MAX_VALUE, mx = -Double.MAX_VALUE;
        for (int i = n - k; i < n; i++) { s += y[i]; s2 += y[i] * y[i]; mn = Math.min(mn, y[i]); mx = Math.max(mx, y[i]); }
        double m = s / k, sd = Math.sqrt(Math.max(0, s2 / k - m * m)), den = Math.max(1e-12, Math.abs(y[n - 1]));
        cv.add(str(((NamedObject) o).getPresentationName()) + ": {\"n\": " + n + ", \"ultimo\": " + num(y[n - 1]) + ", \"media100\": " + num(m)
          + ", \"desv100\": " + num(sd) + ", \"deriva100_pct\": " + num(100 * Math.abs(y[n - 1] - y[n - k]) / den)
          + ", \"oscil100_pct\": " + num(100 * (mx - mn) / den) + "}");
      }
      raw("convergencia", obj(cv));
    } catch (Exception e) { err("convergencia", e); }

    try { if (!tmp.isEmpty()) rm.removeObjects(tmp); } catch (Exception e) { }
    for (UserFieldFunction u : tmpff) try { sim.getFieldFunctionManager().remove(u); } catch (Exception e) { }

    // historiales: cada gráfico a CSV; residuales finales al JSON
    new java.io.File(dir, "reports").mkdirs();
    List<String> res = new ArrayList<String>();
    for (StarPlot pl : sim.getPlotManager().getPlots()) {
      String n = pl.getPresentationName().replaceAll("[^A-Za-z0-9_-]", "_");
      String csv = dir + "/reports/" + n + ".csv";
      try {
        pl.export(csv, ",");
        if (pl.getPresentationName().equals("Residuals")) {
          List<String> L = Files.readAllLines(Paths.get(csv));
          String[] h = L.get(0).replace("\"", "").split(","), last = L.get(L.size() - 1).split(",");
          for (int j = 1; j < h.length && j < last.length; j++) res.add(str(h[j].trim()) + ": " + last[j].trim());
        }
      } catch (Exception e) { sim.println("WARN plot " + n + ": " + e); }
    }
    raw("residuales", obj(res));
    try { Files.write(Paths.get(dir, "resultados.json"), ("{\n" + sb + "\n}\n").getBytes("UTF-8")); }
    catch (Exception e) { sim.println("WARN resultados.json " + e); }
    // el .sim resuelto, en su sitio (Design_N de .mdxruntime, que KeepTemporaryArtifacts conserva): DM con SaveOption NONE
    // (setSelected(ALL_DESIGNS) no se aplica en 2602) solo dejaba el .sim de antes de iterar. Lo usa render.ps1.
    if (GUARDAR) {
      try { sim.saveState(sim.getSessionPath()); } catch (Exception e) { sim.println("WARN guardar sim " + e); }
      try { Files.write(Paths.get(dir, "sim_origen.txt"), (sim.getSessionPath() + "\n").getBytes("UTF-8")); } catch (Exception e) { }
    }
    // SIN escenas aquí: el render por software tumbaba el solver («LLVM ERROR: IMAGE_REL_AMD64_ADDR32NB», G012, G019,
    // G027). Las escenas las exporta después `scripts/render.ps1` desde este .sim, punto a punto y con tiempo límite.
    sim.println("DOE_DESPUES " + dir);
  }
}
