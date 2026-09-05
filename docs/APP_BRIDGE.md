# Track A — official Android app bridge

## Why this is first

A June 2026 working implementation demonstrated that the official myQ Android app can be automated through UIAutomator and exposed as a local REST API. The author used ReDroid; the important primitive is **driving the real app through Android's accessibility/UI tree**, not ReDroid itself.

Reference: https://www.reddit.com/r/myq/comments/1u1oqvn/

The same thread reports that myQ `5.243.1.73243` can authenticate without the hardware-backed Play Integrity requirement introduced in later builds, and another user confirmed the overall approach still worked in late August 2026.

Our existing SuperBOX S7MAX is preferable to a new Android VM because it is already an always-on Android device on the LAN with remote ADB. This repo therefore has two implementations of the same bridge contract:

1. `android_bridge/` — **preferred steady-state path**. Accessibility service + authenticated HTTP API run directly on the Superbox; no PC is required after setup.
2. `src/myq_bridge/` — Python/UIAutomator bring-up and diagnostic fallback. Useful for inspecting the UI and testing selectors rapidly from a development machine.

Both use the same `config/doors.json` selector schema.

## Phase A1 — install and authenticate official myQ

1. Obtain myQ `5.243.1.73243` locally. Do not commit the APK.
2. Connect:

   ```powershell
   $serial = .\scripts\connect_superbox.ps1
   ```

3. Install either a single APK or a folder containing split APKs:

   ```powershell
   .\scripts\install_myq_superbox.ps1 -PackagePath C:\local\myq -AdbSerial $serial
   ```

4. Complete account authentication interactively on the TV / through a trusted screen-control path.
5. Verify the real garage door is visible and its status updates.

Do **not** change `ro.secure`, `ro.debuggable`, remove `su`, or modify the Superbox system image preemptively. The box is shared infrastructure for other projects. First observe whether the older app actually objects to its existing root state.

## Phase A2 — install the native LAN bridge

Build/install our companion app:

```powershell
$key = .\scripts\build_install_android_bridge.ps1 -AdbSerial $serial | Select-Object -Last 1
$headers = @{ 'X-API-Key' = $key }
```

The installer:

- builds `android_bridge/app`;
- installs `com.tahlor.myqbridge`;
- stores the supplied/generated API key in the app's private preferences;
- **appends** our accessibility service to Android's enabled service list rather than replacing existing services;
- enables accessibility globally if requested;
- optionally pushes an already-calibrated `doors.json`;
- prints the Superbox LAN API endpoint and secret.

The accessibility service is package-scoped to `com.chamberlain.android.liftmaster.myq`. It is not a generic remote UI-control service.

If automatic accessibility enablement is undesirable for a test, pass `-NoEnableAccessibility` and enable **myQ LAN Bridge** manually in Android Accessibility settings.

## Phase A3 — calibrate selectors

Before any command, inspect the dashboard hierarchy through the native bridge:

```powershell
Invoke-RestMethod http://<superbox-ip>:8765/debug/nodes -Headers $headers
```

Find stable selectors for:

- each door's current-state label (`Open`, `Closed`, `Opening`, `Closing`);
- the corresponding explicit action buttons, if separate buttons exist;
- otherwise the door's toggle/action element.

Prefer `resource_id` over display text when possible. Copy `config/doors.example.json` to ignored `config/doors.json`, fill the selectors, then push it:

```powershell
.\scripts\push_bridge_config.ps1 -AdbSerial $serial -ConfigPath config\doors.json
```

The native bridge reloads this file on every request, so selector changes do not require rebuild/restart.

### Optional Python calibration fallback

If native accessibility output is insufficient during bring-up:

```powershell
python -m venv .venv
.\.venv\Scripts\pip install -e ".[dev]"
$env:MYQ_ADB_SERIAL = $serial
$env:MYQ_API_KEY = ([guid]::NewGuid().ToString("N") + [guid]::NewGuid().ToString("N"))
python -m myq_bridge
```

Then inspect `http://127.0.0.1:8765/debug/nodes`. The Python implementation also exposes raw `/debug/tree`.

## Phase A4 — verify read-only state, then one safe command

Native endpoints:

- `GET /health` — unauthenticated liveness only
- `GET /status` — authenticated state
- `GET /debug/nodes` — authenticated compact accessibility hierarchy
- `POST /doors/{name}/open`
- `POST /doors/{name}/close`
- `POST /doors/{name}/toggle`

Every non-health request requires `X-API-Key`.

Verify `GET /status` repeatedly before sending a command. During the first command test, physically observe the door and request an **explicit state** rather than `toggle`.

Both implementations serialize operations. If an explicit `open`/`close` request has only a toggle selector available, the bridge reads current state first and **refuses to click when state is unknown**. It also no-ops if the requested state is already observed.

For production, firewall TCP `8765` to trusted home-automation clients / VLANs.

## Phase A5 — remove UI fragility

Once the app is authenticated and stable, pull its installed packages:

```powershell
.\scripts\pull_myq_apks.ps1
```

Then use Track B1 to recover the current cloud calls. If authenticated requests can be replayed directly, replace accessibility automation with a direct client behind the same conceptual API while retaining the official app for bootstrap/recovery.

## Current live unknowns

- Does `5.243.1.73243` install and run normally on the S7MAX's 32-bit ARM Android 12 build?
- Does its login WebView work with the Superbox's current WebView, or does WebView need an update?
- Does the app reject the Superbox's exposed `su` binary?
- Which MyQ accessibility resource IDs are stable on the real dashboard?
- Does the native service remain bound and its TCP server recover after Superbox reboot?
- Does the authenticated MyQ session persist through app restart and Superbox reboot?
- Can a newer myQ APK reuse a session created by the older build without a new Integrity check?
