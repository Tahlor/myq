# Live MyQ runbook

This is the shortest hands-on sequence for the local agent. The objective is to keep a working 2026 control path while recovering an opener-local protocol.

## 0. Working baseline first: official app bridge

Follow issue #1 and `docs/APP_BRIDGE.md` until all are true:

- official MyQ app is authenticated on the Superbox;
- the real garage is visible;
- native bridge `/status` matches the physical door;
- Broadlink can reach the bridge;
- one already-satisfied explicit command is a no-op;
- one physically observed explicit transition succeeds.

Do not enable experimental direct-cloud mode in Broadlink.

If login/MFA needs user interaction, leave the app at that prompt and continue the read-only LAN/APK work below rather than blocking the whole session.

## 1. Identify the opener on the normal LAN

From a host on the home LAN:

```bash
python tools/lan_probe.py --subnet 192.168.187.0/24
```

Positive identification needs more than ping/hostname. Use MAC/OUI plus router association and, if needed, a controlled opener Wi-Fi reconnect.

Record locally:

```text
opener IP
opener MAC
model/firmware if known
local listening ports
```

Keep raw identifiers out of GitHub issue comments.

Do not attempt DNS redirection until the opener is positively identified and its normal cloud hostname has been observed.

## 2. Mine the exact installed official APK

On the authorized Superbox:

```powershell
$serial = .\scripts\connect_superbox.ps1
$dir = .\scripts\pull_myq_apks.ps1 -AdbSerial $serial
.\scripts\decompile_myq.ps1 -ApkDirectory $dir
```

Then run:

```bash
python tools/summarize_jadx.py <jadx-output>
```

Read `myq-static-summary.json` in this order:

1. `setup_portal`
2. `local_network`
3. `mqtt`
4. `iot_cloud`
5. `tls_cert`
6. `wifi` / `ble`

Highest-value facts to extract:

- `setup.myqdevice.com` or other setup hostnames;
- literal local API paths;
- broker/cloud hostnames;
- 8883/MQTT client library evidence;
- certificate pinning/trust-manager code;
- client certificate/keystore references;
- BLE/Wi-Fi commissioning protocol clues.

Only post sanitized protocol facts; keep the raw decompile output local/ignored.

## 3. Inspect the opener's supported setup portal

Do not factory reset. Enter only the normal documented Wi-Fi learn/setup mode after preserving a reprovision path.

When `myQ-*` appears, connect a disposable laptop/client and record its gateway/DNS configuration.

First try:

```bash
python tools/setup_portal_capture.py http://setup.myqdevice.com/
```

If DNS fails but the setup gateway IP is known:

```bash
python tools/setup_portal_capture.py http://<SETUP-GATEWAY-IP>/ --host-header setup.myqdevice.com
```

The tool performs GET requests only. It saves root HTML plus same-origin JS/CSS and prints candidate endpoint strings from the shipped code.

Do **not** submit Wi-Fi credentials while doing the initial capture.

Then return the opener to normal home Wi-Fi and test only the exact read-only paths/ports revealed by its own setup assets against the confirmed normal opener IP.

If entering setup mode would erase current Wi-Fi configuration rather than merely expose the supported temporary AP, do not continue unless the reprovision path is known; continue normal-LAN/8883 work instead.

## 4. Capture opener → Chamberlain traffic

Preferred source is the router/AP, scoped to the opener IP/MAC. Capture:

1. idle/reconnect baseline;
2. official app status refresh;
3. one wall-button state change;
4. at most one official-app explicit state command while physically observed.

Summarize:

```bash
python tools/pcap_summary.py captures/opener.pcap --opener-ip <OPENER-IP>
```

We need:

- DNS hostname(s);
- destination IP/port;
- whether TCP 8883 is really present;
- TLS SNI/ALPN/certificate metadata;
- connection/reconnect cadence.

Do not label it MQTT merely because the destination port is 8883.

## 5. First cloud-emulation experiment: DNS redirect to passive listener

Only after the real opener hostname is known.

On a LAN host reachable by the opener:

```bash
sudo python tools/tls_clienthello_listener.py --bind 0.0.0.0 --port 8883
```

Temporarily override **only the discovered Chamberlain hostname** in the DNS path used by the opener so it resolves to this listener host. Keep rollback ready.

Interpretation:

- no connection: opener may ignore DNS/cache/hard-code address, or redirect path is wrong;
- connection but non-TLS: inspect protocol bytes separately;
- TLS ClientHello with expected SNI: DNS redirect works — cloud emulator milestone E0;
- ClientHello ALPN/cipher data gives the next TLS experiment.

The listener does not complete TLS and sends no command.

After proving or disproving E0, restore normal DNS before doing certificate/emulator design. Do not leave the opener offline unnecessarily.

## 6. TLS decision tree

After E0:

### If normal certificate validation appears likely
We cannot impersonate Chamberlain merely with a self-signed certificate. Determine whether the opener has a vendor CA/pinning model or whether commissioning provides any trust mechanism.

### If certificate pinning is evident
Static analysis/firmware work becomes necessary before transparent emulation.

### If mTLS/client certificate is evident
Determine whether the opener's client credential is exportable software state or device-bound. Do not commit private key material.

### If TLS can legitimately be terminated
Only then recover application semantics (MQTT or otherwise), build the minimum telemetry-only emulator, then test one explicit command.

A self-signed certificate failure alone is **not** proof of pinning; ordinary CA validation produces the same result.

## 7. Broadlink integration target

Any successful true-local implementation must expose:

```text
GET  /garage/status
POST /garage/open
POST /garage/close
```

Broadlink configuration:

```text
MYQ_LOCAL_URL=http://<local-service>
MYQ_LOCAL_API_KEY=<private key>
```

Broadlink already prefers this over the Superbox bridge.

## What counts as useful progress

Do not stop just because local command control is not achieved in one session. These are distinct milestones:

- opener positively identified;
- setup portal captured;
- local endpoint found;
- normal-LAN local status found;
- broker hostname found;
- TCP 8883 confirmed;
- MQTT confirmed;
- DNS redirect followed;
- TLS model classified;
- telemetry semantics recovered;
- one local command works.

Post sanitized evidence to #1, #3, #5, or #6 as appropriate and keep raw captures local/ignored.
