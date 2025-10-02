"""
Unit tests for the RateLimiter and TokenBucket classes.
"""

import unittest
import asyncio
import time
import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../')))

from src.core.rate_limiter import RateLimiter, TokenBucket, RateLimitConfig


class TestRateLimitConfig(unittest.TestCase):
    """Tests for the RateLimitConfig dataclass."""

    def test_init(self):
        """Test RateLimitConfig initialization."""
        config = RateLimitConfig(requests_per_second=2.0, burst_size=10)
        self.assertEqual(config.requests_per_second, 2.0)
        self.assertEqual(config.burst_size, 10)

    def test_default_values(self):
        """Test RateLimitConfig default values."""
        config = RateLimitConfig()
        self.assertEqual(config.requests_per_second, 1.0)
        self.assertEqual(config.burst_size, 5)

    def test_to_dict(self):
        """Test converting RateLimitConfig to dictionary."""
        config = RateLimitConfig(requests_per_second=3.0, burst_size=7)
        config_dict = config.to_dict()

        self.assertEqual(config_dict['requests_per_second'], 3.0)
        self.assertEqual(config_dict['burst_size'], 7)


class TestTokenBucket(unittest.IsolatedAsyncioTestCase):
    """Tests for the TokenBucket class."""

    async def test_init(self):
        """Test TokenBucket initialization."""
        config = RateLimitConfig(requests_per_second=2.0, burst_size=5)
        bucket = TokenBucket(config)

        self.assertEqual(bucket.config, config)
        self.assertEqual(bucket.tokens, 5.0)
        self.assertFalse(bucket.is_blocked)

    async def test_acquire_single_token(self):
        """Test acquiring a single token."""
        config = RateLimitConfig(requests_per_second=10.0, burst_size=10)
        bucket = TokenBucket(config)

        # Should be immediate with full bucket
        wait_time = await bucket.acquire(1.0)

        self.assertLess(wait_time, 0.01)  # Nearly instant
        self.assertAlmostEqual(bucket.tokens, 9.0, places=1)

    async def test_acquire_multiple_tokens(self):
        """Test acquiring multiple tokens."""
        config = RateLimitConfig(requests_per_second=10.0, burst_size=10)
        bucket = TokenBucket(config)

        # Acquire 3 tokens
        wait_time = await bucket.acquire(3.0)

        self.assertLess(wait_time, 0.01)
        self.assertAlmostEqual(bucket.tokens, 7.0, places=1)

    async def test_acquire_waits_when_insufficient_tokens(self):
        """Test that acquire waits when tokens are insufficient."""
        config = RateLimitConfig(requests_per_second=5.0, burst_size=2)
        bucket = TokenBucket(config)

        # Drain tokens
        await bucket.acquire(2.0)
        self.assertAlmostEqual(bucket.tokens, 0.0, places=1)

        # Next request should wait
        start = time.time()
        wait_time = await bucket.acquire(1.0)
        elapsed = time.time() - start

        # Should wait approximately 1/5 = 0.2 seconds
        self.assertGreater(wait_time, 0.15)
        self.assertLess(wait_time, 0.3)
        self.assertGreater(elapsed, 0.15)

    async def test_token_refill(self):
        """Test token bucket refills over time."""
        config = RateLimitConfig(requests_per_second=10.0, burst_size=10)
        bucket = TokenBucket(config)

        # Drain tokens
        await bucket.acquire(10.0)
        self.assertAlmostEqual(bucket.tokens, 0.0, places=1)

        # Wait for refill
        await asyncio.sleep(0.5)  # 0.5s * 10 tokens/s = 5 tokens

        # Manually trigger refill by acquiring
        start_tokens = bucket.tokens
        await bucket.acquire(0.0)  # Acquire 0 tokens to trigger refill

        # Should have approximately 5 tokens
        self.assertGreater(bucket.tokens, 4.0)
        self.assertLess(bucket.tokens, 6.0)

    async def test_burst_capacity(self):
        """Test that bucket respects burst capacity."""
        config = RateLimitConfig(requests_per_second=1.0, burst_size=5)
        bucket = TokenBucket(config)

        # Wait long enough for many tokens to accumulate
        await asyncio.sleep(2.0)  # Would be 2 tokens without cap

        # Trigger refill
        await bucket.acquire(0.0)

        # Should be capped at burst_size
        self.assertLessEqual(bucket.tokens, 5.0)

    async def test_block_until(self):
        """Test blocking mechanism for 429 responses."""
        config = RateLimitConfig(requests_per_second=10.0, burst_size=10)
        bucket = TokenBucket(config)

        # Block for 0.3 seconds
        block_until = time.time() + 0.3
        bucket.block_until(block_until)

        self.assertTrue(bucket.is_blocked)
        self.assertEqual(bucket.tokens, 0)  # Tokens reset on block

        # Try to acquire - should wait
        start = time.time()
        wait_time = await bucket.acquire(1.0)
        elapsed = time.time() - start

        self.assertGreater(elapsed, 0.25)
        self.assertFalse(bucket.is_blocked)

    async def test_available_tokens_property(self):
        """Test available_tokens property."""
        config = RateLimitConfig(requests_per_second=10.0, burst_size=10)
        bucket = TokenBucket(config)

        self.assertEqual(bucket.available_tokens, 10.0)

        await bucket.acquire(3.0)
        self.assertAlmostEqual(bucket.available_tokens, 7.0, places=1)

    async def test_reset(self):
        """Test bucket reset."""
        config = RateLimitConfig(requests_per_second=5.0, burst_size=5)
        bucket = TokenBucket(config)

        # Drain and block
        await bucket.acquire(5.0)
        bucket.block_until(time.time() + 100)

        self.assertEqual(bucket.tokens, 0)
        self.assertTrue(bucket.is_blocked)

        # Reset
        bucket.reset()

        self.assertEqual(bucket.tokens, 5.0)
        self.assertFalse(bucket.is_blocked)

    async def test_get_stats(self):
        """Test get_stats method."""
        config = RateLimitConfig(requests_per_second=2.0, burst_size=8)
        bucket = TokenBucket(config)

        stats = bucket.get_stats()

        self.assertEqual(stats['available_tokens'], 8.0)
        self.assertFalse(stats['is_blocked'])
        self.assertIn('config', stats)
        self.assertEqual(stats['config']['requests_per_second'], 2.0)


