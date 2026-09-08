# MyQ software-first research tools

Raw captures belong under ignored captures/ and must not be committed. These
tools are observation/parsing aids; none is a production cloud or garage
command implementation.

The next #9 implementation items are a secret-safe APK surface inventory and
a HEAD/GET-only G0401 route archaeologist. They are intentionally not listed as
available commands until their read-only behavior and tests are committed.

## lan_probe.py

Find likely Chamberlain/LiftMaster devices on the home LAN, retaining
ARP-visible hosts that ignore ping.

    python tools/lan_probe.py --subnet 192.168.187.0/24

## setup_portal_capture.py

GET-only capture of the supported setup portal and same-origin JS/CSS assets.
It does not submit Wi-Fi credentials.

    python tools/setup_portal_capture.py http://setup.myqdevice.com/

## pcap_summary.py

Summarize DNS, TLS-SNI, and endpoint metadata from an existing router/AP/switch
capture. Encrypted application payloads are not decoded.

    python tools/pcap_summary.py captures/opener.pcap --opener-ip <opener-ip>

## tls observation tools

tls_clienthello_listener.py passively records initial ClientHello metadata.
tls_transparent_probe.py relays only handshake records to a known upstream and
blocks application-data records. The current G0401 uses a PSK handshake, so
these tools do not create a usable local broker.

## myq_firmware_psm.py

Offline, secret-safe triage of related firmware/SPI dumps. It locates the
historical myq_aes record, reproduces the observed TEA unwrap in memory, and
prints metadata/hashes only. It does not derive or print a current-device key.

## historical_mcu_protocol.py

Offline parser/tests for labeled public historical MCU frames. Its CRC,
state, and action meanings are hypotheses for comparison and do not prove
current G0401 compatibility.

## summarize_jadx.py

Static triage of the exact installed official APK for cloud hosts, local
setup/provisioning, transport, TLS, Wi-Fi, and BLE clues. Decompile output
stays ignored.

See docs/LIVE_RUNBOOK.md for the current issue #9 execution order. Direct
cloud remains experimental/current-2026 evidence only, and pymyq is permanently
deprecated.
