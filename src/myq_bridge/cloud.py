from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Callable

import httpx


DEFAULT_CLIENT_ID = "IOS_CGI_MYQ"
DEFAULT_APP_VERSION = "5.315.0.66076"
DEFAULT_USER_AGENT = "myQ/315.0.66076 CFNetwork/3860.700.1 Darwin/25.6.0"

AUTH_URL = "https://partner-identity.myq-cloud.com/connect/token"
ACCOUNTS_URL = "https://accounts.myq-cloud.com/api/v6.0/accounts"
DEVICES_URL = "https://devices.myq-cloud.com/api/v6.2/Accounts/{account_id}/Devices"
DOOR_ACTION_URL = (
    "https://account-devices-gdo.myq-cloud.com/api/v6.0/Accounts/"
    "{account_id}/door_openers/{door_opener_id}/{action}"
)
LOCKMODE_URL = (
    "https://account-devices-gdo.myq-cloud.com/api/v6.0/accounts/"
    "{account_id}/door_openers/{door_opener_id}/lockmode"
)


class MyQCloudError(RuntimeError):
    pass


class MyQAuthError(MyQCloudError):
    pass


@dataclass(frozen=True)
class CloudSession:
    access_token: str
    refresh_token: str
    client_id: str = DEFAULT_CLIENT_ID
    app_version: str = DEFAULT_APP_VERSION
    user_agent: str = DEFAULT_USER_AGENT

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "CloudSession":
        access = str(raw.get("access_token") or raw.get("jwt") or "").strip()
        refresh = str(raw.get("refresh_token") or "").strip()
        if not access or not refresh:
            raise ValueError("Cloud session requires access_token/jwt and refresh_token")
        return cls(
            access_token=access,
            refresh_token=refresh,
            client_id=str(raw.get("client_id") or DEFAULT_CLIENT_ID),
            app_version=str(raw.get("app_version") or DEFAULT_APP_VERSION),
            user_agent=str(raw.get("user_agent") or DEFAULT_USER_AGENT),
        )

    def to_dict(self) -> dict[str, str]:
        return {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "client_id": self.client_id,
            "app_version": self.app_version,
            "user_agent": self.user_agent,
        }


