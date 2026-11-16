# Video (pat/transitorio/video.java) sobre transitorio_fin.sim: una vuelta más con fotogramas; video.java NO guarda el .sim.
# Deja video.out (enmascarado), frames*.png y video_fin.txt en -Out. Nunca imprime la clave.
param([string]$Sim, [string]$Out, [int]$Np = 44, [int]$Limite = 43200)
$exe = 'C:\Program Files\Siemens\21.02.007-R8\STAR-CCM+21.02.007-R8\star\bin\starccm+.bat'
$cfg = @{}; Get-Content C:\trabajo\.env | ? { $_ -match '^[A-Z_]+=' } | % { $n, $v = $_.Split('=', 2); $cfg[$n] = $v }
$lic = "-power -podkey $($cfg.STARCCM_PODKEY) -licpath $($cfg.STARCCM_LICPATH)"
Remove-Item (Join-Path $Out 'video_fin.txt') -ErrorAction SilentlyContinue
$copia = Join-Path $Out 'transitorio_fin.sim'
$o = Join-Path $Out 'video.out'
$pr = Start-Process cmd.exe -ArgumentList "/c `"`"$exe`" -batch `"$(Join-Path $Out 'video.java')`" `"$copia`" -np $Np $lic > `"$o`" 2>&1`"" -WindowStyle Hidden -PassThru
$ok = $pr.WaitForExit($Limite * 1000)
Get-CimInstance Win32_Process | ? { $_.ExecutablePath -like '*STAR-CCM+*' -and $_.Name -ne 'hydra_service.exe' } | % { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
(Get-Content $o) | % { $_.Replace($cfg.STARCCM_PODKEY, '****') } | Set-Content $o
"ok=$ok" | Set-Content (Join-Path $Out 'video_fin.txt')
