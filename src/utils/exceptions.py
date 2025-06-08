"""
Exception classes for SurfCastAI.
Provides a hierarchy of custom exceptions for different error types.
"""

class SurfCastAIError(Exception):
    """Base exception for all SurfCastAI errors."""
    pass


class ConfigError(SurfCastAIError):
    """Error in configuration."""
    pass


class HTTPError(SurfCastAIError):
    """Base class for HTTP-related errors."""
    pass


class NetworkError(HTTPError):
    """Network connectivity error."""
    pass


class RateLimitError(HTTPError):
    """Rate limiting error."""
    pass


class SecurityError(SurfCastAIError):
    """Security-related error."""
    pass


class ValidationError(SurfCastAIError):
    """Data validation error."""
    pass


class DataCollectionError(SurfCastAIError):
    """Error during data collection."""
    pass


class ProcessingError(SurfCastAIError):
    """Error during data processing."""
    pass


class ForecastGenerationError(SurfCastAIError):
    """Error during forecast generation."""
    pass


class APIError(SurfCastAIError):
    """Error from external API."""
    
    def __init__(self, message: str, status_code: int = None, response: str = None):
        super().__init__(message)
        self.status_code = status_code
        self.response = response