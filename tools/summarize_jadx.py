from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

PATTERNS = {
    "myq_domains": re.compile(r"[A-Za-z0-9._-]*myq-cloud\.com", re.I),
    "mqtt": re.compile(r"\bmqtt\b|mqtts://|tcp://[^\s\"']+:8883", re.I),
    "firebase": re.compile(r"firebase|appcheck", re.I),
    "integrity": re.compile(r"play.?integrity|integritymanager|standardintegrity", re.I),
    "http_stack": re.compile(r"okhttp|retrofit|certificatepinner", re.I),
    "websocket": re.compile(r"websocket|wss://", re.I),
    "auth": re.compile(r"oauth|pkce|authorization|bearer", re.I),
}


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: summarize_jadx.py <jadx-output>", file=sys.stderr)
        return 2

    root = Path(sys.argv[1])
    hits: dict[str, list[dict[str, object]]] = defaultdict(list)
    seen_domains: set[str] = set()

    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {".java", ".xml", ".json", ".txt", ".properties"}:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        rel = str(path.relative_to(root))
        lines = text.splitlines()
        for category, pattern in PATTERNS.items():
            matched = 0
            for number, line in enumerate(lines, 1):
                if not pattern.search(line):
                    continue
                clean = " ".join(line.strip().split())[:500]
                hits[category].append({"file": rel, "line": number, "text": clean})
                matched += 1
                if category == "myq_domains":
                    seen_domains.update(m.group(0).lower() for m in PATTERNS["myq_domains"].finditer(line))
                if matched >= 12:
                    break

    report = {
        "root": str(root.resolve()),
        "domains": sorted(seen_domains),
        "categories": {key: value[:100] for key, value in sorted(hits.items())},
    }
    output = root / "myq-static-summary.json"
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"summary": str(output), "domains": report["domains"], "hit_counts": {k: len(v) for k, v in hits.items()}}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
