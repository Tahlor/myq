"""Secret-safe drift audit for the public MyQ protocol profile.

Point this at one or more exact-APK decompile/resource roots. It reports only
known public markers and narrowly shaped public candidates; it never dumps
arbitrary strings, tokens, cookies, serials, or request bodies.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from myq_bridge.protocol_profile import ANDROID_2026_09

TEXT_SUFFIXES = {".smali", ".xml", ".json", ".txt", ".kt", ".java", ".properties"}
MAX_FILE_BYTES = 4 * 1024 * 1024
CLIENT_RE = re.compile(rb"\b[A-Z][A-Z0-9_]{2,32}_CGI_MYQ\b")
HOST_RE = re.compile(rb"\b[a-z0-9.-]+\.myq-cloud\.com\b", re.I)
REDIRECT_RE = re.compile(rb"\bcom\.[a-z0-9._-]+://android\b", re.I)
SCOPE_RE = re.compile(rb"\bMyQ_Residential(?:\s+offline_access)?\b")
APP_ID_LABEL = b"MyQApplicationId"
HEX64_RE = re.compile(rb"\b[A-Fa-f0-9]{64}\b")


def iter_files(roots: list[Path]):
    for root in roots:
        if root.is_file():
            yield root
            continue
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
                continue
            try:
                if path.stat().st_size <= MAX_FILE_BYTES:
                    yield path
            except OSError:
                continue


def audit(roots: list[Path]) -> dict[str, object]:
    profile = ANDROID_2026_09
    expected = {
        "client_id": profile.client_id,
        "scope": profile.scope or "",
        "redirect_uri": profile.redirect_uri or "",
        "application_id": profile.application_id or "",
        "auth_host": "partner-identity.myq-cloud.com",
        "accounts_host": "accounts.myq-cloud.com",
        "devices_host": "devices.myq-cloud.com",
        "gdo_host": "account-devices-gdo.myq-cloud.com",
    }
    needles = {key: value.encode("utf-8") for key, value in expected.items() if value}
    found = {key: False for key in needles}
    candidates: dict[str, set[str]] = {
        "client_ids": set(), "hosts": set(), "redirect_uris": set(), "scopes": set(),
        "labeled_application_ids": set(),
    }
    files_scanned = 0
    for path in iter_files(roots):
        try:
            data = path.read_bytes()
        except OSError:
            continue
        files_scanned += 1
        for key, needle in needles.items():
            if needle in data:
                found[key] = True
        candidates["client_ids"].update(x.decode("ascii") for x in CLIENT_RE.findall(data))
        candidates["hosts"].update(x.decode("ascii").lower() for x in HOST_RE.findall(data))
        candidates["redirect_uris"].update(x.decode("ascii") for x in REDIRECT_RE.findall(data))
        candidates["scopes"].update(x.decode("ascii") for x in SCOPE_RE.findall(data))
        if APP_ID_LABEL in data:
            candidates["labeled_application_ids"].update(x.decode("ascii") for x in HEX64_RE.findall(data))
    # Token-shaped values must match exactly; substring checks can create false
    # positives such as NEWANDROID_CGI_MYQ containing ANDROID_CGI_MYQ.
    found["client_id"] = expected["client_id"] in candidates["client_ids"]
    found["scope"] = expected["scope"] in candidates["scopes"]
    found["redirect_uri"] = expected["redirect_uri"] in candidates["redirect_uris"]
    if candidates["labeled_application_ids"]:
        found["application_id"] = expected["application_id"] in candidates["labeled_application_ids"]
    required_static_markers = {
        "client_id", "scope", "redirect_uri", "auth_host", "accounts_host",
        "devices_host", "gdo_host",
    }
    missing = [key for key in sorted(required_static_markers) if not found.get(key, False)]
    unattested = [key for key, present in found.items() if key not in required_static_markers and not present]
    return {
        "profile": profile.name,
        "files_scanned": files_scanned,
        "expected_markers": found,
        "missing_markers": missing,
        "unattested_runtime_markers": unattested,
        "candidate_public_values": {key: sorted(values) for key, values in candidates.items()},
        "drift_detected": bool(missing),
        "note": "Missing required static markers require review; runtime-attested fields may legitimately be absent from decompiled literals.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("roots", nargs="+", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    result = audit(args.roots)
    rendered = json.dumps(result, indent=2, sort_keys=True)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    raise SystemExit(2 if result["drift_detected"] else 0)


if __name__ == "__main__":
    main()
