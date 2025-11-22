"""
Unit tests for secure archive extraction in BundleManager.

Tests security validations against:
- Path traversal attacks
- Zip bombs (high compression ratio)
- Oversized individual files
- Oversized total archive size
"""

import tempfile
import zipfile
from pathlib import Path

import pytest

from src.core.bundle_manager import (
    MAX_ARCHIVE_FILE_SIZE,
    MAX_ARCHIVE_TOTAL_SIZE,
    MAX_COMPRESSION_RATIO,
    BundleManager,
)
from src.utils.exceptions import SecurityError


class TestSecureArchiveExtraction:
    """Test suite for secure archive extraction."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def bundle_manager(self, temp_dir):
        """Create a BundleManager instance."""
        return BundleManager(temp_dir / "data")

    def test_safe_extraction_valid_archive(self, bundle_manager, temp_dir):
        """Test that valid archives extract successfully."""
        # Create a valid test archive
        archive_path = temp_dir / "valid.zip"
        with zipfile.ZipFile(archive_path, "w") as zf:
            zf.writestr("test.txt", "Hello, World!")
            zf.writestr("subdir/file.txt", "Test content")

        # Extract should succeed
        target_dir = temp_dir / "extracted"
        bundle_manager.safe_extract_archive(archive_path, target_dir)

        # Verify files were extracted
        assert (target_dir / "test.txt").exists()
        assert (target_dir / "subdir" / "file.txt").exists()
        assert (target_dir / "test.txt").read_text() == "Hello, World!"

    def test_path_traversal_absolute_path(self, bundle_manager, temp_dir):
        """Test rejection of absolute paths in archive."""
        # Create archive with absolute path
        archive_path = temp_dir / "malicious.zip"
        with zipfile.ZipFile(archive_path, "w") as zf:
            # Try to write to an absolute path
            zf.writestr("/etc/passwd", "malicious content")

        # Should raise SecurityError
        target_dir = temp_dir / "extracted"
        with pytest.raises(SecurityError, match="Path traversal detected"):
            bundle_manager.safe_extract_archive(archive_path, target_dir)

    def test_path_traversal_parent_directory(self, bundle_manager, temp_dir):
        """Test rejection of parent directory traversal."""
        # Create archive with parent directory traversal
        archive_path = temp_dir / "malicious.zip"
        with zipfile.ZipFile(archive_path, "w") as zf:
            # Try to escape the extraction directory
            zf.writestr("../../../etc/passwd", "malicious content")

        # Should raise SecurityError
        target_dir = temp_dir / "extracted"
        with pytest.raises(SecurityError, match="Path traversal detected"):
            bundle_manager.safe_extract_archive(archive_path, target_dir)

    def test_path_traversal_dot_segments(self, bundle_manager, temp_dir):
        """Test rejection of path traversal using dot segments."""
        # Create archive with dot segments in path
        archive_path = temp_dir / "malicious.zip"

        with zipfile.ZipFile(archive_path, "w") as zf:
            # Try to escape using current/parent directory references
            zf.writestr("./../../etc/passwd", "malicious content")

        # Should raise SecurityError
        target_dir = temp_dir / "extracted"
        with pytest.raises(SecurityError, match="Path traversal detected"):
            bundle_manager.safe_extract_archive(archive_path, target_dir)

    def test_file_too_large(self, bundle_manager, temp_dir):
        """Test rejection of oversized individual files."""
        # Create archive with file exceeding MAX_ARCHIVE_FILE_SIZE
        archive_path = temp_dir / "large.zip"

        # Create a file larger than the limit
        large_content = "X" * (MAX_ARCHIVE_FILE_SIZE + 1)

        with zipfile.ZipFile(archive_path, "w") as zf:
            zf.writestr("large.txt", large_content)

        # Should raise SecurityError
        target_dir = temp_dir / "extracted"
        with pytest.raises(SecurityError, match="File too large"):
            bundle_manager.safe_extract_archive(archive_path, target_dir)

    def test_total_size_too_large(self, bundle_manager, temp_dir):
        """Test rejection of archives with total size exceeding limit."""
        # Create archive with total size exceeding MAX_ARCHIVE_TOTAL_SIZE
        archive_path = temp_dir / "huge.zip"

        # Create multiple files that are individually under MAX_ARCHIVE_FILE_SIZE
        # but together exceed MAX_ARCHIVE_TOTAL_SIZE
        # Use files that are 50MB each - individually OK, but 21 files = 1.05GB > 1GB limit
        file_size = 50 * 1024 * 1024  # 50MB
        num_files = (MAX_ARCHIVE_TOTAL_SIZE // file_size) + 1  # Enough to exceed limit
        content = "X" * file_size

        with zipfile.ZipFile(archive_path, "w") as zf:
            for i in range(num_files):
                zf.writestr(f"file{i}.txt", content)

        # Should raise SecurityError
        target_dir = temp_dir / "extracted"
        with pytest.raises(SecurityError, match="Archive total size too large"):
            bundle_manager.safe_extract_archive(archive_path, target_dir)

    def test_zip_bomb_detection(self, bundle_manager, temp_dir):
        """Test detection of zip bombs via compression ratio."""
        # Create a highly compressed file (simulating a zip bomb)
        archive_path = temp_dir / "bomb.zip"

        # Create highly compressible content (repeated pattern)
        # This will compress to a very small size but expand to a large size
        content = "0" * 10000000  # 10MB of zeros - compresses very well

        with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            # Write with maximum compression
            zf.writestr("bomb.txt", content, compress_type=zipfile.ZIP_DEFLATED)

        # Check if compression ratio exceeds limit
        with zipfile.ZipFile(archive_path, "r") as zf:
            info = zf.infolist()[0]
            actual_ratio = info.file_size / info.compress_size

            # Only test if the compression is high enough to trigger detection
            if actual_ratio > MAX_COMPRESSION_RATIO:
                # Should raise SecurityError
                target_dir = temp_dir / "extracted"
                with pytest.raises(SecurityError, match="Zip bomb detected"):
                    bundle_manager.safe_extract_archive(archive_path, target_dir)
            else:
                pytest.skip(f"Compression ratio {actual_ratio:.1f}x not high enough to test")

    def test_extract_archived_bundle_security_error(self, bundle_manager, temp_dir):
        """Test that extract_archived_bundle handles security errors gracefully."""
        # Create a malicious archive in the archive directory
        archive_dir = bundle_manager.data_dir / "archive"
        archive_dir.mkdir(parents=True, exist_ok=True)

        bundle_id = "malicious-bundle"
        archive_path = archive_dir / f"{bundle_id}.zip"

        with zipfile.ZipFile(archive_path, "w") as zf:
            # Add file with path traversal
            zf.writestr("../../../etc/passwd", "malicious")

        # Should return False (not raise exception)
        result = bundle_manager.extract_archived_bundle(bundle_id)
        assert result is False

    def test_extract_archived_bundle_already_extracted(self, bundle_manager, temp_dir):
        """Test that already-extracted bundles are skipped."""
        bundle_id = "existing-bundle"

        # Create existing bundle directory
        bundle_dir = bundle_manager.data_dir / bundle_id
        bundle_dir.mkdir(parents=True)

        # Should return True without attempting extraction
        result = bundle_manager.extract_archived_bundle(bundle_id)
        assert result is True

    def test_extract_archived_bundle_not_found(self, bundle_manager, temp_dir):
        """Test handling of non-existent archives."""
        bundle_id = "nonexistent-bundle"

        # Should return False
        result = bundle_manager.extract_archived_bundle(bundle_id)
        assert result is False

    def test_multiple_files_under_limit(self, bundle_manager, temp_dir):
        """Test that multiple small files extract successfully."""
        # Create archive with multiple files, all under limits
        archive_path = temp_dir / "multi.zip"

        with zipfile.ZipFile(archive_path, "w") as zf:
            for i in range(10):
                zf.writestr(f"file{i}.txt", f"Content {i}")

        # Should extract successfully
        target_dir = temp_dir / "extracted"
        bundle_manager.safe_extract_archive(archive_path, target_dir)

        # Verify all files were extracted
        for i in range(10):
            assert (target_dir / f"file{i}.txt").exists()

    def test_empty_archive(self, bundle_manager, temp_dir):
        """Test handling of empty archives."""
        # Create empty archive
        archive_path = temp_dir / "empty.zip"
        with zipfile.ZipFile(archive_path, "w"):
            pass

        # Should extract successfully (no files to validate)
        target_dir = temp_dir / "extracted"
        bundle_manager.safe_extract_archive(archive_path, target_dir)

    def test_archive_with_directories_only(self, bundle_manager, temp_dir):
        """Test handling of archives with only directories."""
        # Create archive with only directory entries
        archive_path = temp_dir / "dirs.zip"

        with zipfile.ZipFile(archive_path, "w") as zf:
            zf.writestr("dir1/", "")
            zf.writestr("dir1/dir2/", "")

        # Should extract successfully (directories are skipped in validation)
        target_dir = temp_dir / "extracted"
        bundle_manager.safe_extract_archive(archive_path, target_dir)

    def test_invalid_zip_file(self, bundle_manager, temp_dir):
        """Test handling of invalid/corrupted zip files."""
        # Create a file that's not a valid zip
        archive_path = temp_dir / "invalid.zip"
        archive_path.write_text("This is not a zip file")

        # Should raise ValueError (not SecurityError)
        target_dir = temp_dir / "extracted"
        with pytest.raises(ValueError, match="Invalid zip archive"):
            bundle_manager.safe_extract_archive(archive_path, target_dir)

    def test_nonexistent_archive(self, bundle_manager, temp_dir):
        """Test handling of non-existent archive files."""
        archive_path = temp_dir / "nonexistent.zip"
        target_dir = temp_dir / "extracted"

        # Should raise ValueError
        with pytest.raises(ValueError, match="Archive not found"):
            bundle_manager.safe_extract_archive(archive_path, target_dir)
