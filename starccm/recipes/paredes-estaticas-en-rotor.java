// QUE: pared estática (marco de laboratorio) dentro de una región MRF: carcasas CasingHub/CasingShroud de CFturbo; imports star.motion.*; verificado BombaNQ10 2026-10-28
// VERSION: 19.06.009-R8
// FECHA: 2026-10-28
// imports: star.motion.*
Region rot = sim.getRegionManager().getRegion("rotor");
for (String n : new String[]{"CasingHub", "CasingShroud"}) {
  Boundary b = rot.getBoundaryManager().getBoundary(n);
  b.getConditions().get(WallReferenceFrameOption.class).setSelected(ReferenceFrameOption.Type.LAB_FRAME);
  sim.println("STATIC\t" + n + "\t" + b.getConditions().get(WallReferenceFrameOption.class).getSelectedElement());
}
