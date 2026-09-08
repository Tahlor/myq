> 🚫 **DO NOT EXECUTE UNTIL #9 GATE.** This is a deferred hardware archive,
> not an active queue. Execute no physical step here until issue #9 explicitly
> records `SOFTWARE_EXHAUSTED=yes` and `HARDWARE_NOW_JUSTIFIED=yes` in
> `docs/COMPLETION_CRITERIA.md`, with explicit approval for the next
> least-invasive experiment.

# Deferred archive — MYQ-G0401 hardware / firmware / RF plan

## Objective

If the mandatory software-exhaustion gate eventually passes, this archive
describes how to investigate a reliable local control/status path for the
owner's Chamberlain MYQ-G0401 without adding replacement hardware.

The cloud-emulator track is no longer the best first attack. Live testing proved that the G0401's outbound TCP/8883 connection negotiates TLS 1.2 with `TLS_PSK_WITH_AES_128_CBC_SHA`. A fake certificate, DNS redirect, or generic MQTT broker therefore cannot replace Chamberlain by itself. Recovering the per-device PSK may eventually be useful, but it should be treated as an opportunistic consequence of firmware/NVM acquisition rather than the project’s primary bet.

If activated, the fallback route works downward toward the physical RF
boundary:

```text
Broadlink / local API
        |
        v
  G0401 Wi-Fi MCU
        |
        |  <-- highest-value boundary to observe
        v
  RF/control subsystem
        |
        +------ RF command ------> garage-door opener
        |
        <------ RF telemetry ----- G0402 door sensor
```

The best possible result is to discover a local/internal command interface that lets us reuse the G0401's already-paired RF machinery. That would avoid both Chamberlain cloud authentication and reimplementation of the garage opener's rolling-code protocol.

## Facts already established on the owner's hardware

Do not redo these investigations unless a later experiment specifically needs confirmation:

- Device is positively identified as **Chamberlain MYQ-G0401**, firmware **1.10** (`GET /jabout`).
- Normal-LAN TCP 80 exposes setup/metadata pages and `/jabout`, but no local garage status/action endpoint has been found.
- Current-app BLE `CHUB` service is commissioning-oriented (`about`, `scan_results`, `config_save`) and exposes no model-specific `open`/`close` primitive in static analysis.
- The G0401 maintains an outbound TCP/8883 session.
- Live TLS handshake is TLS 1.2 PSK (`TLS_PSK_WITH_AES_128_CBC_SHA`), no SNI/ALPN; Chamberlain's real server successfully completes the PSK handshake.
- MQTT remains plausible but is not proven because application-data records have not been decrypted/classified.
- A historical related MyQ firmware dump contains a device-specific `myq_aes` NVM value and firmware routines that unwrap it. This proves that older related hardware stored useful per-device cryptographic material locally, but it does **not** prove that firmware 1.10 on the G0401 uses the same storage/layout.
- The official-app/Superbox path and the experimental direct-cloud tooling give us controlled ways to create known status/action events for correlation. Preserve those as experimental or fallback tools; do not let hardware research break the working baseline.

See `docs/LAN_RECON.md` for the evidence record.

## Public hardware facts that materially change the plan

### G0401 RF capability

The G0401 is itself a universal garage remote/gateway, not merely a Wi-Fi bridge. Chamberlain's compatibility material lists opener-control families/frequencies including 303, 310, 315, 318, 372.5, 390 MHz and several 433 MHz variants. The exact frequency/protocol used in this installation depends on the **actual ceiling-mounted garage-door opener**, which we have not yet positively identified.

Public FCC material for `HBW9545` includes internal photographs and RF test material. Use those photographs as a board-map reference before touching the owner's unit:

- FCC exhibits: https://fccid.io/HBW9545
- Chamberlain G0401 compatibility/specification material: https://www.chamberlain.com/smart-garage-control/p/MYQ-G0401-ESMC

### G0402 sensor

