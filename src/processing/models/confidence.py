"""
Confidence reporting models for SurfCastAI forecasts.

This module defines structured confidence reports that provide visibility
into forecast quality and the factors that contribute to the confidence score.
"""


from pydantic import BaseModel, ConfigDict, Field, field_validator


class ConfidenceReport(BaseModel):
    """
    Structured report of forecast confidence with detailed breakdown.

    Provides transparency into forecast quality by exposing the cascade of
    confidence factors from data sources through to the final score.

    Attributes:
        overall_score: Overall confidence score (0.0-1.0)
        category: Human-readable confidence category
        factors: Contributing factors to overall score
        breakdown: Source-level confidence scores
        warnings: Quality warnings and issues identified
    """

    overall_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Overall confidence score (0.0 = no confidence, 1.0 = perfect confidence)",
    )

    category: str = Field(
        ..., description="Human-readable confidence category: 'high', 'medium', or 'low'"
    )

    factors: dict[str, float] = Field(
        default_factory=dict,
        description="Contributing factors (e.g., model_consensus, data_completeness, source_agreement)",
    )

    breakdown: dict[str, float] = Field(
        default_factory=dict,
        description="Source-level confidence scores (e.g., buoy_confidence, pressure_confidence, model_confidence)",
    )

    warnings: list[str] = Field(
        default_factory=list,
        description="Quality warnings (e.g., 'Limited buoy data', 'Model disagreement')",
    )

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: str) -> str:
        """Ensure category is one of the expected values."""
        valid_categories = {"high", "medium", "low"}
        if v not in valid_categories:
            raise ValueError(f"Category must be one of {valid_categories}, got: {v}")
        return v

    @field_validator("factors", "breakdown")
    @classmethod
    def validate_confidence_values(cls, v: dict[str, float]) -> dict[str, float]:
        """Ensure all confidence values are in valid range [0.0, 1.0]."""
        for key, value in v.items():
            if not isinstance(value, (int, float)):
                raise ValueError(
                    f"Confidence value for '{key}' must be numeric, got: {type(value)}"
                )
            if not 0.0 <= value <= 1.0:
                raise ValueError(
                    f"Confidence value for '{key}' must be in [0.0, 1.0], got: {value}"
                )
        return v

    @staticmethod
    def categorize_score(score: float) -> str:
        """
        Convert numeric score to category.

        Args:
            score: Confidence score (0.0-1.0)

        Returns:
            Category string: 'high', 'medium', or 'low'
        """
        if score >= 0.7:
            return "high"
        elif score >= 0.4:
            return "medium"
        else:
            return "low"

    def to_log_summary(self) -> str:
        """
        Generate a concise log summary of the confidence report.

        Returns:
            Formatted string suitable for logging

        Example:
            "Confidence: 0.85 (high) - buoy: 0.90, pressure: 0.80, model: 0.85"
        """
        breakdown_str = ", ".join(
            f"{key}: {value:.2f}" for key, value in sorted(self.breakdown.items())
        )

        if breakdown_str:
            return f"Confidence: {self.overall_score:.2f} ({self.category}) - {breakdown_str}"
        else:
            return f"Confidence: {self.overall_score:.2f} ({self.category})"

    def to_detailed_summary(self) -> str:
        """
        Generate a detailed multi-line summary of the confidence report.

        Returns:
            Formatted multi-line string with full details
        """
        lines = [f"Overall Confidence: {self.overall_score:.2f} ({self.category})", ""]

        if self.breakdown:
            lines.append("Source Breakdown:")
            for key, value in sorted(self.breakdown.items()):
                lines.append(f"  - {key}: {value:.2f}")
            lines.append("")

        if self.factors:
            lines.append("Contributing Factors:")
            for key, value in sorted(self.factors.items()):
                lines.append(f"  - {key}: {value:.2f}")
            lines.append("")

        if self.warnings:
            lines.append("Warnings:")
            for warning in self.warnings:
                lines.append(f"  - {warning}")

        return "\n".join(lines)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "overall_score": 0.85,
                "category": "high",
                "factors": {
                    "model_consensus": 0.90,
                    "data_completeness": 0.80,
                    "source_agreement": 0.85,
                },
                "breakdown": {
                    "buoy_confidence": 0.90,
                    "pressure_confidence": 0.80,
                    "model_confidence": 0.85,
                },
                "warnings": [],
            }
        }
    )


__all__ = ["ConfidenceReport"]
