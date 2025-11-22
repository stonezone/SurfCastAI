"""
Unit tests for OpenAI API client module.

Tests cover:
1. Text-only API calls (5 tests)
2. Multimodal API calls with images (4 tests)
3. Image conversion to data URLs (4 tests)
4. Usage tracking and cost calculation (4 tests)
5. API fallback mechanisms (2 tests)
6. Thread safety (2 tests)

All tests follow AAA (Arrange-Act-Assert) pattern and use mocking to avoid real API calls.
"""

import asyncio
import base64
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from src.core.openai_client import OpenAIClient


class TestCallOpenAIAPITextMode:
    """Tests for call_openai_api() in text-only mode."""

    @pytest.mark.asyncio
    async def test_call_openai_api_text_only_returns_content(self):
        """Test text-only API call returns generated content."""
        # Arrange
        client = OpenAIClient(api_key="test-key", model="gpt-5-nano", max_tokens=1000)

        # Mock AsyncOpenAI at the import location
        with patch("openai.AsyncOpenAI") as mock_openai_class:
            mock_response = Mock()
            mock_response.choices = [Mock(message=Mock(content="Test forecast response"))]
            mock_response.usage = Mock(prompt_tokens=100, completion_tokens=50)

            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_openai_class.return_value = mock_client

            # Act
            result = await client.call_openai_api("You are a surf forecaster", "Analyze this swell")

            # Assert
            assert result == "Test forecast response", "API should return generated content"
            assert client.api_call_count == 1, "API call count should increment"

    @pytest.mark.asyncio
    async def test_call_openai_api_increments_call_count(self):
        """Test API call increments call count correctly."""
        # Arrange
        client = OpenAIClient(api_key="test-key", model="gpt-5-nano", max_tokens=1000)

        with patch("openai.AsyncOpenAI") as mock_openai_class:
            mock_response = Mock()
            mock_response.choices = [Mock(message=Mock(content="Response"))]
            mock_response.usage = Mock(prompt_tokens=50, completion_tokens=25)

            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_openai_class.return_value = mock_client

            # Act - make three API calls
            await client.call_openai_api("system", "user1")
            await client.call_openai_api("system", "user2")
            await client.call_openai_api("system", "user3")

            # Assert
            assert client.api_call_count == 3, "Call count should increment for each API call"

    @pytest.mark.asyncio
    async def test_call_openai_api_handles_api_error(self):
        """Test API error handling returns error message."""
        # Arrange
        client = OpenAIClient(api_key="invalid-key", model="gpt-5-nano", max_tokens=1000)

        with patch("openai.AsyncOpenAI") as mock_openai_class:
            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(
                side_effect=Exception("Invalid API key")
            )
            mock_openai_class.return_value = mock_client

            # Act
            result = await client.call_openai_api("system", "user")

            # Assert
            assert result.startswith("Error generating forecast:"), "Should return error message"
            assert "Invalid API key" in result, "Should include error details"

    @pytest.mark.asyncio
    async def test_call_openai_api_formats_system_user_prompts(self):
        """Test system and user prompts are properly formatted in messages."""
        # Arrange
        client = OpenAIClient(api_key="test-key", model="gpt-5-nano", max_tokens=1000)
        system_prompt = "You are an expert surf forecaster"
        user_prompt = "Analyze swell data"

        with patch("openai.AsyncOpenAI") as mock_openai_class:
            mock_response = Mock()
            mock_response.choices = [Mock(message=Mock(content="Analysis"))]
            mock_response.usage = Mock(prompt_tokens=100, completion_tokens=50)

            mock_client = AsyncMock()
            mock_create = AsyncMock(return_value=mock_response)
            mock_client.chat.completions.create = mock_create
            mock_openai_class.return_value = mock_client

            # Act
            await client.call_openai_api(system_prompt, user_prompt)

            # Assert - verify messages structure
            call_kwargs = mock_create.call_args[1]
            messages = call_kwargs["messages"]
            assert len(messages) == 2, "Should have system and user messages"
            assert messages[0]["role"] == "system", "First message should be system"
            assert messages[0]["content"] == system_prompt, "System content should match"
            assert messages[1]["role"] == "user", "Second message should be user"
            assert messages[1]["content"] == user_prompt, "User content should match"

    @pytest.mark.asyncio
    async def test_call_openai_api_respects_max_tokens(self):
        """Test max_tokens parameter is passed to API."""
        # Arrange
        max_tokens = 2048
        client = OpenAIClient(api_key="test-key", model="gpt-5-nano", max_tokens=max_tokens)

        with patch("openai.AsyncOpenAI") as mock_openai_class:
            mock_response = Mock()
            mock_response.choices = [Mock(message=Mock(content="Response"))]
            mock_response.usage = Mock(prompt_tokens=100, completion_tokens=50)

            mock_client = AsyncMock()
            mock_create = AsyncMock(return_value=mock_response)
            mock_client.chat.completions.create = mock_create
            mock_openai_class.return_value = mock_client

            # Act
            await client.call_openai_api("system", "user")

            # Assert - verify max_completion_tokens parameter
            call_kwargs = mock_create.call_args[1]
            assert "max_completion_tokens" in call_kwargs, "Should include max_completion_tokens"
            assert (
                call_kwargs["max_completion_tokens"] == max_tokens
            ), "Should match configured value"


