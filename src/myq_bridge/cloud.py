from __future__ import annotations

import json
import os
import tempfile
import threading
import time
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Callable

import httpx


DEFAULT_CLIENT_ID = "IOS_CGI_MYQ"
DEFAULT_APP_VERSION = "5.315.0.66076"
DEFAULT_USER_AGENT = "myQ/315.0.66076 CFNetwork/3860.700.1 Darwin/25.6.0"
ANDROID_CLIENT_ID = "ANDROID_CGI_MYQ"
ANDROID_APPLICATION_ID = "226AC80CE0E4456384CC91DFF702D5C29909A176ADF14309A7DA3D18AFE5561D"
ANDROID_CULTURE = "en"
ANDROID_BRAND_ID = "1"
ANDROID_API_VERSION = "4.1"

AUTH_URL = "https://partner-identity.myq-cloud.com/connect/token"
ACCOUNTS_URL = "https://accounts.myq-cloud.com/api/v6.0/accounts"
DEVICES_URL = "https://devices.myq-cloud.com/api/v6.2/Accounts/{account_id}/Devices"
ANDROID_DEVICES_URL = "https://devices.myq-cloud.com/api/v6.0/Accounts/{account_id}/Devices"
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
        self._command_lock = threading.Lock()

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "MyQCloudClient":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    @property
    def headers(self) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self.session.access_token}",
            "App-Version": self.session.app_version,
            "User-Agent": self.session.user_agent,
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.9",
        }
        if self.session.client_id == ANDROID_CLIENT_ID:
            # These are the non-secret common headers emitted by the current
            # official Android APK. Keep them scoped to Android sessions so
            # the independently observed iOS client identity is unchanged.
            headers.update(
                {
                    "MyQApplicationId": ANDROID_APPLICATION_ID,
                    "Culture": ANDROID_CULTURE,
                    "BrandId": ANDROID_BRAND_ID,
                    "ApiVersion": ANDROID_API_VERSION,
                    "Accept": "application/json",
                }
            )
        return headers

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
        refresh = payload.get("refresh_token") or self.session.refresh_token
        if not access:
            raise MyQAuthError("MyQ token refresh response omitted access token")
        self.session = replace(
            self.session,
            access_token=str(access),
            refresh_token=str(refresh),
        )
        if self.on_session_updated is not None:
            self.on_session_updated(self.session)
        return self.session

    def request(
        self,
        method: str,
        url: str,
        *,
        retry_on_unauthorized: bool | None = None,
        **kwargs: Any,
    ) -> httpx.Response:
        # A read can be safely replayed after a token refresh. Do not replay
        # a mutation automatically: a 401 can be returned after a server or
        # intermediary has already accepted the request, and repeating an
        # open/close/lock operation would be unsafe.
        if retry_on_unauthorized is None:
            retry_on_unauthorized = method.upper() in {"GET", "HEAD", "OPTIONS"}
        response = self._client.request(method, url, headers=self.headers, **kwargs)
        if response.status_code == 401 and retry_on_unauthorized:
            self.refresh()
            response = self._client.request(method, url, headers=self.headers, **kwargs)
        if response.status_code == 401:
            raise MyQAuthError("MyQ request was unauthorized; automatic replay was refused")
        return response

    def accounts(self) -> list[dict[str, Any]]:
        response = self.request("GET", ACCOUNTS_URL)
        self._raise(response, "fetch accounts")
        return self._collection(response.json(), "accounts", "fetch accounts")

    def devices(self, account_id: str) -> list[dict[str, Any]]:
        # The installed Android APK still carries a v6.0 device-list service
        # on devices.myq-cloud.com. The newer direct-client evidence uses the
        # v6.2 route. Prefer the APK-shaped route for Android sessions, then
        # fall back to v6.2 only when the service says that route is absent.
        urls = [
            ANDROID_DEVICES_URL.format(account_id=account_id),
            DEVICES_URL.format(account_id=account_id),
        ] if self.session.client_id == ANDROID_CLIENT_ID else [
            DEVICES_URL.format(account_id=account_id)
        ]
        response: httpx.Response | None = None
        for url in urls:
            response = self.request("GET", url)
            if response.status_code not in (404, 405):
                break
        assert response is not None
        self._raise(response, "fetch devices")
        return self._collection(response.json(), "items", "fetch devices")

    def door_status(self, account_id: str | None = None) -> list[dict[str, Any]]:
        """Return a compact automation-friendly summary of every garage door."""
        doors: list[dict[str, Any]] = []
        for account in self.accounts():
            current_account_id = str(account.get("id") or "")
            if not current_account_id:
                continue
            if account_id is not None and current_account_id != str(account_id):
                continue
            for device in self.devices(current_account_id):
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
                        "account_id": str(device.get("account_id") or current_account_id),
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
        """Send one raw explicit action.

        Callers that can affect a real opener should use :meth:`door_command`,
        which performs the observed-state and post-action verification gate.
        This lower-level method remains separate so protocol tests can assert
        the exact mutating request without accidentally adding a second
        command or replaying one after an ambiguous response.
        """
        if action not in {"open", "close"}:
            raise ValueError("action must be 'open' or 'close'")
        response = self.request(
            "PUT",
            DOOR_ACTION_URL.format(
                account_id=account_id,
                door_opener_id=door_opener_id,
                action=action,
            ),
            retry_on_unauthorized=False,
            content=b"",
        )
        if response.status_code not in (200, 202):
            self._raise(response, f"{action} door")

    def door_command(
        self,
        account_id: str,
        door_opener_id: str,
        action: str,
        *,
        verify_timeout: float = 12.0,
        poll_interval: float = 0.75,
    ) -> dict[str, Any]:
        """Serialize and safely perform one explicit door action."""
        with self._command_lock:
            return self._door_command(
                account_id,
                door_opener_id,
                action,
                verify_timeout=verify_timeout,
                poll_interval=poll_interval,
            )

    def door_preflight(
        self, account_id: str, door_opener_id: str, action: str
    ) -> dict[str, Any]:
        """Read the named door and report whether an action is safe to send."""
        if action not in {"open", "close"}:
            raise ValueError("action must be 'open' or 'close'")

        desired = "open" if action == "open" else "closed"
        door = self._find_door(account_id, door_opener_id)
        if door is None:
            raise MyQCloudError(
                f"Refusing {action}: door {door_opener_id!r} was not found in status"
            )

        before = self._state_value(door)
        reason = None
        if before not in {"open", "closed"}:
            reason = f"current state is {before!r}"
        elif door.get("online") is False:
            reason = "door is offline"

        return {
            "ready": reason is None,
            "changed": before != desired,
            "action": action,
            "account_id": account_id,
            "door_opener_id": door_opener_id,
            "before": before,
            "desired": desired,
            "online": door.get("online"),
            "reason": reason,
        }

    def _door_command(
        self,
        account_id: str,
        door_opener_id: str,
        action: str,
        *,
        verify_timeout: float = 12.0,
        poll_interval: float = 0.75,
    ) -> dict[str, Any]:
        """Safely perform one explicit door action and verify the resulting state.

        The command is never sent when the current state is missing, in
        transition, offline, or already equal to the requested state. A
        successful return means the cloud status read observed the requested
        state after the action; failure after the PUT is intentionally
        reported as an error instead of claiming success.
        """
        if action not in {"open", "close"}:
            raise ValueError("action must be 'open' or 'close'")
        if verify_timeout < 0:
            raise ValueError("verify_timeout must be non-negative")
        if poll_interval < 0:
            raise ValueError("poll_interval must be non-negative")

        plan = self.door_preflight(account_id, door_opener_id, action)
        before = str(plan["before"])
        desired = str(plan["desired"])
        if not plan["ready"]:
            raise MyQCloudError(f"Refusing {action}: {plan['reason']}")
        if not plan["changed"]:
            return self._command_result(
                account_id, door_opener_id, action, before, before, changed=False
            )

        self.door_action(account_id, door_opener_id, action)
        after = before
        deadline = time.monotonic() + verify_timeout
        while time.monotonic() < deadline:
            if poll_interval:
                time.sleep(min(poll_interval, max(0.0, deadline - time.monotonic())))
            after_door = self._find_door(account_id, door_opener_id)
            after = self._state_value(after_door) if after_door is not None else "unknown"
            if after == desired:
                return self._command_result(
                    account_id, door_opener_id, action, before, after, changed=True
                )

        raise MyQCloudError(
            f"MyQ {action} request was sent but state did not verify "
            f"(before={before!r}, after={after!r})"
        )

    def _find_door(self, account_id: str, door_opener_id: str) -> dict[str, Any] | None:
        wanted = str(door_opener_id)
        return next(
            (
                door
                for door in self.door_status(account_id)
                if str(door.get("door_opener_id") or "") == wanted
            ),
            None,
        )

    @staticmethod
    def _state_value(door: dict[str, Any] | None) -> str:
        if door is None:
            return "unknown"
        value = door.get("door_state")
        if value is None:
            return "unknown"
        return str(value).strip().lower().replace("_", " ") or "unknown"

    @staticmethod
    def _command_result(
        account_id: str,
        door_opener_id: str,
        action: str,
        before: str,
        after: str,
        *,
        changed: bool,
    ) -> dict[str, Any]:
        return {
            "ok": True,
            "changed": changed,
            "action": action,
            "account_id": account_id,
            "door_opener_id": door_opener_id,
            "before": before,
            "after": after,
        }

    def set_lock_mode(
        self, account_id: str, door_opener_id: str, enabled: bool
    ) -> None:
        response = self.request(
            "PUT",
            LOCKMODE_URL.format(
                account_id=account_id,
                door_opener_id=door_opener_id,
            ),
            retry_on_unauthorized=False,
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

    @staticmethod
    def _collection(payload: Any, key: str, operation: str) -> list[dict[str, Any]]:
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        if isinstance(payload, dict):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        raise MyQCloudError(f"MyQ {operation} returned an unexpected JSON shape")
