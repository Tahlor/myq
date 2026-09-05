# Track B2 — true local/LAN control

## Goal

Determine whether the existing myQ Wi-Fi opener can be controlled by software on the home LAN **without** using the myQ cloud and without adding hardware to the opener.

This is a protocol-recovery problem, not an assumption that a friendly HTTP API already exists.

## Known network lead: TCP 8883

Current Chamberlain support documentation explicitly says **myQ devices use TCP port 8883 to communicate with myQ servers** and may appear offline when that port is blocked:

- https://support.chamberlaingroup.com/s/article/Recommended-router-settings-for-the-MyQ-Wi-Fi-products-1484145723404
- https://support.chamberlaingroup.com/s/article/When-to-Contact-Your-Internet-Service-Provider-ISP

TCP 8883 is conventionally MQTT over TLS, so outbound 8883 traffic is our highest-priority capture target. Do **not** treat the port number alone as proof that a given connection speaks MQTT; confirm from current live traffic and/or firmware/app evidence.

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

The router has no `tcpdump`, `tshark`, or `conntrack` executable, but its read-only `/proc/net/nf_conntrack` table showed the confirmed MyQ candidate maintaining an `ESTABLISHED` TCP session to a public AWS endpoint on destination port `8883`. This upgrades the outbound-port result from a port hypothesis to live connection evidence. There was no packet payload, TLS SNI, or MQTT framing available from conntrack, so the protocol classification remains **8883-only; MQTT unconfirmed**. No traffic was redirected or mutated.

**Important:** no listening TCP ports does not rule out a myQ device. An opener can operate as an outbound-only TLS/MQTT client.

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
