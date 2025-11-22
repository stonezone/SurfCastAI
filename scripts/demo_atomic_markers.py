#!/usr/bin/env python3
"""
Demo script showing atomic marker updates in action.

This script demonstrates:
1. Thread-safe marker updates
2. No corruption under concurrent access
3. Proper error handling and cleanup
"""

import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.bundle_manager import BundleManager


def demo_basic_operations():
    """Demonstrate basic atomic marker operations."""
    print("\n" + "=" * 70)
    print("DEMO 1: Basic Atomic Operations")
    print("=" * 70)

    with tempfile.TemporaryDirectory() as tmpdir:
        manager = BundleManager(tmpdir)
        marker_file = Path(tmpdir) / "latest_bundle.txt"

        # Create marker
        print("\n1. Creating marker...")
        manager.set_latest_bundle("bundle-001")
        print(f"   Marker content: {marker_file.read_text()}")
        print(f"   Marker exists: {marker_file.exists()}")

        # Update marker
        print("\n2. Updating marker...")
        manager.set_latest_bundle("bundle-002")
        print(f"   Marker content: {marker_file.read_text()}")

        # Remove marker
        print("\n3. Removing marker...")
        manager.set_latest_bundle(None)
        print(f"   Marker exists: {marker_file.exists()}")

        print("\nBasic operations completed successfully!")


def demo_concurrent_updates():
    """Demonstrate concurrent marker updates without corruption."""
    print("\n" + "=" * 70)
    print("DEMO 2: Concurrent Updates (100 threads)")
    print("=" * 70)

    with tempfile.TemporaryDirectory() as tmpdir:
        manager = BundleManager(tmpdir)
        marker_file = Path(tmpdir) / "latest_bundle.txt"

        bundle_ids = [f"bundle-{i:04d}" for i in range(100)]

        def update_marker(bundle_id: str) -> tuple[str, bool]:
            """Update marker and verify success."""
            try:
                manager.set_latest_bundle(bundle_id)
                return bundle_id, True
            except Exception as e:
                return bundle_id, False

        print("\nExecuting 100 concurrent marker updates...")
        start_time = time.time()

        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(update_marker, bid) for bid in bundle_ids]
            results = [f.result() for f in as_completed(futures)]

        elapsed = time.time() - start_time

        # Check results
        successes = sum(1 for _, success in results if success)
        failures = len(results) - successes

        print(f"\nResults:")
        print(f"  Total updates:  {len(results)}")
        print(f"  Successful:     {successes}")
        print(f"  Failed:         {failures}")
        print(f"  Time elapsed:   {elapsed:.3f}s")
        print(f"  Updates/sec:    {len(results) / elapsed:.1f}")

        # Verify marker integrity
        if marker_file.exists():
            content = marker_file.read_text()
            is_valid = content in bundle_ids
            print(f"\nMarker integrity check:")
            print(f"  Final content:  {content}")
            print(f"  Is valid ID:    {is_valid}")
            print(f"  Not corrupted:  {content.count('bundle-') == 1}")
        else:
            print("\nMarker file does not exist (unexpected)")


def demo_concurrent_read_write():
    """Demonstrate concurrent reads never see partial writes."""
    print("\n" + "=" * 70)
    print("DEMO 3: Concurrent Reads and Writes (No Partial Reads)")
    print("=" * 70)

    with tempfile.TemporaryDirectory() as tmpdir:
        manager = BundleManager(tmpdir)

        bundle_ids = [f"bundle-{i:04d}" for i in range(20)]
        partial_reads = []
        total_reads = 0

        def writer_task(bundle_id: str) -> None:
            """Write marker repeatedly."""
            for _ in range(10):
                manager.set_latest_bundle(bundle_id)
                time.sleep(0.001)  # Small delay

        def reader_task() -> int:
            """Read marker repeatedly and check for partial data."""
            nonlocal total_reads
            reads = 0
            for _ in range(50):
                latest = manager.get_latest_bundle()
                reads += 1
                if latest is not None:
                    # Check if this looks like a valid bundle ID
                    if not latest.startswith("bundle-") or len(latest) < 11:
                        partial_reads.append(latest)
            return reads

        print("\nExecuting concurrent reads and writes...")
        print("  Writers: 20 threads (10 updates each)")
        print("  Readers: 10 threads (50 reads each)")

        start_time = time.time()

        with ThreadPoolExecutor(max_workers=30) as executor:
            # Submit writer tasks
            writer_futures = [
                executor.submit(writer_task, bid) for bid in bundle_ids
            ]
            # Submit reader tasks
            reader_futures = [
                executor.submit(reader_task) for _ in range(10)
            ]

            # Wait for completion
            all_futures = writer_futures + reader_futures
            for future in as_completed(all_futures):
                if future in reader_futures:
                    total_reads += future.result()

        elapsed = time.time() - start_time

        print(f"\nResults:")
        print(f"  Total reads:       {total_reads}")
        print(f"  Partial reads:     {len(partial_reads)}")
        print(f"  Corruption rate:   {len(partial_reads) / total_reads * 100:.2f}%")
        print(f"  Time elapsed:      {elapsed:.3f}s")

        if len(partial_reads) == 0:
            print("\n✓ SUCCESS: No partial reads detected!")
        else:
            print(f"\n✗ FAILURE: Found {len(partial_reads)} partial reads:")
            for i, pr in enumerate(partial_reads[:5], 1):
                print(f"    {i}. {repr(pr)}")


def demo_no_temp_file_leaks():
    """Demonstrate no temporary files are left behind."""
    print("\n" + "=" * 70)
    print("DEMO 4: No Temporary File Leaks")
    print("=" * 70)

    with tempfile.TemporaryDirectory() as tmpdir:
        manager = BundleManager(tmpdir)
        tmpdir_path = Path(tmpdir)

        print("\nPerforming 100 marker updates...")
        for i in range(100):
            manager.set_latest_bundle(f"bundle-{i:04d}")

        # Check for temp files
        temp_files = list(tmpdir_path.glob("tmp*"))
        temp_files.extend(tmpdir_path.glob("*.tmp"))

        print(f"\nResults:")
        print(f"  Updates completed: 100")
        print(f"  Temp files found:  {len(temp_files)}")

        if len(temp_files) == 0:
            print("\n✓ SUCCESS: No temporary files leaked!")
        else:
            print(f"\n✗ FAILURE: Found {len(temp_files)} temp files:")
            for tf in temp_files:
                print(f"    - {tf.name}")


def main():
    """Run all demonstrations."""
    print("\n" + "=" * 70)
    print("ATOMIC BUNDLE MARKER DEMONSTRATIONS")
    print("=" * 70)
    print("\nThis script demonstrates the atomic marker update implementation")
    print("that prevents race conditions and file corruption in concurrent")
    print("bundle operations.")

    try:
        demo_basic_operations()
        demo_concurrent_updates()
        demo_concurrent_read_write()
        demo_no_temp_file_leaks()

        print("\n" + "=" * 70)
        print("ALL DEMONSTRATIONS COMPLETED SUCCESSFULLY")
        print("=" * 70)
        print("\nKey takeaways:")
        print("  • Marker updates are atomic (no partial writes)")
        print("  • Thread-safe under concurrent access")
        print("  • No temporary file leaks")
        print("  • Proper error handling and cleanup")
        print()

    except Exception as e:
        print(f"\n✗ DEMO FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
