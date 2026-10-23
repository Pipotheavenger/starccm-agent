# bootstrap.ps1 — deja el PC Windows con CFturbo listo para el agente.
# Correr en PowerShell dentro de esta carpeta:  powershell -ExecutionPolicy Bypass -File bootstrap.ps1
$ErrorActionPreference = "Stop"

function Log($m) { Write-Host "`n==> $m" -ForegroundColor Green }

# ---------------------------------------------------------------- CFturbo
$exe = $env:CFTURBO_EXE
if (-not $exe) {
  $exe = Get-ChildItem "C:\Program Files\CFturbo*\cfturbo.exe" -ErrorAction SilentlyContinue |
         Sort-Object FullName | Select-Object -Last 1 -ExpandProperty FullName
}
if (-not $exe) { throw "No encuentro cfturbo.exe. Define `$env:CFTURBO_EXE y vuelve a correr." }
Log "CFturbo: $exe"

# ---------------------------------------------------------------- Python
$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) { winget install -e --id Python.Python.3.12 --silent; $env:Path = [Environment]::GetEnvironmentVariable("Path","User") + ";" + $env:Path }
python --version
if (-not (Test-Path .venv)) { python -m venv .venv }
.\.venv\Scripts\pip install -q --upgrade pip
.\.venv\Scripts\pip install -q "mcp[cli]" fastapi "uvicorn[standard]"

# ---------------------------------------------------------------- Claude Code
if (-not (Get-Command claude -ErrorAction SilentlyContinue)) {
  Log "Instalando Claude Code"
  irm https://claude.ai/install.ps1 | iex
  $env:Path = [Environment]::GetEnvironmentVariable("Path","User") + ";" + $env:Path
}
claude --version

# ---------------------------------------------------------------- git
if (-not (Get-Command git -ErrorAction SilentlyContinue)) { winget install -e --id Git.Git --silent }
if (-not (Test-Path .git)) { git init -q }

# ---------------------------------------------------------------- env + mcp
[Environment]::SetEnvironmentVariable("CFTURBO_EXE", $exe, "User")
$env:CFTURBO_EXE = $exe
New-Item -ItemType Directory -Force work, recipes, projects | Out-Null

$venvPy = (Resolve-Path .\.venv\Scripts\python.exe).Path
$mcp = @{ mcpServers = @{ cfturbo = @{ command = $venvPy; args = @((Resolve-Path .\mcp_server.py).Path) } } }
$mcp | ConvertTo-Json -Depth 5 | Set-Content .mcp.json -Encoding UTF8

Log "Selftest del MCP"
& $venvPy mcp_server.py --selftest

Log "Listo"
Write-Host @"

Siguiente:
  1. Copia una bomba base de CFturbo como projects\<bomba>\<bomba>.cft (no hace falta plantilla batch)
  2. claude            (login la primera vez)
  3. interfaz: .venv\Scripts\python -m uvicorn ui.server:app --port 8765  ->  http://localhost:8765
  4. sigue PRIMER-PROMPT.md
"@
