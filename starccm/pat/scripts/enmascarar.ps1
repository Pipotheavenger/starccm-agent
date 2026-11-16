# Quita la clave PoD de los archivos de texto bajo -Dir (DM la escribe en cada Design_N.log al lanzar el diseño).
# -MinEdad: solo archivos sin escribir hace al menos esos segundos (no tocar logs que el solver aún escribe).
param([string]$Dir, [int]$MinEdad = 0)
$k = ((Get-Content C:\trabajo\.env | ? { $_ -match '^STARCCM_PODKEY=' }) -split '=', 2)[1]
if (-not $k) { return }
$n = 0
Get-ChildItem $Dir -Recurse -File -ErrorAction SilentlyContinue |
  ? { $_.Length -lt 50MB -and $_.Extension -notin '.sim', '.png', '.dmprj' -and ((Get-Date) - $_.LastWriteTime).TotalSeconds -ge $MinEdad } |
  ? { Select-String -Path $_.FullName -SimpleMatch $k -Quiet } | % {
    try { $t = [IO.File]::ReadAllText($_.FullName); [IO.File]::WriteAllText($_.FullName, $t.Replace($k, '****')); $n++ } catch { }
  }
"enmascarados=$n"
