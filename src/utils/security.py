"""
Security utilities for SurfCastAI.
Provides URL validation, file path sanitization, and other security functions.
"""

import re
import os
from pathlib import Path
from urllib.parse import urlparse, urlunparse, ParseResult
from typing import Set, Optional, List


class SecurityError(Exception):
    """Base exception for security-related errors."""
    pass


def validate_url(url: str, allowed_domains: Optional[Set[str]] = None) -> str:
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
        
        # Require scheme and netloc
        if not parsed.scheme or not parsed.netloc:
            raise SecurityError("URL must include scheme and domain")
        
        # Only allow HTTP(S)
        if parsed.scheme not in ['http', 'https']:
            raise SecurityError(f"URL scheme '{parsed.scheme}' not allowed")
        
        # Check against allowed domains if provided
        if allowed_domains and parsed.netloc not in allowed_domains:
            # Check if it's a subdomain of an allowed domain
            if not any(parsed.netloc.endswith('.' + domain) for domain in allowed_domains):
                raise SecurityError(f"Domain '{parsed.netloc}' not in allowed domains")
        
        # Prevent localhost and private networks
        if parsed.netloc in ['localhost', '127.0.0.1', '::1'] or \
           parsed.netloc.startswith('192.168.') or \
           parsed.netloc.startswith('10.') or \
           parsed.netloc.startswith('172.16.'):
            raise SecurityError(f"Accessing local network '{parsed.netloc}' not allowed")
        
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
    # Remove invalid characters
    sanitized = re.sub(r'[<>:"/\\|?*]', '_', filename)
    
    # Prevent path traversal
    sanitized = os.path.basename(sanitized)
    
    # Limit length
    if len(sanitized) > 255:
        name, ext = os.path.splitext(sanitized)
        sanitized = name[:250 - len(ext)] + ext
    
    # Ensure not empty
    if not sanitized:
        sanitized = 'unnamed_file'
    
    return sanitized


def validate_file_path(path: str, allowed_dirs: Optional[List[Path]] = None) -> Path:
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
        file_path = Path(path).resolve()
        
        # Check if path exists
        if not file_path.exists():
            parent_dir = file_path.parent
            if not parent_dir.exists():
                raise SecurityError(f"Parent directory does not exist: {parent_dir}")
        
        # Check if path is within allowed directories
        if allowed_dirs:
            if not any(is_subpath(file_path, allowed_dir) for allowed_dir in allowed_dirs):
                raise SecurityError(f"Path not in allowed directories: {file_path}")
        
        return file_path
    
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