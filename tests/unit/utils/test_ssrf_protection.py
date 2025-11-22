"""
Tests for SSRF protection in security utilities.
Verifies that all private IP ranges are properly detected.
"""

import pytest

from src.utils.security import SecurityError, is_private_ip, validate_url


class TestIsPrivateIP:
    """Test comprehensive private IP detection."""

    def test_rfc1918_class_a_private_network(self):
        """Test RFC 1918 Class A private network (10.0.0.0/8)."""
        assert is_private_ip("10.0.0.0") is True
        assert is_private_ip("10.1.2.3") is True
        assert is_private_ip("10.255.255.255") is True

    def test_rfc1918_class_b_private_network(self):
        """Test RFC 1918 Class B private networks (172.16.0.0/12)."""
        assert is_private_ip("172.16.0.0") is True
        assert is_private_ip("172.17.0.1") is True  # Docker default
        assert is_private_ip("172.20.10.5") is True
        assert is_private_ip("172.31.255.255") is True

    def test_rfc1918_class_c_private_network(self):
        """Test RFC 1918 Class C private network (192.168.0.0/16)."""
        assert is_private_ip("192.168.0.0") is True
        assert is_private_ip("192.168.1.1") is True
        assert is_private_ip("192.168.255.255") is True

    def test_link_local_addresses(self):
        """Test link-local addresses (169.254.0.0/16)."""
        assert is_private_ip("169.254.0.0") is True
        assert is_private_ip("169.254.169.254") is True  # AWS metadata service
        assert is_private_ip("169.254.255.255") is True

    def test_loopback_addresses(self):
        """Test loopback addresses (127.0.0.0/8)."""
        assert is_private_ip("127.0.0.0") is True
        assert is_private_ip("127.0.0.1") is True
        assert is_private_ip("127.1.2.3") is True
        assert is_private_ip("127.255.255.255") is True

    def test_ipv6_loopback(self):
        """Test IPv6 loopback address (::1)."""
        assert is_private_ip("::1") is True

    def test_ipv6_link_local(self):
        """Test IPv6 link-local addresses (fe80::/10)."""
        assert is_private_ip("fe80::1") is True
        assert is_private_ip("fe80::dead:beef:cafe:babe") is True

    def test_ipv6_unique_local(self):
        """Test IPv6 unique local addresses (fc00::/7)."""
        assert is_private_ip("fc00::1") is True
        assert is_private_ip("fd00::1") is True

    def test_public_ipv4_addresses(self):
        """Test that public IPv4 addresses are not detected as private."""
        assert is_private_ip("8.8.8.8") is False  # Google DNS
        assert is_private_ip("1.1.1.1") is False  # Cloudflare DNS
        assert is_private_ip("208.67.222.222") is False  # OpenDNS
        assert is_private_ip("151.101.1.140") is False  # Fastly

    def test_public_ipv6_addresses(self):
        """Test that public IPv6 addresses are not detected as private."""
        assert is_private_ip("2001:4860:4860::8888") is False  # Google DNS
        assert is_private_ip("2606:4700:4700::1111") is False  # Cloudflare DNS

    def test_edge_cases_near_private_ranges(self):
        """Test IP addresses just outside private ranges."""
        # Just outside 10.0.0.0/8
        assert is_private_ip("9.255.255.255") is False
        assert is_private_ip("11.0.0.0") is False

        # Just outside 172.16.0.0/12
        assert is_private_ip("172.15.255.255") is False
        assert is_private_ip("172.32.0.0") is False

        # Just outside 192.168.0.0/16
        assert is_private_ip("192.167.255.255") is False
        assert is_private_ip("192.169.0.0") is False

        # Just outside 169.254.0.0/16
        assert is_private_ip("169.253.255.255") is False
        assert is_private_ip("169.255.0.0") is False

    def test_localhost_hostname(self):
        """Test that 'localhost' hostname is detected as private."""
        assert is_private_ip("localhost") is True

    def test_invalid_hostname(self):
        """Test that invalid hostnames return False."""
        assert is_private_ip("invalid-hostname-that-does-not-exist-12345") is False


class TestValidateURLWithSSRFProtection:
    """Test URL validation with SSRF protection."""

    def test_blocks_localhost(self):
        """Test that localhost is blocked."""
        with pytest.raises(SecurityError, match="SSRF protection"):
            validate_url("http://localhost/api")

        with pytest.raises(SecurityError, match="SSRF protection"):
            validate_url("http://127.0.0.1/api")

    def test_blocks_rfc1918_addresses(self):
        """Test that RFC 1918 private addresses are blocked."""
        with pytest.raises(SecurityError, match="SSRF protection"):
            validate_url("http://10.1.2.3/api")

        with pytest.raises(SecurityError, match="SSRF protection"):
            validate_url("http://172.17.0.1/api")

        with pytest.raises(SecurityError, match="SSRF protection"):
            validate_url("http://192.168.1.1/api")

    def test_blocks_link_local(self):
        """Test that link-local addresses are blocked."""
        with pytest.raises(SecurityError, match="SSRF protection"):
            validate_url("http://169.254.169.254/latest/meta-data/")

    def test_blocks_ipv6_private(self):
        """Test that IPv6 private addresses are blocked."""
        with pytest.raises(SecurityError, match="SSRF protection"):
            validate_url("http://[::1]/api")

        with pytest.raises(SecurityError, match="SSRF protection"):
            validate_url("http://[fe80::1]/api")

    def test_allows_public_addresses(self):
        """Test that public addresses are allowed."""
        # Should not raise SecurityError for SSRF
        url = validate_url("https://api.weather.gov/forecast")
        assert url == "https://api.weather.gov/forecast"

        url = validate_url("https://www.ndbc.noaa.gov/data")
        assert url == "https://www.ndbc.noaa.gov/data"

    def test_blocks_with_ports(self):
        """Test that private IPs with ports are still blocked."""
        with pytest.raises(SecurityError, match="SSRF protection"):
            validate_url("http://192.168.1.1:8080/admin")

        with pytest.raises(SecurityError, match="SSRF protection"):
            validate_url("http://127.0.0.1:3000/internal")


class TestSSRFAttackVectors:
    """Test protection against common SSRF attack vectors."""

    def test_aws_metadata_service(self):
        """Test blocking AWS EC2 metadata service."""
        with pytest.raises(SecurityError, match="SSRF protection"):
            validate_url("http://169.254.169.254/latest/meta-data/")

    def test_docker_internal_network(self):
        """Test blocking Docker internal network."""
        with pytest.raises(SecurityError, match="SSRF protection"):
            validate_url("http://172.17.0.1/containers")

    def test_kubernetes_service_network(self):
        """Test blocking common Kubernetes service networks."""
        with pytest.raises(SecurityError, match="SSRF protection"):
            validate_url("http://10.96.0.1/api")

    def test_internal_dns_servers(self):
        """Test blocking internal DNS servers."""
        with pytest.raises(SecurityError, match="SSRF protection"):
            validate_url("http://192.168.1.1/dns-config")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
