"""
Unit tests for comprehensive config validation (Task 2.2).

Tests validation of:
- Model names
- Specialist configuration
- Data source URLs
- Rate limits
- Templates directory
- API key requirements
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from src.core.config import Config


class TestConfigValidation:
    """Test comprehensive configuration validation."""

    def test_valid_config_no_errors(self, tmp_path):
        """Test that a valid configuration produces no errors."""
        config_data = {
            "general": {
                "data_directory": "./data",
                "output_directory": str(tmp_path / "output"),
                "log_level": "INFO",
                "log_file": "surfcastai.log",
            },
            "forecast": {
                "templates_dir": str(tmp_path / "templates"),
                "use_local_generator": True,
                "use_specialist_team": False,
            },
            "openai": {"default_model": "gpt-5-nano"},
            "data_sources": {
                "buoys": {
                    "enabled": True,
                    "urls": ["https://www.ndbc.noaa.gov/data/realtime2/51001.txt"],
                }
            },
            "rate_limits": {"www.ndbc.noaa.gov": {"requests_per_second": 1.0, "burst_size": 5}},
        }

        # Create templates directory
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()

        # Write config
        config_file = tmp_path / "config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        # Load and validate
        config = Config(config_file)
        errors, warnings = config.validate()

        assert len(errors) == 0, f"Unexpected errors: {errors}"
        # May have warnings about output directory not existing
        assert all("output_directory" in w or "Output directory" in w for w in warnings)

    def test_invalid_model_name_warning(self, tmp_path):
        """Test that invalid model names generate warnings."""
        config_data = {
            "general": {"data_directory": "./data", "output_directory": "./output"},
            "forecast": {"use_local_generator": True},
            "openai": {"default_model": "gpt-9000"},  # Invalid model
        }

        config_file = tmp_path / "config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        config = Config(config_file)
        errors, warnings = config.validate()

        assert any("Unknown OpenAI model" in w and "gpt-9000" in w for w in warnings)

    def test_valid_model_names(self, tmp_path):
        """Test that all valid model names pass validation."""
        valid_models = [
            "gpt-5-nano",
            "gpt-5-mini",
            "gpt-5",
            "gpt-4",
            "gpt-4-turbo",
            "gpt-3.5-turbo",
        ]

        for model in valid_models:
            config_data = {
                "general": {"data_directory": "./data", "output_directory": "./output"},
                "forecast": {"use_local_generator": True},
                "openai": {"default_model": model},
            }

            config_file = tmp_path / f'config_{model.replace(".", "_")}.yaml'
            with open(config_file, "w") as f:
                yaml.dump(config_data, f)

            config = Config(config_file)
            errors, warnings = config.validate()

            # Filter out warnings about directories
            model_warnings = [w for w in warnings if "model" in w.lower()]
            assert (
                len(model_warnings) == 0
            ), f"Model {model} should be valid but got warnings: {model_warnings}"

    def test_specialist_missing_model_error(self, tmp_path):
        """Test that specialists without configured models generate errors."""
        config_data = {
            "general": {"data_directory": "./data", "output_directory": "./output"},
            "forecast": {"use_local_generator": True, "use_specialist_team": True},
            "openai": {
                # No default_model and no specialist_models
            },
        }

        config_file = tmp_path / "config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        config = Config(config_file)
        errors, warnings = config.validate()

        # Should have errors for missing specialist models
        assert len(errors) > 0
        assert any("specialist" in e.lower() for e in errors)

    def test_specialist_valid_configuration(self, tmp_path):
        """Test that properly configured specialists pass validation."""
        config_data = {
            "general": {"data_directory": "./data", "output_directory": "./output"},
            "forecast": {"use_local_generator": True, "use_specialist_team": True},
            "openai": {
                "default_model": "gpt-5-nano",
                "specialist_models": {
                    "buoy_analyst": "gpt-5-nano",
                    "pressure_analyst": "gpt-5-mini",
                    "senior_forecaster": "gpt-5",
                },
            },
        }

        config_file = tmp_path / "config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        config = Config(config_file)
        errors, warnings = config.validate()

        # Should not have specialist-related errors
        specialist_errors = [e for e in errors if "specialist" in e.lower()]
        assert len(specialist_errors) == 0, f"Unexpected specialist errors: {specialist_errors}"

    def test_invalid_url_error(self, tmp_path):
        """Test that invalid URLs in data sources generate errors."""
        config_data = {
            "general": {"data_directory": "./data", "output_directory": "./output"},
            "forecast": {"use_local_generator": True},
            "data_sources": {
                "buoys": {
                    "enabled": True,
                    "urls": [
                        "https://www.ndbc.noaa.gov/data/realtime2/51001.txt",
                        "ftp://invalid.url",  # Invalid scheme
                        "not-a-url",  # Invalid URL
                    ],
                }
            },
        }

        config_file = tmp_path / "config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        config = Config(config_file)
        errors, warnings = config.validate()

        # Should have errors for invalid URLs
        assert len(errors) >= 2  # At least 2 invalid URLs
        assert any("Invalid URL" in e for e in errors)

    def test_localhost_url_rejected(self, tmp_path):
        """Test that localhost URLs are rejected."""
        config_data = {
            "general": {"data_directory": "./data", "output_directory": "./output"},
            "forecast": {"use_local_generator": True},
            "data_sources": {"test": {"enabled": True, "urls": ["http://localhost:8000/data"]}},
        }

        config_file = tmp_path / "config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        config = Config(config_file)
        errors, warnings = config.validate()

        # Should have error mentioning localhost
        assert any("localhost" in e for e in errors)

    def test_invalid_rate_limit_error(self, tmp_path):
        """Test that invalid rate limits generate errors."""
        config_data = {
            "general": {"data_directory": "./data", "output_directory": "./output"},
            "forecast": {"use_local_generator": True},
            "rate_limits": {"example.com": {"requests_per_second": -1.0}},  # Invalid: must be > 0
        }

        config_file = tmp_path / "config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        config = Config(config_file)
        errors, warnings = config.validate()

        assert any("Invalid rate limit" in e and "example.com" in e for e in errors)

    def test_zero_rate_limit_error(self, tmp_path):
        """Test that zero rate limit generates error."""
        config_data = {
            "general": {"data_directory": "./data", "output_directory": "./output"},
            "forecast": {"use_local_generator": True},
            "rate_limits": {"example.com": {"requests_per_second": 0}},  # Invalid: must be > 0
        }

        config_file = tmp_path / "config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        config = Config(config_file)
        errors, warnings = config.validate()

        assert any("Invalid rate limit" in e and "example.com" in e for e in errors)

    def test_invalid_burst_size_error(self, tmp_path):
        """Test that invalid burst_size generates error."""
        config_data = {
            "general": {"data_directory": "./data", "output_directory": "./output"},
            "forecast": {"use_local_generator": True},
            "rate_limits": {
                "example.com": {
                    "requests_per_second": 1.0,
                    "burst_size": -5,  # Invalid: must be > 0
                }
            },
        }

        config_file = tmp_path / "config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        config = Config(config_file)
        errors, warnings = config.validate()

        assert any("burst_size" in e and "example.com" in e for e in errors)

    def test_valid_rate_limits(self, tmp_path):
        """Test that valid rate limits pass validation."""
        config_data = {
            "general": {"data_directory": "./data", "output_directory": "./output"},
            "forecast": {"use_local_generator": True},
            "rate_limits": {
                "example.com": {"requests_per_second": 2.5, "burst_size": 10},
                "another.com": {"requests_per_second": 1.0, "burst_size": 3},
            },
        }

        config_file = tmp_path / "config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        config = Config(config_file)
        errors, warnings = config.validate()

        # Should not have rate limit errors
        rate_errors = [e for e in errors if "rate" in e.lower()]
        assert len(rate_errors) == 0, f"Unexpected rate limit errors: {rate_errors}"

    def test_missing_templates_dir_error(self, tmp_path):
        """Test that missing templates directory generates error."""
        config_data = {
            "general": {"data_directory": "./data", "output_directory": "./output"},
            "forecast": {
                "templates_dir": str(tmp_path / "nonexistent"),
                "use_local_generator": True,
            },
        }

        config_file = tmp_path / "config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        config = Config(config_file)
        errors, warnings = config.validate()

        assert any("templates directory missing" in e.lower() for e in errors)

    def test_multiple_validation_errors(self, tmp_path):
        """Test that multiple validation errors are all reported."""
        config_data = {
            "general": {"data_directory": "./data", "output_directory": "./output"},
            "forecast": {
                "templates_dir": str(tmp_path / "nonexistent"),  # Error: missing
                "use_local_generator": True,
                "use_specialist_team": True,
            },
            "openai": {
                "default_model": "invalid-model"  # Warning: unknown model
                # Missing specialist configuration will trigger errors
            },
            "data_sources": {
                "test": {"enabled": True, "urls": ["not-a-url"]}  # Error: invalid URL
            },
            "rate_limits": {"example.com": {"requests_per_second": -1}},  # Error: invalid rate
        }

        config_file = tmp_path / "config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        config = Config(config_file)
        errors, warnings = config.validate()

        # Should have multiple errors: templates, URL, rate_limit
        # Note: specialist errors will be 3 (one per specialist: buoy_analyst, pressure_analyst, senior_forecaster)
        assert len(errors) >= 3  # At minimum: templates, URL, rate_limit
        assert len(warnings) >= 1  # unknown model

        # Verify we have errors for different types of issues
        assert any("templates" in e.lower() for e in errors)
        assert any("url" in e.lower() or "not-a-url" in e for e in errors)
        assert any("rate limit" in e.lower() for e in errors)

    def test_legacy_agents_config_validation(self, tmp_path):
        """Test that legacy 'agents' configuration is validated."""
        config_data = {
            "general": {"data_directory": "./data", "output_directory": "./output"},
            "forecast": {"use_local_generator": True},
            "agents": {  # Legacy format
                "buoys": {
                    "enabled": True,
                    "urls": ["https://www.ndbc.noaa.gov/data/realtime2/51001.txt"],
                }
            },
        }

        config_file = tmp_path / "config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        config = Config(config_file)
        errors, warnings = config.validate()

        # Should validate legacy format without errors
        url_errors = [e for e in errors if "URL" in e]
        assert len(url_errors) == 0

    def test_non_numeric_rate_limit_error(self, tmp_path):
        """Test that non-numeric rate limit values generate errors."""
        config_data = {
            "general": {"data_directory": "./data", "output_directory": "./output"},
            "forecast": {"use_local_generator": True},
            "rate_limits": {"example.com": {"requests_per_second": "fast"}},  # Invalid: not numeric
        }

        config_file = tmp_path / "config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        config = Config(config_file)
        errors, warnings = config.validate()

        assert any("rate limit value" in e.lower() and "numeric" in e.lower() for e in errors)

    def test_specialist_with_invalid_model_warning(self, tmp_path):
        """Test that specialists with invalid model names generate warnings."""
        config_data = {
            "general": {"data_directory": "./data", "output_directory": "./output"},
            "forecast": {"use_local_generator": True, "use_specialist_team": True},
            "openai": {
                "default_model": "gpt-5-nano",
                "specialist_models": {
                    "buoy_analyst": "gpt-9000",  # Invalid model
                    "pressure_analyst": "gpt-5-mini",
                    "senior_forecaster": "gpt-5",
                },
            },
        }

        config_file = tmp_path / "config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        config = Config(config_file)
        errors, warnings = config.validate()

        assert any("buoy_analyst" in w and "unknown model" in w.lower() for w in warnings)

    def test_validate_reports_missing_openai_key_when_local_generator_disabled(self, tmp_path):
        """Test that missing API key is caught when local generator is disabled."""
        config_data = {
            "general": {"data_directory": "./data", "output_directory": "./output"},
            "forecast": {
                "use_local_generator": False,
                "templates_dir": str(tmp_path / "templates_missing"),
            },
            "openai": {"model": "gpt-5-nano"},
        }

        config_file = tmp_path / "config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        config = Config(config_file)

        with patch.dict(os.environ, {"OPENAI_API_KEY": ""}):
            errors, warnings = config.validate()

        assert any("OPENAI_API_KEY" in err for err in errors)
        assert any("templates directory missing" in err.lower() for err in errors)
