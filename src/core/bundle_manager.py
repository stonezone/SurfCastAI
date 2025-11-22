"""Bundle Manager for organizing and managing data bundles."""

import json
import os
import shutil
import logging
import tempfile
import zipfile
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional, Union

from ..utils.exceptions import SecurityError


# Security constants for archive extraction
MAX_ARCHIVE_FILE_SIZE = 100 * 1024 * 1024  # 100MB per file
MAX_ARCHIVE_TOTAL_SIZE = 1024 * 1024 * 1024  # 1GB total
MAX_COMPRESSION_RATIO = 100  # Zip bomb detection


class BundleManager:
    """
    Manages data bundles for the SurfCastAI system.

    Features:
    - Organizes collected data into bundles
    - Provides access to bundle metadata
    - Handles bundle cleanup and archiving
    - Supports operations on multiple bundles
    """

    def __init__(self, data_dir: Union[str, Path]):
        """
        Initialize the bundle manager.

        Args:
            data_dir: Root directory for data storage
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        self.logger = logging.getLogger('bundle_manager')

    def _write_latest_bundle_atomic(self, bundle_id: Optional[str]) -> None:
        """
        Atomically update the latest bundle marker file.

        Uses temp file + rename pattern to ensure atomic updates,
        preventing race conditions in concurrent bundle operations.

        Args:
            bundle_id: Bundle ID to mark as latest, or None to remove marker
        """
        latest_file = self.data_dir / "latest_bundle.txt"

        if bundle_id is None:
            # Remove marker atomically
            try:
                latest_file.unlink(missing_ok=True)
            except OSError as e:
                self.logger.warning(f"Failed to remove marker: {e}")
            return

        # Write atomically using temp file + rename
        temp_path = None
        try:
            # Create temp file in same directory (required for atomic rename)
            with tempfile.NamedTemporaryFile(
                mode='w',
                dir=latest_file.parent,
                delete=False
            ) as tf:
                tf.write(bundle_id)
                temp_path = Path(tf.name)

            # Atomic rename (POSIX guarantee)
            temp_path.rename(latest_file)
            self.logger.debug(f"Atomically updated marker: {bundle_id}")
        except OSError as e:
            self.logger.error(f"Failed to update marker atomically: {e}")
            if temp_path and temp_path.exists():
                try:
                    temp_path.unlink()
                except OSError:
                    pass  # Best effort cleanup
            raise

    def set_latest_bundle(self, bundle_id: Optional[str]) -> None:
        """Persist the provided bundle ID as the latest bundle reference."""
        self._write_latest_bundle_atomic(bundle_id)

    def get_latest_bundle(self) -> Optional[str]:
        """
        Get the ID of the latest bundle.

        Returns:
            Bundle ID or None if no bundles exist
        """
        try:
            # First check for the latest_bundle.txt file
            latest_file = self.data_dir / "latest_bundle.txt"
            if latest_file.exists():
                with open(latest_file, 'r') as f:
                    bundle_id = f.read().strip()
                    if (self.data_dir / bundle_id).exists():
                        return bundle_id

            # Fall back to finding the most recent bundle directory
            bundles = [d for d in self.data_dir.iterdir()
                     if d.is_dir() and d.name != 'temp' and d.name != 'archive']

            if not bundles:
                return None

            # Sort by creation time (newest first)
            bundles.sort(key=lambda d: d.stat().st_mtime, reverse=True)
            return bundles[0].name

        except Exception as e:
            self.logger.error(f"Error getting latest bundle: {e}")
            return None

    def get_bundle_path(self, bundle_id: Optional[str] = None) -> Optional[Path]:
        """
        Get the path to a specific bundle.

        Args:
            bundle_id: Bundle ID (uses latest if not provided)

        Returns:
            Path to the bundle directory or None if not found
        """
        # Get bundle ID if not provided
        if bundle_id is None:
            bundle_id = self.get_latest_bundle()
            if bundle_id is None:
                return None

        # Check if bundle exists
        bundle_path = self.data_dir / bundle_id
        if bundle_path.exists() and bundle_path.is_dir():
            return bundle_path

        return None

    def get_bundle_metadata(self, bundle_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Get metadata for a specific bundle.

        Args:
            bundle_id: Bundle ID (uses latest if not provided)

        Returns:
            Bundle metadata dictionary or None if not found
        """
        bundle_path = self.get_bundle_path(bundle_id)
        if bundle_path is None:
            return None

        # Try to load metadata
        metadata_path = bundle_path / "bundle_metadata.json"
        if metadata_path.exists():
            try:
                with open(metadata_path, 'r') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                self.logger.error(f"Invalid JSON in bundle metadata: {metadata_path}")

        return None

    def list_bundles(
        self,
        limit: Optional[int] = None,
        include_incomplete: bool = False
    ) -> List[Dict[str, Any]]:
        """
        List all available bundles.

        Args:
            limit: Maximum number of bundles to return
            include_incomplete: When True, include bundles missing
                processed outputs and flag them as incomplete.
                When False (default), incomplete bundles are excluded.

        Returns:
            List of bundle information dictionaries
        """
        bundles = []

        # Find all bundle directories
        for item in self.data_dir.iterdir():
            if item.is_dir() and item.name != 'temp' and item.name != 'archive':
                processed_fused = item / 'processed' / 'fused_forecast.json'
                is_complete = processed_fused.exists()
                if not include_incomplete and not is_complete:
                    self.logger.debug(
                        "Skipping incomplete bundle %s (missing %s)",
                        item.name,
                        processed_fused.relative_to(item)
                    )
                    continue
                # Try to load metadata
                metadata_path = item / "bundle_metadata.json"

                if metadata_path.exists():
                    try:
                        with open(metadata_path, 'r') as f:
                            metadata = json.load(f)
                            if isinstance(metadata, dict):
                                metadata.setdefault("bundle_id", item.name)
                                metadata['complete'] = is_complete
                                bundles.append(metadata)
                            else:
                                bundles.append({
                                    "bundle_id": item.name,
                                    "timestamp": datetime.fromtimestamp(
                                        item.stat().st_mtime, tz=timezone.utc
                                    ).isoformat(),
                                    "error": "Invalid metadata format",
                                    "complete": is_complete,
                                })
                    except json.JSONDecodeError:
                        # Add basic info if metadata invalid
                        bundles.append({
                            "bundle_id": item.name,
                            "timestamp": datetime.fromtimestamp(
                                item.stat().st_mtime, tz=timezone.utc
                            ).isoformat(),
                            "error": "Invalid metadata file",
                            "complete": is_complete,
                        })
                else:
                    # Add basic info if metadata not available
                    bundles.append({
                        "bundle_id": item.name,
                        "timestamp": datetime.fromtimestamp(
                            item.stat().st_mtime, tz=timezone.utc
                        ).isoformat(),
                        "error": "Missing metadata file",
                        "complete": is_complete,
                    })

        # Sort by timestamp (newest first)
        bundles.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

        # Apply limit if provided
        if limit is not None and limit > 0:
            bundles = bundles[:limit]

        return bundles

    def get_bundle_age(self, bundle_id: str) -> timedelta:
        """Return age of bundle as timedelta (0 if missing)."""
        bundle_path = self.data_dir / bundle_id
        if not bundle_path.exists():
            return timedelta(0)

        try:
            mtime = datetime.fromtimestamp(bundle_path.stat().st_mtime, tz=timezone.utc)
        except FileNotFoundError:
            return timedelta(0)

        return datetime.now(timezone.utc) - mtime

    def cleanup_old_bundles(self, days_to_keep: int = 7) -> int:
        """
        Clean up old bundles that exceed the retention period.

        Args:
            days_to_keep: Number of days to keep bundles

        Returns:
            Number of bundles removed
        """
        cutoff_time = datetime.now(timezone.utc) - timedelta(days=days_to_keep)
        removed_count = 0

        # List all bundles, including incomplete ones for cleanup
        bundles = self.list_bundles(include_incomplete=True)

        for bundle in bundles:
            # Check if bundle is older than cutoff
            try:
                bundle_time = datetime.fromisoformat(bundle.get("timestamp", ""))
                if bundle_time < cutoff_time:
                    # Remove the bundle
                    bundle_id = bundle.get("bundle_id")
                    if bundle_id:
                        self._remove_bundle(bundle_id)
                        removed_count += 1
            except (ValueError, TypeError):
                # If timestamp is invalid, check file modification time
                bundle_id = bundle.get("bundle_id")
                if bundle_id:
                    bundle_path = self.data_dir / bundle_id
                    if bundle_path.exists():
                        mtime = datetime.fromtimestamp(
                            bundle_path.stat().st_mtime, tz=timezone.utc
                        )
                        if mtime < cutoff_time:
                            self._remove_bundle(bundle_id)
                            removed_count += 1

        self.logger.info(f"Cleaned up {removed_count} old bundles")
        return removed_count

    def cleanup_old_bundles_using_config(self, config) -> List[Dict[str, Any]]:
        """Cleanup bundles using retention settings from configuration.

        Args:
            config: Config instance providing general.data_retention_days

        Returns:
            List of removed bundle metadata dicts
        """
        retention_days = getattr(config, 'getint', None)
        if callable(retention_days):
            days = config.getint('general', 'data_retention_days', 30)
        else:
            days = 30

        cutoff_time = datetime.now(timezone.utc) - timedelta(days=days)
        removed: List[Dict[str, Any]] = []

        bundles = self.list_bundles(include_incomplete=True)

        for bundle in bundles:
            bundle_id = bundle.get('bundle_id')
            if not bundle_id:
                continue

            complete = bundle.get('complete', False)
            if not complete:
                self.logger.debug("Skipping cleanup for incomplete bundle %s", bundle_id)
                continue

            timestamp = bundle.get('timestamp')
            try:
                bundle_time = datetime.fromisoformat(timestamp) if timestamp else None
            except (TypeError, ValueError):
                bundle_time = None

            if bundle_time is None:
                bundle_path = self.data_dir / bundle_id
                if bundle_path.exists():
                    bundle_time = datetime.fromtimestamp(bundle_path.stat().st_mtime, tz=timezone.utc)

            if bundle_time and bundle_time < cutoff_time:
                if self._remove_bundle(bundle_id):
                    removed.append(bundle)

        if removed:
            self.logger.info("Removed %d bundle(s) older than %d days", len(removed), days)

        return removed

    def _remove_bundle(self, bundle_id: str) -> bool:
        """
        Remove a specific bundle.

        Args:
            bundle_id: Bundle ID to remove

        Returns:
            True if bundle was removed, False otherwise
        """
        bundle_path = self.data_dir / bundle_id
        if bundle_path.exists() and bundle_path.is_dir():
            try:
                shutil.rmtree(bundle_path)
                self.logger.info(f"Removed bundle: {bundle_id}")
                return True
            except Exception as e:
                self.logger.error(f"Error removing bundle {bundle_id}: {e}")

        return False

    def archive_bundle(self, bundle_id: str) -> bool:
        """
        Archive a bundle to save space.

        Args:
            bundle_id: Bundle ID to archive

        Returns:
            True if bundle was archived, False otherwise
        """
        bundle_path = self.data_dir / bundle_id
        if not bundle_path.exists():
            self.logger.warning(f"Bundle not found: {bundle_id}")
            return False

        # Create archive directory if it doesn't exist
        archive_dir = self.data_dir / "archive"
        archive_dir.mkdir(exist_ok=True)

        # Archive file path
        archive_file = archive_dir / f"{bundle_id}.zip"

        try:
            # Create zip archive
            shutil.make_archive(
                str(archive_file.with_suffix('')),  # Base name without extension
                'zip',
                root_dir=self.data_dir,
                base_dir=bundle_id
            )

            # Remove original bundle directory
            shutil.rmtree(bundle_path)

            self.logger.info(f"Archived bundle {bundle_id} to {archive_file}")
            return True

        except Exception as e:
            self.logger.error(f"Error archiving bundle {bundle_id}: {e}")
            return False

    def safe_extract_archive(self, archive_path: Path, target_dir: Path) -> None:
        """
        Safely extract a zip archive with comprehensive security validation.

        Validates all archive members BEFORE extracting ANY to prevent:
        - Path traversal attacks (../../../etc/passwd)
        - Zip bombs (highly compressed malicious files)
        - Resource exhaustion (files too large)

        Args:
            archive_path: Path to the zip archive
            target_dir: Target directory for extraction

        Raises:
            SecurityError: If any security validation fails
            ValueError: If archive is invalid
        """
        if not archive_path.exists():
            raise ValueError(f"Archive not found: {archive_path}")

        # Ensure target directory exists and is resolved
        target_dir.mkdir(parents=True, exist_ok=True)
        target_dir_resolved = target_dir.resolve()

        # Open and validate the archive
        try:
            with zipfile.ZipFile(archive_path, 'r') as zf:
                # First pass: validate ALL members before extracting ANY
                total_size = 0

                for member in zf.infolist():
                    # Skip directories
                    if member.is_dir():
                        continue

                    # 1. Path Traversal Check
                    # Construct the full extraction path and verify it's within target_dir
                    member_path = target_dir / member.filename
                    try:
                        member_path_resolved = member_path.resolve()
                        if not member_path_resolved.is_relative_to(target_dir_resolved):
                            self.logger.error(
                                "Path traversal attempt detected: %s resolves outside target directory",
                                member.filename
                            )
                            raise SecurityError(
                                f"Path traversal detected: {member.filename} "
                                f"would extract outside target directory"
                            )
                    except (ValueError, OSError) as e:
                        self.logger.error("Invalid path in archive member: %s (%s)", member.filename, e)
                        raise SecurityError(f"Invalid path in archive: {member.filename}")

                    # 2. Individual File Size Check
                    if member.file_size > MAX_ARCHIVE_FILE_SIZE:
                        self.logger.error(
                            "File too large in archive: %s (%d bytes, max %d bytes)",
                            member.filename,
                            member.file_size,
                            MAX_ARCHIVE_FILE_SIZE
                        )
                        raise SecurityError(
                            f"File too large: {member.filename} "
                            f"({member.file_size} bytes, max {MAX_ARCHIVE_FILE_SIZE} bytes)"
                        )

                    # 3. Compression Ratio Check (Zip Bomb Detection)
                    # Avoid division by zero for uncompressed files
                    if member.compress_size > 0:
                        compression_ratio = member.file_size / member.compress_size
                        if compression_ratio > MAX_COMPRESSION_RATIO:
                            self.logger.error(
                                "Zip bomb detected: %s has compression ratio %.1fx (max %dx)",
                                member.filename,
                                compression_ratio,
                                MAX_COMPRESSION_RATIO
                            )
                            raise SecurityError(
                                f"Zip bomb detected: {member.filename} "
                                f"has compression ratio {compression_ratio:.1f}x "
                                f"(max {MAX_COMPRESSION_RATIO}x)"
                            )

                    # 4. Accumulate total size
                    total_size += member.file_size

                # 5. Total Size Check
                if total_size > MAX_ARCHIVE_TOTAL_SIZE:
                    self.logger.error(
                        "Archive total size too large: %d bytes (max %d bytes)",
                        total_size,
                        MAX_ARCHIVE_TOTAL_SIZE
                    )
                    raise SecurityError(
                        f"Archive total size too large: {total_size} bytes "
                        f"(max {MAX_ARCHIVE_TOTAL_SIZE} bytes)"
                    )

                # All validation passed - now safe to extract
                self.logger.info(
                    "Archive validation passed: %d files, %d total bytes",
                    len([m for m in zf.infolist() if not m.is_dir()]),
                    total_size
                )

                # Extract with explicit path for each member (safest approach)
                for member in zf.infolist():
                    # ZipFile.extract() already handles path traversal, but we've
                    # validated above. Using extractall with target_dir is safe now.
                    zf.extract(member, path=target_dir)

        except zipfile.BadZipFile as e:
            self.logger.error("Invalid zip archive: %s (%s)", archive_path, e)
            raise ValueError(f"Invalid zip archive: {e}")
        except SecurityError:
            # Re-raise security errors as-is
            raise
        except Exception as e:
            self.logger.error("Error validating archive %s: %s", archive_path, e)
            raise

    def extract_archived_bundle(self, bundle_id: str) -> bool:
        """
        Extract an archived bundle using secure extraction.

        Args:
            bundle_id: Bundle ID to extract

        Returns:
            True if bundle was extracted, False otherwise
        """
        # Check if bundle is already extracted
        if (self.data_dir / bundle_id).exists():
            self.logger.info(f"Bundle already extracted: {bundle_id}")
            return True

        # Check if archive exists
        archive_file = self.data_dir / "archive" / f"{bundle_id}.zip"
        if not archive_file.exists():
            self.logger.warning(f"Archive not found: {archive_file}")
            return False

        try:
            # Use secure extraction
            self.safe_extract_archive(archive_file, self.data_dir)

            self.logger.info(f"Extracted archive: {bundle_id}")
            return True

        except SecurityError as e:
            self.logger.error(f"Security violation extracting {bundle_id}: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Error extracting archive {bundle_id}: {e}")
            return False

    def get_bundle_file_list(self, bundle_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get list of all files in a bundle.

        Args:
            bundle_id: Bundle ID (uses latest if not provided)

        Returns:
            List of file information dictionaries
        """
        bundle_path = self.get_bundle_path(bundle_id)
        if bundle_path is None:
            return []

        # Try to load all metadata
        metadata_path = bundle_path / "all_metadata.json"
        if metadata_path.exists():
            try:
                with open(metadata_path, 'r') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                self.logger.error(f"Invalid JSON in all_metadata.json: {metadata_path}")

        # Fall back to scanning the bundle directory
        files = []
        for agent_dir in bundle_path.iterdir():
            if agent_dir.is_dir():
                agent_name = agent_dir.name

                for file_path in agent_dir.rglob('*'):
                    if file_path.is_file():
                        files.append({
                            "name": file_path.name,
                            "path": str(file_path.relative_to(bundle_path)),
                            "agent": agent_name,
                            "size_bytes": file_path.stat().st_size,
                            "mtime": datetime.fromtimestamp(
                                file_path.stat().st_mtime, tz=timezone.utc
                            ).isoformat()
                        })

        return files

    def get_bundle_file(self, bundle_id: str, file_path: str) -> Optional[Path]:
        """
        Get path to a specific file within a bundle.

        Args:
            bundle_id: Bundle ID
            file_path: Relative path to file within bundle

        Returns:
            Path to the file or None if not found
        """
        bundle_path = self.get_bundle_path(bundle_id)
        if bundle_path is None:
            return None

        # Normalize file path
        file_path = file_path.lstrip('/')
        full_path = bundle_path / file_path

        if full_path.exists() and full_path.is_file():
            return full_path

        return None
