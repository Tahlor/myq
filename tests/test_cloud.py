from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx
import pytest

import myq_bridge.cloud_cli as cloud_cli
from myq_bridge.cloud import (
    ANDROID_CLIENT_ID,
    ANDROID_DEVICES_URL,
    ACCOUNTS_URL,
    AUTH_URL,
    DEVICES_URL,
    DOOR_ACTION_URL,
    CloudSession,
    MyQAuthError,
    MyQCloudError,
    MyQCloudClient,
    SessionStore,
)
from myq_bridge.cloud_cli import select_door


def test_refresh_rotates_and_persists_session(tmp_path: Path):
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert str(request.url) == AUTH_URL
        body = request.content.decode()
        assert "grant_type=refresh_token" in body
        assert "client_id=IOS_CGI_MYQ" in body
        return httpx.Response(
            200,
            json={"access_token": "new-access", "refresh_token": "new-refresh"},
        )

    store = SessionStore(tmp_path / "session.json")
    initial = CloudSession("old-access", "old-refresh")
    client = MyQCloudClient(
        initial,
        transport=httpx.MockTransport(handler),
        on_session_updated=store.save,
    )
    try:
        refreshed = client.refresh()
    finally:
        client.close()

    assert refreshed.access_token == "new-access"
    assert refreshed.refresh_token == "new-refresh"
    assert store.load() == refreshed
    assert len(requests) == 1


def test_refresh_keeps_existing_refresh_token_when_not_rotated():
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == AUTH_URL
        return httpx.Response(200, json={"access_token": "new-access"})

    client = MyQCloudClient(
        CloudSession("old-access", "old-refresh"),
        transport=httpx.MockTransport(handler),
    )
    try:
        refreshed = client.refresh()
    finally:
        client.close()

    assert refreshed.access_token == "new-access"
    assert refreshed.refresh_token == "old-refresh"


def test_401_refreshes_then_retries_account_request():
    account_calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal account_calls
        if str(request.url) == ACCOUNTS_URL:
            account_calls += 1
            if account_calls == 1:
                assert request.headers["authorization"] == "Bearer expired"
                return httpx.Response(401)
            assert request.headers["authorization"] == "Bearer fresh"
            return httpx.Response(200, json={"accounts": [{"id": "acct-1"}]})
        if str(request.url) == AUTH_URL:
            return httpx.Response(
                200,
                json={"access_token": "fresh", "refresh_token": "rotated"},
            )
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    client = MyQCloudClient(
        CloudSession("expired", "refresh"),
        transport=httpx.MockTransport(handler),
    )
    try:
        assert client.accounts() == [{"id": "acct-1"}]
    finally:
        client.close()
    assert account_calls == 2


def test_mutation_401_is_not_replayed_after_refresh():
    calls: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, str(request.url)))
        if request.method == "PUT":
            return httpx.Response(401)
        raise AssertionError("A mutating 401 must not trigger token refresh")

    client = MyQCloudClient(
        CloudSession("expired", "refresh"),
        transport=httpx.MockTransport(handler),
    )
    try:
        with pytest.raises(MyQAuthError, match="automatic replay was refused"):
            client.door_action("acct", "door", "close")
    finally:
        client.close()

    assert calls == [
        (
            "PUT",
            DOOR_ACTION_URL.format(account_id="acct", door_opener_id="door", action="close"),
        )
    ]


def test_device_and_explicit_action_paths_are_current_v6_shapes():
    seen: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((request.method, str(request.url)))
        if request.method == "GET":
            return httpx.Response(200, json={"items": [{"device_family": "garagedoor"}]})
        return httpx.Response(202)

    client = MyQCloudClient(
        CloudSession("access", "refresh"),
        transport=httpx.MockTransport(handler),
    )
    try:
        assert client.devices("acct") == [{"device_family": "garagedoor"}]
        client.door_action("acct", "door", "open")
        client.door_action("acct", "door", "close")
    finally:
        client.close()

    assert seen == [
        ("GET", DEVICES_URL.format(account_id="acct")),
        (
            "PUT",
            DOOR_ACTION_URL.format(
                account_id="acct", door_opener_id="door", action="open"
            ),
        ),
        (
            "PUT",
            DOOR_ACTION_URL.format(
                account_id="acct", door_opener_id="door", action="close"
            ),
        ),
    ]


