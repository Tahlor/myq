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
import struct
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree


ANDROID_NS = "http://schemas.android.com/apk/res/android"
RES_STRING_POOL_TYPE = 0x0001
RES_XML_TYPE = 0x0003
RES_XML_START_NAMESPACE_TYPE = 0x0100
RES_XML_END_NAMESPACE_TYPE = 0x0101
RES_XML_START_ELEMENT_TYPE = 0x0102
RES_XML_END_ELEMENT_TYPE = 0x0103
UTF8_FLAG = 0x00000100
TYPE_STRING = 0x03
TYPE_INT_DEC = 0x10
TYPE_INT_HEX = 0x11
TYPE_INT_BOOLEAN = 0x12
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


def _read_length8(data: bytes, offset: int) -> tuple[int, int]:
    first = data[offset]
    offset += 1
    if first & 0x80:
        return ((first & 0x7F) << 7) | data[offset], offset + 1
    return first, offset


def _read_length16(data: bytes, offset: int) -> tuple[int, int]:
    first = struct.unpack_from("<H", data, offset)[0]
    offset += 2
    if first & 0x8000:
        second = struct.unpack_from("<H", data, offset)[0]
        return ((first & 0x7FFF) << 16) | second, offset + 2
    return first, offset


def _binary_string_pool(data: bytes, chunk_offset: int) -> list[str]:
    (
        _chunk_type,
        header_size,
        chunk_size,
        string_count,
        _style_count,
        flags,
        strings_start,
        _styles_start,
    ) = struct.unpack_from("<HHI5I", data, chunk_offset)
    if header_size < 28 or chunk_size > len(data) - chunk_offset:
        raise ValueError("invalid Android string-pool chunk")
    offsets_start = chunk_offset + header_size
    strings_base = chunk_offset + strings_start
    offsets = [
        struct.unpack_from("<I", data, offsets_start + index * 4)[0]
        for index in range(string_count)
    ]
    decoded: list[str] = []
    for relative in offsets:
        start = strings_base + relative
        if flags & UTF8_FLAG:
            _utf16_length, cursor = _read_length8(data, start)
            byte_length, cursor = _read_length8(data, cursor)
            raw = data[cursor : cursor + byte_length]
            decoded.append(raw.decode("utf-8", errors="replace"))
        else:
            unit_length, cursor = _read_length16(data, start)
            raw = data[cursor : cursor + unit_length * 2]
            decoded.append(raw.decode("utf-16le", errors="replace"))
    return decoded


def _string_at(strings: list[str], index: int) -> str | None:
    if index < 0 or index >= len(strings):
        return None
    return strings[index]


def _typed_value(strings: list[str], raw_index: int, value_type: int, value: int) -> str:
    raw = _string_at(strings, raw_index)
    if raw is not None:
        return raw
    if value_type == TYPE_STRING:
        return _string_at(strings, value) or ""
    if value_type == TYPE_INT_BOOLEAN:
        return "true" if value else "false"
    if value_type == TYPE_INT_DEC:
        return str(value if value < 0x80000000 else value - 0x100000000)
    if value_type == TYPE_INT_HEX:
        return f"0x{value:08x}"
    return str(value)


def _binary_attribute(
    data: bytes, offset: int, strings: list[str]
) -> tuple[str, str]:
    namespace_index, name_index, raw_index = struct.unpack_from("<III", data, offset)
    _value_size, _res0, value_type, value = struct.unpack_from(
        "<HBBI", data, offset + 12
    )
    name = _string_at(strings, name_index) or "<unnamed>"
    namespace = _string_at(strings, namespace_index)
    key = f"{{{namespace}}}{name}" if namespace else name
    return key, _typed_value(strings, raw_index, value_type, value)


def _decode_binary_manifest(data: bytes) -> ElementTree.Element:
    """Decode the metadata-bearing subset of Android's binary XML format."""

    if len(data) < 8:
        raise ValueError("AndroidManifest.xml is too short")
    root_type, root_header_size, root_size = struct.unpack_from("<HHI", data, 0)
    if root_type != RES_XML_TYPE or root_header_size < 8 or root_size > len(data):
        raise ValueError("not an Android binary XML document")

    strings: list[str] | None = None
    element_root: ElementTree.Element | None = None
    stack: list[ElementTree.Element] = []
    offset = root_header_size
    while offset + 8 <= root_size:
        chunk_type, header_size, chunk_size = struct.unpack_from(
            "<HHI", data, offset
        )
        if (
            header_size < 8
            or chunk_size < header_size
            or offset + chunk_size > root_size
        ):
            raise ValueError("invalid Android XML chunk")
        if chunk_type == RES_STRING_POOL_TYPE:
            strings = _binary_string_pool(data, offset)
        elif chunk_type in {
            RES_XML_START_NAMESPACE_TYPE,
            RES_XML_END_NAMESPACE_TYPE,
        }:
            pass
        elif chunk_type == RES_XML_START_ELEMENT_TYPE:
            if strings is None or header_size < 16:
                raise ValueError("invalid Android XML element")
            extension = offset + header_size
            (
                _namespace_index,
                name_index,
                attribute_start,
                attribute_size,
                attribute_count,
                *_indexes,
            ) = struct.unpack_from("<ii6H", data, extension)
            if attribute_size < 20:
                raise ValueError("invalid Android XML attribute size")
            name = _string_at(strings, name_index) or "<unnamed>"
            element = ElementTree.Element(name)
            attributes_offset = extension + attribute_start
            for index in range(attribute_count):
                key, value = _binary_attribute(
                    data, attributes_offset + index * attribute_size, strings
                )
                element.set(key, value)
            if stack:
                stack[-1].append(element)
            else:
                element_root = element
            stack.append(element)
        elif chunk_type == RES_XML_END_ELEMENT_TYPE and stack:
            stack.pop()
        offset += chunk_size

    if element_root is None:
        raise ValueError("Android binary XML contains no root element")
    return element_root


def _read_manifest_bytes(path: Path) -> bytes:
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as archive:
            try:
                return archive.read("AndroidManifest.xml")
            except KeyError as exc:
                raise ValueError("APK does not contain AndroidManifest.xml") from exc
    return path.read_bytes()


def _manifest_root(path: Path) -> ElementTree.Element:
    data = _read_manifest_bytes(path)
    try:
        return ElementTree.fromstring(data)
    except ElementTree.ParseError:
        return _decode_binary_manifest(data)


def _inventory_manifest_root(root: ElementTree.Element) -> dict[str, Any]:
    """Return sanitized component and intent metadata from a manifest root."""

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


def inventory_manifest(path: Path) -> dict[str, Any]:
    """Read text XML, binary XML, or an exact APK's embedded manifest."""

    return _inventory_manifest_root(_manifest_root(path))


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
        description="Read-only Android manifest/APK/JADX surface inventory"
    )
    parser.add_argument(
        "manifest",
        type=Path,
        help="text/binary AndroidManifest.xml or an APK containing one",
    )
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
