# Live runbook — issue #9 only

Issue #9 is the only active implementation/research worklist. Issue #4 is the
handoff/index. This file is the software-only execution order; it does not
authorize a physical experiment or a production direct-cloud deployment.

## Hard stops for this unattended run

- Do not open, close, toggle, or replay a garage command.
- Do not reboot, reset, re-pair, or put the opener or Superbox into setup mode.
- Do not attach probes, transmit RF, flash firmware, unlock debug protection,
  or change root/security properties.
- Do not brute-force the TLS PSK or treat a generic MQTT/fake-certificate plan
  as a solution.
- Keep credentials, sessions, APKs, firmware/NVM, captures, screenshots, and
  UI dumps local and ignored.
- `pymyq` is permanently deprecated. Do not install, debug, or revive it.

Read-only ADB, APK/static analysis, local parser tests, and passive network
inspection are allowed. Any physical or mutating test must remain a precisely
described pending item for an owner-authorized run.

## Baseline and facts

The production baseline is:

```text
home automation -> Superbox S7MAX bridge -> official myQ Android app -> cloud -> G0401
```

The SuperBOX is Android 12/API 31, 32-bit ARM (`armeabi-v7a`), rooted, and
reachable through network ADB. The target is `MYQ-G0401`, firmware `1.10`.
Read-only evidence establishes normal-LAN TCP/80 setup/metadata behavior,
outbound TCP/8883, and TLS 1.2 PSK
`TLS_PSK_WITH_AES_128_CBC_SHA` with no SNI/ALPN. No local garage-action
endpoint is proven. The current APK's `CHUB` BLE path is commissioning and
metadata oriented; it has no proven operation command. Historical
`myq_aes`/NVM and MCU-parser work is structural evidence only.

Preserve the working official-app path. The guarded direct-cloud read/command
one-off is useful current-2026 evidence, but remains an experimental fallback
oracle and never changes the production baseline.

## #9 software exhaustion sequence

Record each result in a sanitized note and link it from the #4 handoff. Work
down this list before considering either deferred hardware archive.

### 1. Official APK/runtime: UI-free internal dispatch

Pull and decompile the exact installed official APK:

```powershell
$dir = .\scripts\pull_myq_apks.ps1
.\scripts\decompile_myq.ps1 -ApkDirectory $dir
python tools\summarize_jadx.py <jadx-output>
```

Inventory exported activities/services/receivers, deep links, shortcuts,
widgets, intent extras, notification actions, and call sites that dispatch
explicit open/close operations. Prefer a read-only component inventory and
static call graph. Do not invoke an unknown component against the real
opener. The known user-facing dashboard activity is
`com.chamberlain.myq.main.HomeTabsActivity`; the package Splash/Login path has
shown a focus-loss ANR, so the dashboard path remains the foreground baseline.

### 2. Keep four app-bridge drivers available

1. **Accessibility + Single Tap:** use the native package-scoped bridge, a
   stable state selector, and one explicit tap only after an authorized future
   test has a known state and physical verification plan. Never use a blind
   toggle as a probe.
2. **UIAutomator fallback:** retain `src/myq_bridge/` for hierarchy dumps,
   selector calibration, and a second driver when the native service is not
   enough. It must remain foreground-only and fail closed on unknown state.
3. **Notification side-channel:** capture notification text/timestamps as an
   advisory state signal. It cannot authorize an action and must be compared
   with a fresh app read.
4. **Screenshot/vision driver:** add a read-only screenshot/vision observer
   for layouts that expose state visually but not reliably in the accessibility
   tree. Keep raw screenshots ignored and require independent state confirmation
   before any future command.

The bridge HTTP host must survive the browser/MFA handoff, remain scoped to the
official package, and never launch myQ from a background LAN request. Rebind
the accessibility component after APK updates without removing other enabled
services.

### 3. Authenticated Android environment recovery

Document a reversible backup/clone path for the authenticated app environment
and its app-local configuration. Prove what survives an app-process restart,
APK update, and (only in a separately authorized run) a host reboot. Do not
copy raw credentials or OAuth values into the repository. ReDroid may be used
as a spare Android host only if the Superbox path is blocked; it is not the
production baseline and does not justify changing the garage hardware.

### 4. Alternate clients as code oracles

Inspect current myQ Community/Craftsman clients, where available, for endpoint,
OAuth, notification, and UI behavior clues. Treat them as code/documentation
oracles only; do not vendor unlicensed code, add a deprecated runtime, or
replace the official-app baseline with an unofficial client.

### 5. Evidence-driven local network and firmware lanes

- Query the confirmed normal-LAN IP with exact, read-only HTTP `GET`/metadata
  paths already evidenced on TCP/80. Do not broad-fuzz, submit setup forms, or
  enter setup/AP mode. A setup-mode path is not an active prerequisite.
- Catalog passive OTA/current-firmware evidence from the app, DNS/router
  observations, shipped resources, and naturally occurring update artifacts.
  Do not force an update or downgrade.
- Fingerprint the Realtek/AmebaD `RTL8720CS` / `6220N-IS` lineage from exact
  APK/FCC/datasheet evidence and inspect software-visible OTA, boot-log, and
  module-interface clues.
- Trace PSK-provisioning lineage without guessing or brute-forcing secrets.
  The live 8883 PSK handshake needs the per-device PSK and encrypted
  application protocol; MQTT remains unconfirmed.
- Run `tools/myq_firmware_psm.py` and the historical MCU parser
  (`tools/historical_mcu_protocol.py`) only against sanitized historical or
  owner-authorized local images. Never transplant historical keys/layouts into
  the current device.

### 6. Bounded current-2026 cloud and partner fallback

The clean-room `myq-cloud` client may be used for read-only MFA/refresh/session
experiments and correlation evidence only. It requires
`MYQ_ENABLE_EXPERIMENTAL_CLOUD=1`, has no checked-in service deployment, and
must not be placed behind the normal Broadlink path. Do not retry an ambiguous
mutation. A current session refresh or guarded one-off is evidence, not a
production promotion.

Check Ezlo SoftHub/Tricon and IFTTT/partner surfaces for supported
read/status or command contracts, authentication requirements, and current
availability. Keep these as bounded compatibility research; do not assume a
partner route controls this exact G0401 until live evidence proves it.

## Evidence handoff and hardware gate

For each lane, record `PROVEN`, `DISPROVEN`, or `BLOCKED`, the evidence date,
the sanitized artifact path, and the next safe observation. Update the #4
handoff with one highest-value software item only.

Hardware remains in `docs/G0401_DEFERRED_HARDWARE_*`. No agent may execute those
documents until issue #9 itself explicitly records:

```text
SOFTWARE_EXHAUSTED=yes
HARDWARE_NOW_JUSTIFIED=yes
```

The completion gate is defined in
[`COMPLETION_CRITERIA.md`](COMPLETION_CRITERIA.md). Until both values are
present, the next action is another software-only #9 lane or a clearly stated
owner-input blocker—not hardware.
