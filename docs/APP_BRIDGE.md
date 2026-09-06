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

The native bridge was revalidated after the APK and bridge installs: `/health` returned `ok`, authenticated `/debug/nodes` returned six nodes, and the foreground activity was `WelcomeActivity`. The bridge then opened the app's Login button, which launched Chrome's custom-tab OAuth flow for the current myQ identity service. The owner-authorized credentials were entered without logging their values, and the flow advanced to the MFA choice screen. No OAuth code, access token, refresh token, or garage command was entered or emitted.

## Live MFA checkpoint — 2026-09-05

The identity service presents separate SMS and email MFA choices plus a skip action. The screen was intentionally left unchanged: choosing a delivery channel sends a one-time code or changes the account's MFA flow, so the owner must choose the preferred channel and enter the code on the Superbox. The code should not be sent through chat or committed to the repository.

## Live bridge lifecycle validation — 2026-09-05

The HTTP lifecycle is now hosted by a separate foreground service, while the accessibility service only supplies myQ UI roots and actions. This fixes the OAuth handoff failure where the old design stopped TCP 8765 when Chrome became foreground. After rebuilding and reinstalling, authenticated `/debug/nodes` returned six WelcomeActivity nodes, Chrome's custom-tab login opened, and both `/health` and TCP 8765 remained available during the handoff. No door command was issued.

The bridge host now also registers a boot receiver so the foreground HTTP service can restart after a normal Android boot. A live reboot/persistence test remains pending because it would interrupt the shared Superbox and should be performed after authentication and read-only validation are complete.

The installed service was rechecked while OAuth MFA remained in Chrome: `GET /health` returned `{"status":"ok"}`, while an invalid-key request to the protected `/status` endpoint returned `401` before touching the myQ UI. This confirms both liveness and the authentication gate without launching the app or sending a garage command.

## Background navigation guard and independent app ANR — 2026-09-06

The original native bridge tried to launch myQ from its foreground HTTP service whenever a protected request arrived without an attached UI root. On Android 12, a live probe showed the background activity-start abort immediately before a `LoginActivity` focus-loss ANR. The bridge now leaves navigation to the user-facing `MainActivity` and waits only for an already-foreground myQ root. If myQ is not foreground, protected UI reads return HTTP `409` with `myQ must be in the foreground before reading or commanding it`; no activity start is attempted.

The rebuilt APK was installed and the accessibility service was rebound while preserving the existing enabled service list. A protected `/debug/nodes` probe with the bridge activity foreground returned the expected `409`, and no new myQ launch or background-start abort occurred in that probe window.

The official app was then launched directly from the Superbox launcher with the bridge activity out of focus. It reached `LoginActivity`, the launcher regained focus, and Android recorded the same `LoginActivity` focus-loss ANR. Repeating the launch with the bridge accessibility component temporarily disabled produced the same result. This separates the remaining cold-start/login lifecycle failure from the bridge's removed background navigation; no door command was issued.

## Authorized credential bootstrap — 2026-09-05

The existing Pi3 Broadlink deployment was reachable through its configured SSH profile. Its expected `/home/pi/bashrc/secure/credentials_myq` file was present and had the two-line email/password shape used by the Broadlink controller. The values were copied in memory into ignored `config/myq_credentials.local.json` with `scripts/import_pi3_myq_credentials.ps1`, preserving the bridge API key. The temporary raw copy was removed immediately after import. Secret values were not printed, committed, or added to documentation.

Our existing SuperBOX S7MAX is preferable to a new Android VM because it is already an always-on Android device on the LAN with remote ADB. This repo therefore has two implementations of the same bridge contract:

1. `android_bridge/` — **preferred steady-state path**. Accessibility service + authenticated HTTP API run directly on the Superbox; no PC is required after setup.
2. `src/myq_bridge/` — Python/UIAutomator bring-up and diagnostic fallback. Useful for inspecting the UI and testing selectors rapidly from a development machine.

Both use the same `config/doors.json` selector schema.

## Live authorized session and read-only validation — 2026-09-06

The owner-authorized Android OAuth flow completed on the Superbox. The Chrome custom tab closed and returned control to myQ; the APK then became unresponsive in `LoginActivity` during callback handling and Android force-finished the app. Before that ANR, the encrypted app preferences contained both rotating OAuth values, and `scripts/extract_myq_session.ps1` wrote only the ignored `config/cloud_session.json` session shape.

The direct client then successfully refreshed the Android-issued session, discovered one account containing a garage door and hub, and read the door as `closed` and `online`. No open, close, lock-mode, or other mutating request was issued. The current result is therefore a working direct-cloud read path with an official-app callback/UI stability issue still open.

A separate cold-start test on the same date reproduced the `LoginActivity` focus-loss ANR before any OAuth interaction, including with the bridge accessibility component disabled. The app's callback ANR and this cold-start ANR are therefore tracked as official-app/host lifecycle evidence, not as a reason to reintroduce background activity launches in the bridge.

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

The foreground host service keeps the HTTP port available while myQ hands off to Chrome for OAuth. The accessibility component remains package-scoped to `com.chamberlain.android.liftmaster.myq`, and it only reads or acts on that package's root. It is not a generic remote UI-control service.

The service does not bring myQ to the foreground on behalf of a LAN request. Use the companion activity's **Open myQ** action (or an already-running myQ task), verify the dashboard, and then call `/status` or `/debug/nodes`.

On 2026-09-06, the user-facing launcher path was narrowed to the official APK's exported `com.chamberlain.myq.main.HomeTabsActivity`. A cold explicit launch of that dashboard activity completed in 2.487 seconds and remained foreground without the `LoginActivity` focus-loss ANR. The package launcher still takes the Splash/Login path that reproduces the ANR, so this dashboard shortcut is the current bridge validation path. After rebinding the service and closing the first-run tour, the native bridge observed 42 dashboard nodes and two consecutive `GET /status` reads returned one configured `Garage Door` as `closed`.

The dashboard's large `device_view_progress_indicator` is a live action surface, not a safe navigation target. A calibration tap on 2026-09-06 produced a transient `Opening` UI state and then a `Garage Door is not responding` alert. The alert was dismissed without another device tap; two independent direct-cloud status reads and two subsequent bridge reads reported `closed` and `online=True`. The selector is intentionally not present in the state-only local configuration until an explicit action-control test is authorized and can be physically observed.

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

- Can the official app display its authenticated dashboard after the OAuth callback once the independent `LoginActivity` focus-loss ANR is resolved?
- Does its login WebView work with the Superbox's current WebView, or does WebView need an update?
- Does the app reject the Superbox's exposed `su` binary?
- Which MyQ accessibility resource IDs are stable on the real dashboard?
- Does the native service remain bound and its TCP server recover after Superbox reboot?
- Does the authenticated MyQ session remain usable through app restart and Superbox reboot?
- Can a newer myQ APK reuse a session created by the older build without a new Integrity check?
