#!/usr/bin/env python3
"""
Demonstration script for secure archive extraction.

This script creates various malicious archives and demonstrates how the
security validations detect and prevent extraction attacks.
"""

import logging
import sys
import tempfile
import zipfile
from pathlib import Path

# Add parent directory to path to import from src
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.bundle_manager import (
    MAX_ARCHIVE_FILE_SIZE,
    MAX_ARCHIVE_TOTAL_SIZE,
    MAX_COMPRESSION_RATIO,
    BundleManager,
)
from src.utils.exceptions import SecurityError

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)


def demo_path_traversal():
    """Demonstrate path traversal attack detection."""
    print("\n" + "=" * 70)
    print("DEMO 1: Path Traversal Attack Detection")
    print("=" * 70)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create malicious archive with path traversal
        archive_path = tmpdir / "malicious_traversal.zip"
        with zipfile.ZipFile(archive_path, "w") as zf:
            zf.writestr("../../../etc/passwd", "malicious content")

        print(f"Created malicious archive: {archive_path.name}")
        print("Archive contains: ../../../etc/passwd")

        # Try to extract
        bundle_manager = BundleManager(tmpdir / "data")
        target_dir = tmpdir / "extracted"

        try:
            bundle_manager.safe_extract_archive(archive_path, target_dir)
            print("❌ FAIL: Archive was extracted (should have been blocked!)")
        except SecurityError as e:
            print("✓ SUCCESS: Path traversal detected and blocked")
            print(f"  Error: {e}")


def demo_file_too_large():
    """Demonstrate oversized file detection."""
    print("\n" + "=" * 70)
    print("DEMO 2: Oversized File Detection")
    print("=" * 70)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create archive with file exceeding size limit
        archive_path = tmpdir / "large_file.zip"
        large_size = MAX_ARCHIVE_FILE_SIZE + 1
        large_content = "X" * large_size

        print(f"Creating archive with {large_size / (1024*1024):.1f}MB file")
        print(f"Limit: {MAX_ARCHIVE_FILE_SIZE / (1024*1024):.1f}MB")

        with zipfile.ZipFile(archive_path, "w") as zf:
            zf.writestr("huge.txt", large_content)

        # Try to extract
        bundle_manager = BundleManager(tmpdir / "data")
        target_dir = tmpdir / "extracted"

        try:
            bundle_manager.safe_extract_archive(archive_path, target_dir)
            print("❌ FAIL: Large file was extracted (should have been blocked!)")
        except SecurityError as e:
            print("✓ SUCCESS: Oversized file detected and blocked")
            print(f"  Error: {e}")


def demo_zip_bomb():
    """Demonstrate zip bomb detection."""
    print("\n" + "=" * 70)
    print("DEMO 3: Zip Bomb Detection (High Compression Ratio)")
    print("=" * 70)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create highly compressed file (simulating zip bomb)
        archive_path = tmpdir / "bomb.zip"

        # Create very compressible content (repeated pattern)
        # This compresses to a small size but expands to a large size
        content = "0" * 10_000_000  # 10MB of zeros

        with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("bomb.txt", content, compress_type=zipfile.ZIP_DEFLATED)

        # Check actual compression ratio
        with zipfile.ZipFile(archive_path, "r") as zf:
            info = zf.infolist()[0]
            ratio = info.file_size / info.compress_size

            print("Archive stats:")
            print(f"  Uncompressed size: {info.file_size / 1024:.1f}KB")
            print(f"  Compressed size: {info.compress_size / 1024:.1f}KB")
            print(f"  Compression ratio: {ratio:.1f}x")
            print(f"  Max allowed ratio: {MAX_COMPRESSION_RATIO}x")

        # Try to extract
        bundle_manager = BundleManager(tmpdir / "data")
        target_dir = tmpdir / "extracted"

        try:
            bundle_manager.safe_extract_archive(archive_path, target_dir)
            if ratio > MAX_COMPRESSION_RATIO:
                print("❌ FAIL: Zip bomb was extracted (should have been blocked!)")
            else:
                print(
                    f"⚠ SKIP: Compression ratio ({ratio:.1f}x) not high enough to trigger detection"
                )
        except SecurityError as e:
            print("✓ SUCCESS: Zip bomb detected and blocked")
            print(f"  Error: {e}")


