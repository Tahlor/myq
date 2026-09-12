"""Offline audit of firmware/update surfaces in a decompiled Android APK.

This tool is intentionally static. It never invokes an Android component or
contacts a network service. It reports only source locations, method
signatures, known firmware/update symbol names, Retrofit route literals, and
coarse download/storage primitive names.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

TARGET_LITERALS = (
    "latest_available_firmware_version",
    "firmware_version",
    "firmware_available",
    "mandatory_update_status",
    "vkp_current_firmware_version",
    "myq_firmware_version",
)

DOWNLOAD_PRIMITIVES = (
    "Landroid/app/DownloadManager;",
    "Ljava/net/HttpURLConnection;",
    "Ljava/net/URL;",
    "Ljava/io/FileOutputStream;",
    "Lokhttp3/e0;",
    "Lretrofit2/b;",
)

METHOD_RE = re.compile(r"^\s*\.method\s+(?P<sig>.+)$")
END_METHOD_RE = re.compile(r"^\s*\.end\s+method\b")
ANNOTATION_RE = re.compile(r"^\s*\.annotation\s+runtime\s+Lretrofit2/http/(?P<kind>[^;]+);")
END_ANNOTATION_RE = re.compile(r"^\s*\.end\s+annotation\b")
VALUE_RE = re.compile(r'^\s*value\s*=\s*"(?P<value>[^"]*)"')
URL_RE = re.compile(r'https?://[^\s"<>]+', re.IGNORECASE)
HOST_RE = re.compile(r"\b(?:[a-z0-9-]+\.)+(?:com|net|org|io|cloud)\b", re.IGNORECASE)
ROUTE_SIGNAL_RE = re.compile(r"(?:^|[/_.-])(firmware|update|upgrade|ota|manifest)(?:$|[/_.-])", re.IGNORECASE)
ROUTE_SHORTLIST_RE = re.compile(
    r'value\s*=\s*"[^"]*(?:firmware|update|upgrade|ota|manifest)', re.IGNORECASE
)
PRIMITIVE_CONTEXT_RE = re.compile(
    r"firmware|mandatory_update_status|latest_available_firmware_version|"
    r"firmware_available|vkp_current_firmware_version|myq_firmware_version",
    re.IGNORECASE,
)


def _smali_files(root: Path) -> list[Path]:
    if root.is_file():
        return [root]
    return sorted(path for path in root.rglob("*.smali") if path.is_file())


def _relative(path: Path, root: Path) -> str:
    return path.name if root.is_file() else path.relative_to(root).as_posix()


def _method_ranges(lines: list[str]) -> list[tuple[int, int, str]]:
    ranges: list[tuple[int, int, str]] = []
    start: int | None = None
    signature = "<class-scope>"
    for index, line in enumerate(lines):
        match = METHOD_RE.match(line)
        if match:
            start = index
            signature = match.group("sig").strip()
        elif start is not None and END_METHOD_RE.match(line):
            ranges.append((start, index, signature))
            start = None
            signature = "<class-scope>"
    if start is not None:
        ranges.append((start, len(lines) - 1, signature))
    return ranges


def _method_at(index: int, ranges: list[tuple[int, int, str]]) -> str:
    for start, end, signature in ranges:
        if start <= index <= end:
            return signature
    return "<class-scope>"


def _retrofit_routes(
    lines: list[str], path: str, method_ranges: list[tuple[int, int, str]]
) -> list[dict[str, Any]]:
    routes: list[dict[str, Any]] = []
    active_kind: str | None = None
    for index, line in enumerate(lines):
        annotation = ANNOTATION_RE.match(line)
        if annotation:
            active_kind = annotation.group("kind")
            continue
        if active_kind and END_ANNOTATION_RE.match(line):
            active_kind = None
            continue
        if not active_kind:
            continue
        value_match = VALUE_RE.match(line)
        if not value_match:
            continue
        value = value_match.group("value")
        if not ROUTE_SIGNAL_RE.search(value):
            continue
        routes.append(
            {
                "path": path,
                "line": index + 1,
                "method": _method_at(index, method_ranges),
                "annotation_kind": active_kind,
                "route": value,
            }
        )
    return routes


def audit(root: Path) -> dict[str, Any]:
    if not root.exists():
        raise FileNotFoundError(root)

    target_refs: list[dict[str, Any]] = []
    route_candidates: list[dict[str, Any]] = []
    primitive_refs: list[dict[str, Any]] = []
    network_literals: set[str] = set()
    files_scanned = 0
    files_deep_parsed = 0

    for file_path in _smali_files(root):
        files_scanned += 1
        text = file_path.read_text(encoding="utf-8", errors="replace")
        has_target = any(literal in text for literal in TARGET_LITERALS)
        has_route_candidate = "Lretrofit2/http/" in text and bool(ROUTE_SHORTLIST_RE.search(text))
        if not has_target and not has_route_candidate:
            continue

        files_deep_parsed += 1
        lines = text.splitlines()
        rel = _relative(file_path, root)
        ranges = _method_ranges(lines)

        if has_target:
            for index, line in enumerate(lines):
                for literal in TARGET_LITERALS:
                    if literal in line:
                        target_refs.append(
                            {
                                "symbol": literal,
                                "path": rel,
                                "line": index + 1,
                                "method": _method_at(index, ranges),
                            }
                        )

                if not PRIMITIVE_CONTEXT_RE.search(text):
                    continue
                for primitive in DOWNLOAD_PRIMITIVES:
                    if primitive not in line:
                        continue
                    nearby = "\n".join(
                        lines[max(0, index - 24) : min(len(lines), index + 25)]
                    )
                    if PRIMITIVE_CONTEXT_RE.search(nearby):
                        primitive_refs.append(
                            {
                                "primitive": primitive,
                                "path": rel,
                                "line": index + 1,
                                "method": _method_at(index, ranges),
                            }
                        )

            network_literals.update(URL_RE.findall(text))
            network_literals.update(HOST_RE.findall(text))

        if has_route_candidate:
            route_candidates.extend(_retrofit_routes(lines, rel, ranges))

    unique_refs = sorted(
        {tuple(sorted(item.items())) for item in target_refs},
        key=lambda item: (dict(item)["path"], dict(item)["line"], dict(item)["symbol"]),
    )
    target_refs = [dict(items) for items in unique_refs]

    return {
        "tool": "android_firmware_surface_audit",
        "root": "<redacted>",
        "target_refs": target_refs,
        "retrofit_route_candidates": route_candidates,
        "download_primitive_refs": primitive_refs,
        "network_literals_in_firmware_files": sorted(network_literals),
        "summary": {
            "files_scanned": files_scanned,
            "files_deep_parsed": files_deep_parsed,
            "target_ref_count": len(target_refs),
            "retrofit_route_candidate_count": len(route_candidates),
            "download_primitive_ref_count": len(primitive_refs),
            "network_literal_count": len(network_literals),
        },
        "network_requests_made": False,
        "android_components_invoked": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Offline Android firmware/update surface audit")
    parser.add_argument("path", type=Path, help="Decompiled smali root or one .smali file")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    try:
        report = audit(args.path)
    except FileNotFoundError as exc:
        parser.error(str(exc))
    payload = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(payload, encoding="utf-8")
    print(payload, end="")


if __name__ == "__main__":
    main()
