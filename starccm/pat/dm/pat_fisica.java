// QUE: convierte una simulación de bomba del DOE (base.sim del lote, STAR-CCM+ 2602) a MODO PAT (bomba como turbina):
//      · flujo al revés: ext_salida/outlet (brida de descarga de la bomba) = ENTRADA con caudal +${Flujo} kg/s;
//        ext_entrada/inlet (succión de la bomba) = SALIDA de presión estática 0 Pa;
//      · nuevo parámetro global rpm (magnitud, > 0): el MRF gira al revés que en bomba, ω = SIGNO·${rpm}·π/30;
//      · reportes con convención de turbina (mismos nombres que en bomba para reusar despues.java y el Excel):
//          pt_in / Q_in = entrada PAT (brida de la voluta), pt_out / Q_out = salida PAT (succión)
//          H     = (pt_in − pt_out)/(ρ g)             altura que entrega el fluido (> 0)
//          P_hid = |Q_in| g H                          potencia hidráulica disponible (W)
//          P_eje = M·ω (con signo)                     > 0 la PAT entrega potencia; ≤ 0 freno / pasó el embalamiento (runaway)
//          eta   = P_eje / P_hid                       (0 si P_hid = 0)
//          M_turb = P_eje / |ω|                        par motor en el sentido de giro (> 0 turbina, < 0 freno)
//          triángulos: 1 = entrada del rotor PAT (radio mayor), 2 = salida (radio menor);
//          H_Euler = (U1·Vu1 − U2·Vu2)/g, eta_Euler = H_Euler / H
//        Vu2_inf y factor_deslizamiento (de bomba) quedan en 0 (no se pueden borrar: los usan campos «Report: …»).
//      Parámetros: caso (lo barre DM), Flujo y rpm = expresiones del caso. No itera; borra la solución de bomba y guarda
//      encima del mismo .sim (pat.py lo corre sobre base.sim en el worker). STAR-CCM+ 2602, 2026-11-10.
// imports: star.motion.*, star.flow.*
import java.util.*;
import star.common.*;
import star.base.neo.*;
import star.base.report.*;
import star.flow.*;
import star.motion.*;

public class pat_fisica extends StarMacro {
  Simulation sim;

  ExpressionReport ex(String nom, String def) {
    ReportManager rm = sim.getReportManager();
    ExpressionReport r = rm.has(nom) && rm.getReport(nom) instanceof ExpressionReport ? (ExpressionReport) rm.getReport(nom) : rm.createReport(ExpressionReport.class);
    r.setPresentationName(nom); r.setDefinition(def);
    try { if (!sim.getMonitorManager().has(nom + " Monitor")) r.createMonitor(); } catch (Exception e) { }
    return r;
  }

  // intercambia las partes de dos reportes (p. ej. U1 ↔ U2): la entrada del rotor en PAT es la salida en bomba
  void cambiar(String a, String b) {
    ReportManager rm = sim.getReportManager();
    if (!rm.has(a) || !rm.has(b)) { sim.println("PAT_WARN falta " + a + " o " + b); return; }
    try {
      Object pa = rm.getReport(a).getClass().getMethod("getParts").invoke(rm.getReport(a));
      Object pb = rm.getReport(b).getClass().getMethod("getParts").invoke(rm.getReport(b));
      Collection<?> oa = new ArrayList<Object>((Collection<?>) pa.getClass().getMethod("getObjects").invoke(pa));
      Collection<?> ob = new ArrayList<Object>((Collection<?>) pb.getClass().getMethod("getObjects").invoke(pb));
      pa.getClass().getMethod("setObjects", Collection.class).invoke(pa, ob);
      pb.getClass().getMethod("setObjects", Collection.class).invoke(pb, oa);
      sim.println("PAT_CAMBIO " + a + " <-> " + b);
    } catch (Exception e) { sim.println("PAT_WARN cambiar " + a + "/" + b + " " + e); }
  }

