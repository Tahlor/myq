from __future__ import annotations

import argparse
import collections
import json
import shutil
import subprocess
from pathlib import Path


def run_tshark(pcap: Path) -> list[list[str]]:
    tshark = shutil.which("tshark")
    if not tshark:
        raise RuntimeError("tshark is required and was not found on PATH")
    fields = [
        "frame.time_epoch",
        "ip.src",
        "ip.dst",
        "tcp.srcport",
        "tcp.dstport",
        "udp.srcport",
        "udp.dstport",
        "dns.qry.name",
        "tls.handshake.extensions_server_name",
    ]
    command = [tshark, "-r", str(pcap), "-T", "fields", "-E", "separator=\t"]
    for field in fields:
        command.extend(["-e", field])
    result = subprocess.run(command, capture_output=True, text=True, errors="replace")
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "tshark failed")
    rows: list[list[str]] = []
    for line in result.stdout.splitlines():
        parts = line.split("\t")
        parts.extend([""] * (len(fields) - len(parts)))
        rows.append(parts[: len(fields)])
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize DNS/TLS/endpoint metadata from an opener pcap")
    parser.add_argument("pcap", type=Path)
    parser.add_argument("--opener-ip", default="", help="If supplied, include only packets to/from this IPv4 address")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    rows = run_tshark(args.pcap)
    dns: collections.Counter[str] = collections.Counter()
    sni: collections.Counter[str] = collections.Counter()
    endpoints: collections.Counter[str] = collections.Counter()
    filtered = 0

    for row in rows:
        _, src, dst, tcp_src, tcp_dst, udp_src, udp_dst, dns_name, server_name = row
        if args.opener_ip and args.opener_ip not in {src, dst}:
            continue
        filtered += 1
        if dns_name:
            for name in dns_name.split(","):
                if name.strip():
                    dns[name.strip().lower()] += 1
        if server_name:
            for name in server_name.split(","):
                if name.strip():
                    sni[name.strip().lower()] += 1
        if src and dst:
            if args.opener_ip:
                remote = dst if src == args.opener_ip else src
                remote_port = tcp_dst or udp_dst if src == args.opener_ip else tcp_src or udp_src
                if remote and remote_port:
                    endpoints[f"{remote}:{remote_port}"] += 1
            else:
                port = tcp_dst or udp_dst
                if port:
                    endpoints[f"{dst}:{port}"] += 1

    report = {
        "pcap": str(args.pcap),
        "opener_ip": args.opener_ip or None,
        "filtered_packet_rows": filtered,
        "dns_queries": dns.most_common(),
        "tls_sni": sni.most_common(),
        "remote_endpoints": endpoints.most_common(),
        "note": "This report contains transport metadata only; encrypted application payloads are not decoded.",
    }
    output = args.output or args.pcap.with_suffix(args.pcap.suffix + ".summary.json")
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
