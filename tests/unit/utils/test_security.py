"""
Unit tests for security utilities.
"""

import unittest
import os
import sys
from pathlib import Path
import tempfile

# Add src directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../')))

from src.utils.security import (
    validate_url,
    sanitize_filename,
    validate_file_path,
    is_subpath,
    SecurityError
)


class TestValidateUrl(unittest.TestCase):
    """Tests for validate_url function."""

    def test_valid_http_url(self):
        """Test validation of valid HTTP URL."""
        url = "http://example.com/path/to/resource"
        validated = validate_url(url)
        self.assertEqual(validated, url)

    def test_valid_https_url(self):
        """Test validation of valid HTTPS URL."""
        url = "https://example.com/path/to/resource"
        validated = validate_url(url)
        self.assertEqual(validated, url)

    def test_url_with_query_parameters(self):
        """Test URL with query parameters."""
        url = "https://api.example.com/data?id=123&format=json"
        validated = validate_url(url)
        self.assertIn("example.com", validated)
        self.assertIn("id=123", validated)

    def test_url_with_port(self):
        """Test URL with port number."""
        url = "https://example.com:8080/data"
        validated = validate_url(url)
        self.assertIn("8080", validated)

    def test_empty_url_raises_error(self):
        """Test that empty URL raises SecurityError."""
        with self.assertRaises(SecurityError) as ctx:
            validate_url("")
        self.assertIn("non-empty string", str(ctx.exception))

    def test_none_url_raises_error(self):
        """Test that None raises SecurityError."""
        with self.assertRaises(SecurityError) as ctx:
            validate_url(None)
        self.assertIn("non-empty string", str(ctx.exception))

    def test_url_without_scheme_raises_error(self):
        """Test URL without scheme raises SecurityError."""
        with self.assertRaises(SecurityError) as ctx:
            validate_url("example.com/path")
        self.assertIn("scheme", str(ctx.exception).lower())

    def test_url_without_netloc_raises_error(self):
        """Test URL without netloc raises SecurityError."""
        with self.assertRaises(SecurityError) as ctx:
            validate_url("http:///path")
        self.assertIn("domain", str(ctx.exception).lower())

    def test_ftp_scheme_raises_error(self):
        """Test that FTP scheme is not allowed."""
        with self.assertRaises(SecurityError) as ctx:
            validate_url("ftp://example.com/file.txt")
        self.assertIn("not allowed", str(ctx.exception))

    def test_file_scheme_raises_error(self):
        """Test that file:// scheme is not allowed."""
        with self.assertRaises(SecurityError) as ctx:
            validate_url("file:///etc/passwd")
        self.assertIn("not allowed", str(ctx.exception))

    def test_localhost_raises_error(self):
        """Test that localhost is blocked."""
        with self.assertRaises(SecurityError) as ctx:
            validate_url("http://localhost/test")
        self.assertIn("not allowed", str(ctx.exception))

    def test_127_0_0_1_raises_error(self):
        """Test that 127.0.0.1 is blocked."""
        with self.assertRaises(SecurityError) as ctx:
            validate_url("http://127.0.0.1/test")
        self.assertIn("not allowed", str(ctx.exception))

    def test_private_network_192_168_raises_error(self):
        """Test that 192.168.x.x is blocked."""
        with self.assertRaises(SecurityError) as ctx:
            validate_url("http://192.168.1.1/admin")
        self.assertIn("not allowed", str(ctx.exception))

    def test_private_network_10_raises_error(self):
        """Test that 10.x.x.x is blocked."""
        with self.assertRaises(SecurityError) as ctx:
            validate_url("http://10.0.0.1/test")
        self.assertIn("not allowed", str(ctx.exception))

    def test_private_network_172_16_raises_error(self):
        """Test that 172.16.x.x is blocked."""
        with self.assertRaises(SecurityError) as ctx:
            validate_url("http://172.16.0.1/test")
        self.assertIn("not allowed", str(ctx.exception))

    def test_ipv6_localhost_raises_error(self):
        """Test that IPv6 localhost (::1) is blocked."""
        with self.assertRaises(SecurityError) as ctx:
            validate_url("http://[::1]/test")
        self.assertIn("not allowed", str(ctx.exception))

    def test_allowed_domains_restriction(self):
        """Test URL validation with allowed domains."""
        allowed_domains = {'example.com', 'test.com'}

        # Allowed domain
        validated = validate_url("http://example.com/data", allowed_domains)
        self.assertIn("example.com", validated)

        # Disallowed domain
        with self.assertRaises(SecurityError) as ctx:
            validate_url("http://other.com/data", allowed_domains)
        self.assertIn("not in allowed domains", str(ctx.exception))

    def test_subdomain_of_allowed_domain(self):
        """Test that subdomains of allowed domains are permitted."""
        allowed_domains = {'example.com'}

        # Subdomain should be allowed
        validated = validate_url("http://api.example.com/data", allowed_domains)
        self.assertIn("api.example.com", validated)

    def test_url_normalization(self):
        """Test that URLs are normalized."""
        url = "https://EXAMPLE.COM/Path/To/Resource"
        validated = validate_url(url)
        # URL should be normalized (scheme and domain lowercased)
        self.assertTrue(validated.startswith("https://"))


