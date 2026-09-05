from __future__ import annotations

import json
from pathlib import Path

import httpx

from myq_bridge.cloud import (
    ACCOUNTS_URL,
    AUTH_URL,
    DEVICES_URL,
    DOOR_ACTION_URL,
    CloudSession,
    MyQCloudClient,
    SessionStore,
)


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
