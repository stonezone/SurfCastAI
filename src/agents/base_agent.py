"""
Base Agent abstract class for SurfCastAI.

Provides a standard interface for all data collection agents.
"""

import logging
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ..core.config import Config
from ..core.http_client import HTTPClient


class BaseAgent(ABC):
    """
    Abstract base class for all data collection agents.

    Features:
    - Standardized interface for data collection
    - Shared utilities for HTTP requests and file operations
    - Consistent metadata creation
    - Error handling and logging
    """

    def __init__(self, config: Config, http_client: HTTPClient | None = None):
        """
        Initialize the agent.

        Args:
            config: Application configuration
            http_client: Optional HTTP client (will create one if not provided)
        """
        self.config = config
        self.http_client = http_client
        self.agent_name = self.__class__.__name__
        self.logger = logging.getLogger(f"agent.{self.agent_name.lower()}")
        self._owns_client = False

    @abstractmethod
    async def collect(self, data_dir: Path) -> list[dict[str, Any]]:
        """
        Collect data from the agent's sources.

        Args:
            data_dir: Directory to store collected data

        Returns:
            List of metadata dictionaries describing collected data
        """
        pass

    def create_metadata(
        self,
        name: str,
        description: str,
        data_type: str = "unknown",
        source_url: str | None = None,
        file_path: str | None = None,
        error: str | None = None,
        **kwargs,
    ) -> dict[str, Any]:
        """
        Create standardized metadata for collected data.

        Args:
            name: Name of the data item
            description: Description of the data
            data_type: Type of data (json, text, html, image, etc.)
            source_url: URL the data was fetched from
            file_path: Local path where data was saved
            error: Error message if collection failed
            **kwargs: Additional metadata fields

        Returns:
            Standardized metadata dictionary
        """
        status = "failed" if error else "success"

        metadata = {
            "name": name,
            "description": description,
            "type": data_type,
            "source": self.agent_name,
            "status": status,
            "timestamp": datetime.now(UTC).isoformat(),
        }

        if source_url:
            metadata["source_url"] = source_url
        if file_path:
            metadata["file_path"] = file_path
        if error:
            metadata["error"] = error

        # Add any additional fields
        metadata.update(kwargs)

        return metadata

    def _get_timestamp(self) -> str:
        """Get current timestamp in ISO format."""
        return datetime.now(UTC).isoformat()

    async def ensure_http_client(self):
        """Ensure HTTP client is available."""
        if self.http_client is None:
            self.logger.info("Creating HTTP client")
            self.http_client = HTTPClient(
                timeout=self.config.getint("data_collection", "timeout", 30),
                max_concurrent=self.config.getint("data_collection", "max_concurrent", 10),
                retry_attempts=self.config.getint("data_collection", "retry_attempts", 3),
                user_agent=self.config.get("data_collection", "user_agent", "SurfCastAI/1.0"),
                output_dir=self.config.data_directory,
            )
            self._owns_client = True

    async def close(self):
        """
        Close the HTTP client if it was created by this agent.

        This method should be called when the agent is no longer needed
        to prevent resource leaks. Only closes the client if it was
        created by this agent (not provided externally).
        """
        if self._owns_client and self.http_client:
            self.logger.debug("Closing HTTP client")
            await self.http_client.close()
            self.http_client = None
            self._owns_client = False

    async def __aenter__(self):
        """
        Async context manager entry.

        Ensures HTTP client is initialized when entering the context.
        """
        await self.ensure_http_client()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """
        Async context manager exit.

        Ensures HTTP client is properly closed when exiting the context.
        """
        await self.close()
        return False

    async def download_file(
        self,
        url: str,
        filename: str | None = None,
        data_dir: Path | None = None,
        description: str = "",
    ) -> dict[str, Any]:
        """
        Download a file with error handling.

        Args:
            url: URL to download
            filename: Optional filename (derived from URL if not provided)
            data_dir: Directory to save the file
            description: Description of the file

        Returns:
            Metadata dictionary
        """
        await self.ensure_http_client()

        try:
            # Generate filename if not provided
            if not filename:
                filename = url.split("/")[-1]

            # Set up file path
            if data_dir:
                file_path = data_dir / filename
            else:
                file_path = None  # Let HTTP client handle it

            # Download the file
            self.logger.info(f"Downloading {url} to {file_path}")
            result = await self.http_client.download(
                url, save_to_disk=True, custom_file_path=file_path
            )

            if result.success:
                return self.create_metadata(
                    name=filename,
                    description=description or f"Downloaded from {url}",
                    data_type=self._get_data_type(result.content_type),
                    source_url=url,
                    file_path=result.file_path,
                    size_bytes=result.size_bytes,
                    content_type=result.content_type,
                    download_time=result.download_time,
                )
            else:
                return self.create_metadata(
                    name=filename,
                    description=description or f"Failed to download from {url}",
                    data_type=self._get_data_type(result.content_type),
                    source_url=url,
                    error=result.error,
                    status_code=result.status_code,
                )

        except Exception as e:
            self.logger.error(f"Error downloading {url}: {e}")
            return self.create_metadata(
                name=filename or "unknown",
                description=description or f"Failed to download from {url}",
                data_type="unknown",
                source_url=url,
                error=str(e),
            )

    def _get_data_type(self, content_type: str | None) -> str:
        """
        Determine data type from content type.

        Args:
            content_type: Content type string from HTTP headers

        Returns:
            Data type string
        """
        if not content_type:
            return "unknown"

        content_type = content_type.lower()

        if "json" in content_type:
            return "json"
        elif "html" in content_type:
            return "html"
        elif "xml" in content_type:
            return "xml"
        elif "text" in content_type:
            return "text"
        elif "image" in content_type:
            return "image"
        elif "application/pdf" in content_type:
            return "pdf"
        elif "application/octet-stream" in content_type:
            return "binary"
        else:
            return "unknown"
