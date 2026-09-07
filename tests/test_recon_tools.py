from __future__ import annotations

import struct

from tools.myq_firmware_psm import (
    find_psm_record,
    unwrap_myq_aes,
)
from tools.setup_portal_capture import extract_endpoint_candidates, same_origin_asset
from tools.tls_clienthello_listener import parse_client_hello
from tools.tls_transparent_probe import RecordBuffer, summarize_record


def test_extract_endpoint_candidates_is_sanitized_and_relevant():
    text = r'''
    const scan = "/api/wifi/scan?token=secret";
    const status = 'http://setup.myqdevice.com/device/status?serial=private';
    const irrelevant = '/images/logo.png';
    const broker = "wss://example.local/mqtt?auth=secret";
    '''
    assert extract_endpoint_candidates([text]) == [
        "/api/wifi/scan",
        "http://setup.myqdevice.com/device/status",
        "wss://example.local/mqtt",
    ]


def test_same_origin_asset_rejects_external_hosts():
    base = "http://192.168.10.1/index.html"
    assert same_origin_asset(base, "/app.js") == "http://192.168.10.1/app.js"
    assert same_origin_asset(base, "styles/main.css") == "http://192.168.10.1/styles/main.css"
    assert same_origin_asset(base, "https://cdn.example/app.js") is None


def _extension(ext_type: int, body: bytes) -> bytes:
    return struct.pack("!HH", ext_type, len(body)) + body


def _client_hello(sni: str = "broker.example", alpn: str = "mqtt") -> bytes:
    # Minimal structurally valid ClientHello sufficient for our passive parser.
    server_name = sni.encode()
    sni_entry = b"\x00" + struct.pack("!H", len(server_name)) + server_name
    sni_body = struct.pack("!H", len(sni_entry)) + sni_entry

    proto = alpn.encode()
    alpn_list = bytes([len(proto)]) + proto
    alpn_body = struct.pack("!H", len(alpn_list)) + alpn_list

    extensions = _extension(0, sni_body) + _extension(16, alpn_body)
    hello = (
        b"\x03\x03"  # client legacy version
        + bytes(range(32))
        + b"\x00"  # session id length
        + struct.pack("!H", 2)
        + b"\x13\x01"  # one cipher suite
        + b"\x01\x00"  # one null compression method
        + struct.pack("!H", len(extensions))
        + extensions
    )
    handshake = b"\x01" + len(hello).to_bytes(3, "big") + hello
    return b"\x16\x03\x01" + struct.pack("!H", len(handshake)) + handshake


def test_parse_tls_clienthello_extracts_sni_and_alpn():
    summary = parse_client_hello(_client_hello(), ("192.168.1.55", 54321))
    assert summary.parse_error is None
    assert summary.peer == "192.168.1.55"
    assert summary.handshake_type == 1
    assert summary.sni == "broker.example"
    assert summary.alpn == ["mqtt"]
    assert summary.cipher_count == 1
    assert summary.cipher_suites == ["0x1301"]
    assert 0 in summary.extension_types
    assert 16 in summary.extension_types


def test_parse_non_tls_payload_reports_error_without_throwing():
    summary = parse_client_hello(b"HELLO WORLD", ("127.0.0.1", 1))
    assert summary.parse_error


def test_transparent_probe_summarizes_client_ciphers_and_record_boundaries():
    record = _client_hello()
    summary = summarize_record(record, "client_to_server")
    assert summary["content_name"] == "handshake"
    assert summary["handshake_types"] == [1]
    assert summary["client_cipher_suites"] == ["0x1301"]

    tracker = RecordBuffer()
    assert list(tracker.feed(record[:7])) == []
    assert list(tracker.feed(record[7:])) == [record]


def test_transparent_probe_extracts_server_selected_cipher():
    hello = b"\x03\x03" + bytes(range(32)) + b"\x00\x00\x2f\x00"
    handshake = b"\x02" + len(hello).to_bytes(3, "big") + hello
    record = b"\x16\x03\x03" + struct.pack("!H", len(handshake)) + handshake
    summary = summarize_record(record, "server_to_client")
    assert summary["handshake_types"] == [2]
    assert summary["server_selected_cipher"] == "0x002f"


def test_transparent_probe_reports_psk_identity_length_without_identity():
    identity = b"1234567890"
    exchange = struct.pack("!H", len(identity)) + identity
    handshake = b"\x10" + len(exchange).to_bytes(3, "big") + exchange
    record = b"\x16\x03\x03" + struct.pack("!H", len(handshake)) + handshake
    summary = summarize_record(record, "client_to_server")
    assert summary["handshake_types"] == [16]
    assert summary["client_psk_identity_length"] == 10


def test_firmware_psm_finds_named_myq_aes_record_without_value_logging():
    value = bytes(range(16))
    record = (
        b"\x55\xAA\xFF"
        + b"\x00\x00\x00\x00"
        + b"\x10\x00\x03\x00\x07"
        + b"myq_aes"
        + value
    )
    parsed = find_psm_record(b"prefix" + record + b"\xFF" * 8, "myq_aes")
    assert parsed is not None
    assert parsed.record_type == 0x10
    assert parsed.index == 3
    assert parsed.value == value


def test_firmware_psm_unwrap_matches_disassembled_tea_vector():
    # Synthetic vector for plaintext b"0123456789ABCDEF"; it contains no
    # device-derived material.
    wrapped = bytes.fromhex("12f31c46782c932eac4eed494287225f")
    assert unwrap_myq_aes(wrapped) == b"0123456789ABCDEF"
