# Compila macros con el javac de STAR-CCM+ 2602 contra sus jars (sin licencia, ~segundos): detecta nombres de API mal puestos.
param([string[]]$Files)
$r = 'C:\Program Files\Siemens\21.02.007-R8'
$cp = "$r\STAR-CCM+21.02.007-R8\star\lib\java\platform\modules\ext\*"
$out = Join-Path $env:TEMP "doe_javac"; New-Item -ItemType Directory -Force $out | Out-Null
foreach ($f in $Files) {
  $o = & "$r\jdk\win64\jdk21.0.8\bin\javac.exe" -nowarn -proc:none -cp $cp -d $out $f 2>&1
  if ($LASTEXITCODE -eq 0) { "OK $f" } else { "FALLA $f"; $o | Select -First 30 }
}
