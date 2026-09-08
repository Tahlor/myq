from __future__ import annotations

from types import SimpleNamespace

from myq_bridge.watchdog import BridgeWatchdog, WatchdogSettings


class FakeClient:
    def __init__(self, responses):
        self.responses = iter(responses)

    def get(self, _url, **_kwargs):
        return next(self.responses)


def test_watchdog_reports_healthy_status_without_recovery():
    watchdog = BridgeWatchdog(
        WatchdogSettings("http://bridge", "a" * 16, adb_serial="adb"),
        client=FakeClient(
            [
                SimpleNamespace(status_code=200, json=lambda: {"status": "ok"}),
                SimpleNamespace(status_code=200, json=lambda: {"doors": {}}),
            ]
        ),
        run_command=lambda _command: (_ for _ in ()).throw(AssertionError()),
    )

    assert watchdog.run_once() == {
        "healthy": True,
        "stage": "status",
        "status_code": 200,
        "recovery": None,
    }


def test_watchdog_never_background_launches_dashboard_for_foreground_error():
    commands: list[list[str]] = []
    watchdog = BridgeWatchdog(
        WatchdogSettings("http://bridge", "a" * 16, adb_serial="adb"),
        client=FakeClient(
            [
                SimpleNamespace(status_code=200, json=lambda: {"status": "ok"}),
                SimpleNamespace(
                    status_code=409,
                    json=lambda: {"error": "myQ must be in the foreground"},
                ),
            ]
        ),
        run_command=lambda command: commands.append(list(command)),
    )

    result = watchdog.run_once()

    assert result["healthy"] is False
    assert result["recovery"] == {
        "action": "launch_dashboard",
        "attempted": False,
        "ok": False,
        "reason": "official dashboard must be foregrounded by the user",
    }
    assert commands == []


def test_watchdog_defaults_to_dry_run_for_host_recovery():
    commands: list[list[str]] = []
    watchdog = BridgeWatchdog(
        WatchdogSettings(
            "http://bridge",
            "a" * 16,
            adb_serial="adb",
            dry_run=True,
        ),
        client=FakeClient(
            [SimpleNamespace(status_code=503, json=lambda: {"error": "down"})]
        ),
        run_command=lambda command: commands.append(list(command)),
    )

    result = watchdog.run_once()

    assert result["recovery"] == {
        "action": "restart_host",
        "attempted": False,
        "ok": True,
        "dry_run": True,
    }
    assert commands == []
