"""Audit the exact APK's internal device surface without invoking it.

This is deliberately narrower than a decompiler.  It records method and
dispatch counts from selected smali files, plus dashboard call-site markers.
It never copies source lines, URLs, identifiers, request bodies, or tokens to
the report.  A transport surface is evidence for further analysis, not proof
that an external caller can safely invoke a garage operation.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Iterable


METHOD_LINE = re.compile(r"^\.method\s+(.+)$")
OPERATION_INVOKE = re.compile(
    r"invoke-[^ ]+\s+.*;->(?:open|close|operate|command|actuat|toggle)\(",
    re.IGNORECASE,
)
DIRECT_API_CALL = re.compile(
    r"Lmyq/sdk/(?:external/api/device/DeviceApiImpl|external/api/device/a);->",
    re.IGNORECASE,
)
V6_SERVICE_CALL = re.compile(
    r"Lcom/chamberlain/network/framework/service/api/v6/devices/",
    re.IGNORECASE,
)
VGDOS_BODY = re.compile(r"vgdoservice/body/", re.IGNORECASE)


def _read_lines(path: Path) -> list[str]:
    try:
        return path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []


def _method_name(line: str) -> str | None:
    match = METHOD_LINE.match(line.strip())
    if not match:
        return None
    before_parameters = match.group(1).split("(", 1)[0]
    parts = before_parameters.split()
    return parts[-1] if parts else None


def _method_lines(lines: Iterable[str]) -> list[tuple[int, str, str]]:
    records: list[tuple[int, str, str]] = []
    for line_number, line in enumerate(lines, start=1):
        name = _method_name(line)
        if name is not None:
            records.append((line_number, name, line.strip()))
    return records


def _find_suffix(root: Path, suffix: str) -> Path | None:
    normalized = suffix.replace("\\", "/")
    direct = root / Path(normalized)
    if direct.is_file():
        return direct
    if not root.is_dir():
        return None
    for path in root.rglob("*.smali"):
        if path.as_posix().endswith("/" + normalized):
            return path
    return None


def _relative_name(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.name


def audit_transport(path: Path | None, *, source_root: Path) -> dict[str, Any]:
    if path is None:
        return {"present": False}
    lines = _read_lines(path)
    records = _method_lines(lines)
    body_methods = [
        name for _, name, signature in records if VGDOS_BODY.search(signature)
    ]
    return {
        "present": True,
        "path": _relative_name(path, source_root),
        "method_count": len(records),
        "method_names": sorted({name for _, name, _ in records}),
        "v6_service_dispatch_line_count": sum(
            1 for line in lines if V6_SERVICE_CALL.search(line)
        ),
        "vgdo_service_body_method_names": sorted(set(body_methods)),
        "vgdo_service_body_method_count": len(set(body_methods)),
        "payloads_emitted": False,
    }


def audit_device_api(path: Path | None, *, source_root: Path) -> dict[str, Any]:
    if path is None:
        return {"present": False}
    lines = _read_lines(path)
    records = _method_lines(lines)
    return {
        "present": True,
        "path": _relative_name(path, source_root),
        "method_count": len(records),
        "method_names": sorted({name for _, name, _ in records}),
        "device_interaction_reference_line_count": sum(
            1 for line in lines if "DeviceInteraction" in line
        ),
        "payloads_emitted": False,
    }


def audit_dashboard(path: Path | None, *, source_root: Path) -> dict[str, Any]:
    if path is None:
        return {"present": False}
    lines = _read_lines(path)
    counts = {
        "start_activity_line_count": sum(
            1 for line in lines if "startActivity" in line
        ),
        "start_service_line_count": sum(
            1 for line in lines if re.search(r"start(?:Foreground)?Service", line)
        ),
        "broadcast_line_count": sum(
            1 for line in lines if re.search(r"send(?:Ordered)?Broadcast", line)
        ),
        "pending_intent_line_count": sum(
            1 for line in lines if "PendingIntent" in line
        ),
        "shortcut_or_widget_line_count": sum(
            1
            for line in lines
            if re.search(r"Shortcut|AppWidget|Widget", line, re.IGNORECASE)
        ),
        "operation_term_line_count": sum(
            1
            for line in lines
            if re.search(r"open|close|door|device", line, re.IGNORECASE)
        ),
        "direct_operation_invocation_line_count": sum(
            1 for line in lines if OPERATION_INVOKE.search(line)
        ),
    }
    return {
        "present": True,
        "path": _relative_name(path, source_root),
        "line_count": len(lines),
        "signals": counts,
        "direct_operation_invocation_signal": bool(
            counts["direct_operation_invocation_line_count"]
        ),
        "payloads_emitted": False,
    }


def audit_app_call_sites(app_root: Path | None) -> dict[str, Any]:
    """Count app-side references to the SDK wrapper, excluding SDK sources."""

    if app_root is None or not app_root.is_dir():
        return {"present": False}
    files = 0
    lines = 0
    for path in app_root.rglob("*.smali"):
        source = _read_lines(path)
        matches = sum(1 for line in source if DIRECT_API_CALL.search(line))
        if matches:
            files += 1
            lines += matches
    return {
        "present": True,
        "app_root": app_root.name,
        "wrapper_reference_file_count": files,
        "wrapper_reference_line_count": lines,
        "payloads_emitted": False,
    }


def build_report(
    source_root: Path,
    *,
    dashboard: Path | None = None,
    app_root: Path | None = None,
) -> dict[str, Any]:
    """Build a bounded report from an extracted smali tree."""

    dashboard_path = dashboard or _find_suffix(
        source_root, "com/chamberlain/myq/main/HomeTabsActivity.smali"
    )
    transport_path = _find_suffix(
        source_root, "myq/sdk/common/misc/communication/method/k.smali"
    )
    device_api_path = _find_suffix(
        source_root, "myq/sdk/external/api/device/DeviceApiImpl.smali"
    )
    dashboard_report = audit_dashboard(dashboard_path, source_root=source_root)
    transport_report = audit_transport(transport_path, source_root=source_root)
    direct_dashboard_signal = bool(
        dashboard_report.get("direct_operation_invocation_signal", False)
    )
    has_transport_body = bool(transport_report.get("vgdo_service_body_method_count"))
    if direct_dashboard_signal:
        conclusion = "dashboard operation invocation signal present; runtime classification required"
    elif has_transport_body:
        conclusion = "internal transport surface found; no direct dashboard operation invocation signal"
    else:
        conclusion = "no direct dashboard operation or internal transport body signal established"
    return {
        "tool": "android_sdk_surface_audit",
        "source_root": source_root.name,
        "runtime_validation": "not_run",
        "state_changing_actions_attempted": False,
        "dashboard": dashboard_report,
        "device_api_wrapper": audit_device_api(device_api_path, source_root=source_root),
        "v6_transport": transport_report,
        "app_call_sites": audit_app_call_sites(app_root),
        "conclusion": conclusion,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Read-only static audit of the official APK device surface"
    )
    parser.add_argument("source_root", type=Path)
    parser.add_argument(
        "--dashboard",
        type=Path,
        help="Optional exact HomeTabsActivity.smali path when it is in another dex tree",
    )
    parser.add_argument(
        "--app-root",
        type=Path,
        help="Optional app smali root for wrapper reference counts",
    )
    parser.add_argument("--output", type=Path, help="Optional JSON output path")
    args = parser.parse_args()
    if not args.source_root.is_dir():
        parser.error(f"source root does not exist: {args.source_root}")
    if args.dashboard is not None and not args.dashboard.is_file():
        parser.error(f"dashboard file does not exist: {args.dashboard}")
    if args.app_root is not None and not args.app_root.is_dir():
        parser.error(f"app root does not exist: {args.app_root}")

    payload = json.dumps(
        build_report(
            args.source_root,
            dashboard=args.dashboard,
            app_root=args.app_root,
        ),
        indent=2,
        sort_keys=True,
    )
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")
    print(payload)


if __name__ == "__main__":
    main()