class TestCallOpenAIAPIMultimodalMode:
    """Tests for call_openai_api() in multimodal mode with images."""

    @pytest.mark.asyncio
    async def test_call_openai_api_multimodal_with_images(self):
        """Test successful multimodal API call with images."""
        # Arrange
        client = OpenAIClient(api_key="test-key", model="gpt-5-nano", max_tokens=1000)
        image_urls = ["https://example.com/chart.png"]

        with patch("openai.AsyncOpenAI") as mock_openai_class:
            mock_response = Mock()
            mock_response.choices = [Mock(message=Mock(content="Image analysis"))]
            mock_response.usage = Mock(prompt_tokens=200, completion_tokens=100)

            mock_client = AsyncMock()
            mock_create = AsyncMock(return_value=mock_response)
            mock_client.chat.completions.create = mock_create
            mock_openai_class.return_value = mock_client

            # Act
            result = await client.call_openai_api("system", "user", image_urls=image_urls)

            # Assert
            assert result == "Image analysis", "Should return response content"
            call_kwargs = mock_create.call_args[1]
            messages = call_kwargs["messages"]
            user_content = messages[1]["content"]
            assert isinstance(user_content, list), "User content should be list for multimodal"
            assert len(user_content) == 2, "Should have text and image parts"
            assert user_content[0]["type"] == "text", "First part should be text"
            assert user_content[1]["type"] == "image_url", "Second part should be image"
            assert user_content[1]["image_url"]["url"] == image_urls[0], "Image URL should match"

    @pytest.mark.asyncio
    async def test_call_openai_api_converts_local_image_to_data_url(self, tmp_path):
        """Test image conversion to data URLs for local files."""
        # Arrange
        client = OpenAIClient(api_key="test-key", model="gpt-5-nano", max_tokens=1000)

        # Create test image
        image_path = tmp_path / "test.png"
        image_path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

        # Mock _convert_image_to_data_url to avoid actual file I/O
        with patch("openai.AsyncOpenAI") as mock_openai_class:
            with patch.object(
                client, "_convert_image_to_data_url", return_value="data:image/png;base64,test"
            ):
                mock_response = Mock()
                mock_response.choices = [Mock(message=Mock(content="Analysis"))]
                mock_response.usage = Mock(prompt_tokens=200, completion_tokens=100)

                mock_client = AsyncMock()
                mock_create = AsyncMock(return_value=mock_response)
                mock_client.chat.completions.create = mock_create
                mock_openai_class.return_value = mock_client

                # Act
                await client.call_openai_api(
                    "system", "user", image_urls=[f"data/{image_path.name}"]
                )

                # Assert
                client._convert_image_to_data_url.assert_called_once()

    @pytest.mark.asyncio
    async def test_call_openai_api_handles_multiple_images(self):
        """Test multiple images handling."""
        # Arrange
        client = OpenAIClient(api_key="test-key", model="gpt-5-nano", max_tokens=1000)
        image_urls = [
            "https://example.com/chart1.png",
            "https://example.com/chart2.png",
            "https://example.com/chart3.png",
        ]

        with patch("openai.AsyncOpenAI") as mock_openai_class:
            mock_response = Mock()
            mock_response.choices = [Mock(message=Mock(content="Multi-image analysis"))]
            mock_response.usage = Mock(prompt_tokens=300, completion_tokens=150)

            mock_client = AsyncMock()
            mock_create = AsyncMock(return_value=mock_response)
            mock_client.chat.completions.create = mock_create
            mock_openai_class.return_value = mock_client

            # Act
            await client.call_openai_api("system", "user", image_urls=image_urls)

            # Assert
            call_kwargs = mock_create.call_args[1]
            user_content = call_kwargs["messages"][1]["content"]
            # Should have 1 text part + 3 image parts
            assert len(user_content) == 4, "Should include all images"
            image_parts = [p for p in user_content if p["type"] == "image_url"]
            assert len(image_parts) == 3, "Should have 3 image parts"

    @pytest.mark.asyncio
    async def test_call_openai_api_falls_back_on_image_error(self):
        """Test fallback to text-only on image error."""
        # Arrange
        client = OpenAIClient(api_key="test-key", model="gpt-5-nano", max_tokens=1000)

        with patch("openai.AsyncOpenAI") as mock_openai_class:
            with patch.object(
                client, "_convert_image_to_data_url", side_effect=FileNotFoundError("Not found")
            ):
                mock_response = Mock()
                mock_response.choices = [Mock(message=Mock(content="Text-only response"))]
                mock_response.usage = Mock(prompt_tokens=100, completion_tokens=50)

                mock_client = AsyncMock()
                mock_create = AsyncMock(return_value=mock_response)
                mock_client.chat.completions.create = mock_create
                mock_openai_class.return_value = mock_client

                # Act - image loading fails but should continue with text
                result = await client.call_openai_api(
                    "system", "user", image_urls=["data/missing.png"]
                )

                # Assert
                assert result == "Text-only response", "Should continue with text-only"
                call_kwargs = mock_create.call_args[1]
                user_content = call_kwargs["messages"][1]["content"]
                # Should only have text part (no images loaded successfully)
                image_parts = [p for p in user_content if p["type"] == "image_url"]
                assert len(image_parts) == 0, "Should have no images after error"


