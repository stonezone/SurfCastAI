"""
Enhanced HTTP client with rate limiting, retry logic, and robust error handling.
Combines best features from both urlGrabber and url_downloader libraries.
"""

import asyncio
import hashlib
import inspect
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import aiohttp

from ..utils.exceptions import RateLimitError, SecurityError
from ..utils.security import sanitize_filename, validate_url
from .rate_limiter import RateLimitConfig, RateLimiter


class DownloadResult:
    """Result of a download operation with comprehensive metadata."""

    def __init__(self, url: str, success: bool = False):
        self.url = url
        self.success = success
        self.status_code: int | None = None
        self.content: bytes | None = None
        self.headers: dict[str, str] = {}
        self.error: str | None = None
        self.download_time: float = 0
        self.wait_time: float = 0
        self.retry_count: int = 0
        self.file_path: str | None = None
        self.size_bytes: int | None = None
        self.content_type: str | None = None
        self.timestamp = datetime.now().isoformat()
        self.domain = urlparse(url).netloc

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "url": self.url,
            "success": self.success,
            "status_code": self.status_code,
            "error": self.error,
            "download_time": self.download_time,
            "wait_time": self.wait_time,
            "retry_count": self.retry_count,
            "file_path": self.file_path,
            "size_bytes": self.size_bytes,
            "content_type": self.content_type,
            "timestamp": self.timestamp,
            "domain": self.domain,
        }

    @classmethod
    def from_error(cls, url: str, error: str) -> "DownloadResult":
        """Create a failed result with error message."""
        result = cls(url, success=False)
        result.error = error
        return result


