# myQ software bridge

Software-only integration work for Chamberlain/LiftMaster myQ devices. The goal is reliable home-automation control **without adding hardware to the garage opener**.

## Architecture

We are pursuing three software layers in parallel, ordered from easiest to most independent:

1. **Official-app bridge (working code, live validation pending)**
   `Home automation -> Superbox:8765 -> official myQ Android app -> myQ cloud -> opener`
2. **Direct-cloud bridge (implemented, initial authorized session pending)**
   `Home automation -> local daemon:8766 -> myQ v6 cloud -> opener`
3. **True local control (protocol-recovery track)**
   `Home automation -> opener on LAN`, ideally with no Chamberlain cloud.

The first two are complementary: the official app can remain a compatibility/bootstrap fallback even if direct cloud calls become the normal path.

## Current 2026 direct-cloud finding

A new August 2026 Home Assistant integration (`vector-sec/chamberlain-myq-hacs`) demonstrates the current v6 account/device/action endpoints and a normal OAuth refresh-token grant. We clean-room implemented those protocol facts in `src/myq_bridge/cloud.py`; we do not vendor or copy that repository's implementation.

Current defaults are configurable but start from the working August 2026 client identity:

- client id: `IOS_CGI_MYQ`
- app version: `5.315.0.66076`
- token endpoint: `partner-identity.myq-cloud.com/connect/token`
- account/device APIs: current v6/v6.2 MyQ cloud endpoints

This is important because the observed refresh and door-command flow does **not** require Play Integrity/App Check fields. The remaining question is how best to bootstrap the first authorized access/refresh-token pair from our own authorized account. Do not commit tokens.

Once a local authorized session exists in ignored `config/cloud_session.json` (copy `config/cloud_session.example.json`), the direct client can:

```powershell
# Refresh + rotate the session normally.
myq-cloud refresh

# Discover account/device IDs.
myq-cloud accounts
myq-cloud devices <account-id>

# Run a local authenticated REST facade on port 8766.
$env:MYQ_API_KEY = '<local-secret>'
myq-cloud serve
```

The REST service exposes authenticated account/device discovery and **explicit** open/close endpoints; it never uses a blind toggle.

## Official-app / Superbox bridge

The existing **SuperBOX S7MAX** is our Android host:

- Android 12 / API 31
- 32-bit ARM (`armeabi-v7a`)
- root available
- persistent ADB reachable on the home LAN
- logcat, app sideloading, and Frida-server deployment already established

`android_bridge/` is an on-device companion accessibility service and authenticated HTTP server. GitHub CI builds it as artifact **`myq-superbox-bridge-debug`**.

First live run:

```powershell
$serial = .\scripts\connect_superbox.ps1

# Install a locally obtained official myQ APK/split set; authenticate interactively.
.\scripts\install_myq_superbox.ps1 -PackagePath C:\path\to\myq -AdbSerial $serial

# Build/install our companion and get its local API key.
$key = .\scripts\build_install_android_bridge.ps1 -AdbSerial $serial | Select-Object -Last 1
$headers = @{ 'X-API-Key' = $key }

# Inspect current myQ UI nodes and calibrate state/action selectors.
Invoke-RestMethod http://<superbox-ip>:8765/debug/nodes -Headers $headers
.\scripts\push_bridge_config.ps1 -AdbSerial $serial -ConfigPath config\doors.json

# Read state before any physical command.
Invoke-RestMethod http://<superbox-ip>:8765/status -Headers $headers
```

The native service is scoped only to `com.chamberlain.android.liftmaster.myq`. The Python/UIAutomator implementation under `src/myq_bridge/` is retained as a diagnostic fallback.

## Protocol-recovery tooling

```powershell
# Pull/decompile the exact installed official app.
$dir = .\scripts\pull_myq_apks.ps1
.\scripts\decompile_myq.ps1 -ApkDirectory $dir

# Capture app metadata without committing account credentials/tokens.
.\scripts\capture_myq_logcat.ps1 -Seconds 60
.\scripts\trace_myq_network.ps1 -InstallFridaServer

# Find the opener, including ARP-visible devices that ignore ICMP.
python tools\lan_probe.py --subnet <home-subnet>

# Summarize DNS/TLS/endpoints from a router/AP/switch capture.
python tools\pcap_summary.py capture.pcap --opener-ip <opener-ip>
```

Current Chamberlain support documentation says myQ devices require outbound **TCP 8883** to communicate with MyQ servers. Because 8883 is conventionally MQTT-over-TLS, it is the highest-priority opener traffic to capture, but the port number alone is not treated as proof of MQTT.

## Safety / secrets

A garage door is a physical access-control device. The project:

- requires an API key on local control/state APIs;
- performs no geolocation-triggered opening by default;
- serializes UI commands;
- no-ops when an explicit requested state is already observed;
- refuses a UI toggle when current state is unknown;
- keeps credentials, rotating OAuth tokens, APKs, screenshots/UI dumps, pcaps and raw captures out of Git.

See `docs/APP_BRIDGE.md`, `docs/REVERSE_ENGINEERING.md`, `docs/LAN_RECON.md`, and issues #1–#3 for live evidence gates.
