"""
Utility functions and classes for SurfCastAI.
"""

from .exceptions import (
    SurfCastAIError, ConfigError, HTTPError, NetworkError,
    RateLimitError, SecurityError, ValidationError,
    DataCollectionError, ProcessingError, ForecastGenerationError,
    APIError
)

from .security import (
    validate_url, sanitize_filename, validate_file_path, is_subpath
)

__all__ = [
    'SurfCastAIError',
    'ConfigError',
    'HTTPError',
    'NetworkError',
    'RateLimitError',
    'SecurityError',
    'ValidationError',
    'DataCollectionError',
    'ProcessingError',
    'ForecastGenerationError',
    'APIError',
    'validate_url',
    'sanitize_filename',
    'validate_file_path',
    'is_subpath'
]