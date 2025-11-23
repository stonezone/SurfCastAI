"""
Configuration management for SurfCastAI.
Provides a unified interface for loading and accessing configuration.
"""

import logging
import os
from pathlib import Path
from typing import Any, Set

import yaml
from dotenv import load_dotenv

from .rate_limiter import RateLimitConfig

# Load environment variables from .env file at module import
# This ensures env vars are available before any config is loaded
# Get project root (2 levels up from this file: src/core/config.py)
_project_root = Path(__file__).parent.parent.parent
_env_path = _project_root / ".env"
load_dotenv(
    dotenv_path=_env_path, override=True
)  # override=True allows .env to override shell variables

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

    def __init__(self, config_path: str | Path | None = None, *, auto_discover: bool = False):
        """
        Initialize configuration from YAML file.

        Args:
            config_path: Path to config.yaml file
            auto_discover: Whether to search default locations when config_path not provided
        """
        self._config = {}

        if config_path:
            self.load(config_path)
        else:
            if auto_discover:
                # Try default locations
                default_paths = [
                    Path("config/config.yaml"),
                    Path("config/config.yml"),
                    Path(os.path.expanduser("~/.surfcastai/config.yaml")),
                    Path("/etc/surfcastai/config.yaml"),
                ]

                for path in default_paths:
                    if path.exists():
                        self.load(path)
                        break

    def load(self, config_path: str | Path):
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
            with open(path) as f:
                self._config = yaml.safe_load(f)
            logger.info(f"Loaded configuration from {path}")
        except Exception as e:
            logger.error(f"Error loading configuration from {path}: {e}")
            raise

    def get(self, section: str, key: str | None = None, default: Any = None) -> Any:
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

    def set(self, section: str, key: str | None, value: Any) -> None:
        """Set a configuration value in-memory."""
        if section not in self._config or not isinstance(self._config[section], dict):
            self._config[section] = {}

        if key is None:
            if isinstance(value, dict):
                self._config[section] = value
            else:
                raise ValueError("Top-level set requires a mapping value")
        else:
            self._config[section][key] = value

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
            return value.lower() in ("true", "yes", "1", "on")

        return bool(value)

    def getlist(self, section: str, key: str, default: list | None = None) -> list:
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
            return [item.strip() for item in value.split(",")]

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

    # ------------------------------------------------------------------
    # Validation helpers
    # ------------------------------------------------------------------
    def validate(self) -> tuple[list[str], list[str]]:
        """
        Validate configuration comprehensively.

        Returns:
            Tuple of (errors, warnings) where errors are critical issues
            that prevent operation and warnings are non-critical issues.
        """
        errors: list[str] = []
        warnings: list[str] = []

        # Validate output directory
        output_dir = self.get("general", "output_directory")
        if output_dir and not Path(output_dir).exists():
            warnings.append(
                f"Output directory does not exist: {output_dir}. It will be created when needed."
            )

        # Validate templates directory
        templates_dir = self.get("forecast", "templates_dir")
        if templates_dir and not Path(templates_dir).exists():
            errors.append(f"Forecast templates directory missing: {templates_dir}")

        # Validate API key if not using local generator
        use_local = self.getboolean("forecast", "use_local_generator", False)
        if not use_local:
            try:
                api_key = self.openai_api_key
            except ValueError as e:
                errors.append(str(e))

        # Validate model names
        model = self.openai_model
        valid_models = [
            "gpt-5-nano",
            "gpt-5-mini",
            "gpt-5",
            "gpt-4",
            "gpt-4-turbo",
            "gpt-3.5-turbo",
        ]
        if model not in valid_models:
            warnings.append(
                f"Unknown OpenAI model: {model}. Valid models: {', '.join(valid_models)}"
            )

        # Validate specialist configuration
        if self.getboolean("forecast", "use_specialist_team", False):
            specialists = ["buoy_analyst", "pressure_analyst", "senior_forecaster"]
            for specialist in specialists:
                try:
                    specialist_model = self.get_specialist_model(specialist)
                    if not specialist_model:
                        errors.append(f"Specialist '{specialist}' has no model configured")
                    elif specialist_model not in valid_models:
                        warnings.append(
                            f"Specialist '{specialist}' uses unknown model: {specialist_model}"
                        )
                except ValueError as e:
                    errors.append(str(e))

        # Validate data source URLs
        try:
            from ..utils.exceptions import SecurityError
            from ..utils.security import validate_url

            data_sources = self._resolve_data_sources()
            for source_type, config in data_sources.items():
                if isinstance(config, dict) and "urls" in config:
                    urls = config["urls"]
                    if isinstance(urls, list):
                        for url in urls:
                            try:
                                validate_url(url)
                            except SecurityError as e:
                                errors.append(f"Invalid URL in {source_type}: {url} - {str(e)}")
                            except Exception as e:
                                errors.append(
                                    f"Error validating URL in {source_type}: {url} - {str(e)}"
                                )
        except ImportError:
            warnings.append("Could not import security module for URL validation")

        # Validate rate limits
        rate_limits = self.get("rate_limits", key=None, default={})
        if isinstance(rate_limits, dict):
            for domain, config in rate_limits.items():
                if domain == "default":
                    continue

                if isinstance(config, dict):
                    rps = config.get("requests_per_second", 1.0)
                    try:
                        rps_float = float(rps)
                        if rps_float <= 0:
                            errors.append(f"Invalid rate limit for {domain}: {rps} (must be > 0)")
                    except (ValueError, TypeError):
                        errors.append(
                            f"Invalid rate limit value for {domain}: {rps} (must be numeric)"
                        )

                    # Validate burst_size if present
                    burst_size = config.get("burst_size")
                    if burst_size is not None:
                        try:
                            burst_int = int(burst_size)
                            if burst_int <= 0:
                                errors.append(
                                    f"Invalid burst_size for {domain}: {burst_size} (must be > 0)"
                                )
                        except (ValueError, TypeError):
                            errors.append(
                                f"Invalid burst_size value for {domain}: {burst_size} (must be integer)"
                            )

        return errors, warnings

    def get_rate_limits(self) -> dict[str, RateLimitConfig]:
        """
        Get rate limit configurations for all domains.

        Returns:
            Dictionary mapping domains to rate limit configurations
        """
        limits = {}
        rate_limits = self.get("rate_limits", key=None, default={})

        for domain, config in rate_limits.items():
            if domain == "default":
                continue

            if isinstance(config, dict):
                limits[domain] = RateLimitConfig(
                    requests_per_second=config.get("requests_per_second", 1.0),
                    burst_size=config.get("burst_size", 5),
                )
            elif isinstance(config, (int, float)):
                limits[domain] = RateLimitConfig(requests_per_second=float(config), burst_size=5)

        return limits

    def _resolve_data_sources(self) -> dict[str, dict[str, Any]]:
        """Return normalized data source configuration (supports legacy agents entries)."""
        data_sources = self.get("data_sources", key=None, default=None)
        if isinstance(data_sources, dict) and data_sources:
            return data_sources

        legacy_agents = self.get("agents", key=None, default={})
        normalized: dict[str, dict[str, Any]] = {}
        if isinstance(legacy_agents, dict):
            for name, cfg in legacy_agents.items():
                if isinstance(cfg, dict):
                    normalized[name] = {
                        "enabled": cfg.get("enabled", False),
                        "urls": cfg.get("urls", []),
                    }
        return normalized

    def get_data_source_urls(self, source_type: str | None = None) -> dict[str, list[str]]:
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
            if isinstance(source_config, dict) and "urls" in source_config:
                return {source_type: list(source_config.get("urls", []))}
            return {source_type: []}

        for src_type, config in data_sources.items():
            if isinstance(config, dict) and "urls" in config:
                sources[src_type] = list(config.get("urls", []))

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
            if isinstance(config, dict) and config.get("enabled", True):
                enabled.add(source_type)

        return enabled

    @property
    def data_directory(self) -> Path:
        """Get data directory path."""
        raw = self.get("general", "data_directory", "./data")
        return Path(raw)

    @property
    def output_directory(self) -> Path:
        """Get output directory path."""
        raw = self.get("general", "output_directory", "./output")
        return Path(raw)

    @property
    def openai_api_key(self) -> str | None:
        """
        Get OpenAI API key from environment variable only.

        BREAKING CHANGE: As of this version, API keys must come from environment
        variables only for security reasons. Config file API keys are no longer supported.

        Returns:
            API key from OPENAI_API_KEY environment variable

        Raises:
            ValueError: If OPENAI_API_KEY is not set in environment
        """
        env_key = os.getenv("OPENAI_API_KEY")
        if not env_key:
            raise ValueError(
                "OPENAI_API_KEY environment variable not set. "
                "For security, API keys must come from environment variables only."
            )
        return env_key

    @property
    def openai_model(self) -> str:
        """
        Get OpenAI model name (legacy property for backward compatibility).

        For tiered specialist architecture, use get_specialist_model() instead.
        Falls back to 'model' key, then 'default_model', then 'gpt-5-nano'.
        """
        # Try legacy 'model' key first for backward compatibility
        model = self.get("openai", "model")
        if model:
            return model
        # Fall back to 'default_model' if using new config structure
        return self.get("openai", "default_model", "gpt-4o")

    def get_specialist_model(self, specialist_name: str) -> str:
        """
        Get the AI model assigned to a specific specialist.

        Falls back to default_model if specialist not configured, maintaining
        full backward compatibility with old configuration files.

        Args:
            specialist_name: Specialist identifier (lowercase with underscores)
                            e.g., 'buoy_analyst', 'pressure_analyst', 'senior_forecaster'

        Returns:
            Model name string (e.g., 'gpt-5-nano', 'gpt-5-mini', 'gpt-5')

        Example:
            >>> config.get_specialist_model('buoy_analyst')
            'gpt-5-nano'
            >>> config.get_specialist_model('pressure_analyst')
            'gpt-5-mini'
        """
        # Get specialist_models section (may not exist in old configs)
        specialist_models = self.get("openai", "specialist_models", {})

        if not isinstance(specialist_models, dict):
            specialist_models = {}

        # Try to get specialist-specific model
        specialist_model = specialist_models.get(specialist_name)

        if specialist_model:
            logger.debug(f"Using model '{specialist_model}' for specialist '{specialist_name}'")
            return specialist_model

        # Fall back to default_model
        default_model = self.get("openai", "default_model")
        if default_model:
            logger.debug(
                f"Specialist '{specialist_name}' not configured, "
                f"using default model '{default_model}'"
            )
            return default_model

        # NO FALLBACK: Raise exception to prevent silent accuracy degradation
        raise ValueError(
            f"No model configured for specialist '{specialist_name}'. "
            f"Please configure openai.specialist_models.{specialist_name} or openai.default_model "
            f"in your config file to prevent silent accuracy degradation."
        )

    def __getitem__(self, key: str) -> Any:
        """Allow dictionary-style access to top-level sections."""
        return self._config.get(key, {})

    def __contains__(self, key: str) -> bool:
        """Check if section exists."""
        return key in self._config


def load_config(config_path: str | Path | None = None) -> Config:
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
    return Config(config_path, auto_discover=True)
