from tools.router_traffic_summary import summarize


def test_summary_reports_public_endpoints_and_redacts_candidate():
    candidate = "192.168.50.44"
    capture = f"""
ipv4 2 tcp 6 431999 ESTABLISHED src={candidate} dst=18.1.2.3 sport=50000 dport=8883 src=18.1.2.3 dst={candidate} sport=8883 dport=50000
ipv4 2 tcp 6 120 ESTABLISHED src={candidate} dst=34.2.3.4 sport=50001 dport=443 src=34.2.3.4 dst={candidate} sport=443 dport=50001
ipv4 2 udp 17 20 src={candidate} dst=192.168.50.1 sport=54000 dport=53 src=192.168.50.1 dst={candidate} sport=53 dport=54000
"""

    report = summarize(capture, candidate)

    assert report["candidate_ip"] == "<redacted-g0401-lan-ip>"
    assert candidate not in str(report)
    assert report["destination_ports"] == {"443": 1, "8883": 1}
    assert report["baseline_8883_only"] is False
    assert {row["protocol"] for row in report["endpoints"]} == {"tcp"}


def test_summary_aggregates_duplicate_observations():
    candidate = "192.168.50.44"
    row = f"tcp 6 100 ESTABLISHED src={candidate} dst=18.1.2.3 sport=50000 dport=8883 src=18.1.2.3 dst={candidate} sport=8883 dport=50000"
    report = summarize(f"{row}\n{row}\n", candidate)
    assert report["destination_ports"] == {"8883": 2}
    assert report["endpoints"][0]["count"] == 2
    assert report["baseline_8883_only"] is True


def test_summary_classifies_known_and_novel_hostnames():
    candidate = "192.168.50.44"
    capture = f"""
dnsmasq: query[A] connect.myqdevice.com from {candidate}
dnsmasq: query[A] firmware.example.net from {candidate}
tcp 6 100 ESTABLISHED src={candidate} dst=18.1.2.3 sport=50000 dport=8883
"""
    report = summarize(capture, candidate)

    assert report["known_connection_hosts_seen"] == ["connect.myqdevice.com"]
    assert report["other_hostnames_seen"] == ["firmware.example.net"]
    assert candidate not in str(report)


def test_summary_ignores_unrelated_device_conntrack():
    candidate = "192.168.50.44"
    capture = "tcp 6 100 ESTABLISHED src=192.168.50.99 dst=8.8.8.8 sport=1 dport=443"
    report = summarize(capture, candidate)
    assert report["endpoints"] == []
    assert report["destination_ports"] == {}
    assert report["baseline_8883_only"] is False


def test_summary_parses_passive_tcpdump_and_dns_name():
    candidate = "192.168.50.44"
    capture = (
        f"22:00:00 IP {candidate}.50123 > 34.5.6.7.443: Flags [S]\n"
        f"22:00:01 IP {candidate}.53000 > 192.168.50.1.53: "
        "1234+ A? ota.example.net. (33)"
    )
    report = summarize(capture, candidate)
    assert report["destination_ports"] == {"443": 1}
    assert report["other_hostnames_seen"] == ["ota.example.net"]
    assert candidate not in str(report)
