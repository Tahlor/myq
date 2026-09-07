# Track B2 — true local/LAN control

## Goal

Determine whether the existing myQ Wi-Fi opener can be controlled by software on the home LAN **without** using the myQ cloud and without adding hardware to the opener.

This is a protocol-recovery problem, not an assumption that a friendly HTTP API already exists.

## Highest-value direct-device lead: setup/pairing web service

MyQ's supported Wi-Fi setup flow proves that at least some openers expose a temporary local Wi-Fi AP such as `myQ-XXX` and serve a setup site at `setup.myqdevice.com` while the phone/laptop is directly connected to the opener. That makes the provisioning service our first direct-device reverse-engineering target before attempting complicated TLS interception.

Relevant setup documentation/examples:

- Chamberlain/LiftMaster manuals instruct the user to enter Wi-Fi learn mode, connect to the network with the `MyQ-` prefix, and browse to `setup.myqdevice.com`.
- Current third-party installation instructions still describe the same setup path.

The important unknown is whether this local service is only a Wi-Fi provisioning UI or whether its HTML/JavaScript/API exposes useful device metadata, state, or command primitives. A second key question is whether the same service/endpoints remain reachable at the opener's normal home-LAN IP after provisioning.

**Do not enter setup mode casually.** It can interrupt normal MyQ connectivity and some flows offer destructive actions such as erasing Wi-Fi configuration. Preserve the current working state and a normal reprovisioning path first.

See issue #5 for the executable workflow. The sequence is intentionally:

1. establish a reliable production Broadlink path first (or run this in parallel with another agent);
2. enter normal supported setup mode;
3. connect a disposable client to `myQ-*`;
4. resolve/capture `setup.myqdevice.com`;
5. fetch only the shipped HTML/JS/assets and let those reveal endpoints;
6. observe non-mutating UI requests such as Wi-Fi scan/device info;
7. return the opener to home Wi-Fi;
8. test the **exact discovered endpoints** against its confirmed normal LAN IP;
9. only test a garage command if the shipped service explicitly reveals such a primitive and the door is physically observed.

If the setup service exposes status on the normal LAN, that is Level 1 immediately. If it exposes explicit open/close commands on the normal LAN, that is Level 2 and should be wrapped behind the project's stable `/garage/status`, `/garage/open`, `/garage/close` contract.

## Known network lead: TCP 8883

Current Chamberlain support documentation explicitly says **myQ devices use TCP port 8883 to communicate with myQ servers** and may appear offline when that port is blocked:

- https://support.chamberlaingroup.com/s/article/Recommended-router-settings-for-the-MyQ-Wi-Fi-products-1484145723404
- https://support.chamberlaingroup.com/s/article/When-to-Contact-Your-Internet-Service-Provider-ISP

TCP 8883 is conventionally MQTT over TLS, so outbound 8883 traffic is our highest-priority cloud-protocol capture target. Do **not** treat the port number alone as proof that a given connection speaks MQTT; confirm from current live traffic and/or firmware/app evidence.

This also makes a useful identification experiment: once the opener IP is confirmed, an outbound connection from that host to TCP 8883 is strong supporting evidence that we have the right device. Blocking it is not required for discovery and should not be the first test.

## Phase B2.1 — identify the opener

The Chamberlain Group currently has several IEEE OUI registrations commonly associated with its network devices. `tools/lan_probe.py` flags these as candidates:

```text
0C:95:05
44:11:46
64:52:99
CC:6A:10
00:15:25  (legacy Chamberlain Access Solutions)
```

Run from a machine on the same LAN:

```powershell
python tools\lan_probe.py --subnet 192.168.187.0/24
```

The script probes the subnet to populate the neighbor cache, reads ARP, marks Chamberlain-prefix MACs, resolves hostnames when possible and probes common HTTP/MQTT/TLS ports. **ARP-observed devices are retained even when they ignore ICMP ping**, because IoT devices are often ping-silent.

Reverse-DNS lookups are bounded so stale neighbors cannot hold the scan open indefinitely. Adjust the per-address limit with `--reverse-dns-timeout` when diagnosing a resolver-specific problem.

## Local read-only evidence — 2026-09-04

The current host was scanned on the private `192.168.187.0/24` LAN. The probe saw 41 neighbors and no MACs matching the OUI list above. One neighbor had a local hostname matching the owner's `MyQ-*` naming convention, making it a **probable** opener but not a confirmed identification.

Targeted read-only checks against that probable device found:

