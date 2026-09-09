from pathlib import Path

from tools.android_sdk_surface_audit import build_report


def test_audit_separates_dashboard_navigation_from_transport_body(tmp_path: Path):
    root = tmp_path / "smali"
    dashboard = root / "com/chamberlain/myq/main/HomeTabsActivity.smali"
    transport = root / "myq/sdk/common/misc/communication/method/k.smali"
    api = root / "myq/sdk/external/api/device/DeviceApiImpl.smali"
    app_root = root / "com/chamberlain/myq"
    dashboard.parent.mkdir(parents=True)
    transport.parent.mkdir(parents=True)
    api.parent.mkdir(parents=True)
    dashboard.write_text(
        ".class public Lcom/chamberlain/myq/main/HomeTabsActivity;\n"
        "invoke-virtual {p0, v0}, Landroid/content/Context;->startActivity(Landroid/content/Intent;)V\n"
        "const-string v0, \"GATE_OPENED\"\n",
        encoding="utf-8",
    )
    transport.write_text(
        ".class public final Lmyq/sdk/common/misc/communication/method/k;\n"
        ".method public final l(Ljava/lang/String;Ljava/lang/String;Lcom/chamberlain/network/framework/model/vgdoservice/body/b;Lx;)V\n"
        "invoke-static {v0}, Lcom/chamberlain/network/framework/service/api/v6/devices/a$a;->h(Lx;)V\n"
        ".end method\n",
        encoding="utf-8",
    )
    api.write_text(
        ".class public final Lmyq/sdk/external/api/device/DeviceApiImpl;\n"
        ".method public p(Lmyq/sdk/data/model/devices/k;)V\n"
        "const-string v0, \"DeviceInteraction\"\n"
        ".end method\n",
        encoding="utf-8",
    )

    report = build_report(root, app_root=app_root)

    assert report["dashboard"]["signals"]["start_activity_line_count"] == 1
    assert report["dashboard"]["direct_operation_invocation_signal"] is False
    assert report["dashboard"]["signals"]["shortcut_or_widget_line_count"] == 0
    assert report["v6_transport"]["vgdo_service_body_method_names"] == ["l"]
    assert report["v6_transport"]["v6_service_dispatch_line_count"] == 1
    assert report["device_api_wrapper"]["device_interaction_reference_line_count"] == 1
    assert report["state_changing_actions_attempted"] is False
    assert "internal transport surface" in report["conclusion"]


def test_audit_does_not_copy_source_payloads(tmp_path: Path):
    root = tmp_path / "smali"
    path = root / "myq/sdk/common/misc/communication/method/k.smali"
    path.parent.mkdir(parents=True)
    secret = "bearer-token-and-device-serial"
    path.write_text(
        f".class public final Lmyq/sdk/common/misc/communication/method/k; // {secret}\n",
        encoding="utf-8",
    )

    report = build_report(root)

    assert secret not in str(report)
