# Lanza starccm+ 2602 en el worker con la licencia PoD leída de C:\trabajo\.env (nunca se imprime).
#   -Dir      carpeta de trabajo (cwd)
#   -Log      archivo de salida (stdout+stderr); al terminar se reescribe sin la clave ni la línea codificada de DM
#   -StarArgs argumentos de starccm+ (sin licencia); la licencia se añade sola
#   -Design   añade además -dmnoshare -passtodesign "<licencia>" (corridas de Design Manager)
#   -Wait     espera a que termine (si no, solo lanza y devuelve el PID)
param([string]$Dir, [string]$Log, [string]$StarArgs, [switch]$Design, [switch]$Wait)
$ErrorActionPreference = 'Stop'
$exe = 'C:\Program Files\Siemens\21.02.007-R8\STAR-CCM+21.02.007-R8\star\bin\starccm+.bat'
$cfg = @{}; Get-Content C:\trabajo\.env | ? { $_ -match '^[A-Z_]+=' } | % { $n, $v = $_.Split('=', 2); $cfg[$n] = $v }
$lic = "-power -podkey $($cfg.STARCCM_PODKEY) -licpath $($cfg.STARCCM_LICPATH)"
$a = "$StarArgs $lic"
if ($Design) { $a += " -dmnoshare -passtodesign `"$lic`"" }
Set-Location $Dir
$p = Start-Process cmd.exe -ArgumentList "/c `"`"$exe`" $a > `"$Log`" 2>&1`"" -WorkingDirectory $Dir -WindowStyle Hidden -PassThru
"PID $($p.Id)"
if ($Wait) {
  $p.WaitForExit()
  $k = $cfg.STARCCM_PODKEY
  (Get-Content $Log) | ? { $_ -notmatch 'xencoded-passtodesign' } | % { $_.Replace($k, '****') } | Set-Content $Log
  & (Join-Path $PSScriptRoot 'enmascarar.ps1') -Dir $Dir   # DM la deja en cada Design_N.log
  "RC $($p.ExitCode)"
}