The G0402 door sensor (`HBW9546`) transmits in the ~312 MHz region. FCC grants list 311.885, 312.507 and 313.126 MHz; the test material identifies OOK modulation. This is likely the easiest passive RF protocol to characterize and gives us an independent status-recovery track.

- FCC exhibits: https://fcc.report/FCC-ID/HBW9546

### Wi-Fi/BLE module

The G0401 FCC filing identifies the Wi-Fi/BLE module as **Fn-Link 6220N-IS** (`2AATL-6220N-IS`), based on Realtek **RTL8720CS-VA1**. Its public module datasheet is unusually useful:

- 3.3 V module;
- pin 31: `UART_LOG_RXD`;
- pin 32: `UART_LOG_TXD`;
- pins 35/36: I2C SCL/SDA;
- pins 54/55: SWDIO/SWCLK;
- pins 63/64: communication UART RXD/TXD;
- module contains an 8 MiB SPI NOR flash (listed as GigaDevice GD25Q64CSIG, with an MXIC alternative on later module revision).

Datasheet: https://fcc.report/FCC-ID/2AATL-6220N-IS/4519624.pdf

The Realtek RTL872xCS family supports SWD and SPI-flash programming/debug facilities, but it also supports secure boot, debug-port protection/prohibition, secure eFuse, TrustZone and on-the-fly flash decryption. **Those are chipset capabilities, not proof Chamberlain enabled every protection.** The live tests must determine what this unit actually permits.

Realtek/AmebaD SDK reference: https://github.com/Ameba-AIoT/ameba-rtos-d

## Governing strategy

Attack in this order:

1. **identify the exact garage opener and preserve the working system;**
2. **passively observe RF and board signals;**
3. **map test pads to documented module pins;**
4. **listen to UART/internal buses without driving them;**
5. **try read-only debug/firmware acquisition;**
6. **only then consider boot straps, physical flash access, or command injection;**
7. **return to the PSK/cloud-emulator path only if firmware/NVM work makes it cheap.**

Do not spend hours trying to decrypt TLS from the wire, brute-force the PSK, replay unknown rolling-code RF, or fuzz arbitrary endpoints while easier evidence paths remain.

---

# Phase 0 — preserve baseline and identify the actual garage-door opener

This is mandatory before RF work because the G0401 supports multiple incompatible opener protocols.

### Record, without changing pairing

- G0401: model `MYQ-G0401`, firmware `1.10` (already known; simply confirm `/jabout` still answers if convenient).
- **Ceiling-mounted garage-door opener:** manufacturer, full model number, approximate manufacture date, Learn-button color and any FCC ID visible on the opener/receiver.
- Existing handheld remotes: model/FCC ID if easily visible.
- G0402 sensor model/FCC ID.
- Current G0401 LED/state and working MyQ/Superbox path.

Take local photographs of labels rather than transcribing uncertain characters. Keep serial numbers, MACs and other unique identifiers out of GitHub.

### Why the Learn-button/model matters

It narrows the expected carrier frequency and coding family, tells us whether a rolling-code scheme is expected, and makes the RF capture targeted rather than a blind sweep.

### Baseline gate

Before opening hardware, prove that a known read path still works. A hardware session must end with the same baseline unless a separately approved experiment intentionally interrupts it.

**Output:** sanitized opener model/protocol hypothesis and `BASELINE PASS/FAIL`.

---

# Phase 1 — passive RF characterization

No transmitting, replaying, pairing or desynchronization in this phase.

## 1A. Door-sensor RF

If an SDR/sub-GHz receiver is already available, capture the G0402 while changing physical door/sensor state once in each direction. Start around the FCC-listed 311.885/312.507/313.126 MHz frequencies and use bandwidth sufficient to see the whole signal.

Collect timestamped windows for:

1. idle;
2. closed/stable;
3. transition to open (manual/local movement is fine);
4. open/stable;
5. transition to closed.

Determine:

- exact observed carrier/frequency hopping behavior, if any;
- burst length and repetition count;
- symbol/bit timing;
- whether packets vary between repeats;
- which bits/fields correlate with open vs. closed;
- whether a counter/checksum appears to change.

