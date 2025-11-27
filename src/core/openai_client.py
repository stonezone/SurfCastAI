"""
OpenAI API client with cost and token tracking.

This module provides a centralized OpenAI API client used by ForecastEngine
and specialist classes (BuoyAnalyst, PressureAnalyst, SeniorForecaster).
It handles both text and multimodal (vision) API calls while tracking
token usage and costs in a thread-safe manner.
"""

import asyncio
import base64
import logging
from pathlib import Path
from typing import Any


class OpenAIClient:
    """
    Centralized OpenAI-compatible API client with cost and token tracking.

    Features:
    - Text and multimodal (vision) API calls
    - Automatic cost calculation by model
    - Thread-safe token/cost tracking
    - Graceful handling of model parameter differences
    - Support for local file paths (converts to base64 data URLs)
    - Support for alternative providers (Kimi K2) via custom base_url

    Usage:
        # OpenAI (default)
        client = OpenAIClient(
            api_key="sk-...",
            model="gpt-5-nano",
            max_tokens=32768,
            temperature=None  # GPT-5 uses default
        )

        # Kimi K2 (Moonshot AI)
        client = OpenAIClient(
            api_key="your-moonshot-key",
            model="kimi-k2-0711-preview",
            max_tokens=4000,
            base_url="https://api.moonshot.ai/v1"
        )

        response = await client.call_openai_api(
            system_prompt="You are a surf forecaster...",
            user_prompt="Analyze this swell...",
            image_urls=["data/bundle/chart.png"],
            detail="high"
        )

        metrics = await client.get_metrics()
        print(f"Cost: ${metrics['total_cost']:.6f}")
    """

    # Model pricing (per 1M tokens)
    # Source: https://openai.com/pricing, https://platform.moonshot.ai/pricing
    MODEL_PRICING = {
        # GPT-5 family (August 2025) - all vision-capable
        "gpt-5": {"input": 1.25, "output": 10.00},
        "gpt-5-mini": {"input": 0.25, "output": 2.00},
        "gpt-5-nano": {"input": 0.05, "output": 0.40},  # Default - cheapest
        # GPT-4.1 family (April 2025) - 1M token context, vision-capable
        "gpt-4.1": {"input": 2.00, "output": 8.00},
        "gpt-4.1-mini": {"input": 0.40, "output": 1.60},
        "gpt-4.1-nano": {"input": 0.10, "output": 0.40},
        # GPT-4o family - multimodal (text + vision + audio)
        "gpt-4o": {"input": 2.50, "output": 10.00},
        "chatgpt-4o-latest": {"input": 5.00, "output": 15.00},
        "gpt-4o-mini": {"input": 0.15, "output": 0.60},
        "gpt-4o-nano": {"input": 0.05, "output": 0.20},
        # Kimi K2 (Moonshot AI) - essentially free tier
        # 3M tokens/day free, 6 req/min limit
        "kimi-k2-0711-preview": {"input": 0.00, "output": 0.00},
        "kimi-k2": {"input": 0.00, "output": 0.00},
        "default": {"input": 0.10, "output": 0.40},  # Fallback pricing
    }

    # Supported image formats
    IMAGE_MIME_TYPES = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
    }

    def __init__(
        self,
        api_key: str,
        model: str,
        max_tokens: int,
        temperature: float | None = None,
        logger: logging.Logger | None = None,
        base_url: str | None = None,
    ):
        """
        Initialize OpenAI-compatible API client.

        Args:
            api_key: API key (OpenAI or Moonshot/Kimi)
            model: Model name (e.g., 'gpt-5-nano', 'gpt-5-mini', 'gpt-5', 'kimi-k2-0711-preview')
            max_tokens: Maximum output tokens
            temperature: Sampling temperature (None = use model default, recommended for GPT-5)
            logger: Optional logger instance (creates one if not provided)
            base_url: Optional custom API base URL (e.g., 'https://api.moonshot.ai/v1' for Kimi)
        """
        self.api_key = api_key
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.logger = logger or logging.getLogger("openai.client")
        self.base_url = base_url

        # Initialize cost tracking
        self.total_cost = 0.0
        self.api_call_count = 0
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self._cost_lock = asyncio.Lock()  # Thread-safe metric updates

        # Log initialization
        temp_str = (
            f"temperature={temperature}" if temperature is not None else "default temperature"
        )
        provider_str = f", base_url={base_url}" if base_url else ""
        self.logger.info(
            f"OpenAI client initialized: model={model}, max_tokens={max_tokens}, {temp_str}{provider_str}"
        )

    async def call_openai_api(
        self,
        system_prompt: str,
        user_prompt: str,
        image_urls: list[str] | None = None,
        detail: str = "auto",
    ) -> str:
        """
        Call OpenAI API to generate text with optional image inputs.

        This method handles both text-only and multimodal (vision) API calls.
        It automatically tracks token usage and costs in a thread-safe manner.

        Args:
            system_prompt: System prompt for the model
            user_prompt: User prompt containing specific request
            image_urls: Optional list of image URLs/paths (max 10 for GPT-5)
            detail: Image resolution - "auto", "low", or "high"

        Returns:
            Generated text content

        Raises:
            ImportError: If openai package is not installed
            Exception: For API errors or other failures
        """
        # Import here to avoid dependency if OpenAI is not available
        try:
            from openai import AsyncOpenAI
        except ImportError:
            self.logger.error("OpenAI package not installed. Install with: pip install openai")
            return "Error: OpenAI package not installed."

        try:
            # Log prompt details for debugging
            self.logger.debug(f"System prompt length: {len(system_prompt)} chars")
            self.logger.debug(f"User prompt length: {len(user_prompt)} chars")
            self.logger.debug(f"User prompt preview: {user_prompt[:500]}...")

            # Initialize client with optional custom base URL (for Kimi K2, etc.)
            client_kwargs = {"api_key": self.api_key}
            if self.base_url:
                client_kwargs["base_url"] = self.base_url
            client = AsyncOpenAI(**client_kwargs)

            # Build message content
            if image_urls:
                # Multimodal message with images
                content = [{"type": "text", "text": user_prompt}]

                for url in image_urls[:10]:  # GPT-5 limit: 10 images
                    # Convert local paths to base64 data URLs
                    if url.startswith("data/"):
                        try:
                            url = self._convert_image_to_data_url(url)
                        except Exception as e:
                            self.logger.warning(f"Failed to load image {url}: {e}")
                            continue

                    content.append(
                        {"type": "image_url", "image_url": {"url": url, "detail": detail}}
                    )

                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": content},
                ]
            else:
                # Text-only message
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ]

            # Build API request parameters
            request_kwargs = {
                "model": self.model,
                "messages": messages,
            }

            # Only add temperature if specified (GPT-5 models use default)
            if self.temperature is not None:
                request_kwargs["temperature"] = self.temperature

            # Call API with parameter fallback for legacy models
            response = await self._call_api_with_fallback(client, request_kwargs)

            # Extract and track usage
            if response.choices and response.choices[0].message:
                content = response.choices[0].message.content
                self.logger.debug(
                    f"API response content type: {type(content)}, value: {repr(content)}"
                )

                # Track token usage and costs
                if hasattr(response, "usage") and response.usage:
                    await self._track_usage(response.usage)
                else:
                    self.logger.warning("No usage data returned from API")

                if content is None:
                    self.logger.error("API returned None for content")
                    return ""
                return content.strip()
            else:
                self.logger.error("No content returned from OpenAI API")
                return ""

        except Exception as e:
            self.logger.error(f"Error calling OpenAI API: {e}")
            return f"Error generating forecast: {str(e)}"

    async def reset_metrics(self) -> None:
        """
        Reset per-run tracking metrics.

        Call this before starting a new forecast generation to reset
        cost and token counters. Thread-safe.
        """
        async with self._cost_lock:
            self.total_cost = 0.0
            self.api_call_count = 0
            self.total_input_tokens = 0
            self.total_output_tokens = 0
            self.logger.debug("Metrics reset")

    async def get_metrics(self) -> dict[str, Any]:
        """
        Get current usage metrics.

        Returns:
            Dictionary with keys:
            - total_cost: Total cost in USD
            - api_calls: Number of API calls made
            - input_tokens: Total input tokens
            - output_tokens: Total output tokens
            - model: Model name
        """
        async with self._cost_lock:
            return {
                "total_cost": round(self.total_cost, 6),
                "api_calls": self.api_call_count,
                "input_tokens": self.total_input_tokens,
                "output_tokens": self.total_output_tokens,
                "model": self.model,
            }

    def _convert_image_to_data_url(self, file_path: str) -> str:
        """
        Convert local image file to base64 data URL.

        Args:
            file_path: Path to local image file

        Returns:
            Base64-encoded data URL

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If file format is not supported
        """
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"Image file not found: {file_path}")

        # Get MIME type from extension
        ext = path.suffix.lower()
        mime_type = self.IMAGE_MIME_TYPES.get(ext)
        if not mime_type:
            raise ValueError(
                f"Unsupported image format: {ext}. "
                f"Supported formats: {', '.join(self.IMAGE_MIME_TYPES.keys())}"
            )

        # Read and encode image
        image_data = base64.b64encode(path.read_bytes()).decode()
        return f"data:{mime_type};base64,{image_data}"

    async def _call_api_with_fallback(self, client, request_kwargs: dict[str, Any]):
        """
        Call OpenAI API with graceful fallback for legacy models.

        Modern models support max_completion_tokens, but legacy models
        require max_tokens. This method tries the modern parameter first,
        then falls back if unsupported.

        Args:
            client: AsyncOpenAI client instance
            request_kwargs: Base request parameters (model, messages, etc.)

        Returns:
            API response object
        """
        try:
            # Try modern parameter first
            response = await client.chat.completions.create(
                **request_kwargs, max_completion_tokens=self.max_tokens
            )
            return response
        except Exception as call_error:
            # Check if error is due to unsupported parameter
            error_text = str(call_error).lower()
            if "max_completion_tokens" in error_text and any(
                keyword in error_text for keyword in ("unsupported", "unrecognized", "unknown")
            ):
                self.logger.debug(
                    f"max_completion_tokens unsupported for model {self.model}; retrying with max_tokens"
                )
                response = await client.chat.completions.create(
                    **request_kwargs, max_tokens=self.max_tokens
                )
                return response
            else:
                # Re-raise if it's a different error
                raise

    async def _track_usage(self, usage) -> None:
        """
        Track token usage and calculate costs.

        Thread-safe method that updates metrics and logs per-call costs.

        Args:
            usage: Usage object from API response
        """
        input_tokens = usage.prompt_tokens
        output_tokens = usage.completion_tokens

        # Calculate cost based on model pricing
        cost = self._calculate_cost(input_tokens, output_tokens)

        # Accumulate totals (thread-safe)
        async with self._cost_lock:
            self.total_input_tokens += input_tokens
            self.total_output_tokens += output_tokens
            self.total_cost += cost
            self.api_call_count += 1
            # Capture values for logging outside lock
            call_num = self.api_call_count
            total_cost = self.total_cost

        self.logger.info(
            f"API call #{call_num}: {input_tokens} input + {output_tokens} output tokens = ${cost:.6f} "
            f"(total: ${total_cost:.6f})"
        )

    def _calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """
        Calculate cost for token usage based on model pricing.

        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens

        Returns:
            Cost in USD
        """
        # Determine pricing tier - check most specific matches first
        model_lower = self.model.lower()

        if "kimi-k2" in model_lower:
            pricing = self.MODEL_PRICING["kimi-k2"]
        # GPT-5 family
        elif "gpt-5-nano" in model_lower:
            pricing = self.MODEL_PRICING["gpt-5-nano"]
        elif "gpt-5-mini" in model_lower:
            pricing = self.MODEL_PRICING["gpt-5-mini"]
        elif "gpt-5" in model_lower:
            pricing = self.MODEL_PRICING["gpt-5"]
        # GPT-4.1 family
        elif "gpt-4.1-nano" in model_lower:
            pricing = self.MODEL_PRICING["gpt-4.1-nano"]
        elif "gpt-4.1-mini" in model_lower:
            pricing = self.MODEL_PRICING["gpt-4.1-mini"]
        elif "gpt-4.1" in model_lower:
            pricing = self.MODEL_PRICING["gpt-4.1"]
        # GPT-4o family
        elif "gpt-4o-nano" in model_lower:
            pricing = self.MODEL_PRICING["gpt-4o-nano"]
        elif "gpt-4o-mini" in model_lower:
            pricing = self.MODEL_PRICING["gpt-4o-mini"]
        elif "chatgpt-4o-latest" in model_lower:
            pricing = self.MODEL_PRICING["chatgpt-4o-latest"]
        elif "gpt-4o" in model_lower:
            pricing = self.MODEL_PRICING["gpt-4o"]
        else:
            pricing = self.MODEL_PRICING["default"]
            self.logger.debug(f"Using default pricing for unknown model: {self.model}")

        # Calculate cost (pricing is per 1M tokens, so divide by 1M)
        input_cost = input_tokens * (pricing["input"] / 1_000_000)
        output_cost = output_tokens * (pricing["output"] / 1_000_000)

        return input_cost + output_cost
