# Completion and hardware gate

Issue #9 is the only active worklist. Issue #4 is the handoff/index. This
project is not hardware-ready merely because a cloud call or a UI click once
worked.

## Current gate

```text
PRODUCTION_BASELINE: official MyQ Android app on SuperBOX S7MAX
SOFTWARE_EXHAUSTED: no
HARDWARE_NOW_JUSTIFIED: no
```

Hardware is deferred until issue #9 explicitly records both exact values below
after credible software-only routes have been exhausted:

```text
SOFTWARE_EXHAUSTED=yes
HARDWARE_NOW_JUSTIFIED=yes
```

The deferred plans are archives, not an active queue:
`docs/G0401_DEFERRED_HARDWARE_ATTACK_PLAN.md`,
`docs/G0401_DEFERRED_HARDWARE_RF_PLAN.md`, and
`docs/G0401_DEFERRED_HARDWARE_PROGRESS.md`.

## Required software gates

1. **Authority gate.** README, AGENTS, this file, and the live runbook point
   only to #9/#4 for current work. Closed issue records are not execution
   instructions, and `pymyq` is absent from runtime dependencies.
2. **Baseline gate.** The official Android app remains installable and
   authenticated on the Superbox; the native bridge, Accessibility + Single
   Tap path, UIAutomator fallback, notification side-channel, and screenshot/
   vision observer are documented with fail-closed state handling.
3. **Runtime-recovery gate.** Exact-APK internal dispatch, authenticated
   Android backup/clone, alternate myQ Community/Craftsman code oracles, and
   ReDroid as a spare host have been checked or have a dated blocker.
4. **Local-evidence gate.** Evidence-driven normal-LAN HTTP, passive OTA/current
   firmware discovery, RTL8720CS/AmebaD fingerprinting, PSK-provisioning
   lineage, and the offline historical MCU parser have each been checked or
   have a dated blocker. Setup mode, resets, pairing changes, and forced
   updates are not prerequisites.
5. **Fallback gate.** Bounded current-2026 MFA/refresh direct-cloud evidence,
   Ezlo SoftHub/Tricon, and IFTTT/partner surfaces have been checked or have a
   dated blocker. Direct cloud remains fallback/oracle evidence only and has
   no production deployment template.
6. **Safety gate.** No unattended run sends a garage command, and no command
   is accepted without an explicit action, known stable pre-state, one-shot
   serialization, and independently verified post-state. Raw credentials,
   tokens, APKs, firmware/NVM, captures, screenshots, and UI dumps remain
   ignored/local.

## Preserved evidence

The target is `MYQ-G0401`, firmware `1.10`. Normal-LAN TCP/80 exposes
setup/metadata behavior; no local garage-action endpoint is proven. Outbound
TCP/8883 is observed, with TLS 1.2
`TLS_PSK_WITH_AES_128_CBC_SHA` and no SNI/ALPN. The port does not prove MQTT;
fake certificates, DNS-only redirection, and generic MQTT are insufficient
without the per-device PSK and encrypted application protocol. The current
APK's `CHUB` BLE path is commissioning/metadata oriented, with no proven
operation command. Historical `myq_aes`/NVM and MCU-parser work remains
historical evidence only.

The official-app/Superbox path is the working production baseline. A guarded
current-2026 direct-cloud one-off has value as experimental evidence, but does
not satisfy the production or software-exhaustion gate by itself.

## What counts as completion

A software-only milestone is complete only when the baseline read path is
repeatable, explicit actions are fail-closed and post-state verified, the
software lanes above have dated evidence or blockers, and #4 has a concise
handoff. Hardware eligibility is a separate decision and requires the two
explicit #9 values; it is never inferred from schedule pressure, convenience,
or a blocked cloud session.
