# MyQ software-first research tools

Raw captures belong under ignored captures/ and must not be committed. These
tools are observation/parsing aids; none is a production cloud or garage
command implementation.

## android_surface_inventory.py

Read an exact APK (including its binary AndroidManifest.xml), a decompiled
AndroidManifest.xml, and an optional JADX/smali source tree. It reports
component/export/intent metadata plus sanitized call-site locations for
internal action discovery. It never invokes an Android component.

    python tools/android_surface_inventory.py <exact.apk> --jadx <jadx-output>/sources

## android_sdk_surface_audit.py

Audit the exact APK's selected smali surfaces without invoking an Android
component. It separates dashboard navigation markers from the bundled v6
device transport and reports only counts, method names, and a conclusion. A
transport body type is an audit lead, not permission to invoke a command:

    python tools/android_sdk_surface_audit.py captures/apk/smali-classes3-20260907 --dashboard captures/apk/smali-classes2-20260907/com/chamberlain/myq/main/HomeTabsActivity.smali --app-root captures/apk/smali-classes2-20260907/com/chamberlain/myq

## g0401_http_archaeology.py

GET-only normal-LAN route archaeology for the current G0401. It checks a small
evidence-backed route dictionary, fetches same-origin static assets referenced
by returned pages, classifies route candidates offline, and writes sanitized
metadata. It never submits forms or calls provisioning mutations.

    python tools/g0401_http_archaeology.py http://<g0401-ip>/ --host-header setup.myqdevice.com --out captures/lan/http-archaeology

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

## ota_surface_catalog.py

Offline catalog for APK/resources/firmware artifacts. It reports only hashes,
sizes, signal category names, and match counts for OTA/update, Realtek/AmebaD
`RTL8720CS`/`6220N-IS`, and PSK-provisioning lineage clues. It never emits
matching strings or secret bytes:

    python tools/ota_surface_catalog.py captures/firmware --out captures/ota/catalog.json

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
