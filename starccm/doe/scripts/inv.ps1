$ErrorActionPreference='SilentlyContinue'
$o=[ordered]@{}
$o.host=$env:COMPUTERNAME
$c=Get-CimInstance Win32_Processor
$o.cpu=($c | select -First 1).Name.Trim()
$o.cores=($c | Measure-Object NumberOfCores -Sum).Sum
$o.threads=($c | Measure-Object NumberOfLogicalProcessors -Sum).Sum
$o.ram_gb=[math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory/1GB,1)
foreach($d in 'C','D'){ $v=Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='${d}:'"; if($v -and $v.Size){ $o["${d}_libre_gb"]=[math]::Round($v.FreeSpace/1GB); $o["${d}_total_gb"]=[math]::Round($v.Size/1GB) } else { $o["${d}_libre_gb"]=$null; $o["${d}_tipo"]= if($v){$v.DriveType}else{'no existe'} } }
$keys='HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*','HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*'
$o.star=@(Get-ItemProperty $keys | ? { $_.DisplayName -match 'STAR-CCM|Simcenter STAR|STAR-View' } | select DisplayName,DisplayVersion,InstallLocation,UninstallString)
$t=New-Object Net.Sockets.TcpClient
try { $a=$t.BeginConnect('flex.cd-adapco.com',1999,$null,$null); $o.flex1999=$a.AsyncWaitHandle.WaitOne(8000) -and $t.Connected } finally { $t.Close() }
$o | ConvertTo-Json -Depth 4 -Compress
