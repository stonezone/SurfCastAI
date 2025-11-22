"""
Security utilities for SurfCastAI.
Provides URL validation, file path sanitization, and other security functions.
"""

import os
import re
import socket
from ipaddress import ip_address, ip_network
from pathlib import Path
from urllib.parse import urlparse, urlunparse

from .exceptions import SecurityError


def is_private_ip(hostname: str) -> bool:
    """
    Check if hostname resolves to a private IP address.

    Detects all private IP ranges including:
    - RFC 1918 private networks (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16)
    - Link-local addresses (169.254.0.0/16)
    - Loopback addresses (127.0.0.0/8)
    - IPv6 unique local addresses (fc00::/7)
    - IPv6 link-local addresses (fe80::/10)
    - IPv6 loopback (::1/128)

    Args:
        hostname: Hostname or IP address to check

    Returns:
        True if hostname resolves to a private IP address, False otherwise
    """
    # Define all private IP ranges
    private_ranges = [
        # IPv4 private ranges
        ip_network("10.0.0.0/8"),  # RFC 1918 - Class A private network
        ip_network("172.16.0.0/12"),  # RFC 1918 - Class B private networks
        ip_network("192.168.0.0/16"),  # RFC 1918 - Class C private networks
        ip_network("169.254.0.0/16"),  # RFC 3927 - Link-local
        ip_network("127.0.0.0/8"),  # RFC 1122 - Loopback
        # IPv6 private ranges
        ip_network("fc00::/7"),  # RFC 4193 - Unique local addresses
        ip_network("fe80::/10"),  # RFC 4291 - Link-local
        ip_network("::1/128"),  # RFC 4291 - Loopback
    ]

    try:
        # Try to parse as IP address directly
        addr = ip_address(hostname)

        # Check if address falls within any private range
        return any(addr in network for network in private_ranges)

    except ValueError:
        # Not a valid IP address, might be a hostname
        # Try to resolve hostname to IP address
        try:
            resolved_ip = socket.gethostbyname(hostname)
            # Recursively check the resolved IP
            return is_private_ip(resolved_ip)
        except (OSError, socket.gaierror):
            # Unable to resolve hostname
            # For security, assume it's not private and let URL validation handle it
            return False


def validate_url(url: str, allowed_domains: set[str] | None = None) -> str:
    """
    Validate URL for security and correctness.

    Args:
        url: URL to validate
        allowed_domains: Optional set of allowed domains

    Returns:
        Validated URL

    Raises:
        SecurityError: If URL is invalid or disallowed
    """
    # Basic validation
    if not url or not isinstance(url, str):
        raise SecurityError("URL must be a non-empty string")

    # Ensure URL is properly formed
    try:
        parsed = urlparse(url)

        # Require scheme first so error messages surface correct root cause
        if not parsed.scheme:
            raise SecurityError("URL must include scheme and domain")

        # Only allow HTTP(S)
        if parsed.scheme not in ["http", "https"]:
            raise SecurityError(f"URL scheme '{parsed.scheme}' not allowed")

        if not parsed.netloc:
            raise SecurityError("URL must include domain")

        # Check against allowed domains if provided
        if allowed_domains and parsed.netloc not in allowed_domains:
            # Check if it's a subdomain of an allowed domain
            if not any(parsed.netloc.endswith("." + domain) for domain in allowed_domains):
                raise SecurityError(f"Domain '{parsed.netloc}' not in allowed domains")

        # Prevent SSRF attacks - block all private/internal IP addresses
        # Extract hostname (netloc includes port, so split it off)
        hostname = parsed.hostname or parsed.netloc

        # Use comprehensive private IP detection
        if is_private_ip(hostname):
            raise SecurityError(
                f"Accessing private network '{hostname}' not allowed (SSRF protection)"
            )

        # Rebuild URL to normalize components
        normalized_url = urlunparse(parsed)

        return normalized_url

    except Exception as e:
        if isinstance(e, SecurityError):
            raise
        raise SecurityError(f"Invalid URL: {e}")


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename for safe file system use.

    Args:
        filename: Original filename

    Returns:
        Sanitized filename
    """
    if not filename:
        return "unnamed_file"

    # Prevent path traversal and strip surrounding whitespace
    normalized = str(filename).replace("\\", "/")
    sanitized = os.path.basename(normalized).strip()

    # Whitelist characters: letters, numbers, space, dash, underscore, dot
    sanitized = re.sub(r"[^A-Za-z0-9._\- ]+", "", sanitized)

    # Collapse repeated whitespace
    sanitized = re.sub(r"\s+", " ", sanitized).strip()

    if not sanitized:
        sanitized = "unnamed_file"

    # Limit length while preserving extension
    if len(sanitized) > 255:
        name, ext = os.path.splitext(sanitized)
        ext = ext[:10]  # guard extreme extensions
        sanitized = name[: 255 - len(ext)] + ext

    return sanitized


def validate_file_path(path: str, allowed_dirs: list[Path] | None = None) -> Path:
    """
    Validate file path for security.

    Args:
        path: File path to validate
        allowed_dirs: Optional list of allowed directories

    Returns:
        Validated Path object

    Raises:
        SecurityError: If path is invalid or disallowed
    """
    try:
        candidate = Path(path)
        resolved = candidate.resolve()

        # Check if path exists
        exists = resolved.exists()
        if not exists:
            parent_dir = resolved.parent
            if not parent_dir.exists():
                raise SecurityError(f"Parent directory does not exist: {parent_dir}")

        # Check if path is within allowed directories
        if allowed_dirs:
            allowed_resolved = [Path(p).resolve() for p in allowed_dirs]
            if not any(is_subpath(resolved, allowed_dir) for allowed_dir in allowed_resolved):
                raise SecurityError(f"Path not in allowed directories: {resolved}")

        return candidate if exists else resolved

    except Exception as e:
        if isinstance(e, SecurityError):
            raise
        raise SecurityError(f"Invalid file path: {e}")


def is_subpath(path: Path, parent: Path) -> bool:
    """
    Check if path is a subpath of parent.

    Args:
        path: Path to check
        parent: Parent path

    Returns:
        True if path is a subpath of parent
    """
    try:
        resolved_path = path.resolve()
        resolved_parent = parent.resolve()

        # Path.is_relative_to() in Python 3.9+
        # For earlier versions, use this workaround
        try:
            resolved_path.relative_to(resolved_parent)
            return True
        except ValueError:
            return False

    except Exception:
        return False
