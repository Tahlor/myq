> 🚫 **DO NOT EXECUTE UNTIL #9 GATE.** This is a deferred hardware archive,
> not an active queue. Execute no physical step here until issue #9 explicitly
> records `SOFTWARE_EXHAUSTED=yes` and `HARDWARE_NOW_JUSTIFIED=yes` in
> `docs/COMPLETION_CRITERIA.md`, with explicit approval for the next
> least-invasive experiment.

# Deferred archive — MYQ-G0401 hardware / firmware attack plan

## Objective

If the mandatory software-exhaustion gate eventually passes, this archive
describes how to investigate a durable local control/state path for the
owner's Chamberlain MYQ-G0401 without adding permanent garage-opener hardware.

This archive records that PSK extraction may not be necessary if later-approved
evidence identifies where a decrypted cloud command crosses from the network
MCU into the PIC/RF side. No hardware strategy is active before the software
gate.

This is dormant execution context, not the current local-agent queue. Do not
restart from a generic audit or use it before the software gate.

## High-value research already established

### Exact target

Live `/jabout` evidence identifies the installed hub as:

- Chamberlain Smart Garage Control Gen 3
- model `MYQ-G0401`
- firmware `1.10`

### Public teardown of the same model family

A 2023 teardown of a Chamberlain Smart Garage Control identifies:

- **Microchip PIC18F67J11** main MCU (128 KiB internal program flash)
- **24C16K** serial EEPROM (~2 KiB)
- **Silicon Labs Si4432** sub-GHz transceiver
- **Fn-Link 6220N-IS** Wi-Fi/BLE module
- apparent PIC programming/test points on the PCB

Source: https://claymccauley.info/index.php/2023/11/20/chamberlain-smart-garage-control-teardown/

The teardown author successfully dumped the 24C16K on a spare unit and found it mostly empty; they hypothesized it stores configuration/pairing material. Treat that as a lead, not a proven mapping for our unit.

### Wi-Fi module is itself a capable MCU

Fn-Link documents the `6220N-IS` as:

- Realtek **RTL8720CS-VA1**
- KM4 + KM0 MCU cores
- Wi-Fi + BLE 5
- UART / I2C / GPIO host interfaces
- 3.3 V operation
- external **8 MiB GD25Q64** SPI flash on the module

Sources:

- https://www.fn-link.com/6220N-IS-IoT-Module-pd44915459.html
- https://fcc.report/FCC-ID/2AATL-6220N-IS/4519624.pdf

The deferred hypothesis is that the TLS-PSK session may terminate inside the
Realtek module, with a simpler plaintext command/status protocol crossing
between the 6220N-IS and PIC18. If this archive is ever activated, prove or
reject that boundary before attacking TLS credentials.

### PIC18 has a standard non-destructive read path

Microchip documents the PIC18F67J11 family as ICSP-programmable. PGC/PGD are RB6/RB7. Configuration/device-ID information remains readable even when code protection is enabled. The PIC has a single program-memory code-protection bit (`CP0`). If protection is enabled, normal program-memory reads are blocked after reset.

Source: https://ww1.microchip.com/downloads/en/DeviceDoc/39644h.pdf

Therefore the first PIC test should be **read config/device ID only**, not an erase/program/debug operation. If `CP0` is off, a normal full flash dump becomes high value. If `CP0` is on, stop; do not erase or attempt invasive bypass on the production unit.

### RF facts

FCC evidence for HBW9545 confirms the hub transmits on multiple opener-control bands including 303, 310, 315, 318, 372.5, 390 MHz and also a 902–927 MHz ISM path. The separate MYQ-G0402 door sensor (HBW9546) uses OOK at approximately 311.885 / 312.507 / 313.126 MHz.

Sources:

- https://fccid.io/HBW9545
- https://fccid.io/HBW9546

The Si4432 can cover these sub-GHz regions. The most valuable RF experiment is therefore **inside the hub, before modulation**: observe the PIC↔Si4432 control/data bus while one authorized command occurs.

---

# Attack order

## Rule: start at the plaintext boundaries

Do **not** begin with PSK extraction, glitching, code-protection bypass, firmware replacement, or blind RF replay.

The preferred order is:

