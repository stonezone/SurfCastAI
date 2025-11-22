"""
Unit tests for specialist Pydantic schemas.

Tests all 20 models and 10 enums in schemas.py for:
- Field validation (ranges, rounding, types)
- Enum conversions
- Nested model construction
- Serialization
- Error handling

Follows test pattern from tests/unit/processing/test_bounds_validation.py
using unittest framework.
"""

import json
import unittest
from datetime import datetime

from pydantic import ValidationError

from src.forecast_engine.specialists.schemas import (
    AgreementLevel,
    AnalysisSummary,
    BuoyAnalystData,
    BuoyAnalystOutput,
    BuoyAnomaly,
    # BuoyAnalyst Models
    BuoyTrend,
    # SeniorForecaster Models
    Contradiction,
    CrossValidation,
    FetchQuality,
    # PressureAnalyst Models
    FetchWindow,
    FrontalBoundary,
    FrontType,
    ImpactLevel,
    IntensificationTrend,
    PredictedSwell,
    PressureAnalystData,
    PressureAnalystOutput,
    QualityFlag,
    SeniorForecasterData,
    SeniorForecasterInput,
    SeniorForecasterOutput,
    SeverityLevel,
    ShoreConditions,
    ShoreForecast,
    SummaryStats,
    SwellBreakdown,
    Synthesis,
    SystemType,
    # Enums
    TrendType,
    WeatherSystem,
    # Utility functions
    validate_buoy_output,
    validate_pressure_output,
    validate_senior_output,
)

# =============================================================================
# ENUM TESTS
# =============================================================================


class TestEnumValues(unittest.TestCase):
    """Test enum value integrity and string values."""

    def test_trend_type_enum_values(self):
        """Test TrendType enum has all expected values."""
        self.assertEqual(TrendType.STEADY.value, "steady")
        self.assertEqual(TrendType.INCREASING_STRONG.value, "increasing_strong")
        self.assertEqual(TrendType.INCREASING_MODERATE.value, "increasing_moderate")
        self.assertEqual(TrendType.INCREASING_SLIGHT.value, "increasing_slight")
        self.assertEqual(TrendType.DECREASING_STRONG.value, "decreasing_strong")
        self.assertEqual(TrendType.DECREASING_MODERATE.value, "decreasing_moderate")
        self.assertEqual(TrendType.DECREASING_SLIGHT.value, "decreasing_slight")
        self.assertEqual(TrendType.INSUFFICIENT_DATA.value, "insufficient_data")

    def test_severity_level_enum_values(self):
        """Test SeverityLevel enum has all expected values."""
        self.assertEqual(SeverityLevel.HIGH.value, "high")
        self.assertEqual(SeverityLevel.MODERATE.value, "moderate")

    def test_quality_flag_enum_values(self):
        """Test QualityFlag enum has all expected values."""
        self.assertEqual(QualityFlag.EXCLUDED.value, "excluded")
        self.assertEqual(QualityFlag.SUSPECT.value, "suspect")
        self.assertEqual(QualityFlag.VALID.value, "valid")

    def test_agreement_level_enum_values(self):
        """Test AgreementLevel enum has all expected values."""
        self.assertEqual(AgreementLevel.EXCELLENT_AGREEMENT.value, "excellent_agreement")
        self.assertEqual(AgreementLevel.GOOD_AGREEMENT.value, "good_agreement")
        self.assertEqual(AgreementLevel.MODERATE_AGREEMENT.value, "moderate_agreement")
        self.assertEqual(AgreementLevel.POOR_AGREEMENT.value, "poor_agreement")
        self.assertEqual(AgreementLevel.VERY_POOR_AGREEMENT.value, "very_poor_agreement")

    def test_system_type_enum_values(self):
        """Test SystemType enum has all expected values."""
        self.assertEqual(SystemType.LOW_PRESSURE.value, "low_pressure")
        self.assertEqual(SystemType.HIGH_PRESSURE.value, "high_pressure")

    def test_front_type_enum_values(self):
        """Test FrontType enum has all expected values."""
        self.assertEqual(FrontType.COLD_FRONT.value, "cold_front")
        self.assertEqual(FrontType.WARM_FRONT.value, "warm_front")

    def test_fetch_quality_enum_values(self):
        """Test FetchQuality enum has all expected values."""
        self.assertEqual(FetchQuality.STRONG.value, "strong")
        self.assertEqual(FetchQuality.MODERATE.value, "moderate")
        self.assertEqual(FetchQuality.WEAK.value, "weak")

    def test_intensification_trend_enum_values(self):
        """Test IntensificationTrend enum has all expected values."""
        self.assertEqual(IntensificationTrend.STRENGTHENING.value, "strengthening")
        self.assertEqual(IntensificationTrend.WEAKENING.value, "weakening")
        self.assertEqual(IntensificationTrend.STEADY.value, "steady")

    def test_impact_level_enum_values(self):
        """Test ImpactLevel enum has all expected values."""
        self.assertEqual(ImpactLevel.HIGH.value, "high")
        self.assertEqual(ImpactLevel.MEDIUM.value, "medium")
        self.assertEqual(ImpactLevel.LOW.value, "low")

    def test_shore_conditions_enum_values(self):
        """Test ShoreConditions enum has all expected values."""
        self.assertEqual(ShoreConditions.CLEAN.value, "clean")
        self.assertEqual(ShoreConditions.FAIR.value, "fair")
        self.assertEqual(ShoreConditions.CHOPPY.value, "choppy")
        self.assertEqual(ShoreConditions.MIXED_AND_CHOPPY.value, "mixed and choppy")
        self.assertEqual(ShoreConditions.FAIR_TO_CHOPPY.value, "fair to choppy")
        self.assertEqual(ShoreConditions.SMALL_AND_CLEAN.value, "small and clean")


# =============================================================================
# BUOY ANALYST TESTS
# =============================================================================


