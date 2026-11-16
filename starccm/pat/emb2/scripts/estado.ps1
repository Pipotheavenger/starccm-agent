# Estado de los barridos de Design Manager de este worker, en JSON (lo lee doe.py estado / el tablero). Nunca imprime la clave.
param([string]$Raiz = 'C:\trabajo\DOE-2026-11_PAT1')
$ErrorActionPreference = 'SilentlyContinue'
$k = ((Get-Content C:\trabajo\.env | ? { $_ -match '^STARCCM_PODKEY=' }) -split '=', 2)[1]
function limpio($s) { if ($k) { $s.Replace($k, '****') } else { $s } }
$todos = @(Get-CimInstance Win32_Process)
# Huérfanos: servidores de diseño (star-ccm+.exe con -xmpidriver) de un diseño ya terminado que no se cerraron. Retienen
# la licencia PoD de la IP y los diseños siguientes fallan con «Failed to get all licenses» (G012, 2026-11-04). Con un
# solo job por worker solo puede haber UN grupo de diseño vivo: se cierran los grupos anteriores al más nuevo.
$cerrados = 0
$grupos = @($todos | ? { $_.Name -eq 'star-ccm+.exe' -and $_.CommandLine -match '-xmpidriver' } | Group-Object { ([regex]::Match($_.CommandLine, 'tmpdir "([^"]+)"')).Groups[1].Value } |
  Sort-Object { ($_.Group | Measure-Object { $_.CreationDate.Ticks } -Minimum).Minimum })
if ($grupos.Count -gt 1) {
  foreach ($gr in $grupos[0..($grupos.Count - 2)]) {
    $ini = ($gr.Group | Measure-Object { $_.CreationDate.Ticks } -Minimum).Minimum
    if (((Get-Date).Ticks - $ini) / 1e7 -gt 600) { $gr.Group | % { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue; $cerrados++ } }
  }
}
# (2026-11-05: el cierre por «LLVM ERROR» se quitó: DM ya no renderiza; las escenas van en render.ps1, que cierra lo suyo)
$procs = @($todos | ? { $_.ExecutablePath -like '*STAR-CCM+*' -and $_.Name -ne 'hydra_service.exe' })
$out = [ordered]@{ host = $env:COMPUTERNAME; hora = (Get-Date -Format s); procesos_star = $procs.Count; huerfanos_cerrados = $cerrados;
  cpu_pct = [math]::Round((Get-CimInstance Win32_Processor | Measure-Object LoadPercentage -Average).Average);
  c_libre_gb = [math]::Round((Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='C:'").FreeSpace / 1GB); geometrias = @() }
foreach ($g in Get-ChildItem $Raiz -Directory) {
  $log = Join-Path $g.FullName 'correr.log'
  $cola = @(); if (Test-Path $log) { $cola = Get-Content $log -Tail 400 | ? { $_ -notmatch 'xencoded|podkey' } | % { limpio $_ } }
  $dis = @()
  foreach ($pf in Get-ChildItem $g.FullName -Recurse -Filter progreso.txt | ? { $_.FullName -notmatch '\\_intento' }) {
    $dd = $pf.DirectoryName
    $p = @{}; Get-Content $pf.FullName | ? { $_ -match '=' } | % { $a, $b = $_.Split('=', 2); $p[$a] = $b }
    $it = $null; $hdr = $null; $fila = $null
    $lg = Get-ChildItem $dd -Filter *.log | Sort LastWriteTime -Desc | Select -First 1
    if ($lg) {
      foreach ($l in (Get-Content $lg.FullName -Tail 300)) {
        if ($l -match '^\s*Iteration\s') { $hdr = ($l.Trim() -split '\s{2,}') }
        elseif ($l -match '^\s*\d+(\s+[-+0-9.eE]+){2,}\s*$') { $fila = ($l.Trim() -split '\s+') }
      }
    }
    $val = [ordered]@{}
    if ($hdr -and $fila) { for ($i = 0; $i -lt [math]::Min($hdr.Count, $fila.Count); $i++) { $val[$hdr[$i]] = $fila[$i] } }
    $dis += [ordered]@{ dir = $dd.Substring($g.FullName.Length); it0 = $p.it0; meta = $p.meta; Flujo = $p.Flujo; inicio = $p.inicio;
      ultima = $val; log_mod = if ($lg) { $lg.LastWriteTime.ToString('s') } else { $null } }
  }
  # puntos terminados: despues.java los deja en <geometría>\puntos\Q…_m3h\ (DM limpia sus carpetas de diseño)
  $pts = @()
  foreach ($rj in Get-ChildItem (Join-Path $g.FullName 'puntos') -Recurse -Filter resultados.json) {
    $pts += [ordered]@{ dir = $rj.Directory.Name; imagenes = @(Get-ChildItem (Join-Path $rj.DirectoryName 'images') -Filter *.png).Count;
      fin = $rj.LastWriteTime.ToString('s');
      resultados = (Get-Content $rj.FullName -Raw | ConvertFrom-Json) }
  }
  $out.geometrias += [ordered]@{ id = $g.Name; log_mod = if (Test-Path $log) { (Get-Item $log).LastWriteTime.ToString('s') } else { $null };
    log = @($cola | ? { $_ -match 'Design|design|ERROR|rror|DOE_|xception|Running|finished|complete' } | Select -Last 25);
    dmprj = Test-Path (Join-Path $g.FullName "$($g.Name).dmprj"); disenos = $dis; puntos = $pts;
    # el barrido sigue vivo mientras viva su lanzador (star.ps1 -Dir <esta carpeta>)
    dm_vivo = [bool]($todos | ? { $_.Name -eq 'powershell.exe' -and $_.CommandLine -match 'star\.ps1' -and $_.CommandLine -like "*$($g.FullName)*" });
    fallidos = @($cola | ? { $_ -match 'Design \d+ : -1e\+99' }).Count;
    render_fin = $(if (Test-Path (Join-Path $g.FullName 'render_fin.txt')) { (Get-Content (Join-Path $g.FullName 'render_fin.txt') -Raw).Trim() } else { $null });
    extraer_fin = $(if (Test-Path (Join-Path $g.FullName 'extraer_fin.txt')) { (Get-Content (Join-Path $g.FullName 'extraer_fin.txt') -Raw).Trim() } else { $null }) }
}
& (Join-Path $PSScriptRoot 'enmascarar.ps1') -Dir $Raiz -MinEdad 60 | Out-Null   # logs de diseño ya escritos
$out | ConvertTo-Json -Depth 6 -Compress
