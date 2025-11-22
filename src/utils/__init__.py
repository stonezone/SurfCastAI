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
from .prompt_loader import PromptLoader
from .validation_feedback import (
    ValidationFeedback, PerformanceReport, ShorePerformance
)
from .numeric import safe_float

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
    'is_subpath',
    'PromptLoader',
    'ValidationFeedback',
    'PerformanceReport',
    'ShorePerformance',
    'safe_float'
]
