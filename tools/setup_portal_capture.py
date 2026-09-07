#!/usr/bin/env python3
"""Read-only capture/analyzer for the opener's MyQ setup web portal.

This tool intentionally performs GET requests only. It never submits forms or
Wi-Fi credentials. Use it while connected to the opener's supported `myQ-*`
setup AP to preserve the HTML/JS/CSS that reveals the local provisioning API.

Examples:

    python tools/setup_portal_capture.py http://setup.myqdevice.com/

If DNS does not resolve but the opener gateway is 192.168.10.1:

    python tools/setup_portal_capture.py http://192.168.10.1/ \
        --host-header setup.myqdevice.com

Raw captures are private/runtime evidence and should remain under ignored
`captures/`. The printed endpoint candidates are intentionally sanitized.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

DEFAULT_TIMEOUT = 5.0
MAX_ASSET_BYTES = 2_000_000
INTERESTING_WORDS = (
    "api",
    "setup",
    "system",
    "device",
    "wifi",
    "network",
    "status",
    "scan",
    "ssid",
    "firmware",
    "model",
    "serial",
    "open",
    "close",
    "door",
    "garage",
    "mqtt",
    "websocket",
    "ws://",
    "wss://",
)

# URL-ish/path-ish string literals. We report only the literal path/URL, never
# surrounding source text that might contain credentials or personal data.
PATH_RE = re.compile(
    r"(?P<q>['\"])(?P<value>(?:https?://|wss?://|/)[^'\"\s<>]{1,220})(?P=q)",
    re.IGNORECASE,
)


class AssetParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.assets: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        candidate = None
        if tag == "script":
            candidate = values.get("src")
        elif tag == "link":
            rel = (values.get("rel") or "").lower()
            if "stylesheet" in rel or values.get("href", "").lower().endswith((".js", ".css")):
                candidate = values.get("href")
        if candidate:
            self.assets.append(candidate)


def _safe_filename(url: str, content_type: str | None = None) -> str:
    parsed = urlparse(url)
    name = Path(parsed.path).name or "index.html"
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", name)[:100] or "asset"
    if "." not in name and content_type:
        if "javascript" in content_type:
            name += ".js"
        elif "css" in content_type:
            name += ".css"
        elif "html" in content_type:
            name += ".html"
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:10]
    return f"{digest}_{name}"


def _fetch(url: str, host_header: str | None, timeout: float) -> tuple[bytes, dict[str, str]]:
    headers = {
        "User-Agent": "myq-local-interoperability-capture/1.0",
        "Accept": "text/html,application/javascript,text/css,*/*;q=0.2",
    }
    if host_header:
        headers["Host"] = host_header
    req = Request(url, method="GET", headers=headers)
    with urlopen(req, timeout=timeout) as response:
        data = response.read(MAX_ASSET_BYTES + 1)
        if len(data) > MAX_ASSET_BYTES:
            raise RuntimeError(f"response exceeded {MAX_ASSET_BYTES} bytes: {url}")
        return data, {k.lower(): v for k, v in response.headers.items()}


def extract_endpoint_candidates(texts: Iterable[str]) -> list[str]:
    found: set[str] = set()
    for text in texts:
        for match in PATH_RE.finditer(text):
            value = match.group("value")
            lower = value.lower()
            if any(word in lower for word in INTERESTING_WORDS):
                # Avoid accidentally printing obvious query-string values. Keep only
                # scheme/netloc/path for absolute URLs and strip query/fragment.
                parsed = urlparse(value)
                if parsed.scheme:
                    value = parsed._replace(query="", fragment="").geturl()
                else:
                    value = value.split("?", 1)[0].split("#", 1)[0]
                found.add(value)
    return sorted(found)


def same_origin_asset(base_url: str, candidate: str) -> str | None:
    full = urljoin(base_url, candidate)
    base = urlparse(base_url)
    parsed = urlparse(full)
    if parsed.scheme not in {"http", "https"}:
        return None
    if parsed.hostname != base.hostname or parsed.port != base.port:
        return None
    return full


def capture(base_url: str, out_dir: Path, host_header: str | None, timeout: float) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    root_data, root_headers = _fetch(base_url, host_header, timeout)
    root_path = out_dir / _safe_filename(base_url, root_headers.get("content-type"))
    root_path.write_bytes(root_data)

    root_text = root_data.decode("utf-8", errors="replace")
    parser = AssetParser()
    parser.feed(root_text)

    captured: list[dict[str, str | int]] = [
        {
            "url": base_url,
            "file": root_path.name,
            "bytes": len(root_data),
            "content_type": root_headers.get("content-type", ""),
        }
    ]
    text_blobs = [root_text]

    seen: set[str] = {base_url}
    for candidate in parser.assets:
        asset_url = same_origin_asset(base_url, candidate)
        if not asset_url or asset_url in seen:
            continue
        seen.add(asset_url)
        try:
            data, headers = _fetch(asset_url, host_header, timeout)
        except (HTTPError, URLError, TimeoutError, RuntimeError) as exc:
            captured.append({"url": asset_url, "error": type(exc).__name__})
            continue
        path = out_dir / _safe_filename(asset_url, headers.get("content-type"))
        path.write_bytes(data)
        captured.append(
            {
                "url": asset_url,
                "file": path.name,
                "bytes": len(data),
                "content_type": headers.get("content-type", ""),
            }
        )
        content_type = headers.get("content-type", "").lower()
        if any(x in content_type for x in ("javascript", "json", "html", "text/")) or path.suffix.lower() in {".js", ".html", ".json", ".txt"}:
            text_blobs.append(data.decode("utf-8", errors="replace"))

    endpoints = extract_endpoint_candidates(text_blobs)
    manifest = {
        "base_url": base_url,
        "host_header": host_header,
        "captured": captured,
        "endpoint_candidates": endpoints,
        "note": "GET-only capture; endpoint candidates are static strings, not proof endpoints are live.",
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", help="Setup portal URL, usually http://setup.myqdevice.com/")
    parser.add_argument("--host-header", help="Optional Host header when addressing setup gateway by IP")
    parser.add_argument("--out", type=Path, default=Path("captures/setup_portal"))
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    args = parser.parse_args(argv)

    parsed = urlparse(args.url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        parser.error("url must be an http(s) URL")

    try:
        result = capture(args.url, args.out, args.host_header, args.timeout)
    except (HTTPError, URLError, TimeoutError, RuntimeError) as exc:
        print(f"capture failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    print(f"Captured {len(result['captured'])} page/assets into {args.out}")
    print("Candidate local endpoints/URLs from shipped assets:")
    if result["endpoint_candidates"]:
        for value in result["endpoint_candidates"]:
            print(f"  {value}")
    else:
        print("  (none found by static string scan)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