class TestConvertImageToDataURL:
    """Tests for _convert_image_to_data_url() helper method."""

    def test_convert_png_image_to_data_url(self, tmp_path):
        """Test PNG image conversion to base64 data URL."""
        # Arrange
        client = OpenAIClient(api_key="test-key", model="gpt-5-nano", max_tokens=1000)
        image_path = tmp_path / "test.png"
        image_data = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        image_path.write_bytes(image_data)

        # Act
        data_url = client._convert_image_to_data_url(str(image_path))

        # Assert
        assert data_url.startswith("data:image/png;base64,"), "Should have PNG MIME type"
        encoded_data = data_url.split(",")[1]
        decoded_data = base64.b64decode(encoded_data)
        assert decoded_data == image_data, "Decoded data should match original"

    def test_convert_jpeg_image_to_data_url(self, tmp_path):
        """Test JPEG image conversion to base64 data URL."""
        # Arrange
        client = OpenAIClient(api_key="test-key", model="gpt-5-nano", max_tokens=1000)
        image_path = tmp_path / "test.jpg"
        image_data = b"\xff\xd8\xff\xe0" + b"\x00" * 100  # JPEG header
        image_path.write_bytes(image_data)

        # Act
        data_url = client._convert_image_to_data_url(str(image_path))

        # Assert
        assert data_url.startswith("data:image/jpeg;base64,"), "Should have JPEG MIME type"
        encoded_data = data_url.split(",")[1]
        decoded_data = base64.b64decode(encoded_data)
        assert decoded_data == image_data, "Decoded data should match original"

    def test_convert_image_raises_file_not_found(self):
        """Test missing file raises FileNotFoundError."""
        # Arrange
        client = OpenAIClient(api_key="test-key", model="gpt-5-nano", max_tokens=1000)

        # Act & Assert
        with pytest.raises(FileNotFoundError, match="Image file not found"):
            client._convert_image_to_data_url("/nonexistent/path/image.png")

    def test_convert_image_raises_invalid_format(self, tmp_path):
        """Test invalid image file handling."""
        # Arrange
        client = OpenAIClient(api_key="test-key", model="gpt-5-nano", max_tokens=1000)
        invalid_path = tmp_path / "test.bmp"
        invalid_path.write_bytes(b"BM" + b"\x00" * 100)

        # Act & Assert
        with pytest.raises(ValueError, match="Unsupported image format"):
            client._convert_image_to_data_url(str(invalid_path))