class TestBuoyTrendSchema(unittest.TestCase):
    """Test BuoyTrend Pydantic model."""

    def test_creation_with_valid_data(self):
        """Test BuoyTrend creation with valid data."""
        trend = BuoyTrend(
            buoy_id="51001",
            buoy_name="NW Hawaii",
            height_trend=TrendType.INCREASING_MODERATE,
            height_slope=0.1234,
            height_current=5.5,
            period_trend=TrendType.STEADY,
            period_slope=0.0012,
            period_current=12.5,
            direction_trend=TrendType.DECREASING_SLIGHT,
            direction_current=270.0,
            observations_count=24,
        )
        self.assertEqual(trend.buoy_id, "51001")
        self.assertEqual(trend.buoy_name, "NW Hawaii")
        self.assertEqual(trend.height_trend, TrendType.INCREASING_MODERATE)
        self.assertEqual(trend.height_slope, 0.1234)
        self.assertEqual(trend.height_current, 5.5)
        self.assertEqual(trend.observations_count, 24)

    def test_slope_rounding_to_4_decimals(self):
        """Test height_slope and period_slope round to 4 decimals."""
        trend = BuoyTrend(
            buoy_id="51001",
            buoy_name="NW Hawaii",
            height_trend=TrendType.STEADY,
            height_slope=0.123456789,
            period_trend=TrendType.STEADY,
            period_slope=0.987654321,
            direction_trend=TrendType.STEADY,
            observations_count=10,
        )
        self.assertEqual(trend.height_slope, 0.1235)  # Rounded to 4 decimals
        self.assertEqual(trend.period_slope, 0.9877)  # Rounded to 4 decimals

    def test_measurements_rounding_to_2_decimals(self):
        """Test height_current and period_current round to 2 decimals."""
        trend = BuoyTrend(
            buoy_id="51001",
            buoy_name="NW Hawaii",
            height_trend=TrendType.STEADY,
            height_slope=0.0,
            height_current=5.5555,
            period_trend=TrendType.STEADY,
            period_slope=0.0,
            period_current=12.7777,
            direction_trend=TrendType.STEADY,
            observations_count=10,
        )
        self.assertEqual(trend.height_current, 5.56)  # Rounded to 2 decimals
        self.assertEqual(trend.period_current, 12.78)  # Rounded to 2 decimals

    def test_direction_validation_valid_range(self):
        """Test direction_current accepts 0-360 degrees."""
        trend = BuoyTrend(
            buoy_id="51001",
            buoy_name="NW Hawaii",
            height_trend=TrendType.STEADY,
            height_slope=0.0,
            period_trend=TrendType.STEADY,
            period_slope=0.0,
            direction_trend=TrendType.STEADY,
            direction_current=270.0,
            observations_count=10,
        )
        self.assertEqual(trend.direction_current, 270.0)

    def test_direction_validation_rejects_over_360(self):
        """Test direction_current rejects values > 360."""
        with self.assertRaises(ValidationError) as context:
            BuoyTrend(
                buoy_id="51001",
                buoy_name="NW Hawaii",
                height_trend=TrendType.STEADY,
                height_slope=0.0,
                period_trend=TrendType.STEADY,
                period_slope=0.0,
                direction_trend=TrendType.STEADY,
                direction_current=400.0,
                observations_count=10,
            )
        self.assertIn("Direction must be between 0 and 360", str(context.exception))

    def test_direction_validation_rejects_negative(self):
        """Test direction_current rejects negative values."""
        with self.assertRaises(ValidationError) as context:
            BuoyTrend(
                buoy_id="51001",
                buoy_name="NW Hawaii",
                height_trend=TrendType.STEADY,
                height_slope=0.0,
                period_trend=TrendType.STEADY,
                period_slope=0.0,
                direction_trend=TrendType.STEADY,
                direction_current=-10.0,
                observations_count=10,
            )
        self.assertIn("Direction must be between 0 and 360", str(context.exception))

    def test_string_to_enum_conversion(self):
        """Test string values auto-convert to TrendType enum."""
        trend = BuoyTrend(
            buoy_id="51001",
            buoy_name="NW Hawaii",
            height_trend="steady",  # String instead of enum
            height_slope=0.0,
            period_trend="increasing_moderate",  # String
            period_slope=0.0,
            direction_trend="decreasing_strong",  # String
            observations_count=10,
        )
        self.assertEqual(trend.height_trend, TrendType.STEADY)
        self.assertIsInstance(trend.height_trend, TrendType)
        self.assertEqual(trend.period_trend, TrendType.INCREASING_MODERATE)
        self.assertIsInstance(trend.period_trend, TrendType)

    def test_optional_fields_accept_none(self):
        """Test BuoyTrend allows None for optional fields."""
        trend = BuoyTrend(
            buoy_id="51001",
            buoy_name="NW Hawaii",
            height_trend=TrendType.STEADY,
            height_slope=0.0,
            height_current=None,  # Optional
            period_trend=TrendType.STEADY,
            period_slope=0.0,
            period_current=None,  # Optional
            direction_trend=TrendType.STEADY,
            direction_current=None,  # Optional
            observations_count=10,
        )
        self.assertIsNone(trend.height_current)
        self.assertIsNone(trend.period_current)
        self.assertIsNone(trend.direction_current)

    def test_serialization_to_dict(self):
        """Test BuoyTrend can serialize to dict."""
        trend = BuoyTrend(
            buoy_id="51001",
            buoy_name="NW Hawaii",
            height_trend=TrendType.STEADY,
            height_slope=0.1234,
            period_trend=TrendType.STEADY,
            period_slope=0.0012,
            direction_trend=TrendType.STEADY,
            observations_count=10,
        )
        data_dict = trend.model_dump()
        self.assertIsInstance(data_dict, dict)
        self.assertEqual(data_dict["buoy_id"], "51001")
        self.assertEqual(data_dict["height_trend"], "steady")

    def test_serialization_to_json(self):
        """Test BuoyTrend can serialize to JSON string."""
        trend = BuoyTrend(
            buoy_id="51001",
            buoy_name="NW Hawaii",
            height_trend=TrendType.STEADY,
            height_slope=0.1234,
            period_trend=TrendType.STEADY,
            period_slope=0.0012,
            direction_trend=TrendType.STEADY,
            observations_count=10,
        )
        json_str = trend.model_dump_json()
        self.assertIsInstance(json_str, str)
        parsed = json.loads(json_str)
        self.assertEqual(parsed["buoy_id"], "51001")

    def test_invalid_enum_string_rejected(self):
        """Test invalid enum string raises ValidationError."""
        with self.assertRaises(ValidationError):
            BuoyTrend(
                buoy_id="51001",
                buoy_name="NW Hawaii",
                height_trend="invalid_trend",  # Invalid enum value
                height_slope=0.0,
                period_trend=TrendType.STEADY,
                period_slope=0.0,
                direction_trend=TrendType.STEADY,
                observations_count=10,
            )