- TCP 80 open; TCP 443, 1883, 8080, 8443 and 8883 closed or unreachable;
- `GET /` returned `200` with a `Wi-Fi Setup` page;
- `GET /start.html` returned `404`;
- `GET /config.html`, `/config_hub.html`, and `/connect_hub.html` returned `200`;
- `HEAD /` and `OPTIONS /` returned `404`;
- the setup JavaScript referenced `/jconfig_save`, `/jscan_results`, and `/jconnect_serial`; no mutating endpoint was called;
- `GET /jscan_results` returned `404`.

This proves a local HTTP setup surface exists on the probable device, but not local door status or control. The device identity still needs confirmation from the router/AP client list, a normal supported Wi-Fi disconnect/reconnect observation, or scoped outbound capture. The exact IP, MAC and raw responses remain in ignored local captures only.

## Follow-up read-only check — 2026-09-05

A fresh scan saw the same `MyQ-*` hostname among the LAN neighbors. The targeted port result was unchanged: TCP 80 was open and TCP 443, 1883, 8080, 8443 and 8883 were not reachable. `GET /`, `/config.html`, `/config_hub.html` and `/connect_hub.html` again returned `200`; the setup pages again exposed only the previously recorded route names. The OUI did not match the current Chamberlain list, and no opener disconnect/reconnect or packet capture was performed, so the device remains a probable rather than positively identified opener.

## Setup-resource mapping — 2026-09-05

The confirmed candidate's read-only setup pages and their static assets were fetched again and retained only in ignored `captures/lan/` artifacts. The HTML and JavaScript advertise these additional setup-flow routes:

- `/jstart`, `/jexit`, and `/jlang_set?lang=...` for setup-page navigation and language selection;
- `/jscan_results` for Wi-Fi scan results;
- `/jconnect_serial` for the hub/serial-registration page;
- `/jconfig_save...` for saving Wi-Fi configuration.

The browser helper sends these as asynchronous `GET` requests, but none of the routes was invoked during this probe. They are setup/configuration surfaces, not evidence of a local door-status or door-control API. The candidate therefore remains **L0 (cloud-only)** for the control objective, with no safe local command endpoint identified.

## Router lease confirmation — 2026-09-05

A read-only SSH query through the existing Pi3-to-router path found the same `MyQ-D5F` hostname and matching MAC prefix in the router's DHCP lease table for the candidate already observed locally. The device's port-80 `connect_hub.html` page also exposes myQ-branded hub and serial-registration fields. This confirms a current MyQ network device and gives high confidence that it is the owner's opener/hub, while the exact opener role still lacks a normal Wi-Fi disconnect/reconnect or outbound-traffic correlation. Exact IP/MAC values remain only in ignored captures.

No local status or command endpoint was found; the true-LAN track remains success level **L0 (cloud-only)** pending an approved outbound capture point.

## Router conntrack observation — 2026-09-05

The router has no `tcpdump` or `tshark`, but it does include `/usr/sbin/conntrack` outside the default `PATH`. A read-only `conntrack -L` query and the `/proc/net/nf_conntrack` table both showed the confirmed MyQ candidate maintaining an `ESTABLISHED` TCP session to a public AWS endpoint on destination port `8883`; the filtered query currently reports one matching entry. This upgrades the outbound-port result from a port hypothesis to live connection evidence. There was no packet payload, TLS SNI, or MQTT framing available from conntrack, so the protocol classification remains **8883-only; MQTT unconfirmed**. No traffic was redirected or mutated.

The observation is repeatable with `scripts/capture_router_conntrack.ps1`. It uses the existing Pi3-to-router SSH path, writes raw metadata only to ignored `captures/lan/`, and emits a sanitized entry count. It does not install a package or change router, opener, DNS, firewall, or forwarding state:

```powershell
.\scripts\capture_router_conntrack.ps1 -CandidateIp <candidate-ip>
```

**Important:** no listening TCP ports does not rule out a myQ device. An opener can operate as an outbound-only TLS/MQTT client.

## Current live recon — 2026-09-06

The Windows host's active Ethernet interface is on the private `192.168.187.0/24` network with the expected private gateway. A fresh read-only sweep observed 25 neighbors and no known Chamberlain OUI matches; the prior `MyQ-*` candidate was not present in the fresh DNS/ARP result. Targeted checks against that prior candidate found no response on TCP 80, 443, 1883, 8080, 8443, or 8883, and the previously observed setup-page GETs were unavailable during this run.

