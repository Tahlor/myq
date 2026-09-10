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


def test_session_round_trip_pins_exact_profile():
    from myq_bridge.cloud import CloudSession

    session = CloudSession(
        "access", "refresh",
        client_id=ANDROID_2026_09.client_id,
        app_version=ANDROID_2026_09.app_version,
        user_agent=ANDROID_2026_09.user_agent,
        profile_name=ANDROID_2026_09.name,
    )
    raw = session.to_dict()
    assert raw["profile_name"] == ANDROID_2026_09.name
    restored = CloudSession.from_dict(raw)
    assert restored.profile is ANDROID_2026_09
    assert restored.profile_name == ANDROID_2026_09.name


def test_legacy_session_migrates_to_unique_profile():
    from myq_bridge.cloud import CloudSession

    restored = CloudSession.from_dict({
        "access_token": "access", "refresh_token": "refresh",
        "client_id": ANDROID_2026_09.client_id,
        "app_version": ANDROID_2026_09.app_version,
    })
    assert restored.profile_name == ANDROID_2026_09.name


def test_unknown_or_mismatched_profile_fails_closed():
    import pytest
    from myq_bridge.cloud import CloudSession

    unknown = CloudSession("a", "r", profile_name="missing-profile")
    with pytest.raises(ValueError, match="Unknown MyQ protocol profile"):
        _ = unknown.profile

    mismatched = CloudSession(
        "a", "r",
        client_id="IOS_CGI_MYQ",
        profile_name=ANDROID_2026_09.name,
    )
    with pytest.raises(ValueError, match="expects client_id"):
        _ = mismatched.profile


def test_cloud_health_surfaces_pinned_profile(monkeypatch):
    from fastapi.testclient import TestClient
    from myq_bridge import cloud_cli
    from myq_bridge.cloud import CloudSession

    class FakeClient:
        session = CloudSession(
            "access", "refresh",
            client_id=ANDROID_2026_09.client_id,
            app_version=ANDROID_2026_09.app_version,
            profile_name=ANDROID_2026_09.name,
        )

        def close(self):
            pass

    monkeypatch.setattr(cloud_cli, "_client", lambda: FakeClient())
    with TestClient(cloud_cli.create_app("local-api-key-1234")) as web:
        payload = web.get("/health").json()
    assert payload["protocol_profile"] == ANDROID_2026_09.name