class TestBuoyAnomalySchema(unittest.TestCase):
    """Test BuoyAnomaly Pydantic model."""

    def test_creation_with_valid_data(self):
        """Test BuoyAnomaly creation with valid data."""
        anomaly = BuoyAnomaly(
            buoy_id="51001",
            buoy_name="NW Hawaii",
            issue="wave_height_anomaly",
            severity=SeverityLevel.HIGH,
            details="Wave height spike detected",
            z_score=3.5,
        )
        self.assertEqual(anomaly.buoy_id, "51001")
        self.assertEqual(anomaly.severity, SeverityLevel.HIGH)
        self.assertEqual(anomaly.z_score, 3.5)

    def test_z_score_rounding_to_2_decimals(self):
        """Test z_score rounds to 2 decimal places."""
        anomaly = BuoyAnomaly(
            buoy_id="51001",
            buoy_name="NW Hawaii",
            issue="wave_height_anomaly",
            severity=SeverityLevel.HIGH,
            details="Test",
            z_score=3.123456,
        )
        self.assertEqual(anomaly.z_score, 3.12)  # Rounded to 2 decimals

    def test_severity_string_to_enum_conversion(self):
        """Test severity string converts to SeverityLevel enum."""
        anomaly = BuoyAnomaly(
            buoy_id="51001",
            buoy_name="NW Hawaii",
            issue="test",
            severity="moderate",  # String instead of enum
            details="Test",
            z_score=2.5,
        )
        self.assertEqual(anomaly.severity, SeverityLevel.MODERATE)
        self.assertIsInstance(anomaly.severity, SeverityLevel)

    def test_serialization_to_dict(self):
        """Test BuoyAnomaly serialization."""
        anomaly = BuoyAnomaly(
            buoy_id="51001",
            buoy_name="NW Hawaii",
            issue="wave_height_anomaly",
            severity=SeverityLevel.MODERATE,
            details="Test anomaly",
            z_score=2.5,
        )
        data_dict = anomaly.model_dump()
        self.assertIsInstance(data_dict, dict)
        self.assertIn("severity", data_dict)
        self.assertEqual(data_dict["severity"], "moderate")


class TestCrossValidationSchema(unittest.TestCase):
    """Test CrossValidation Pydantic model."""

    def test_creation_with_valid_data(self):
        """Test CrossValidation creation with valid data."""
        cv = CrossValidation(
            agreement_score=0.85,
            height_agreement=0.90,
            period_agreement=0.80,
            num_buoys_compared=5,
            interpretation=AgreementLevel.GOOD_AGREEMENT,
        )
        self.assertEqual(cv.agreement_score, 0.85)
        self.assertEqual(cv.height_agreement, 0.90)
        self.assertEqual(cv.interpretation, AgreementLevel.GOOD_AGREEMENT)

    def test_score_rounding_to_3_decimals(self):
        """Test agreement scores round to 3 decimal places."""
        cv = CrossValidation(
            agreement_score=0.8555555,
            height_agreement=0.9012345,
            period_agreement=0.7987654,
            num_buoys_compared=3,
            interpretation=AgreementLevel.GOOD_AGREEMENT,
        )
        self.assertEqual(cv.agreement_score, 0.856)  # Rounded to 3 decimals
        self.assertEqual(cv.height_agreement, 0.901)
        self.assertEqual(cv.period_agreement, 0.799)

    def test_score_range_validation_accepts_zero_and_one(self):
        """Test agreement scores accept boundary values 0.0 and 1.0."""
        cv = CrossValidation(
            agreement_score=0.5,
            height_agreement=0.0,
            period_agreement=1.0,
            num_buoys_compared=2,
            interpretation=AgreementLevel.MODERATE_AGREEMENT,
        )
        self.assertEqual(cv.agreement_score, 0.5)
        self.assertEqual(cv.height_agreement, 0.0)
        self.assertEqual(cv.period_agreement, 1.0)

    def test_score_range_rejects_over_1(self):
        """Test agreement scores reject values > 1.0."""
        with self.assertRaises(ValidationError):
            CrossValidation(
                agreement_score=1.5,
                height_agreement=0.9,
                period_agreement=0.8,
                num_buoys_compared=2,
                interpretation=AgreementLevel.GOOD_AGREEMENT,
            )

    def test_score_range_rejects_negative(self):
        """Test agreement scores reject negative values."""
        with self.assertRaises(ValidationError):
            CrossValidation(
                agreement_score=-0.1,
                height_agreement=0.9,
                period_agreement=0.8,
                num_buoys_compared=2,
                interpretation=AgreementLevel.POOR_AGREEMENT,
            )

    def test_serialization_to_dict(self):
        """Test CrossValidation serialization."""
        cv = CrossValidation(
            agreement_score=0.85,
            height_agreement=0.90,
            period_agreement=0.80,
            num_buoys_compared=5,
            interpretation=AgreementLevel.EXCELLENT_AGREEMENT,
        )
        data_dict = cv.model_dump()
        self.assertIsInstance(data_dict, dict)
        self.assertEqual(data_dict["interpretation"], "excellent_agreement")


class TestSummaryStatsSchema(unittest.TestCase):
    """Test SummaryStats Pydantic model."""

    def test_creation_with_valid_data(self):
        """Test SummaryStats creation with valid data."""
        stats = SummaryStats(
            avg_wave_height=5.5,
            max_wave_height=8.2,
            min_wave_height=3.1,
            avg_period=12.5,
            max_period=15.0,
            min_period=10.0,
        )
        self.assertEqual(stats.avg_wave_height, 5.5)
        self.assertEqual(stats.max_period, 15.0)

    def test_stats_rounding_to_2_decimals(self):
        """Test all stats round to 2 decimal places."""
        stats = SummaryStats(
            avg_wave_height=5.5555,
            max_wave_height=8.2222,
            min_wave_height=3.1111,
            avg_period=12.5555,
            max_period=15.0123,
            min_period=10.0987,
        )
        self.assertEqual(stats.avg_wave_height, 5.56)
        self.assertEqual(stats.max_wave_height, 8.22)
        self.assertEqual(stats.min_wave_height, 3.11)
        self.assertEqual(stats.avg_period, 12.56)
        self.assertEqual(stats.max_period, 15.01)
        self.assertEqual(stats.min_period, 10.1)

    def test_all_fields_optional_accept_none(self):
        """Test SummaryStats allows None for all fields."""
        stats = SummaryStats(
            avg_wave_height=None,
            max_wave_height=None,
            min_wave_height=None,
            avg_period=None,
            max_period=None,
            min_period=None,
        )
        self.assertIsNone(stats.avg_wave_height)
        self.assertIsNone(stats.avg_period)

    def test_partial_none_values(self):
        """Test SummaryStats with some None, some values."""
        stats = SummaryStats(avg_wave_height=5.5, max_wave_height=None, min_wave_height=3.1)
        self.assertEqual(stats.avg_wave_height, 5.5)
        self.assertIsNone(stats.max_wave_height)


