"""
Data Collector for orchestrating data collection from multiple agents.
"""

import asyncio
import logging
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any, Optional, Set

from .config import Config
from .http_client import HTTPClient
from ..agents.buoy_agent import BuoyAgent
from ..agents.weather_agent import WeatherAgent
from ..agents.model_agent import ModelAgent
from ..agents.satellite_agent import SatelliteAgent


class DataCollector:
    """
    Orchestrates data collection from multiple specialized agents.
    
    Features:
    - Coordinates multiple data collection agents
    - Manages HTTP client with rate limiting
    - Creates organized data bundles
    - Tracks metadata for all collected data
    - Provides statistics on collection performance
    """
    
    def __init__(self, config: Config):
        """
        Initialize the data collector.
        
        Args:
            config: Application configuration
        """
        self.config = config
        self.logger = logging.getLogger('collector')
        
        # Configure HTTP client
        self.http_client = None
        
        # Create data directory if it doesn't exist
        self.data_dir = Path(config.data_directory)
        self.data_dir.mkdir(exist_ok=True)
        
        # Initialize statistics
        self.stats = {
            "total_files": 0,
            "successful_files": 0,
            "failed_files": 0,
            "agents": {},
            "total_size_bytes": 0
        }
        
        # Configure agents
        self.agents = {}
        self._configure_agents()
    
    def _configure_agents(self):
        """Configure all data collection agents."""
        # Determine which agents to enable
        enabled_sources = self.config.get_enabled_data_sources()
        self.logger.info(f"Enabled data sources: {', '.join(enabled_sources)}")
        
        # Initialize agents
        if 'buoys' in enabled_sources:
            self.agents['buoys'] = BuoyAgent(self.config)
        
        if 'weather' in enabled_sources:
            self.agents['weather'] = WeatherAgent(self.config)
        
        if 'models' in enabled_sources:
            self.agents['models'] = ModelAgent(self.config)
        
        if 'satellite' in enabled_sources:
            self.agents['satellite'] = SatelliteAgent(self.config)
    
    async def _ensure_http_client(self):
        """Ensure HTTP client is available and configured."""
        if self.http_client is None or self.http_client._session is None:
            self.logger.info("Creating HTTP client")
            self.http_client = HTTPClient(
                timeout=self.config.getint('data_collection', 'timeout', 30),
                max_concurrent=self.config.getint('data_collection', 'max_concurrent', 10),
                retry_attempts=self.config.getint('data_collection', 'retry_attempts', 3),
                user_agent=self.config.get('data_collection', 'user_agent', 'SurfCastAI/1.0'),
                output_dir=self.data_dir
            )
    
    async def collect_data(self, region: Optional[str] = None) -> Dict[str, Any]:
        """
        Collect data from all configured agents.
        
        Args:
            region: Optional region to focus on (e.g., 'Hawaii', 'North Pacific')
            
        Returns:
            Dictionary with collection results and metadata
        """
        # Create a unique bundle ID
        bundle_id = str(uuid.uuid4())
        bundle_time = datetime.now(timezone.utc).isoformat()
        
        # Create bundle directory
        bundle_dir = self.data_dir / bundle_id
        bundle_dir.mkdir(exist_ok=True)
        
        self.logger.info(f"Starting data collection for bundle {bundle_id}")
        
        # Ensure HTTP client is available
        await self._ensure_http_client()
        
        # Execute all agents
        agent_results = {}
        all_metadata = []
        
        try:
            # Create tasks for all agents
            tasks = []
            for agent_name, agent in self.agents.items():
                self.logger.info(f"Starting agent: {agent_name}")
                # Pass the HTTP client to the agent
                agent.http_client = self.http_client
                tasks.append(self._run_agent(agent_name, agent, bundle_dir))
            
            # Execute all tasks concurrently
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            for i, (agent_name, result) in enumerate(zip(self.agents.keys(), results)):
                if isinstance(result, Exception):
                    self.logger.error(f"Error in agent {agent_name}: {result}")
                    agent_results[agent_name] = {
                        "status": "error",
                        "error": str(result),
                        "files_collected": 0
                    }
                else:
                    metadata, stats = result
                    agent_results[agent_name] = stats
                    all_metadata.extend(metadata)
                    
                    # Update global statistics
                    self.stats["total_files"] += stats["total"]
                    self.stats["successful_files"] += stats["successful"]
                    self.stats["failed_files"] += stats["failed"]
                    self.stats["total_size_bytes"] += stats["total_size_bytes"]
                    self.stats["agents"][agent_name] = stats
        
        finally:
            # Close HTTP client
            if self.http_client:
                await self.http_client.close()
                self.http_client = None
        
        # Save bundle metadata
        bundle_metadata = {
            "bundle_id": bundle_id,
            "timestamp": bundle_time,
            "region": region,
            "agent_results": agent_results,
            "stats": {
                "total_files": self.stats["total_files"],
                "successful_files": self.stats["successful_files"],
                "failed_files": self.stats["failed_files"],
                "total_size_mb": round(self.stats["total_size_bytes"] / (1024 * 1024), 2)
            }
        }
        
        # Save metadata files
        self._save_bundle_metadata(bundle_dir, bundle_metadata, all_metadata)
        
        # Update latest bundle reference
        self._update_latest_bundle(bundle_id)
        
        self.logger.info(f"Data collection complete. Bundle ID: {bundle_id}")
        self.logger.info(f"Total files: {self.stats['total_files']}, "
                      f"Successful: {self.stats['successful_files']}, "
                      f"Failed: {self.stats['failed_files']}")
        
        return {
            "bundle_id": bundle_id,
            "bundle_dir": str(bundle_dir),
            "stats": self.stats,
            "metadata": bundle_metadata
        }
    
    async def _run_agent(self, agent_name: str, agent: Any, bundle_dir: Path) -> tuple:
        """
        Run a single agent and collect its results.
        
        Args:
            agent_name: Name of the agent
            agent: Agent instance
            bundle_dir: Directory to store collected data
            
        Returns:
            Tuple of (metadata_list, stats_dict)
        """
        try:
            # Create agent-specific directory
            agent_dir = bundle_dir / agent_name
            agent_dir.mkdir(exist_ok=True)
            
            # Run the agent
            metadata = await agent.collect(agent_dir)
            
            # Calculate statistics
            total = len(metadata)
            successful = sum(1 for item in metadata if item.get('status') == 'success')
            failed = total - successful
            total_size = sum(int(item.get('size_bytes', 0)) for item in metadata)
            
            # Save agent-specific metadata
            self._save_agent_metadata(agent_dir, metadata)
            
            stats = {
                "total": total,
                "successful": successful,
                "failed": failed,
                "success_rate": round(successful / total * 100, 1) if total > 0 else 0,
                "total_size_bytes": total_size
            }
            
            return metadata, stats
        
        except Exception as e:
            self.logger.error(f"Error running agent {agent_name}: {e}")
            raise
    
    def _save_bundle_metadata(self, bundle_dir: Path, bundle_metadata: Dict[str, Any], 
                            all_metadata: List[Dict[str, Any]]):
        """Save bundle metadata to files."""
        # Save bundle summary
        with open(bundle_dir / "bundle_metadata.json", 'w') as f:
            json.dump(bundle_metadata, f, indent=2)
        
        # Save complete metadata
        with open(bundle_dir / "all_metadata.json", 'w') as f:
            json.dump(all_metadata, f, indent=2)
    
    def _save_agent_metadata(self, agent_dir: Path, metadata: List[Dict[str, Any]]):
        """Save agent-specific metadata."""
        with open(agent_dir / "metadata.json", 'w') as f:
            json.dump(metadata, f, indent=2)
    
    def _update_latest_bundle(self, bundle_id: str):
        """Update reference to the latest bundle."""
        with open(self.data_dir / "latest_bundle.txt", 'w') as f:
            f.write(bundle_id)
    
    def get_bundle_info(self, bundle_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get information about a specific bundle or the latest bundle.
        
        Args:
            bundle_id: Optional bundle ID (uses latest if not provided)
            
        Returns:
            Bundle information dictionary
        """
        # Get bundle ID if not provided
        if bundle_id is None:
            try:
                with open(self.data_dir / "latest_bundle.txt", 'r') as f:
                    bundle_id = f.read().strip()
            except FileNotFoundError:
                return {"error": "No bundles found"}
        
        # Check if bundle exists
        bundle_dir = self.data_dir / bundle_id
        if not bundle_dir.exists():
            return {"error": f"Bundle {bundle_id} not found"}
        
        # Load metadata
        try:
            with open(bundle_dir / "bundle_metadata.json", 'r') as f:
                metadata = json.load(f)
                return metadata
        except (FileNotFoundError, json.JSONDecodeError):
            return {
                "bundle_id": bundle_id,
                "error": "Metadata file missing or invalid"
            }
    
    def get_bundle_file_list(self, bundle_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get list of all files in a bundle.
        
        Args:
            bundle_id: Optional bundle ID (uses latest if not provided)
            
        Returns:
            List of file information dictionaries
        """
        # Get bundle ID if not provided
        if bundle_id is None:
            try:
                with open(self.data_dir / "latest_bundle.txt", 'r') as f:
                    bundle_id = f.read().strip()
            except FileNotFoundError:
                return []
        
        # Check if bundle exists
        bundle_dir = self.data_dir / bundle_id
        if not bundle_dir.exists():
            return []
        
        # Load metadata
        try:
            with open(bundle_dir / "all_metadata.json", 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return []
    
    def list_bundles(self) -> List[Dict[str, Any]]:
        """
        List all available data bundles.
        
        Returns:
            List of bundle information dictionaries
        """
        bundles = []
        
        # Find all bundle directories
        for item in self.data_dir.iterdir():
            if item.is_dir() and item.name != 'temp':
                # Try to load metadata
                try:
                    with open(item / "bundle_metadata.json", 'r') as f:
                        metadata = json.load(f)
                        bundles.append(metadata)
                except (FileNotFoundError, json.JSONDecodeError):
                    # Add basic info if metadata not available
                    bundles.append({
                        "bundle_id": item.name,
                        "timestamp": datetime.fromtimestamp(
                            item.stat().st_mtime, tz=timezone.utc
                        ).isoformat(),
                        "error": "Metadata file missing or invalid"
                    })
        
        # Sort by timestamp (newest first)
        bundles.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        
        return bundles