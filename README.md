# myQ software bridge

Software-only integration work for Chamberlain/LiftMaster myQ devices. The goal is reliable home-automation control **without adding hardware to the garage opener**.

## Architecture and priority

We are pursuing three software layers, with production and research separated deliberately:

1. **Official-app bridge — production baseline**
   `Home automation -> Superbox:8765 -> official myQ Android app -> myQ cloud -> opener`

   This is the practical path demonstrated working in 2026 and is the first thing the local agent should make reliable for Broadlink.

2. **True local / opener-side control — preferred end state**
   `Home automation -> opener on LAN`

   First inspect the opener's own supported pairing/provisioning service (`myQ-*`, `setup.myqdevice.com`) and test exact discovered endpoints on its normal LAN IP. If there is no reusable local API, capture the opener's outbound DNS/TLS/TCP 8883 traffic and determine whether a local Chamberlain-service emulator can replace the cloud.

3. **Direct MyQ cloud REST client — experimental evidence only**
   `Home automation -> unofficial MyQ cloud API -> opener`

   The repository contains clean-room direct-cloud tooling because it is useful for protocol comparison and controlled experiments, but **Broadlink does not use it by default**. Community direct-cloud integrations have repeatedly broken as Chamberlain changes/blocks unofficial access. It must not be promoted to production unless independently proven durable, not merely shown to work once.

See **`docs/LIVE_RUNBOOK.md`** for the concrete hands-on sequence. Current execution tickets are #1 (Superbox), #3 (LAN/8883), #5 (pairing/setup service), and #6 (cloud emulation). Issue #2 is explicitly experimental.

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

## Direct pairing / provisioning research

Supported MyQ setup behavior gives us a direct-device foothold: compatible openers expose a temporary `myQ-*` Wi-Fi network and a setup web service reached through `setup.myqdevice.com`.

The repository now includes a GET-only capture tool:

```bash
python tools/setup_portal_capture.py http://setup.myqdevice.com/
```

or, when addressing the setup gateway directly:

```bash
python tools/setup_portal_capture.py http://<SETUP-GATEWAY-IP>/ --host-header setup.myqdevice.com
```

It saves the shipped HTML/JS/CSS under ignored `captures/` and extracts candidate local API strings without submitting Wi-Fi credentials. Issue #5 defines the experiment and the normal-LAN follow-up.

## Opener-side cloud emulation research

Current Chamberlain support says MyQ devices require **TCP 8883** to communicate with MyQ servers. Because 8883 is conventionally MQTT-over-TLS, MQTT is a strong hypothesis, but the port number alone is not proof.

Once the opener is positively identified and its real Chamberlain hostname is observed from DNS/TLS captures, the first redirection test is deliberately passive:

```bash
sudo python tools/tls_clienthello_listener.py --bind 0.0.0.0 --port 8883
```

Temporarily redirect only the discovered opener hostname to that host. The listener records the opener's initial TLS ClientHello metadata (SNI, ALPN, cipher/extension counts) and sends no application command. A connection establishes emulator milestone E0: the opener follows our redirect. Issue #6 contains the TLS/protocol/emulator decision tree.

## Installed-APK static analysis

Pull and decompile the **exact installed official app** before guessing about pairing or broker behavior:

```powershell
$dir = .\scripts\pull_myq_apks.ps1
.\scripts\decompile_myq.ps1 -ApkDirectory $dir
```

Then:

```bash
python tools/summarize_jadx.py <jadx-output>
```

The summary prioritizes:

- setup/provisioning hostnames and code;
- local API paths/listeners;
- MQTT/8883/broker clues;
- TLS pinning, trust-manager and client-certificate clues;
- Wi-Fi/BLE commissioning code.

## Other protocol-recovery tooling

```powershell
# Capture app metadata without committing account credentials/tokens.
.\scripts\capture_myq_logcat.ps1 -Seconds 60
.\scripts\trace_myq_network.ps1 -InstallFridaServer

# Find the opener, including ARP-visible devices that ignore ICMP.
python tools\lan_probe.py --subnet <home-subnet>

# Summarize DNS/TLS/endpoints from a router/AP/switch capture.
python tools\pcap_summary.py capture.pcap --opener-ip <opener-ip>
```

## Experimental direct-cloud tooling

A recent 2026 implementation exposed useful current v6 protocol facts, which this repository clean-room implemented for interoperability research. That tooling is useful as an **oracle** in experiments—for example, correlating a known server-side close command with opener-side TCP 8883 traffic—but it is not the production plan.

Broadlink includes the direct-cloud backend only when `MYQ_ENABLE_EXPERIMENTAL_CLOUD=1` is explicitly set. Do not enable it for normal garage automation.

## Safety / secrets

A garage door is a physical access-control device. The project:

- requires an API key on local control/state APIs;
- performs no geolocation-triggered opening by default;
- serializes UI commands;
- no-ops when an explicit requested state is already observed;
- refuses a UI toggle when current state is unknown;
- never retries through another backend after an ambiguous mutating request;
- keeps credentials, rotating OAuth tokens, APKs, screenshots/UI dumps, pcaps and raw captures out of Git.

See `docs/APP_BRIDGE.md`, `docs/REVERSE_ENGINEERING.md`, `docs/LAN_RECON.md`, `docs/LIVE_RUNBOOK.md`, and issues #1/#3/#5/#6 for live evidence gates.
