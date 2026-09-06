# myQ software bridge

Software-only integration work for Chamberlain/LiftMaster myQ devices. The goal is reliable home-automation control **without adding hardware to the garage opener**.

## Project strategy

We are pursuing three paths in parallel, but they are **not equal priorities**:

1. **Official-app bridge — practical 2026-working path**
   `Broadlink -> Superbox:8765 -> official myQ Android app -> myQ cloud -> opener`
2. **True local / opener-side control — preferred end state**
   Either:
   `Broadlink -> opener directly on LAN`
   or:
   `Broadlink -> local Chamberlain-service emulator <- opener redirected from Chamberlain cloud`
3. **Direct unofficial MyQ cloud API — experimental protocol evidence only**
   `local daemon -> undocumented myQ cloud API -> opener`

The project does **not** treat a reverse-engineered cloud REST/OAuth client as a reliable production solution merely because it can be made to work temporarily. Community integrations repeatedly broke as Chamberlain changed and blocked unofficial access.

## What counts as production-worthy

A path is production-worthy if either:

- it is demonstrably working in 2026 using Chamberlain's supported official app behavior; or
- it is under our control locally and does not depend on undocumented Chamberlain cloud APIs.

Today that means the **official-app/Superbox bridge** is the practical path while true-local work continues.

## Official-app / Superbox bridge

The existing **SuperBOX S7MAX** is our Android host:

- Android 12 / API 31
- 32-bit ARM (`armeabi-v7a`)
- root available
- persistent ADB reachable on the home LAN
- logcat, app sideloading, and Frida-server deployment already established

`android_bridge/` is an on-device companion accessibility service and authenticated HTTP server. GitHub CI builds it as artifact **`myq-superbox-bridge-debug`**.

A June 2026 community implementation independently demonstrated the same general pattern — run the official MyQ Android app in a controlled Android environment, automate it, and expose a local REST API — as a working stateful bridge. Our Superbox-native approach removes the need for a separate ReDroid/Docker host in steady state.

First live run:

```powershell
$serial = .\scripts\connect_superbox.ps1

# Official app is already installed; authenticate interactively if needed.

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

## True local path A — opener pairing/provisioning service

Supported MyQ Wi-Fi setup proves that at least some openers expose a temporary local Wi-Fi AP such as `myQ-XXX` and a setup website at `setup.myqdevice.com`.

Issue #5 investigates the opener's own shipped provisioning UI/API:

1. enter normal supported setup mode without factory-resetting;
2. connect a disposable client to `myQ-*`;
3. capture `setup.myqdevice.com` HTML/JS/API traffic;
4. let the shipped UI reveal its own endpoints;
5. return the opener to normal home Wi-Fi;
6. test those **exact endpoints** against the opener's normal LAN IP;
7. if status or explicit command primitives survive, wrap them in our stable local API.

Best-case result:

```text
Broadlink -> local /garage/* gateway -> opener directly
```

## True local path B — emulate Chamberlain's service

Current Chamberlain support documentation explicitly says MyQ devices require TCP **8883** to communicate with MyQ servers. Port 8883 is conventionally MQTT-over-TLS, but the project does not call the protocol MQTT until live/static evidence confirms it.

Issues #3 and #6 investigate the opener's own outbound client behavior:

1. positively identify the opener;
2. capture DNS, destination host/port, TLS SNI/ALPN/certificate metadata and reconnect cadence;
3. determine whether the opener follows DNS redirection;
4. redirect only the discovered Chamberlain hostname to a passive local listener;
5. characterize normal CA validation vs pinning vs mutual TLS;
6. confirm the application protocol;
7. recover telemetry and command semantics from the opener side;
8. implement the smallest local service emulator that can keep the opener connected and eventually issue one explicit command.

Desired end state:

```text
Broadlink -> local /garage/* API -> local Chamberlain-service emulator
                                      ^
                                      |
                                 existing opener
```

This would remove Chamberlain's cloud from the control loop without adding garage hardware.

## Broadlink integration contract

All working backends should expose the same single-garage interface:

```text
GET  /garage/status
POST /garage/open
POST /garage/close
```

`Tahlor/broadlink` already prefers:

1. `MYQ_LOCAL_URL` — direct opener/local emulator
2. `MYQ_SUPERBOX_URL` — official-app bridge

The direct-cloud provider is excluded by default and appears only when `MYQ_ENABLE_EXPERIMENTAL_CLOUD=1` is explicitly set.

## Experimental direct-cloud code

The repository retains current v6 endpoint/OAuth work under `src/myq_bridge/cloud.py` because it can still be useful as **protocol evidence** — for example, to correlate a known server-side command with opener-side TCP 8883 traffic.

It is **not** the production plan. See issue #2.

Do not spend substantial time bootstrapping OAuth unless a specific opener-side experiment needs it.

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

## Safety / secrets

A garage door is a physical access-control device. The project:

- requires an API key on local control/state APIs;
- performs no geolocation-triggered opening by default;
- serializes UI commands;
- no-ops when an explicit requested state is already observed;
- refuses a UI toggle when current state is unknown;
- never fails over to another provider after an ambiguous mutating request;
- keeps credentials, tokens, APKs, screenshots/UI dumps, pcaps and raw captures out of Git.

## Agent execution order

See:

- #1 — official-app/Superbox bridge
- #5 — pairing/provisioning local service
- #3 — normal-LAN + TCP 8883 characterization
- #6 — local Chamberlain-service emulation
- #2 — experimental direct-cloud evidence only
- #4 — consolidated local-agent handoff
