from pathlib import Path

from tools.android_firmware_surface_audit import audit


def test_audit_finds_firmware_fields_routes_and_contextual_primitives(tmp_path: Path):
    dto = tmp_path / "device.smali"
    dto.write_text(
        """
.class public Lexample/device;
.field private firmware:Ljava/lang/String;
.method public final a()V
    const-string v0, "latest_available_firmware_version"
    const-string v1, "mandatory_update_status"
    invoke-virtual {p0}, Ljava/net/URL;->openConnection()Ljava/net/URLConnection;
.end method
""".strip()
        + "\n",
        encoding="utf-8",
    )

    api = tmp_path / "api.smali"
    api.write_text(
        """
.class public interface abstract Lexample/api;
.method public abstract a()Lretrofit2/b;
    .annotation runtime Lretrofit2/http/f;
        value = "/api/v6/firmware/manifest"
    .end annotation
.end method
""".strip()
        + "\n",
        encoding="utf-8",
    )

    report = audit(tmp_path)

    symbols = {item["symbol"] for item in report["target_refs"]}
    assert {"latest_available_firmware_version", "mandatory_update_status"} <= symbols
    assert report["retrofit_route_candidates"] == [
        {
            "path": "api.smali",
            "line": 4,
            "method": "public abstract a()Lretrofit2/b;",
            "annotation_kind": "f",
            "route": "/api/v6/firmware/manifest",
        }
    ]
    assert any(item["primitive"] == "Ljava/net/URL;" for item in report["download_primitive_refs"])
    assert report["network_requests_made"] is False
    assert report["android_components_invoked"] is False


def test_annotation_text_does_not_count_as_ota_route(tmp_path: Path):
    smali = tmp_path / "noise.smali"
    smali.write_text(
        """
.class public Lexample/noise;
.method public a()V
    const-string v0, "annotation metadata rotation"
    const-string v1, "firmware_version"
.end method
""".strip()
        + "\n",
        encoding="utf-8",
    )

    report = audit(tmp_path)

    assert report["summary"]["target_ref_count"] == 1
    assert report["retrofit_route_candidates"] == []
