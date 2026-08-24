# Launcher scripts

Windows PowerShell scripts for running PhishGuard without a terminal. All are
PowerShell 5.1 compatible (the `powershell.exe` that ships with Windows) and
none require administrator rights.

| Script | What it does |
|---|---|
| `Start-PhishGuard.ps1` | Start the server if it isn't running, then open the dashboard |
| `Stop-PhishGuard.ps1` | Stop the running server |
| `Install-Autostart.ps1` | Register a logon task + create a desktop shortcut |
| `Uninstall-Autostart.ps1` | Remove both |

## The recommended setup

```powershell
cd C:\Users\Juan\EmailFiltering\scripts
.\Install-Autostart.ps1
```

That registers a Scheduled Task under your user account which runs
`Start-PhishGuard.ps1 -NoBrowser` 30 seconds after logon, and puts a
**PhishGuard** shortcut on your desktop that opens the dashboard.

After that you never start anything. The server is up whenever you are logged
in; the desktop shortcut and the browser extension are just ways to look at it.

To start it immediately rather than waiting for a reboot:

```powershell
Start-ScheduledTask -TaskName PhishGuard
```

## Details worth knowing

**`Start-PhishGuard.ps1` is idempotent.** It is wired to a desktop shortcut, a
logon task, and manual runs — all of which can fire while it is already
running. If the API already answers, it just opens the browser and exits.
Starting a second uvicorn would mean two pollers racing to scan the same
inbox.

**The server runs under `pythonw.exe`**, so there is no console window. Its
output goes to `backend/data/phishguard.log` (uvicorn and the poller both log
to stderr) and `backend/data/phishguard.out.log`. Its pid is recorded in
`backend/data/phishguard.pid`.

**uvicorn runs as two processes** on Windows — a supervisor and the worker
that actually serves. Only one runs the poller, so there is no double
scanning. `Stop-PhishGuard.ps1` handles both, and treats "already exited" as
success, because stopping one usually takes the other with it.

**`Stop-PhishGuard.ps1` is deliberately narrow.** It will only stop a process
whose command line mentions `app.main:app`. "Kill whatever is on port 8000" is
how you end up terminating something unrelated.

**The logon task has a 30-second delay** so the network stack is up before the
first Gmail poll. Without it the first scan after a reboot usually fails DNS
and logs an alarming traceback for no reason.

## Options

```powershell
.\Start-PhishGuard.ps1 -Port 8123        # different port
.\Start-PhishGuard.ps1 -NoBrowser        # start without opening the dashboard
.\Install-Autostart.ps1 -Port 8123       # autostart on a different port
.\Install-Autostart.ps1 -NoShortcut      # skip the desktop shortcut
```

If you change the port, change it in the extension's settings too.

## If a script won't run

PowerShell's execution policy may block unsigned local scripts. The shortcut
and the task both pass `-ExecutionPolicy Bypass` so they are unaffected, but a
manual run may need it:

```powershell
powershell -ExecutionPolicy Bypass -File .\Start-PhishGuard.ps1
```
