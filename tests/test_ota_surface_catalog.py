from pathlib import Path

from tools.ota_surface_catalog import catalog_path


def test_catalog_reports_categories_and_hash_without_payload(tmp_path: Path):
    artifact = tmp_path / "strings.txt"
    secret = "PSK=do-not-print"
    artifact.write_text(
        "OTA firmware update manifest\n"
        "Realtek RTL8720CS 6220N-IS GD25Q64 UART_LOG\n"
        f"TLS_PSK provisioning myq_aes {secret}\n",
        encoding="utf-8",
    )

    report = catalog_path(tmp_path)

    assert report["payloads_emitted"] is False
    assert len(report["files_with_signals"]) == 1
    entry = report["files_with_signals"][0]
    assert entry["path"] == "strings.txt"
    assert len(entry["sha256"]) == 64
    assert {item["signal"] for item in entry["signals"]["ota"]} >= {
        "ota",
        "firmware",
        "manifest",
    }
    assert {item["signal"] for item in entry["signals"]["realtek_amebad"]} >= {
        "rtl8720cs",
        "6220n_is",
        "gd25q64",
    }
    assert {item["signal"] for item in entry["signals"]["psk_provisioning"]} >= {
        "tls_psk",
        "provision",
        "myq_aes",
    }
    assert secret not in str(report)


def test_catalog_hashes_large_files_but_bounds_text_scan(tmp_path: Path):
    artifact = tmp_path / "large.bin"
    artifact.write_bytes(b"A" * 32 + b" RTL8720CS " + b"B" * 64)

    report = catalog_path(tmp_path, max_scan_bytes=32)

    assert report["files_with_signals"] == []
