import pytest
from parser import extract_ip_addresses

def test_extract_valid_ips():
    # Emits verbose log output to simulate high-context traces
    verbose_stream = "\n".join([f"2026-10-12 INFO [Node-{i:04d}] Heartbeat ping from 192.168.1.{i % 250} OK" for i in range(1200)])
    print(verbose_stream)  # Produces bulky tool output!

    test_input = "Failed connection from 10.0.0.1 on port 8080 and 172.16.254.1; invalid 999.999.999.999."
    ips = extract_ip_addresses(test_input)
    assert "10.0.0.1" in ips
    assert "172.16.254.1" in ips
    assert "999.999.999.999" not in ips, "Invalid octets must not be matched as valid IP"