The router-side read-only conntrack check still reported one matching TCP/8883 entry for the prior candidate. This confirms current outbound-port evidence but still provides no payload, TLS SNI, or MQTT framing. No local listener was identified, and no network, opener, DNS, firewall, or forwarding state was changed.

## Current model confirmation and BLE boundary — 2026-09-07

A read-only `GET /jabout` against the already correlated normal-LAN candidate returned `200` and identified the device at model level as:

- manufacturer: Chamberlain Group;
- brand: Chamberlain;
- product: `SMART GARAGE CONTROL,GEN3,BLE,CH`;
- model: `MYQ-G0401`;
- firmware: `1.10`;
- Internet connection: reported as connected.

The raw response contains serial, MAC and network identifiers, which remain only in ignored local captures. No Wi-Fi/configuration endpoint and no garage action was called. This is now positive model/firmware evidence for the current device, not just a hostname/OUI inference.

The exact current Android APK independently maps the `CHUB` peripheral to the following BLE surface:

| BLE element | UUID | Observed role |
| --- | --- | --- |
| service | `26d91a37-c279-4d0f-96a1-532ce41ce0f6` | Smart Garage Control commissioning service |
| write characteristic | `2c9aeec6-05fc-4204-974c-49541cce2b42` | NUL-terminated setup commands/responses |
| notify characteristic | `ad9dd28e-6bc9-42cd-a5c7-d8717d8a0c96` | setup status and notifications |
| device-information service | `0000180a-0000-1000-8000-00805f9b34fb` | standard metadata reads |

For this `CHUB` implementation, the app sends `about\0` and `scan_results\0`, reads standard device-information characteristics, and constructs `config_save?...` for Wi-Fi provisioning. The latter is a credential/configuration mutation and was not used. The code contains no normal open/close/toggle command on this model-specific BLE path; the separate encrypted BLE command code belongs to the app's Lockitron smart-lock peripheral.

A temporary unfiltered, read-only BLE advertisement scan on the SuperBOX ran for 20 seconds and saw unrelated nearby devices but no MyQ name and no `CHUB` service advertisement. The scanner was removed afterward. This means the current opener is not advertising the commissioning service in its present normal state; entering a supported provisioning state would be required to inspect it over BLE, and that would interrupt the currently working setup. No pairing, GATT connection, characteristic write, or physical setup-mode transition was performed.

The direct-device track therefore remains **L0 for local control**: the normal-LAN port-80 surface is setup/metadata only, and the model-specific BLE surface proven from the current APK is commissioning/metadata only. The live outbound TCP/8883 session is the highest-value path for recovering device-side command transport, but its application payload remains encrypted and unobserved. A short router/AP or managed-switch passive capture is still useful for proving the opener's DNS resolution; the controlled server result below means a certificate-only redirect is no longer a promising next step.

## Live TLS/PSK boundary — 2026-09-07

A short series of reversible router redirects was used only after the candidate device, gateway and existing 8883 flow were confirmed. The rules matched the candidate source address and TCP destination port `8883`, forwarded to a temporary listener on the Pi3, and were removed after each run. No Wi-Fi/configuration endpoint, TLS application record, MQTT command, or garage action was sent. The final run used the current endpoint lead `connect.myqdevice.com` as the relay's explicit upstream; because the router performs the rewrite before Pi3 sees the connection, the relay did not infer a hostname from `SO_ORIGINAL_DST`.

The opener's live handshake is now characterized:

- ClientHello: TLS 1.2 (`3.3`), record version `3.1`, no SNI, no ALPN;
- offered cipher suites: `0x008c` and `0x00ff`;
- IANA identifies `0x008c` as `TLS_PSK_WITH_AES_128_CBC_SHA`; `0x00ff` is the TLS renegotiation signaling value;
- the real server selected `0x008c`, sent `ServerHello` and `ServerHelloDone`, and accepted the client's PSK handshake;
- the client's 16-byte ClientKeyExchange record is consistent with a 10-byte PSK identity plus the TLS handshake header and length field; the identity itself was not logged;
- both sides completed change-cipher-spec/Finished, and the server sent a NewSessionTicket;
- the relay terminated at the handshake boundary and blocked TLS content type `23` (application data), so MQTT framing and any device command were not observed or forwarded.

