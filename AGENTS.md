# Agent guidance

## Authority

- Issue #9 is the only active implementation/research worklist.
- Issue #4 is the only handoff/index.
- Issues #1-3 and #5-8 are closed archive/superseded records, not execution
  instructions.
- The official myQ Android app on the SuperBOX S7MAX is the production
  baseline. Direct cloud is experimental/current-2026 fallback-oracle only.
- Hardware is deferred until #9 explicitly records
  `SOFTWARE_EXHAUSTED=yes` and `HARDWARE_NOW_JUSTIFIED=yes`.

## Objective

Build a reliable software-only integration for the owner's existing myQ
system. Do not require ratgdo, relays, ESP32s, wiring changes, replacement
logic boards, or other garage-side hardware before the #9 gate.

Follow [docs/LIVE_RUNBOOK.md](docs/LIVE_RUNBOOK.md) for the active order and
[docs/COMPLETION_CRITERIA.md](docs/COMPLETION_CRITERIA.md) for the gate. Keep
the Superbox official-app bridge usable while protocol recovery proceeds.
The required software lanes include internal app dispatch, Accessibility and
Single Tap, UIAutomator, notification and screenshot/vision drivers,
authenticated-environment backup/clone, alternate myQ Community/Craftsman
code oracles, normal-LAN HTTP, passive OTA/current firmware, RTL8720CS and PSK
lineage, the offline MCU parser, bounded MFA/refresh cloud evidence, Ezlo
SoftHub/Tricon, IFTTT/partners, and ReDroid only as a spare host.

## Evidence and safety

Prefer live behavior, then current APK/runtime analysis, current official
behavior, maintained third-party code, and historical evidence. Do not treat
historical API behavior or a generic MQTT/fake-certificate plan as current
proof. Preserve these facts: G0401 firmware 1.10; normal-LAN TCP/80; outbound
8883; TLS 1.2 `TLS_PSK_WITH_AES_128_CBC_SHA` with no SNI/ALPN; commissioning-
only CHUB BLE; historical `myq_aes`/NVM and MCU parser evidence; the working
official-app path; and the guarded direct-cloud one-off as experimental.

Never use a garage command, toggle, RF replay, setup mode, reset, re-pair,
reboot/reset of the Superbox, or hardware probe as a connectivity test. For a
future authorized live command, read the explicit current state, serialize
the request, send at most one action, and verify the requested post-state.
This unattended run permits read-only ADB/static/network inspection only.

## Repository hygiene

- Work on `master` unless explicitly told otherwise.
- Never revive the permanently deprecated `pymyq` client.
- Keep credentials, session tokens, APKs, firmware/NVM, pcaps, screenshots,
  UI dumps, and live identifiers out of Git.
- Prefer scripts that produce sanitized summaries plus ignored raw artifacts.
- Add parser/state/policy tests whenever evidence makes that possible.
- Record decisive runtime findings in the canonical docs and update the #4
  handoff/index after meaningful #9 progress.

## Superbox

Reuse `Tahlor/superbox` as the canonical device-access reference. The S7MAX
is Android 12, 32-bit ARM, rooted, and reachable through network ADB. Do not
permanently alter root/security properties merely to satisfy myQ; use
reversible, read-only checks first because the box supports other projects.
