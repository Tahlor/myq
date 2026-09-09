"""Bounded, read-only archaeology of the G0401 normal-LAN HTTP surface."""

from __future__ import annotations

import argparse
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable


EVIDENCE_ROUTES = (
    "/",
    "/jabout",
    "/config.html",
    "/config_hub.html",
    "/connect_hub.html",
    "/start.html",
    "/jscan_results",
)
READ_ONLY_ROUTES = frozenset(EVIDENCE_ROUTES)
_MUTATING_ROUTE_MARKERS = (
    "config_save",
    "connect_serial",
    "provision",
    "factory_reset",
    "pair",
    "submit",
    "reset",
    "save",
)
MAX_BODY_BYTES = 256 * 1024
MAX_ASSETS = 32
MAX_CANDIDATES = 200
_PATH_RE = re.compile(
    r"(?<![A-Za-z0-9_/:<])/(?:[A-Za-z0-9._-]+/)*[A-Za-z0-9._-]+"
)
_ASSET_RE = re.compile(r"(?:src|href)\s*=\s*['\"]([^'\"]+)['\"]", re.IGNORECASE)
_CSS_URL_RE = re.compile(r"url\(\s*['\"]?([^'\")]+)", re.IGNORECASE)


def classify_route(route: str) -> str:
    """Classify a fixed route before any network request is made."""

    path = urllib.parse.urlsplit(route).path.lower()
    if path in READ_ONLY_ROUTES:
        return "read-only"
    if any(marker in path for marker in _MUTATING_ROUTE_MARKERS):
        return "provisioning-mutation"
    return "unknown"


def _same_origin(left: str, right: str) -> bool:
    a = urllib.parse.urlsplit(left)
    b = urllib.parse.urlsplit(right)
    return (a.scheme, a.netloc) == (b.scheme, b.netloc)