def test_door_command_verifies_observed_state_before_and_after_action():
    seen: list[tuple[str, str]] = []
    states = iter(["closed", "open"])

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((request.method, str(request.url)))
        if str(request.url) == ACCOUNTS_URL:
            return httpx.Response(200, json={"accounts": [{"id": "acct"}]})
        if str(request.url) == DEVICES_URL.format(account_id="acct"):
            return httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "serial_number": "door-1",
                            "device_family": "garagedoor",
                            "state": {"door_state": next(states), "online": True},
                        }
                    ]
                },
            )
        if str(request.url) == DOOR_ACTION_URL.format(
            account_id="acct", door_opener_id="door-1", action="open"
        ):
            assert request.method == "PUT"
            return httpx.Response(202)
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    client = MyQCloudClient(
        CloudSession("access", "refresh"),
        transport=httpx.MockTransport(handler),
    )
    try:
        result = client.door_command(
            "acct", "door-1", "open", verify_timeout=1, poll_interval=0
        )
    finally:
        client.close()

    assert result == {
        "ok": True,
        "changed": True,
        "action": "open",
        "account_id": "acct",
        "door_opener_id": "door-1",
        "before": "closed",
        "after": "open",
    }
    assert seen == [
        ("GET", ACCOUNTS_URL),
        ("GET", DEVICES_URL.format(account_id="acct")),
        (
            "PUT",
            DOOR_ACTION_URL.format(
                account_id="acct", door_opener_id="door-1", action="open"
            ),
        ),
        ("GET", ACCOUNTS_URL),
        ("GET", DEVICES_URL.format(account_id="acct")),
    ]


def test_door_preflight_is_read_only_and_reports_action_plan():
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.method)
        if str(request.url) == ACCOUNTS_URL:
            return httpx.Response(200, json={"accounts": [{"id": "acct"}]})
        if str(request.url) == DEVICES_URL.format(account_id="acct"):
            return httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "serial_number": "door-1",
                            "device_family": "garagedoor",
                            "state": {"door_state": "closed", "online": True},
                        }
                    ]
                },
            )
        raise AssertionError(f"Unexpected mutation: {request.method} {request.url}")

    client = MyQCloudClient(
        CloudSession("access", "refresh"),
        transport=httpx.MockTransport(handler),
    )
    try:
        plan = client.door_preflight("acct", "door-1", "open")
    finally:
        client.close()

    assert plan == {
        "ready": True,
        "changed": True,
        "action": "open",
        "account_id": "acct",
        "door_opener_id": "door-1",
        "before": "closed",
        "desired": "open",
        "online": True,
        "reason": None,
    }
    assert seen == ["GET", "GET"]


def test_door_command_noops_when_requested_state_is_already_observed():
    seen: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((request.method, str(request.url)))
        if str(request.url) == ACCOUNTS_URL:
            return httpx.Response(200, json={"accounts": [{"id": "acct"}]})
        if str(request.url) == DEVICES_URL.format(account_id="acct"):
            return httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "serial_number": "door-1",
                            "device_family": "garagedoor",
                            "state": {"door_state": "closed", "online": True},
                        }
                    ]
                },
            )
        raise AssertionError(f"Unexpected mutation: {request.method} {request.url}")

    client = MyQCloudClient(
        CloudSession("access", "refresh"),
        transport=httpx.MockTransport(handler),
    )
    try:
        result = client.door_command(
            "acct", "door-1", "close", verify_timeout=1, poll_interval=0
        )
    finally:
        client.close()

    assert result["ok"] is True
    assert result["changed"] is False
    assert result["before"] == result["after"] == "closed"
    assert all(method == "GET" for method, _url in seen)