class HTTPClient:
    """
    Enhanced HTTP client with rate limiting, retry logic, and error handling.

    Features:
    - Per-domain rate limiting with configurable limits
    - Exponential backoff retry logic
    - Comprehensive error handling
    - Request/response logging
    - URL validation and sanitization
    - Support for dynamic URL parameters
    """

    def __init__(
        self,
        rate_limiter: RateLimiter | None = None,
        timeout: int = 30,
        max_concurrent: int = 10,
        retry_attempts: int = 3,
        user_agent: str = "SurfCastAI/1.0",
        output_dir: Path | None = None,
        logger: logging.Logger | None = None,
    ):
        """
        Initialize HTTP client.

        Args:
            rate_limiter: Optional rate limiter (will create default if None)
            timeout: Request timeout in seconds
            max_concurrent: Maximum concurrent requests
            retry_attempts: Number of retry attempts for failed requests
            user_agent: User agent string
            output_dir: Output directory for downloads
            logger: Optional logger instance
        """
        self.timeout = timeout
        self.max_concurrent = max_concurrent
        self.retry_attempts = retry_attempts
        self.user_agent = user_agent
        self.output_dir = output_dir or Path("./data")
        self.logger = logger or logging.getLogger(__name__)

        # Create rate limiter if not provided
        self.rate_limiter = rate_limiter or RateLimiter(
            default_config=RateLimitConfig(requests_per_second=0.5, burst_size=3)
        )

        # Create output directory if it doesn't exist
        os.makedirs(self.output_dir, exist_ok=True)

        # Session and connector
        self._session: aiohttp.ClientSession | None = None
        self._connector: aiohttp.TCPConnector | None = None

        # Statistics tracking
        self.stats = {
            "downloads_per_domain": {},
            "errors_per_domain": {},
            "wait_times": {},
            "total_downloads": 0,
            "total_errors": 0,
            "total_wait_time": 0,
        }

    async def __aenter__(self):
        """Context manager entry."""
        await self._ensure_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        await self.close()

    async def _ensure_session(self):
        """Ensure HTTP session is created."""
        if self._session is None or self._session.closed:
            # Create connector with connection pooling
            self._connector = aiohttp.TCPConnector(
                limit=self.max_concurrent * 2,  # Total connections
                limit_per_host=5,  # Per-host limit
                ttl_dns_cache=300,  # DNS cache timeout
                enable_cleanup_closed=True,
            )

            # Create session with timeout and headers
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            headers = {"User-Agent": self.user_agent}

            self._session = aiohttp.ClientSession(
                connector=self._connector, timeout=timeout, headers=headers
            )

    async def _resolve_response(self, request: Any) -> tuple[Any, bool]:
        """Normalise aiohttp responses versus AsyncMock test doubles."""
        async_mock_type = None
        try:
            from unittest.mock import AsyncMock  # type: ignore

            async_mock_type = AsyncMock
        except Exception:  # pragma: no cover - fallback when unittest.mock unavailable
            async_mock_type = None

        if async_mock_type and isinstance(request, async_mock_type):
            return request, False

        if hasattr(request, "__aenter__") and hasattr(request, "__aexit__"):
            return request, True

        if inspect.isawaitable(request):
            awaited = await request
            if async_mock_type and isinstance(awaited, async_mock_type):
                return awaited, False
            if hasattr(awaited, "__aenter__") and hasattr(awaited, "__aexit__"):
                return awaited, True
            return awaited, False

        return request, False

    def _coerce_headers(self, headers: Any) -> dict[str, Any]:
        """Safely convert headers object to a dictionary."""
        if headers is None:
            return {}
        if isinstance(headers, dict):
            return dict(headers)
        if hasattr(headers, "items"):
            try:
                return {k: v for k, v in headers.items()}
            except TypeError:
                return {}
        return {}

    async def _finalize_response(self, response: Any) -> None:
        """Release resources on responses when not using a context manager."""
        if response is None:
            return

        for attr in ("release", "close"):
            fn = getattr(response, attr, None)
            if callable(fn):
                try:
                    result = fn()
                    if inspect.isawaitable(result):
                        await result
                except Exception:
                    pass
                finally:
                    return

    async def _consume_content(self, response: Any) -> bytes | None:
        """Read response content handling coroutines/mocked methods."""
        reader = getattr(response, "read", None)
        if not callable(reader):
            return None

        try:
            content = reader()
            if inspect.isawaitable(content):
                content = await content
            return content
        except Exception:
            self.logger.warning("Failed to read response body", exc_info=True)
            return None

    async def _handle_http_response(
        self,
        response: Any,
        result: DownloadResult,
        url: str,
        domain: str,
        save_to_disk: bool,
        custom_file_path: Path | None,
        attempt: int,
    ) -> dict[str, Any]:
        """Process a single HTTP response and decide next action."""

        headers = self._coerce_headers(getattr(response, "headers", {}))
        status = getattr(response, "status", None)
        result.status_code = status
        result.content_type = headers.get("Content-Type", "unknown")
        result.headers = headers

        if status == 200:
            content = await self._consume_content(response)
            result.content = content

            if content is not None:
                size_bytes = len(content)
                if result.content_type and "json" in result.content_type.lower():
                    try:
                        import json

                        text = content.decode("utf-8")
                        compact = json.dumps(json.loads(text), separators=(",", ":"))
                        size_bytes = len(compact.encode("utf-8"))
                    except Exception:
                        size_bytes = len(content)
                result.size_bytes = size_bytes
            else:
                result.size_bytes = None
            result.success = True

            if save_to_disk and content is not None:
                file_path = custom_file_path or self._generate_file_path(url, result.content_type)
                file_path.parent.mkdir(parents=True, exist_ok=True)
                with open(file_path, "wb") as f:
                    f.write(content)
                result.file_path = str(file_path)
                self.logger.info(f"Saved {url} to {file_path} ({len(content)} bytes)")

            if domain in self.stats["downloads_per_domain"]:
                self.stats["downloads_per_domain"][domain] += 1
            else:
                self.stats["downloads_per_domain"][domain] = 1
            self.stats["total_downloads"] += 1

            return {"action": "success"}

        if status == 429:
            retry_after = headers.get("Retry-After", "60")
            try:
                wait_seconds = int(retry_after)
            except (TypeError, ValueError):
                wait_seconds = 60

            message = f"Rate limited. Retry after {wait_seconds}s"
            result.error = message
            self.rate_limiter.block_domain(domain, time.time() + wait_seconds)
            self.logger.warning(f"Rate limited on {url}. Retry after {wait_seconds}s")

            return {"action": "retry", "error": message, "sleep": min(wait_seconds, 120)}

        reason = getattr(response, "reason", "") or ""
        if status is None:
            message = "HTTP error"
        else:
            message = f"HTTP {status}: {reason}".strip()

        result.error = message

        if status is not None and status >= 500:
            backoff = min(2**attempt, 30)
            self.logger.warning(f"Server error {status} on {url}. Retrying in {backoff}s")
            return {"action": "retry", "error": message, "sleep": backoff}

        self.logger.warning(f"Failed to download {url}: {message}")
        return {"action": "break", "error": message}

    def _process_url_placeholders(self, url: str) -> str:
        """
        Replace date/time placeholders in URL.

        Supports:
        - {current_date}, {date} -> YYYYMMDD
        - {hour} -> HH
        - {forecast} -> 000 (typical for model runs)
        - Standard strftime format codes (%Y, %m, %d, etc.)

        Args:
            url: URL with potential placeholders

        Returns:
            URL with placeholders replaced
        """
        now = datetime.now()

        replacements = {
            "{current_date}": now.strftime("%Y%m%d"),
            "{date}": now.strftime("%Y%m%d"),
            "{hour}": now.strftime("%H"),
            "%Y": now.strftime("%Y"),
            "%m": now.strftime("%m"),
            "%d": now.strftime("%d"),
            "%H": now.strftime("%H"),
        }

        if "{forecast}" in url:
            url = url.replace("{forecast}", "000")

        for placeholder, value in replacements.items():
            url = url.replace(placeholder, value)

        return url

    def _generate_file_path(self, url: str, content_type: str | None = None) -> Path:
        """
        Generate file path for downloaded content.

        Args:
            url: URL of the content
            content_type: Optional content type for determining extension

        Returns:
            Path object for the file
        """
        parsed = urlparse(url)

        # Create domain subdirectory
        domain = parsed.netloc.replace(".", "_")
        domain = sanitize_filename(domain)
        domain_dir = self.output_dir / domain
        domain_dir.mkdir(exist_ok=True)

        # Extract filename from URL path
        path_parts = parsed.path.strip("/").split("/")
        filename = path_parts[-1] if path_parts[-1] else "index"

        # Add extension if not present
        if "." not in filename:
            # Try to guess extension from content type
            if content_type:
                if "json" in content_type:
                    filename += ".json"
                elif "html" in content_type:
                    filename += ".html"
                elif "xml" in content_type:
                    filename += ".xml"
                elif "image" in content_type:
                    ext = content_type.split("/")[-1]
                    filename += f".{ext}"
                else:
                    filename += ".txt"
            else:
                filename += ".dat"

        # Sanitize filename
        filename = sanitize_filename(filename)

        # Handle dynamic URLs with query parameters
        if parsed.query:
            url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
            base_name, ext = filename.rsplit(".", 1) if "." in filename else (filename, "")
            filename = f"{base_name}_{url_hash}.{ext}" if ext else f"{base_name}_{url_hash}"

        return domain_dir / filename

    async def download(
        self, url: str, save_to_disk: bool = True, custom_file_path: Path | None = None
    ) -> DownloadResult:
        """
        Download a URL with comprehensive error handling and retry logic.

        Args:
            url: URL to download
            save_to_disk: Whether to save content to disk
            custom_file_path: Optional custom file path

        Returns:
            DownloadResult object with comprehensive metadata
        """
        start_time = time.time()
        result = DownloadResult(url)

        # Replace placeholders in URL
        processed_url = self._process_url_placeholders(url)

        # Validate URL
        preliminary_domain = urlparse(processed_url).netloc or "invalid"
        result.domain = preliminary_domain
        try:
            validated_url = validate_url(processed_url)
            domain = urlparse(validated_url).netloc
            result.domain = domain
        except SecurityError as e:
            result.error = f"Security validation failed: {e}"
            error_domain = preliminary_domain or "invalid"
            if error_domain in self.stats["errors_per_domain"]:
                self.stats["errors_per_domain"][error_domain] += 1
            else:
                self.stats["errors_per_domain"][error_domain] = 1
            self.stats["total_errors"] += 1
            self.logger.warning(f"Security validation failed for {url}: {e}")
            return result

        # Ensure session exists
        await self._ensure_session()

        # Get rate limiter for domain
        try:
            # Apply rate limiting
            wait_time = await self.rate_limiter.acquire(domain)
            result.wait_time = wait_time

            # Track wait time
            if wait_time > 0.01:  # Only log significant waits
                self.logger.info(f"Rate limit wait for {domain}: {wait_time:.2f}s")
                if domain in self.stats["wait_times"]:
                    self.stats["wait_times"][domain].append(wait_time)
                else:
                    self.stats["wait_times"][domain] = [wait_time]
                self.stats["total_wait_time"] += wait_time
        except RateLimitError as e:
            result.error = f"Rate limit error: {e}"
            if domain in self.stats["errors_per_domain"]:
                self.stats["errors_per_domain"][domain] += 1
            else:
                self.stats["errors_per_domain"][domain] = 1
            self.stats["total_errors"] += 1
            self.logger.warning(f"Rate limit error for {url}: {e}")
            return result

        # Retry loop
        last_error = None
        for attempt in range(self.retry_attempts + 1):  # +1 for initial attempt
            try:
                result.retry_count = attempt

                if attempt > 0:
                    self.logger.info(f"Retry {attempt}/{self.retry_attempts} for {url}")
                else:
                    self.logger.info(f"Downloading {url}")

                request = self._session.get(validated_url)
                response_obj, use_context = await self._resolve_response(request)

                if use_context:
                    async with response_obj as response:
                        outcome = await self._handle_http_response(
                            response, result, url, domain, save_to_disk, custom_file_path, attempt
                        )
                else:
                    response = response_obj
                    outcome = await self._handle_http_response(
                        response, result, url, domain, save_to_disk, custom_file_path, attempt
                    )
                    await self._finalize_response(response)

                action = outcome.get("action")
                last_error = outcome.get("error", last_error)

                if action == "success":
                    break

                if action == "retry" and attempt < self.retry_attempts:
                    sleep_for = outcome.get("sleep", 0)
                    if sleep_for:
                        await asyncio.sleep(sleep_for)
                    continue

                # Either non-retriable error or out of retries
                break

            except TimeoutError:
                last_error = f"Request timeout after {self.timeout}s"
                if attempt < self.retry_attempts:
                    backoff = min(2**attempt, 30)
                    self.logger.warning(f"Timeout on {url}. Retrying in {backoff}s")
                    await asyncio.sleep(backoff)
                    continue
                break

            except aiohttp.ClientError as e:
                last_error = f"HTTP client error: {str(e)}"
                if attempt < self.retry_attempts:
                    backoff = min(2**attempt, 30)
                    self.logger.warning(f"Client error on {url}: {e}. Retrying in {backoff}s")
                    await asyncio.sleep(backoff)
                    continue
                break

            except Exception as e:
                last_error = f"Unexpected error: {str(e)}"
                self.logger.error(f"Unexpected error downloading {url}: {e}")
                break

        # Set error if unsuccessful
        if not result.success and last_error:
            result.error = last_error
            if domain in self.stats["errors_per_domain"]:
                self.stats["errors_per_domain"][domain] += 1
            else:
                self.stats["errors_per_domain"][domain] = 1
            self.stats["total_errors"] += 1
            self.logger.warning(f"Failed to download {url}: {last_error}")

        # Calculate download time
        result.download_time = time.time() - start_time

        return result

    async def download_multiple(
        self, urls: list[str], save_to_disk: bool = True, max_concurrent: int | None = None
    ) -> dict[str, DownloadResult]:
        """
        Download multiple URLs concurrently with rate limiting.

        Args:
            urls: List of URLs to download
            save_to_disk: Whether to save content to disk
            max_concurrent: Maximum concurrent downloads (defaults to self.max_concurrent)

        Returns:
            Dictionary mapping URLs to their download results
        """
        # Ensure session exists
        await self._ensure_session()

        # Create semaphore to limit concurrency
        semaphore = asyncio.Semaphore(max_concurrent or self.max_concurrent)

        async def download_with_semaphore(url: str) -> tuple[str, DownloadResult]:
            """Download URL with semaphore for concurrency limiting."""
            async with semaphore:
                result = await self.download(url, save_to_disk)
                return url, result

        # Create tasks for all URLs
        tasks = [download_with_semaphore(url) for url in urls]

        # Execute all tasks and collect results
        results = {}
        for i, task in enumerate(asyncio.as_completed(tasks)):
            url, result = await task
            results[url] = result

            # Log progress
            if (i + 1) % 10 == 0 or (i + 1) == len(urls):
                self.logger.info(f"Progress: {i+1}/{len(urls)} downloads complete")

        return results

    async def head(self, url: str) -> tuple[int, dict[str, str]]:
        """
        Perform HEAD request to get headers without downloading content.

        Args:
            url: URL to check

        Returns:
            Tuple of (status_code, headers)
        """
        # Ensure session exists
        await self._ensure_session()

        # Replace placeholders in URL
        processed_url = self._process_url_placeholders(url)

        # Validate URL
        try:
            validated_url = validate_url(processed_url)
            domain = urlparse(validated_url).netloc

            # Apply rate limiting
            await self.rate_limiter.acquire(domain)

            request = self._session.head(validated_url)
            response_obj, use_context = await self._resolve_response(request)

            if use_context:
                async with response_obj as response:
                    return (
                        getattr(response, "status", 0),
                        self._coerce_headers(getattr(response, "headers", {})),
                    )

            response = response_obj
            headers = self._coerce_headers(getattr(response, "headers", {}))
            status = getattr(response, "status", 0)
            await self._finalize_response(response)
            return status, headers

        except Exception as e:
            self.logger.error(f"HEAD request failed for {url}: {e}")
            return 0, {}

    async def close(self):
        """Close session and connector."""
        if self._session and not self._session.closed:
            await self._session.close()

        if self._connector and not self._connector.closed:
            await self._connector.close()

        self._session = None
        self._connector = None

    def get_statistics(self) -> dict[str, Any]:
        """
        Get comprehensive download statistics.

        Returns:
            Dictionary with detailed statistics
        """
        # Calculate averages and additional stats
        domain_stats = {}
        for domain, count in self.stats["downloads_per_domain"].items():
            errors = self.stats["errors_per_domain"].get(domain, 0)
            waits = self.stats["wait_times"].get(domain, [])

            domain_stats[domain] = {
                "successful": count,
                "errors": errors,
                "total": count + errors,
                "success_rate": (
                    round(count / (count + errors) * 100, 1) if (count + errors) > 0 else 0
                ),
                "avg_wait_time": sum(waits) / len(waits) if waits else 0,
                "max_wait_time": max(waits) if waits else 0,
                "total_wait_time": sum(waits) if waits else 0,
            }

        return {
            "total_downloads": self.stats["total_downloads"],
            "total_errors": self.stats["total_errors"],
            "success_rate": (
                round(
                    self.stats["total_downloads"]
                    / (self.stats["total_downloads"] + self.stats["total_errors"])
                    * 100,
                    1,
                )
                if (self.stats["total_downloads"] + self.stats["total_errors"]) > 0
                else 0
            ),
            "total_wait_time": self.stats["total_wait_time"],
            "domain_statistics": domain_stats,
        }