Do **not** transmit captured sensor packets yet. The immediate goal is an independent local state decoder.

## 1B. Garage-control RF

After the ceiling-opener model identifies the likely band, record passively during **one** controlled official MyQ action while the door is physically/sensor observed. If a handheld remote exists, record one corresponding remote action separately for comparison.

Questions:

- What exact carrier does this installation use?
- Does the G0401 transmission resemble the handheld remote in timing/modulation?
- Is there a fixed preamble/sync structure?
- Do repeated activations produce changing payloads consistent with rolling code?
- Does the G0401 emit more than one RF protocol burst during a command?

Do not blind-replay a captured opener command. A rejected/accepted replay can desynchronize rolling-code state or create ambiguous physical behavior.

**High-value outcome:** classify the exact RF family used by the owner's opener. Full cryptographic decoding is *not* required yet.

---

# Phase 2 — physical board map, powered off first

Opening the G0401 is a separate physical step from opening/altering the ceiling opener. The target is the removable G0401 gateway only.

## 2A. Photograph before probing

With power disconnected:

- photograph both PCB sides at high resolution;
- photograph all module markings and board revision text;
- photograph every unpopulated header/test-pad cluster;
- compare against FCC `HBW9545` internal photos;
- identify the Fn-Link 6220N-IS module orientation and pin-1 reference;
- identify obvious RF sections/antenna feeds without guessing component roles.

Do not remove the module shield yet.

## 2B. Continuity map

Use a DMM in continuity/resistance mode, power disconnected. Map accessible test pads/header pins to the **module pins documented by Fn-Link**, prioritizing:

1. GND;
2. module pin 32 `UART_LOG_TXD` and pin 31 `UART_LOG_RXD`;
3. pins 63/64 communication UART;
4. pins 54/55 SWDIO/SWCLK;
5. pins 35/36 I2C;
6. GPIOs 40/41/49/61/62 only if they clearly route to test pads or another IC.

Record the mapping as local photos/notes and post only generic pad labels or board coordinates to GitHub.

### Stop conditions

- uncertain ground/reference;
- pads that appear tied directly to mains/high voltage (unlikely on this low-voltage hub, but verify);
- physical damage required merely to reach the pad;
- ambiguous module orientation.

**Goal:** convert the FCC/module pinout into a trustworthy test-pad map before any active probe touches the board.

---

# Phase 3 — passive internal signal capture (highest-value live phase)

This phase is intentionally **listen-only**. Do not connect a USB-TTL TX lead to the board. A logic analyzer/high-impedance scope input is preferred for discovery.

## 3A. Determine logic voltage

Power the G0401 normally and measure candidate signal idle levels relative to GND. The module itself is 3.3 V, but do not assume every neighboring subsystem is 3.3 V.

## 3B. Log UART

Listen to module pin 32 / mapped `UART_LOG_TXD` from power-on through normal operation. Realtek's AmebaD development platform commonly uses a 115200-bps log UART, so try 115200 first, then auto-detect/common rates only if it is not intelligible.

Capture separate windows for:

- cold boot;
- Wi-Fi association;
- idle;
- `GET /jabout`;
- MyQ app status refresh;
- one controlled cloud/app action if authorized.

Search logs for:

- firmware/build identifiers;
- partition/flash addresses;
- OTA host/path/version;
- broker/server identity;
- PSK/NVM record *names* (not secret values in Git);
- RF protocol selection;
- internal peripheral/UART task names;
- asserts/debug commands.

## 3C. Communication UART — potentially the jackpot

Passively sniff module pins 63/64 (`UART_RXD` / `UART_TXD`) simultaneously if they route off-module.

Correlate traffic with:

1. boot;
2. idle;
3. `/jabout`;
4. manual sensor transition;
5. official-app status refresh;
6. exactly one explicit garage action.

The most valuable possible finding is a small frame on this bus immediately before the G0401 transmits garage RF, e.g.:

```text
cloud/TLS event -> module UART frame -> RF subsystem -> opener moves
```

