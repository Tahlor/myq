"""Inventory Android surfaces without invoking an Android component.

The input is an exact decompiled APK manifest and, optionally, its JADX source
tree. Output contains component/intent metadata and signal locations only; it
does not copy source lines, tokens, URLs, or other potentially sensitive
payloads into the report.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any
from xml.etree import ElementTree


ANDROID_NS = "http://schemas.android.com/apk/res/android"
SOURCE_SUFFIXES = {".java", ".kt", ".kts", ".smali", ".xml"}
SIGNAL_PATTERNS: dict[str, re.Pattern[str]] = {
    "pending_intent": re.compile(r"\bPendingIntent\b"),
    "shortcut": re.compile(r"\bShortcutInfo\b|\bShortcutManager\b"),
    "widget": re.compile(r"\bAppWidgetProvider\b|\bAppWidgetManager\b"),
    "intent": re.compile(r"\bIntent\b|\bIntentFilter\b"),
    "activity_dispatch": re.compile(r"\bstartActivity(?:ForResult)?\b"),
    "service_dispatch": re.compile(r"\bstart(?:Foreground)?Service\b"),
    "broadcast_dispatch": re.compile(r"\bsendBroadcast\b|\bsendOrderedBroadcast\b"),
    "notification_action": re.compile(r"\bNotification\b|\bRemoteInput\b"),
    "operation_terms": re.compile(
        r"\b(?:garage|door|opener|device)\b.{0,80}\b(?:open|close|unlock|lock)\b"
        r"|\b(?:open|close|unlock|lock)\b.{0,80}\b(?:garage|door|opener|device)\b",
        re.IGNORECASE,
    ),
}


def _android_attr(element: ElementTree.Element, name: str) -> str:
    return element.attrib.get(f"{{{ANDROID_NS}}}{name}", element.attrib.get(name, ""))


def _component_name(element: ElementTree.Element) -> str:
    return _android_attr(element, "name") or "<unnamed>"


def inventory_manifest(path: Path) -> dict[str, Any]:
    """Return sanitized component and intent metadata from a manifest."""

    root = ElementTree.parse(path).getroot()
    application = root.find("application")
    components: list[dict[str, Any]] = []
    if application is not None:
        for tag in ("activity", "activity-alias", "service", "receiver", "provider"):
            for element in application.findall(tag):
                filters: list[dict[str, Any]] = []
                for intent_filter in element.findall("intent-filter"):
                    actions = sorted(
                        name
                        for action in intent_filter.findall("action")
                        if (name := _android_attr(action, "name"))
                    )
                    categories = sorted(
                        name
                        for category in intent_filter.findall("category")
                        if (name := _android_attr(category, "name"))
                    )
                    data = [
                        {
                            key: value
                            for key, value in (
                                ("scheme", _android_attr(item, "scheme")),
                                ("host", _android_attr(item, "host")),
                                ("path", _android_attr(item, "path")),
                                ("mime_type", _android_attr(item, "mimeType")),
                            )
                            if value
                        }
                        for item in intent_filter.findall("data")
                    ]
                    filters.append(
                        {
                            "actions": actions,
                            "categories": categories,
                            "data": data,
                        }
                    )
                components.append(
                    {
                        "type": tag,
                        "name": _component_name(element),
                        "exported": _android_attr(element, "exported") or None,
                        "permission": _android_attr(element, "permission") or None,
                        "has_intent_filter": bool(filters),
                        "intent_filters": filters,
                    }
                )

    return {
        "package": _android_attr(root, "package") or None,
        "components": sorted(components, key=lambda item: (item["type"], item["name"])),
    }


def inventory_source_signals(source_root: Path, *, max_matches: int = 2000) -> list[dict[str, Any]]:
    """Locate non-secret action-dispatch signals in an extracted source tree."""

    if not source_root.exists():
        return []
    matches: list[dict[str, Any]] = []
    for path in sorted(source_root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in SOURCE_SUFFIXES:
            continue
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        relative = path.relative_to(source_root).as_posix()
        for line_number, line in enumerate(lines, start=1):
            signals = sorted(
                name for name, pattern in SIGNAL_PATTERNS.items() if pattern.search(line)
            )
            if signals:
                matches.append(
                    {
                        "file": relative,
                        "line": line_number,
                        "signals": signals,
                    }
                )
                if len(matches) >= max_matches:
                    return matches
    return matches


def parse_manifest(path: Path) -> dict[str, Any]:
    """Compatibility-shaped manifest report for policy/tests and CLI callers."""

    report = inventory_manifest(path)
    package = report["package"] or ""
    components = []
    counts: dict[str, int] = {}
    for component in report["components"]:
        name = component["name"]
        if package and not name.startswith(".") and "." not in name:
            name = f"{package}.{name}"
        elif package and name.startswith("."):
            name = f"{package}{name}"
        item = {**component, "name": name}
        components.append(item)
        counts[item["type"]] = counts.get(item["type"], 0) + 1
    return {
        "package": package or None,
        "component_counts": counts,
        "components": components,
    }


def scan_jadx_sources(source_root: Path, *, max_matches: int = 2000) -> dict[str, Any]:
    """Return sanitized source signal locations in the historical test shape."""

    marker_patterns: tuple[tuple[str, re.Pattern[str]], ...] = (
        ("PendingIntent", re.compile(r"\bPendingIntent\b")),
        ("ShortcutInfo", re.compile(r"\bShortcutInfo\b|\bShortcutManager\b")),
        ("AppWidgetProvider", re.compile(r"\bAppWidgetProvider\b|\bAppWidgetManager\b")),
        ("Intent", re.compile(r"\bIntent\b|\bIntentFilter\b")),
        ("startActivity", re.compile(r"\bstartActivity(?:ForResult)?\b")),
        ("startService", re.compile(r"\bstart(?:Foreground)?Service\b")),
        ("sendBroadcast", re.compile(r"\bsendBroadcast\b|\bsendOrderedBroadcast\b")),
        ("open_close", SIGNAL_PATTERNS["operation_terms"]),
    )
    matches: list[dict[str, Any]] = []
    if not source_root.exists():
        return {"action_call_site_matches": matches}
    for path in sorted(source_root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in SOURCE_SUFFIXES:
            continue
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        relative = path.relative_to(source_root).as_posix()
        for line_number, line in enumerate(lines, start=1):
            markers = [name for name, pattern in marker_patterns if pattern.search(line)]
            if not markers:
                continue
            matches.append({"file": relative, "line": line_number, "markers": markers})
            if len(matches) >= max_matches:
                return {"action_call_site_matches": matches}
    return {"action_call_site_matches": matches}


def build_report(manifest: Path, source_root: Path | None = None) -> dict[str, Any]:
    report: dict[str, Any] = {
        "tool": "android_surface_inventory",
        "manifest": manifest.name,
        "manifest_inventory": inventory_manifest(manifest),
        "source_signals": [],
    }
    if source_root is not None:
        report["source_root"] = source_root.name
        report["source_signals"] = inventory_source_signals(source_root)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Read-only Android manifest/JADX surface inventory"
    )
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--jadx", type=Path, help="Optional JADX source directory")
    parser.add_argument("--output", type=Path, help="Optional JSON output path")
    args = parser.parse_args()

    if not args.manifest.is_file():
        parser.error(f"Manifest does not exist: {args.manifest}")
    if args.jadx is not None and not args.jadx.is_dir():
        parser.error(f"JADX source directory does not exist: {args.jadx}")

    payload = json.dumps(build_report(args.manifest, args.jadx), indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")
    print(payload)


if __name__ == "__main__":
    main()
