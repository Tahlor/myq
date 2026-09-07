#!/usr/bin/env python3
"""Safely inspect the MyQ firmware PSM record that wraps ``myq_aes``.

The related 88MW30x firmware dump studied for this project stores a 16-byte
``myq_aes`` value in a small PSM record.  The firmware unwraps that value with
a 32-round, little-endian TEA variant and a fixed 16-byte binary code constant.
The constant is the literal immediately before the ``mac_addr``/``myq_sn``
labels in that image; it is not a device credential.

This tool is intentionally an offline, secret-safe summary tool.  It prints
record metadata and hashes only; it never prints the ciphertext or unwrapped
key bytes.  Raw firmware dumps belong under the ignored ``captures/`` tree.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator


PSM_MAGIC = b"\x55\xAA"
PSM_MARKERS = frozenset((0xFE, 0xFF))
MYQ_AES_KEY = "myq_aes"
MYQ_AES_VALUE_LENGTH = 16

# Exact 16-byte literal passed to the unwrap routine in the related firmware
# image.  It is a public firmware code constant, not a device credential.
TEA_WRAP_KEY = bytes.fromhex("ff10b54a43b61ab933fdcba30b071c57")
TEA_DELTA = 0x9E3779B9
UINT32_MASK = 0xFFFFFFFF


@dataclass(frozen=True)
class PsmRecord:
    """A minimally parsed PSM record with its value kept in memory only."""

    offset: int
    marker: int
    record_type: int
    index: int
    key: str
    value: bytes


def _is_printable_key(value: bytes) -> bool:
    return bool(value) and all(0x20 <= byte < 0x7F for byte in value)


def _iter_headers(blob: bytes) -> Iterator[tuple[int, int, int, int, str, int]]:
    """Yield plausible PSM headers without interpreting their values.

    The record's two-byte index and two-byte key length are big-endian in the
    observed firmware format.  Value lengths are not carried in the header;
    callers that need a named value should use its known length or the next
    plausible header boundary.
    """

    pos = 0
    while True:
        start = blob.find(PSM_MAGIC, pos)
        if start < 0:
            return
        pos = start + len(PSM_MAGIC)
        if start + 12 > len(blob) or blob[start + 2] not in PSM_MARKERS:
            continue

        marker = blob[start + 2]
        record_type = blob[start + 7]
        index = int.from_bytes(blob[start + 8 : start + 10], "big")
        key_length = int.from_bytes(blob[start + 10 : start + 12], "big")
        key_start = start + 12
        key_end = key_start + key_length
        if not 1 <= key_length <= 128 or key_end > len(blob):
            continue
        key_bytes = blob[key_start:key_end]
        if not _is_printable_key(key_bytes):
            continue
        yield start, marker, record_type, index, key_bytes.decode("ascii"), key_end


def find_psm_record(blob: bytes, key: str) -> PsmRecord | None:
    """Find a named record and return its value without logging it.

    ``myq_aes`` is known to be exactly 16 bytes in the related firmware.  For
    other names, the value extends to the next plausible PSM header.  This is
    useful for offline triage, but is deliberately not a general-purpose PSM
    database parser because the format's checksum and tombstone semantics are
    not needed for the key-recovery decision.
    """

    headers = list(_iter_headers(blob))
    for position, header in enumerate(headers):
        start, marker, record_type, index, record_key, value_start = header
        if record_key != key:
            continue

        if key == MYQ_AES_KEY:
            value_end = value_start + MYQ_AES_VALUE_LENGTH
            if value_end > len(blob):
                return None
        elif position + 1 < len(headers):
            value_end = headers[position + 1][0]
        else:
            value_end = len(blob)
        return PsmRecord(
            offset=start,
            marker=marker,
            record_type=record_type,
            index=index,
            key=record_key,
            value=blob[value_start:value_end],
        )
    return None


def _tea_decrypt_block(block: bytes, key_words: tuple[int, int, int, int]) -> bytes:
    if len(block) != 8:
        raise ValueError("TEA operates on 8-byte blocks")
    if len(key_words) != 4:
        raise ValueError("the firmware TEA routine requires four key words")

    v0, v1 = struct.unpack("<2I", block)
    total = (TEA_DELTA * 32) & UINT32_MASK
    key_index = 0
    for _ in range(32):
        mix = ((((v0 << 4) & UINT32_MASK) ^ (v0 >> 5)) + v0) & UINT32_MASK
        v1 = (
            v1 - (mix ^ ((total + key_words[key_index]) & UINT32_MASK))
        ) & UINT32_MASK
        key_index = (key_index - 1) & 3
        total = (total - TEA_DELTA) & UINT32_MASK
        mix = ((((v1 << 4) & UINT32_MASK) ^ (v1 >> 5)) + v1) & UINT32_MASK
        v0 = (
            v0 - (mix ^ ((total + key_words[key_index]) & UINT32_MASK))
        ) & UINT32_MASK
    return struct.pack("<2I", v0, v1)


def unwrap_myq_aes(value: bytes) -> bytes:
    """Unwrap a 16-byte related-firmware ``myq_aes`` value in memory."""

    if len(value) != MYQ_AES_VALUE_LENGTH:
        raise ValueError("myq_aes must be exactly 16 bytes")
    key_words = struct.unpack("<4I", TEA_WRAP_KEY)
    return b"".join(
        _tea_decrypt_block(value[offset : offset + 8], key_words)
        for offset in (0, 8)
    )


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def summarize_image(path: Path, key: str = MYQ_AES_KEY) -> dict[str, object]:
    blob = path.read_bytes()
    record = find_psm_record(blob, key)
    summary: dict[str, object] = {
        "file": path.name,
        "key": key,
        "found": record is not None,
    }
    if record is None:
        return summary

    summary.update(
        {
            "record_offset": f"0x{record.offset:x}",
            "marker": f"0x{record.marker:02x}",
            "record_type": f"0x{record.record_type:02x}",
            "index": f"0x{record.index:04x}",
            "ciphertext_length": len(record.value),
            "ciphertext_sha256": _sha256(record.value),
        }
    )
    if key == MYQ_AES_KEY and len(record.value) == MYQ_AES_VALUE_LENGTH:
        unwrapped = unwrap_myq_aes(record.value)
        summary.update(
            {
                "unwrapped_length": len(unwrapped),
                "unwrapped_sha256": _sha256(unwrapped),
            }
        )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path, help="offline firmware/SPI-flash dump")
    parser.add_argument(
        "--key",
        default=MYQ_AES_KEY,
        help="PSM key to locate (default: myq_aes; values are never printed)",
    )
    args = parser.parse_args()
    print(json.dumps(summarize_image(args.image, args.key), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