def test_door_command_refuses_unknown_or_transitional_state_before_mutation():
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.method)
        if str(request.url) == ACCOUNTS_URL:
            return httpx.Response(200, json={"accounts": [{"id": "acct"}]})
        if str(request.url) == DEVICES_URL.format(account_id="acct"):
            return httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "serial_number": "door-1",
                            "device_family": "garagedoor",
                            "state": {"door_state": "opening", "online": True},
                        }
                    ]
                },
            )
        raise AssertionError(f"Unexpected mutation: {request.method} {request.url}")

    client = MyQCloudClient(
        CloudSession("access", "refresh"),
        transport=httpx.MockTransport(handler),
    )
    try:
        with pytest.raises(MyQCloudError, match="Refusing close"):
            client.door_command("acct", "door-1", "close")
    finally:
        client.close()

    assert seen == ["GET", "GET"]


def test_door_command_refuses_unconfirmed_online_state_before_mutation():
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.method)
        if str(request.url) == ACCOUNTS_URL:
            return httpx.Response(200, json={"accounts": [{"id": "acct"}]})
        if str(request.url) == DEVICES_URL.format(account_id="acct"):
            return httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "serial_number": "door-1",
                            "device_family": "garagedoor",
                            "state": {"door_state": "closed"},
                        }
                    ]
                },
            )
        raise AssertionError(f"Unexpected mutation: {request.method} {request.url}")

    client = MyQCloudClient(
        CloudSession("access", "refresh"),
        transport=httpx.MockTransport(handler),
    )
    try:
        with pytest.raises(MyQCloudError, match="online state is not confirmed"):
            client.door_command("acct", "door-1", "open")
    finally:
        client.close()

    assert seen == ["GET", "GET"]


def test_door_command_fails_closed_when_post_state_is_not_verified():
    seen: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((request.method, str(request.url)))
        if str(request.url) == ACCOUNTS_URL:
            return httpx.Response(200, json={"accounts": [{"id": "acct"}]})
        if str(request.url) == DEVICES_URL.format(account_id="acct"):
            return httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "serial_number": "door-1",
                            "device_family": "garagedoor",
                            "state": {"door_state": "closed", "online": True},
                        }
                    ]
                },
            )
        if str(request.url) == DOOR_ACTION_URL.format(
            account_id="acct", door_opener_id="door-1", action="open"
        ):
            return httpx.Response(202)
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    client = MyQCloudClient(
        CloudSession("access", "refresh"),
        transport=httpx.MockTransport(handler),
    )
    try:
        with pytest.raises(MyQCloudError, match="did not verify"):
            client.door_command(
                "acct", "door-1", "open", verify_timeout=0, poll_interval=0
            )
    finally:
        client.close()

    assert seen == [
        ("GET", ACCOUNTS_URL),
        ("GET", DEVICES_URL.format(account_id="acct")),
        (
            "PUT",
            DOOR_ACTION_URL.format(
                account_id="acct", door_opener_id="door-1", action="open"
            ),
        ),
    ]


def test_android_session_prefers_the_apk_device_route_and_headers():
    seen: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((request.method, str(request.url)))
        assert request.headers["myqapplicationid"]
        assert request.headers["culture"] == "en"
        assert request.headers["brandid"] == "1"
        assert request.headers["apiversion"] == "4.1"
        return httpx.Response(200, json={"items": [{"device_family": "garagedoor"}]})

    client = MyQCloudClient(
        CloudSession("access", "refresh", client_id=ANDROID_CLIENT_ID),
        transport=httpx.MockTransport(handler),
    )
    try:
        assert client.devices("acct") == [{"device_family": "garagedoor"}]
    finally:
        client.close()

    assert seen == [
        ("GET", ANDROID_DEVICES_URL.format(account_id="acct")),
    ]