class TestTrackUsage:
    """Tests for _track_usage() and cost calculation."""

    @pytest.mark.asyncio
    async def test_track_usage_gpt5_nano_pricing(self):
        """Test cost calculation for gpt-5-nano pricing tier ($0.05/$0.40 per 1M tokens)."""
        # Arrange
        client = OpenAIClient(api_key="test-key", model="gpt-5-nano", max_tokens=1000)
        usage = Mock(prompt_tokens=1000, completion_tokens=500)

        # Act
        await client._track_usage(usage)

        # Assert
        # Input: 1000 tokens * $0.05 / 1M = $0.00005
        # Output: 500 tokens * $0.40 / 1M = $0.00020
        # Total: $0.00025
        expected_cost = (1000 * 0.05 / 1_000_000) + (500 * 0.40 / 1_000_000)
        assert (
            abs(client.total_cost - expected_cost) < 1e-10
        ), "Cost should match gpt-5-nano pricing"
        assert client.total_input_tokens == 1000, "Should track input tokens"
        assert client.total_output_tokens == 500, "Should track output tokens"
        assert client.api_call_count == 1, "Should increment call count"

    @pytest.mark.asyncio
    async def test_track_usage_gpt5_mini_pricing(self):
        """Test cost calculation for gpt-5-mini pricing tier ($0.25/$2.00 per 1M tokens)."""
        # Arrange
        client = OpenAIClient(api_key="test-key", model="gpt-5-mini", max_tokens=1000)
        usage = Mock(prompt_tokens=2000, completion_tokens=1000)

        # Act
        await client._track_usage(usage)

        # Assert
        # Input: 2000 tokens * $0.25 / 1M = $0.00050
        # Output: 1000 tokens * $2.00 / 1M = $0.00200
        # Total: $0.00250
        expected_cost = (2000 * 0.25 / 1_000_000) + (1000 * 2.00 / 1_000_000)
        assert (
            abs(client.total_cost - expected_cost) < 1e-10
        ), "Cost should match gpt-5-mini pricing"

    @pytest.mark.asyncio
    async def test_track_usage_gpt5_pricing(self):
        """Test cost calculation for gpt-5 pricing tier ($1.25/$10.00 per 1M tokens)."""
        # Arrange
        client = OpenAIClient(api_key="test-key", model="gpt-5", max_tokens=1000)
        usage = Mock(prompt_tokens=5000, completion_tokens=2000)

        # Act
        await client._track_usage(usage)

        # Assert
        # Input: 5000 tokens * $1.25 / 1M = $0.00625
        # Output: 2000 tokens * $10.00 / 1M = $0.02000
        # Total: $0.02625
        expected_cost = (5000 * 1.25 / 1_000_000) + (2000 * 10.00 / 1_000_000)
        assert abs(client.total_cost - expected_cost) < 1e-10, "Cost should match gpt-5 pricing"

    @pytest.mark.asyncio
    async def test_track_usage_cumulative_costs(self):
        """Test cumulative cost tracking across multiple calls."""
        # Arrange
        client = OpenAIClient(api_key="test-key", model="gpt-5-nano", max_tokens=1000)
        usage1 = Mock(prompt_tokens=1000, completion_tokens=500)
        usage2 = Mock(prompt_tokens=2000, completion_tokens=1000)
        usage3 = Mock(prompt_tokens=500, completion_tokens=250)

        # Act
        await client._track_usage(usage1)
        await client._track_usage(usage2)
        await client._track_usage(usage3)

        # Assert
        total_input = 1000 + 2000 + 500
        total_output = 500 + 1000 + 250
        expected_cost = (total_input * 0.05 / 1_000_000) + (total_output * 0.40 / 1_000_000)
        assert abs(client.total_cost - expected_cost) < 1e-10, "Should accumulate costs correctly"
        assert client.total_input_tokens == total_input, "Should accumulate input tokens"
        assert client.total_output_tokens == total_output, "Should accumulate output tokens"
        assert client.api_call_count == 3, "Should count all calls"


