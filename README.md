# myQ software-only bridge

This repository builds a reliable software-only integration for the owner's
existing Chamberlain/LiftMaster myQ system. The current goal excludes ratgdo,
relays, ESP32s, wiring changes, replacement logic boards, and other
garage-side hardware.

## Authority

- **Issue #9 is the only active implementation/research worklist.** Its job is
  to exhaust credible software-only routes and record evidence.
- **Issue #4 is the only handoff/index.** It points to the current state and
  the next #9 item; it is not a competing queue.
- Issues **#1-3 and #5-8 are closed archive/superseded records**. Do not use
  them as execution instructions.
- Hardware is deferred. It becomes eligible only when #9 explicitly records
  both `SOFTWARE_EXHAUSTED=yes` and `HARDWARE_NOW_JUSTIFIED=yes`.

The **current default proven software path** keeps the official authenticated
myQ Android process on the rooted SuperBOX S7MAX but bypasses UI clicking. A
Frida 17.9.0 harness invokes the official app's own internal garage API. A live
dry-run on 2026-09-09 found exactly one `devices.a0` garage in `CLOSED` state,
reached both Chamberlain `open` and `close` v6 wrappers, and suppressed both
before the network layer. No physical movement occurred.

```text
home automation -> Superbox -> official myQ process/internal SDK -> Chamberlain -> G0401
```

Provider preference is now explicit:

1. **true local / no Chamberlain cloud** ? preferred end state and active research target;
2. **official-app internal SDK dispatch** ? default proven fallback;
3. **Accessibility/Single Tap or UIAutomator** ? retained compatibility fallback;
4. **Linux-native direct cloud** ? bounded fallback/oracle work, not production yet.

The packaged internal dry-run is `scripts/invoke_myq_internal_action.ps1`; it
requires the validated Frida 17.9.0 pair and defaults to network-suppressed
probe mode. Live actuation additionally requires `-Execute` and an exactly
matching `-ConfirmAction`. Direct cloud remains secondary research. `pymyq`
is permanently deprecated; see [docs/PYMYQ_DEPRECATION.md](docs/PYMYQ_DEPRECATION.md).

## #9 software-exhaustion order

Before hardware, #9 must evaluate and record an outcome for every credible
software route:

1. Preserve and regression-test the proven official-app internal SDK dispatch;
   treat Accessibility/UI automation as fallback, not the primary command path.
2. Keep the official-app bridge usable: Accessibility plus a guarded Single
   Tap path, the Python/UIAutomator fallback, the notification state
   side-channel, and a screenshot/vision third driver.
3. Test backup/clone of an authenticated Android environment without putting
   credentials, tokens, APKs, screenshots, or UI dumps in Git. ReDroid is a
   spare-host option only if the Superbox path is blocked.
4. Use alternate current myQ Community/Craftsman clients as code oracles only;
   do not add an unlicensed or deprecated runtime dependency.
5. Exhaust evidence-driven normal-LAN HTTP reads, then passive OTA/current
   firmware discovery. Do not enter setup mode, reset, re-pair, or force an
   update in an unattended run.
6. Fingerprint the Realtek/AmebaD RTL8720CS lineage and PSK-provisioning
   lineage, and run the offline historical MCU parser against sanitized
   evidence only.
7. Bound current-2026 MFA/refresh direct-cloud experiments, then check
   Ezlo SoftHub/Tricon and IFTTT/partner surfaces as compatibility oracles.

The exact order and evidence template are in
[docs/LIVE_RUNBOOK.md](docs/LIVE_RUNBOOK.md). Completion and the hardware gate
are in [docs/COMPLETION_CRITERIA.md](docs/COMPLETION_CRITERIA.md).

The long-lived architecture rules are in [docs/GOALS_AND_PROVIDER_HIERARCHY.md](docs/GOALS_AND_PROVIDER_HIERARCHY.md), and the exact recovery procedure for future APK/API changes is in [docs/FUTURE_CHANGE_RECOVERY.md](docs/FUTURE_CHANGE_RECOVERY.md).

## Current evidence that must not be lost

The current target is `MYQ-G0401`, firmware `1.10`. Read-only evidence shows
normal-LAN TCP/80 setup/metadata behavior and no proven local garage-action
endpoint. The device has an outbound TCP/8883 session. Its observed TLS 1.2
handshake uses `TLS_PSK_WITH_AES_128_CBC_SHA` with no SNI or ALPN. The port does
not prove MQTT; a fake certificate, DNS-only redirect, or generic MQTT broker
is insufficient without the per-device PSK and encrypted application
protocol.

The current app's `CHUB` BLE surface is commissioning/metadata oriented; no
proven operation command exists there. Historical `myq_aes`/NVM evidence and
the historical MCU parser are useful structural leads, not current-device
credentials. Preserve the working official-app path and the guarded direct-
cloud one-off as experimental evidence.

## Official-app bridge quick start

The SuperBOX is Android 12/API 31, 32-bit ARM (`armeabi-v7a`), rooted, and
reachable through network ADB. Install and authenticate the exact official APK
interactively, then build the companion:

```powershell
$serial = .\scripts\connect_superbox.ps1
.\scripts\install_myq_superbox.ps1 -PackagePath C:\path\to\myq -AdbSerial $serial
$key = .\scripts\build_install_android_bridge.ps1 -AdbSerial $serial | Select-Object -Last 1
$headers = @{ 'X-API-Key' = $key }
Invoke-RestMethod http://<superbox-ip>:8765/status -Headers $headers
```

Bring the official dashboard to the foreground before protected reads. Copy
`config/doors.example.json` to ignored `config/doors.json` and calibrate only
read-only state selectors first. Every explicit action requires matching
confirmation, a stable observed pre-state, one request at most, and a fresh
verified post-state. The optional native notification side-channel stores only
normalized state and time; it is advisory and must never authorize a command.

## Experimental tools and hygiene

`src/myq_bridge/` is the UIAutomator diagnostic/second driver. `tools/`
contains read-only LAN/TLS observation helpers and offline historical parsers.
`myq-cloud` is deliberately bounded experimental oracle tooling and requires
`MYQ_ENABLE_EXPERIMENTAL_CLOUD=1`; no checked-in service deploys it.

Keep credentials, OAuth/session tokens, APKs, firmware/NVM, pcaps, screenshots,
UI dumps, and live identifiers in ignored local paths. Never use a command,
toggle, reset, re-pair, RF replay, setup transition, or hardware probe as a
connectivity test.
