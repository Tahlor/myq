# MyQ reverse-engineering tools

These tools support opener-local interoperability work. Raw captures belong under ignored `captures/` and must not be committed.

## `lan_probe.py`
Find likely Chamberlain/LiftMaster devices on the home LAN, including ARP-visible hosts that ignore ping.

```bash
python tools/lan_probe.py --subnet 192.168.187.0/24
```

## `setup_portal_capture.py`
GET-only capture of the opener's supported setup portal and same-origin JS/CSS assets. Extracts candidate local API paths from the shipped code.

```bash
python tools/setup_portal_capture.py http://setup.myqdevice.com/
```

Or by setup-gateway IP:

```bash
python tools/setup_portal_capture.py http://<SETUP-GATEWAY-IP>/ --host-header setup.myqdevice.com
```

The tool does not submit forms or Wi-Fi credentials.

## `pcap_summary.py`
Summarize opener DNS/TLS/remote endpoints from a router/AP/switch capture.

```bash
python tools/pcap_summary.py captures/opener.pcap --opener-ip <OPENER-IP>
```

## `tls_clienthello_listener.py`
Passive listener for the first cloud-emulation experiment. After discovering the opener's real Chamberlain hostname, temporarily redirect only that hostname to the listener host and see whether the opener follows DNS.

```bash
sudo python tools/tls_clienthello_listener.py --bind 0.0.0.0 --port 8883
```

It records only initial TLS metadata such as SNI/ALPN/cipher counts and does not complete TLS or send an application command.

## `tls_transparent_probe.py`
Handshake-only relay for a controlled, already-authorized redirect when the
opener's upstream endpoint is known. It forwards TLS handshake records to the
real upstream, logs record/cipher metadata, and blocks application-data records
in both directions. It does not terminate TLS or inject a command:

```bash
python tools/tls_transparent_probe.py --bind 0.0.0.0 --port 8883 \
  --upstream-host connect.myqdevice.com --upstream-port 8883 --once
```

Use only with a temporary router rule scoped to the confirmed opener and remove
that rule immediately after the observation. The current MYQ-G0401 evidence
shows a PSK-based TLS handshake, so this tool is an observation aid rather than
a local broker implementation.

## `myq_firmware_psm.py`
Offline, secret-safe triage for a firmware/SPI-flash dump. It locates the
related firmware's `myq_aes` PSM record, reproduces the observed 32-round
four-word TEA unwrap, and prints metadata plus hashes only—never the key bytes:

```bash
python tools/myq_firmware_psm.py captures/firmware.bin
```

Keep the raw dump under ignored `captures/`. The unwrap constant is from the
related historical image, so re-validate the model/version and code literal
before treating an output as evidence about another device.

## `summarize_jadx.py`
Static triage of the exact installed official MyQ APK after JADX decompilation. Prioritizes opener-local provisioning, network, MQTT/cloud, TLS/pinning, Wi-Fi and BLE clues.

```bash
python tools/summarize_jadx.py <jadx-output>
```

Read `myq-static-summary.json`; it remains local with the decompile output.

See `docs/LIVE_RUNBOOK.md` for the complete hands-on sequence.