class TestCallAPIWithFallback:
    """Tests for _call_api_with_fallback() fallback mechanism."""

    @pytest.mark.asyncio
    async def test_fallback_to_max_tokens_for_legacy_models(self):
        """Test fallback to max_tokens for legacy models."""
        # Arrange
        client = OpenAIClient(api_key="test-key", model="gpt-4", max_tokens=1000)
        mock_client = AsyncMock()

        # First call with max_completion_tokens fails, second with max_tokens succeeds
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="Response"))]
        mock_response.usage = Mock(prompt_tokens=100, completion_tokens=50)

        call_count = 0

        async def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1 and "max_completion_tokens" in kwargs:
                raise Exception("max_completion_tokens is unsupported for this model")
            return mock_response

        mock_client.chat.completions.create = AsyncMock(side_effect=side_effect)

        # Act
        request_kwargs = {"model": "gpt-4", "messages": []}
        result = await client._call_api_with_fallback(mock_client, request_kwargs)

        # Assert
        assert result == mock_response, "Should return response after fallback"
        assert call_count == 2, "Should retry with max_tokens"

    @pytest.mark.asyncio
    async def test_fallback_reraises_non_parameter_errors(self):
        """Test retry logic on parameter error."""
        # Arrange
        client = OpenAIClient(api_key="test-key", model="gpt-5-nano", max_tokens=1000)
        mock_client = AsyncMock()

        # Simulate non-parameter error
        mock_client.chat.completions.create = AsyncMock(
            side_effect=Exception("Rate limit exceeded")
        )

        # Act & Assert
        request_kwargs = {"model": "gpt-5-nano", "messages": []}
        with pytest.raises(Exception, match="Rate limit exceeded"):
            await client._call_api_with_fallback(mock_client, request_kwargs)


class TestThreadSafety:
    """Tests for thread safety in concurrent scenarios."""

    @pytest.mark.asyncio
    async def test_concurrent_cost_tracking_maintains_accuracy(self):
        """Test concurrent cost tracking maintains accuracy."""
        # Arrange
        client = OpenAIClient(api_key="test-key", model="gpt-5-nano", max_tokens=1000)

        # Create multiple usage objects
        usage_objects = [Mock(prompt_tokens=100, completion_tokens=50) for _ in range(10)]

        # Act - track usage concurrently
        tasks = [client._track_usage(usage) for usage in usage_objects]
        await asyncio.gather(*tasks)

        # Assert
        expected_input = 100 * 10
        expected_output = 50 * 10
        expected_cost = (expected_input * 0.05 / 1_000_000) + (expected_output * 0.40 / 1_000_000)

        assert client.total_input_tokens == expected_input, "Should track all input tokens"
        assert client.total_output_tokens == expected_output, "Should track all output tokens"
        assert (
            abs(client.total_cost - expected_cost) < 1e-10
        ), "Should calculate total cost correctly"
        assert client.api_call_count == 10, "Should count all calls"

    @pytest.mark.asyncio
    async def test_concurrent_api_calls_dont_corrupt_state(self):
        """Test concurrent API calls don't corrupt state."""
        # Arrange
        client = OpenAIClient(api_key="test-key", model="gpt-5-nano", max_tokens=1000)

        with patch("openai.AsyncOpenAI") as mock_openai_class:
            mock_response = Mock()
            mock_response.choices = [Mock(message=Mock(content="Response"))]
            mock_response.usage = Mock(prompt_tokens=100, completion_tokens=50)

            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_openai_class.return_value = mock_client

            # Act - make 5 concurrent API calls
            tasks = [client.call_openai_api("system", f"user{i}") for i in range(5)]
            results = await asyncio.gather(*tasks)

            # Assert
            assert all(r == "Response" for r in results), "All calls should succeed"
            assert client.api_call_count == 5, "Should count all concurrent calls"
            # Each call: (100 * 0.05 + 50 * 0.40) / 1M = 0.000025
            expected_total = 0.000025 * 5
            assert abs(client.total_cost - expected_total) < 1e-10, "Should track costs correctly"


