"""
Configuration management for SurfCastAI.
Provides a unified interface for loading and accessing configuration.
"""

import yaml
import os
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Union, Set
from dotenv import load_dotenv
from .rate_limiter import RateLimitConfig

# Load environment variables from .env file at module import
# This ensures env vars are available before any config is loaded
# Get project root (2 levels up from this file: src/core/config.py)
_project_root = Path(__file__).parent.parent.parent
_env_path = _project_root / '.env'
load_dotenv(dotenv_path=_env_path, override=True)  # override=True allows .env to override shell variables

logger = logging.getLogger(__name__)


class Config:
    """
    Centralized configuration manager for SurfCastAI.
    
    Features:
    - Typed access to configuration values (get, getint, getfloat, getboolean)
    - Default values for missing configuration
    - Nested configuration support
    - Validation of configuration values
    """
    
    def __init__(self, config_path: Optional[Union[str, Path]] = None):
        """
        Initialize configuration from YAML file.
        
        Args:
            config_path: Path to config.yaml file
        """
        self._config = {}
        
        if config_path:
            self.load(config_path)
        else:
            # Try default locations
            default_paths = [
                Path("config/config.yaml"),
                Path("config/config.yml"),
                Path(os.path.expanduser("~/.surfcastai/config.yaml")),
                Path("/etc/surfcastai/config.yaml")
            ]
            
            for path in default_paths:
                if path.exists():
                    self.load(path)
                    break
    
    def load(self, config_path: Union[str, Path]):
        """
        Load configuration from file.
        
        Args:
            config_path: Path to configuration file
        """
        path = Path(config_path)
        
        if not path.exists():
            logger.warning(f"Configuration file not found: {path}")
            return
        
        try:
            with open(path, 'r') as f:
                self._config = yaml.safe_load(f)
            logger.info(f"Loaded configuration from {path}")
        except Exception as e:
            logger.error(f"Error loading configuration from {path}: {e}")
            raise
    
    def get(self, section: str, key: Optional[str] = None, default: Any = None) -> Any:
        """
        Get configuration value.
        
        Args:
            section: Configuration section
            key: Optional key within section
            default: Default value if not found
            
        Returns:
            Configuration value or default
        """
        if section not in self._config:
            return default
        
        if key is None:
            return self._config[section]
        
        return self._config[section].get(key, default)
    
    def getint(self, section: str, key: str, default: int = 0) -> int:
        """
        Get integer configuration value.
        
        Args:
            section: Configuration section
            key: Key within section
            default: Default value if not found
            
        Returns:
            Integer value
        """
        value = self.get(section, key, default)
        try:
            return int(value)
        except (ValueError, TypeError):
            logger.warning(f"Invalid integer value for {section}.{key}: {value}")
            return default
    
    def getfloat(self, section: str, key: str, default: float = 0.0) -> float:
        """
        Get float configuration value.
        
        Args:
            section: Configuration section
            key: Key within section
            default: Default value if not found
            
        Returns:
            Float value
        """
        value = self.get(section, key, default)
        try:
            return float(value)
        except (ValueError, TypeError):
            logger.warning(f"Invalid float value for {section}.{key}: {value}")
            return default
    
    def getboolean(self, section: str, key: str, default: bool = False) -> bool:
        """
        Get boolean configuration value.
        
        Args:
            section: Configuration section
            key: Key within section
            default: Default value if not found
            
        Returns:
            Boolean value
        """
        value = self.get(section, key, default)
        
        if isinstance(value, bool):
            return value
        
        if isinstance(value, str):
            return value.lower() in ('true', 'yes', '1', 'on')
        
        return bool(value)
    
    def getlist(self, section: str, key: str, default: Optional[List] = None) -> List:
        """
        Get list configuration value.
        
        Args:
            section: Configuration section
            key: Key within section
            default: Default value if not found
            
        Returns:
            List value
        """
        value = self.get(section, key, default or [])
        
        if isinstance(value, list):
            return value
        
        if isinstance(value, str):
            return [item.strip() for item in value.split(',')]
        
        return default or []
    
    def get_nested(self, *keys: str, default: Any = None) -> Any:
        """
        Get nested configuration value.
        
        Args:
            *keys: Sequence of keys to traverse
            default: Default value if not found
            
        Returns:
            Nested value or default
        """
        value = self._config
        
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        
        return value
    
    def get_rate_limits(self) -> Dict[str, RateLimitConfig]:
        """
        Get rate limit configurations for all domains.
        
        Returns:
            Dictionary mapping domains to rate limit configurations
        """
        limits = {}
        rate_limits = self.get('rate_limits', {})
        
        for domain, config in rate_limits.items():
            if domain == 'default':
                continue
                
            if isinstance(config, dict):
                limits[domain] = RateLimitConfig(
                    requests_per_second=config.get('requests_per_second', 1.0),
                    burst_size=config.get('burst_size', 5)
                )
            elif isinstance(config, (int, float)):
                limits[domain] = RateLimitConfig(
                    requests_per_second=float(config),
                    burst_size=5
                )
        
        return limits
    
    def _resolve_data_sources(self) -> Dict[str, Dict[str, Any]]:
        """Return normalized data source configuration (supports legacy agents entries)."""
        data_sources = self.get('data_sources', None)
        if isinstance(data_sources, dict) and data_sources:
            return data_sources

        legacy_agents = self.get('agents', {})
        normalized: Dict[str, Dict[str, Any]] = {}
        if isinstance(legacy_agents, dict):
            for name, cfg in legacy_agents.items():
                if isinstance(cfg, dict):
                    normalized[name] = {
                        'enabled': cfg.get('enabled', False),
                        'urls': cfg.get('urls', [])
                    }
        return normalized

    def get_data_source_urls(self, source_type: Optional[str] = None) -> Dict[str, List[str]]:
        """
        Get URLs for data sources.
        
        Args:
            source_type: Optional type of data source (buoys, weather, etc.)
            
        Returns:
            Dictionary mapping source types to URL lists
        """
        sources = {}
        data_sources = self._resolve_data_sources()

        if source_type:
            source_config = data_sources.get(source_type, {})
            if isinstance(source_config, dict) and 'urls' in source_config:
                return {source_type: list(source_config.get('urls', []))}
            return {source_type: []}

        for src_type, config in data_sources.items():
            if isinstance(config, dict) and 'urls' in config:
                sources[src_type] = list(config.get('urls', []))

        return sources
    
    def get_enabled_data_sources(self) -> Set[str]:
        """
        Get set of enabled data source types.
        
        Returns:
            Set of enabled source types
        """
        enabled = set()
        data_sources = self._resolve_data_sources()

        for source_type, config in data_sources.items():
            if isinstance(config, dict) and config.get('enabled', True):
                enabled.add(source_type)

        return enabled
    
    @property
    def data_directory(self) -> Path:
        """Get data directory path."""
        return Path(self.get('general', 'data_directory', './data'))
    
    @property
    def output_directory(self) -> Path:
        """Get output directory path."""
        return Path(self.get('general', 'output_directory', './output'))
    
    @property
    def openai_api_key(self) -> Optional[str]:
        """
        Get OpenAI API key with priority:
        1. Environment variable (OPENAI_API_KEY)
        2. Config file (config.yaml)
        3. None if not found
        """
        # First check environment variable
        env_key = os.getenv('OPENAI_API_KEY')
        if env_key:
            return env_key

        # Fall back to config file
        return self.get('openai', 'api_key')
    
    @property
    def openai_model(self) -> str:
        """Get OpenAI model name."""
        return self.get('openai', 'model', 'gpt-4o')
    
    def __getitem__(self, key: str) -> Any:
        """Allow dictionary-style access to top-level sections."""
        return self._config.get(key, {})
    
    def __contains__(self, key: str) -> bool:
        """Check if section exists."""
        return key in self._config


def load_config(config_path: Optional[Union[str, Path]] = None) -> Config:
    """
    Load configuration from file.

    Environment variables from .env are loaded automatically on module import,
    ensuring they're available before config.yaml is processed.

    Args:
        config_path: Path to configuration file

    Returns:
        Config instance
    """
    # Note: load_dotenv() is already called at module import time
    # This ensures env vars are loaded before any config instantiation
    return Config(config_path)