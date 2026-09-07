# Live MyQ runbook

This is the hands-on execution order for the local agent. **Do not restart a general audit.** Preserve the working software path and execute the highest-value remaining live experiment.

The current hardware/RF research plan is `docs/G0401_HARDWARE_RF_PLAN.md`; issue #7 is the live execution ticket; issue #4 is the current cross-track handoff/index.

## 🚨 Hard stops that still apply

- `pymyq` is completely deprecated. Do not install/debug/revive it.
- Direct-cloud code is experimental evidence/oracle tooling, not the normal Broadlink backend.
- Do not factory-reset the G0401 merely to inspect it.
- Do not brute-force the TLS PSK.
- Do not blind-replay unknown/rolling-code RF.
- Do not use SWD/debug “unlock,” mass erase, option-byte/eFuse writes or firmware flashing merely to inspect the device.
- Raw credentials, device IDs, firmware/NVM, RF captures and UART logs stay local/ignored until sanitized.

## 0. Preserve a working baseline

The practical production/fallback route remains:

```text
Broadlink -> Superbox native bridge -> official myQ Android app -> Chamberlain -> G0401
```

Before and after a hardware session, confirm a read-only status path still works. If the official-app bridge has a specific persistence/reboot bug, handle it in #1, but do not let routine bridge work consume the true-local research session once the baseline is usable.

The experimental direct-cloud tooling has already completed one guarded real `closed -> open` transition and may be used as a controlled event source for passive RF/internal-bus correlation. It is not promoted to production merely because that one test worked.

## 1. Do not redo the already-resolved LAN/BLE/TLS audit

Already established on the owner's unit:

- `MYQ-G0401`, firmware `1.10` via local `/jabout`;
- local TCP 80 setup/metadata surface, no local garage-action endpoint found;
- current-app `CHUB` BLE implementation is commissioning/metadata oriented;
- outbound TCP/8883 proven;
- TLS 1.2 PSK with `TLS_PSK_WITH_AES_128_CBC_SHA`, no SNI/ALPN;
- fake certificate/DNS-only/generic-MQTT cloud replacement is therefore insufficient;
- historical related MyQ firmware proves useful per-device cryptographic material can reside in NVM, but it is not a current G0401 firmware dump.

Use `docs/LAN_RECON.md` for evidence. Revisit these surfaces only when a new firmware/log/static-analysis fact gives a concrete new endpoint or hypothesis.

## 2. First missing fact: identify the actual ceiling-mounted opener

The G0401 is a universal RF remote/gateway and supports multiple opener families. Before interpreting RF, record locally:

- ceiling opener manufacturer + full model;
- approximate manufacture date;
- Learn-button color;
- handheld remote model/FCC ID if trivial;
- G0402 sensor model/FCC ID.

Do not change pairing. Post sanitized model/protocol/frequency hypotheses only.

## 3. Passive RF if receiver equipment is available

Follow #7 / `docs/G0401_HARDWARE_RF_PLAN.md`.

### G0402 state path

FCC evidence places the door sensor around 311.885 / 312.507 / 313.126 MHz with OOK modulation. Capture idle plus one state transition each direction. Recover carrier, timing, burst structure and fields correlated with open/closed if possible.

### G0401 -> opener path

Use the actual ceiling-opener model to choose the band. Capture one known G0401 action and, if available, one corresponding handheld-remote action. Compare modulation/timing and changing fields. **Do not transmit/replay yet.**

No SDR? Continue to board/UART work immediately.

## 4. Map the G0401 board before active probing

Public FCC `HBW9545` photos and the Fn-Link `6220N-IS` module datasheet give us concrete landmarks.

With G0401 power disconnected:

1. photograph both PCB sides and board revision;
2. confirm the `6220N-IS` module orientation;
3. compare to FCC internal photos;
4. continuity-map accessible test pads/header pins to the module, prioritizing:
   - GND;
   - pin 32 `UART_LOG_TXD`, pin 31 `UART_LOG_RXD`;
   - pins 63/64 communication UART RX/TX;
   - pins 54/55 SWDIO/SWCLK;
   - pins 35/36 I2C.

Do not remove the module shield just to do this mapping.

## 5. Highest-value live test: passive internal UART/bus capture

**Listen only first. Do not connect a USB-TTL TX lead to the board.** Verify logic voltage before attaching any analyzer.

### Log UART

Capture `UART_LOG_TXD` from cold boot; try 115200 bps first. Correlate separate windows for boot, Wi-Fi association, idle, `/jabout`, app status refresh and one controlled action if authorized.