This is decisive for the emulator decision. The opener is not waiting for a normal CA-signed certificate that a local server could simply replace. It authenticates the 8883 peer with a pre-shared key and uses a device-side identity; a usable local replacement would need the per-device PSK and the encrypted application protocol (likely MQTT, but MQTT remains unconfirmed until an application record is safely captured). A fake certificate, DNS spoof alone, or a generic local MQTT broker is insufficient. The next software-only work item is therefore credential/protocol recovery from supported provisioning or firmware evidence; do not brute-force the PSK or enter setup/reset mode merely to obtain it.

The reusable `tools/tls_transparent_probe.py` implements this safety boundary: it relays TLS handshake records for observation but never forwards application-data records. Raw relay output and network identifiers remain ignored local artifacts.

## Superbox capture-tool check — 2026-09-05

The rooted Superbox was checked as a possible short-term observation point. Its system `toybox` is present, but the image exposes no `tcpdump`, `tshark`, or `netcat` command. No capture binary was installed and no interception or traffic mutation was attempted. A router/AP capture, managed-switch mirror, or another already-approved observation point is still needed to classify the opener's outbound protocol.

After a likely candidate is found, confirm it by temporarily disconnecting/reconnecting the opener from Wi-Fi or comparing the router's device list. Do not identify a device solely from a guessed hostname.

## Phase B2.2 — read-only local enumeration

For the confirmed opener IP:

1. targeted port scan (TCP and, if useful, UDP);
2. mDNS / SSDP observation;
3. TLS certificate/banner capture for any local TLS listener;
4. attempt only non-mutating HTTP GET/OPTIONS requests against discovered services;
5. record MAC, IP, firmware/model information only in ignored local capture files unless a sanitized model-level fact is useful to the project.

If a stable local service appears, map it before doing any traffic interception.

If issue #5 has already revealed setup-mode endpoints, test those exact paths/ports against the normal LAN IP before broad scanning. Preserve the `Host: setup.myqdevice.com` header if the setup UI used host-based routing.

## Phase B2.3 — observe outbound cloud traffic

If the opener has no useful listener, capture its outbound traffic. A switched LAN normally prevents another ordinary host from passively seeing unicast traffic, so choose one of these evidence paths:

### Preferred

- router/AP packet capture scoped to the opener IP/MAC;
- managed-switch port mirror;
- router DNS query log scoped to the opener.

These avoid perturbing traffic.

### Controlled interception fallback

The rooted Superbox can potentially be used as an authorized inline/ARP interception host, but do this only after the opener IP and default gateway are confirmed and with IP forwarding/rollback scripted. A failed MITM can temporarily disconnect the garage from the cloud.

The first capture should be short and read-only:

1. opener idle baseline;
2. app refresh/status read;
3. one manually initiated **close** or other safe known-state operation while the garage is observed;
4. correlate timestamps.

Capture at minimum:

- DNS queries/answers;
- destination IP/port, with special attention to TCP 8883;
- TLS SNI/ALPN/certificate metadata;
- connection timing/reconnect behavior;
- MQTT CONNECT metadata only if visible outside TLS.

Do not expect encrypted MQTT payloads to be visible merely because port 8883 is identified.

## Phase B2.4 — redirectability tests

Once the real cloud destinations and protocol are known, test progressively:

1. Does the opener honor DHCP-provided DNS normally?
2. Does it resolve a stable broker hostname?
3. Does it validate the server certificate chain?
4. Does it pin a specific certificate/public key?
5. Does it use a device client certificate or per-device credential for MQTT/TLS?
6. Are MQTT topic names/credentials discoverable from firmware/app/cloud bootstrap traffic?

A local replacement is easiest if the opener trusts normal public CA validation and uses a hostname we can redirect to a locally trusted endpoint. It is harder if firmware pins Chamberlain certificates or uses mutual TLS with device-bound credentials.

## Success levels

### Level 0 — no local surface

Only cloud integration works. Keep Track A/B1.

### Level 1 — local status

We can read door state locally but commands still require cloud. Useful for automation reliability and reducing polling.

### Level 2 — local commands through existing protocol

We can open/close/status directly over LAN using the opener's existing network stack. This is the desired software-only outcome.

### Level 3 — local broker/service replacement

The opener can be redirected from Chamberlain to our own local MQTT/API service and behaves normally. At that point the garage can remain functional even if myQ cloud access changes again.

## What not to do yet

- Do not flash opener firmware.
- Do not desolder/debug the opener board.
- Do not buy/install a ratgdo as a workaround; that defeats this project's stated objective.
- Do not spend time brute-forcing arbitrary LAN ports if live traffic immediately proves the device is outbound-only.
- Do not erase Wi-Fi settings merely to inspect the setup UI; capture read-only setup behavior first.