class TestBuoyAnalystDataSchema(unittest.TestCase):
    """Test BuoyAnalystData Pydantic model."""

    def test_creation_with_nested_models(self):
        """Test BuoyAnalystData creation with valid nested models."""
        trend = BuoyTrend(
            buoy_id="51001",
            buoy_name="NW Hawaii",
            height_trend=TrendType.STEADY,
            height_slope=0.0,
            period_trend=TrendType.STEADY,
            period_slope=0.0,
            direction_trend=TrendType.STEADY,
            observations_count=10,
        )
        cv = CrossValidation(
            agreement_score=0.85,
            height_agreement=0.90,
            period_agreement=0.80,
            num_buoys_compared=3,
            interpretation=AgreementLevel.GOOD_AGREEMENT,
        )
        stats = SummaryStats(avg_wave_height=5.5)

        data = BuoyAnalystData(
            trends=[trend],
            cross_validation=cv,
            summary_stats=stats,
            quality_flags={"51001": QualityFlag.VALID},
        )
        self.assertEqual(len(data.trends), 1)
        self.assertEqual(data.trends[0].buoy_id, "51001")
        self.assertIsInstance(data.cross_validation, CrossValidation)
        self.assertEqual(data.quality_flags["51001"], QualityFlag.VALID)

    def test_default_empty_lists(self):
        """Test BuoyAnalystData uses default empty lists."""
        cv = CrossValidation(
            agreement_score=0.85,
            height_agreement=0.90,
            period_agreement=0.80,
            num_buoys_compared=3,
            interpretation=AgreementLevel.GOOD_AGREEMENT,
        )
        stats = SummaryStats()

        data = BuoyAnalystData(cross_validation=cv, summary_stats=stats)
        self.assertEqual(len(data.trends), 0)
        self.assertEqual(len(data.anomalies), 0)
        self.assertEqual(len(data.quality_flags), 0)

    def test_serialization_with_nested_models(self):
        """Test BuoyAnalystData serialization with nested models."""
        cv = CrossValidation(
            agreement_score=0.85,
            height_agreement=0.90,
            period_agreement=0.80,
            num_buoys_compared=3,
            interpretation=AgreementLevel.GOOD_AGREEMENT,
        )
        stats = SummaryStats(avg_wave_height=5.5)

        data = BuoyAnalystData(cross_validation=cv, summary_stats=stats)
        data_dict = data.model_dump()
        self.assertIsInstance(data_dict, dict)
        self.assertIn("cross_validation", data_dict)
        self.assertIn("summary_stats", data_dict)


class TestBuoyAnalystOutputSchema(unittest.TestCase):
    """Test BuoyAnalystOutput Pydantic model."""

    def test_creation_with_valid_data(self):
        """Test BuoyAnalystOutput creation with valid data."""
        cv = CrossValidation(
            agreement_score=0.85,
            height_agreement=0.90,
            period_agreement=0.80,
            num_buoys_compared=3,
            interpretation=AgreementLevel.GOOD_AGREEMENT,
        )
        stats = SummaryStats(avg_wave_height=5.5)
        data = BuoyAnalystData(cross_validation=cv, summary_stats=stats)

        output = BuoyAnalystOutput(
            confidence=0.85, data=data, narrative="Test narrative content here."
        )
        self.assertEqual(output.confidence, 0.85)
        self.assertIsInstance(output.data, BuoyAnalystData)
        self.assertEqual(output.narrative, "Test narrative content here.")

    def test_confidence_rounding_to_3_decimals(self):
        """Test confidence rounds to 3 decimal places."""
        cv = CrossValidation(
            agreement_score=0.85,
            height_agreement=0.90,
            period_agreement=0.80,
            num_buoys_compared=3,
            interpretation=AgreementLevel.GOOD_AGREEMENT,
        )
        stats = SummaryStats()
        data = BuoyAnalystData(cross_validation=cv, summary_stats=stats)

        output = BuoyAnalystOutput(confidence=0.8555555, data=data, narrative="Test")
        self.assertEqual(output.confidence, 0.856)  # Rounded to 3 decimals

    def test_confidence_range_rejects_over_1(self):
        """Test confidence rejects values > 1.0."""
        cv = CrossValidation(
            agreement_score=0.85,
            height_agreement=0.90,
            period_agreement=0.80,
            num_buoys_compared=3,
            interpretation=AgreementLevel.GOOD_AGREEMENT,
        )
        stats = SummaryStats()
        data = BuoyAnalystData(cross_validation=cv, summary_stats=stats)

        with self.assertRaises(ValidationError):
            BuoyAnalystOutput(confidence=1.5, data=data, narrative="Test")

    def test_narrative_min_length_rejects_empty(self):
        """Test narrative must have min_length=1."""
        cv = CrossValidation(
            agreement_score=0.85,
            height_agreement=0.90,
            period_agreement=0.80,
            num_buoys_compared=3,
            interpretation=AgreementLevel.GOOD_AGREEMENT,
        )
        stats = SummaryStats()
        data = BuoyAnalystData(cross_validation=cv, summary_stats=stats)

        with self.assertRaises(ValidationError):
            BuoyAnalystOutput(confidence=0.85, data=data, narrative="")

    def test_serialization_to_dict_and_json(self):
        """Test BuoyAnalystOutput can serialize to dict and JSON."""
        cv = CrossValidation(
            agreement_score=0.85,
            height_agreement=0.90,
            period_agreement=0.80,
            num_buoys_compared=3,
            interpretation=AgreementLevel.GOOD_AGREEMENT,
        )
        stats = SummaryStats(avg_wave_height=5.5)
        data = BuoyAnalystData(cross_validation=cv, summary_stats=stats)

        output = BuoyAnalystOutput(confidence=0.85, data=data, narrative="Test narrative")

        # Test model_dump
        data_dict = output.model_dump()
        self.assertIsInstance(data_dict, dict)
        self.assertIn("confidence", data_dict)
        self.assertIn("data", data_dict)
        self.assertIn("narrative", data_dict)

        # Test model_dump_json
        json_str = output.model_dump_json()
        self.assertIsInstance(json_str, str)
        parsed = json.loads(json_str)
        self.assertEqual(parsed["confidence"], 0.85)


# =============================================================================
# PRESSURE ANALYST TESTS
# =============================================================================


