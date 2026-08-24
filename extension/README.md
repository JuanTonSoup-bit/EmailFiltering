# PhishGuard browser extension

A toolbar badge and popup for your local PhishGuard server. Shows what it
flagged without you opening anything, and gets you to the dashboard in one
click.

## What it does

- **Badge** on the toolbar icon, updated every minute:
  | Badge | Meaning |
  |---|---|
  | *(empty)* | Server up, nothing flagged — the normal state |
  | `3` red | 3 flagged, at least one suspicious |
  | `3` amber | 3 flagged, junk only |
  | `!` grey | Server not reachable |
- **Popup** with the current counts, the last few flagged messages, an
  **Open dashboard** button and a **Scan now** button.
- **Settings** for the port and the day window it reports on.

## Install

It is unpacked/developer-mode only — it talks to `127.0.0.1`, so there would
be no point publishing it to the Web Store.

1. Open `chrome://extensions/`
2. Turn on **Developer mode** (top right)
3. **Load unpacked** → select this `extension/` folder
4. Pin it: click the puzzle-piece icon in the toolbar, then the pin next to
   PhishGuard

## It does not start the server

Worth being explicit, because it is the obvious thing to want: **a Chrome
extension cannot launch a local process.** The sandbox has no API for it. The
only workaround is a registered native-messaging host — a manifest in the
registry plus a helper executable plus per-extension-ID configuration — which
is a lot of moving parts to solve a problem that has a better solution.

That solution is `scripts/Install-Autostart.ps1`: it registers a logon task so
the server is simply always running, the way a local service should be. Then
there is nothing to launch, and this extension is the window into a thing that
is already up.

If the server is down anyway, the popup says so and hands you the command to
start it.

## Permissions, and why each is needed

| Permission | Why |
|---|---|
| `alarms` | The one-minute poll that keeps the badge current. Manifest V3 service workers are killed when idle, so a `setInterval` would simply stop running. |
| `storage` | Remembers your port/window settings and caches the last poll so the popup paints instantly instead of showing a spinner. |
| `http://localhost/*`, `http://127.0.0.1/*` | Reaching the API. Loopback only, and broad across ports so the port stays configurable. |

There is no `tabs` permission — opening the dashboard uses `chrome.tabs.create`,
which needs no permission — and no content scripts, so the extension never
touches or reads any page you visit.

## A note on the code

Everything the popup renders — subject lines, sender addresses — originates in
email, and is inserted with `textContent` only. Building that DOM with
`innerHTML` would make a crafted subject line executable inside the extension.
That is a bad trade in any extension and an absurd one in an anti-phishing
tool.

## Icons

`icons/*.png` are generated, not hand-drawn:

```bash
python icons/make_icons.py
```

Generating them keeps the shape reviewable in source instead of arriving as an
opaque binary, and avoids a Pillow dependency — `make_icons.py` writes PNG
bytes directly with `zlib`.
