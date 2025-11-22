"""Unit tests for atomic bundle marker updates."""

import tempfile
from pathlib import Path
import pytest

from src.core.bundle_manager import BundleManager


class TestAtomicMarkerUpdates:
    """Test atomic marker file operations."""

    def test_atomic_write_creates_marker(self, tmp_path):
        """Test that atomic write creates marker file correctly."""
        manager = BundleManager(tmp_path)
        bundle_id = "test-bundle-123"

        # Set the marker
        manager.set_latest_bundle(bundle_id)

        # Verify marker file exists and contains correct ID
        marker_file = tmp_path / "latest_bundle.txt"
        assert marker_file.exists()
        assert marker_file.read_text() == bundle_id

    def test_atomic_write_overwrites_existing_marker(self, tmp_path):
        """Test that atomic write correctly overwrites existing marker."""
        manager = BundleManager(tmp_path)

        # Write first marker
        first_id = "bundle-001"
        manager.set_latest_bundle(first_id)

        marker_file = tmp_path / "latest_bundle.txt"
        assert marker_file.read_text() == first_id

        # Overwrite with second marker
        second_id = "bundle-002"
        manager.set_latest_bundle(second_id)

        assert marker_file.read_text() == second_id

    def test_atomic_write_removes_marker_on_none(self, tmp_path):
        """Test that passing None removes the marker file."""
        manager = BundleManager(tmp_path)

        # Create a marker
        bundle_id = "test-bundle-456"
        manager.set_latest_bundle(bundle_id)

        marker_file = tmp_path / "latest_bundle.txt"
        assert marker_file.exists()

        # Remove marker by passing None
        manager.set_latest_bundle(None)

        assert not marker_file.exists()

    def test_atomic_write_no_leftover_temp_files(self, tmp_path):
        """Test that atomic write doesn't leave temp files behind."""
        manager = BundleManager(tmp_path)
        bundle_id = "test-bundle-789"

        # Set the marker
        manager.set_latest_bundle(bundle_id)

        # Check for any temp files (should be none)
        temp_files = list(tmp_path.glob("tmp*"))
        temp_files.extend(tmp_path.glob("*.tmp"))

        assert len(temp_files) == 0, f"Found temp files: {temp_files}"

    def test_atomic_write_cleanup_on_failure(self, tmp_path, monkeypatch):
        """Test that temp file is cleaned up on failure."""
        manager = BundleManager(tmp_path)
        bundle_id = "test-bundle-fail"

        # Track temp file paths
        temp_file_created = None
        original_rename = Path.rename

        def failing_rename(self, target):
            nonlocal temp_file_created
            temp_file_created = self
            raise OSError("Simulated rename failure")

        # Patch rename to fail
        monkeypatch.setattr(Path, "rename", failing_rename)

        # Attempt to set marker (should fail)
        with pytest.raises(OSError, match="Simulated rename failure"):
            manager.set_latest_bundle(bundle_id)

        # Verify temp file was cleaned up
        if temp_file_created:
            assert not temp_file_created.exists(), "Temp file was not cleaned up"

    def test_atomic_write_creates_in_same_directory(self, tmp_path):
        """Test that temp file is created in same directory as target."""
        manager = BundleManager(tmp_path)
        bundle_id = "test-bundle-directory"

        # Track where temp file is created
        temp_file_path = None
        original_tempfile = tempfile.NamedTemporaryFile

        def tracking_tempfile(*args, **kwargs):
            nonlocal temp_file_path
            tf = original_tempfile(*args, **kwargs)
            temp_file_path = Path(tf.name).parent
            return tf

        # Temporarily replace NamedTemporaryFile
        import tempfile as tempfile_module
        original_func = tempfile_module.NamedTemporaryFile
        tempfile_module.NamedTemporaryFile = tracking_tempfile

        try:
            manager.set_latest_bundle(bundle_id)
        finally:
            tempfile_module.NamedTemporaryFile = original_func

        # Verify temp file was created in same directory as marker
        assert temp_file_path == tmp_path, \
            f"Temp file created in {temp_file_path}, expected {tmp_path}"

    def test_marker_file_never_contains_partial_data(self, tmp_path):
        """Test that marker file is never left in partial state."""
        manager = BundleManager(tmp_path)
        marker_file = tmp_path / "latest_bundle.txt"

        # Write multiple times rapidly
        bundle_ids = [f"bundle-{i:03d}" for i in range(10)]

        for bundle_id in bundle_ids:
            manager.set_latest_bundle(bundle_id)

            # After each write, marker should contain complete bundle ID
            if marker_file.exists():
                content = marker_file.read_text()
                assert content in bundle_ids, \
                    f"Marker contains unexpected content: {content}"
                # Content should not be truncated or empty
                assert len(content) > 0, "Marker file is empty"