If that exists, we may be able to invoke the **already paired** RF subsystem locally and never need to implement the rolling-code algorithm.

For each candidate bus frame, note direction, timestamp, length and byte-level delta. Keep raw captures local until identifiers/secrets are understood.

## 3D. Other buses only when evidence points there

If the communication UART is silent, use board routing and logic activity to test likely I2C/SPI/GPIO boundaries. Do not clip onto the module's external flash bus while powered unless the electrical setup and analyzer loading are understood.

**Phase-3 success levels:**

- `B0`: no useful internal signal found;
- `B1`: boot/debug logs recovered;
- `B2`: inter-processor/peripheral command bus found;
- `B3`: garage action frame correlated reproducibly without transmitting it ourselves.

---

# Phase 4 — SWD, read-only first

Only after pin mapping and voltage confirmation.

The 6220N-IS exposes SWDIO/SWCLK, but RTL8720CS supports debug protection. The correct first question is simply: **is debug accessible?**

### Allowed first probe

- connect debugger with target voltage reference and common ground;
- attempt core/device identification;
- query debug state;
- if possible, halt/read a small known memory region without writing;
- record protection/error status.

### Hard stops

- **never** choose “unlock,” “recover,” “mass erase,” “erase before connect,” or equivalent;
- do not write option bytes/eFuse/security settings;
- do not disable secure boot;
- if the tool's only path to access is destructive, stop and report `SWD LOCKED/DESTRUCTIVE-ONLY`.

If read access works, acquire firmware conservatively, hash every acquisition, and compare repeated reads. Search offline before attempting any modification.

**Phase-4 outcomes:**

- `D0`: no electrical/debug response;
- `D1`: debug identifies chip but memory is protected;
- `D2`: read-only memory access works;
- `D3`: full relevant firmware/NVM acquisition succeeds reproducibly.

---

# Phase 5 — exact firmware/NVM acquisition and offline triage

This phase may be reached from SWD, OTA capture, ROM readback, or eventually physical flash acquisition. Prefer the least invasive source.

## Search an exact G0401/firmware-1.10 image for

### Cloud/credential material

- `connect.myqdevice.com` and other broker/API hostnames;
- TLS PSK identity construction;
- `myq_aes` or analogous NVM labels;
- NVM/PSM partition definitions;
- key-wrap/unwrapping routines;
- eFuse/secure-storage calls;
- MQTT strings/topics/client-ID code.

### Local/setup surfaces

- `/jabout`, `/jconfig_save`, `/jscan_results`, `/jconnect_serial` handlers;
- hidden diagnostic/test/manufacturing command tables;
- UART shell/CLI command names;
- OTA routes/version checks.

### RF/internal control

- UART/I2C/SPI driver initialization;
- frequency tables matching 303/310/315/318/372.5/390/433 MHz families;
- opener protocol names (`Security+`, `Intellicode`, `MegaCode`, `KeeLoq`, `SecureCode`, etc.);
- command-frame constructors;
- sensor packet parser;
- RF MCU/subsystem firmware blob or update mechanism.

### Security state

Determine whether the external 8 MiB flash contents are plaintext, partially encrypted, or entirely encrypted. High entropy alone is not sufficient to label everything encrypted; identify boot headers/partition metadata first.

The historical `MyQ-ESP-transplant` image is a **reference for concepts and tooling only**. Never assume its fixed unwrap material, offsets, or per-device key applies to the G0401 until the exact current image demonstrates the same design.

---

# Phase 6 — external SPI flash acquisition (later, not first)

The public 6220N-IS datasheet lists an 8 MiB SPI NOR inside the module shield. Physical acquisition is valuable because it may yield exact firmware even when SWD is locked, but it is more invasive and may return encrypted bytes if Realtek flash encryption is enabled.

Order of preference:

1. software/SWD read;
2. safe in-circuit flash read with G0401 unpowered, after verifying that other circuitry will not contend/back-power;
3. isolate chip/select or module as needed;
4. desolder/read only as a later forensic step with explicit approval.

Rules:

