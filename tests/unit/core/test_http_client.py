"""
Unit tests for the HTTPClient class.
"""

import unittest
from unittest.mock import MagicMock, patch, AsyncMock, Mock
import asyncio
import aiohttp
import os
import sys
from pathlib import Path
import time

# Add src directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../')))

from src.core.http_client import HTTPClient, DownloadResult
from src.core.rate_limiter import RateLimiter, RateLimitConfig
from src.utils.exceptions import SecurityError


class TestDownloadResult(unittest.TestCase):
    """Tests for the DownloadResult class."""

    def test_init(self):
        """Test DownloadResult initialization."""
        result = DownloadResult("http://example.com/test.json")
        self.assertEqual(result.url, "http://example.com/test.json")
        self.assertFalse(result.success)
        self.assertIsNone(result.status_code)
        self.assertIsNone(result.content)
        self.assertEqual(result.domain, "example.com")

    def test_to_dict(self):
        """Test converting DownloadResult to dictionary."""
        result = DownloadResult("http://example.com/test.json", success=True)
        result.status_code = 200
        result.size_bytes = 1024

        result_dict = result.to_dict()

        self.assertEqual(result_dict['url'], "http://example.com/test.json")
        self.assertTrue(result_dict['success'])
        self.assertEqual(result_dict['status_code'], 200)
        self.assertEqual(result_dict['size_bytes'], 1024)
        self.assertEqual(result_dict['domain'], "example.com")

    def test_from_error(self):
        """Test creating DownloadResult from error."""
        result = DownloadResult.from_error("http://example.com/test.json", "Connection timeout")

        self.assertFalse(result.success)
        self.assertEqual(result.error, "Connection timeout")
        self.assertEqual(result.url, "http://example.com/test.json")