class TestFetchWindowSchema(unittest.TestCase):
    """Test FetchWindow Pydantic model."""

    def test_creation_with_valid_data(self):
        """Test FetchWindow creation with valid data."""
        fetch = FetchWindow(
            direction="NNE",
            distance_nm=1500.5,
            duration_hrs=24.0,
            fetch_length_nm=800.25,
            quality=FetchQuality.STRONG,
        )
        self.assertEqual(fetch.direction, "NNE")
        self.assertEqual(fetch.distance_nm, 1500.5)
        self.assertEqual(fetch.quality, FetchQuality.STRONG)

    def test_metrics_rounding_to_1_decimal(self):
        """Test fetch metrics round to 1 decimal place."""
        fetch = FetchWindow(
            direction="NNE",
            distance_nm=1500.5555,
            duration_hrs=24.7777,
            fetch_length_nm=800.2222,
            quality=FetchQuality.MODERATE,
        )
        self.assertEqual(fetch.distance_nm, 1500.6)  # Rounded to 1 decimal
        self.assertEqual(fetch.duration_hrs, 24.8)
        self.assertEqual(fetch.fetch_length_nm, 800.2)

    def test_negative_distance_rejected(self):
        """Test negative distance values are rejected."""
        with self.assertRaises(ValidationError):
            FetchWindow(
                direction="NNE",
                distance_nm=-100.0,  # Invalid: negative
                duration_hrs=24.0,
                fetch_length_nm=800.0,
                quality=FetchQuality.STRONG,
            )

    def test_serialization_to_dict(self):
        """Test FetchWindow serialization."""
        fetch = FetchWindow(
            direction="NNE",
            distance_nm=1500.5,
            duration_hrs=24.0,
            fetch_length_nm=800.0,
            quality=FetchQuality.STRONG,
        )
        data_dict = fetch.model_dump()
        self.assertIsInstance(data_dict, dict)
        self.assertEqual(data_dict["quality"], "strong")


class TestWeatherSystemSchema(unittest.TestCase):
    """Test WeatherSystem Pydantic model."""

    def test_creation_with_valid_data(self):
        """Test WeatherSystem creation with valid data."""
        system = WeatherSystem(
            type=SystemType.LOW_PRESSURE,
            location="45N 160W",
            location_lat=45.0,
            location_lon=-160.0,
            pressure_mb=995,
            wind_speed_kt=35,
            movement="SE at 25kt",
            intensification=IntensificationTrend.STRENGTHENING,
        )
        self.assertEqual(system.type, SystemType.LOW_PRESSURE)
        self.assertEqual(system.location_lat, 45.0)
        self.assertEqual(system.pressure_mb, 995)

    def test_creation_with_nested_fetch_window(self):
        """Test WeatherSystem with nested FetchWindow."""
        fetch = FetchWindow(
            direction="NNE",
            distance_nm=1500.0,
            duration_hrs=24.0,
            fetch_length_nm=800.0,
            quality=FetchQuality.STRONG,
        )
        system = WeatherSystem(
            type=SystemType.LOW_PRESSURE,
            location="45N 160W",
            location_lat=45.0,
            location_lon=-160.0,
            movement="SE at 25kt",
            intensification=IntensificationTrend.STRENGTHENING,
            fetch=fetch,
        )
        self.assertIsInstance(system.fetch, FetchWindow)
        self.assertEqual(system.fetch.direction, "NNE")

    def test_latitude_range_validation(self):
        """Test latitude must be between -90 and 90."""
        # Valid latitude
        system = WeatherSystem(
            type=SystemType.LOW_PRESSURE,
            location="45N 160W",
            location_lat=45.0,
            location_lon=-160.0,
            movement="SE at 25kt",
            intensification=IntensificationTrend.STEADY,
        )
        self.assertEqual(system.location_lat, 45.0)

        # Invalid latitude > 90
        with self.assertRaises(ValidationError):
            WeatherSystem(
                type=SystemType.LOW_PRESSURE,
                location="100N 160W",
                location_lat=100.0,
                location_lon=-160.0,
                movement="SE at 25kt",
                intensification=IntensificationTrend.STEADY,
            )

    def test_longitude_range_validation(self):
        """Test longitude must be between -180 and 180."""
        # Invalid longitude > 180
        with self.assertRaises(ValidationError):
            WeatherSystem(
                type=SystemType.LOW_PRESSURE,
                location="45N 200W",
                location_lat=45.0,
                location_lon=-200.0,
                movement="SE at 25kt",
                intensification=IntensificationTrend.STEADY,
            )

    def test_timestamp_validation_valid_iso(self):
        """Test ISO timestamp validation accepts valid format."""
        system = WeatherSystem(
            type=SystemType.LOW_PRESSURE,
            location="45N 160W",
            location_lat=45.0,
            location_lon=-160.0,
            movement="SE at 25kt",
            intensification=IntensificationTrend.STEADY,
            generation_time="2025-10-09T12:00:00Z",
        )
        self.assertEqual(system.generation_time, "2025-10-09T12:00:00Z")

    def test_timestamp_validation_rejects_invalid(self):
        """Test ISO timestamp validation rejects invalid format."""
        with self.assertRaises(ValidationError):
            WeatherSystem(
                type=SystemType.LOW_PRESSURE,
                location="45N 160W",
                location_lat=45.0,
                location_lon=-160.0,
                movement="SE at 25kt",
                intensification=IntensificationTrend.STEADY,
                generation_time="not-a-timestamp",
            )

    def test_serialization_to_dict(self):
        """Test WeatherSystem serialization."""
        system = WeatherSystem(
            type=SystemType.HIGH_PRESSURE,
            location="45N 160W",
            location_lat=45.0,
            location_lon=-160.0,
            movement="SE at 25kt",
            intensification=IntensificationTrend.WEAKENING,
        )
        data_dict = system.model_dump()
        self.assertIsInstance(data_dict, dict)
        self.assertEqual(data_dict["type"], "high_pressure")
        self.assertEqual(data_dict["intensification"], "weakening")


