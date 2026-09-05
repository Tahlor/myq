# myQ software bridge

Software-only integration work for Chamberlain/LiftMaster myQ devices. The goal is reliable home-automation control **without adding hardware to the garage opener**.

## Tracks

### A. Official-app bridge — working architecture to validate live

Run the official myQ Android app on the existing SuperBOX S7MAX and drive it through Android's accessibility surface. `android_bridge/` is an on-device companion that exposes a small authenticated REST API directly from the Superbox, so the steady-state path can be:

```text
Home Assistant / automations -> Superbox:8765 -> official myQ app -> myQ cloud -> opener
```

The Python/UIAutomator bridge under `src/myq_bridge/` remains useful for calibration, diagnostics, and fallback testing, but it is not required in the intended steady state.

The first bring-up target is myQ `5.243.1.73243`, which multiple users reported in 2026 can authenticate in Android environments that fail newer MyQ Play Integrity checks. Once authenticated, test current versions and session persistence rather than assuming that old build must remain permanently installed.

### B. Protocol recovery — preferred end state

Use the official app and the Wi-Fi opener as ground truth to recover:

1. current app/cloud endpoints and request semantics;
2. whether authenticated app requests can be replayed directly by our own client;
3. the opener's LAN identity and exposed services;
4. its outbound DNS/TLS/MQTT behavior;
5. whether the opener can be redirected to a local broker/service without firmware or hardware changes.

The best outcome is true LAN control with no Chamberlain cloud. A direct but cloud-backed client is still an improvement over UI automation. Track A stays available as the compatibility fallback.

## Existing hardware we reuse

The already-owned **SuperBOX S7MAX** documented in `Tahlor/superbox` is the Android host:

- Android 12 / API 31
- 32-bit ARM (`armeabi-v7a`)
- root available
- persistent ADB reachable on the home LAN
- logcat, app sideloading, and Frida-server deployment already established

No fixed ADB IP/port is authoritative; use `scripts/connect_superbox.ps1`.

## First live run

```powershell
# 1. Connect to the Superbox.
$serial = .\scripts\connect_superbox.ps1

# 2. Install a locally obtained official myQ APK / split-APK directory.
.\scripts\install_myq_superbox.ps1 -PackagePath C:\path\to\myq -AdbSerial $serial
# Complete myQ login interactively and verify the real door is visible.

# 3. Build/install our native companion. It prints the generated API key.
$key = .\scripts\build_install_android_bridge.ps1 -AdbSerial $serial | Select-Object -Last 1

# 4. Inspect the live MyQ accessibility tree from the Superbox itself.
$headers = @{ 'X-API-Key' = $key }
Invoke-RestMethod http://<superbox-ip>:8765/debug/nodes -Headers $headers

# 5. Copy config/doors.example.json -> ignored config/doors.json,
#    fill in stable live selectors, then push it without rebuilding.
.\scripts\push_bridge_config.ps1 -AdbSerial $serial -ConfigPath config\doors.json

# 6. Read state before attempting any command.
Invoke-RestMethod http://<superbox-ip>:8765/status -Headers $headers
```

The native API supports `GET /health`, `GET /status`, `GET /debug/nodes`, and authenticated `POST /doors/{name}/{open|close|toggle}`.

## Reverse-engineering tools

```powershell
# Pull the exact installed official APK/splits and inspect them with JADX.
$dir = .\scripts\pull_myq_apks.ps1
.\scripts\decompile_myq.ps1 -ApkDirectory $dir

# Capture app-only logcat metadata.
.\scripts\capture_myq_logcat.ps1 -Seconds 60

# Reuse the Superbox repo's Frida-server installer, then trace URL/socket metadata.
.\scripts\trace_myq_network.ps1 -InstallFridaServer

# Discover likely Chamberlain devices on the LAN.
python tools\lan_probe.py --subnet <home-subnet>

# Summarize DNS/TLS/endpoints from a router/AP/switch capture.
python tools\pcap_summary.py capture.pcap --opener-ip <opener-ip>
```

Raw captures, APKs, tokens, UI dumps and pcaps stay ignored. Commit only sanitized interoperability findings.

## Safety / security

A garage door is a physical access-control device. Both bridge implementations:

- require an API key for control/state endpoints;
- perform no automatic geolocation opening by default;
- serialize commands;
- avoid acting when the requested state is already observed;
- refuse an explicit-state request that would require a **blind toggle** while state is unknown;
- keep captured credentials/tokens/APKs/screenshots/UI dumps/pcaps out of Git.

See `docs/APP_BRIDGE.md`, `docs/REVERSE_ENGINEERING.md`, `docs/LAN_RECON.md`, and the open GitHub issues for the live evidence gates.
