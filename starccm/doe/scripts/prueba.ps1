# Prueba de convergencia (dm/prueba.java) sobre una COPIA del .sim resuelto de Qn de una geometría: así el original no
# cambia aunque STAR autoguarde. Deja prueba.out (enmascarado) y prueba_fin.txt en -Out y borra la copia al acabar.
# 2026-11-10 (nq 10–25 sin converger). Nunca imprime la clave.
param([string]$Dir, [string]$Out, [double]$Qn, [int]$Np = 44, [int]$Limite = 21600)
$exe = 'C:\Program Files\Siemens\21.02.007-R8\STAR-CCM+21.02.007-R8\star\bin\starccm+.bat'
$cfg = @{}; Get-Content C:\trabajo\.env | ? { $_ -match '^[A-Z_]+=' } | % { $n, $v = $_.Split('=', 2); $cfg[$n] = $v }
$lic = "-power -podkey $($cfg.STARCCM_PODKEY) -licpath $($cfg.STARCCM_LICPATH)"
Remove-Item (Join-Path $Out 'prueba_fin.txt') -ErrorAction SilentlyContinue
$cerca = Get-ChildItem "$Dir\puntos" -Directory | Sort-Object { [math]::Abs([double]::Parse(($_.Name -replace '^Q|_m3h$', ''), [cultureinfo]::InvariantCulture) - $Qn) } | Select -First 1
$sim = (Get-Content (Join-Path $cerca.FullName 'sim_origen.txt') -Raw).Trim()
if (-not (Test-Path $sim)) {   # reiniciar lo movió a _intentoN\
  $rel = $sim.Substring($Dir.Length).TrimStart('\')
  $sim = @(Get-ChildItem $Dir -Directory -Force -Filter '_intento*' | % { Join-Path $_.FullName $rel } | ? { Test-Path $_ })[0]
}
if (-not $sim) { 'sin .sim de Qn' | Set-Content (Join-Path $Out 'prueba_fin.txt'); return }
$copia = Join-Path $Out 'prueba.sim'
Copy-Item $sim $copia -Force
$o = Join-Path $Out 'prueba.out'
$pr = Start-Process cmd.exe -ArgumentList "/c `"`"$exe`" -batch `"$(Join-Path $Out 'prueba.java')`" `"$copia`" -np $Np $lic > `"$o`" 2>&1`"" -WindowStyle Hidden -PassThru
$ok = $pr.WaitForExit($Limite * 1000)
Get-CimInstance Win32_Process | ? { $_.ExecutablePath -like '*STAR-CCM+*' -and $_.Name -ne 'hydra_service.exe' } | % { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
& (Join-Path $PSScriptRoot 'enmascarar.ps1') -Dir $Out | Out-Null
Get-ChildItem $Out -Filter 'prueba*.sim*' | Remove-Item -Force -ErrorAction SilentlyContinue
"ok=$ok sim=$sim" | Set-Content (Join-Path $Out 'prueba_fin.txt')