def test_android_device_route_falls_back_to_direct_v6_2_route():
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        if str(request.url) == ANDROID_DEVICES_URL.format(account_id="acct"):
            return httpx.Response(404)
        return httpx.Response(200, json={"items": [{"device_family": "garagedoor"}]})

    client = MyQCloudClient(
        CloudSession("access", "refresh", client_id=ANDROID_CLIENT_ID),
        transport=httpx.MockTransport(handler),
    )
    try:
        assert client.devices("acct") == [{"device_family": "garagedoor"}]
    finally:
        client.close()

    assert seen == [
        ANDROID_DEVICES_URL.format(account_id="acct"),
        DEVICES_URL.format(account_id="acct"),
    ]


def test_door_status_normalizes_only_garage_devices():
    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == ACCOUNTS_URL:
            return httpx.Response(200, json={"accounts": [{"id": "acct"}]})
        if str(request.url) == DEVICES_URL.format(account_id="acct"):
            return httpx.Response(
                200,
                json={
                    "items": [
                        {
                            "serial_number": "door-1",
                            "account_id": "acct",
                            "device_family": "garagedoor",
                            "name": "Main Garage",
                            "device_model": "wifigaragedooropener",
                            "state": {
                                "door_state": "closed",
                                "online": True,
                                "absolute_cycle_count": 123,
                            },
                        },
                        {
                            "serial_number": "light-1",
                            "device_family": "lamp",
                            "state": {"online": True},
                        },
                    ]
                },
            )
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    client = MyQCloudClient(
        CloudSession("access", "refresh"),
        transport=httpx.MockTransport(handler),
    )
    try:
        assert client.door_status() == [
            {
                "account_id": "acct",
                "door_opener_id": "door-1",
                "name": "Main Garage",
                "model": "wifigaragedooropener",
                "door_state": "closed",
                "online": True,
                "last_update": None,
                "service_cycle_count": None,
                "absolute_cycle_count": 123,
                "battery_backup_voltage": None,
                "battery_backup_state": None,
                "attached_worklight_on": None,
            }
        ]
    finally:
        client.close()


def test_select_door_uses_only_door_without_configuration():
    door = {"door_opener_id": "one", "name": "Main Garage"}
    assert select_door([door]) is door


def test_select_door_requires_configuration_when_multiple_doors_exist():
    doors = [
        {"door_opener_id": "one", "name": "Main Garage"},
        {"door_opener_id": "two", "name": "Shop"},
    ]
    with pytest.raises(ValueError, match="Multiple garage doors"):
        select_door(doors)
    assert select_door(doors, door_name="main garage") is doors[0]
    assert select_door(doors, door_id="two") is doors[1]


def test_select_door_rejects_stale_configuration():
    doors = [{"door_opener_id": "one", "name": "Main Garage"}]
    with pytest.raises(ValueError, match="MYQ_DOOR_ID"):
        select_door(doors, door_id="missing")
    with pytest.raises(ValueError, match="MYQ_DOOR_NAME"):
        select_door(doors, door_name="Missing Garage")


def test_session_store_accepts_legacy_jwt_key(tmp_path: Path):
    path = tmp_path / "session.json"
    path.write_text(
        json.dumps({"jwt": "access", "refresh_token": "refresh"}),
        encoding="utf-8",
    )
    loaded = SessionStore(path).load()
    assert loaded is not None
    assert loaded.access_token == "access"
    assert loaded.refresh_token == "refresh"


def test_account_scoped_cloud_status_endpoint(monkeypatch):
    class FakeClient:
        def close(self):
            pass

        def door_status(self, account_id=None):
            return [{"account_id": account_id, "door_state": "closed"}]

    monkeypatch.setattr(cloud_cli, "_client", lambda: FakeClient())
    app = cloud_cli.create_app("local-api-key-1234")

    with TestClient(app) as web:
        response = web.get(
            "/accounts/acct-1/status",
            headers={"X-API-Key": "local-api-key-1234"},
        )

    assert response.status_code == 200
    assert response.json() == {
        "backend": "direct-cloud",
        "account_id": "acct-1",
        "doors": [{"account_id": "acct-1", "door_state": "closed"}],
    }


