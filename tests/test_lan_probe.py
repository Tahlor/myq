import ipaddress

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