def _safe_path(url: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    path = parsed.path or "/"
    return path[:300]


def extract_candidate_paths(text: str) -> list[str]:
    paths = {_safe_path(match) for match in _PATH_RE.findall(text)}
    return sorted(path for path in paths if path != "/")[:MAX_CANDIDATES]


def extract_same_origin_assets(base_url: str, text: str) -> list[str]:
    references = _ASSET_RE.findall(text) + _CSS_URL_RE.findall(text)
    assets: list[str] = []
    seen: set[str] = set()
    for reference in references:
        absolute = urllib.parse.urljoin(base_url, reference)
        if not _same_origin(base_url, absolute):
            continue
        path = urllib.parse.urlsplit(absolute).path
        if not path or path in seen:
            continue
        if not path.lower().endswith((".js", ".css", ".html", ".htm")):
            continue
        seen.add(path)
        assets.append(absolute)
        if len(assets) >= MAX_ASSETS:
            break
    return assets


def _decode_body(body: bytes, content_type: str) -> str:
    charset = "utf-8"
    match = re.search(r"charset=\s*([A-Za-z0-9._-]+)", content_type, re.IGNORECASE)
    if match:
        charset = match.group(1)
    return body.decode(charset, errors="replace")


def fetch_read_only(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    timeout: float = 5.0,
    max_body_bytes: int = MAX_BODY_BYTES,
    opener: Callable[..., Any] = urllib.request.urlopen,
) -> dict[str, Any]:
    """Fetch one URL with GET and return metadata plus a bounded private body."""

    request = urllib.request.Request(url, method="GET", headers=headers or {})
    try:
        with opener(request, timeout=timeout) as response:
            body = response.read(max_body_bytes + 1)
            headers_obj = response.headers
            content_type = headers_obj.get("Content-Type", "")
            return {
                "status": int(getattr(response, "status", response.getcode())),
                "content_type": content_type,
                "content_length": len(body),
                "truncated": len(body) > max_body_bytes,
                "final_path": _safe_path(response.geturl()),
                "body": body[:max_body_bytes],
            }
    except urllib.error.HTTPError as exc:
        body = exc.read(max_body_bytes + 1)
        return {
            "status": exc.code,
            "content_type": exc.headers.get("Content-Type", ""),
            "content_length": len(body),
            "truncated": len(body) > max_body_bytes,
            "final_path": _safe_path(exc.geturl()),
            "body": body[:max_body_bytes],
        }
    except (OSError, urllib.error.URLError) as exc:
        return {
            "status": None,
            "content_type": "",
            "content_length": 0,
            "truncated": False,
            "final_path": None,
            "error": type(exc).__name__,
            "body": b"",
        }


def _public_record(path: str, response: dict[str, Any]) -> dict[str, Any]:
    return {
        "path": path,
        "status": response.get("status"),
        "content_type": response.get("content_type", ""),
        "content_length": response.get("content_length", 0),
        "truncated": response.get("truncated", False),
        "final_path": response.get("final_path"),
        **({"error": response["error"]} if response.get("error") else {}),
    }


def run_archaeology(
    base_url: str,
    *,
    host_header: str | None = None,
    routes: tuple[str, ...] = EVIDENCE_ROUTES,
    timeout: float = 5.0,
    opener: Callable[..., Any] = urllib.request.urlopen,
) -> dict[str, Any]:
    parsed = urllib.parse.urlsplit(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("base_url must be an absolute http(s) URL")
    base = base_url.rstrip("/") + "/"
    headers = {"Host": host_header} if host_header else {}
    route_records: list[dict[str, Any]] = []
    asset_urls: list[str] = []
    candidates: set[str] = set()
    asset_seen: set[str] = set()

    for route in routes:
        if not route.startswith("/") or "?" in route:
            raise ValueError(f"route is not a fixed read-only path: {route!r}")
        category = classify_route(route)
        if category != "read-only":
            route_records.append(
                {
                    "path": route,
                    "category": category,
                    "skipped": True,
                    "reason": "route is not in the evidence-backed read-only dictionary",
                }
            )
            continue
        url = urllib.parse.urljoin(base, route)
        response = fetch_read_only(url, headers=headers, timeout=timeout, opener=opener)
        route_record = _public_record(route, response)
        route_record["category"] = category
        route_records.append(route_record)
        if response.get("status") != 200 or not _same_origin(base, url):
            continue
        content_type = str(response.get("content_type", "")).lower()
        if "text" not in content_type and "javascript" not in content_type:
            continue
        text = _decode_body(response.get("body", b""), content_type)
        candidates.update(extract_candidate_paths(text))
        for asset in extract_same_origin_assets(url, text):
            if asset not in asset_seen and len(asset_urls) < MAX_ASSETS:
                asset_seen.add(asset)
                asset_urls.append(asset)

    assets: list[dict[str, Any]] = []
    for asset in asset_urls:
        response = fetch_read_only(asset, headers=headers, timeout=timeout, opener=opener)
        assets.append(_public_record(_safe_path(asset), response))
        if response.get("status") == 200:
            content_type = str(response.get("content_type", "")).lower()
            if "text" in content_type or "javascript" in content_type:
                candidates.update(
                    extract_candidate_paths(
                        _decode_body(response.get("body", b""), content_type)
                    )
                )

    return {
        "tool": "g0401_http_archaeology",
        "target": "<redacted>",
        "host_header_used": bool(host_header),
        "routes": route_records,
        "same_origin_assets": assets,
        "candidate_paths": sorted(candidates)[:MAX_CANDIDATES],
        "mutations_attempted": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="GET-only G0401 HTTP archaeology")
    parser.add_argument("base_url")
    parser.add_argument("--host-header")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=5.0)
    args = parser.parse_args()
    try:
        report = run_archaeology(
            args.base_url,
            host_header=args.host_header,
            timeout=args.timeout,
        )
    except ValueError as exc:
        parser.error(str(exc))
    args.out.mkdir(parents=True, exist_ok=True)
    output = args.out / "summary.json"
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
