import ipaddress
import socket

from tools import lan_probe
from tools.lan_probe import is_chamberlain, observed_hosts


def test_arp_only_host_is_retained_even_if_ping_is_silent():
    network = ipaddress.ip_network("192.168.10.0/24")
    ping_results = {
        "192.168.10.10": True,
        "192.168.10.20": False,
    }
    arp = {
        "192.168.10.20": "0C:95:05:12:34:56",
        "192.168.11.30": "44:11:46:00:00:01",
    }

    assert observed_hosts(network, ping_results, arp) == [
        "192.168.10.10",
        "192.168.10.20",
    ]
    assert is_chamberlain(arp["192.168.10.20"])


def test_non_chamberlain_mac_is_not_candidate():
    assert not is_chamberlain("AA:BB:CC:12:34:56")


def test_reverse_name_returns_none_on_lookup_failure(monkeypatch):
    def fail(_ip):
        raise socket.timeout("lookup timed out")

    monkeypatch.setattr(socket, "gethostbyaddr", fail)
    assert lan_probe.reverse_name("192.0.2.1", timeout=0.25) is None


def test_reverse_name_is_bounded_when_platform_lookup_hangs(monkeypatch):
    def hang(_ip):
        import time

        time.sleep(0.1)
        return ("late.example", [], [])

    monkeypatch.setattr(socket, "gethostbyaddr", hang)
    assert lan_probe.reverse_name("192.0.2.1", timeout=0.001) is None
