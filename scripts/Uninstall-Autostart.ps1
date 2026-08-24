<#
.SYNOPSIS
    Undo Install-Autostart: remove the logon task and the desktop shortcut.

.DESCRIPTION
    Does not stop a server that is currently running - use Stop-PhishGuard.ps1
    for that. Removing the task only prevents future automatic starts.
#>
[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$TaskName = 'PhishGuard'

if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "Removed logon task '$TaskName'."
} else {
    Write-Host "No logon task named '$TaskName' was registered."
}

$lnk = Join-Path ([Environment]::GetFolderPath('Desktop')) 'PhishGuard.lnk'
if (Test-Path $lnk) {
    Remove-Item $lnk -Force
    Write-Host "Removed desktop shortcut."
}

Write-Host ""
Write-Host "PhishGuard will no longer start at logon."
Write-Host "If it is running right now, stop it with: .\Stop-PhishGuard.ps1"