class TestPredictedSwellSchema(unittest.TestCase):
    """Test PredictedSwell Pydantic model."""

    def test_creation_with_valid_data(self):
        """Test PredictedSwell creation with valid data."""
        swell = PredictedSwell(
            source_system="low_45N_160W",
            source_lat=45.0,
            source_lon=-160.0,
            direction="NNE",
            direction_degrees=315,
            arrival_time="Thu-Fri",
            estimated_height="7-9ft",
            estimated_period="13-15s",
            confidence=0.85,
        )
        self.assertEqual(swell.source_system, "low_45N_160W")
        self.assertEqual(swell.direction_degrees, 315)
        self.assertEqual(swell.confidence, 0.85)

    def test_confidence_rounding_to_2_decimals(self):
        """Test confidence rounds to 2 decimal places."""
        swell = PredictedSwell(
            source_system="low_45N_160W",
            source_lat=45.0,
            source_lon=-160.0,
            direction="NNE",
            arrival_time="Thu-Fri",
            estimated_height="7-9ft",
            estimated_period="13-15s",
            confidence=0.8555555,
        )
        self.assertEqual(swell.confidence, 0.86)  # Rounded to 2 decimals

    def test_physics_metrics_rounding_to_1_decimal(self):
        """Test physics metrics round to 1 decimal place."""
        swell = PredictedSwell(
            source_system="low_45N_160W",
            source_lat=45.0,
            source_lon=-160.0,
            direction="NNE",
            arrival_time="Thu-Fri",
            estimated_height="7-9ft",
            estimated_period="13-15s",
            confidence=0.85,
            travel_time_hrs=48.7777,
            distance_nm=1200.5555,
            group_velocity_knots=25.3333,
            fetch_duration_hrs=24.8888,
            fetch_length_nm=800.1234,
        )
        self.assertEqual(swell.travel_time_hrs, 48.8)
        self.assertEqual(swell.distance_nm, 1200.6)
        self.assertEqual(swell.group_velocity_knots, 25.3)
        self.assertEqual(swell.fetch_duration_hrs, 24.9)
        self.assertEqual(swell.fetch_length_nm, 800.1)

    def test_direction_degrees_validation(self):
        """Test direction_degrees must be 0-360."""
        # Valid direction
        swell = PredictedSwell(
            source_system="low_45N_160W",
            source_lat=45.0,
            source_lon=-160.0,
            direction="NNE",
            direction_degrees=315,
            arrival_time="Thu-Fri",
            estimated_height="7-9ft",
            estimated_period="13-15s",
            confidence=0.85,
        )
        self.assertEqual(swell.direction_degrees, 315)

        # Invalid direction > 360
        with self.assertRaises(ValidationError):
            PredictedSwell(
                source_system="low_45N_160W",
                source_lat=45.0,
                source_lon=-160.0,
                direction="NNE",
                direction_degrees=400,
                arrival_time="Thu-Fri",
                estimated_height="7-9ft",
                estimated_period="13-15s",
                confidence=0.85,
            )

    def test_serialization_to_dict(self):
        """Test PredictedSwell serialization."""
        swell = PredictedSwell(
            source_system="low_45N_160W",
            source_lat=45.0,
            source_lon=-160.0,
            direction="NNE",
            arrival_time="Thu-Fri",
            estimated_height="7-9ft",
            estimated_period="13-15s",
            confidence=0.85,
            fetch_quality=FetchQuality.STRONG,
        )
        data_dict = swell.model_dump()
        self.assertIsInstance(data_dict, dict)
        self.assertEqual(data_dict["fetch_quality"], "strong")


class TestFrontalBoundarySchema(unittest.TestCase):
    """Test FrontalBoundary Pydantic model."""

    def test_creation_with_valid_data(self):
        """Test FrontalBoundary creation with valid data."""
        front = FrontalBoundary(
            type=FrontType.COLD_FRONT, location="approaching from NW", timing="2025-10-10T06:00:00Z"
        )
        self.assertEqual(front.type, FrontType.COLD_FRONT)
        self.assertEqual(front.location, "approaching from NW")

    def test_serialization_to_dict(self):
        """Test FrontalBoundary serialization."""
        front = FrontalBoundary(
            type=FrontType.WARM_FRONT, location="passing to the north", timing="Friday morning"
        )
        data_dict = front.model_dump()
        self.assertIsInstance(data_dict, dict)
        self.assertEqual(data_dict["type"], "warm_front")


class TestAnalysisSummarySchema(unittest.TestCase):
    """Test AnalysisSummary Pydantic model."""

    def test_creation_with_valid_data(self):
        """Test AnalysisSummary creation with valid data."""
        summary = AnalysisSummary(
            num_low_pressure=3, num_high_pressure=2, num_predicted_swells=4, region="North Pacific"
        )
        self.assertEqual(summary.num_low_pressure, 3)
        self.assertEqual(summary.region, "North Pacific")

    def test_negative_counts_rejected(self):
        """Test negative counts are rejected."""
        with self.assertRaises(ValidationError):
            AnalysisSummary(
                num_low_pressure=-1,
                num_high_pressure=2,
                num_predicted_swells=4,
                region="North Pacific",
            )


class TestPressureAnalystDataSchema(unittest.TestCase):
    """Test PressureAnalystData Pydantic model."""

    def test_creation_with_nested_models(self):
        """Test PressureAnalystData creation with valid nested models."""
        system = WeatherSystem(
            type=SystemType.LOW_PRESSURE,
            location="45N 160W",
            location_lat=45.0,
            location_lon=-160.0,
            movement="SE at 25kt",
            intensification=IntensificationTrend.STRENGTHENING,
        )
        swell = PredictedSwell(
            source_system="low_45N_160W",
            source_lat=45.0,
            source_lon=-160.0,
            direction="NNE",
            arrival_time="Thu-Fri",
            estimated_height="7-9ft",
            estimated_period="13-15s",
            confidence=0.85,
        )
        summary = AnalysisSummary(
            num_low_pressure=1, num_high_pressure=0, num_predicted_swells=1, region="North Pacific"
        )

        data = PressureAnalystData(
            systems=[system], predicted_swells=[swell], analysis_summary=summary
        )
        self.assertEqual(len(data.systems), 1)
        self.assertEqual(len(data.predicted_swells), 1)
        self.assertIsInstance(data.analysis_summary, AnalysisSummary)

    def test_default_empty_lists(self):
        """Test PressureAnalystData uses default empty lists."""
        summary = AnalysisSummary(
            num_low_pressure=0, num_high_pressure=0, num_predicted_swells=0, region="North Pacific"
        )

        data = PressureAnalystData(analysis_summary=summary)
        self.assertEqual(len(data.systems), 0)
        self.assertEqual(len(data.predicted_swells), 0)
        self.assertEqual(len(data.frontal_boundaries), 0)


class TestPressureAnalystOutputSchema(unittest.TestCase):
    """Test PressureAnalystOutput Pydantic model."""

    def test_creation_with_valid_data(self):
        """Test PressureAnalystOutput creation with valid data."""
        summary = AnalysisSummary(
            num_low_pressure=1, num_high_pressure=0, num_predicted_swells=1, region="North Pacific"
        )
        data = PressureAnalystData(analysis_summary=summary)

        output = PressureAnalystOutput(
            confidence=0.85, data=data, narrative="Test narrative content here."
        )
        self.assertEqual(output.confidence, 0.85)
        self.assertIsInstance(output.data, PressureAnalystData)

    def test_confidence_rounding_to_3_decimals(self):
        """Test confidence rounds to 3 decimal places."""
        summary = AnalysisSummary(
            num_low_pressure=0, num_high_pressure=0, num_predicted_swells=0, region="North Pacific"
        )
        data = PressureAnalystData(analysis_summary=summary)

        output = PressureAnalystOutput(confidence=0.8555555, data=data, narrative="Test")
        self.assertEqual(output.confidence, 0.856)