class TestSanitizeFilename(unittest.TestCase):
    """Tests for sanitize_filename function."""

    def test_simple_filename(self):
        """Test sanitizing a simple filename."""
        filename = "test_file.txt"
        sanitized = sanitize_filename(filename)
        self.assertEqual(sanitized, "test_file.txt")

    def test_filename_with_invalid_characters(self):
        """Test removing invalid characters from filename."""
        filename = "test<>:file|?.txt"
        sanitized = sanitize_filename(filename)

        # Invalid characters should be replaced with underscores
        self.assertNotIn('<', sanitized)
        self.assertNotIn('>', sanitized)
        self.assertNotIn(':', sanitized)
        self.assertNotIn('|', sanitized)
        self.assertNotIn('?', sanitized)

    def test_filename_with_path_traversal(self):
        """Test preventing path traversal attacks."""
        filename = "../../etc/passwd"
        sanitized = sanitize_filename(filename)

        # Should only return the base filename
        self.assertEqual(sanitized, "passwd")

    def test_filename_with_backslashes(self):
        """Test handling Windows-style paths."""
        filename = "..\\..\\windows\\system32\\config"
        sanitized = sanitize_filename(filename)

        # Should only return the base filename
        self.assertEqual(sanitized, "config")

    def test_filename_length_limit(self):
        """Test that long filenames are truncated."""
        # Create a 300-character filename
        filename = "a" * 300 + ".txt"
        sanitized = sanitize_filename(filename)

        # Should be truncated to 255 characters
        self.assertLessEqual(len(sanitized), 255)
        # Extension should be preserved
        self.assertTrue(sanitized.endswith(".txt"))

    def test_empty_filename(self):
        """Test handling empty filename."""
        filename = ""
        sanitized = sanitize_filename(filename)

        # Should return a default name
        self.assertEqual(sanitized, "unnamed_file")

    def test_filename_with_only_invalid_chars(self):
        """Test filename consisting only of invalid characters."""
        filename = "<>:|?*"
        sanitized = sanitize_filename(filename)

        # Should return a default name
        self.assertEqual(sanitized, "unnamed_file")

    def test_filename_with_spaces(self):
        """Test that spaces are preserved."""
        filename = "my test file.txt"
        sanitized = sanitize_filename(filename)

        self.assertEqual(sanitized, "my test file.txt")


