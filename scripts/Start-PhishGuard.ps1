<#
.SYNOPSIS
    Start the PhishGuard server (if it isn't already) and open the dashboard.

.DESCRIPTION
    Idempotent: if the API already answers on the port, this just opens the
    browser and exits. That matters because it is wired to a desktop shortcut,
    a Start-menu entry, and a logon task — all of which a user may trigger
    while it is already running. Starting a second uvicorn would mean two
    pollers racing to scan the same inbox.

    The server is launched with pythonw.exe rather than python.exe so no
    console window appears. Its output goes to backend/data/*.log, and its
    process id to backend/data/phishguard.pid so Stop-PhishGuard can find it.

.PARAMETER Port
    Port to serve on. Default 8000.

.PARAMETER NoBrowser
    Start the server but do not open the dashboard. Used by the logon task,
    which should not hijack the screen every time you sign in.

.EXAMPLE
    .\Start-PhishGuard.ps1
    .\Start-PhishGuard.ps1 -Port 8123 -NoBrowser
#>
[CmdletBinding()]
param(
    [int]$Port = 8000,
    [switch]$NoBrowser
)

$ErrorActionPreference = 'Stop'

$Root    = Split-Path -Parent $PSScriptRoot
$Backend = Join-Path $Root 'backend'
$DataDir = Join-Path $Backend 'data'
$PythonW = Join-Path $Backend '.venv\Scripts\pythonw.exe'
$PidFile = Join-Path $DataDir 'phishguard.pid'
$Url     = "http://localhost:$Port/"
$Health  = "http://127.0.0.1:$Port/api/health"

function Test-PhishGuardUp {
    try {
        $r = Invoke-WebRequest -Uri $Health -UseBasicParsing -TimeoutSec 2
        return $r.StatusCode -eq 200
    } catch {
        return $false
    }
}

# --- Already running? Just open it. ---------------------------------------
if (Test-PhishGuardUp) {
    Write-Host "PhishGuard is already running on port $Port."
    if (-not $NoBrowser) { Start-Process $Url }
    exit 0
}

# --- Preflight -------------------------------------------------------------
if (-not (Test-Path $PythonW)) {
    Write-Error @"
Python environment not found at:
  $PythonW

Create it first:
  cd $Backend
  python -m venv .venv
  .venv\Scripts\python.exe -m pip install -r requirements.txt
"@
    exit 1
}

if (-not (Test-Path $DataDir)) {
    New-Item -ItemType Directory -Path $DataDir | Out-Null
}

if (-not (Test-Path (Join-Path $Backend 'credentials.json'))) {
    Write-Warning "backend\credentials.json is missing - the poller cannot reach Gmail."
    Write-Warning "The dashboard will still start. See docs\SETUP.md for the OAuth steps."
}

# --- Launch ----------------------------------------------------------------
# Working directory must be backend\ - .env, data\, credentials.json and
# token.json are all resolved relative to it.
$proc = Start-Process -FilePath $PythonW `
    -ArgumentList @(
        '-m', 'uvicorn', 'app.main:app',
        '--host', '127.0.0.1',
        '--port', "$Port"
    ) `
    -WorkingDirectory $Backend `
    -WindowStyle Hidden `
    -RedirectStandardOutput (Join-Path $DataDir 'phishguard.out.log') `
    -RedirectStandardError  (Join-Path $DataDir 'phishguard.log') `
    -PassThru

$proc.Id | Set-Content -Path $PidFile -Encoding ASCII

# --- Wait for it to answer -------------------------------------------------
Write-Host -NoNewline "Starting PhishGuard on port $Port"
$deadline = (Get-Date).AddSeconds(30)
while ((Get-Date) -lt $deadline) {
    if (Test-PhishGuardUp) {
        Write-Host " - ready."
        if (-not $NoBrowser) { Start-Process $Url }
        exit 0
    }
    if ($proc.HasExited) {
        Write-Host ""
        Write-Error "The server exited immediately (code $($proc.ExitCode)). Last log lines:"
        Get-Content (Join-Path $DataDir 'phishguard.log') -Tail 20 -ErrorAction SilentlyContinue
        exit 1
    }
    Write-Host -NoNewline "."
    Start-Sleep -Milliseconds 500
}

Write-Host ""
Write-Error "Timed out after 30s waiting for $Health. Check backend\data\phishguard.log"
exit 1
