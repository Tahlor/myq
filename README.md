# myQ software bridge

Software-only integration work for Chamberlain/LiftMaster myQ devices. The goal is to regain reliable home-automation control **without adding hardware to the garage opener**.

## Tracks

### A. Official-app bridge — fastest path

Run the official myQ Android app on the existing SuperBOX S7MAX and drive it through Android's accessibility/UI-automation surface. A small LAN REST service exposes state and commands to Home Assistant or anything else on the network.

This deliberately keeps Chamberlain's own app responsible for authentication and cloud protocol details. The first bring-up target is myQ `5.243.1.73243`, which multiple users reported in 2026 can authenticate in non-Play-Integrity Android environments. Once authenticated, we will test current versions and session persistence rather than assuming an old build must remain permanently installed.

### B. Protocol recovery — preferred end state

Use the official app and the Wi-Fi opener as ground truth to recover:

1. current app/cloud endpoints and request semantics;
2. whether authenticated app requests can be replayed directly by our own client;
3. the opener's LAN identity and exposed services;
4. its outbound DNS/TLS/MQTT behavior;
5. whether the opener can be redirected to a local broker/service without firmware or hardware changes.

If B succeeds completely, Track A becomes a fallback rather than the production architecture.

## Existing hardware we reuse

The project assumes the already-owned **SuperBOX S7MAX** documented in `Tahlor/superbox`:

- Android 12 / API 31
- 32-bit ARM (`armeabi-v7a`)
- root available
- persistent ADB reachable on the home LAN through the existing discovery script
- logcat and app sideloading available

No fixed ADB IP/port is treated as authoritative; use `scripts/connect_superbox.ps1`.

## Quick start

```powershell
# 1. Connect to the Superbox
.\scripts\connect_superbox.ps1

# 2. Install a locally obtained myQ APK / split-APK directory
.\scripts\install_myq_superbox.ps1 -PackagePath C:\path\to\myq

# 3. Pull the installed APKs for clean-room inspection
.\scripts\pull_myq_apks.ps1

# 4. Run the bridge after Python dependencies are installed
$env:MYQ_API_KEY = '<random secret>'
$env:MYQ_ADB_SERIAL = (.\scripts\connect_superbox.ps1)
python -m myq_bridge
```

Then inspect `http://<bridge-host>:8765/status` with `X-API-Key: <secret>`. Until selectors are calibrated against the live myQ UI, use `/debug/tree` to capture the accessibility hierarchy and fill `config/doors.example.json`.

## Safety / security

A garage door is a physical access-control device. The bridge:

- requires an API key;
- performs no automatic opening based on geolocation by default;
- serializes door commands;
- will not issue a toggle when the observed state already matches the requested state;
- keeps captured account tokens, APKs, screenshots, UI dumps and pcaps out of Git via `.gitignore`.

See `docs/APP_BRIDGE.md`, `docs/REVERSE_ENGINEERING.md`, and `docs/LAN_RECON.md`.
