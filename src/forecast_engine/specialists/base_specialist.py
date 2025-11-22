"""
Base specialist class for SurfCastAI forecast engine.

This module defines the abstract interface for all specialist modules
that analyze specific data types and provide structured insights.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class SpecialistOutput:
    """
    Standard output format for all specialists.

    Attributes:
        confidence: Confidence score (0.0-1.0) in the analysis
        data: Structured data specific to the specialist
        narrative: Natural language narrative of findings (500-1000 words)
        metadata: Additional metadata about the analysis
    """

    confidence: float
    data: dict[str, Any]
    narrative: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate output after initialization."""
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"Confidence must be between 0.0 and 1.0, got {self.confidence}")

        if not isinstance(self.data, dict):
            raise ValueError(f"Data must be a dictionary, got {type(self.data)}")

        if not isinstance(self.narrative, str):
            raise ValueError(f"Narrative must be a string, got {type(self.narrative)}")

        # Add timestamp to metadata if not present
        if "timestamp" not in self.metadata:
            self.metadata["timestamp"] = datetime.now().isoformat()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "confidence": self.confidence,
            "data": self.data,
            "narrative": self.narrative,
            "metadata": self.metadata,
        }


class BaseSpecialist(ABC):
    """
    Abstract base class for all specialist modules.

    Specialists analyze specific types of data (buoys, weather, models)
    and provide structured insights for forecast generation.

    Each specialist must:
    1. Implement the analyze() method
    2. Return a SpecialistOutput with standard schema
    3. Use async/await for API calls
    4. Include proper error handling and logging
    """

    def __init__(
        self,
        config: Any | None = None,
        model_name: str | None = None,
        engine: Any | None = None,
    ):
        """
        Initialize the specialist.

        Args:
            config: Optional configuration object
            model_name: The specific OpenAI model this specialist instance should use (REQUIRED)
            engine: Reference to ForecastEngine for centralized API calls and cost tracking

        Raises:
            ValueError: If model_name is not provided (fail loudly instead of silent degradation)
        """
        if model_name is None:
            raise ValueError(
                f"{self.__class__.__name__} requires explicit model_name parameter. "
                "Silent fallback to default model removed to prevent accuracy degradation. "
                "Check your configuration."
            )

        self.config = config
        self.model_name = model_name
        self.engine = engine
        self.logger = logging.getLogger(f"specialist.{self.__class__.__name__.lower()}")
        self.logger.info(f"Initialized with model: {self.model_name}")

    @abstractmethod
    async def analyze(self, data: dict[str, Any]) -> SpecialistOutput:
        """
        Analyze data and return structured insights.

        This is the main method that must be implemented by all specialists.

        Args:
            data: Input data dictionary specific to the specialist

        Returns:
            SpecialistOutput with confidence, structured data, and narrative

        Raises:
            ValueError: If input data is invalid
            Exception: For other errors during analysis
        """
        pass

    def _validate_input(self, data: dict[str, Any], required_keys: list) -> None:
        """
        Validate input data has required keys.

        Args:
            data: Input data dictionary
            required_keys: List of required keys

        Raises:
            ValueError: If required keys are missing
        """
        missing_keys = [key for key in required_keys if key not in data]
        if missing_keys:
            raise ValueError(f"Missing required keys: {', '.join(missing_keys)}")

    def _log_analysis_start(self, data_summary: str) -> None:
        """Log the start of analysis."""
        self.logger.info(f"Starting analysis: {data_summary}")

    def _log_analysis_complete(self, confidence: float, data_points: int) -> None:
        """Log the completion of analysis."""
        self.logger.info(
            f"Analysis complete: confidence={confidence:.2f}, data_points={data_points}"
        )

    def _calculate_confidence(
        self, data_completeness: float, data_consistency: float, data_quality: float
    ) -> float:
        """
        Calculate overall confidence score from component scores.

        Args:
            data_completeness: Score for data completeness (0.0-1.0)
            data_consistency: Score for data consistency (0.0-1.0)
            data_quality: Score for data quality (0.0-1.0)

        Returns:
            Overall confidence score (0.0-1.0)
        """
        # Weighted average: quality is most important, then consistency, then completeness
        weights = {"quality": 0.5, "consistency": 0.3, "completeness": 0.2}

        confidence = (
            data_quality * weights["quality"]
            + data_consistency * weights["consistency"]
            + data_completeness * weights["completeness"]
        )

        return max(0.0, min(1.0, confidence))