# =============================================================================
# SENIOR FORECASTER TESTS
# =============================================================================


class TestContradictionSchema(unittest.TestCase):
    """Test Contradiction Pydantic model."""

    def test_creation_with_valid_data(self):
        """Test Contradiction creation with valid data."""
        contra = Contradiction(
            issue="Buoy shows decreasing height, pressure predicts increasing swell",
            resolution="Buoy may be in shadow zone; trust pressure prediction",
            impact=ImpactLevel.HIGH,
            buoy_confidence=0.75,
            pressure_confidence=0.90,
        )
        self.assertEqual(contra.impact, ImpactLevel.HIGH)
        self.assertEqual(contra.buoy_confidence, 0.75)

    def test_confidences_rounding_to_2_decimals(self):
        """Test confidence values round to 2 decimal places."""
        contra = Contradiction(
            issue="Test issue",
            resolution="Test resolution",
            impact=ImpactLevel.MEDIUM,
            buoy_confidence=0.755555,
            pressure_confidence=0.911111,
            swell_confidence=0.833333,
        )
        self.assertEqual(contra.buoy_confidence, 0.76)
        self.assertEqual(contra.pressure_confidence, 0.91)
        self.assertEqual(contra.swell_confidence, 0.83)

    def test_confidence_range_validation(self):
        """Test confidence values must be 0.0-1.0."""
        with self.assertRaises(ValidationError):
            Contradiction(
                issue="Test", resolution="Test", impact=ImpactLevel.HIGH, buoy_confidence=1.5
            )

    def test_optional_fields_accept_none(self):
        """Test Contradiction allows None for optional confidence fields."""
        contra = Contradiction(
            issue="Test issue",
            resolution="Test resolution",
            impact=ImpactLevel.LOW,
            buoy_confidence=None,
            pressure_confidence=None,
            swell_confidence=None,
            timing=None,
        )
        self.assertIsNone(contra.buoy_confidence)
        self.assertIsNone(contra.timing)


class TestSynthesisSchema(unittest.TestCase):
    """Test Synthesis Pydantic model."""

    def test_creation_with_valid_data(self):
        """Test Synthesis creation with valid data."""
        contra = Contradiction(issue="Test", resolution="Test", impact=ImpactLevel.LOW)
        synth = Synthesis(
            specialist_agreement=0.85,
            contradictions=[contra],
            key_findings=["Finding 1", "Finding 2"],
        )
        self.assertEqual(synth.specialist_agreement, 0.85)
        self.assertEqual(len(synth.contradictions), 1)
        self.assertEqual(len(synth.key_findings), 2)

    def test_agreement_rounding_to_3_decimals(self):
        """Test specialist_agreement rounds to 3 decimal places."""
        synth = Synthesis(specialist_agreement=0.8555555, contradictions=[], key_findings=[])
        self.assertEqual(synth.specialist_agreement, 0.856)

    def test_agreement_range_validation(self):
        """Test specialist_agreement must be 0.0-1.0."""
        with self.assertRaises(ValidationError):
            Synthesis(specialist_agreement=1.5, contradictions=[], key_findings=[])

    def test_default_empty_lists(self):
        """Test Synthesis uses default empty lists."""
        synth = Synthesis(specialist_agreement=0.85)
        self.assertEqual(len(synth.contradictions), 0)
        self.assertEqual(len(synth.key_findings), 0)


class TestShoreForecastSchema(unittest.TestCase):
    """Test ShoreForecast Pydantic model."""

    def test_creation_with_valid_data(self):
        """Test ShoreForecast creation with valid data."""
        forecast = ShoreForecast(
            size_range="6-8ft",
            conditions="clean",
            timing="building Thursday afternoon",
            confidence=0.85,
        )
        self.assertEqual(forecast.size_range, "6-8ft")
        self.assertEqual(forecast.conditions, "clean")
        self.assertEqual(forecast.confidence, 0.85)

    def test_confidence_rounding_to_2_decimals(self):
        """Test confidence rounds to 2 decimal places."""
        forecast = ShoreForecast(
            size_range="6-8ft", conditions="clean", timing="Thursday", confidence=0.8555555
        )
        self.assertEqual(forecast.confidence, 0.86)

    def test_confidence_range_validation(self):
        """Test confidence must be 0.0-1.0."""
        with self.assertRaises(ValidationError):
            ShoreForecast(size_range="6-8ft", conditions="clean", timing="Thursday", confidence=1.5)


class TestSwellBreakdownSchema(unittest.TestCase):
    """Test SwellBreakdown Pydantic model."""

    def test_creation_with_valid_data(self):
        """Test SwellBreakdown creation with valid data."""
        swell = SwellBreakdown(
            direction="NNE",
            period="13-15s",
            height="7-9ft",
            timing="Thu-Fri",
            confidence=0.85,
            source="low_45N_160W",
            has_pressure_support=True,
            has_buoy_confirmation=True,
            buoy_height="2.5m",
            buoy_period="14s",
        )
        self.assertEqual(swell.direction, "NNE")
        self.assertEqual(swell.confidence, 0.85)
        self.assertTrue(swell.has_pressure_support)
        self.assertTrue(swell.has_buoy_confirmation)

    def test_confidence_rounding_to_2_decimals(self):
        """Test confidence rounds to 2 decimal places."""
        swell = SwellBreakdown(
            direction="NNE",
            period="13-15s",
            height="7-9ft",
            timing="Thu-Fri",
            confidence=0.8555555,
            source="low_45N_160W",
            has_pressure_support=True,
            has_buoy_confirmation=False,
        )
        self.assertEqual(swell.confidence, 0.86)

    def test_optional_buoy_fields_accept_none(self):
        """Test SwellBreakdown allows None for optional buoy fields."""
        swell = SwellBreakdown(
            direction="NNE",
            period="13-15s",
            height="7-9ft",
            timing="Thu-Fri",
            confidence=0.85,
            source="low_45N_160W",
            has_pressure_support=True,
            has_buoy_confirmation=False,
            buoy_height=None,
            buoy_period=None,
        )
        self.assertIsNone(swell.buoy_height)
        self.assertIsNone(swell.buoy_period)


