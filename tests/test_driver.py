from types import SimpleNamespace

import pytest

from myq_bridge.config import DoorConfig, Selector
from myq_bridge.driver import MyQDriver


def test_normalize_state_handles_common_labels():
    assert MyQDriver.normalize_state("OPEN") == "open"
    assert MyQDriver.normalize_state("Garage Closed") == "closed"
    assert MyQDriver.normalize_state("Opening door") == "opening"
    assert MyQDriver.normalize_state(None) == "unknown"


def test_visible_nodes_and_state_tokens():
    xml = """<?xml version='1.0' encoding='UTF-8' standalone='yes' ?>
    <hierarchy rotation="0">
      <node text="Garage Door" resource-id="com.myq:id/name" class="android.widget.TextView" clickable="false" bounds="[0,0][100,30]" />
      <node text="Closed" resource-id="com.myq:id/state" class="android.widget.TextView" clickable="false" bounds="[0,30][100,60]" />
      <node text="" content-desc="Open garage" resource-id="com.myq:id/action" class="android.widget.Button" clickable="true" bounds="[0,60][100,100]" />
    </hierarchy>"""
    nodes = MyQDriver.visible_nodes(xml)
    assert [node["resource_id"] for node in nodes] == [
        "com.myq:id/name",
        "com.myq:id/state",
        "com.myq:id/action",
    ]
    assert MyQDriver.infer_state_tokens(xml) == ["closed"]


def test_explicit_command_refuses_toggle_when_state_is_unknown():
    door = DoorConfig(
        name="Garage Door",
        state=Selector(resource_id="state"),
        toggle=Selector(resource_id="toggle"),
    )

    class FakeDriver(MyQDriver):
        def __init__(self):
            self.settings = SimpleNamespace(doors=(door,))
            self._lock = __import__("threading").RLock()
            self.clicked = False

        def launch(self):
            pass

        def get_state(self, _door):
            return "unknown"

        def _click(self, _selector):
            self.clicked = True

    driver = FakeDriver()
    with pytest.raises(RuntimeError, match="Refusing blind toggle"):
        driver.command("Garage Door", "toggle")
    assert driver.clicked is False


def test_command_fails_closed_when_post_state_is_not_verified(monkeypatch):
    door = DoorConfig(
        name="Garage Door",
        state=Selector(resource_id="state"),
        toggle=Selector(resource_id="toggle"),
    )

    class FakeDriver(MyQDriver):
        def __init__(self):
            self.settings = SimpleNamespace(doors=(door,))
            self._lock = __import__("threading").RLock()
            self.clicked = False
            self.states = iter(("closed",))

        def launch(self):
            pass

        def get_state(self, _door):
            return next(self.states)

        def _click(self, _selector):
            self.clicked = True

    driver = FakeDriver()
    monotonic_values = iter((0.0, 13.0))
    monkeypatch.setattr("myq_bridge.driver.time.monotonic", lambda: next(monotonic_values))

    with pytest.raises(RuntimeError, match="was not verified"):
        driver.command("Garage Door", "open")
    assert driver.clicked is True


def test_explicit_command_refuses_unstable_state_even_with_direct_selector():
    door = DoorConfig(
        name="Garage Door",
        state=Selector(resource_id="state"),
        open=Selector(resource_id="open"),
    )

    class FakeDriver(MyQDriver):
        def __init__(self):
            self.settings = SimpleNamespace(doors=(door,))
            self._lock = __import__("threading").RLock()
            self.clicked = False

        def launch(self):
            pass

        def get_state(self, _door):
            return "opening"

        def _click(self, _selector):
            self.clicked = True

    driver = FakeDriver()
    with pytest.raises(RuntimeError, match="Refusing open"):
        driver.command("Garage Door", "open")
    assert driver.clicked is False