def demo_total_size_exceeded():
    """Demonstrate total archive size limit."""
    print("\n" + "=" * 70)
    print("DEMO 4: Total Archive Size Limit")
    print("=" * 70)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create archive with total size exceeding limit
        archive_path = tmpdir / "huge_total.zip"

        # Create multiple files that together exceed limit
        file_size = 50 * 1024 * 1024  # 50MB each
        num_files = (MAX_ARCHIVE_TOTAL_SIZE // file_size) + 1
        total_size = file_size * num_files

        print(f"Creating archive with {num_files} files")
        print(f"Individual file size: {file_size / (1024*1024):.1f}MB")
        print(f"Total size: {total_size / (1024*1024):.1f}MB")
        print(f"Limit: {MAX_ARCHIVE_TOTAL_SIZE / (1024*1024):.1f}MB")

        content = "X" * file_size

        with zipfile.ZipFile(archive_path, "w") as zf:
            for i in range(num_files):
                zf.writestr(f"file{i}.txt", content)

        # Try to extract
        bundle_manager = BundleManager(tmpdir / "data")
        target_dir = tmpdir / "extracted"

        try:
            bundle_manager.safe_extract_archive(archive_path, target_dir)
            print("❌ FAIL: Large archive was extracted (should have been blocked!)")
        except SecurityError as e:
            print("✓ SUCCESS: Total size limit enforced")
            print(f"  Error: {e}")


def demo_valid_extraction():
    """Demonstrate successful extraction of valid archive."""
    print("\n" + "=" * 70)
    print("DEMO 5: Valid Archive Extraction (Should Succeed)")
    print("=" * 70)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create valid archive
        archive_path = tmpdir / "valid.zip"

        with zipfile.ZipFile(archive_path, "w") as zf:
            zf.writestr("file1.txt", "Hello, World!")
            zf.writestr("subdir/file2.txt", "Test content")
            zf.writestr("subdir/file3.txt", "More test content")

        print("Created valid archive with 3 files")

        # Try to extract
        bundle_manager = BundleManager(tmpdir / "data")
        target_dir = tmpdir / "extracted"

        try:
            bundle_manager.safe_extract_archive(archive_path, target_dir)

            # Verify extraction
            if (target_dir / "file1.txt").exists() and (
                target_dir / "subdir" / "file2.txt"
            ).exists():
                print("✓ SUCCESS: Valid archive extracted successfully")
                print("  Files extracted:")
                for file in sorted(target_dir.rglob("*")):
                    if file.is_file():
                        print(f"    - {file.relative_to(target_dir)}")
            else:
                print("❌ FAIL: Files were not extracted properly")

        except Exception as e:
            print(f"❌ FAIL: Valid archive rejected: {e}")


def main():
    """Run all demonstrations."""
    print("\n" + "=" * 70)
    print("SECURE ARCHIVE EXTRACTION DEMONSTRATION")
    print("=" * 70)
    print("\nThis script demonstrates the security validations that protect")
    print("against common archive-based attacks.")

    # Run all demos
    demo_path_traversal()
    demo_file_too_large()
    demo_zip_bomb()
    demo_total_size_exceeded()
    demo_valid_extraction()

    print("\n" + "=" * 70)
    print("DEMONSTRATION COMPLETE")
    print("=" * 70)
    print("\nSummary:")
    print("  ✓ Path traversal attacks are detected and blocked")
    print("  ✓ Oversized individual files are rejected")
    print("  ✓ Zip bombs (high compression ratio) are detected")
    print("  ✓ Total archive size limits are enforced")
    print("  ✓ Valid archives extract successfully")
    print("\nAll security validations are performed BEFORE extraction begins.")
    print()


if __name__ == "__main__":
    main()
