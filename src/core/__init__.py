"""Core components for the SurfCastAI system."""

from typing import TYPE_CHECKING

from .bundle_manager import BundleManager
from .config import Config, load_config
from .http_client import DownloadResult, HTTPClient
from .metadata_tracker import MetadataTracker
from .rate_limiter import RateLimitConfig, RateLimiter, TokenBucket

if TYPE_CHECKING:  # pragma: no cover - for type checkers only
    from .data_collector import DataCollector  # noqa: F401

__all__ = [
    "Config",
    "load_config",
    "HTTPClient",
    "DownloadResult",
    "RateLimiter",
    "TokenBucket",
    "RateLimitConfig",
    "DataCollector",
    "BundleManager",
    "MetadataTracker",
]


def __getattr__(name: str):
    if name == "DataCollector":
        from .data_collector import DataCollector as _DataCollector

        return _DataCollector
    raise AttributeError(f"module 'src.core' has no attribute {name!r}")