1. PCB identity + bus mapping
2. passive 6220N↔PIC capture
3. passive PIC↔Si4432 capture
4. read-only EEPROM capture
5. read-only PIC ICSP config / optional dump if unprotected
6. read-only 6220N external-flash dump / boot-log work
7. OTA/update-image recovery
8. only then decide whether deeper hardware work is justified

At every stage, keep a known-good cloud/Superbox control path available for recovery.

---

# Phase H0 — preserve production state

Before opening or probing the hub:

- [ ] Confirm current `MYQ-G0401` is online in official app.
- [ ] Confirm current local IP / firmware (`1.10`) and save sanitized baseline.
- [ ] Confirm Broadlink/Superbox fallback still works.
- [ ] Photograph outside labels locally, including revision codes; do not publish serial/MAC.
- [ ] Record whether the owner has a spare G0401. Prefer destructive/desolder tests on a spare.
- [ ] Do not factory-reset, unpair the opener, clear Wi-Fi, or press Learn unless a later step explicitly requires it.

Pass condition: we can return to the current working state after opening/reassembly.

---

# Phase H1 — board confirmation and non-powered mapping

Open the hub only if the enclosure can be reassembled without damage. Photograph both PCB sides at high resolution.

Confirm whether our board revision actually has:

- PIC18F67J11
- 24C16K EEPROM
- Si4432
- Fn-Link 6220N-IS
- GD25Q64 flash on/under the Fn-Link module if visible

Do not assume the public teardown's board revision matches ours.

### Map likely debug / bus points

With power disconnected, use continuity only to identify:

- PIC `MCLR/VPP`, `RB6/PGC`, `RB7/PGD`, VDD, GND
- 24C16K SDA/SCL/VCC/GND
- Si4432 SPI/control pins to PIC
- Fn-Link host-interface pins to PIC (UART/I2C/GPIO candidates)
- unlabeled test pads that land on the above nets

Create a **local-only annotated board image**. Git gets only sanitized pad labels / pin relationships, not serials.

Do not inject voltage or connect a programmer yet.

Pass condition: at least one plausible network-MCU↔PIC bus and one PIC↔RF bus identified.

---

# Phase H2 — if activated: passive 6220N ↔ PIC capture

## Why this is first

The 6220N contains the Wi-Fi/BLE MCU and external flash. The PIC controls the sub-GHz radio. There must be some mechanism by which a network-side command becomes an RF-side action. If that boundary is UART/I2C/SPI/GPIO, it may expose the command **after TLS decryption**.

This is the highest-payoff hypothesis in the project.

## Test sequence

Use a high-impedance logic analyzer only. **No line driving.** Common ground only after confirming voltage levels (expected 3.3 V, verify).

Capture candidate bus lines during these timestamped windows:

1. `NET_A_BOOT` — power-up / reconnect
2. `NET_B_IDLE` — 60 s idle
3. `NET_C_STATUS` — official-app status refresh
4. `NET_D_SENSOR` — manually change door state once using wall control if convenient, observing only
5. `NET_E_COMMAND` — one explicitly authorized MyQ `open` or `close`, only if safe and needed

For UART candidates, auto-test common baud rates and framing. For I2C/SPI, decode address/chip-select activity. Save raw captures locally.

### What success looks like

Any repeatable frame correlated with:

- online/reconnect
- status refresh
- sensor state
- open/close command
- command acknowledgement

If a command/status frame is visible here, stop attacking the PSK. Reverse this local IPC first.

Classify:

- `N0`: no plausible bus found
- `N1`: bus activity decoded but semantics unknown
- `N2`: status/event semantics recovered
- `N3`: open/close command semantics recovered
- `N4`: command can be injected locally without cloud

**Do not inject at N1–N3 on the production unit until framing, direction, voltage, and state checks are understood.**

---

# Phase H3 — passive PIC ↔ Si4432 capture

## Why

Even if the network boundary is opaque, the PIC must program the Si4432 to emit the opener RF command. Observing this bus bypasses RF demodulation and exposes register/FIFO bytes before transmission.

Capture likely SPI/control lines during:

1. idle
2. G0402 sensor event
3. one known opener command
4. if practical, the same action twice separated normally, to see what changes between rolling-code transmissions

Correlate chip-select activity, register writes, FIFO payloads, frequency changes, packet length, and timing.

Do not assume every transmission uses the same modulation or band; HBW9545 supports several opener families.

Classify:

- `R0`: no bus identified
- `R1`: Si4432 register traffic decoded
- `R2`: sensor receive path understood
- `R3`: opener TX payload/register sequence isolated
- `R4`: local re-invocation possible using existing hub hardware

Do **not** blindly replay an old RF payload. Modern opener protocols may use rolling/code-hopping state.

---

# Phase H4 — read-only 24C16K EEPROM capture

The public teardown found a 24C16K and successfully dumped it. It may hold Wi-Fi-independent state such as opener pairing data, counters, device configuration, or IDs.

Preferred order:

1. identify exact part + pins
2. inspect bus activity passively during boot / command / sensor event
3. take a read-only backup using a safe method that does not fight the powered PIC
4. hash the dump
5. search for structure / repeated records / counters / ASCII

If safe and only after a baseline backup, compare snapshots before/after a naturally occurring state change to find mutable fields. Do not deliberately unpair/re-pair solely for diffing on the production hub.

A PSK in this tiny EEPROM would be a bonus, but **do not assume the cloud secret lives here**.

---

# Phase H5 — PIC ICSP configuration first; dump only if unprotected

The PIC18F67J11 has standard ICSP.

### H5a — safe read

Using confirmed test pads and a supported PIC programmer/debugger:

- read device ID
- read configuration words
- determine `CP0`
- do not issue erase/program operations
- do not enable debug if it changes configuration

If device ID or electrical behavior does not match the expected PIC, stop and re-check mapping.

### H5b — fork on CP0

If `CP0 = OFF` (unprotected):

- dump full program flash read-only
- dump config separately
- hash raw image
- preserve local original
- disassemble/static-analyze a copy

Priorities in the PIC image:

- UART/I2C/SPI initialization
- Si4432 register constants and FIFO routines
- strings/tables for opener types/frequencies
- EEPROM record access
- network-module command parser
- boot/update/debug/test handlers

If `CP0 = ON` (protected):

- record that fact
- **stop normal PIC dumping**
- do not mass-erase
- do not voltage-glitch or attempt code-protection bypass on the production unit
- continue H6/H7 and bus capture instead

---

# Phase H6 — 6220N / RTL8720CS firmware and external 8 MiB flash

This is a possible post-gate software target after an approved passive
inter-MCU observation.

The Fn-Link module has a GD25Q64 8 MiB flash according to its module documentation. It is a plausible location for:

- Realtek application firmware
- Chamberlain network/cloud logic
- TLS-PSK identity/material or encrypted credential storage
- OTA metadata
- local setup web assets
- command/status framing used toward the PIC

## H6a — passive boot/log interfaces first

Map module UART/test pads from datasheet + continuity. Power normally and passively sniff boot output at common UART configurations. Do not send bootloader commands yet.

If a console appears, record only sanitized firmware/version/module details.

## H6b — external flash read-only backup

Only after identifying flash pins and safe electrical isolation:

- obtain a full read-only GD25Q64 image
- read at least twice and verify identical hashes
- never write/erase the original
- search copy for ASCII/UTF-8 strings, hostnames, `connect.myqdevice.com`, setup routes, MQTT terms, TLS/PSK references, version strings, update URLs, PIC command words
- run entropy/partition/binwalk-style inspection on a copy

If the flash is memory-mapped/encrypted, document that rather than guessing.

## H6c — static analysis

If executable regions can be identified, use RTL8720/Ameba architecture knowledge to map:

- network startup
- TLS-PSK setup callback
- client identity selection
- TCP/8883 protocol implementation
- UART/I2C/GPIO host protocol
- BLE setup commands
- OTA/update verification

The goal is not necessarily to extract the PSK; learning the **host protocol to the PIC** is enough.

---

# Phase H7 — OTA / update-image recovery

Before considering code-protection bypass, determine whether Chamberlain delivers firmware images in a recoverable form.

Use passive network/DNS evidence and static flash/app strings to locate:

- update hostnames
- manifest endpoints
- firmware version checks
- image format / compression
- signature/encryption metadata

Do not force an update or downgrade the production hub just to capture it.

If a current/older legitimate image can be obtained without device mutation, archive/hash locally and compare against H6 flash contents.

A signed image can still be extremely valuable for static analysis even if we cannot flash our own firmware.

---

# Phase H8 — RF SDR work, only after internal-bus work

Use SDR/RF capture mainly to validate what H3 shows, not as the first reverse-engineering layer.

