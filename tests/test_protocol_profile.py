from pathlib import Path

from myq_bridge.cloud import (
    ANDROID_APPLICATION_ID,
    ANDROID_CLIENT_ID,
    ANDROID_DEVICES_URL,
    AUTH_URL,
)
from myq_bridge.protocol_profile import ANDROID_2026_09, PROFILES
from tools.audit_protocol_profile import audit


def test_cloud_public_constants_come_from_versioned_profile():
    assert ANDROID_CLIENT_ID == ANDROID_2026_09.client_id
    assert ANDROID_APPLICATION_ID == ANDROID_2026_09.application_id
    assert ANDROID_DEVICES_URL == ANDROID_2026_09.device_urls[0]
    assert AUTH_URL == ANDROID_2026_09.token_url
    assert PROFILES[ANDROID_2026_09.name] is ANDROID_2026_09


def test_profile_audit_reports_known_public_markers_without_generic_secrets(tmp_path: Path):
    profile = ANDROID_2026_09
    text = "\n".join(
        [
            profile.client_id,
            profile.scope or "",
            profile.redirect_uri or "",
            "MyQApplicationId " + (profile.application_id or ""),
            profile.authorization_url,
            profile.accounts_url,
            profile.device_urls[0],
            profile.door_action_url,
            "password=DO_NOT_SURFACE_THIS",
            "Bearer DO_NOT_SURFACE_THIS_EITHER",
        ]
    )
    (tmp_path / "sample.smali").write_text(text, encoding="utf-8")
    result = audit([tmp_path])
    assert result["drift_detected"] is False
    rendered = str(result)
    assert "DO_NOT_SURFACE_THIS" not in rendered
    assert profile.client_id in rendered


def test_profile_audit_flags_missing_expected_markers(tmp_path: Path):
    (tmp_path / "candidate.smali").write_text(
        "NEWANDROID_CGI_MYQ https://devices.myq-cloud.com com.changed://android",
        encoding="utf-8",
    )
    result = audit([tmp_path])
    assert result["drift_detected"] is True
    assert "client_id" in result["missing_markers"]
    assert "NEWANDROID_CGI_MYQ" in result["candidate_public_values"]["client_ids"]


def test_profile_audit_does_not_require_runtime_only_application_id(tmp_path: Path):
    profile = ANDROID_2026_09
    text = "\n".join(
        [
            profile.client_id,
            profile.scope or "",
            profile.redirect_uri or "",
            profile.authorization_url,
            profile.accounts_url,
            profile.device_urls[0],
            profile.door_action_url,
        ]
    )
    (tmp_path / "known-good.smali").write_text(text, encoding="utf-8")
    result = audit([tmp_path])
    assert result["drift_detected"] is False
    assert "application_id" in result["unattested_runtime_markers"]