- never write to the original flash;
- take at least two independent reads and require identical hashes;
- save a pristine full-image backup before analysis;
- do not power the G0401 and external programmer simultaneously;
- verify normal boot after reassembly.

If the dump is encrypted, that is still useful: compare unencrypted regions, boot headers and OTA image format, and correlate with Realtek secure-boot/flash-decryption behavior. Do not immediately jump to fault injection.

---

# Phase 7 — Realtek ROM/UART download mode (only after mapping/backups)

RTL8720CS documentation exposes a UART-download boot strap at the chip family level. This can be useful if it offers non-destructive readback, but changing boot straps is a materially different risk level from listening to UART.

Only attempt after:

- board/module pin mapping is trustworthy;
- current firmware/NVM has been backed up by another route if possible;
- exact boot strap and voltage are confirmed from documentation;
- normal recovery/boot procedure is known;
- user explicitly approves entering the alternate boot mode.

Goal: determine whether the ROM monitor identifies the chip and permits **readback**. If available tooling insists on erase/write/flash as its first operation, stop. We do not need custom firmware merely to prove a read path.

---

# Phase 8 — OTA as a firmware-acquisition route

This remains worth pursuing in parallel because it can beat physical extraction.

Use existing log/DNS/network tooling to identify natural firmware-update checks. Prefer observing a normal check rather than forcing an update/downgrade.

Recover, if visible:

- update hostname/path;
- current/target version metadata;
- package/image format;
- signature/encryption metadata;
- partition/image names.

If a current firmware package can be captured legitimately, analyze it offline before any attempt to install or modify it. Never force an older image onto the live G0401 simply to simplify reverse engineering.

---

# Phase 9 — turn observations into local control

Only move from observation to injection once the command boundary is understood and a single operation can be bounded safely.

## Preferred path A: internal command bus

If phase 3 identifies a command frame sent from the network MCU to an RF/control subsystem:

1. understand frame boundaries/checksum and explicit vs. toggle semantics;
2. test a non-mutating/read/status command first if one exists;
3. confirm current door state via G0402/MyQ sensor;
4. physically ensure the path is clear;
5. inject **exactly one explicit `close` or `open`** frame, preferring `close` if the door is open;
6. verify movement once and final state;
7. do not retry after an ambiguous result.

Then implement a small local service that talks to this boundary and exposes the existing stable API:

```text
GET  /garage/status
POST /garage/open
POST /garage/close
```

## Preferred path B: reuse recovered firmware function

If firmware analysis reveals a local/test/manufacturing command that invokes the normal RF routine, use that rather than inventing RF packets. Validate read-only commands first and retain action-specific confirmation guards.

## Path C: implement a new paired RF remote

Only if the internal boundary cannot be reused and the actual opener protocol is understood well enough.

Prefer **pairing our implementation as a new legitimate remote using the opener's Learn process** over cloning/copying the rolling state of an existing remote. Do not replay rolling-code captures blindly.

This route may ultimately require an external radio to become a permanent implementation, which is outside the preferred “reuse the G0401 hardware” goal. It is still useful as protocol proof and as a comparison target.

---

# Phase 10 — PSK/cloud emulation remains blocked

The direct-device emulator question remains blocked. It can be reconsidered
only if exact current firmware/NVM work cheaply yields:

- the per-device TLS PSK or its recoverable wrapped representation;
- the PSK identity;
- enough application-protocol detail to classify/decrypt the 8883 session.

At that point the previous transparent-relay capture becomes valuable again and MQTT can be confirmed/rejected from decrypted application data. Until
then this is a bounded #9 software research lane, not an execution priority
in this archive.

Do **not**:

- brute-force the PSK;
- assume the historical public MyQ key is the owner's key;
- pursue a zero-day before exhausting documented debug/flash/OTA/internal-bus paths;
- disable security fuses merely to make emulation easier.

---

# Dormant fallback sequence (only after activation)

This list is not an instruction for the current agent. If the explicit
software-exhaustion gate is approved later, a hands-on agent can use this order:

