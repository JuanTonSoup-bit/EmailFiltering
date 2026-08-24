<#
.SYNOPSIS
    Stop the running PhishGuard server.

.DESCRIPTION
    Prefers the pid recorded by Start-PhishGuard. Falls back to finding the
    process that owns the port, because a pid file can go stale (a crash, a
    reboot, or a server started by hand from a terminal).

    Deliberately narrow: it will only kill a process whose command line
    actually mentions this project's uvicorn app. "Kill whatever is on port
    8000" is how you end up terminating something unrelated.
#>
[CmdletBinding()]
param([int]$Port = 8000)

$ErrorActionPreference = 'Stop'

$Root    = Split-Path -Parent $PSScriptRoot
$DataDir = Join-Path $Root 'backend\data'
$PidFile = Join-Path $DataDir 'phishguard.pid'

function Get-CommandLine($ProcessId) {
    try {
        (Get-CimInstance Win32_Process -Filter "ProcessId = $ProcessId").CommandLine
    } catch { $null }
}

$targets = @()

# 1. The pid we recorded at start.
if (Test-Path $PidFile) {
    $recorded = (Get-Content $PidFile -Raw).Trim()
    if ($recorded -match '^\d+$') { $targets += [int]$recorded }
}

# 2. Whatever currently holds the port.
try {
    $targets += (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction Stop).OwningProcess
} catch {
    # No listener, or Get-NetTCPConnection unavailable - the pid file is all we have.
}

$stopped = 0
foreach ($processId in ($targets | Sort-Object -Unique)) {
    $proc = Get-Process -Id $processId -ErrorAction SilentlyContinue
    if (-not $proc) { continue }

    # Only ever stop OUR server.
    $cmd = Get-CommandLine $processId
    if ($cmd -and $cmd -notmatch 'app\.main:app') {
        Write-Warning "PID $processId holds port $Port but is not PhishGuard - leaving it alone."
        continue
    }

    # uvicorn runs as a supervisor plus a worker, so stopping one usually
    # takes the other with it. By the time we reach the second pid it may
    # already be gone - that is success, not an error.
    try {
        Stop-Process -Id $processId -Force -ErrorAction Stop
        Write-Host "Stopped PhishGuard (PID $processId)."
        $stopped++
    } catch [Microsoft.PowerShell.Commands.ProcessCommandException] {
        Write-Verbose "PID $processId had already exited."
        $stopped++
    }
}

if (Test-Path $PidFile) { Remove-Item $PidFile -Force }

if ($stopped -eq 0) { Write-Host "PhishGuard was not running." }
