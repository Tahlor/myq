# Track A — official Android app bridge

## Why this is first

A June 2026 working implementation demonstrated that the official myQ Android app can be automated through UIAutomator and exposed as a local REST API. The author used ReDroid; the important primitive is not ReDroid itself, but **driving the real app through the Android accessibility/UI tree**.

Reference: https://www.reddit.com/r/myq/comments/1u1oqvn/

The same thread reports that myQ `5.243.1.73243` can authenticate without the hardware-backed Play Integrity requirement introduced in later builds, and a separate user confirmed the approach still worked in late August 2026.

Our existing SuperBOX S7MAX is preferable to a new ReDroid VM for initial work because it is already an always-on Android device on the LAN and already has working remote ADB.

## Phase A1 — install and authenticate

1. Obtain myQ `5.243.1.73243` locally. Do not commit the APK.
2. Connect:

   ```powershell
   $serial = .\scripts\connect_superbox.ps1
   ```

3. Install either a single APK or a folder containing split APKs:

   ```powershell
   .\scripts\install_myq_superbox.ps1 -PackagePath C:\local\myq -AdbSerial $serial
   ```

4. Complete account authentication interactively on the TV / via a trusted screen-control path.
5. Verify the garage door is visible and its status updates.

Do **not** change `ro.secure`, `ro.debuggable`, remove `su`, or modify the Superbox system image preemptively. This box is shared infrastructure for other projects. First observe whether the older app actually objects to the existing root state.

## Phase A2 — calibrate the UI bridge

Create a Python environment and install the package:

```powershell
python -m venv .venv
.\.venv\Scripts\pip install -e ".[dev]"
Copy-Item config\doors.example.json config\doors.json
$env:MYQ_ADB_SERIAL = (.\scripts\connect_superbox.ps1)
$env:MYQ_API_KEY = ([guid]::NewGuid().ToString("N") + [guid]::NewGuid().ToString("N"))
python -m myq_bridge
```

Fetch the visible accessibility tree:

```powershell
$headers = @{ "X-API-Key" = $env:MYQ_API_KEY }
Invoke-RestMethod http://127.0.0.1:8765/debug/nodes -Headers $headers
```

Find stable selectors for:

- the door name;
- the current state (`Open`, `Closed`, `Opening`, `Closing`);
- the action button(s).

Prefer `resource-id` over display text when possible. Put the resulting selectors in ignored `config/doors.json`.

The bridge supports separate `open` / `close` selectors or a single `toggle` selector. When a toggle is used for a requested explicit state, it reads the current state first and refuses to click if the door is already in the requested state.

## Phase A3 — expose to home automation

Endpoints:

- `GET /health` — no secret, liveness only
- `GET /status` — authenticated state
- `POST /doors/{name}/open`
- `POST /doors/{name}/close`
- `POST /doors/{name}/toggle`
- `GET /debug/tree` — authenticated raw hierarchy for calibration
- `GET /debug/nodes` — authenticated compact hierarchy

Every non-health request requires `X-API-Key`.

For production, bind the bridge only to the home-automation interface/VLAN and firewall port `8765` to trusted clients.

## Phase A4 — remove UI fragility

Once the app is working, pull its installed packages:

```powershell
.\scripts\pull_myq_apks.ps1
```

Then use Track B1 to recover the actual cloud calls. If we can replay the authenticated requests directly, replace UI automation with a direct client while keeping the official app available for re-authentication/session bootstrap.

## Current unknowns to resolve live

- Does `5.243.1.73243` install and run normally on the S7MAX's 32-bit ARM Android 12 build?
- Does its login WebView work with the Superbox's current WebView, or does WebView need an update?
- Does the app reject the Superbox's exposed `su` binary?
- Which accessibility resource IDs are stable on the dashboard?
- Does the authenticated session persist through app restart and Superbox reboot?
- Can a newer myQ APK reuse the authenticated session created by the old build without a new Integrity check?
