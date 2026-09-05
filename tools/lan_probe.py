from __future__ import annotations

import argparse
import concurrent.futures
import ipaddress
import json
import platform
import re
import socket
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path

CHAMBERLAIN_OUIS = {
    "0C:95:05",
    "44:11:46",
    "64:52:99",
    "CC:6A:10",
    "00:15:25",  # legacy Chamberlain Access Solutions registration
}
DEFAULT_PORTS = (22, 53, 80, 443, 554, 1883, 8080, 8443, 8883)


@dataclass
class Host:
    ip: str
    mac: str | None
    hostname: str | None
    chamberlain_oui: bool
    open_ports: list[int]


def normalize_mac(value: str) -> str:
    return value.replace("-", ":").upper()


def ping(ip: str, timeout_ms: int = 350) -> bool:
    if platform.system() == "Windows":
        cmd = ["ping", "-n", "1", "-w", str(timeout_ms), ip]
    else:
        cmd = ["ping", "-c", "1", "-W", "1", ip]
    result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return result.returncode == 0


def arp_table() -> dict[str, str]:
    result = subprocess.run(["arp", "-a"], capture_output=True, text=True, errors="ignore")
    table: dict[str, str] = {}
    # Covers Windows `192.168.x.x  aa-bb-cc...` and common POSIX `(...) at aa:bb...` output.
    pattern = re.compile(
        r"(?P<ip>\d{1,3}(?:\.\d{1,3}){3}).*?(?P<mac>[0-9a-fA-F]{2}(?:[:-][0-9a-fA-F]{2}){5})"
    )
    for line in result.stdout.splitlines():
        match = pattern.search(line)
        if match:
            table[match.group("ip")] = normalize_mac(match.group("mac"))
    return table


def reverse_name(ip: str) -> str | None:
    try:
        return socket.gethostbyaddr(ip)[0]
    except (socket.herror, socket.gaierror, OSError):
        return None


def port_open(ip: str, port: int, timeout: float = 0.25) -> bool:
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return True
    except OSError:
        return False


def is_chamberlain(mac: str | None) -> bool:
    if not mac:
        return False
    normalized = normalize_mac(mac)
    return any(normalized.startswith(prefix) for prefix in CHAMBERLAIN_OUIS)


def main() -> int:
    parser = argparse.ArgumentParser(description="Discover likely myQ devices on a local IPv4 subnet")
    parser.add_argument("--subnet", default="192.168.187.0/24")
    parser.add_argument("--ports", default=",".join(map(str, DEFAULT_PORTS)))
    parser.add_argument("--scan-all-ports", action="store_true", help="Probe ports on every responding host, not just Chamberlain OUI matches")
    parser.add_argument("--output", default="captures/lan/latest.json")
    args = parser.parse_args()

    network = ipaddress.ip_network(args.subnet, strict=False)
    ips = [str(ip) for ip in network.hosts()]
    with concurrent.futures.ThreadPoolExecutor(max_workers=64) as pool:
        live = [ip for ip, ok in zip(ips, pool.map(ping, ips)) if ok]

    arp = arp_table()
    ports = [int(value) for value in args.ports.split(",") if value.strip()]
    hosts: list[Host] = []
    for ip in live:
        mac = arp.get(ip)
        candidate = is_chamberlain(mac)
        opened: list[int] = []
        if candidate or args.scan_all_ports:
            with concurrent.futures.ThreadPoolExecutor(max_workers=min(16, len(ports) or 1)) as pool:
                checks = list(pool.map(lambda p: port_open(ip, p), ports))
            opened = [port for port, ok in zip(ports, checks) if ok]
        hosts.append(Host(ip, mac, reverse_name(ip), candidate, opened))

    candidates = [asdict(host) for host in hosts if host.chamberlain_oui]
    report = {
        "subnet": str(network),
        "known_chamberlain_ouis": sorted(CHAMBERLAIN_OUIS),
        "candidate_count": len(candidates),
        "candidates": candidates,
        "live_hosts": [asdict(host) for host in hosts],
        "note": "No listening ports does not rule out myQ; openers may be outbound-only cloud clients.",
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
