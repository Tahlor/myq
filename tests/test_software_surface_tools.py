from __future__ import annotations

import io
from pathlib import Path

from tools.android_surface_inventory import (
    build_report,
    inventory_manifest,
    inventory_source_signals,
)
from tools.g0401_http_archaeology import (
    classify_route,
    extract_candidate_paths,
    extract_same_origin_assets,
    run_archaeology,
)


def test_android_surface_inventory_reports_components_and_signal_locations(tmp_path: Path):
    manifest = tmp_path / "AndroidManifest.xml"
    manifest.write_text(
        """<manifest xmlns:android="http://schemas.android.com/apk/res/android"
            package="com.example.app">
          <application>
            <activity android:name=".MainActivity" android:exported="true">
              <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
              </intent-filter>
            </activity>
            <service android:name=".ActionService" android:exported="false" />
          </application>
        </manifest>""",
        encoding="utf-8",
    )
    source = tmp_path / "sources"
    source.mkdir()
    source_file = source / "Actions.kt"
    source_file.write_text(
        """val intent = Intent(context, ActionService::class.java)
val pending = PendingIntent.getActivity(context, 0, intent, 0)
sendBroadcast(intent) // open door action
""",
        encoding="utf-8",
    )

    manifest_report = inventory_manifest(manifest)
    assert manifest_report["package"] == "com.example.app"
    components = {item["name"]: item for item in manifest_report["components"]}
    assert components[".ActionService"]["exported"] == "false"
    assert components[".MainActivity"]["intent_filters"][0]["actions"] == [
        "android.intent.action.MAIN"
    ]

    signals = inventory_source_signals(source)
    assert signals[0]["file"] == "Actions.kt"
    assert {signal for item in signals for signal in item["signals"]} >= {
        "pending_intent",
        "intent",
        "broadcast_dispatch",
        "operation_terms",
    }
    assert all("open door action" not in item for item in signals)
    assert build_report(manifest, source)["source_root"] == "sources"


class _FakeResponse:
    def __init__(self, url: str, body: bytes, content_type: str = "text/html"):
        self.status = 200
        self._url = url
        self._body = io.BytesIO(body)
        self.headers = {"Content-Type": content_type}

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, size: int = -1) -> bytes:
        return self._body.read(size)

    def getcode(self) -> int:
        return self.status

    def geturl(self) -> str:
        return self._url


def test_g0401_archaeology_is_bounded_to_get_and_same_origin_assets():
    calls: list[tuple[str, str]] = []

    def opener(request, timeout):
        calls.append((request.method, request.full_url))
        if request.full_url.endswith("/"):
            return _FakeResponse(
                request.full_url,
                b'<html><script src="/app.js"></script><script src="https://other/app.js"></script>'
                b'<a href="/jconfig_save?ssid=secret">save</a></html>',
            )
        if request.full_url.endswith("/app.js"):
            return _FakeResponse(
                request.full_url,
                b'const route = "/jscan_results"; const token = "secret";',
                "application/javascript",
            )
        return _FakeResponse(request.full_url, b"not found")

    report = run_archaeology(
        "http://192.0.2.1/",
        host_header="setup.myqdevice.com",
        routes=("/",),
        opener=opener,
    )

    assert calls == [
        ("GET", "http://192.0.2.1/"),
        ("GET", "http://192.0.2.1/app.js"),
    ]
    assert report["mutations_attempted"] is False
    assert report["same_origin_assets"][0]["path"] == "/app.js"
    assert "/jconfig_save" in report["candidate_paths"]
    assert "/jscan_results" in report["candidate_paths"]
    assert "secret" not in str(report)
    assert all(method == "GET" for method, _url in calls)


def test_g0401_path_extractors_strip_query_and_external_assets():
    assert extract_candidate_paths("/jconfig_save?ssid=secret /jabout") == [
        "/jabout",
        "/jconfig_save",
    ]
    assert extract_candidate_paths(
        '<div class="panel">http://example.invalid/ignored</div> /jabout'
    ) == ["/jabout"]
    assert extract_same_origin_assets(
        "http://192.0.2.1/", '<link href="/style.css"><script src="https://x/a.js">'
    ) == ["http://192.0.2.1/style.css"]


def test_g0401_archaeology_skips_routes_outside_the_read_only_dictionary():
    assert classify_route("/jabout") == "read-only"
    assert classify_route("/jconfig_save") == "provisioning-mutation"
    assert classify_route("/unknown") == "unknown"

    calls: list[str] = []

    def opener(request, timeout):
        calls.append(request.full_url)
        raise AssertionError("a skipped route must not be fetched")

    report = run_archaeology(
        "http://192.0.2.1/",
        routes=("/jconfig_save", "/unknown"),
        opener=opener,
    )

    assert calls == []
    assert [item["category"] for item in report["routes"]] == [
        "provisioning-mutation",
        "unknown",
    ]
    assert all(item["skipped"] for item in report["routes"])
    assert report["mutations_attempted"] is False
