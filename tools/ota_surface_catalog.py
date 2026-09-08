"""Secret-safe offline catalog for OTA, Realtek, and PSK-lineage evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


SIGNALS: dict[str, tuple[tuple[str, re.Pattern[str]], ...]] = {
    "ota": (
        ("ota", re.compile(rb"\bota\b", re.IGNORECASE)),
        ("firmware", re.compile(rb"firmware", re.IGNORECASE)),
        ("update", re.compile(rb"update", re.IGNORECASE)),
        ("manifest", re.compile(rb"manifest", re.IGNORECASE)),
        ("download", re.compile(rb"download", re.IGNORECASE)),
        ("image", re.compile(rb"image", re.IGNORECASE)),
        ("version", re.compile(rb"version", re.IGNORECASE)),
    ),
    "realtek_amebad": (
        ("rtl8720cs", re.compile(rb"rtl8720cs", re.IGNORECASE)),
        ("rtl8720", re.compile(rb"rtl8720", re.IGNORECASE)),
        ("ameba", re.compile(rb"ameba", re.IGNORECASE)),
        ("6220n_is", re.compile(rb"6220n[-_ ]?is", re.IGNORECASE)),
        ("gd25q64", re.compile(rb"gd25q64", re.IGNORECASE)),
        ("swd", re.compile(rb"swd(?:io|clk)?", re.IGNORECASE)),
        ("uart_log", re.compile(rb"uart[_ -]?log", re.IGNORECASE)),
    ),
    "psk_provisioning": (
        ("psk", re.compile(rb"\bpsk\b", re.IGNORECASE)),
        ("pre_shared", re.compile(rb"pre[-_ ]shared", re.IGNORECASE)),
        ("tls_psk", re.compile(rb"tls[_ -]?psk", re.IGNORECASE)),
        ("provision", re.compile(rb"provision", re.IGNORECASE)),
        ("nvm", re.compile(rb"\bnvm\b", re.IGNORECASE)),
        ("myq_aes", re.compile(rb"myq[_ -]?aes", re.IGNORECASE)),
        ("identity", re.compile(rb"identity", re.IGNORECASE)),
        ("key_wrap", re.compile(rb"key[-_ ]?wrap", re.IGNORECASE)),
    ),
}
DEFAULT_MAX_SCAN_BYTES = 16 * 1024 * 1024


def _files(root: Path) -> list[Path]:
    if root.is_file():
        return [root]
    return [path for path in sorted(root.rglob("*")) if path.is_file()]


def _relative(path: Path, root: Path) -> str:
    if root.is_file():
        return path.name
    return path.relative_to(root).as_posix()


def _hash_and_sample(path: Path, max_scan_bytes: int) -> tuple[int, str, bytes, bool]:
    digest = hashlib.sha256()
    sample = bytearray()
    size = 0
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
            size += len(chunk)
            if len(sample) < max_scan_bytes:
                sample.extend(chunk[: max_scan_bytes - len(sample)])
    return size, digest.hexdigest(), bytes(sample), size > max_scan_bytes


def catalog_path(root: Path, *, max_scan_bytes: int = DEFAULT_MAX_SCAN_BYTES) -> dict[str, Any]:
    """Catalog signal categories without returning matching bytes or strings."""

    if not root.exists():
        raise FileNotFoundError(root)
    entries: list[dict[str, Any]] = []
    for path in _files(root):
        size, sha256, sample, truncated = _hash_and_sample(path, max_scan_bytes)
        category_results: dict[str, list[dict[str, Any]]] = {}
        for category, patterns in SIGNALS.items():
            matches = [
                {"signal": name, "count": len(pattern.findall(sample))}
                for name, pattern in patterns
                if pattern.search(sample)
            ]
            if matches:
                category_results[category] = matches
        if category_results:
            entries.append(
                {
                    "path": _relative(path, root),
                    "size": size,
                    "sha256": sha256,
                    "scan_truncated": truncated,
                    "signals": category_results,
                }
            )
    return {
        "tool": "ota_surface_catalog",
        "root": "<redacted>",
        "files_with_signals": entries,
        "payloads_emitted": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Offline secret-safe OTA/Realtek/PSK evidence catalog"
    )
    parser.add_argument("path", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--max-scan-bytes", type=int, default=DEFAULT_MAX_SCAN_BYTES)
    args = parser.parse_args()
    try:
        report = catalog_path(args.path, max_scan_bytes=args.max_scan_bytes)
    except (FileNotFoundError, ValueError) as exc:
        parser.error(str(exc))
    payload = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(payload, encoding="utf-8")
    print(payload, end="")


if __name__ == "__main__":
    main()
