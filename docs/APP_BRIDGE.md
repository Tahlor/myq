# Track A — official Android app bridge

## Why this is first

A June 2026 working implementation demonstrated that the official myQ Android app can be automated through UIAutomator and exposed as a local REST API. The author used ReDroid; the important primitive is **driving the real app through Android's accessibility/UI tree**, not ReDroid itself.

Reference: https://www.reddit.com/r/myq/comments/1u1oqvn/

The same thread reports that myQ `5.243.1.73243` can authenticate without the hardware-backed Play Integrity requirement introduced in later builds, and another user confirmed the overall approach still worked in late August 2026.

## Local baseline — 2026-09-04

The canonical Superbox answered on its configured network-ADB endpoint and reported Android 12 with `armeabi-v7a`. Before installation, neither `com.chamberlain.android.liftmaster.myq` nor `com.tahlor.myqbridge` was installed, and TCP 8765 was not listening. No accessibility change or garage operation was attempted during this baseline.

## Live app install — 2026-09-04

APKMirror's manually reviewed universal APK was downloaded through the existing Edge session and kept under ignored `captures/apk/` storage. The file size and SHA-256 matched the download page exactly:

- version `5.243.1.73243`, package `com.chamberlain.android.liftmaster.myq`;
- `118,474,022` bytes;
- SHA-256 `252cfdff12dad8e57b10a5c8f066ca733b2885cd6ea1fd6515726cf7fe90fc55`;
- installed successfully on the Superbox (`versionCode=73243`, APK signing scheme v2);
- Android reported the Chamberlain certificate fingerprint `3C:49:83:4E:C2:79:0E:B4:72:33:08:04:01:A5:D3:7B:35:4B:D5:AC:63:9B:EE:AF:BB:EF:7C:56:20:05:E4:0C`.

The app initially launched to `ConsentToTermsActivity`; the current Terms of Service and Privacy Policy have since been accepted on the Superbox. No credentials have been copied into the repository, terminal commands, logs, or screenshots.

## Live native bridge install — 2026-09-05

The bridge was built locally with JDK 17, Gradle 8.9, Android platform 35, and build-tools 35.0.0, then installed as `com.tahlor.myqbridge`. Its accessibility service was appended to the existing enabled-service list without removing the Superbox's existing service. `GET /health` returned `{"status":"ok"}` and authenticated `GET /debug/nodes` successfully inspected the myQ welcome screen, including the stable sign-in resource ID `com.chamberlain.android.liftmaster.myq:id/welcome_btn_sign_in`.

The first authenticated probe exposed an Android 11+ package-visibility issue: `getLaunchIntentForPackage()` could not see the installed myQ package. The bridge manifest now declares a package query for `com.chamberlain.android.liftmaster.myq`; after rebuilding and reinstalling, the read-only probe reached `WelcomeActivity` normally. No door configuration is installed yet, and no status or command endpoint has been used against a physical door.

The generated bridge API key and the owner-authorized account credentials are stored locally in ignored `config/myq_credentials.local.json`; neither has been committed.

## Live login handoff — 2026-09-05

The native bridge was revalidated after the APK and bridge installs: `/health` returned `ok`, authenticated `/debug/nodes` returned six nodes, and the foreground activity was `WelcomeActivity`. The bridge then opened the app's Login button, which launched Chrome's custom-tab OAuth flow for the current myQ identity service. No username, password, OAuth code, access token, refresh token, or garage command was entered or emitted. The Superbox is currently positioned at the login handoff and is ready for the owner-authorized credential step.

## Authorized credential bootstrap — 2026-09-05

The existing Pi3 Broadlink deployment was reachable through its configured SSH profile. Its expected `/home/pi/bashrc/secure/credentials_myq` file was present and had the two-line email/password shape used by the Broadlink controller. The values were copied in memory into ignored `config/myq_credentials.local.json` with `scripts/import_pi3_myq_credentials.ps1`, preserving the bridge API key. The temporary raw copy was removed immediately after import. Secret values were not printed, committed, or added to documentation.

Our existing SuperBOX S7MAX is preferable to a new Android VM because it is already an always-on Android device on the LAN with remote ADB. This repo therefore has two implementations of the same bridge contract:

1. `android_bridge/` — **preferred steady-state path**. Accessibility service + authenticated HTTP API run directly on the Superbox; no PC is required after setup.
2. `src/myq_bridge/` — Python/UIAutomator bring-up and diagnostic fallback. Useful for inspecting the UI and testing selectors rapidly from a development machine.

Both use the same `config/doors.json` selector schema.

## Phase A1 — install and authenticate official myQ

1. Obtain myQ `5.243.1.73243` locally. Do not commit the APK. This has been completed and verified as documented above.
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

- Does the owner-authorized login complete on the S7MAX's 32-bit ARM Android 12 build?
- Does its login WebView work with the Superbox's current WebView, or does WebView need an update?
- Does the app reject the Superbox's exposed `su` binary?
- Which MyQ accessibility resource IDs are stable on the real dashboard?
- Does the native service remain bound and its TCP server recover after Superbox reboot?
- Does the authenticated MyQ session persist through app restart and Superbox reboot?
- Can a newer myQ APK reuse a session created by the older build without a new Integrity check?