### Sensor

G0402 is OOK around 312 MHz. Capture repeated closed/open events and identify stable vs changing fields, repetition timing, and channel behavior.

### Opener command

Capture the hub transmission for one authorized action and correlate exact time/frequency with the PIC↔Si4432 bus trace.

Do not attempt broad replay attacks. The objective is interoperability with the owner's own paired device and understanding whether state/counters live in PIC/EEPROM.

---

# Phase H9 — only if all non-invasive routes fail

These are **decision points**, not default tasks:

- entering supported provisioning mode to expose more debug/setup behavior
- controlled command injection on a proven plaintext internal bus
- replacing the network module while retaining PIC/RF side
- replacing PIC firmware if unprotected and fully backed up
- code-protection bypass / fault injection
- invasive desoldering from the production board

Escalate only with an explicit reason, recovery plan, and preference for a spare unit.

The project does **not** need a PSK breakthrough to succeed if N4 or R4 is reached.

---

# Fallback relative-payoff matrix (only after activation)

| Path | Expected payoff | Risk | Activation order |
| --- | --- | --- | --- |
| Passive 6220N↔PIC bus capture | Very high | Low | 1 |
| Passive PIC↔Si4432 capture | Very high | Low | 1 |
| Board/test-pad mapping | Enables everything | Low | 1 |
| 24C16K backup/analysis | Medium-high | Low-medium | 2 |
| PIC config read / CP0 check | Very high if unprotected | Low-medium | 2 |
| 6220N boot UART | High | Low | 2 |
| GD25Q64 flash dump | Very high | Medium | 2 |
| OTA image recovery | High | Low | 2 |
| RF SDR capture | Medium | Low | 3 |
| TLS PSK extraction as end goal | High but uncertain | High | 4 |
| PIC code-protection bypass | Uncertain | Very high | 5 / spare only |
| Custom firmware flashing | Potentially decisive | Very high | 5 / after backups |

---

# Deferred first physical session (only after activation)

The next physical session, if the gate is ever approved, should not touch the
router or cloud TLS path first.

1. Verify working state and power down hub.
2. Open enclosure and photograph both PCB sides.
3. Confirm chip markings/revision against public teardown.
4. Map ground + voltage rails.
5. Continuity-map:
   - 6220N host pins → PIC/test pads
   - PIC → Si4432
   - PIC → 24C16
   - PIC ICSP pads
6. Reassemble enough for safe powered bench observation.
7. Attach logic analyzer **passively** to the most likely 6220N↔PIC bus.
8. Capture boot + idle + status refresh.
9. If decoded traffic is promising, perform one safe authorized command while capturing.
10. In parallel or next, capture PIC↔Si4432 for that same command.
11. Only after passive evidence, attempt EEPROM/PIC/flash reads.

If the local agent only gets through steps 1–8, that is still a good session. Do not rush into driving test pads.

---

# Required local-agent report

```text
G0401 BOARD REVISION: <sanitized>
CHIPS CONFIRMED: PIC / 24C16 / Si4432 / 6220N / GD25Q64

NETWORK->PIC BOUNDARY: N0/N1/N2/N3/N4
- bus: UART/I2C/SPI/GPIO/unknown
- voltage: <value>
- boot traffic: yes/no
- status-correlated frame: yes/no
- command-correlated frame: yes/no

PIC->RF BOUNDARY: R0/R1/R2/R3/R4
- bus: <type>
- Si4432 traffic decoded: yes/no
- sensor event correlated: yes/no
- opener TX correlated: yes/no

EEPROM:
- part confirmed: yes/no
- passive activity: yes/no
- read-only dump: yes/no
- stable hash: yes/no
- notable structure: <sanitized summary>

PIC ICSP:
- pads mapped: yes/no
- device ID read: yes/no
- CP0: ON/OFF/UNKNOWN
- firmware dump: yes/no/not attempted

6220N:
- boot UART/log: yes/no
- GD25Q64 confirmed: yes/no
- flash dump: yes/no
- cloud/protocol strings: <sanitized summary>

OTA IMAGE: recovered/no/unknown
RF SDR: sensor/opener/not attempted

NEXT POST-GATE STEP: <one concrete experiment>
PRODUCTION STATE PRESERVED: yes/no
COMMITS: <sha(s) or none>
RAW CAPTURES: local only
```
