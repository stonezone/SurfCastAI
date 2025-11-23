"""
Unit tests for the BaseAgent abstract class.
"""

import unittest
from unittest.mock import MagicMock, patch, AsyncMock
import asyncio
import os
import sys
from pathlib import Path
from datetime import datetime, timezone

# Add src directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../')))

from src.agents.base_agent import BaseAgent
from src.core.config import Config
from src.core.http_client import HTTPClient, DownloadResult


class ConcreteAgent(BaseAgent):
    """Concrete implementation of BaseAgent for testing."""

    async def collect(self, data_dir: Path):
        """Simple collect implementation."""
        return [
            self.create_metadata(
                name="test_data",
                description="Test data collected",
                data_type="json",
                source_url="http://example.com/test.json"
            )
        ]


class TestBaseAgent(unittest.IsolatedAsyncioTestCase):
    """Tests for the BaseAgent class."""

    def setUp(self):
        """Set up test fixtures."""
        self.config = MagicMock(spec=Config)
        self.config.getint.return_value = 30  # timeout
        self.config.get.return_value = "SurfCastAI/1.0"
        self.config.data_directory = Path("/tmp/test_data")

        self.http_client = MagicMock(spec=HTTPClient)

    async def test_init_with_http_client(self):
        """Test initialization with provided HTTP client."""
        agent = ConcreteAgent(self.config, self.http_client)

        self.assertEqual(agent.config, self.config)
        self.assertEqual(agent.http_client, self.http_client)
        self.assertEqual(agent.agent_name, "ConcreteAgent")

    async def test_init_without_http_client(self):
        """Test initialization without HTTP client."""
        agent = ConcreteAgent(self.config)

        self.assertEqual(agent.config, self.config)
        self.assertIsNone(agent.http_client)
        self.assertEqual(agent.agent_name, "ConcreteAgent")

    async def test_logger_name(self):
        """Test that logger has correct name."""
        agent = ConcreteAgent(self.config)

        # Logger name should be lowercase agent name
        self.assertEqual(agent.logger.name, "agent.concreteagent")

    async def test_collect_abstract_method(self):
        """Test that collect is an abstract method."""
        # BaseAgent cannot be instantiated directly
        with self.assertRaises(TypeError):
            BaseAgent(self.config)

    async def test_concrete_collect_implementation(self):
        """Test concrete implementation of collect."""
        agent = ConcreteAgent(self.config)
        data_dir = Path("/tmp/test")

        results = await agent.collect(data_dir)

        self.assertIsInstance(results, list)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['name'], 'test_data')

    def test_create_metadata_basic(self):
        """Test creating basic metadata."""
        agent = ConcreteAgent(self.config)

        metadata = agent.create_metadata(
            name="test_file",
            description="Test file data",
            data_type="json"
        )

        self.assertEqual(metadata['name'], "test_file")
        self.assertEqual(metadata['description'], "Test file data")
        self.assertEqual(metadata['type'], "json")
        self.assertEqual(metadata['source'], "ConcreteAgent")
        self.assertEqual(metadata['status'], 'success')
        self.assertIn('timestamp', metadata)

    def test_create_metadata_with_source_url(self):
        """Test creating metadata with source URL."""
        agent = ConcreteAgent(self.config)

        metadata = agent.create_metadata(
            name="test_file",
            description="Test file",
            data_type="json",
            source_url="http://example.com/test.json"
        )

        self.assertEqual(metadata['source_url'], "http://example.com/test.json")

    def test_create_metadata_with_file_path(self):
        """Test creating metadata with file path."""
        agent = ConcreteAgent(self.config)

        metadata = agent.create_metadata(
            name="test_file",
            description="Test file",
            data_type="json",
            file_path="/tmp/data/test.json"
        )

        self.assertEqual(metadata['file_path'], "/tmp/data/test.json")

    def test_create_metadata_with_error(self):
        """Test creating metadata with error."""
        agent = ConcreteAgent(self.config)

        metadata = agent.create_metadata(
            name="test_file",
            description="Failed download",
            data_type="json",
            error="Connection timeout"
        )

        self.assertEqual(metadata['status'], 'failed')
        self.assertEqual(metadata['error'], "Connection timeout")

    def test_create_metadata_with_additional_fields(self):
        """Test creating metadata with additional custom fields."""
        agent = ConcreteAgent(self.config)

        metadata = agent.create_metadata(
            name="test_file",
            description="Test file",
            data_type="json",
            custom_field="custom_value",
            size_bytes=1024,
            content_type="application/json"
        )

        self.assertEqual(metadata['custom_field'], "custom_value")
        self.assertEqual(metadata['size_bytes'], 1024)
        self.assertEqual(metadata['content_type'], "application/json")

    def test_get_timestamp(self):
        """Test _get_timestamp returns ISO format."""
        agent = ConcreteAgent(self.config)

        timestamp = agent._get_timestamp()

        # Should be valid ISO format with timezone
        parsed = datetime.fromisoformat(timestamp)
        self.assertIsNotNone(parsed)
        # Should be in UTC
        self.assertEqual(parsed.tzinfo, timezone.utc)

    async def test_ensure_http_client_creates_client(self):
        """Test ensure_http_client creates HTTPClient if not exists."""
        agent = ConcreteAgent(self.config)

        self.assertIsNone(agent.http_client)

        with patch('src.agents.base_agent.HTTPClient') as mock_http_client_class:
            await agent.ensure_http_client()

            # Should have created an HTTPClient
            mock_http_client_class.assert_called_once()

    async def test_ensure_http_client_does_not_recreate(self):
        """Test ensure_http_client doesn't recreate existing client."""
        agent = ConcreteAgent(self.config, self.http_client)

        initial_client = agent.http_client

        await agent.ensure_http_client()

        # Should still be the same client
        self.assertIs(agent.http_client, initial_client)

    async def test_download_file_success(self):
        """Test successful file download."""
        agent = ConcreteAgent(self.config)
        agent.http_client = MagicMock(spec=HTTPClient)

        # Mock successful download
        mock_result = DownloadResult("http://example.com/test.json", success=True)
        mock_result.status_code = 200
        mock_result.file_path = "/tmp/data/test.json"
        mock_result.size_bytes = 1024
        mock_result.content_type = "application/json"
        mock_result.download_time = 0.5

        agent.http_client.download = AsyncMock(return_value=mock_result)

        data_dir = Path("/tmp/data")
        metadata = await agent.download_file(
            url="http://example.com/test.json",
            filename="test.json",
            data_dir=data_dir,
            description="Test JSON data"
        )

        self.assertEqual(metadata['name'], 'test.json')
        self.assertEqual(metadata['status'], 'success')
        self.assertEqual(metadata['source_url'], 'http://example.com/test.json')
        self.assertEqual(metadata['file_path'], '/tmp/data/test.json')
        self.assertEqual(metadata['size_bytes'], 1024)
        self.assertEqual(metadata['type'], 'json')

    async def test_download_file_failure(self):
        """Test failed file download."""
        agent = ConcreteAgent(self.config)
        agent.http_client = MagicMock(spec=HTTPClient)

        # Mock failed download
        mock_result = DownloadResult("http://example.com/test.json", success=False)
        mock_result.status_code = 404
        mock_result.error = "Not Found"

        agent.http_client.download = AsyncMock(return_value=mock_result)

        metadata = await agent.download_file(
            url="http://example.com/test.json",
            filename="test.json",
            description="Test JSON data"
        )

        self.assertEqual(metadata['status'], 'failed')
        self.assertEqual(metadata['error'], 'Not Found')
        self.assertEqual(metadata['status_code'], 404)

    async def test_download_file_exception(self):
        """Test download_file handles exceptions."""
        agent = ConcreteAgent(self.config)
        agent.http_client = MagicMock(spec=HTTPClient)

        # Mock exception during download
        agent.http_client.download = AsyncMock(side_effect=Exception("Network error"))

        metadata = await agent.download_file(
            url="http://example.com/test.json",
            filename="test.json",
            description="Test JSON data"
        )

        self.assertEqual(metadata['status'], 'failed')
        self.assertIn('Network error', metadata['error'])

    async def test_download_file_generates_filename(self):
        """Test download_file generates filename from URL if not provided."""
        agent = ConcreteAgent(self.config)
        agent.http_client = MagicMock(spec=HTTPClient)

        mock_result = DownloadResult("http://example.com/data/file.json", success=True)
        mock_result.file_path = "/tmp/data/file.json"
        mock_result.content_type = "application/json"

        agent.http_client.download = AsyncMock(return_value=mock_result)

        # Don't provide filename
        metadata = await agent.download_file(
            url="http://example.com/data/file.json",
            description="Test data"
        )

        # Should extract filename from URL
        self.assertEqual(metadata['name'], 'file.json')

    def test_get_data_type_json(self):
        """Test _get_data_type for JSON content."""
        agent = ConcreteAgent(self.config)

        data_type = agent._get_data_type("application/json")
        self.assertEqual(data_type, "json")

        data_type = agent._get_data_type("text/json")
        self.assertEqual(data_type, "json")

    def test_get_data_type_html(self):
        """Test _get_data_type for HTML content."""
        agent = ConcreteAgent(self.config)

        data_type = agent._get_data_type("text/html")
        self.assertEqual(data_type, "html")

    def test_get_data_type_xml(self):
        """Test _get_data_type for XML content."""
        agent = ConcreteAgent(self.config)

        data_type = agent._get_data_type("application/xml")
        self.assertEqual(data_type, "xml")

        data_type = agent._get_data_type("text/xml")
        self.assertEqual(data_type, "xml")

    def test_get_data_type_text(self):
        """Test _get_data_type for plain text content."""
        agent = ConcreteAgent(self.config)

        data_type = agent._get_data_type("text/plain")
        self.assertEqual(data_type, "text")

    def test_get_data_type_image(self):
        """Test _get_data_type for image content."""
        agent = ConcreteAgent(self.config)

        data_type = agent._get_data_type("image/png")
        self.assertEqual(data_type, "image")

        data_type = agent._get_data_type("image/jpeg")
        self.assertEqual(data_type, "image")

    def test_get_data_type_pdf(self):
        """Test _get_data_type for PDF content."""
        agent = ConcreteAgent(self.config)

        data_type = agent._get_data_type("application/pdf")
        self.assertEqual(data_type, "pdf")

    def test_get_data_type_binary(self):
        """Test _get_data_type for binary content."""
        agent = ConcreteAgent(self.config)

        data_type = agent._get_data_type("application/octet-stream")
        self.assertEqual(data_type, "binary")

    def test_get_data_type_unknown(self):
        """Test _get_data_type for unknown content type."""
        agent = ConcreteAgent(self.config)

        data_type = agent._get_data_type("application/x-custom")
        self.assertEqual(data_type, "unknown")

        data_type = agent._get_data_type(None)
        self.assertEqual(data_type, "unknown")

    def test_get_data_type_case_insensitive(self):
        """Test _get_data_type is case-insensitive."""
        agent = ConcreteAgent(self.config)

        data_type = agent._get_data_type("APPLICATION/JSON")
        self.assertEqual(data_type, "json")

        data_type = agent._get_data_type("TEXT/HTML")
        self.assertEqual(data_type, "html")

    async def test_owns_client_flag_on_creation(self):
        """Test that agent creates and owns HTTP client."""
        agent = ConcreteAgent(self.config)

        # Initially no client and doesn't own it
        self.assertIsNone(agent.http_client)
        self.assertFalse(agent._owns_client)

        # After ensuring client, it should be created and owned
        await agent.ensure_http_client()
        self.assertIsNotNone(agent.http_client)
        self.assertTrue(agent._owns_client)

        # Clean up
        await agent.close()

    async def test_owns_client_flag_with_external_client(self):
        """Test that agent doesn't own externally provided HTTP client."""
        mock_client = AsyncMock(spec=HTTPClient)
        agent = ConcreteAgent(self.config, http_client=mock_client)

        # Should have client but not own it
        self.assertIs(agent.http_client, mock_client)
        self.assertFalse(agent._owns_client)

        # Ensure should not change ownership
        await agent.ensure_http_client()
        self.assertIs(agent.http_client, mock_client)
        self.assertFalse(agent._owns_client)

        # Close should not close external client
        await agent.close()
        self.assertIs(agent.http_client, mock_client)
        mock_client.close.assert_not_called()

    async def test_close_owned_client(self):
        """Test that close() closes client when agent owns it."""
        agent = ConcreteAgent(self.config)

        # Create client
        await agent.ensure_http_client()
        self.assertTrue(agent._owns_client)

        # Mock the close method and keep reference
        mock_close = AsyncMock()
        agent.http_client.close = mock_close

        # Close should clean up
        await agent.close()
        self.assertIsNone(agent.http_client)
        self.assertFalse(agent._owns_client)
        mock_close.assert_awaited_once()

    async def test_close_external_client(self):
        """Test that close() doesn't close external client."""
        mock_client = AsyncMock(spec=HTTPClient)
        agent = ConcreteAgent(self.config, http_client=mock_client)

        # Close should not affect external client
        await agent.close()
        self.assertIs(agent.http_client, mock_client)
        self.assertFalse(agent._owns_client)
        mock_client.close.assert_not_called()

    async def test_close_when_no_client(self):
        """Test that close() is safe when no client exists."""
        agent = ConcreteAgent(self.config)

        # Should not raise exception
        await agent.close()
        self.assertIsNone(agent.http_client)
        self.assertFalse(agent._owns_client)

    async def test_context_manager_creates_and_closes_client(self):
        """Test async context manager properly manages client lifecycle."""
        agent = ConcreteAgent(self.config)

        # Before context, no client
        self.assertIsNone(agent.http_client)
        self.assertFalse(agent._owns_client)

        async with agent as ctx_agent:
            # Inside context, client should exist
            self.assertIs(ctx_agent, agent)
            self.assertIsNotNone(agent.http_client)
            self.assertTrue(agent._owns_client)

            # Mock close for verification
            agent.http_client.close = AsyncMock()

        # After context, client should be closed
        self.assertIsNone(agent.http_client)
        self.assertFalse(agent._owns_client)

    async def test_context_manager_with_external_client(self):
        """Test context manager with externally provided client."""
        mock_client = AsyncMock(spec=HTTPClient)
        agent = ConcreteAgent(self.config, http_client=mock_client)

        async with agent as ctx_agent:
            # Should use external client
            self.assertIs(ctx_agent, agent)
            self.assertIs(agent.http_client, mock_client)
            self.assertFalse(agent._owns_client)

        # External client should not be closed
        self.assertIs(agent.http_client, mock_client)
        mock_client.close.assert_not_called()

    async def test_context_manager_exception_handling(self):
        """Test that context manager closes client even on exception."""
        agent = ConcreteAgent(self.config)

        try:
            async with agent:
                self.assertIsNotNone(agent.http_client)
                agent.http_client.close = AsyncMock()
                # Simulate exception
                raise ValueError("Test exception")
        except ValueError:
            pass

        # Client should still be closed after exception
        self.assertIsNone(agent.http_client)
        self.assertFalse(agent._owns_client)


if __name__ == '__main__':
    unittest.main()
