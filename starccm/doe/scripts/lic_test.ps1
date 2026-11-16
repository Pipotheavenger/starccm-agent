# Prueba de licencia PoD: servidor vacio, espera la licencia, apaga SOLO el solver. Nunca imprime la clave.
param([int]$Port=47900, [int]$Wait=240, [int]$Hold=0)
$ErrorActionPreference='Stop'
$exe='C:\Program Files\Siemens\21.02.007-R8\STAR-CCM+21.02.007-R8\star\bin\starccm+.bat'
if(-not (Test-Path $exe)){ "ERROR sin lanzador: $exe"; exit 1 }
$cfg=@{}; Get-Content C:\trabajo\.env | ? { $_ -match '^[A-Z_]+=' } | % { $n,$v=$_.Split('=',2); $cfg[$n]=$v }
$key=$cfg.STARCCM_PODKEY; $np=$cfg.STARCCM_NP
$vivos = Get-CimInstance Win32_Process | ? { ($_.ExecutablePath -like '*STAR-CCM+*' -and $_.Name -ne 'hydra_service.exe') }
if($vivos){ "ERROR ya hay STAR-CCM+ vivo: " + (($vivos | % { "$($_.Name)/$($_.ProcessId)" }) -join ','); exit 1 }
$log='C:\trabajo\lic_test.log'; Remove-Item $log -ErrorAction SilentlyContinue
$t0=Get-Date
$sargs="-server -port $Port -np $np -power -podkey $key -licpath $($cfg.STARCCM_LICPATH)"
$p=Start-Process cmd.exe -ArgumentList "/c `"`"$exe`" $sargs > `"$log`" 2>&1`"" -WindowStyle Hidden -PassThru
$res='TIMEOUT'
while(((Get-Date)-$t0).TotalSeconds -lt $Wait){
  Start-Sleep 3
  $txt = if(Test-Path $log){ Get-Content $log -Raw } else { '' }
  if($txt -match 'Server::start|listening|Starting local server'){ $res='OK'; break }
  if($txt -match 'Failed to get all licenses|license.*(denied|error|fail)|Unable to checkout'){ $res='LICENCIA_FALLA'; break }
  if($p.HasExited){ $res="SALIO rc=$($p.ExitCode)"; break }
}
$seg=[math]::Round(((Get-Date)-$t0).TotalSeconds,1)
if($res -eq 'OK' -and $Hold){ Start-Sleep $Hold }; $vivoAl=$(-not $p.HasExited); $hok=Get-Date -Format HH:mm:ss
$lineas = Get-Content $log -ErrorAction SilentlyContinue | % { $_.Replace($key,'****') } | ? { $_ -match 'licen|PoD|power|Server|error|fail|version|STAR-CCM\+ ' } | Select -First 15
# apagar solo el solver: todo proceso de STAR-CCM+ y el cmd lanzador
$mios = Get-CimInstance Win32_Process | ? { ($_.ExecutablePath -like '*STAR-CCM+*' -and $_.Name -ne 'hydra_service.exe') -or $_.ProcessId -eq $p.Id }
$mios | % { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Start-Sleep 3
$quedan = @(Get-CimInstance Win32_Process | ? { ($_.ExecutablePath -like '*STAR-CCM+*' -and $_.Name -ne 'hydra_service.exe') }).Count
if(Test-Path $log){ (Get-Content $log) | % { $_.Replace($key,'****') } | Set-Content $log }
"RESULTADO $res segundos=$seg vivo_tras_hold=$vivoAl apagado=$hok procesos_cerrados=$(@($mios).Count) quedan=$quedan"
$lineas


