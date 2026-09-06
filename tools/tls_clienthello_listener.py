#!/usr/bin/env python3
"""Passive TCP/TLS ClientHello listener for MyQ opener redirect experiments.

The listener does not complete TLS and does not send application data. Its job is
simply to answer the first redirect question: if DNS points the opener's cloud
hostname at us, does the opener connect, and what TLS metadata does it present?

Typical use on a LAN test host:

    sudo python tools/tls_clienthello_listener.py --bind 0.0.0.0 --port 8883

Then temporarily redirect only the opener's discovered MyQ hostname to that host.
The tool prints JSON records containing source IP, TLS record version, SNI, ALPN,
and cipher/extension counts. Raw handshake bytes are not logged by default.
"""

from __future__ import annotations

import argparse
import json
import socket
import struct
import time
from dataclasses import dataclass, asdict
from typing import Any


@dataclass
class ClientHelloSummary:
    peer: str
    peer_port: int
    received_bytes: int
    tls_record_version: str | None = None
    client_version: str | None = None
    handshake_type: int | None = None
    sni: str | None = None
    alpn: list[str] | None = None
    cipher_count: int | None = None
    extension_types: list[int] | None = None
    parse_error: str | None = None


def _version(raw: bytes) -> str:
    if len(raw) != 2:
        return "unknown"
    return f"{raw[0]}.{raw[1]}"


def parse_client_hello(data: bytes, peer: tuple[str, int] = ("unknown", 0)) -> ClientHelloSummary:
    summary = ClientHelloSummary(peer=peer[0], peer_port=peer[1], received_bytes=len(data))
    try:
        if len(data) < 9:
            raise ValueError("too short for TLS record + handshake")
        content_type = data[0]
        if content_type != 22:
            raise ValueError(f"first TLS record content type is {content_type}, not handshake(22)")
        summary.tls_record_version = _version(data[1:3])
        record_len = struct.unpack("!H", data[3:5])[0]
        if len(data) < 5 + record_len:
            raise ValueError(f"incomplete TLS record: need {5 + record_len}, got {len(data)}")

        body = memoryview(data)[5 : 5 + record_len]
        summary.handshake_type = int(body[0])
        if summary.handshake_type != 1:
            raise ValueError(f"handshake type {summary.handshake_type} is not ClientHello(1)")
        handshake_len = int.from_bytes(body[1:4], "big")
        if len(body) < 4 + handshake_len:
            raise ValueError("incomplete ClientHello")
        hello = body[4 : 4 + handshake_len]

        pos = 0
        if len(hello) < 34:
            raise ValueError("ClientHello missing version/random")
        summary.client_version = _version(bytes(hello[pos : pos + 2]))
        pos += 2 + 32

        session_len = int(hello[pos])
        pos += 1 + session_len
        if pos + 2 > len(hello):
            raise ValueError("missing cipher suite length")
        cipher_len = struct.unpack("!H", hello[pos : pos + 2])[0]
        pos += 2
        summary.cipher_count = cipher_len // 2
        pos += cipher_len

        if pos >= len(hello):
            return summary
        compression_len = int(hello[pos])
        pos += 1 + compression_len
        if pos == len(hello):
            return summary
        if pos + 2 > len(hello):
            raise ValueError("missing extensions length")
        ext_total = struct.unpack("!H", hello[pos : pos + 2])[0]
        pos += 2
        end = min(pos + ext_total, len(hello))

        extension_types: list[int] = []
        alpn: list[str] = []
        while pos + 4 <= end:
            ext_type = struct.unpack("!H", hello[pos : pos + 2])[0]
            ext_len = struct.unpack("!H", hello[pos + 2 : pos + 4])[0]
            pos += 4
            ext = bytes(hello[pos : pos + ext_len])
            pos += ext_len
            extension_types.append(ext_type)

            if ext_type == 0 and len(ext) >= 5:  # server_name
                list_len = struct.unpack("!H", ext[:2])[0]
                q = 2
                limit = min(2 + list_len, len(ext))
                while q + 3 <= limit:
                    name_type = ext[q]
                    name_len = struct.unpack("!H", ext[q + 1 : q + 3])[0]
                    q += 3
                    name = ext[q : q + name_len]
                    q += name_len
                    if name_type == 0:
                        summary.sni = name.decode("utf-8", errors="replace")
                        break
            elif ext_type == 16 and len(ext) >= 2:  # ALPN
                q = 2
                while q < len(ext):
                    n = ext[q]
                    q += 1
                    proto = ext[q : q + n]
                    q += n
                    if proto:
                        alpn.append(proto.decode("ascii", errors="replace"))

        summary.extension_types = extension_types
        summary.alpn = alpn
    except Exception as exc:
        summary.parse_error = str(exc)
    return summary


def recv_first_record(conn: socket.socket, timeout: float, max_bytes: int = 65535) -> bytes:
    conn.settimeout(timeout)
    chunks = bytearray()
    while len(chunks) < 5:
        part = conn.recv(5 - len(chunks))
        if not part:
            return bytes(chunks)
        chunks.extend(part)
    record_len = struct.unpack("!H", chunks[3:5])[0]
    target = min(5 + record_len, max_bytes)
    while len(chunks) < target:
        part = conn.recv(target - len(chunks))
        if not part:
            break
        chunks.extend(part)
    return bytes(chunks)


def serve(bind: str, port: int, timeout: float, once: bool) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((bind, port))
        server.listen(16)
        print(json.dumps({"event": "listening", "bind": bind, "port": port}), flush=True)
        while True:
            conn, peer = server.accept()
            with conn:
                started = time.time()
                try:
                    data = recv_first_record(conn, timeout)
                    summary = parse_client_hello(data, peer)
                except Exception as exc:
                    summary = ClientHelloSummary(
                        peer=peer[0],
                        peer_port=peer[1],
                        received_bytes=0,
                        parse_error=f"receive failed: {exc}",
                    )
                record: dict[str, Any] = asdict(summary)
                record["event"] = "connection"
                record["elapsed_ms"] = round((time.time() - started) * 1000, 1)
                print(json.dumps(record, sort_keys=True), flush=True)
            if once:
                return


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bind", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8883)
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    serve(args.bind, args.port, args.timeout, args.once)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
