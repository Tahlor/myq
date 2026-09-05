from __future__ import annotations

import threading
import time
import xml.etree.ElementTree as ET
from dataclasses import asdict
from typing import Any

from .config import DoorConfig, Selector, Settings


_STATE_MAP = {
    "open": "open",
    "opened": "open",
    "closed": "closed",
    "close": "closed",
    "opening": "opening",
    "closing": "closing",
    "stopped": "stopped",
    "offline": "offline",
}


class MyQDriver:
    """Drive the official myQ app through Android UIAutomator.

    The first live run is intentionally calibration-oriented: `/debug/tree`
    exposes the current accessibility hierarchy so stable resource IDs / text
    selectors can be captured in `config/doors.json`.
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self._device: Any | None = None
        self._lock = threading.RLock()

    def connect(self) -> Any:
        if self._device is None:
            import uiautomator2 as u2

            self._device = u2.connect(self.settings.adb_serial)
        return self._device

    def launch(self) -> None:
        d = self.connect()
        d.app_start(self.settings.package_name, stop=False)
        time.sleep(1.0)

    def hierarchy(self) -> str:
        return self.connect().dump_hierarchy(compressed=False)

    @staticmethod
    def visible_nodes(xml: str) -> list[dict[str, str]]:
        root = ET.fromstring(xml)
        nodes: list[dict[str, str]] = []
        for node in root.iter("node"):
            if node.attrib.get("visible-to-user", "true") == "false":
                continue
            entry = {
                "text": node.attrib.get("text", ""),
                "description": node.attrib.get("content-desc", ""),
                "resource_id": node.attrib.get("resource-id", ""),
                "class": node.attrib.get("class", ""),
                "clickable": node.attrib.get("clickable", "false"),
                "bounds": node.attrib.get("bounds", ""),
            }
            if any((entry["text"], entry["description"], entry["resource_id"])):
                nodes.append(entry)
        return nodes

    @staticmethod
    def normalize_state(value: str | None) -> str:
        if not value:
            return "unknown"
        cleaned = " ".join(value.strip().lower().replace("_", " ").split())
        for token, normalized in _STATE_MAP.items():
            if cleaned == token or cleaned.endswith(f" {token}") or cleaned.startswith(f"{token} "):
                return normalized
        return cleaned

    @staticmethod
    def infer_state_tokens(xml: str) -> list[str]:
        found: list[str] = []
        for node in MyQDriver.visible_nodes(xml):
            for value in (node["text"], node["description"]):
                state = MyQDriver.normalize_state(value)
                if state in {"open", "closed", "opening", "closing", "stopped", "offline"}:
                    found.append(state)
        return found

    def _ui_selector(self, selector: Selector) -> Any:
        kwargs: dict[str, str] = {}
        if selector.resource_id:
            kwargs["resourceId"] = selector.resource_id
        if selector.text:
            kwargs["text"] = selector.text
        if selector.description:
            kwargs["description"] = selector.description
        if selector.text_contains:
            kwargs["textContains"] = selector.text_contains
        if not kwargs:
            raise ValueError("Empty UI selector")
        return self.connect()(**kwargs)

    def _read_selector(self, selector: Selector) -> str | None:
        obj = self._ui_selector(selector)
        if not obj.exists(timeout=2.0):
            return None
        try:
            text = obj.get_text()
            if text:
                return str(text)
        except Exception:
            pass
        try:
            info = obj.info
            return str(info.get("contentDescription") or info.get("text") or "") or None
        except Exception:
            return None

    def get_state(self, door: DoorConfig) -> str:
        return self.normalize_state(self._read_selector(door.state))

    def status(self) -> dict[str, Any]:
        with self._lock:
            self.launch()
            xml = self.hierarchy()
            doors = {
                door.name: {"state": self.get_state(door)}
                for door in self.settings.doors
            }
            return {
                "status": "online",
                "package": self.settings.package_name,
                "adb_serial": self.settings.adb_serial,
                "doors": doors,
                "inferred_state_tokens": self.infer_state_tokens(xml),
                "configured_doors": len(self.settings.doors),
            }

    def _click(self, selector: Selector) -> None:
        obj = self._ui_selector(selector)
        if not obj.exists(timeout=3.0):
            raise RuntimeError(f"UI selector not found: {asdict(selector)}")
        if not obj.click_exists(timeout=3.0):
            raise RuntimeError(f"UI selector was not clickable: {asdict(selector)}")

    def command(self, door_name: str, target: str) -> dict[str, Any]:
        if target not in {"open", "closed", "toggle"}:
            raise ValueError(f"Unsupported target: {target}")
        door = next((item for item in self.settings.doors if item.name == door_name), None)
        if door is None:
            raise KeyError(f"Unknown door: {door_name}")

        with self._lock:
            self.launch()
            before = self.get_state(door)
            if target in {"open", "closed"} and before == target:
                return {"ok": True, "changed": False, "before": before, "after": before}

            selector = (
                door.open if target == "open" else
                door.close if target == "closed" else
                door.toggle
            )
            if selector is None and target in {"open", "closed"}:
                selector = door.toggle
            if selector is None:
                raise RuntimeError(f"No selector configured for {door.name!r} -> {target}")

            self._click(selector)

            deadline = time.monotonic() + 12.0
            after = before
            desired = target if target != "toggle" else None
            while time.monotonic() < deadline:
                time.sleep(0.75)
                after = self.get_state(door)
                if desired and after == desired:
                    break
                if desired is None and after != before and after != "unknown":
                    break

            return {"ok": True, "changed": True, "before": before, "after": after}