class TestSeniorForecasterDataSchema(unittest.TestCase):
    """Test SeniorForecasterData Pydantic model."""

    def test_creation_with_nested_models(self):
        """Test SeniorForecasterData creation with valid nested models."""
        synth = Synthesis(specialist_agreement=0.85)
        shore_forecast = ShoreForecast(
            size_range="6-8ft", conditions="clean", timing="Thursday", confidence=0.85
        )
        swell = SwellBreakdown(
            direction="NNE",
            period="13-15s",
            height="7-9ft",
            timing="Thu-Fri",
            confidence=0.85,
            source="low_45N_160W",
            has_pressure_support=True,
            has_buoy_confirmation=True,
        )

        data = SeniorForecasterData(
            synthesis=synth,
            shore_forecasts={"north_shore": shore_forecast},
            swell_breakdown=[swell],
        )
        self.assertIsInstance(data.synthesis, Synthesis)
        self.assertEqual(len(data.shore_forecasts), 1)
        self.assertEqual(len(data.swell_breakdown), 1)

    def test_default_empty_collections(self):
        """Test SeniorForecasterData uses default empty collections."""
        synth = Synthesis(specialist_agreement=0.85)

        data = SeniorForecasterData(synthesis=synth)
        self.assertEqual(len(data.shore_forecasts), 0)
        self.assertEqual(len(data.swell_breakdown), 0)


class TestSeniorForecasterInputSchema(unittest.TestCase):
    """Test SeniorForecasterInput Pydantic model."""

    def test_creation_with_valid_data(self):
        """Test SeniorForecasterInput creation with valid data."""
        input_data = SeniorForecasterInput(
            buoy_analysis=None,
            pressure_analysis=None,
            swell_events=[],
            shore_data={},
            seasonal_context={"season": "winter"},
            metadata={"forecast_date": "2025-10-09"},
        )
        self.assertIsNone(input_data.buoy_analysis)
        self.assertEqual(input_data.seasonal_context["season"], "winter")

    def test_default_empty_collections(self):
        """Test SeniorForecasterInput uses default empty collections."""
        input_data = SeniorForecasterInput()
        self.assertIsNone(input_data.buoy_analysis)
        self.assertEqual(len(input_data.swell_events), 0)
        self.assertEqual(len(input_data.shore_data), 0)


class TestSeniorForecasterOutputSchema(unittest.TestCase):
    """Test SeniorForecasterOutput Pydantic model."""

    def test_creation_with_valid_data(self):
        """Test SeniorForecasterOutput creation with valid data."""
        synth = Synthesis(specialist_agreement=0.85)
        data = SeniorForecasterData(synthesis=synth)

        output = SeniorForecasterOutput(
            confidence=0.85, data=data, narrative="Test narrative in Pat Caldwell style."
        )
        self.assertEqual(output.confidence, 0.85)
        self.assertIsInstance(output.data, SeniorForecasterData)

    def test_confidence_rounding_to_3_decimals(self):
        """Test confidence rounds to 3 decimal places."""
        synth = Synthesis(specialist_agreement=0.85)
        data = SeniorForecasterData(synthesis=synth)

        output = SeniorForecasterOutput(confidence=0.8555555, data=data, narrative="Test")
        self.assertEqual(output.confidence, 0.856)

    def test_confidence_range_validation(self):
        """Test confidence must be 0.0-1.0."""
        synth = Synthesis(specialist_agreement=0.85)
        data = SeniorForecasterData(synthesis=synth)

        with self.assertRaises(ValidationError):
            SeniorForecasterOutput(confidence=1.5, data=data, narrative="Test")

    def test_narrative_min_length_validation(self):
        """Test narrative must have min_length=1."""
        synth = Synthesis(specialist_agreement=0.85)
        data = SeniorForecasterData(synthesis=synth)

        with self.assertRaises(ValidationError):
            SeniorForecasterOutput(confidence=0.85, data=data, narrative="")


# =============================================================================
# UTILITY FUNCTION TESTS
# =============================================================================


class TestUtilityFunctions(unittest.TestCase):
    """Test utility validation functions."""

    def test_validate_buoy_output_valid(self):
        """Test validate_buoy_output with valid data."""
        cv = CrossValidation(
            agreement_score=0.85,
            height_agreement=0.90,
            period_agreement=0.80,
            num_buoys_compared=3,
            interpretation=AgreementLevel.GOOD_AGREEMENT,
        )
        stats = SummaryStats()
        data = BuoyAnalystData(cross_validation=cv, summary_stats=stats)

        output_dict = {
            "confidence": 0.85,
            "data": data.model_dump(),
            "narrative": "Test narrative",
            "metadata": {},
        }

        result = validate_buoy_output(output_dict)
        self.assertIsInstance(result, BuoyAnalystOutput)
        self.assertEqual(result.confidence, 0.85)

    def test_validate_buoy_output_invalid(self):
        """Test validate_buoy_output with invalid data raises ValidationError."""
        invalid_dict = {"confidence": 1.5, "data": {}, "narrative": "Test"}  # Invalid: > 1.0

        with self.assertRaises(ValidationError):
            validate_buoy_output(invalid_dict)

    def test_validate_pressure_output_valid(self):
        """Test validate_pressure_output with valid data."""
        summary = AnalysisSummary(
            num_low_pressure=0, num_high_pressure=0, num_predicted_swells=0, region="North Pacific"
        )
        data = PressureAnalystData(analysis_summary=summary)

        output_dict = {
            "confidence": 0.85,
            "data": data.model_dump(),
            "narrative": "Test narrative",
            "metadata": {},
        }

        result = validate_pressure_output(output_dict)
        self.assertIsInstance(result, PressureAnalystOutput)
        self.assertEqual(result.confidence, 0.85)

    def test_validate_pressure_output_invalid(self):
        """Test validate_pressure_output with invalid data raises ValidationError."""
        invalid_dict = {"confidence": -0.5, "data": {}, "narrative": "Test"}  # Invalid: < 0.0

        with self.assertRaises(ValidationError):
            validate_pressure_output(invalid_dict)

    def test_validate_senior_output_valid(self):
        """Test validate_senior_output with valid data."""
        synth = Synthesis(specialist_agreement=0.85)
        data = SeniorForecasterData(synthesis=synth)

        output_dict = {
            "confidence": 0.85,
            "data": data.model_dump(),
            "narrative": "Test narrative",
            "metadata": {},
        }

        result = validate_senior_output(output_dict)
        self.assertIsInstance(result, SeniorForecasterOutput)
        self.assertEqual(result.confidence, 0.85)

    def test_validate_senior_output_invalid(self):
        """Test validate_senior_output with invalid data raises ValidationError."""
        invalid_dict = {
            "confidence": 0.85,
            "data": {},
            "narrative": "",  # Invalid: empty string with min_length=1
        }

        with self.assertRaises(ValidationError):
            validate_senior_output(invalid_dict)


if __name__ == "__main__":
    unittest.main()
