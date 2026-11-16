# Re-extrae los datos completos (resultados.json versión 2: malla, paredes, convergencia…) de una geometría ya
# entregada con la macro vieja, abriendo el .sim resuelto de cada puntos\Q…\ (sim_origen.txt) en batch con
# extraer\despues.java (GUARDAR=false). Va antes de borrar los .sim que no son de Qn (2026-11-09). Un punto a la vez,
# con tiempo límite y dos intentos; al acabar escribe extraer_fin.txt (lo espera doe.py). Nunca imprime la clave.
param([string]$Dir, [int]$Np = 8, [int]$Limite = 900)
# sim_origen.txt guarda la ruta del .sim al resolverse; si luego se relanzó la bomba, reiniciar movió ese .mdxruntime a
# _intentoN\ (2026-11-09: G025 no se podaba por eso). Busca la misma ruta relativa dentro de cada _intento*.
function Resolver([string]$s, [string]$Dir) {
  if ($s -and (Test-Path $s)) { return $s }
  if (-not $s -or -not $s.StartsWith($Dir)) { return '' }
  $rel = $s.Substring($Dir.Length).TrimStart('\')
  foreach ($a in Get-ChildItem $Dir -Directory -Force -Filter '_intento*') { $c = Join-Path $a.FullName $rel; if (Test-Path $c) { return $c } }
  return ''
}
$exe = 'C:\Program Files\Siemens\21.02.007-R8\STAR-CCM+21.02.007-R8\star\bin\starccm+.bat'
$cfg = @{}; Get-Content C:\trabajo\.env | ? { $_ -match '^[A-Z_]+=' } | % { $n, $v = $_.Split('=', 2); $cfg[$n] = $v }
$lic = "-power -podkey $($cfg.STARCCM_PODKEY) -licpath $($cfg.STARCCM_LICPATH)"
$mac = Join-Path $Dir 'extraer\despues.java'
$log = Join-Path $Dir 'extraer.log'
Remove-Item (Join-Path $Dir 'extraer_fin.txt') -ErrorAction SilentlyContinue
$ok = 0; $mal = 0
foreach ($p in Get-ChildItem (Join-Path $Dir 'puntos') -Directory) {
  $rj = Join-Path $p.FullName 'resultados.json'
  if ((Test-Path $rj) -and ((Get-Content $rj -Raw) -match '"version_json"')) { $ok++; continue }   # ya en versión 2
  $so = Join-Path $p.FullName 'sim_origen.txt'
  $sim = if (Test-Path $so) { Resolver (Get-Content $so -Raw).Trim() $Dir } else { '' }
  if (-not $sim -or -not (Test-Path $sim)) { "$(Get-Date -Format s) $($p.Name) sin .sim" | Add-Content $log; $mal++; continue }
  $hecho = $false
  foreach ($intento in 1, 2) {
    $out = Join-Path $p.FullName 'extraer.out'
    $pr = Start-Process cmd.exe -ArgumentList "/c `"`"$exe`" -batch `"$mac`" `"$sim`" -np $Np $lic > `"$out`" 2>&1`"" -WindowStyle Hidden -PassThru
    if (-not $pr.WaitForExit($Limite * 1000)) { "$(Get-Date -Format s) $($p.Name) intento ${intento}: tiempo agotado" | Add-Content $log }
    Get-CimInstance Win32_Process | ? { $_.ExecutablePath -like '*STAR-CCM+*' -and $_.Name -ne 'hydra_service.exe' } |
      % { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    & (Join-Path $PSScriptRoot 'enmascarar.ps1') -Dir $p.FullName | Out-Null
    if ((Test-Path $rj) -and ((Get-Content $rj -Raw) -match '"version_json"')) { $hecho = $true; break }
    "$(Get-Date -Format s) $($p.Name) intento ${intento} sin resultados.json v2" | Add-Content $log
  }
  if ($hecho) { $ok++ } else { $mal++ }
  "$(Get-Date -Format s) $($p.Name) " + $(if ($hecho) { 'ok' } else { 'FALLO' }) | Add-Content $log
}
"ok=$ok fallos=$mal" | Set-Content (Join-Path $Dir 'extraer_fin.txt')
