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

**Important:** no listening TCP ports does not rule out a myQ device. An opener can operate as an outbound-only TLS/MQTT client.

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