1. identify the ceiling-opener model/Learn-button color and record baseline;
2. inspect public FCC/module pinout and photograph the owner's G0401 board;
3. passive RF capture of G0402 + one G0401/handheld opener command if receiver equipment is available;
4. power-off continuity-map test pads to 6220N-IS log UART, communication UART and SWD;
5. passive boot/log-UART capture;
6. passive communication-UART capture correlated with one known action;
7. if UART reveals the internal RF command boundary, prioritize decoding it immediately;
8. otherwise try non-destructive SWD identification/read;
9. pursue natural OTA firmware capture in parallel;
10. only if still blocked, plan external SPI-flash acquisition;
11. only after backup/mapping, consider ROM UART/download mode;
12. only after a command primitive is understood, run one bounded local-command test;
13. revisit the PSK/cloud emulator only if firmware acquisition makes credential recovery straightforward.

This order deliberately front-loads tests that are cheap, reversible and likely to reveal the architecture.

# What the local agent should have ready

If this archive is activated, use what is already available before buying
anything. Equipment is listed from least to most invasive:

- phone/camera with macro capability;
- DMM with continuity mode;
- logic analyzer capable of 3.3 V digital capture;
- 3.3 V USB-TTL adapter (**RX-only initially**);
- SWD debugger compatible with Cortex-M targets;
- SDR/sub-GHz receiver covering the actual opener/sensor bands;
- SOIC-8 flash clip/programmer only for the later flash phase.

If a tool is unavailable, report it and continue another track; lack of an SDR must not block UART/SWD work, and lack of a debugger must not block RF/log-UART work.

# Evidence and secret handling

Keep these **local/ignored**:

- full MAC/serial/device IDs;
- raw firmware/NVM dumps;
- PSKs or decrypted per-device keys;
- raw RF captures until identifiers/counters are understood;
- detailed board photos if they contain unique labels;
- raw UART logs if they contain credentials/tokens.

Commit sanitized facts, parsers and interoperability code only.

# Stop rules

Stop the specific experiment (not the whole research session) if it would require:

- mass erase/debug unlock;
- eFuse/security-bit modification;
- firmware flashing merely to inspect the device;
- blind RF replay against an unknown rolling-code system;
- destructive desoldering before non-invasive acquisition paths are exhausted;
- repeated garage-door cycling;
- a command when physical/sensor state is unknown.

When blocked, move to the next independent track.

# Progress levels / required handoff

Use this compact report so the next agent knows exactly where to resume:

```text
WORKING BASELINE: PASS/FAIL
CEILING OPENER: <sanitized model>; learn button <color>; RF family <known/hypothesis>

RF SENSOR:
- level: R0 none / R1 carrier+timing / R2 state fields decoded
- observed frequency/modulation: <sanitized>

RF OPENER CONTROL:
- level: T0 none / T1 carrier+timing / T2 protocol family / T3 command implementation
- G0401 vs handheld comparison: <result>

BOARD:
- revision matched FCC photos: yes/no/unknown
- 6220N-IS confirmed: yes/no
- mapped pads: log UART / comm UART / SWD / other

INTERNAL BUS:
- level: B0 none / B1 logs / B2 command bus / B3 action frame correlated / B4 local injection proven
- protocol/baud: <result>

DEBUG/FIRMWARE:
- SWD: D0 none / D1 identified+protected / D2 read access / D3 firmware acquired
- exact G0401 FW 1.10 image: yes/no
- flash: plaintext / partial / encrypted / unknown
- OTA lead: yes/no

LOCAL CONTROL:
- status without cloud: yes/no
- explicit command without cloud: yes/no
- success level: L0/L1/L2/L3

PSK/8883:
- current PSK recovered: yes/no
- application protocol: MQTT confirmed / other / encrypted unknown
- cloud emulator remains: blocked / newly actionable

COMMITS: <sha(s) or none>
NEXT HIGHEST-VALUE TEST: <one sentence>
BLOCKERS/TOOLS NEEDED: <short list>
```

The agent should update the appropriate issue after each meaningful level change rather than waiting for a perfect end-to-end result.
