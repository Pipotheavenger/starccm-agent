// PAT (2026-11-10): copia de ../../doe/dm/crear_estudio.java con el parámetro «caso» (1…32 = caudal × rpm) en vez de Flujo.
// QUE: crea el proyecto de Design Manager de una geometrÃ­a: estudio Sweep Â«BarridoÂ» sobre SIM, parÃ¡metro global Flujo
//      (kg/s) DISCRETO con FLUJOS en ese orden, respuestas = todos los reportes, 1 job a la vez con NP procesos y reuso de
//      la soluciÃ³n del diseÃ±o terminado mÃ¡s cercano; macros ANTES (antes de correr) y DESPUES (antes de resultados).
//      Guarda PROJ (.dmprj) e imprime lo que quedÃ³. STAR-CCM+ 2602 (21.02.007), 2026-11-04.
// Uso: starccm+ -dmproject -batch crear_estudio.java <licencia>
import java.util.*;
import star.common.*;
import star.base.neo.*;
import star.mdx.*;

public class crear_estudio extends MdxMacro {
  public void execute() {
    String SIM = "{{SIM}}", PROJ = "{{PROJ}}", ANTES = "{{ANTES}}", DESPUES = "{{DESPUES}}";
    double[] FLUJOS = {{{FLUJOS}}};
    int NP = {{NP}};
    MdxProject p = getActiveMdxProject();
    try {
      p.getReferenceSimulationManager().readReferenceSimulation(SIM);
      MdxReferenceSimulation ref = p.getReferenceSimulationManager().getReferenceSimulations().iterator().next();
      p.println("DM ref " + ref.getPresentationName() + " " + ref.getFilePath());

      MdxDesignStudy st = p.getDesignStudyManager().createDesignStudy();
      st.setPresentationName("Barrido");
      st.getReferenceSimulationGroup().setObjects(ref);
      st.setStudyType(p.getDesignStudyTypeManager().get(MdxSweepStudyType.class));

      // los parÃ¡metros globales de la sim no entran solos al estudio: aÃ±adir Flujo desde los de referencia
      MdxStudyParameterManager pm = st.getStudyParameters();
      // vienen dentro de la carpeta Â«Simulation ParametersÂ»: recorrer el Ã¡rbol
      MdxParameter refQ = null;
      Deque<Object> pila = new ArrayDeque<Object>(ref.getReferenceParameterManager().getObjects());
      while (!pila.isEmpty()) {
        Object o = pila.pop();
        String n = o instanceof ClientServerObject ? ((ClientServerObject) o).getPresentationName() : o.toString();
        p.println("DM refparam " + n + " " + o.getClass().getSimpleName());
        if (o instanceof MdxParameter && n.equals("caso")) refQ = (MdxParameter) o;
        if (o instanceof ClientServerObject) try { pila.addAll(((ClientServerObject) o).getChildren()); } catch (Exception e) { }
      }
      if (refQ == null) throw new RuntimeException("la sim no tiene el parÃ¡metro global Flujo");
      // sin esto DM lo da por Â«UnknownÂ» â†’ supone que afecta a la malla y no reusa malla ni soluciÃ³n entre diseÃ±os
      refQ.setSimulationEffect(SimulationEffect.SOLVER);
      pm.addReferenceParameter(refQ);
      for (MdxStudyParameterBase b : pm.getStudyParameterBaseCollection()) p.println("DM param " + b.getPresentationName() + " " + b.getClass().getSimpleName());
      MdxStudyParameter q = (MdxStudyParameter) pm.getStudyParameterBase("caso");
      q.setParameterType(MdxStudyParameterBase.ParameterType.DISCRETE);
      q.getDiscreteQuantity().setArray(new DoubleVector(FLUJOS));
      p.println("DM Flujo " + q.getDiscreteParameterValue().getQuantities());

      MdxStudyResponseManager rm = st.getStudyResponses();
      for (Object o : ref.getReferenceReportManager().getObjects())
        if (o instanceof MdxReferenceReport) rm.addReferenceReport((MdxReferenceReport) o);
      for (MdxStudyResponse r : rm.getStudyResponses()) p.println("DM resp " + r.getPresentationName());

      MdxLaunchSettings ls = st.getStudySettings().getLaunchSettings();
      ls.setNumComputeProcesses(NP);
      ls.setNumSimultaneousJobs(1);
      ls.setReuseDesignEnabled(true);
      ls.setClearHistoryEnabled(true);   // contador a 0 en cada diseÃ±o: antes_correr pone Maximum Steps = ITS
      // por defecto NONE: DM borra el .sim de cada diseÃ±o al terminar y el reuso arranca siempre desde la base
      MdxSaveOption so = ls.getSaveOption();
      so.setSelected(MdxSaveOption.Type.ALL_DESIGNS);
      ls.setSaveOptionInput(so.getSelectedInput());   // solo con setSelected seguía en NONE
      p.setKeepTemporaryArtifacts(true);               // y que no borre las carpetas de diseño (.mdxruntime)
      p.println("DM keepTemp " + p.getKeepTemporaryArtifacts());
      p.println("DM guardar " + ls.getSaveOption().getSelectedElement() + "/" + ls.getSaveOption().getSelectedInput() + " reuso " + ls.getReuseDesignEnabled() + " clear " + ls.getClearHistoryEnabled());
      ls.setSaveLogs(true);
      MdxMacroFileManager mf = st.getStudySettings().getMacroFiles();
      mf.createMacroFile(MdxMacroFile.MacroInsertionPoint.BEFORE_RUNNING, ANTES);
      mf.createMacroFile(MdxMacroFile.MacroInsertionPoint.BEFORE_RESULTS, DESPUES);
      for (MdxMacroFile m : mf.getMacroFiles()) p.println("DM macro " + m.getMacroInsertionPoint() + " " + m.getFilePath());

      p.saveState(PROJ);
      p.println("DM_OK " + PROJ + " diseÃ±os " + FLUJOS.length);
    } catch (Exception e) {
      p.println("DM_ERROR " + e);
      for (StackTraceElement s : e.getStackTrace()) p.println("  at " + s);
    }
  }
}
