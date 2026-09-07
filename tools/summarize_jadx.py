from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

# This is a triage tool, not a credential extractor. It focuses on transport,
# provisioning, local-device and certificate clues that help us understand the
# opener's own protocol. Reports stay in ignored decompile output.
PATTERNS = {
    "myq_domains": re.compile(
        r"(?:[A-Za-z0-9._-]+\.)?(?:myq-cloud\.com|myqdevice\.com|myq\.com)", re.I
    ),
    "setup_portal": re.compile(
        r"setup\.myqdevice\.com|myQ-[A-Za-z0-9_-]*|setup.?mode|provision|commission", re.I
    ),
    "local_network": re.compile(
        r"(?:https?://)?(?:192\.168\.|10\.|172\.(?:1[6-9]|2\d|3[01])\.)|"
        r"/api/|/sys/|/setup/|/device/|/wifi/|/network/|/status/|"
        r"nsdmanager|mdns|bonjour|ssdp|multicast|socket", re.I
    ),
    "mqtt": re.compile(
        r"\bmqtt\b|mqtts?://|\b8883\b|client.?id|keep.?alive|subscribe|publish|topic", re.I
    ),
    "iot_cloud": re.compile(
        r"amazonaws\.com|iot\.amazonaws|azure-devices|device.?gateway|broker", re.I
    ),
    "tls_cert": re.compile(
        r"certificatepinner|certificate.?pin|public.?key.?pin|x509|trustmanager|"
        r"hostnameverifier|sslcontext|keystore|truststore|client.?cert|mutual.?tls|mtls", re.I
    ),
    "wifi": re.compile(
        r"wifi(manager|network|scan|ssid|bssid|specifier|suggestion)|softap|access.?point", re.I
    ),
    "ble": re.compile(
        r"bluetooth|ble|gatt|service.?uuid|characteristic.?uuid|scanrecord", re.I
    ),
    "webview": re.compile(
        r"webview|javascriptinterface|shouldinterceptrequest|loadurl|webviewclient", re.I
    ),
    "firebase": re.compile(r"firebase|appcheck", re.I),
    "integrity": re.compile(r"play.?integrity|integritymanager|standardintegrity", re.I),
    "http_stack": re.compile(r"okhttp|retrofit|cronet|volley", re.I),
    "websocket": re.compile(r"websocket|wss?://", re.I),
    "auth": re.compile(r"oauth|pkce|authorization|bearer", re.I),
}

URL_RE = re.compile(r"(?:https?|wss?|mqtts?)://[^\s\"'<>]{3,240}", re.I)
HOST_RE = re.compile(
    r"\b(?:[A-Za-z0-9-]+\.)+(?:com|net|org|io|local)\b", re.I
)
SENSITIVE_RE = re.compile(
    r"(?i)(authorization|bearer|access[_-]?token|refresh[_-]?token|password|secret)"
    r"\s*[:=]\s*([^,;\s]+)"
)


def _redact(text: str) -> str:
    return SENSITIVE_RE.sub(lambda m: f"{m.group(1)}=<redacted>", text)


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: summarize_jadx.py <jadx-output>", file=sys.stderr)
        return 2

    root = Path(sys.argv[1])
    hits: dict[str, list[dict[str, object]]] = defaultdict(list)
    seen_domains: set[str] = set()
    seen_urls: set[str] = set()
    seen_hosts: set[str] = set()

    allowed_suffixes = {
        ".java",
        ".kt",
        ".xml",
        ".json",
        ".txt",
        ".properties",
        ".js",
        ".html",
        ".smali",
    }

    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in allowed_suffixes:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        rel = str(path.relative_to(root))
        lines = text.splitlines()

        for match in URL_RE.finditer(text):
            value = match.group(0).rstrip("),.;]")
            if any(term in value.lower() for term in ("myq", "mqtt", "iot", "device", "setup")):
                seen_urls.add(value.split("?", 1)[0])
        for match in HOST_RE.finditer(text):
            value = match.group(0).lower()
            if any(term in value for term in ("myq", "chamberlain", "liftmaster", "iot", "mqtt")):
                seen_hosts.add(value)

        for category, pattern in PATTERNS.items():
            matched = 0
            for number, line in enumerate(lines, 1):
                if not pattern.search(line):
                    continue
                clean = _redact(" ".join(line.strip().split())[:600])
                hits[category].append({"file": rel, "line": number, "text": clean})
                matched += 1
                if category == "myq_domains":
                    seen_domains.update(m.group(0).lower() for m in PATTERNS["myq_domains"].finditer(line))
                if matched >= 20:
                    break

    report = {
        "root": str(root.resolve()),
        "domains": sorted(seen_domains),
        "interesting_hosts": sorted(seen_hosts),
        "interesting_urls": sorted(seen_urls),
        "categories": {key: value[:150] for key, value in sorted(hits.items())},
        "priority": [
            "setup_portal: opener provisioning/local API clues",
            "local_network: normal-LAN endpoints/listeners",
            "mqtt + iot_cloud: opener-side broker/protocol clues",
            "tls_cert: pinning, trust and mTLS clues",
            "wifi + ble: pairing transport",
        ],
    }
    output = root / "myq-static-summary.json"
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "summary": str(output),
                "domains": report["domains"],
                "interesting_hosts": report["interesting_hosts"],
                "interesting_urls": report["interesting_urls"],
                "hit_counts": {k: len(v) for k, v in hits.items()},
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
