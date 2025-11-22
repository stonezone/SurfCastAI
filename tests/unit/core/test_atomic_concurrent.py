"""Integration test for concurrent atomic marker updates."""

import concurrent.futures
from pathlib import Path

import pytest

from src.core.bundle_manager import BundleManager


class TestConcurrentAtomicUpdates:
    """Test atomic marker updates under concurrent access."""

    def test_concurrent_marker_updates_no_corruption(self, tmp_path):
        """Test that concurrent marker updates don't corrupt the file."""
        manager = BundleManager(tmp_path)
        marker_file = tmp_path / "latest_bundle.txt"

        # Generate bundle IDs
        bundle_ids = [f"bundle-{i:04d}" for i in range(100)]

        def update_marker(bundle_id: str) -> str:
            """Update marker and return the bundle ID."""
            manager.set_latest_bundle(bundle_id)
            return bundle_id

        # Execute concurrent updates
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(update_marker, bid) for bid in bundle_ids]
            # Wait for all to complete
            concurrent.futures.wait(futures)

        # Verify marker file is not corrupted
        assert marker_file.exists(), "Marker file should exist"

        content = marker_file.read_text()
        # Content should be one of the valid bundle IDs (not partial/corrupt)
        assert content in bundle_ids, f"Marker contains unexpected content: {content}"
        # Should not be truncated or contain multiple IDs
        assert (
            content.count("bundle-") == 1
        ), f"Marker contains multiple or malformed IDs: {content}"

    def test_concurrent_read_write_no_partial_reads(self, tmp_path):
        """Test that reads never see partial writes."""
        manager = BundleManager(tmp_path)

        bundle_ids = [f"bundle-{i:04d}" for i in range(50)]
        partial_reads = []

        def writer_task(bundle_id: str) -> None:
            """Write marker repeatedly."""
            for _ in range(5):
                manager.set_latest_bundle(bundle_id)

        def reader_task() -> None:
            """Read marker repeatedly and check for partial data."""
            for _ in range(25):
                latest = manager.get_latest_bundle()
                if latest is not None:
                    # Check if this looks like a valid bundle ID
                    if not latest.startswith("bundle-") or len(latest) < 11:
                        partial_reads.append(latest)

        # Execute concurrent reads and writes
        with concurrent.futures.ThreadPoolExecutor(max_workers=15) as executor:
            # Submit writer tasks
            writer_futures = [executor.submit(writer_task, bid) for bid in bundle_ids[:10]]
            # Submit reader tasks
            reader_futures = [executor.submit(reader_task) for _ in range(5)]

            # Wait for all tasks
            all_futures = writer_futures + reader_futures
            concurrent.futures.wait(all_futures)

        # Verify no partial reads occurred
        assert (
            len(partial_reads) == 0
        ), f"Found {len(partial_reads)} partial reads: {partial_reads[:5]}"

    def test_concurrent_updates_with_removals(self, tmp_path):
        """Test concurrent updates and removals maintain consistency."""
        manager = BundleManager(tmp_path)
        marker_file = tmp_path / "latest_bundle.txt"

        def mixed_operations(index: int) -> None:
            """Perform mixed update and removal operations."""
            if index % 3 == 0:
                # Remove marker
                manager.set_latest_bundle(None)
            else:
                # Update marker
                manager.set_latest_bundle(f"bundle-{index:04d}")

        # Execute concurrent mixed operations
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(mixed_operations, i) for i in range(40)]
            concurrent.futures.wait(futures)

        # At the end, marker either exists with valid ID or doesn't exist
        if marker_file.exists():
            content = marker_file.read_text()
            # Should be a valid bundle ID
            assert content.startswith("bundle-"), f"Invalid marker content: {content}"
            assert len(content) > 7, f"Truncated marker content: {content}"
        # If it doesn't exist, that's also fine (last operation was removal)
