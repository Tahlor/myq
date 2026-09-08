> 🚫 **DO NOT EXECUTE UNTIL #9 GATE.** This is a sanitized hardware archive,
> not an active work queue. Do not open the hub, attach a probe, reset, re-pair,
> dump, or replay RF from this document until issue #9 explicitly records
> `SOFTWARE_EXHAUSTED=yes` and `HARDWARE_NOW_JUSTIFIED=yes` in
> `docs/COMPLETION_CRITERIA.md`.

# G0401 deferred-hardware progress

## Preserved software evidence — 2026-09-07

- A read-only GET /jabout against the correlated LAN candidate identified
  Chamberlain MYQ-G0401, firmware 1.10, with Internet connected.
- The normal-LAN TCP/80 root and setup pages remain reachable. No configuration
  route or garage action was called.
- Router conntrack reported an established outbound TCP/8883 session. It
  exposed no payload, so MQTT and application semantics remain unproven.
- The live TLS handshake is TLS 1.2 PSK using
  TLS_PSK_WITH_AES_128_CBC_SHA, with no SNI or ALPN.
- The current Android CHUB BLE surface is commissioning/metadata oriented:
  about, scan_results, and config_save. No normal BLE open/close command is
  proven.
- Historical related firmware contains per-device myq_aes/NVM material and
  offline unwrap logic. The public historical MCU frame parser is tested, but
  neither is proof about current G0401 layout or semantics.
- The official-app/Superbox path remains the production-capable software
  baseline. The direct-cloud client has one authorized sensor-verified command
  result and remains experimental/oracle evidence only.
- No reset, pairing change, hardware action, or unapproved garage command was
  used for this record.

## Dormant handoff state

    CEILING OPENER: unknown; Learn-button color unknown
    BOARD REVISION: not inspected
    G0401 CHIPS: not confirmed from the owner's board
    INTERNAL BUS: not attempted
    DEBUG/FIRMWARE: not attempted
    OTA IMAGE: not acquired
    LOCAL STATUS: not proven; level L0
    LOCAL COMMAND: no
    PSK/8883: current PSK not recovered; emulator blocked
    PRODUCTION STATE PRESERVED: yes
    SOFTWARE_EXHAUSTED: no
    HARDWARE_NOW_JUSTIFIED: no

## What remains behind the gate

If and only if issue #9 later satisfies the activation gate, resume with the
least-invasive passive comparison described in the renamed
docs/G0401_DEFERRED_HARDWARE_ATTACK_PLAN.md and
docs/G0401_DEFERRED_HARDWARE_RF_PLAN.md. The dormant sequence begins with
board identity and power-off mapping, then passive bus observation. It does
not begin with reset, firmware write, debug unlock, RF transmission, or
command injection.

The exact missing physical prerequisites are access to the removable G0401
hub, the actual ceiling-opener model/Learn-button information, and a DMM plus
high-impedance analyzer if passive work is eventually approved. No board
photos, firmware, RF captures, serials, MACs, or credentials belong in Git.
