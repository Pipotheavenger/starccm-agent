# Batch mínimo que CFturbo 2026.1.1 acepta (Export StarCCM + Save), verificado 2026-10-23

Sin `<Updates>` (solo se aceptan con plantilla de la GUI; los cambios se hacen editando el `.cft`).
Rutas absolutas con `\`. En `ExportComponents` cada `<Value>` lleva `Caption="[Nombre]"` (el
`Caption` del componente en el `.cft`) y valor = `Index`+1. **Sin `Caption` solo sale el primer
componente.** Interfaces útiles: `StarCCM` (STEP + .cfturbo-ccm + .java) y `OpenFOAM` (STL por
superficie); `General` solo da .geo-xml salvo que se configure en la GUI.

```xml
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<CFturboFile Version="2026.1">
  <CFturboBatchProject InputFile="C:\ruta\bomba.cft">
    <Updates/>
    <Output/>
    <BatchAction Name="Export">
      <WorkingDir>C:\ruta\salida</WorkingDir>
      <BaseFileName>bomba_v1</BaseFileName>
      <ExportInterface Type="Enum">StarCCM</ExportInterface>
      <ExportComponents Type="Array1" Count="3">
        <Value Type="Integer" Caption="[Stator_1]" Index="0">1</Value>
        <Value Type="Integer" Caption="[Impeller_1]" Index="1">2</Value>
        <Value Type="Integer" Caption="[Volute_1]" Index="2">3</Value>
      </ExportComponents>
    </BatchAction>
    <BatchAction Name="Save">
      <OutputFile>C:\ruta\salida\bomba_v1.cft</OutputFile>
    </BatchAction>
  </CFturboBatchProject>
</CFturboFile>
```

Comando: `"C:\Program Files\CFturbo 2026.1.1\CFturbo.exe" -batch bomba.cft-batch -verbose -log bomba.log`

El `.cft-res` devuelve cada `BatchAction` con `State="success"` y, en `ExportComponents`, el
`Caption` real de cada componente exportado. Formatos internos del export General vistos en el
ejecutable: enfSTEP, enfIGES, enfSTL, enfParasolid, enfBREP, ggfXML, ggfTXT.