class TestHTTPClient(unittest.IsolatedAsyncioTestCase):
    """Tests for the HTTPClient class."""

    def setUp(self):
        """Set up test fixtures."""
        self.rate_limiter = RateLimiter(
            default_config=RateLimitConfig(requests_per_second=10.0, burst_size=10)
        )
        self.temp_dir = Path("/tmp/test_http_client")
        self.temp_dir.mkdir(exist_ok=True)

    def tearDown(self):
        """Clean up test fixtures."""
        # Clean up temp directory
        if self.temp_dir.exists():
            for file in self.temp_dir.glob("**/*"):
                if file.is_file():
                    file.unlink()
            for dir in sorted(self.temp_dir.glob("**/*"), reverse=True):
                if dir.is_dir():
                    dir.rmdir()
            self.temp_dir.rmdir()

    async def test_init(self):
        """Test HTTPClient initialization."""
        client = HTTPClient(
            rate_limiter=self.rate_limiter,
            timeout=60,
            max_concurrent=5,
            output_dir=self.temp_dir
        )

        self.assertEqual(client.timeout, 60)
        self.assertEqual(client.max_concurrent, 5)
        self.assertEqual(client.output_dir, self.temp_dir)
        self.assertIsNotNone(client.rate_limiter)

        await client.close()

    async def test_context_manager(self):
        """Test HTTPClient as async context manager."""
        async with HTTPClient(rate_limiter=self.rate_limiter) as client:
            self.assertIsNotNone(client._session)

        # Session should be closed after context
        self.assertIsNone(client._session)

    async def test_ensure_session(self):
        """Test _ensure_session creates session."""
        client = HTTPClient(rate_limiter=self.rate_limiter)

        self.assertIsNone(client._session)

        await client._ensure_session()

        self.assertIsNotNone(client._session)
        self.assertIsInstance(client._session, aiohttp.ClientSession)

        await client.close()

    def test_process_url_placeholders(self):
        """Test URL placeholder replacement."""
        client = HTTPClient(rate_limiter=self.rate_limiter)

        # Test current_date placeholder
        url = "http://example.com/data/{current_date}/file.json"
        processed = client._process_url_placeholders(url)
        self.assertNotIn("{current_date}", processed)
        self.assertIn("example.com/data/", processed)

        # Test hour placeholder
        url = "http://example.com/data/{hour}/file.json"
        processed = client._process_url_placeholders(url)
        self.assertNotIn("{hour}", processed)

        # Test forecast placeholder
        url = "http://example.com/data/{forecast}/file.json"
        processed = client._process_url_placeholders(url)
        self.assertIn("000", processed)

    def test_generate_file_path(self):
        """Test file path generation."""
        client = HTTPClient(rate_limiter=self.rate_limiter, output_dir=self.temp_dir)

        # Simple URL
        url = "http://example.com/data/test.json"
        file_path = client._generate_file_path(url, "application/json")

        self.assertTrue(str(file_path).startswith(str(self.temp_dir)))
        self.assertTrue(str(file_path).endswith(".json"))
        self.assertIn("example_com", str(file_path))

        # URL with query parameters
        url = "http://example.com/data?id=123&format=json"
        file_path = client._generate_file_path(url, "application/json")

        self.assertTrue(str(file_path).endswith(".json"))
        # Should include hash for unique identification
        self.assertIn("_", file_path.name)

    async def test_download_success(self):
        """Test successful download."""
        client = HTTPClient(rate_limiter=self.rate_limiter, output_dir=self.temp_dir)

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.headers = {'Content-Type': 'application/json'}
        mock_response.read = AsyncMock(return_value=b'{"test": "data"}')

        async with client:
            with patch.object(client._session, 'get', return_value=mock_response):
                result = await client.download("http://example.com/test.json")

                self.assertTrue(result.success)
                self.assertEqual(result.status_code, 200)
                self.assertEqual(result.content, b'{"test": "data"}')
                self.assertEqual(result.size_bytes, 15)

    async def test_download_http_error(self):
        """Test download with HTTP error."""
        client = HTTPClient(rate_limiter=self.rate_limiter, output_dir=self.temp_dir)

        mock_response = AsyncMock()
        mock_response.status = 404
        mock_response.reason = "Not Found"
        mock_response.headers = {}

        async with client:
            with patch.object(client._session, 'get', return_value=mock_response):
                result = await client.download("http://example.com/missing.json")

                self.assertFalse(result.success)
                self.assertEqual(result.status_code, 404)
                self.assertIn("404", result.error)

    async def test_download_rate_limit(self):
        """Test download with rate limiting (429)."""
        client = HTTPClient(rate_limiter=self.rate_limiter, output_dir=self.temp_dir, retry_attempts=1)

        mock_response = AsyncMock()
        mock_response.status = 429
        mock_response.headers = {'Retry-After': '1'}

        async with client:
            with patch.object(client._session, 'get', return_value=mock_response):
                result = await client.download("http://example.com/test.json")

                self.assertFalse(result.success)
                self.assertIn("Rate limited", result.error)

    async def test_download_timeout(self):
        """Test download with timeout."""
        client = HTTPClient(rate_limiter=self.rate_limiter, output_dir=self.temp_dir, retry_attempts=1, timeout=1)

        async with client:
            with patch.object(client._session, 'get', side_effect=asyncio.TimeoutError):
                result = await client.download("http://example.com/test.json")

                self.assertFalse(result.success)
                self.assertIn("timeout", result.error.lower())

    async def test_download_client_error(self):
        """Test download with aiohttp client error."""
        client = HTTPClient(rate_limiter=self.rate_limiter, output_dir=self.temp_dir, retry_attempts=1)

        async with client:
            with patch.object(client._session, 'get', side_effect=aiohttp.ClientError("Connection failed")):
                result = await client.download("http://example.com/test.json")

                self.assertFalse(result.success)
                self.assertIn("client error", result.error.lower())

    async def test_download_invalid_url(self):
        """Test download with invalid URL."""
        client = HTTPClient(rate_limiter=self.rate_limiter, output_dir=self.temp_dir)

        # URL without scheme
        result = await client.download("not-a-valid-url")
        self.assertFalse(result.success)
        self.assertIn("Security validation failed", result.error)

        # Local network URL
        result = await client.download("http://localhost/test.json")
        self.assertFalse(result.success)
        self.assertIn("Security validation failed", result.error)

    async def test_download_with_retry(self):
        """Test download retry logic on server errors."""
        client = HTTPClient(rate_limiter=self.rate_limiter, output_dir=self.temp_dir, retry_attempts=2)

        # First call returns 500, second succeeds
        mock_error_response = AsyncMock()
        mock_error_response.status = 500
        mock_error_response.reason = "Internal Server Error"
        mock_error_response.headers = {}

        mock_success_response = AsyncMock()
        mock_success_response.status = 200
        mock_success_response.headers = {'Content-Type': 'text/plain'}
        mock_success_response.read = AsyncMock(return_value=b'success')

        async with client:
            with patch.object(client._session, 'get', side_effect=[mock_error_response, mock_success_response]):
                result = await client.download("http://example.com/test.txt")

                self.assertTrue(result.success)
                self.assertEqual(result.retry_count, 1)

    async def test_download_multiple(self):
        """Test downloading multiple URLs."""
        client = HTTPClient(rate_limiter=self.rate_limiter, output_dir=self.temp_dir)

        urls = [
            "http://example.com/file1.json",
            "http://example.com/file2.json",
            "http://example.com/file3.json"
        ]

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.headers = {'Content-Type': 'application/json'}
        mock_response.read = AsyncMock(return_value=b'{"data": "test"}')

        async with client:
            with patch.object(client._session, 'get', return_value=mock_response):
                results = await client.download_multiple(urls)

                self.assertEqual(len(results), 3)
                for url in urls:
                    self.assertIn(url, results)
                    self.assertTrue(results[url].success)

    async def test_head_request(self):
        """Test HEAD request."""
        client = HTTPClient(rate_limiter=self.rate_limiter)

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.headers = {'Content-Type': 'application/json', 'Content-Length': '1024'}

        async with client:
            with patch.object(client._session, 'head', return_value=mock_response):
                status, headers = await client.head("http://example.com/test.json")

                self.assertEqual(status, 200)
                self.assertEqual(headers['Content-Type'], 'application/json')
                self.assertEqual(headers['Content-Length'], '1024')

    def test_get_statistics(self):
        """Test getting download statistics."""
        client = HTTPClient(rate_limiter=self.rate_limiter)

        # Manually update stats
        client.stats['total_downloads'] = 10
        client.stats['total_errors'] = 2
        client.stats['downloads_per_domain']['example.com'] = 8
        client.stats['errors_per_domain']['example.com'] = 2

        stats = client.get_statistics()

        self.assertEqual(stats['total_downloads'], 10)
        self.assertEqual(stats['total_errors'], 2)
        self.assertIn('success_rate', stats)
        self.assertIn('domain_statistics', stats)
        self.assertIn('example.com', stats['domain_statistics'])

    async def test_save_to_disk_flag(self):
        """Test save_to_disk parameter."""
        client = HTTPClient(rate_limiter=self.rate_limiter, output_dir=self.temp_dir)

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.headers = {'Content-Type': 'text/plain'}
        mock_response.read = AsyncMock(return_value=b'test content')

        async with client:
            with patch.object(client._session, 'get', return_value=mock_response):
                # Don't save to disk
                result = await client.download("http://example.com/test.txt", save_to_disk=False)

                self.assertTrue(result.success)
                self.assertIsNone(result.file_path)
                self.assertEqual(result.content, b'test content')


if __name__ == '__main__':
    unittest.main()
