#!/usr/bin/env python3
"""Analyze the public historical MyQ PIC/MCU serial protocol captures.

This module is intentionally *not* a live G0401 command implementation.  It
encodes facts recoverable from the public ``fuxxociety/MyQ-ESP-transplant``
``MCU Communication.log`` so we can compare any future current-unit evidence
without first probing the owner's hardware.

Observed public frame syntax::

    <P8...74>

``P`` is a literal marker.  The next hex nibble is a rotating/log sequence
prefix and is not covered by the checksum.  The remaining characters are hex
bytes; the final byte is a CRC-8 over all preceding binary bytes.

The checksum parameters fit every distinct public sample tested:

* polynomial: 0x1D
* initial value: 0xAA
* xor-out: 0x00
* MSB-first / non-reflected

Two additional field hypotheses come only from explicitly labelled portions of
that public log and are therefore reported as ``historical_*`` semantics:

* a 20-byte status payload with the observed signature has byte 17 values
  0x01=open, 0x02=closed, 0x04=opening, 0x05=closing;
* a 21-byte wall-button/action payload with the observed signature has final
  byte 0x0D on the labelled open sample and 0x0E on the labelled close sample.

Do not use these hypotheses to move a real door without independently proving
the current device uses the same protocol and preserving the project's normal
state/confirmation safety gates.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


CRC8_POLY = 0x1D
CRC8_INIT = 0xAA

FRAME_RE = re.compile(r"<(?P<frame>P[0-9A-Fa-f][0-9A-Fa-f]+)>")

# Signatures are deliberately narrow: they describe the public capture, not a
# claim about all Chamberlain/MyQ generations.
HISTORICAL_STATUS_PREFIX = bytes.fromhex("011102110f008601b31fa0")
HISTORICAL_ACTION_PREFIX = bytes.fromhex("0111021110020501020100247259fa41")

HISTORICAL_STATES = {
    0x01: "open",
    0x02: "closed",
    0x04: "opening",
    0x05: "closing",
}

HISTORICAL_ACTIONS = {
    0x0D: "open",
    0x0E: "close",
}


@dataclass(frozen=True)
class ParsedFrame:
    raw: str
    sequence: int
    payload: bytes
    checksum: int
    checksum_valid: bool
    historical_kind: str | None = None
    historical_state: str | None = None
    historical_action: str | None = None

    def summary(self) -> dict[str, object]:
        value = asdict(self)
        value["payload"] = self.payload.hex()
        return value


def crc8(data: bytes) -> int:
    """Return the checksum used by the public historical MCU capture."""

    value = CRC8_INIT
    for byte in data:
        value ^= byte
        for _ in range(8):
            if value & 0x80:
                value = ((value << 1) & 0xFF) ^ CRC8_POLY
            else:
                value = (value << 1) & 0xFF
    return value


def parse_frame(frame: str) -> ParsedFrame:
    """Parse one ``P<n><hex...>`` frame, with optional angle brackets."""

    raw = frame.strip()
    if raw.startswith("<") and raw.endswith(">"):
        raw = raw[1:-1]
    if len(raw) < 6 or raw[0] != "P":
        raise ValueError("frame must have form P<sequence><hex payload+crc>")

    try:
        sequence = int(raw[1], 16)
        encoded = bytes.fromhex(raw[2:])
    except ValueError as exc:
        raise ValueError("invalid hexadecimal historical frame") from exc
    if len(encoded) < 2:
        raise ValueError("historical frame is too short")

    payload, checksum = encoded[:-1], encoded[-1]
    valid = crc8(payload) == checksum

    kind = state = action = None
    if valid and len(payload) == 20 and payload.startswith(HISTORICAL_STATUS_PREFIX):
        kind = "status"
        state = HISTORICAL_STATES.get(payload[17])
    elif valid and len(payload) == 21 and payload.startswith(HISTORICAL_ACTION_PREFIX):
        kind = "action"
        action = HISTORICAL_ACTIONS.get(payload[-1])

    return ParsedFrame(
        raw=raw,
        sequence=sequence,
        payload=payload,
        checksum=checksum,
        checksum_valid=valid,
        historical_kind=kind,
        historical_state=state,
        historical_action=action,
    )


def extract_frames(text: str) -> list[ParsedFrame]:
    return [parse_frame(match.group("frame")) for match in FRAME_RE.finditer(text)]


def summarize(frames: Iterable[ParsedFrame]) -> dict[str, object]:
    items = list(frames)
    states: dict[str, int] = {}
    actions: dict[str, int] = {}
    for item in items:
        if item.historical_state:
            states[item.historical_state] = states.get(item.historical_state, 0) + 1
        if item.historical_action:
            actions[item.historical_action] = actions.get(item.historical_action, 0) + 1
    return {
        "frames": len(items),
        "checksum_valid": sum(item.checksum_valid for item in items),
        "checksum_invalid": sum(not item.checksum_valid for item in items),
        "historical_states": states,
        "historical_actions": actions,
        "warning": (
            "Semantics are inferred from a public historical MyQ capture and are "
            "not proven for the owner's MYQ-G0401."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture", type=Path, help="text file containing <P...> frames")
    parser.add_argument(
        "--frames",
        action="store_true",
        help="include parsed frame summaries as well as aggregate counts",
    )
    args = parser.parse_args()

    parsed = extract_frames(args.capture.read_text(encoding="utf-8", errors="replace"))
    report = summarize(parsed)
    if args.frames:
        report["parsed_frames"] = [frame.summary() for frame in parsed]
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
