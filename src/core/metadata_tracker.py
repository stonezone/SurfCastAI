"""
Metadata Tracker for tracking and managing metadata for collected data.
"""

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class MetadataTracker:
    """
    Tracks and manages metadata for collected data.

    Features:
    - Maintains comprehensive metadata for all collected data
    - Provides validation and quality metrics
    - Supports tracking data provenance
    - Helps identify data issues and gaps
    """

    def __init__(self, metadata_file: str | Path | None = None):
        """
        Initialize the metadata tracker.

        Args:
            metadata_file: Optional path to metadata file for persistence
        """
        self.logger = logging.getLogger("metadata_tracker")
        self.metadata_file = Path(metadata_file) if metadata_file else None

        # Initialize metadata structure
        self.metadata = {
            "version": "1.0",
            "created_at": datetime.now(UTC).isoformat(),
            "updated_at": datetime.now(UTC).isoformat(),
            "sources": {},
            "files": {},
            "quality_metrics": {"completeness": 0.0, "freshness": 0.0, "consistency": 0.0},
            "stats": {
                "total_files": 0,
                "successful_files": 0,
                "failed_files": 0,
                "total_size_bytes": 0,
            },
        }

        # Load existing metadata if file exists
        if self.metadata_file and self.metadata_file.exists():
            self.load()

    def load(self) -> bool:
        """
        Load metadata from file.

        Returns:
            True if loaded successfully, False otherwise
        """
        if not self.metadata_file or not self.metadata_file.exists():
            return False

        try:
            with open(self.metadata_file) as f:
                loaded_metadata = json.load(f)
                self.metadata.update(loaded_metadata)
                self.logger.info(f"Loaded metadata from {self.metadata_file}")
                return True
        except (OSError, json.JSONDecodeError) as e:
            self.logger.error(f"Error loading metadata from {self.metadata_file}: {e}")
            return False

    def save(self) -> bool:
        """
        Save metadata to file.

        Returns:
            True if saved successfully, False otherwise
        """
        if not self.metadata_file:
            return False

        # Update timestamp
        self.metadata["updated_at"] = datetime.now(UTC).isoformat()

        try:
            # Ensure parent directory exists
            self.metadata_file.parent.mkdir(parents=True, exist_ok=True)

            with open(self.metadata_file, "w") as f:
                json.dump(self.metadata, f, indent=2)
                self.logger.info(f"Saved metadata to {self.metadata_file}")
                return True
        except OSError as e:
            self.logger.error(f"Error saving metadata to {self.metadata_file}: {e}")
            return False

    def add_file(self, file_metadata: dict[str, Any]) -> None:
        """
        Add metadata for a collected file.

        Args:
            file_metadata: Metadata dictionary for the file
        """
        # Generate a unique ID for the file
        file_id = file_metadata.get("file_path", file_metadata.get("name", ""))
        if not file_id:
            file_id = f"file_{len(self.metadata['files']) + 1}"

        # Add to files
        self.metadata["files"][file_id] = file_metadata

        # Update source metadata
        source = file_metadata.get("source", "unknown")
        if source not in self.metadata["sources"]:
            self.metadata["sources"][source] = {
                "files": [],
                "successful": 0,
                "failed": 0,
                "last_updated": datetime.now(UTC).isoformat(),
            }

        self.metadata["sources"][source]["files"].append(file_id)

        # Update success/failure counts
        status = file_metadata.get("status", "unknown")
        if status == "success":
            self.metadata["sources"][source]["successful"] += 1
            self.metadata["stats"]["successful_files"] += 1
        elif status == "failed":
            self.metadata["sources"][source]["failed"] += 1
            self.metadata["stats"]["failed_files"] += 1

        # Update total count
        self.metadata["stats"]["total_files"] += 1

        # Update total size
        size_bytes = file_metadata.get("size_bytes", 0)
        if size_bytes:
            self.metadata["stats"]["total_size_bytes"] += size_bytes

        # Update quality metrics
        self._update_quality_metrics()

    def add_files(self, file_metadata_list: list[dict[str, Any]]) -> None:
        """
        Add metadata for multiple collected files.

        Args:
            file_metadata_list: List of metadata dictionaries
        """
        for file_metadata in file_metadata_list:
            self.add_file(file_metadata)

    def get_file_metadata(self, file_id: str) -> dict[str, Any] | None:
        """
        Get metadata for a specific file.

        Args:
            file_id: File ID or path

        Returns:
            File metadata dictionary or None if not found
        """
        return self.metadata["files"].get(file_id)

    def get_source_metadata(self, source: str) -> dict[str, Any] | None:
        """
        Get metadata for a specific source.

        Args:
            source: Source name

        Returns:
            Source metadata dictionary or None if not found
        """
        return self.metadata["sources"].get(source)

    def get_quality_metrics(self) -> dict[str, float]:
        """
        Get quality metrics for collected data.

        Returns:
            Dictionary of quality metrics
        """
        return self.metadata["quality_metrics"]

    def _update_quality_metrics(self) -> None:
        """Update quality metrics based on current metadata."""
        total_files = self.metadata["stats"]["total_files"]
        if total_files == 0:
            return

        # Calculate completeness (ratio of successful files)
        successful_files = self.metadata["stats"]["successful_files"]
        self.metadata["quality_metrics"]["completeness"] = successful_files / total_files

        # Calculate freshness (percentage of files collected within the last 24 hours)
        now = datetime.now(UTC)
        fresh_files = 0

        for file_id, file_metadata in self.metadata["files"].items():
            timestamp_str = file_metadata.get("timestamp")
            if timestamp_str:
                try:
                    timestamp = datetime.fromisoformat(timestamp_str)
                    if (now - timestamp).total_seconds() < 24 * 60 * 60:  # 24 hours
                        fresh_files += 1
                except (ValueError, TypeError):
                    pass

        self.metadata["quality_metrics"]["freshness"] = fresh_files / total_files

        # Calculate consistency (ratio of sources with at least one successful file)
        sources_with_data = sum(
            1 for source, data in self.metadata["sources"].items() if data.get("successful", 0) > 0
        )
        total_sources = len(self.metadata["sources"])

        if total_sources > 0:
            self.metadata["quality_metrics"]["consistency"] = sources_with_data / total_sources

    def find_files_by_criteria(self, criteria: dict[str, Any]) -> list[dict[str, Any]]:
        """
        Find files matching specific criteria.

        Args:
            criteria: Dictionary of criteria to match

        Returns:
            List of matching file metadata dictionaries
        """
        matching_files = []

        for file_id, file_metadata in self.metadata["files"].items():
            matches = True

            for key, value in criteria.items():
                if key not in file_metadata or file_metadata[key] != value:
                    matches = False
                    break

            if matches:
                matching_files.append(file_metadata)

        return matching_files

    def get_stats(self) -> dict[str, Any]:
        """
        Get comprehensive statistics about collected data.

        Returns:
            Dictionary of statistics
        """
        stats = self.metadata["stats"].copy()

        # Add calculated statistics
        if stats["total_files"] > 0:
            stats["success_rate"] = stats["successful_files"] / stats["total_files"]
        else:
            stats["success_rate"] = 0.0

        stats["total_size_mb"] = stats["total_size_bytes"] / (1024 * 1024)
        stats["sources_count"] = len(self.metadata["sources"])

        return stats

    def identify_data_gaps(self) -> dict[str, Any]:
        """
        Identify gaps in the collected data.

        Returns:
            Dictionary describing data gaps
        """
        gaps = {"missing_sources": [], "incomplete_sources": [], "stale_sources": []}

        # Check for sources with no successful files
        for source, data in self.metadata["sources"].items():
            if data.get("successful", 0) == 0:
                gaps["missing_sources"].append(source)
            elif data.get("successful", 0) < data.get("failed", 0):
                # More failures than successes
                gaps["incomplete_sources"].append(
                    {
                        "source": source,
                        "successful": data.get("successful", 0),
                        "failed": data.get("failed", 0),
                    }
                )

        # Check for stale data (no updates in the last 24 hours)
        now = datetime.now(UTC)
        for source, data in self.metadata["sources"].items():
            last_updated = data.get("last_updated")
            if last_updated:
                try:
                    update_time = datetime.fromisoformat(last_updated)
                    if (now - update_time).total_seconds() > 24 * 60 * 60:  # 24 hours
                        gaps["stale_sources"].append(
                            {
                                "source": source,
                                "last_updated": last_updated,
                                "hours_since_update": (now - update_time).total_seconds() / 3600,
                            }
                        )
                except (ValueError, TypeError):
                    pass

        return gaps
