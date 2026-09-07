#!/usr/bin/env python3
"""Handshake-only transparent TCP probe for an outbound TLS client.

This tool is intended for a narrowly scoped, temporary DNAT experiment.  It
uses Linux's SO_ORIGINAL_DST to recover the destination that was rewritten by
the router, opens a byte-transparent upstream connection, and forwards only
TLS handshake records.  Application-data records are logged as blocked and
are never forwarded in either direction.

The probe does not terminate TLS, inject a certificate, or send application
data.  It is therefore useful for answering whether the device's real server
accepts its handshake and which TLS record/cipher behavior follows it.
"""

from __future__ import annotations

import argparse
import json
import select
import socket
import struct
import time
from dataclasses import dataclass, field
from typing import Iterable


SO_ORIGINAL_DST = 80
TLS_CONTENT_TYPES = {
    20: "change_cipher_spec",
    21: "alert",
    22: "handshake",
    23: "application_data",
}


def _version(raw: bytes) -> str:
    if len(raw) != 2:
        return "unknown"
    return f"{raw[0]}.{raw[1]}"


def original_destination(conn: socket.socket) -> tuple[str, int] | None:
    """Return the pre-DNAT IPv4 destination, when Linux exposes it."""

    try:
        raw = conn.getsockopt(socket.SOL_IP, SO_ORIGINAL_DST, 16)
        if len(raw) < 8:
            return None
        port = struct.unpack("!H", raw[2:4])[0]
        address = socket.inet_ntoa(raw[4:8])
        return address, port
    except OSError:
        return None


def _handshake_types(body: bytes) -> list[int]:
    types: list[int] = []
    pos = 0
    while pos + 4 <= len(body):
        message_type = body[pos]
        message_len = int.from_bytes(body[pos + 1 : pos + 4], "big")
        end = pos + 4 + message_len
        if end > len(body):
            break
        types.append(message_type)
        pos = end
    return types


def _server_hello_cipher(body: bytes) -> str | None:
    """Extract the selected cipher from a plaintext ServerHello body."""

    if len(body) < 35:
        return None
    session_length = body[34]
    cipher_offset = 35 + session_length
    if cipher_offset + 2 > len(body):
        return None
    return f"0x{int.from_bytes(body[cipher_offset : cipher_offset + 2], 'big'):04x}"


def _client_hello_ciphers(body: bytes) -> list[str] | None:
    """Extract offered cipher IDs from a plaintext ClientHello body."""

    if len(body) < 35:
        return None
    pos = 2 + 32
    session_length = body[pos]
    pos += 1 + session_length
    if pos + 2 > len(body):
        return None
    cipher_length = struct.unpack("!H", body[pos : pos + 2])[0]
    pos += 2
    if pos + cipher_length > len(body):
        return None
    return [
        f"0x{int.from_bytes(body[offset : offset + 2], 'big'):04x}"
        for offset in range(pos, pos + cipher_length, 2)
    ]


def summarize_record(record: bytes, direction: str) -> dict[str, object]:
    """Return metadata for one TLS record without retaining its payload."""

    if len(record) < 5:
        return {
            "direction": direction,
            "content_type": None,
            "record_version": None,
            "length": len(record),
            "parse_error": "short TLS record",
        }

    content_type = record[0]
    result: dict[str, object] = {
        "direction": direction,
        "content_type": content_type,
        "content_name": TLS_CONTENT_TYPES.get(content_type, "unknown"),
        "record_version": _version(record[1:3]),
        "length": struct.unpack("!H", record[3:5])[0],
    }
    if content_type == 22:
        body = record[5:]
        result["handshake_types"] = _handshake_types(body)
        if direction == "client_to_server" and body[:1] == b"\x01":
            message_len = int.from_bytes(body[1:4], "big")
            hello = body[4 : 4 + message_len]
            ciphers = _client_hello_ciphers(hello)
            if ciphers is not None:
                result["client_cipher_suites"] = ciphers
        elif direction == "client_to_server" and body[:1] == b"\x10":
            message_len = int.from_bytes(body[1:4], "big")
            exchange = body[4 : 4 + message_len]
            if len(exchange) >= 2:
                result["client_psk_identity_length"] = struct.unpack(
                    "!H", exchange[:2]
                )[0]
        elif direction == "server_to_client" and body[:1] == b"\x02":
            message_len = int.from_bytes(body[1:4], "big")
            hello = body[4 : 4 + message_len]
            cipher = _server_hello_cipher(hello)
            if cipher is not None:
                result["server_selected_cipher"] = cipher
    return result


