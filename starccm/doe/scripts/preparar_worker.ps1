# Deja un worker nuevo listo para el DOE (2026-11-11, para .207, .218 y .230). Correr UNA vez en cada máquina, entrando
# por RDP como el usuario administrador «starccm», en PowerShell «Ejecutar como administrador»:
#     powershell -ExecutionPolicy Bypass -File preparar_worker.ps1
# Hace: OpenSSH Server (arranque automático), firewall para SSH (22) y ping, la llave pública de la .72 en
# administrators_authorized_keys con los permisos que exige sshd, y la carpeta C:\trabajo. No toca la licencia: el .env lo
# copia la .72 por SSH después. No pide ni guarda contraseñas.
$ErrorActionPreference = 'Stop'
$llave = 'ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIHKvSd5DcFmO266ty7/Yfiqk27bL4NyjhDx9nWhiPIkS investigacion@server-inv-0013'

$cap = Get-WindowsCapability -Online | ? Name -like 'OpenSSH.Server*'
if ($cap.State -ne 'Installed') { Add-WindowsCapability -Online -Name $cap.Name | Out-Null }
Set-Service sshd -StartupType Automatic
Start-Service sshd
if (-not (Get-NetFirewallRule -Name 'OpenSSH-Server-In-TCP' -ErrorAction SilentlyContinue)) {
  New-NetFirewallRule -Name 'OpenSSH-Server-In-TCP' -DisplayName 'OpenSSH Server (sshd)' -Enabled True -Direction Inbound -Protocol TCP -Action Allow -LocalPort 22 | Out-Null
}
Enable-NetFirewallRule -Name 'OpenSSH-Server-In-TCP'
Get-NetFirewallRule -ErrorAction SilentlyContinue | ? { $_.DisplayName -like '*Echo Request*ICMPv4-In*' } | Enable-NetFirewallRule

$ak = 'C:\ProgramData\ssh\administrators_authorized_keys'
if (-not (Test-Path $ak) -or -not (Select-String -Path $ak -SimpleMatch $llave -Quiet)) { Add-Content -Path $ak -Value $llave -Encoding ascii }
icacls $ak /inheritance:r /grant 'Administrators:F' /grant 'SYSTEM:F' | Out-Null   # sshd ignora el archivo con otros permisos
New-Item -ItemType Directory -Force C:\trabajo | Out-Null

$star = Test-Path 'C:\Program Files\Siemens\21.02.007-R8\STAR-CCM+21.02.007-R8\star\bin\starccm+.bat'
"sshd: $((Get-Service sshd).Status)  llave: OK  C:\trabajo: OK  STAR-CCM+ 2602: $(if ($star) { 'instalado' } else { 'FALTA' })"
