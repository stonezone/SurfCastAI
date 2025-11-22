"""
Token bucket rate limiter with domain-specific rate limiting.
Enhanced version combining features from both url_downloader and urlGrabber.
"""

import asyncio
import time
from dataclasses import dataclass, field
from typing import Dict, Optional, Any
from urllib.parse import urlparse


@dataclass
class RateLimitConfig:
    """Configuration for token bucket rate limiter."""
    requests_per_second: float = 1.0
    burst_size: int = 5

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "requests_per_second": self.requests_per_second,
            "burst_size": self.burst_size
        }


class TokenBucket:
    """
    Token bucket implementation for rate limiting.

    Features:
    - Configurable rate limit (tokens per second)
    - Burst capability with configurable burst size
    - Blocking mechanism for handling 429 responses
    - Thread-safe with asyncio locks
    """

    def __init__(self, config: RateLimitConfig):
        """
        Initialize token bucket.

        Args:
            config: Rate limit configuration
        """
        self.config = config
        self.tokens = float(config.burst_size)
        self.last_refill = time.time()
        self.blocked_until = 0
        self._lock = asyncio.Lock()

    async def acquire(self, tokens_needed: float = 1.0) -> float:
        """
        Wait until tokens are available and consume them.

        Args:
            tokens_needed: Number of tokens to consume (default: 1.0)

        Returns:
            float: Actual wait time in seconds
        """
        async with self._lock:
            start_time = time.time()
            now = start_time

            # Check if we're blocked (e.g., due to 429 response)
            if now < self.blocked_until:
                wait_time = self.blocked_until - now
                await asyncio.sleep(wait_time)
                now = time.time()

            # Refill tokens based on time elapsed
            time_elapsed = now - self.last_refill
            tokens_to_add = time_elapsed * self.config.requests_per_second
            self.tokens = min(self.tokens + tokens_to_add, self.config.burst_size)
            self.last_refill = now

            # Wait if not enough tokens
            while self.tokens < tokens_needed:
                tokens_deficit = tokens_needed - self.tokens
                wait_time = tokens_deficit / self.config.requests_per_second
                await asyncio.sleep(wait_time)

                # Refill again after waiting
                now = time.time()
                time_elapsed = now - self.last_refill
                tokens_to_add = time_elapsed * self.config.requests_per_second
                self.tokens = min(self.tokens + tokens_to_add, self.config.burst_size)
                self.last_refill = now

            # Consume tokens
            self.tokens -= tokens_needed

            return time.time() - start_time

    def block_until(self, timestamp: float):
        """
        Block requests until a specific time.
        Useful for handling 429 (Too Many Requests) responses.

        Args:
            timestamp: Unix timestamp to block until
        """
        self.blocked_until = timestamp
        # Reset tokens to prevent burst after unblock
        self.tokens = 0

    @property
    def available_tokens(self) -> float:
        """Get current number of available tokens."""
        return self.tokens

    @property
    def is_blocked(self) -> bool:
        """Check if bucket is currently blocked."""
        return time.time() < self.blocked_until

    def reset(self):
        """Reset the bucket to full capacity."""
        self.tokens = float(self.config.burst_size)
        self.last_refill = time.time()
        self.blocked_until = 0

    def get_stats(self) -> Dict[str, Any]:
        """Get bucket statistics."""
        return {
            "available_tokens": self.tokens,
            "blocked_until": self.blocked_until,
            "is_blocked": self.is_blocked,
            "config": self.config.to_dict()
        }


class RateLimiter:
    """
    Manages rate limiting across multiple domains.
    Each domain gets its own token bucket with configurable limits.
    """

    def __init__(self, default_config: Optional[RateLimitConfig] = None):
        """
        Initialize rate limiter.

        Args:
            default_config: Default configuration for domains without specific limits
        """
        self.default_config = default_config or RateLimitConfig()
        self.domain_limiters: Dict[str, TokenBucket] = {}
        self.domain_configs: Dict[str, RateLimitConfig] = {}
        self._lock = asyncio.Lock()

    def set_domain_limit(self, domain: str, config: RateLimitConfig):
        """
        Set rate limit configuration for a specific domain.

        Args:
            domain: Domain name (e.g., 'api.weather.gov')
            config: Rate limit configuration for this domain
        """
        self.domain_configs[domain] = config
        # If limiter exists, update its config
        if domain in self.domain_limiters:
            self.domain_limiters[domain].config = config

    def set_domain_limits(self, limits: Dict[str, RateLimitConfig]):
        """
        Set rate limit configurations for multiple domains.

        Args:
            limits: Dictionary mapping domains to configurations
        """
        for domain, config in limits.items():
            self.set_domain_limit(domain, config)

    async def get_limiter(self, domain: str) -> TokenBucket:
        """
        Get or create a token bucket for a domain.

        Args:
            domain: Domain name

        Returns:
            TokenBucket instance for the domain
        """
        async with self._lock:
            if domain not in self.domain_limiters:
                config = self.domain_configs.get(domain, self.default_config)
                self.domain_limiters[domain] = TokenBucket(config)
            return self.domain_limiters[domain]

    async def acquire(self, url_or_domain: str, tokens: float = 1.0) -> float:
        """
        Acquire tokens for a URL or domain, waiting if necessary.

        Args:
            url_or_domain: URL or domain name
            tokens: Number of tokens to acquire

        Returns:
            float: Wait time in seconds
        """
        # Extract domain from URL if needed
        if '://' in url_or_domain:
            domain = urlparse(url_or_domain).netloc
        else:
            domain = url_or_domain

        limiter = await self.get_limiter(domain)
        return await limiter.acquire(tokens)

    def block_domain(self, domain: str, until_timestamp: float):
        """
        Block a domain until a specific time.

        Args:
            domain: Domain name
            until_timestamp: Unix timestamp to block until
        """
        if domain in self.domain_limiters:
            self.domain_limiters[domain].block_until(until_timestamp)

    def get_stats(self) -> Dict[str, Dict]:
        """
        Get statistics for all domains.

        Returns:
            Dict mapping domain names to their stats
        """
        stats = {}
        for domain, limiter in self.domain_limiters.items():
            stats[domain] = limiter.get_stats()
        return stats

    def reset_domain(self, domain: str):
        """Reset a specific domain's rate limiter."""
        if domain in self.domain_limiters:
            self.domain_limiters[domain].reset()

    def reset_all(self):
        """Reset all domain rate limiters."""
        for limiter in self.domain_limiters.values():
            limiter.reset()
