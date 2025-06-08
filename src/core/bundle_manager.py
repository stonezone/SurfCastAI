"""
Bundle Manager for organizing and managing data bundles.
"""

import json
import shutil
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional, Union


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
    
    def list_bundles(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        List all available bundles.
        
        Args:
            limit: Maximum number of bundles to return
            
        Returns:
            List of bundle information dictionaries
        """
        bundles = []
        
        # Find all bundle directories
        for item in self.data_dir.iterdir():
            if item.is_dir() and item.name != 'temp' and item.name != 'archive':
                # Try to load metadata
                metadata_path = item / "bundle_metadata.json"
                
                if metadata_path.exists():
                    try:
                        with open(metadata_path, 'r') as f:
                            metadata = json.load(f)
                            bundles.append(metadata)
                    except json.JSONDecodeError:
                        # Add basic info if metadata invalid
                        bundles.append({
                            "bundle_id": item.name,
                            "timestamp": datetime.fromtimestamp(
                                item.stat().st_mtime, tz=timezone.utc
                            ).isoformat(),
                            "error": "Invalid metadata file"
                        })
                else:
                    # Add basic info if metadata not available
                    bundles.append({
                        "bundle_id": item.name,
                        "timestamp": datetime.fromtimestamp(
                            item.stat().st_mtime, tz=timezone.utc
                        ).isoformat(),
                        "error": "Missing metadata file"
                    })
        
        # Sort by timestamp (newest first)
        bundles.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        
        # Apply limit if provided
        if limit is not None and limit > 0:
            bundles = bundles[:limit]
        
        return bundles
    
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
        
        # List all bundles
        bundles = self.list_bundles()
        
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
    
    def extract_archived_bundle(self, bundle_id: str) -> bool:
        """
        Extract an archived bundle.
        
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
            # Extract archive
            shutil.unpack_archive(
                str(archive_file),
                extract_dir=self.data_dir
            )
            
            self.logger.info(f"Extracted archive: {bundle_id}")
            return True
            
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