from pathlib import Path

from tools.android_surface_inventory import parse_manifest, scan_jadx_sources


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

