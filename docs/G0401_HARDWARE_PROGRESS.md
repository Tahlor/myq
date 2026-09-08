# G0401 hardware research progress

This is the sanitized handoff for the current physical-research track. The
detailed execution order and safety boundaries are in
[`G0401_HARDWARE_RF_PLAN.md`](G0401_HARDWARE_RF_PLAN.md) and
[`G0401_HARDWARE_ATTACK_PLAN.md`](G0401_HARDWARE_ATTACK_PLAN.md).

## Live baseline — 2026-09-07

- The active host is on the private `192.168.187.0/24` LAN.
- A read-only request to the already correlated LAN candidate's `/jabout`
  endpoint returned `200` and identified `MYQ-G0401`, firmware `1.10`,
  manufactured by Chamberlain Group. The device reported Internet connected.
- The candidate's read-only root and setup pages remain reachable on TCP 80.
  No configuration route or garage action was called.
- Router conntrack reported one established outbound TCP/8883 session from
  the candidate. Conntrack exposes no payload, so it adds no MQTT or
  application-protocol evidence.
- The Superbox native bridge returned `ok` from `/health`; an unauthenticated
  `/status` request returned `401`; an authenticated read-only status call
  reported the configured garage door as `open`.
- Android reported version 12 / `armeabi-v7a`; the official myQ app and native
  bridge packages were installed, and both expected accessibility services were
  enabled. No garage command, reset, pairing change, or UI action was issued.

The production software baseline is therefore **PASS** and was preserved.

## Hardware handoff

```text
CEILING OPENER: unknown; Learn-button color unknown
RF SENSOR: R0 / not attempted
RF OPENER: T0 / not attempted

BOARD:
- revision matched FCC photos: not attempted
- PIC18F67J11 / 24C16K / Si4432 / 6220N-IS / GD25Q64: not confirmed in this session
- mapped pads: none

INTERNAL BUS: not attempted (no powered-down board session)
DEBUG/FIRMWARE: not attempted (no debugger or exact G0401 image)
LOCAL STATUS: no local control/status primitive proven; current level L0
LOCAL COMMAND: no
PSK/8883: PSK handshake evidence exists; current PSK not recovered; emulator blocked
PRODUCTION STATE PRESERVED: yes
```

## Next physical session

The next highest-value experiment is a reversible bench session on the removable
G0401 hub: with power disconnected, photograph and identify the board revision,
confirm the module/IC markings, and continuity-map GND plus the documented
6220N-IS log/communication UART, SWD, PIC ICSP, EEPROM, and Si4432 nets. Only
after voltage confirmation should a high-impedance analyzer passively capture
boot, idle, status-refresh, and (if explicitly authorized and physically safe)
one command window. Do not connect a transmit lead, erase/unlock debug state,
flash firmware, factory-reset/pair the hub, or replay RF.

That session requires physical access to the removable hub and the actual
ceiling-opener model/Learn-button information. A DMM and a logic analyzer or
3.3 V RX-only capture tool are not observable in the current software session;
an SDR is optional and must not block UART/bus work. No board photos, firmware,
RF captures, serials, MACs, or credentials were committed.
