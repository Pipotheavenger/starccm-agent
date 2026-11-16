# Escenas de una geometría ya terminada: para cada puntos\Q…\ abre su .sim (sim_origen.txt) en batch con escenas.java y
# deja images\*.png. Un punto a la vez, con tiempo límite; si el render se cae o se cuelga se cierra y se reintenta una
# vez. Al acabar escribe render_fin.txt en la carpeta de la geometría (lo espera doe.py). Nunca imprime la clave.
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
$mac = Join-Path $Dir 'escenas.java'
$log = Join-Path $Dir 'render.log'
Remove-Item (Join-Path $Dir 'render_fin.txt') -ErrorAction SilentlyContinue
$ok = 0; $mal = 0
foreach ($p in Get-ChildItem (Join-Path $Dir 'puntos') -Directory) {
  $img = Join-Path $p.FullName 'images'
  if ((Test-Path (Join-Path $img '_ok.txt')) -or @(Get-ChildItem $img -Filter *.png -ErrorAction SilentlyContinue).Count -gt 0) { $ok++; continue }   # ya renderizado (o con escenas de DM)
  $so = Join-Path $p.FullName 'sim_origen.txt'
  if (-not (Test-Path $so)) { "$(Get-Date -Format s) $($p.Name) sin sim_origen.txt" | Add-Content $log; $mal++; continue }
  $sim = Resolver (Get-Content $so -Raw).Trim() $Dir
  if (-not $sim) { "$(Get-Date -Format s) $($p.Name) sin .sim" | Add-Content $log; $mal++; continue }
  Set-Content -Path (Join-Path (Split-Path $sim) 'render_destino.txt') -Value $img -Encoding ascii
  $hecho = $false
  foreach ($intento in 1, 2) {
    $out = Join-Path $p.FullName 'render.out'
    $pr = Start-Process cmd.exe -ArgumentList "/c `"`"$exe`" -batch `"$mac`" `"$sim`" -np $Np $lic > `"$out`" 2>&1`"" -WindowStyle Hidden -PassThru
    if (-not $pr.WaitForExit($Limite * 1000)) { "$(Get-Date -Format s) $($p.Name) intento ${intento}: tiempo agotado" | Add-Content $log }
    # cerrar lo que quede de este render (servidor colgado tras un LLVM ERROR retiene la licencia)
    Get-CimInstance Win32_Process | ? { $_.ExecutablePath -like '*STAR-CCM+*' -and $_.Name -ne 'hydra_service.exe' } |
      % { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    & (Join-Path $PSScriptRoot 'enmascarar.ps1') -Dir $p.FullName | Out-Null
    if (Test-Path (Join-Path $img '_ok.txt')) { $hecho = $true; break }
    "$(Get-Date -Format s) $($p.Name) intento ${intento} sin _ok.txt" | Add-Content $log
  }
  if ($hecho) { $ok++ } else { $mal++ }
  "$(Get-Date -Format s) $($p.Name) " + $(if ($hecho) { 'ok' } else { 'FALLO' }) | Add-Content $log
}
"ok=$ok fallos=$mal" | Set-Content (Join-Path $Dir 'render_fin.txt')
