from __future__ import annotations

"""Read-only bridge monitor with narrowly scoped, fail-closed recovery.

The watchdog only reads the bridge health/status endpoints. If recovery is
explicitly enabled it may touch the companion package or accessibility
settings through ADB. It never background-launches the official dashboard,
sends a garage command, or falls back after an ambiguous mutation.
"""

import argparse
import json
import os
import subprocess
import time
from dataclasses import dataclass
from typing import Any, Callable, Sequence

import httpx


BRIDGE_PACKAGE = "com.tahlor.myqbridge"
BRIDGE_ACTIVITY = f"{BRIDGE_PACKAGE}/.MainActivity"
BRIDGE_ACCESSIBILITY_COMPONENT = (
    f"{BRIDGE_PACKAGE}/{BRIDGE_PACKAGE}.BridgeAccessibilityService"
)


@dataclass(frozen=True)
class WatchdogSettings:
    bridge_url: str
    api_key: str
    adb_serial: str = ""
    adb_path: str = "adb"
    recovery_cooldown: float = 300.0
    request_timeout: float = 5.0
    use_root: bool = True
    dry_run: bool = False

    @classmethod
    def from_env(cls, *, dry_run: bool = False) -> "WatchdogSettings":
        api_key = os.environ.get("MYQ_API_KEY", "")
        if len(api_key) < 16:
            raise RuntimeError(
                "MYQ_API_KEY must be set to a secret of at least 16 characters"
            )
        return cls(
            bridge_url=os.environ.get("MYQ_BRIDGE_URL", "http://127.0.0.1:8765").rstrip(
                "/"
            ),
            api_key=api_key,
            adb_serial=os.environ.get("MYQ_ADB_SERIAL", "").strip(),
            adb_path=os.environ.get("MYQ_ADB_PATH", "adb"),
            recovery_cooldown=float(
                os.environ.get("MYQ_WATCHDOG_RECOVERY_COOLDOWN", "300")
            ),
            request_timeout=float(
                os.environ.get("MYQ_WATCHDOG_REQUEST_TIMEOUT", "5")
            ),
            use_root=os.environ.get("MYQ_WATCHDOG_USE_ROOT", "1") == "1",
            dry_run=dry_run,
        )


