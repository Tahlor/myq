# G0401 LAN and protocol evidence

This is evidence and a software-first research handoff, not an active hardware
plan. The current objective is to learn whether the existing G0401 offers a
read-only or command-capable local surface without changing pairing or device
state.

## Current confirmed model

A read-only GET /jabout against the correlated normal-LAN candidate on
2026-09-07 returned model-level identity:

- manufacturer: Chamberlain Group;
- brand: Chamberlain;
- product: SMART GARAGE CONTROL,GEN3,BLE,CH;
- model: MYQ-G0401;
- firmware: 1.10;
- Internet connection: connected.

The response contains serial, MAC, and network identifiers; they remain only
in ignored local captures. No configuration endpoint or garage action was
called for this identification.

## Normal-LAN TCP/80 service

The candidate has a normal-LAN TCP/80 HTTP service. Read-only checks on
2026-09-04/05 found:

- GET / returned the Wi-Fi Setup page;
- GET /config.html, /config_hub.html, and /connect_hub.html returned 200;
- GET /start.html and GET /jscan_results returned 404;
- the page assets named /jstart, /jexit, /jlang_set, /jscan_results,
  /jconnect_serial, and /jconfig_save;
- no local door state or open/close endpoint was found;
- related historical /sys/diag/info, /sys/connection, /sys/services,
/sys/prov_status, /sys/interface, /sys, and /sys/firmware checks returned
  404.

The setup JavaScript is useful route evidence but not proof that a route is
safe or live. jconfig_save and jconnect_serial are provisioning/configuration
mutations and are not called. No Wi-Fi configuration was submitted.

The next #9 implementation item is a bounded route-archaeology helper for
HEAD/GET against this evidence-backed dictionary. It must record only status,
content type, length, redirect/server metadata, and sanitized strings; it must
not fuzz, submit forms, or call a route merely because a word such as save or
connect appears in a script. Until that helper exists, retain route output in
ignored local captures and use only the existing GET-only setup capture tool.

## BLE boundary

The exact installed official Android APK maps the model-specific CHUB
commissioning service as follows:

| BLE element | UUID | Observed role |
| --- | --- | --- |
| service | 26d91a37-c279-4d0f-96a1-532ce41ce0f6 | Smart Garage Control commissioning |
| write characteristic | 2c9aeec6-05fc-4204-974c-49541cce2b42 | NUL-terminated setup commands |
| notify characteristic | ad9dd28e-6bc9-42cd-a5c7-d8717d8a0c96 | setup status/notifications |
| device-information service | 0000180a-0000-1000-8000-00805f9b34fb | standard metadata reads |

The app sends about and scan_results, reads device-information values, and
constructs config_save for Wi-Fi provisioning. The current code contains no
normal model-specific BLE open/close/toggle command. Separate encrypted BLE
command code belongs to a Lockitron smart-lock peripheral.

A 20-second read-only advertisement scan on the Superbox saw no CHUB
advertisement in the normal device state. Entering a supported provisioning
state would interrupt the working setup and is outside the current software
runbook. No GATT connection, characteristic write, pairing, or setup-mode
transition was performed.

Conclusion: normal-LAN and normal-state BLE evidence remains L0 for local
control. No proven local status or command primitive exists.

## Outbound TCP/8883 and TLS boundary

Router conntrack repeatedly showed an established outbound TCP/8883 session
from the candidate to a public AWS endpoint. Conntrack provided no payload,
TLS SNI, or MQTT framing. The Superbox image has no tcpdump, tshark, or netcat,
so no capture binary was installed.

A bounded, reversible redirect/relay observation on 2026-09-07 recorded:

- TLS 1.2 ClientHello, record version 3.1;
- no SNI and no ALPN;
- offered cipher suites 0x008c and 0x00ff;
- 0x008c is TLS_PSK_WITH_AES_128_CBC_SHA;
- 0x00ff is the TLS renegotiation signaling value;
- the real server selected 0x008c and completed the PSK handshake;
- the device-side PSK identity length was observable, but the identity and
  secret were not logged;
- application-data records were blocked by the transparent probe.

This proves a local replacement would need the current per-device PSK and
encrypted application protocol. TCP/8883 does not prove MQTT. A fake
certificate, DNS-only redirect, or generic MQTT listener is insufficient.
The direct-device emulator question is therefore blocked pending PSK/protocol
evidence and remains only a bounded #9 software research lane.

The safe observation tools are:

    python tools/tls_clienthello_listener.py --bind 0.0.0.0 --port 8883
    python tools/tls_transparent_probe.py --bind 0.0.0.0 --port 8883 --upstream-host connect.myqdevice.com --upstream-port 8883 --once

Use them only for a confirmed device and a temporary, reversible observation
rule. They do not terminate an authenticated session or forward application
commands.

## Historical NVM and firmware lead

The public fuxxociety/MyQ-ESP-transplant research contains related historical
88MW30x firmware and public MCU communication notes. It is not the owner's
G0401 firmware 1.10. Its PSM data contains a 16-byte per-device myq_aes
record. Historical firmware unwraps that record with a 32-round,
little-endian TEA variant and a fixed public 16-byte code literal.

tools/myq_firmware_psm.py reproduces the historical unwrap in memory and emits
only record metadata and hashes. The historical key, raw dump, and any
current-device secret stay out of Git. The result is a lead for current-image
analysis, not a derivation or credential guess for the G0401.

## Current live limits and next software work

The candidate's OUI was not sufficient for identification, but /jabout and
router correlation now provide positive model/firmware evidence. The current
software-only gaps are:

1. enumerate the exact official APK's exported/internal action surfaces;
2. finish the read-only route dictionary against the current normal-LAN
   candidate when it is available;
3. passively inventory all natural DNS/endpoint/OTA traffic;
4. classify current PSK provisioning as factory/random, derived, or
   server-provisioned;
5. compare an exact/current firmware image if a software-accessible package is
   found.

No reset, re-pair, firmware update, broad URI scan, RF action, or hardware
probe is justified by this document. Keep the official-app bridge available
for any future authorized state/action correlation.