class TestMetricsAndReset:
    """Tests for metrics retrieval and reset functionality."""

    @pytest.mark.asyncio
    async def test_get_metrics_returns_complete_data(self):
        """Test get_metrics() returns all tracking data."""
        # Arrange
        client = OpenAIClient(api_key="test-key", model="gpt-5-nano", max_tokens=1000)
        usage = Mock(prompt_tokens=1000, completion_tokens=500)
        await client._track_usage(usage)

        # Act
        metrics = await client.get_metrics()

        # Assert
        assert "total_cost" in metrics, "Should include total_cost"
        assert "api_calls" in metrics, "Should include api_calls"
        assert "input_tokens" in metrics, "Should include input_tokens"
        assert "output_tokens" in metrics, "Should include output_tokens"
        assert "model" in metrics, "Should include model"
        assert metrics["api_calls"] == 1, "Should report correct call count"
        assert metrics["model"] == "gpt-5-nano", "Should report model name"

    @pytest.mark.asyncio
    async def test_reset_metrics_clears_all_counters(self):
        """Test reset_metrics() clears all tracking counters."""
        # Arrange
        client = OpenAIClient(api_key="test-key", model="gpt-5-nano", max_tokens=1000)
        usage = Mock(prompt_tokens=1000, completion_tokens=500)
        await client._track_usage(usage)

        # Verify initial state
        assert client.api_call_count > 0, "Should have calls before reset"

        # Act
        await client.reset_metrics()

        # Assert
        assert client.total_cost == 0.0, "Should reset total_cost"
        assert client.api_call_count == 0, "Should reset api_call_count"
        assert client.total_input_tokens == 0, "Should reset total_input_tokens"
        assert client.total_output_tokens == 0, "Should reset total_output_tokens"


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_api_returns_none_content(self):
        """Test handling when API returns None content."""
        # Arrange
        client = OpenAIClient(api_key="test-key", model="gpt-5-nano", max_tokens=1000)

        with patch("openai.AsyncOpenAI") as mock_openai_class:
            mock_response = Mock()
            mock_response.choices = [Mock(message=Mock(content=None))]
            mock_response.usage = Mock(prompt_tokens=100, completion_tokens=50)

            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_openai_class.return_value = mock_client

            # Act
            result = await client.call_openai_api("system", "user")

            # Assert
            assert result == "", "Should return empty string when content is None"

    @pytest.mark.asyncio
    async def test_api_returns_no_usage_data(self):
        """Test handling when API returns no usage data."""
        # Arrange
        client = OpenAIClient(api_key="test-key", model="gpt-5-nano", max_tokens=1000)

        with patch("openai.AsyncOpenAI") as mock_openai_class:
            mock_response = Mock()
            mock_response.choices = [Mock(message=Mock(content="Response"))]
            mock_response.usage = None  # No usage data

            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_openai_class.return_value = mock_client

            # Act
            result = await client.call_openai_api("system", "user")

            # Assert
            assert result == "Response", "Should still return content"
            # Cost tracking should not increment without usage data
            assert client.api_call_count == 0, "Should not count call without usage data"

    @pytest.mark.asyncio
    async def test_temperature_parameter_handling(self):
        """Test temperature parameter is only included when specified."""
        # Arrange - client with temperature
        client_with_temp = OpenAIClient(
            api_key="test-key", model="gpt-5-nano", max_tokens=1000, temperature=0.7
        )

        # Arrange - client without temperature
        client_without_temp = OpenAIClient(
            api_key="test-key", model="gpt-5-nano", max_tokens=1000, temperature=None
        )

        with patch("openai.AsyncOpenAI") as mock_openai_class:
            mock_response = Mock()
            mock_response.choices = [Mock(message=Mock(content="Response"))]
            mock_response.usage = Mock(prompt_tokens=100, completion_tokens=50)

            mock_client = AsyncMock()
            mock_create = AsyncMock(return_value=mock_response)
            mock_client.chat.completions.create = mock_create
            mock_openai_class.return_value = mock_client

            # Act - call with temperature
            await client_with_temp.call_openai_api("system", "user")
            call_with_temp_kwargs = mock_create.call_args[1]

            # Reset mock
            mock_create.reset_mock()

            # Act - call without temperature
            await client_without_temp.call_openai_api("system", "user")
            call_without_temp_kwargs = mock_create.call_args[1]

            # Assert
            assert (
                "temperature" in call_with_temp_kwargs
            ), "Should include temperature when specified"
            assert call_with_temp_kwargs["temperature"] == 0.7, "Should match specified value"
            assert (
                "temperature" not in call_without_temp_kwargs
            ), "Should not include temperature when None"

    @pytest.mark.asyncio
    async def test_image_limit_enforcement(self):
        """Test that only first 10 images are processed (GPT-5 limit)."""
        # Arrange
        client = OpenAIClient(api_key="test-key", model="gpt-5-nano", max_tokens=1000)
        image_urls = [f"https://example.com/image{i}.png" for i in range(15)]  # 15 images

        with patch("openai.AsyncOpenAI") as mock_openai_class:
            mock_response = Mock()
            mock_response.choices = [Mock(message=Mock(content="Response"))]
            mock_response.usage = Mock(prompt_tokens=300, completion_tokens=150)

            mock_client = AsyncMock()
            mock_create = AsyncMock(return_value=mock_response)
            mock_client.chat.completions.create = mock_create
            mock_openai_class.return_value = mock_client

            # Act
            await client.call_openai_api("system", "user", image_urls=image_urls)

            # Assert
            call_kwargs = mock_create.call_args[1]
            user_content = call_kwargs["messages"][1]["content"]
            image_parts = [p for p in user_content if p["type"] == "image_url"]
            assert len(image_parts) == 10, "Should limit to 10 images (GPT-5 limit)"
