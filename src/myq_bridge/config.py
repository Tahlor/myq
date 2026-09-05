from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Selector:
    resource_id: str | None = None
    text: str | None = None
    description: str | None = None
    text_contains: str | None = None

    @classmethod
    def from_dict(cls, raw: dict[str, Any] | None) -> "Selector | None":
        if not raw:
            return None
        return cls(
            resource_id=raw.get("resource_id"),
            text=raw.get("text"),
            description=raw.get("description"),
            text_contains=raw.get("text_contains"),
        )

    def is_empty(self) -> bool:
        return not any((self.resource_id, self.text, self.description, self.text_contains))


@dataclass(frozen=True)
class DoorConfig:
    name: str
    state: Selector
    open: Selector | None = None
    close: Selector | None = None
    toggle: Selector | None = None

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "DoorConfig":
        state = Selector.from_dict(raw.get("state"))
        if state is None or state.is_empty():
            raise ValueError(f"Door {raw.get('name')!r} is missing a state selector")
        return cls(
            name=str(raw["name"]),
            state=state,
            open=Selector.from_dict(raw.get("open")),
            close=Selector.from_dict(raw.get("close")),
            toggle=Selector.from_dict(raw.get("toggle")),
        )


@dataclass(frozen=True)
class Settings:
    adb_serial: str
    api_key: str
    package_name: str
    doors: tuple[DoorConfig, ...]
    host: str
    port: int


def load_settings() -> Settings:
    api_key = os.environ.get("MYQ_API_KEY", "")
    if len(api_key) < 16:
        raise RuntimeError("MYQ_API_KEY must be set to a secret of at least 16 characters")

    serial = os.environ.get("MYQ_ADB_SERIAL", "").strip()
    if not serial:
        raise RuntimeError("MYQ_ADB_SERIAL must be set to the Superbox ADB serial (host:port)")

    config_path = Path(os.environ.get("MYQ_DOORS_CONFIG", "config/doors.json"))
    doors: tuple[DoorConfig, ...] = ()
    if config_path.exists():
        raw = json.loads(config_path.read_text(encoding="utf-8"))
        doors = tuple(DoorConfig.from_dict(item) for item in raw.get("doors", []))

    return Settings(
        adb_serial=serial,
        api_key=api_key,
        package_name=os.environ.get(
            "MYQ_PACKAGE", "com.chamberlain.android.liftmaster.myq"
        ),
        doors=doors,
        host=os.environ.get("MYQ_BIND", "0.0.0.0"),
        port=int(os.environ.get("MYQ_PORT", "8765")),
    )
