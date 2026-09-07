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

## `summarize_jadx.py`
Static triage of the exact installed official MyQ APK after JADX decompilation. Prioritizes opener-local provisioning, network, MQTT/cloud, TLS/pinning, Wi-Fi and BLE clues.

```bash
python tools/summarize_jadx.py <jadx-output>
```

Read `myq-static-summary.json`; it remains local with the decompile output.

See `docs/LIVE_RUNBOOK.md` for the complete hands-on sequence.
