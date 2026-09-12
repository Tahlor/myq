"""Summarize passive router observations for one G0401 without exposing its LAN IP."""
from __future__ import annotations

import argparse
import ipaddress
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

PAIR_RE = re.compile(r"\b(src|dst|sport|dport)=([^\s]+)")
HOST_RE = re.compile(r"\b(?:[A-Za-z0-9-]+\.)+(?:com|net|org|io|cloud)\b", re.I)
KNOWN_CONNECTION_HOSTS = {"connect.myqdevice.com", "connect1.myqdevice.com"}
TCPDUMP_IP_RE = re.compile(r"\bIP\s+(\d{1,3}(?:\.\d{1,3}){3})\.(\d+)\s+>\s+(\d{1,3}(?:\.\d{1,3}){3})\.(\d+):")


def _public_remote(value: str) -> str | None:
    try:
        ip = ipaddress.ip_address(value)
    except ValueError:
        return None
    return str(ip) if ip.is_global else None


def _protocol(line: str) -> str:
    tokens = line.lower().split()
    for candidate in ("tcp", "udp"):
        if candidate in tokens[:5]:
            return candidate
    return "unknown"



def _detect_candidate(text: str) -> str:
    sources: set[str] = set()
    for line in text.splitlines():
        tcpdump = TCPDUMP_IP_RE.search(line)
        if tcpdump:
            src, _sport, _dst, dport = tcpdump.groups()
            if dport == "8883":
                sources.add(src)
            continue
        fields = PAIR_RE.findall(line)
        first: dict[str, str] = {}
        for key, value in fields:
            if key not in first:
                first[key] = value
            if {"src", "dst", "sport", "dport"} <= first.keys():
                break
        if first.get("dport") == "8883" and first.get("src"):
            sources.add(first["src"])
    if len(sources) != 1:
        raise ValueError(f"expected exactly one outbound-8883 source, found {len(sources)}")
    return next(iter(sources))

def summarize(text: str, candidate_ip: str) -> dict[str, Any]:
    if candidate_ip == "auto":
        candidate_ip = _detect_candidate(text)
    endpoints: Counter[tuple[str, str, str]] = Counter()
    hostnames: set[str] = set()
    for line in text.splitlines():
        hostnames.update(match.lower() for match in HOST_RE.findall(line))
        tcpdump = TCPDUMP_IP_RE.search(line)
        if tcpdump:
            src, _sport, dst, dport = tcpdump.groups()
            if src == candidate_ip:
                remote = _public_remote(dst)
                if remote is not None:
                    proto = "udp" if " UDP" in line else "tcp"
                    endpoints[(proto, remote, dport)] += 1
            continue
        fields = PAIR_RE.findall(line)
        if not fields:
            continue
        first: dict[str, str] = {}
        for key, value in fields:
            if key not in first:
                first[key] = value
            if {"src", "dst", "sport", "dport"} <= first.keys():
                break
        if first.get("src") != candidate_ip:
            continue
        remote = _public_remote(first.get("dst", ""))
        if remote is None:
            continue
        dport = first.get("dport", "?")
        endpoints[(_protocol(line), remote, dport)] += 1

    endpoint_rows = [
        {"protocol": proto, "remote_ip": remote, "port": port, "count": count}
        for (proto, remote, port), count in sorted(endpoints.items())
    ]
    ports: Counter[str] = Counter()
    for row in endpoint_rows:
        ports[row["port"]] += int(row["count"])

    known_hosts = sorted(hostnames & KNOWN_CONNECTION_HOSTS)
    novel_hosts = sorted(hostnames - KNOWN_CONNECTION_HOSTS)
    return {
        "tool": "router_traffic_summary",
        "candidate_ip": "<redacted-g0401-lan-ip>",
        "endpoints": endpoint_rows,
        "destination_ports": dict(sorted(ports.items())),
        "known_connection_hosts_seen": known_hosts,
        "other_hostnames_seen": novel_hosts,
        "baseline_8883_only": bool(endpoint_rows)
        and all(row["port"] == "8883" for row in endpoint_rows),
        "network_requests_made": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize passive G0401 router metadata")
    parser.add_argument("capture", type=Path)
    parser.add_argument("--candidate-ip", required=True)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    payload = summarize(
        args.capture.read_text(encoding="utf-8", errors="replace"), args.candidate_ip
    )
    encoded = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(encoded, encoding="utf-8")
    print(encoded, end="")


if __name__ == "__main__":
    main()