class TestValidateFilePath(unittest.TestCase):
    """Tests for validate_file_path function."""

    def setUp(self):
        """Set up test fixtures."""
        # Create temporary directory for testing
        self.temp_dir = Path(tempfile.mkdtemp())
        self.test_file = self.temp_dir / "test.txt"
        self.test_file.write_text("test content")

    def tearDown(self):
        """Clean up test fixtures."""
        # Remove test files and directory
        if self.test_file.exists():
            self.test_file.unlink()
        if self.temp_dir.exists():
            self.temp_dir.rmdir()

    def test_valid_existing_file(self):
        """Test validating an existing file."""
        validated = validate_file_path(str(self.test_file))
        self.assertEqual(validated, self.test_file)

    def test_valid_path_in_allowed_dirs(self):
        """Test path validation with allowed directories."""
        allowed_dirs = [self.temp_dir]

        validated = validate_file_path(str(self.test_file), allowed_dirs)
        self.assertEqual(validated, self.test_file)

    def test_path_outside_allowed_dirs_raises_error(self):
        """Test that paths outside allowed directories raise error."""
        other_temp = Path(tempfile.mkdtemp())
        allowed_dirs = [self.temp_dir]

        try:
            with self.assertRaises(SecurityError) as ctx:
                validate_file_path(str(other_temp), allowed_dirs)
            self.assertIn("not in allowed directories", str(ctx.exception))
        finally:
            other_temp.rmdir()

    def test_nonexistent_file_with_existing_parent(self):
        """Test path to nonexistent file with existing parent directory."""
        new_file = self.temp_dir / "new_file.txt"

        # Should succeed if parent exists
        validated = validate_file_path(str(new_file))
        self.assertEqual(validated, new_file.resolve())

    def test_nonexistent_parent_raises_error(self):
        """Test that nonexistent parent directory raises error."""
        nonexistent = "/nonexistent/parent/file.txt"

        with self.assertRaises(SecurityError) as ctx:
            validate_file_path(nonexistent)
        self.assertIn("does not exist", str(ctx.exception).lower())


class TestIsSubpath(unittest.TestCase):
    """Tests for is_subpath function."""

    def setUp(self):
        """Set up test fixtures."""
        self.parent_dir = Path(tempfile.mkdtemp())
        self.child_dir = self.parent_dir / "child"
        self.child_dir.mkdir()

    def tearDown(self):
        """Clean up test fixtures."""
        if self.child_dir.exists():
            self.child_dir.rmdir()
        if self.parent_dir.exists():
            self.parent_dir.rmdir()

    def test_direct_child_is_subpath(self):
        """Test that direct child is recognized as subpath."""
        result = is_subpath(self.child_dir, self.parent_dir)
        self.assertTrue(result)

    def test_grandchild_is_subpath(self):
        """Test that grandchild is recognized as subpath."""
        grandchild = self.child_dir / "grandchild"
        grandchild.mkdir()

        try:
            result = is_subpath(grandchild, self.parent_dir)
            self.assertTrue(result)
        finally:
            grandchild.rmdir()

    def test_parent_is_not_subpath_of_child(self):
        """Test that parent is not a subpath of child."""
        result = is_subpath(self.parent_dir, self.child_dir)
        self.assertFalse(result)

    def test_sibling_is_not_subpath(self):
        """Test that sibling directory is not a subpath."""
        sibling = self.parent_dir / "sibling"
        sibling.mkdir()

        try:
            result = is_subpath(sibling, self.child_dir)
            self.assertFalse(result)
        finally:
            sibling.rmdir()

    def test_unrelated_path_is_not_subpath(self):
        """Test that unrelated paths are not subpaths."""
        other_dir = Path(tempfile.mkdtemp())

        try:
            result = is_subpath(other_dir, self.parent_dir)
            self.assertFalse(result)
        finally:
            other_dir.rmdir()

    def test_same_path_is_subpath(self):
        """Test that a path is considered a subpath of itself."""
        result = is_subpath(self.parent_dir, self.parent_dir)
        self.assertTrue(result)

    def test_path_traversal_attempt(self):
        """Test that path traversal attempts are handled correctly."""
        # Try to use .. to escape
        traversal_path = self.child_dir / ".." / ".."
        result = is_subpath(traversal_path, self.parent_dir)

        # After resolution, this would be outside parent_dir
        self.assertFalse(result)


if __name__ == '__main__':
    unittest.main()