  public void execute() {
    sim = getActiveSimulation();
    // casos del barrido: caso k (1…N) = caudal CASO_FLUJO[k−1] kg/s a CASO_RPM[k−1] rpm. Design Manager barre solo «caso»;
    // Flujo y rpm son expresiones de él (con «< k + 0,5»: DM puede pasar k + 1e-6 al repetir un punto suelto)
    double[] CASO_FLUJO = {{{CASO_FLUJO}}}, CASO_RPM = {{{CASO_RPM}}};
    double RHO = {{RHO}};
    String g = "9.80665";
    GlobalParameterManager gpm = sim.get(GlobalParameterManager.class);
    ScalarGlobalParameter pcaso = gpm.has("caso") ? (ScalarGlobalParameter) gpm.getObject("caso") : gpm.createGlobalParameter(ScalarGlobalParameter.class, "caso");
    pcaso.getQuantity().setValue(1.0);
    ScalarGlobalParameter prpm = gpm.has("rpm") ? (ScalarGlobalParameter) gpm.getObject("rpm") : gpm.createGlobalParameter(ScalarGlobalParameter.class, "rpm");
    StringBuilder dq = new StringBuilder(), dn = new StringBuilder();
    for (int k = 0; k < CASO_FLUJO.length; k++) {
      boolean ult = k == CASO_FLUJO.length - 1;
      dq.append(ult ? "" + CASO_FLUJO[k] : "(${caso} < " + (k + 1.5) + ") ? " + CASO_FLUJO[k] + " : (");
      dn.append(ult ? "" + CASO_RPM[k] : "(${caso} < " + (k + 1.5) + ") ? " + CASO_RPM[k] + " : (");
    }
    for (int k = 0; k < CASO_FLUJO.length - 1; k++) { dq.append(")"); dn.append(")"); }
    prpm.getQuantity().setDefinition(dn.toString());
    ((ScalarGlobalParameter) gpm.getObject("Flujo")).getQuantity().setDefinition(dq.toString());
    sim.println("PAT_CASOS " + CASO_FLUJO.length + " caso1 Flujo=" + ((ScalarGlobalParameter) gpm.getObject("Flujo")).getQuantity().getRawValue()
                + " rpm=" + prpm.getQuantity().getRawValue());
    double RPM = prpm.getQuantity().getRawValue();

    // giro: al revés que la bomba, con la magnitud del parámetro rpm
    RotatingReferenceFrame fr = null;
    for (Object o : sim.get(ReferenceFrameManager.class).getObjects()) if (o instanceof RotatingReferenceFrame) fr = (RotatingReferenceFrame) o;
    double wBomba = fr.getRotationRate().getSIValue();
    int s = wBomba < 0 ? 1 : -1;   // signo del giro PAT sobre el eje del marco
    fr.getRotationRate().setDefinitionAndUnits(s + " * ${rpm} * 3.14159265358979 / 30", sim.getUnitsManager().getUnits("radian/s"));
    sim.println("PAT_GIRO bomba " + wBomba + " rad/s -> PAT signo " + s + " · rpm " + RPM);
    String w = "(" + s + " * ${rpm} * 3.14159265358979 / 30)";   // ω con signo (rad/s)

    // fronteras: entra por la brida de la voluta, sale por la succión
    Boundary suc = sim.getRegionManager().getRegion("ext_entrada").getBoundaryManager().getBoundary("inlet");
    Boundary vol = sim.getRegionManager().getRegion("ext_salida").getBoundaryManager().getBoundary("outlet");
    vol.setBoundaryType(sim.get(ConditionTypeManager.class).get(MassFlowBoundary.class));
    vol.getValues().get(MassFlowRateProfile.class).getMethod(ConstantScalarProfileMethod.class).getQuantity().setDefinition("${Flujo}");
    suc.setBoundaryType(sim.get(ConditionTypeManager.class).get(PressureBoundary.class));
    suc.getValues().get(StaticPressureProfile.class).getMethod(ConstantScalarProfileMethod.class).getQuantity().setValueAndUnits(0.0, sim.getUnitsManager().getUnits("Pa"));
    sim.println("PAT_FRONTERAS entrada " + vol.getPresentationName() + " (caudal +Flujo), salida " + suc.getPresentationName() + " (presión 0 Pa)");

    // presión total y caudal: entrada/salida en sentido PAT
    cambiar("pt_in", "pt_out");
    cambiar("Q_in", "Q_out");
    // triángulos: 1 = entrada del rotor PAT (radio mayor)
    for (String[] p : new String[][] {{"U1", "U2"}, {"Vu1", "Vu2"}, {"Vr1", "Vr2"}, {"UVu1", "UVu2"}}) cambiar(p[0], p[1]);
    // campos de los triángulos: sentido de giro y |ω| del parámetro (en bomba iban como números fijos)
    FieldFunctionManager ffm = sim.getFieldFunctionManager();
    try {
      String r = ((UserFieldFunction) ffm.getFunction("agente_r")).getDefinition();
      String rv = r.substring(r.indexOf('(') + 1, r.lastIndexOf(')'));   // mag(cross(eje, pos − origen)) → cross(…)
      ((UserFieldFunction) ffm.getFunction("agente_U")).setDefinition("abs(" + w + ") * mag(" + rv + ")");
      ((UserFieldFunction) ffm.getFunction("agente_Vu")).setDefinition(s + " * dot(" + rv + ", $$Velocity) / max(mag(" + rv + "), 1e-12)");
      ((UserFieldFunction) ffm.getFunction("agente_UVu")).setDefinition("abs(" + w + ") * " + s + " * dot(" + rv + ", $$Velocity)");
      sim.println("PAT_CAMPOS triángulos con signo " + s + " y ω de ${rpm}");
    } catch (Exception e) { sim.println("PAT_WARN campos de triángulos " + e); }

    ex("H", "(${pt_inReport} - ${pt_outReport}) / (" + RHO + " * " + g + ")");
    ex("P_hid", "abs(${Q_inReport}) * " + g + " * ${HReport}");
    ex("P_eje", "${MReport} * " + w);
    ex("M_turb", "${P_ejeReport} / abs(" + w + ")");
    ex("eta", "(${P_hidReport} != 0) ? ${P_ejeReport} / ((${P_hidReport} != 0) ? ${P_hidReport} : 1) : 0");
    ex("H_Euler", "(${UVu1Report} - ${UVu2Report}) / " + g);
    ex("eta_Euler", "(${HReport} != 0) ? ${H_EulerReport} / ((${HReport} != 0) ? ${HReport} : 1) : 0");
    ex("omega", w);
    ReportManager rm = sim.getReportManager();
    // Vu2_inf y factor_deslizamiento son de bomba; no se pueden borrar (los usan campos «Report: …»): se dejan en 0
    for (String n : new String[] {"Vu2_inf", "factor_deslizamiento"}) if (rm.has(n)) { ex(n, "0"); sim.println("PAT_ANULADO " + n); }
    sim.getSimulationIterator().getAutoSave().setAutoSaveBatch(false);
    sim.getSolution().clearSolution();   // la solución de bomba va al revés: cada caso arranca de cero (o del caso vecino)
    sim.saveState(sim.getSessionPath());
    sim.println("PAT_OK reportes=" + rm.getObjects().size() + " guardado " + sim.getSessionPath());
  }
}
