import struct
import zipfile
from pathlib import Path

from tools.android_surface_inventory import (
    inventory_manifest,
    parse_manifest,
    scan_jadx_sources,
)


def _binary_manifest() -> bytes:
    strings = [
        "manifest",
        "application",
        "activity",
        "intent-filter",
        "action",
        "category",
        "com.example.myq",
        ".HomeTabsActivity",
        "android.intent.action.MAIN",
        "android.intent.category.LAUNCHER",
        "http://schemas.android.com/apk/res/android",
        "package",
        "name",
        "exported",
    ]
    string_bytes = bytearray()
    offsets = []
    for value in strings:
        offsets.append(len(string_bytes))
        encoded = value.encode("utf-8")
        string_bytes.extend((len(value), len(encoded)))
        string_bytes.extend(encoded)
        string_bytes.append(0)
    string_pool_header_size = 28
    string_pool_size = (
        string_pool_header_size + len(offsets) * 4 + len(string_bytes)
    )
    string_pool = struct.pack(
        "<HHI5I",
        0x0001,
        string_pool_header_size,
        string_pool_size,
        len(strings),
        0,
        0x00000100,
        string_pool_header_size + len(offsets) * 4,
        0,
    )
    string_pool += b"".join(struct.pack("<I", offset) for offset in offsets)
    string_pool += string_bytes

    android_ns = strings.index("http://schemas.android.com/apk/res/android")

    def start(name: str, attributes=()):
        attr_bytes = bytearray()
        for namespace, attr_name, raw, value_type, value in attributes:
            attr_bytes.extend(
                struct.pack(
                    "<IIIHBBI",
                    0xFFFFFFFF if namespace is None else strings.index(namespace),
                    strings.index(attr_name),
                    0xFFFFFFFF if raw is None else strings.index(raw),
                    8,
                    0,
                    value_type,
                    value,
                )
            )
        extension = struct.pack(
            "<ii6H",
            -1,
            strings.index(name),
            20,
            20,
            len(attributes),
            0,
            0,
            0,
        )
        size = 16 + len(extension) + len(attr_bytes)
        return struct.pack("<HHIii", 0x0102, 16, size, 1, -1) + extension + attr_bytes

    def end(name: str):
        return struct.pack(
            "<HHIii2i", 0x0103, 16, 24, 1, -1, -1, strings.index(name)
        )

    nodes = [
        start("manifest", ((None, "package", "com.example.myq", 0x03, 0),)),
        start("application"),
        start(
            "activity",
            (
                (strings[android_ns], "name", ".HomeTabsActivity", 0x03, 0),
                (strings[android_ns], "exported", None, 0x12, 1),
            ),
        ),
        start("intent-filter"),
        start(
            "action",
            (
                (
                    strings[android_ns],
                    "name",
                    "android.intent.action.MAIN",
                    0x03,
                    0,
                ),
            ),
        ),
        end("action"),
        start(
            "category",
            (
                (
                    strings[android_ns],
                    "name",
                    "android.intent.category.LAUNCHER",
                    0x03,
                    0,
                ),
            ),
        ),
        end("category"),
        end("intent-filter"),
        end("activity"),
        end("application"),
        end("manifest"),
    ]
    body = string_pool + b"".join(nodes)
    return struct.pack("<HHI", 0x0003, 8, 8 + len(body)) + body


def test_parse_manifest_resolves_components_and_intents(tmp_path: Path):
    manifest = tmp_path / "AndroidManifest.xml"
    manifest.write_text(
        """<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android"
    package="com.example.myq">
  <application>
    <activity android:name=".HomeTabsActivity" android:exported="true">
      <intent-filter>
        <action android:name="android.intent.action.MAIN"/>
        <category android:name="android.intent.category.LAUNCHER"/>
      </intent-filter>
    </activity>
    <service android:name="Bridge" android:permission="android.permission.BIND_SERVICE"
        android:exported="false"/>
    <receiver android:name="com.example.Receiver" android:exported="true"/>
  </application>
</manifest>
""",
        encoding="utf-8",
    )

    report = parse_manifest(manifest)

    assert report["package"] == "com.example.myq"
    assert report["component_counts"] == {
        "activity": 1,
        "receiver": 1,
        "service": 1,
    }
    activity = next(
        item for item in report["components"] if item["type"] == "activity"
    )
    assert activity["name"] == "com.example.myq.HomeTabsActivity"
    assert activity["exported"] == "true"
    assert activity["intent_filters"][0]["actions"] == [
        "android.intent.action.MAIN"
    ]


def test_inventory_manifest_reads_binary_xml_embedded_in_exact_apk(tmp_path: Path):
    apk = tmp_path / "exact.apk"
    with zipfile.ZipFile(apk, "w") as archive:
        archive.writestr("AndroidManifest.xml", _binary_manifest())

    report = inventory_manifest(apk)
    assert report["package"] == "com.example.myq"
    activity = next(
        item for item in report["components"] if item["type"] == "activity"
    )
    assert activity["name"] == ".HomeTabsActivity"
    assert activity["exported"] == "true"
    assert activity["intent_filters"][0]["actions"] == [
        "android.intent.action.MAIN"
    ]

    parsed = parse_manifest(apk)
    assert parsed["components"][0]["name"] == "com.example.myq.HomeTabsActivity"


def test_scan_jadx_sources_returns_locations_without_source_lines(tmp_path: Path):
    source = tmp_path / "Actions.kt"
    secret = "bearer-token-must-not-be-reported"
    source.write_text(
        f'fun send() {{ PendingIntent.getActivity(null, 0, intent, 0) }} // {secret}\n',
        encoding="utf-8",
    )

    report = scan_jadx_sources(tmp_path)
    assert report["action_call_site_matches"] == [
        {
            "file": "Actions.kt",
            "line": 1,
            "markers": ["PendingIntent"],
        }
    ]
    assert secret not in str(report)
