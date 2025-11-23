"""
Unit tests for the Config class.
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import yaml

# Add src directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))

from src.core.config import Config, load_config
from src.core.rate_limiter import RateLimitConfig


class TestConfig(unittest.TestCase):
    """Tests for the Config class."""

    def setUp(self):
        """Set up test fixtures."""
        # Sample configuration data
        self.sample_config = {
            "general": {"data_directory": "./test_data", "output_directory": "./test_output"},
            "rate_limits": {
                "default": {"requests_per_second": 1.0, "burst_size": 5},
                "api.weather.gov": {"requests_per_second": 0.5, "burst_size": 3},
                "www.ndbc.noaa.gov": 2.0,  # Simple format
            },
            "data_sources": {
                "buoys": {
                    "enabled": True,
                    "urls": ["http://example.com/buoy1", "http://example.com/buoy2"],
                },
                "weather": {"enabled": False, "urls": ["http://example.com/weather"]},
            },
            "openai": {"api_key": "test-api-key-from-config", "model": "gpt-4o"},
            "nested": {"level1": {"level2": {"value": "deep_value"}}},
            "test_section": {
                "int_value": "42",
                "float_value": "3.14",
                "bool_true": "true",
                "bool_false": "false",
                "list_value": ["item1", "item2", "item3"],
                "string_list": "a,b,c",
            },
        }

    def test_init_with_no_path(self):
        """Test initialization without a config path."""
        config = Config()
        self.assertIsInstance(config, Config)
        self.assertEqual(config._config, {})

    def test_init_with_nonexistent_path(self):
        """Test initialization with nonexistent file path."""
        config = Config("/nonexistent/path/config.yaml")
        self.assertEqual(config._config, {})

    def test_load_from_file(self):
        """Test loading configuration from a YAML file."""
        # Create temporary config file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(self.sample_config, f)
            temp_path = f.name

        try:
            config = Config(temp_path)

            # Verify loaded configuration
            self.assertEqual(config.get("general", "data_directory"), "./test_data")
            self.assertEqual(config.get("openai", "model"), "gpt-4o")
        finally:
            os.unlink(temp_path)

    def test_get_with_section_only(self):
        """Test get() with section only (returns entire section)."""
        config = Config()
        config._config = self.sample_config

        general_section = config.get("general")
        self.assertIsInstance(general_section, dict)
        self.assertEqual(general_section["data_directory"], "./test_data")

    def test_get_with_section_and_key(self):
        """Test get() with section and key."""
        config = Config()
        config._config = self.sample_config

        value = config.get("general", "data_directory")
        self.assertEqual(value, "./test_data")

    def test_get_with_default(self):
        """Test get() returns default for missing keys."""
        config = Config()
        config._config = self.sample_config

        # Missing key
        value = config.get("general", "missing_key", "default_value")
        self.assertEqual(value, "default_value")

        # Missing section
        value = config.get("missing_section", "key", "default_value")
        self.assertEqual(value, "default_value")

    def test_getint(self):
        """Test getint() type conversion."""
        config = Config()
        config._config = self.sample_config

        # Valid integer string
        value = config.getint("test_section", "int_value")
        self.assertEqual(value, 42)
        self.assertIsInstance(value, int)

        # Missing key with default
        value = config.getint("test_section", "missing", 99)
        self.assertEqual(value, 99)

        # Invalid integer (should return default)
        config._config["test_section"]["invalid_int"] = "not_a_number"
        value = config.getint("test_section", "invalid_int", 0)
        self.assertEqual(value, 0)

    def test_getfloat(self):
        """Test getfloat() type conversion."""
        config = Config()
        config._config = self.sample_config

        # Valid float string
        value = config.getfloat("test_section", "float_value")
        self.assertAlmostEqual(value, 3.14, places=2)
        self.assertIsInstance(value, float)

        # Integer converted to float
        value = config.getfloat("test_section", "int_value")
        self.assertEqual(value, 42.0)

        # Missing key with default
        value = config.getfloat("test_section", "missing", 1.5)
        self.assertEqual(value, 1.5)

        # Invalid float (should return default)
        config._config["test_section"]["invalid_float"] = "not_a_number"
        value = config.getfloat("test_section", "invalid_float", 0.0)
        self.assertEqual(value, 0.0)

    def test_getboolean(self):
        """Test getboolean() type conversion."""
        config = Config()
        config._config = self.sample_config

        # String 'true'
        value = config.getboolean("test_section", "bool_true")
        self.assertTrue(value)

        # String 'false'
        value = config.getboolean("test_section", "bool_false")
        self.assertFalse(value)

        # Boolean True
        config._config["test_section"]["actual_bool"] = True
        value = config.getboolean("test_section", "actual_bool")
        self.assertTrue(value)

        # Various truthy strings
        for truthy in ["yes", "YES", "1", "on", "ON", "True", "TRUE"]:
            config._config["test_section"]["temp"] = truthy
            self.assertTrue(config.getboolean("test_section", "temp"))

        # Missing key with default
        value = config.getboolean("test_section", "missing", True)
        self.assertTrue(value)

    def test_getlist(self):
        """Test getlist() returns list values."""
        config = Config()
        config._config = self.sample_config

        # List value
        value = config.getlist("test_section", "list_value")
        self.assertEqual(value, ["item1", "item2", "item3"])

        # String converted to list
        value = config.getlist("test_section", "string_list")
        self.assertEqual(value, ["a", "b", "c"])

        # Missing key with default
        value = config.getlist("test_section", "missing", ["default"])
        self.assertEqual(value, ["default"])

    def test_get_nested(self):
        """Test get_nested() for deeply nested values."""
        config = Config()
        config._config = self.sample_config

        # Valid nested path
        value = config.get_nested("nested", "level1", "level2", "value")
        self.assertEqual(value, "deep_value")

        # Missing nested key with default
        value = config.get_nested("nested", "level1", "missing", default="default")
        self.assertEqual(value, "default")

        # Completely missing path
        value = config.get_nested("missing", "path", default="default")
        self.assertEqual(value, "default")

    def test_get_rate_limits(self):
        """Test get_rate_limits() returns RateLimitConfig objects."""
        config = Config()
        config._config = self.sample_config

        limits = config.get_rate_limits()

        # Check that default is not included
        self.assertNotIn("default", limits)

        # Check api.weather.gov limit
        self.assertIn("api.weather.gov", limits)
        weather_limit = limits["api.weather.gov"]
        self.assertIsInstance(weather_limit, RateLimitConfig)
        self.assertEqual(weather_limit.requests_per_second, 0.5)
        self.assertEqual(weather_limit.burst_size, 3)

        # Check simple format (www.ndbc.noaa.gov)
        self.assertIn("www.ndbc.noaa.gov", limits)
        ndbc_limit = limits["www.ndbc.noaa.gov"]
        self.assertIsInstance(ndbc_limit, RateLimitConfig)
        self.assertEqual(ndbc_limit.requests_per_second, 2.0)
        self.assertEqual(ndbc_limit.burst_size, 5)  # Default burst_size

    def test_get_data_source_urls(self):
        """Test get_data_source_urls() returns URL lists."""
        config = Config()
        config._config = self.sample_config

        # Get all sources
        urls = config.get_data_source_urls()
        self.assertIn("buoys", urls)
        self.assertEqual(len(urls["buoys"]), 2)
        self.assertEqual(urls["buoys"][0], "http://example.com/buoy1")

        # Get specific source
        buoy_urls = config.get_data_source_urls("buoys")
        self.assertEqual(len(buoy_urls["buoys"]), 2)

        # Missing source
        missing_urls = config.get_data_source_urls("nonexistent")
        self.assertEqual(missing_urls, {"nonexistent": []})

    def test_get_data_source_urls_legacy_agents(self):
        """Test get_data_source_urls() with legacy 'agents' configuration."""
        config = Config()
        config._config = {
            "agents": {"buoys": {"enabled": True, "urls": ["http://example.com/buoy"]}}
        }

        urls = config.get_data_source_urls()
        self.assertIn("buoys", urls)
        self.assertEqual(urls["buoys"], ["http://example.com/buoy"])

    def test_get_enabled_data_sources(self):
        """Test get_enabled_data_sources() filters enabled sources."""
        config = Config()
        config._config = self.sample_config

        enabled = config.get_enabled_data_sources()

        # buoys is enabled
        self.assertIn("buoys", enabled)

        # weather is disabled
        self.assertNotIn("weather", enabled)

    def test_data_directory_property(self):
        """Test data_directory property."""
        config = Config()
        config._config = self.sample_config

        data_dir = config.data_directory
        self.assertIsInstance(data_dir, Path)
        # Path normalizes "./test_data" to "test_data"
        self.assertEqual(str(data_dir), "test_data")

    def test_output_directory_property(self):
        """Test output_directory property."""
        config = Config()
        config._config = self.sample_config

        output_dir = config.output_directory
        self.assertIsInstance(output_dir, Path)
        # Path normalizes "./test_output" to "test_output"
        self.assertEqual(str(output_dir), "test_output")

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key-from-env"})
    def test_openai_api_key_from_env(self):
        """Test openai_api_key prioritizes environment variable."""
        config = Config()
        config._config = self.sample_config

        # Environment variable should take precedence
        api_key = config.openai_api_key
        self.assertEqual(api_key, "test-key-from-env")

    @patch.dict(os.environ, {}, clear=True)
    def test_openai_api_key_raises_without_env(self):
        """Test openai_api_key raises ValueError when environment variable not set."""
        # Clear OPENAI_API_KEY if it exists
        os.environ.pop("OPENAI_API_KEY", None)

        config = Config()
        config._config = self.sample_config

        # Should raise ValueError when API key is not in environment
        with self.assertRaises(ValueError) as context:
            api_key = config.openai_api_key

        self.assertIn("OPENAI_API_KEY environment variable not set", str(context.exception))
        self.assertIn(
            "For security, API keys must come from environment variables only",
            str(context.exception),
        )

    def test_openai_model_property(self):
        """Test openai_model property."""
        config = Config()
        config._config = self.sample_config

        model = config.openai_model
        self.assertEqual(model, "gpt-4o")

        # Test default
        config._config = {}
        model = config.openai_model
        self.assertEqual(model, "gpt-4o")

    def test_dict_style_access(self):
        """Test dictionary-style access with __getitem__."""
        config = Config()
        config._config = self.sample_config

        general = config["general"]
        self.assertEqual(general["data_directory"], "./test_data")

        # Missing section
        missing = config["missing_section"]
        self.assertEqual(missing, {})

    def test_contains(self):
        """Test __contains__ for checking if section exists."""
        config = Config()
        config._config = self.sample_config

        self.assertIn("general", config)
        self.assertIn("openai", config)
        self.assertNotIn("missing_section", config)

    def test_load_config_function(self):
        """Test load_config() helper function."""
        # Create temporary config file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(self.sample_config, f)
            temp_path = f.name

        try:
            config = load_config(temp_path)
            self.assertIsInstance(config, Config)
            self.assertEqual(config.get("general", "data_directory"), "./test_data")
        finally:
            os.unlink(temp_path)

    def test_load_with_exception(self):
        """Test load() handles exceptions gracefully."""
        # Create invalid YAML file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("invalid: yaml: content: [[[")
            temp_path = f.name

        try:
            with self.assertRaises(Exception):
                config = Config(temp_path)
        finally:
            os.unlink(temp_path)


if __name__ == "__main__":
    unittest.main()