Useful output includes firmware/build/partition information, OTA host/path, broker/NVM/RF task names and diagnostic-shell clues.

### Communication UART

If module pins 63/64 route off-module, capture both directions simultaneously while generating bounded known events.

Correlation windows:

1. boot;
2. idle;
3. G0402/manual sensor transition;
4. status refresh;
5. exactly one explicit G0401 garage action.

**Priority discovery:** a repeatable frame appears on this bus immediately before the G0401 transmits RF / the garage moves.

If that happens, stop lower-value exploration and characterize the frame/bus. The preferred end state is to invoke this already-paired RF subsystem locally rather than reimplement rolling code.

## 6. Read-only SWD after pad/voltage mapping

The 6220N-IS exposes SWD, but RTL8720CS also supports debug protection.

First probe only:

- identify chip/core;
- query protection state;
- read a small region if permitted;
- if stable, acquire firmware/NVM and require repeated-read hash agreement.

If the debugger offers only destructive unlock/recover, stop and report it. Do not change eFuse/security state.

## 7. Pursue exact current firmware in parallel

Best acquisition order:

1. read-only SWD/software path;
2. natural OTA/update package capture;
3. safe external SPI-flash read with G0401 unpowered;
4. isolation/desoldering only later with explicit approval;
5. Realtek ROM/UART boot mode only after pin mapping/backups/recovery are understood.

The public module datasheet lists an 8 MiB SPI NOR inside the 6220N-IS module. A physical dump may still be encrypted if Chamberlain enabled RTL8720CS flash protection, so it is not the first move.

Search an exact current G0401 firmware image for:

- internal UART/I2C/SPI protocol;
- RF protocol/frequency tables and command constructors;
- G0402 sensor parser;
- setup/diagnostic/manufacturing commands;
- OTA path/version/image format;
- NVM/PSK identity/key-wrap logic;
- MQTT/broker strings.

Use the historical MyQ firmware only as a structural reference; never transplant its device key/offset assumptions into the owner's unit without exact-current-image evidence.

## 8. One bounded local-control experiment only after semantics are known

Implementation preference:

1. reuse an internal command bus into the G0401's existing paired RF subsystem;
2. invoke a discovered local/test firmware primitive that calls the normal RF routine;
3. only then consider implementing a new legitimate paired RF remote for the exact ceiling-opener protocol.

Before any action:

- current state known;
- path physically clear;
- explicit open/close semantics understood, not blind toggle;
- one command only;
- no retry after an ambiguous result;
- final state independently verified.

Any successful local implementation must expose the stable Broadlink contract:

```text
GET  /garage/status
POST /garage/open
POST /garage/close
```

## 9. Cloud emulator is now opportunistic

Issue #6 is not the primary attack while the device's PSK remains unknown. Return to it only if exact firmware/NVM work gives us the current PSK/identity or another legitimate way to reproduce the TLS session. Then decrypt/classify the application protocol and confirm or reject MQTT.

Do not spend a hardware session re-proving TCP/8883 or attempting certificate tricks already ruled out by the PSK handshake.

## 10. Keep moving when one track is blocked

- no SDR -> board/UART/SWD;
- no debugger -> RF/log-UART/OTA;
- SWD locked -> OTA then external-flash planning;
- external flash encrypted -> internal-bus/RF still valuable;
- no internal bus -> classify exact RF and examine legitimate new-remote pairing;
- exact firmware reveals PSK -> resume #6;
- a step becomes destructive -> stop that step and continue a reversible track.

## Handoff requirement

Use the detailed template in #7. At minimum report:

```text
WORKING BASELINE: PASS/FAIL
CEILING OPENER: <sanitized model + Learn color>
RF SENSOR: R0/R1/R2
RF OPENER: T0/T1/T2/T3
BOARD: log UART / comm UART / SWD mapped yes/no
INTERNAL BUS: B0/B1/B2/B3/B4
SWD/FIRMWARE: D0/D1/D2/D3
EXACT FW 1.10 IMAGE: yes/no
LOCAL STATUS: yes/no
LOCAL COMMAND: yes/no
PSK/8883: blocked/actionable
COMMITS: <list or none>
NEXT HIGHEST-VALUE TEST: <one sentence>
BLOCKERS/TOOLS NEEDED: <short list>
```

Update #7 whenever a meaningful level changes so another agent can resume without repeating the experiment.