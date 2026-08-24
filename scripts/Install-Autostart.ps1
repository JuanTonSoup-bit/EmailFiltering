<#
.SYNOPSIS
    Make PhishGuard start automatically when you log in, and add a desktop
    shortcut for opening the dashboard.

.DESCRIPTION
    This is the piece that removes the need to "launch" PhishGuard at all.

    A browser extension cannot start a local process - Chrome's sandbox has
    no way to spawn one, and the only workaround (a registered native
    messaging host) is a lot of moving parts to solve a problem that is
    better solved by the server simply always being up. A logon task means
    the dashboard is just there at localhost:8000, the way a local service
    should be.

    Registers a Scheduled Task under the CURRENT user only. No admin rights
    needed, no service installation, nothing machine-wide.

.PARAMETER Port
    Port the server should listen on. Default 8000.

.PARAMETER NoShortcut
    Skip creating the desktop shortcut.

.EXAMPLE
    .\Install-Autostart.ps1
#>
[CmdletBinding()]
param(
    [int]$Port = 8000,
    [switch]$NoShortcut
)

$ErrorActionPreference = 'Stop'

$Root      = Split-Path -Parent $PSScriptRoot
$StartPs1  = Join-Path $PSScriptRoot 'Start-PhishGuard.ps1'
$TaskName  = 'PhishGuard'

if (-not (Test-Path $StartPs1)) { throw "Not found: $StartPs1" }

# --- The logon task --------------------------------------------------------
# -NoBrowser: starting the server at logon is welcome; a browser window
# stealing focus every time you sign in is not.
$action = New-ScheduledTaskAction `
    -Execute 'powershell.exe' `
    -Argument "-NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$StartPs1`" -Port $Port -NoBrowser"

# 30s delay so the network stack is up before the first Gmail poll. Without
# it the first scan after a reboot usually fails DNS and logs a scary error.
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$trigger.Delay = 'PT30S'

$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -ExecutionTimeLimit ([TimeSpan]::Zero)   # long-running by design; never kill it

if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "Replaced the existing '$TaskName' task."
}

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Description 'Starts the PhishGuard mail-filtering server at logon.' | Out-Null

Write-Host "Registered logon task '$TaskName' (port $Port)."

# --- Desktop shortcut ------------------------------------------------------
if (-not $NoShortcut) {
    $lnk = Join-Path ([Environment]::GetFolderPath('Desktop')) 'PhishGuard.lnk'
    $shell = New-Object -ComObject WScript.Shell
    $sc = $shell.CreateShortcut($lnk)
    $sc.TargetPath  = 'powershell.exe'
    $sc.Arguments   = "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$StartPs1`" -Port $Port"
    $sc.WorkingDirectory = $Root
    $sc.Description = 'Open the PhishGuard dashboard (starts the server if needed)'
    # shell32.dll,167 is the small shield icon.
    $sc.IconLocation = "$env:SystemRoot\System32\shell32.dll,167"
    $sc.Save()
    Write-Host "Created desktop shortcut: $lnk"
}

Write-Host ""
Write-Host "Done. PhishGuard will start automatically at logon."
Write-Host "Start it right now without waiting for a reboot:"
Write-Host "  Start-ScheduledTask -TaskName $TaskName"
Write-Host ""
Write-Host "To undo: .\Uninstall-Autostart.ps1"