@dataclass
class RecordBuffer:
    data: bytearray = field(default_factory=bytearray)

    def feed(self, chunk: bytes) -> Iterable[bytes]:
        self.data.extend(chunk)
        while len(self.data) >= 5:
            length = struct.unpack("!H", self.data[3:5])[0]
            total = 5 + length
            if len(self.data) < total:
                return
            record = bytes(self.data[:total])
            del self.data[:total]
            yield record


def _emit(event: dict[str, object]) -> None:
    print(json.dumps(event, sort_keys=True), flush=True)


def _forward_records(
    source: socket.socket,
    target: socket.socket,
    tracker: RecordBuffer,
    direction: str,
    state: dict[str, object],
) -> bool:
    """Forward complete non-application TLS records; return whether to stop."""

    try:
        chunk = source.recv(65535)
    except (BlockingIOError, ConnectionResetError, socket.timeout):
        return True
    if not chunk:
        return True

    for record in tracker.feed(chunk):
        summary = summarize_record(record, direction)
        _emit({"event": "record", **summary})
        content_type = record[0] if record else None
        if content_type == 23:
            _emit({
                "event": "blocked_application_data",
                "direction": direction,
                "length": len(record),
            })
            return True

        try:
            target.sendall(record)
        except (BrokenPipeError, ConnectionResetError, socket.timeout):
            return True

        if direction == "server_to_client" and content_type == 20:
            state["server_ccs_seen"] = True
        elif (
            direction == "server_to_client"
            and state.get("server_ccs_seen")
            and content_type == 22
        ):
            _emit({"event": "server_finished_record_forwarded"})
            return True
        elif direction == "server_to_client" and content_type == 21:
            _emit({"event": "server_alert_forwarded"})
            return True
    return False


def probe(
    bind: str,
    port: int,
    connect_timeout: float,
    max_seconds: float,
    once: bool,
    upstream_host: str | None,
    upstream_port: int,
) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((bind, port))
        server.listen(4)
        _emit({"event": "listening", "bind": bind, "port": port})

        while True:
            client, peer = server.accept()
            with client:
                destination = original_destination(client)
                if destination is None and upstream_host is None:
                    _emit({
                        "event": "connection_error",
                        "peer": peer[0],
                        "error": "SO_ORIGINAL_DST unavailable and no upstream fallback",
                    })
                    if once:
                        return
                    continue
                if upstream_host is not None:
                    target_host, target_port = upstream_host, upstream_port
                    destination_source = "explicit"
                else:
                    # A DNAT performed on a different host is not visible to
                    # SO_ORIGINAL_DST here; this branch is mainly useful when
                    # the probe runs on the translating router itself.
                    target_host, target_port = destination  # type: ignore[misc]
                    destination_source = "socket_option"
                _emit({
                    "event": "connection",
                    "peer": peer[0],
                    "peer_port": peer[1],
                    "rewritten_destination": destination[0] if destination else None,
                    "rewritten_port": destination[1] if destination else None,
                    "upstream_destination": target_host,
                    "upstream_port": target_port,
                    "destination_source": destination_source,
                })

                try:
                    upstream = socket.create_connection(
                        (target_host, target_port), timeout=connect_timeout
                    )
                except OSError as exc:
                    _emit({"event": "upstream_error", "error": str(exc)})
                    if once:
                        return
                    continue

                with upstream:
                    client.setblocking(False)
                    upstream.setblocking(False)
                    buffers = {
                        client: RecordBuffer(),
                        upstream: RecordBuffer(),
                    }
                    labels = {
                        client: (upstream, "client_to_server"),
                        upstream: (client, "server_to_client"),
                    }
                    state: dict[str, object] = {"server_ccs_seen": False}
                    deadline = time.monotonic() + max_seconds
                    stop = False
                    while not stop and time.monotonic() < deadline:
                        readable, _, _ = select.select(
                            [client, upstream], [], [], 0.2
                        )
                        if not readable:
                            continue
                        for source in readable:
                            target, direction = labels[source]
                            stop = _forward_records(
                                source,
                                target,
                                buffers[source],
                                direction,
                                state,
                            )
                            if stop:
                                break
                    _emit({
                        "event": "connection_end",
                        "reason": "record_boundary_or_timeout" if stop else "timeout",
                    })
            if once:
                return


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bind", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8883)
    parser.add_argument("--connect-timeout", type=float, default=5.0)
    parser.add_argument("--max-seconds", type=float, default=8.0)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--upstream-host")
    parser.add_argument("--upstream-port", type=int, default=8883)
    args = parser.parse_args()
    probe(
        args.bind,
        args.port,
        args.connect_timeout,
        args.max_seconds,
        args.once,
        args.upstream_host,
        args.upstream_port,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