class BridgeWatchdog:
    """Poll the bridge and perform only known, reversible recovery actions."""

    def __init__(
        self,
        settings: WatchdogSettings,
        *,
        client: Any | None = None,
        run_command: Callable[[Sequence[str]], Any] | None = None,
        monotonic: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.settings = settings
        self.client = client or httpx.Client(
            follow_redirects=False, timeout=settings.request_timeout
        )
        self._owns_client = client is None
        self._run_command = run_command or self._default_run_command
        self._monotonic = monotonic
        self._sleep = sleep
        self._last_recovery_at: float | None = None

    def close(self) -> None:
        if self._owns_client:
            self.client.close()

    def run_once(self) -> dict[str, Any]:
        health, health_error = self._get("/health")
        if health is None or health.status_code != 200:
            return {
                "healthy": False,
                "stage": "health",
                "status_code": health.status_code if health is not None else None,
                "error": health_error or "bridge health endpoint is unavailable",
                "recovery": self._recover("restart_host"),
            }

        status, status_error = self._get("/status", authenticated=True)
        if status is not None and status.status_code == 200:
            return {
                "healthy": True,
                "stage": "status",
                "status_code": status.status_code,
                "recovery": None,
            }

        detail = self._response_detail(status)
        if not detail:
            detail = status_error or "bridge status endpoint is unavailable"
        lowered = detail.casefold()
        if "accessibility" in lowered:
            action = "rebind_accessibility"
        elif "foreground" in lowered:
            action = "launch_dashboard"
        else:
            action = "restart_host"

        return {
            "healthy": False,
            "stage": "status",
            "status_code": status.status_code if status is not None else None,
            "error": detail[:300],
            "recovery": self._recover(action),
        }

    def _get(
        self, path: str, *, authenticated: bool = False
    ) -> tuple[Any | None, str | None]:
        headers = {"X-API-Key": self.settings.api_key} if authenticated else {}
        try:
            response = self.client.get(
                f"{self.settings.bridge_url}{path}",
                headers=headers,
                timeout=self.settings.request_timeout,
            )
            return response, None
        except Exception as exc:
            return None, f"{type(exc).__name__}: {exc}"

    @staticmethod
    def _response_detail(response: Any | None) -> str:
        if response is None:
            return ""
        try:
            payload = response.json()
        except Exception:
            return ""
        if isinstance(payload, dict):
            value = payload.get("detail") or payload.get("error")
            if value is not None:
                return str(value)
        return ""

    def _recover(self, action: str) -> dict[str, Any]:
        if action == "launch_dashboard":
            return {
                "action": action,
                "attempted": False,
                "ok": False,
                "reason": "official dashboard must be foregrounded by the user",
            }
        if not self.settings.adb_serial:
            return {
                "action": action,
                "attempted": False,
                "ok": False,
                "reason": "MYQ_ADB_SERIAL is not configured",
            }

        now = self._monotonic()
        if (
            self._last_recovery_at is not None
            and now - self._last_recovery_at < self.settings.recovery_cooldown
        ):
            return {
                "action": action,
                "attempted": False,
                "ok": False,
                "reason": "recovery cooldown is active",
            }

        self._last_recovery_at = now
        if self.settings.dry_run:
            return {
                "action": action,
                "attempted": False,
                "ok": True,
                "dry_run": True,
            }

        try:
            if action == "restart_host":
                self._adb(["shell", "am", "start", "-n", BRIDGE_ACTIVITY])
            elif action == "rebind_accessibility":
                self._rebind_accessibility()
            else:
                raise ValueError(f"unsupported watchdog recovery action: {action}")
        except Exception as exc:
            return {
                "action": action,
                "attempted": True,
                "ok": False,
                "error": f"{type(exc).__name__}: {exc}",
            }

        return {"action": action, "attempted": True, "ok": True}

    def _rebind_accessibility(self) -> None:
        current = self._adb(
            ["shell", "settings", "get", "secure", "enabled_accessibility_services"]
        ).strip()
        if current == "null":
            current = ""
        services = [
            value.strip()
            for value in current.split(":")
            if value.strip() and value.strip() != BRIDGE_ACCESSIBILITY_COMPONENT
        ]
        without_bridge = ":".join(services)

        self._secure_setting("accessibility_enabled", "0")
        self._secure_setting("enabled_accessibility_services", without_bridge)
        self._sleep(0.5)
        self._secure_setting(
            "enabled_accessibility_services",
            ":".join([*services, BRIDGE_ACCESSIBILITY_COMPONENT]),
        )
        self._secure_setting("accessibility_enabled", "1")
        self._adb(["shell", "am", "start", "-n", BRIDGE_ACTIVITY])

    def _secure_setting(self, name: str, value: str) -> None:
        command = ["shell"]
        if self.settings.use_root:
            command.extend(["su", "0"])
        command.extend(["settings", "put", "secure", name, value])
        self._adb(command)

    def _adb(self, arguments: Sequence[str]) -> str:
        command = [self.settings.adb_path, "-s", self.settings.adb_serial, *arguments]
        completed = self._run_command(command)
        returncode = getattr(completed, "returncode", 0)
        if returncode != 0:
            stderr = str(getattr(completed, "stderr", "") or "").strip()
            stdout = str(getattr(completed, "stdout", "") or "").strip()
            message = stderr or stdout or f"exit {returncode}"
            raise RuntimeError(f"adb command failed: {message[:300]}")
        return str(getattr(completed, "stdout", "") or "")

    @staticmethod
    def _default_run_command(command: Sequence[str]) -> Any:
        return subprocess.run(
            list(command),
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )


def _print_result(result: dict[str, Any]) -> None:
    print(json.dumps(result, sort_keys=True), flush=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true", help="poll once and exit")
    parser.add_argument("--dry-run", action="store_true", help="report recovery without ADB writes")
    parser.add_argument(
        "--apply-recovery",
        action="store_true",
        help="allow scoped host/accessibility recovery (never launches official myQ)",
    )
    parser.add_argument("--interval", type=float, default=float(os.environ.get("MYQ_WATCHDOG_INTERVAL", "60")))
    parser.add_argument("--cooldown", type=float, default=None)
    parser.add_argument("--request-timeout", type=float, default=None)
    parser.add_argument("--no-root", action="store_true", help="do not use su 0 for secure settings")
    args = parser.parse_args(argv)

    try:
        settings = WatchdogSettings.from_env(
            dry_run=args.dry_run or not args.apply_recovery
        )
    except RuntimeError as exc:
        parser.error(str(exc))

    if args.cooldown is not None or args.request_timeout is not None or args.no_root:
        settings = WatchdogSettings(
            bridge_url=settings.bridge_url,
            api_key=settings.api_key,
            adb_serial=settings.adb_serial,
            adb_path=settings.adb_path,
            recovery_cooldown=(
                args.cooldown if args.cooldown is not None else settings.recovery_cooldown
            ),
            request_timeout=(
                args.request_timeout
                if args.request_timeout is not None
                else settings.request_timeout
            ),
            use_root=False if args.no_root else settings.use_root,
            dry_run=settings.dry_run,
        )

    watchdog = BridgeWatchdog(settings)
    try:
        if args.once:
            _print_result(watchdog.run_once())
            return 0

        while True:
            _print_result(watchdog.run_once())
            time.sleep(max(0.1, args.interval))
    except KeyboardInterrupt:
        return 0
    finally:
        watchdog.close()


if __name__ == "__main__":
    raise SystemExit(main())
