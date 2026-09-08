from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_notification_listener_is_package_scoped_and_read_only():
    service = _read(
        "android_bridge/app/src/main/java/com/tahlor/myqbridge/"
        "BridgeNotificationListenerService.kt"
    )
    assert "sbn.packageName != BridgeAccessibilityService.MYQ_PACKAGE" in service
    assert "NotificationStateStore.normalize" in service
    assert "NotificationStateStore.record" in service
    assert "performAction" not in service
    assert "command(" not in service
    assert "click" not in service.lower()


def test_notification_state_contract_is_advisory_metadata_only():
    store = _read(
        "android_bridge/app/src/main/java/com/tahlor/myqbridge/"
        "NotificationStateStore.kt"
    )
    bridge = _read(
        "android_bridge/app/src/main/java/com/tahlor/myqbridge/"
        "BridgeAccessibilityService.kt"
    )
    assert 'put("observed_at_ms"' in store
    assert 'put("stale"' in store
    assert "notification_state" in bridge
    assert "notification body" not in store.lower()
    assert "notification body" not in bridge.lower()


def test_manifest_declares_notification_listener_without_auto_enabling_it():
    manifest = _read("android_bridge/app/src/main/AndroidManifest.xml")
    assert "android.permission.BIND_NOTIFICATION_LISTENER_SERVICE" in manifest
    assert "android.service.notification.NotificationListenerService" in manifest
    assert "ACTION_NOTIFICATION_LISTENER_SETTINGS" not in manifest