def test_cloud_command_endpoint_uses_verified_command_result(monkeypatch):
    calls: list[tuple[str, str, str]] = []

    class FakeClient:
        def close(self):
            pass

        def door_command(self, account_id, door_opener_id, action):
            calls.append((account_id, door_opener_id, action))
            return {
                "ok": True,
                "changed": True,
                "action": action,
                "account_id": account_id,
                "door_opener_id": door_opener_id,
                "before": "open",
                "after": "closed",
            }

    monkeypatch.setattr(cloud_cli, "_client", lambda: FakeClient())
    app = cloud_cli.create_app("local-api-key-1234")

    with TestClient(app) as web:
        response = web.post(
            "/accounts/acct-1/doors/door-1/close",
            headers={
                "X-API-Key": "local-api-key-1234",
                "X-MyQ-Confirm": "close",
            },
        )

    assert response.status_code == 200
    assert response.json()["before"] == "open"
    assert response.json()["after"] == "closed"
    assert calls == [("acct-1", "door-1", "close")]


def test_cloud_command_endpoint_requires_action_specific_confirmation(monkeypatch):
    calls: list[tuple[str, str, str]] = []

    class FakeClient:
        def close(self):
            pass

        def door_command(self, account_id, door_opener_id, action):
            calls.append((account_id, door_opener_id, action))
            raise AssertionError("confirmation must be checked before the client call")

    monkeypatch.setattr(cloud_cli, "_client", lambda: FakeClient())
    app = cloud_cli.create_app("local-api-key-1234")

    with TestClient(app) as web:
        response = web.post(
            "/accounts/acct-1/doors/door-1/open",
            headers={"X-API-Key": "local-api-key-1234"},
        )

    assert response.status_code == 428
    assert response.json()["detail"] == "Set X-MyQ-Confirm: open to authorize this command"
    assert calls == []


def test_cloud_command_endpoint_rejects_confirmation_for_different_action(monkeypatch):
    class FakeClient:
        def close(self):
            pass

        def door_command(self, *_args):
            raise AssertionError("confirmation must be checked before the client call")

    monkeypatch.setattr(cloud_cli, "_client", lambda: FakeClient())
    app = cloud_cli.create_app("local-api-key-1234")

    with TestClient(app) as web:
        response = web.post(
            "/accounts/acct-1/doors/door-1/open",
            headers={
                "X-API-Key": "local-api-key-1234",
                "X-MyQ-Confirm": "close",
            },
        )

    assert response.status_code == 428
    assert response.json()["detail"] == "Set X-MyQ-Confirm: open to authorize this command"


def test_cloud_cli_requires_confirmation_flag_before_loading_session(monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        ["myq-cloud", "open", "acct-1", "door-1"],
    )

    with pytest.raises(SystemExit) as exc_info:
        cloud_cli.main()

    assert exc_info.value.code == 2


def test_cloud_preflight_endpoint_is_read_only(monkeypatch):
    calls: list[tuple[str, str, str]] = []

    class FakeClient:
        def close(self):
            pass

        def door_preflight(self, account_id, door_opener_id, action):
            calls.append((account_id, door_opener_id, action))
            return {
                "ready": True,
                "changed": True,
                "action": action,
                "account_id": account_id,
                "door_opener_id": door_opener_id,
                "before": "closed",
                "desired": "open",
                "online": True,
                "reason": None,
            }

    monkeypatch.setattr(cloud_cli, "_client", lambda: FakeClient())
    app = cloud_cli.create_app("local-api-key-1234")

    with TestClient(app) as web:
        response = web.get(
            "/accounts/acct-1/doors/door-1/preflight/open",
            headers={"X-API-Key": "local-api-key-1234"},
        )

    assert response.status_code == 200
    assert response.json()["ready"] is True
    assert calls == [("acct-1", "door-1", "open")]