class SessionStore:
    """Small local credential store for rotating MyQ OAuth tokens."""

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def load(self) -> CloudSession | None:
        if not self.path.exists():
            return None
        return CloudSession.from_dict(json.loads(self.path.read_text(encoding="utf-8")))

    def save(self, session: CloudSession) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(prefix=f".{self.path.name}.", dir=self.path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(session.to_dict(), handle, indent=2)
                handle.write("\n")
            try:
                os.chmod(temp_name, 0o600)
            except OSError:
                pass
            os.replace(temp_name, self.path)
            try:
                os.chmod(self.path, 0o600)
            except OSError:
                pass
        finally:
            try:
                os.unlink(temp_name)
            except FileNotFoundError:
                pass


def load_cloud_session(store: SessionStore | None = None) -> CloudSession:
    if store is not None:
        saved = store.load()
        if saved is not None:
            return saved

    access = os.environ.get("MYQ_ACCESS_TOKEN") or os.environ.get("MYQ_JWT")
    refresh = os.environ.get("MYQ_REFRESH_TOKEN")
    if not access or not refresh:
        raise RuntimeError(
            "No MyQ cloud session found. Set MYQ_ACCESS_TOKEN/MYQ_JWT and "
            "MYQ_REFRESH_TOKEN, or provide config/cloud_session.json."
        )
    return CloudSession(
        access_token=access,
        refresh_token=refresh,
        client_id=os.environ.get("MYQ_CLIENT_ID", DEFAULT_CLIENT_ID),
        app_version=os.environ.get("MYQ_APP_VERSION", DEFAULT_APP_VERSION),
        user_agent=os.environ.get("MYQ_USER_AGENT", DEFAULT_USER_AGENT),
    )


class MyQCloudClient:
    """Direct client for the MyQ v6 surface observed in August 2026.

    Authentication bootstrap is intentionally separate: this client consumes an
    already-authorized session, refreshes it through the normal OAuth grant, and
    performs account/device/door operations.
    """

    def __init__(
        self,
        session: CloudSession,
        *,
        transport: httpx.BaseTransport | None = None,
        on_session_updated: Callable[[CloudSession], None] | None = None,
        timeout: float = 20.0,
    ):
        self.session = session
        self.on_session_updated = on_session_updated
        self._client = httpx.Client(transport=transport, timeout=timeout, follow_redirects=True)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "MyQCloudClient":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    @property
    def headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.session.access_token}",
            "App-Version": self.session.app_version,
            "User-Agent": self.session.user_agent,
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.9",
        }

    def refresh(self) -> CloudSession:
        response = self._client.post(
            AUTH_URL,
            headers={
                **self.headers,
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={
                "client_id": self.session.client_id,
                "refresh_token": self.session.refresh_token,
                "grant_type": "refresh_token",
            },
        )
        if response.status_code in (400, 401):
            raise MyQAuthError(f"MyQ token refresh rejected ({response.status_code})")
        self._raise(response, "token refresh")
        payload = response.json()
        access = payload.get("access_token")
        refresh = payload.get("refresh_token")
        if not access or not refresh:
            raise MyQAuthError("MyQ token refresh response omitted access/refresh token")
        self.session = replace(
            self.session,
            access_token=str(access),
            refresh_token=str(refresh),
        )
        if self.on_session_updated is not None:
            self.on_session_updated(self.session)
        return self.session

    def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        response = self._client.request(method, url, headers=self.headers, **kwargs)
        if response.status_code == 401:
            self.refresh()
            response = self._client.request(method, url, headers=self.headers, **kwargs)
        if response.status_code == 401:
            raise MyQAuthError("MyQ request remained unauthorized after refresh")
        return response

    def accounts(self) -> list[dict[str, Any]]:
        response = self.request("GET", ACCOUNTS_URL)
        self._raise(response, "fetch accounts")
        payload = response.json()
        return list(payload.get("accounts") or [])

    def devices(self, account_id: str) -> list[dict[str, Any]]:
        response = self.request("GET", DEVICES_URL.format(account_id=account_id))
        self._raise(response, "fetch devices")
        payload = response.json()
        return list(payload.get("items") or [])

    def door_status(self) -> list[dict[str, Any]]:
        """Return a compact automation-friendly summary of every garage door."""
        doors: list[dict[str, Any]] = []
        for account in self.accounts():
            account_id = str(account.get("id") or "")
            if not account_id:
                continue
            for device in self.devices(account_id):
                state = device.get("state") or {}
                if not isinstance(state, dict):
                    state = {}
                if device.get("device_family") != "garagedoor" and "door_state" not in state:
                    continue
                opener_id = str(device.get("serial_number") or device.get("id") or "")
                if not opener_id:
                    continue
                doors.append(
                    {
                        "account_id": str(device.get("account_id") or account_id),
                        "door_opener_id": opener_id,
                        "name": device.get("name") or "Garage Door",
                        "model": device.get("device_model"),
                        "door_state": state.get("door_state"),
                        "online": state.get("online"),
                        "last_update": state.get("last_update"),
                        "service_cycle_count": state.get("service_cycle_count"),
                        "absolute_cycle_count": state.get("absolute_cycle_count"),
                        "battery_backup_voltage": state.get("battery_backup_voltage"),
                        "battery_backup_state": state.get("battery_backup_state"),
                        "attached_worklight_on": state.get("attached_worklight_on"),
                    }
                )
        return doors

    def door_action(self, account_id: str, door_opener_id: str, action: str) -> None:
        if action not in {"open", "close"}:
            raise ValueError("action must be 'open' or 'close'")
        response = self.request(
            "PUT",
            DOOR_ACTION_URL.format(
                account_id=account_id,
                door_opener_id=door_opener_id,
                action=action,
            ),
            content=b"",
        )
        if response.status_code not in (200, 202):
            self._raise(response, f"{action} door")

    def set_lock_mode(
        self, account_id: str, door_opener_id: str, enabled: bool
    ) -> None:
        response = self.request(
            "PUT",
            LOCKMODE_URL.format(
                account_id=account_id,
                door_opener_id=door_opener_id,
            ),
            json={"enable_lock_mode": bool(enabled)},
        )
        if response.status_code not in (200, 202):
            self._raise(response, "set lock mode")

    @staticmethod
    def _raise(response: httpx.Response, operation: str) -> None:
        if response.is_success:
            return
        body = response.text[:500]
        raise MyQCloudError(f"MyQ {operation} failed ({response.status_code}): {body}")