class TestRateLimiter(unittest.IsolatedAsyncioTestCase):
    """Tests for the RateLimiter class."""

    async def test_init(self):
        """Test RateLimiter initialization."""
        default_config = RateLimitConfig(requests_per_second=1.0, burst_size=3)
        limiter = RateLimiter(default_config=default_config)

        self.assertEqual(limiter.default_config, default_config)
        self.assertEqual(len(limiter.domain_limiters), 0)

    async def test_set_domain_limit(self):
        """Test setting domain-specific limit."""
        limiter = RateLimiter()
        config = RateLimitConfig(requests_per_second=2.0, burst_size=10)

        limiter.set_domain_limit('example.com', config)

        self.assertIn('example.com', limiter.domain_configs)
        self.assertEqual(limiter.domain_configs['example.com'], config)

    async def test_set_domain_limits(self):
        """Test setting multiple domain limits."""
        limiter = RateLimiter()
        limits = {
            'example.com': RateLimitConfig(requests_per_second=2.0, burst_size=5),
            'api.test.com': RateLimitConfig(requests_per_second=0.5, burst_size=2)
        }

        limiter.set_domain_limits(limits)

        self.assertEqual(len(limiter.domain_configs), 2)
        self.assertIn('example.com', limiter.domain_configs)
        self.assertIn('api.test.com', limiter.domain_configs)

    async def test_get_limiter_creates_bucket(self):
        """Test that get_limiter creates a new bucket for unknown domain."""
        limiter = RateLimiter()

        self.assertEqual(len(limiter.domain_limiters), 0)

        bucket = await limiter.get_limiter('example.com')

        self.assertIsInstance(bucket, TokenBucket)
        self.assertIn('example.com', limiter.domain_limiters)

    async def test_get_limiter_uses_domain_config(self):
        """Test that get_limiter uses domain-specific config."""
        limiter = RateLimiter()
        domain_config = RateLimitConfig(requests_per_second=5.0, burst_size=15)

        limiter.set_domain_limit('example.com', domain_config)

        bucket = await limiter.get_limiter('example.com')

        self.assertEqual(bucket.config, domain_config)
        self.assertEqual(bucket.tokens, 15.0)

    async def test_get_limiter_returns_existing_bucket(self):
        """Test that get_limiter returns existing bucket for known domain."""
        limiter = RateLimiter()

        bucket1 = await limiter.get_limiter('example.com')
        bucket2 = await limiter.get_limiter('example.com')

        self.assertIs(bucket1, bucket2)

    async def test_acquire_with_url(self):
        """Test acquiring tokens with full URL."""
        limiter = RateLimiter(default_config=RateLimitConfig(requests_per_second=10.0, burst_size=10))

        wait_time = await limiter.acquire('http://example.com/path/to/resource')

        self.assertLess(wait_time, 0.01)
        self.assertIn('example.com', limiter.domain_limiters)

    async def test_acquire_with_domain(self):
        """Test acquiring tokens with domain only."""
        limiter = RateLimiter(default_config=RateLimitConfig(requests_per_second=10.0, burst_size=10))

        wait_time = await limiter.acquire('example.com')

        self.assertLess(wait_time, 0.01)
        self.assertIn('example.com', limiter.domain_limiters)

    async def test_acquire_respects_domain_limits(self):
        """Test that acquire respects different domain limits."""
        limiter = RateLimiter()
        limiter.set_domain_limits({
            'fast.example.com': RateLimitConfig(requests_per_second=10.0, burst_size=10),
            'slow.example.com': RateLimitConfig(requests_per_second=1.0, burst_size=2)
        })

        # Fast domain - should be quick
        wait1 = await limiter.acquire('http://fast.example.com/data')
        self.assertLess(wait1, 0.01)

        # Slow domain - drain tokens
        await limiter.acquire('http://slow.example.com/data', tokens=2.0)

        # Next request to slow domain should wait
        start = time.time()
        wait2 = await limiter.acquire('http://slow.example.com/data')
        elapsed = time.time() - start

        self.assertGreater(elapsed, 0.8)  # Should wait ~1 second

    async def test_block_domain(self):
        """Test blocking a specific domain."""
        limiter = RateLimiter(default_config=RateLimitConfig(requests_per_second=10.0, burst_size=10))

        # Create bucket by acquiring
        await limiter.acquire('example.com')

        # Block domain
        block_until = time.time() + 0.3
        limiter.block_domain('example.com', block_until)

        # Try to acquire - should wait
        start = time.time()
        await limiter.acquire('example.com')
        elapsed = time.time() - start

        self.assertGreater(elapsed, 0.25)

    async def test_get_stats(self):
        """Test getting statistics for all domains."""
        limiter = RateLimiter()

        # Create buckets for multiple domains
        await limiter.acquire('example.com')
        await limiter.acquire('test.com')

        stats = limiter.get_stats()

        self.assertEqual(len(stats), 2)
        self.assertIn('example.com', stats)
        self.assertIn('test.com', stats)
        self.assertIn('available_tokens', stats['example.com'])

    async def test_reset_domain(self):
        """Test resetting a specific domain."""
        limiter = RateLimiter(default_config=RateLimitConfig(requests_per_second=10.0, burst_size=10))

        # Drain tokens
        await limiter.acquire('example.com', tokens=10.0)

        bucket = await limiter.get_limiter('example.com')
        self.assertAlmostEqual(bucket.tokens, 0.0, places=1)

        # Reset
        limiter.reset_domain('example.com')

        self.assertEqual(bucket.tokens, 10.0)

    async def test_reset_all(self):
        """Test resetting all domains."""
        limiter = RateLimiter(default_config=RateLimitConfig(requests_per_second=10.0, burst_size=10))

        # Create and drain multiple buckets
        await limiter.acquire('example.com', tokens=10.0)
        await limiter.acquire('test.com', tokens=10.0)

        # Reset all
        limiter.reset_all()

        bucket1 = await limiter.get_limiter('example.com')
        bucket2 = await limiter.get_limiter('test.com')

        self.assertEqual(bucket1.tokens, 10.0)
        self.assertEqual(bucket2.tokens, 10.0)

    async def test_concurrent_requests_to_same_domain(self):
        """Test that concurrent requests to same domain are properly rate limited."""
        limiter = RateLimiter()
        limiter.set_domain_limit('example.com', RateLimitConfig(requests_per_second=2.0, burst_size=2))

        # Start 5 concurrent requests
        start = time.time()
        tasks = [limiter.acquire('example.com') for _ in range(5)]
        await asyncio.gather(*tasks)
        elapsed = time.time() - start

        # With burst of 2 and rate of 2/s, 5 requests should take:
        # - 2 immediate (burst)
        # - 3 more at 0.5s intervals = 1.5s total
        # So should take between 1.0 and 2.0 seconds
        self.assertGreater(elapsed, 1.0)
        self.assertLess(elapsed, 2.5)

    async def test_concurrent_requests_to_different_domains(self):
        """Test that requests to different domains don't interfere."""
        limiter = RateLimiter(default_config=RateLimitConfig(requests_per_second=10.0, burst_size=10))

        # Start concurrent requests to different domains
        start = time.time()
        tasks = [
            limiter.acquire('domain1.com'),
            limiter.acquire('domain2.com'),
            limiter.acquire('domain3.com')
        ]
        await asyncio.gather(*tasks)
        elapsed = time.time() - start

        # All should complete quickly since they're different domains
        self.assertLess(elapsed, 0.1)


if __name__ == '__main__':
    unittest.main()
