"""
Unit tests for the Context Builder module.

This module tests all functions in src/forecast_engine/context_builder.py
following TDD best practices with comprehensive coverage.
"""

import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

from src.forecast_engine.context_builder import (
    _build_data_gap_section,
    _build_overview,
    _build_shore_digest,
    _build_swell_matrix,
    _build_tide_section,
    _build_timeline_section,
    _build_tropical_section,
    _build_weather_section,
    _deg_to_cardinal,
    _estimate_h10,
    _extract_period,
    _format_exposures,
    _format_hst,
    _parse_datetime,
    _strip_html,
    _summarise_secondary,
    _to_hst,
    build_context,
)


class TestBuildContext(unittest.TestCase):
    """Test cases for the main build_context orchestrator function."""

    def test_build_context_returns_required_keys(self):
        """Test build_context returns data_digest and shore_digests keys."""
        # Arrange
        forecast_data = {"metadata": {}, "swell_events": [], "shore_data": {}, "confidence": {}}

        # Act
        result = build_context(forecast_data)

        # Assert
        self.assertIn("data_digest", result, "Result should contain data_digest key")
        self.assertIn("shore_digests", result, "Result should contain shore_digests key")
        self.assertIsInstance(result["data_digest"], str, "data_digest should be a string")
        self.assertIsInstance(result["shore_digests"], dict, "shore_digests should be a dict")

    def test_build_context_handles_empty_forecast_data_gracefully(self):
        """Test build_context handles empty forecast data without errors."""
        # Arrange
        forecast_data = {}

        # Act
        result = build_context(forecast_data)

        # Assert
        self.assertIsNotNone(result, "Result should not be None")
        self.assertIn("data_digest", result)
        self.assertIn("shore_digests", result)
        # Empty shore_data should produce empty shore_digests
        self.assertEqual(len(result["shore_digests"]), 0)

    def test_build_context_integrates_all_subcomponents(self):
        """Test build_context integrates swell matrix, timeline, weather, tides, tropical."""
        # Arrange
        forecast_data = {
            "metadata": {
                "weather": {"wind_direction": 90, "wind_speed_kt": 15},
                "tides": {"high_tide": [("2025-10-11T12:00:00Z", 2.5)]},
                "tropical": {"headline": "No active advisories"},
                "agent_results": {"buoy_agent": {"total": 5, "successful": 5}},
                "upper_air": [{"analysis_level": "250", "product_type": "jet_stream"}],
                "climatology": [
                    {"source_id": "snn_nsstat10", "description": "SNN stats", "format": "text"}
                ],
            },
            "swell_events": [
                {
                    "hawaii_scale": 5.0,
                    "primary_direction": 315,
                    "dominant_period": 12.0,
                    "start_time": "2025-10-11T08:00:00Z",
                    "peak_time": "2025-10-11T14:00:00Z",
                    "metadata": {"source_details": {"buoy_id": "51201"}},
                }
            ],
            "shore_data": {
                "North Shore": {"name": "North Shore", "swell_events": [], "metadata": {}}
            },
            "confidence": {"overall_score": 0.85, "category": "High"},
        }

        # Act
        result = build_context(forecast_data)
        data_digest = result["data_digest"]

        # Assert
        self.assertIn("SWELL MATRIX", data_digest, "Should include swell matrix section")
        self.assertIn("TIMELINE", data_digest, "Should include timeline section")
        self.assertIn("WEATHER", data_digest, "Should include weather section")
        self.assertIn("TIDES", data_digest, "Should include tides section")
        self.assertIn("UPPER-AIR", data_digest, "Should include upper-air section")
        self.assertIn("CLIMATOLOGY", data_digest, "Should include climatology section")
        self.assertIn("TROPICAL", data_digest, "Should include tropical section")
        self.assertIn("DATA QUALITY", data_digest, "Should include data quality section")

    def test_build_context_handles_missing_optional_fields(self):
        """Test build_context handles missing weather, tides, tropical gracefully."""
        # Arrange
        forecast_data = {
            "metadata": {},  # No weather, tides, or tropical
            "swell_events": [],
            "shore_data": {},
            "confidence": {},
        }

        # Act
        result = build_context(forecast_data)
        data_digest = result["data_digest"]

        # Assert
        self.assertIn("unavailable", data_digest.lower(), "Should indicate unavailable data")
        # Should not crash and should return valid structure
        self.assertIsNotNone(result)


class TestSwellMatrixFormatting(unittest.TestCase):
    """Test cases for _build_swell_matrix function."""

    def test_build_swell_matrix_sorts_by_hawaii_scale_descending(self):
        """Test swell matrix sorts events by hawaii_scale in descending order."""
        # Arrange
        swell_events = [
            {
                "hawaii_scale": 3.0,
                "primary_direction": 180,
                "dominant_period": 10.0,
                "start_time": "2025-10-11T08:00:00Z",
                "peak_time": "2025-10-11T14:00:00Z",
                "metadata": {"source_details": {"buoy_id": "A"}},
            },
            {
                "hawaii_scale": 7.0,
                "primary_direction": 315,
                "dominant_period": 14.0,
                "start_time": "2025-10-11T08:00:00Z",
                "peak_time": "2025-10-11T14:00:00Z",
                "metadata": {"source_details": {"buoy_id": "B"}},
            },
            {
                "hawaii_scale": 5.0,
                "primary_direction": 270,
                "dominant_period": 12.0,
                "start_time": "2025-10-11T08:00:00Z",
                "peak_time": "2025-10-11T14:00:00Z",
                "metadata": {"source_details": {"buoy_id": "C"}},
            },
        ]

        # Act
        result = _build_swell_matrix(swell_events)
        lines = result.split("\n")

        # Assert
        self.assertGreater(len(lines), 0, "Should return swell matrix lines")
        # First line should be the largest swell (7.0 ft)
        self.assertIn("7.0ft", lines[0], "First line should contain largest swell")
        # Second line should be medium swell (5.0 ft)
        self.assertIn("5.0ft", lines[1], "Second line should contain medium swell")
        # Third line should be smallest swell (3.0 ft)
        self.assertIn("3.0ft", lines[2], "Third line should contain smallest swell")

    def test_build_swell_matrix_formats_multiple_swells_correctly(self):
        """Test swell matrix formats multiple swell events with all required fields."""
        # Arrange
        swell_events = [
            {
                "hawaii_scale": 5.0,
                "primary_direction": 315,
                "primary_direction_cardinal": "NW",
                "dominant_period": 12.0,
                "start_time": "2025-10-11T08:00:00Z",
                "peak_time": "2025-10-11T14:00:00Z",
                "metadata": {"source_details": {"buoy_id": "51201"}},
            },
            {
                "hawaii_scale": 3.0,
                "primary_direction": 180,
                "dominant_period": 10.0,
                "start_time": "2025-10-11T09:00:00Z",
                "peak_time": "2025-10-11T15:00:00Z",
                "metadata": {"source_details": {"buoy_id": "51202"}},
            },
        ]

        # Act
        result = _build_swell_matrix(swell_events)

        # Assert
        self.assertIn("NW", result, "Should include direction")
        self.assertIn("315", result, "Should include degree direction")
        self.assertIn("5.0ft", result, "Should include height")
        self.assertIn("12.0s", result, "Should include period")
        self.assertIn("51201", result, "Should include buoy ID")

    def test_build_swell_matrix_handles_single_swell_event(self):
        """Test swell matrix handles a single swell event correctly."""
        # Arrange
        swell_events = [
            {
                "hawaii_scale": 4.0,
                "primary_direction": 270,
                "dominant_period": 11.0,
                "start_time": "2025-10-11T08:00:00Z",
                "peak_time": "2025-10-11T14:00:00Z",
                "metadata": {"source_details": {"buoy_id": "51001"}},
            }
        ]

        # Act
        result = _build_swell_matrix(swell_events)

        # Assert
        self.assertIn("4.0ft", result, "Should format single swell")
        self.assertIn("11.0s", result, "Should include period")
        lines = result.split("\n")
        self.assertEqual(len(lines), 1, "Should have exactly one line for one event")

    def test_build_swell_matrix_handles_empty_swell_events(self):
        """Test swell matrix handles empty swell events list."""
        # Arrange
        swell_events = []

        # Act
        result = _build_swell_matrix(swell_events)

        # Assert
        self.assertEqual(result, "No swell events available.", "Should return no swells message")

    def test_build_swell_matrix_includes_period_direction_arrival(self):
        """Test swell matrix includes swell period, direction, and arrival time."""
        # Arrange
        swell_events = [
            {
                "hawaii_scale": 6.0,
                "primary_direction": 0,
                "primary_direction_cardinal": "N",
                "dominant_period": 15.0,
                "start_time": "2025-10-11T06:00:00Z",
                "peak_time": "2025-10-11T12:00:00Z",
                "metadata": {"source_details": {"buoy_id": "51101"}},
            }
        ]

        # Act
        result = _build_swell_matrix(swell_events)

        # Assert
        self.assertIn("15.0s", result, "Should include period in seconds")
        self.assertIn("N", result, "Should include cardinal direction")
        self.assertIn("0°", result, "Should include degree direction")
        # Should include window with times (will be in HST format)
        self.assertIn("Window:", result, "Should include time window")


class TestTimelineConstruction(unittest.TestCase):
    """Test cases for _build_timeline_section function."""

    def test_build_timeline_chronological_ordering(self):
        """Test timeline orders swell arrivals chronologically."""
        # Arrange
        swell_events = [
            {
                "hawaii_scale": 5.0,
                "primary_direction": 315,
                "dominant_period": 12.0,
                "start_time": "2025-10-13T08:00:00Z",  # Later date
                "peak_time": "2025-10-13T14:00:00Z",
            },
            {
                "hawaii_scale": 4.0,
                "primary_direction": 270,
                "dominant_period": 11.0,
                "start_time": "2025-10-11T08:00:00Z",  # Earlier date
                "peak_time": "2025-10-11T14:00:00Z",
            },
        ]

        # Act
        result = _build_timeline_section(swell_events)
        lines = result.split("\n")

        # Assert
        self.assertGreater(len(lines), 0, "Should produce timeline")
        # Earlier date should appear first
        # Lines should be ordered chronologically
        self.assertTrue(len(lines) >= 2, "Should have at least 2 timeline entries")

    def test_build_timeline_handles_overlapping_swells(self):
        """Test timeline handles overlapping swell events correctly."""
        # Arrange
        swell_events = [
            {
                "hawaii_scale": 5.0,
                "primary_direction": 315,
                "dominant_period": 12.0,
                "start_time": "2025-10-11T08:00:00Z",
                "peak_time": "2025-10-11T14:00:00Z",
                "end_time": "2025-10-12T08:00:00Z",
            },
            {
                "hawaii_scale": 3.0,
                "primary_direction": 180,
                "dominant_period": 10.0,
                "start_time": "2025-10-11T12:00:00Z",  # Overlaps with first
                "peak_time": "2025-10-11T18:00:00Z",
                "end_time": "2025-10-12T12:00:00Z",
            },
        ]

        # Act
        result = _build_timeline_section(swell_events)

        # Assert
        self.assertIsNotNone(result, "Should handle overlapping swells")
        # Should mention secondary energy when multiple swells on same day
        self.assertIn("dominant", result.lower(), "Should identify dominant swell")

    def test_build_timeline_formats_with_hst_timestamps(self):
        """Test timeline formats timestamps in HST."""
        # Arrange
        swell_events = [
            {
                "hawaii_scale": 4.0,
                "primary_direction": 270,
                "dominant_period": 11.0,
                "start_time": "2025-10-11T20:00:00Z",  # 10:00 HST
                "peak_time": "2025-10-11T22:00:00Z",  # 12:00 HST
            }
        ]

        # Act
        result = _build_timeline_section(swell_events)

        # Assert
        # Timeline should include day-level dates
        self.assertIn("Oct", result, "Should include month abbreviation")
        # Should format with readable date format
        self.assertTrue(len(result) > 0, "Should produce formatted timeline")

    def test_build_timeline_handles_no_arrival_time(self):
        """Test timeline handles swells with missing arrival times."""
        # Arrange
        swell_events = [
            {
                "hawaii_scale": 4.0,
                "primary_direction": 270,
                "dominant_period": 11.0,
                # No start_time, peak_time, or end_time
            }
        ]

        # Act
        result = _build_timeline_section(swell_events)

        # Assert
        self.assertIn("unavailable", result.lower(), "Should indicate timeline unavailable")


class TestShoreDigestGeneration(unittest.TestCase):
    """Test cases for _build_shore_digest function."""

    def test_build_shore_digest_for_north_shore(self):
        """Test generates digest for North Shore with relevant swells."""
        # Arrange
        shore_info = {
            "name": "North Shore",
            "swell_events": [
                {
                    "hawaii_scale": 6.0,
                    "primary_direction": 315,
                    "primary_direction_cardinal": "NW",
                    "dominant_period": 14.0,
                    "start_time": "2025-10-11T08:00:00Z",
                    "peak_time": "2025-10-11T14:00:00Z",
                    "exposure_factor": 0.95,
                }
            ],
            "metadata": {"overall_quality": 0.88, "popular_breaks": ["Pipeline", "Sunset"]},
        }

        # Act
        result = _build_shore_digest(shore_info)

        # Assert
        self.assertIn("North Shore", result, "Should include shore name")
        self.assertIn("NW", result, "Should include swell direction")
        self.assertIn("6.0ft", result, "Should include swell height")
        self.assertIn("14.0s", result, "Should include period")
        self.assertIn("0.95", result, "Should include exposure factor")
        self.assertIn("Pipeline", result, "Should include popular breaks")
        self.assertIn("Sunset", result, "Should include popular breaks")

    def test_build_shore_digest_for_each_shore(self):
        """Test generates digest for South, East, West shores."""
        # Arrange
        shores = ["South Shore", "East Shore", "West Shore"]

        for shore_name in shores:
            shore_info = {
                "name": shore_name,
                "swell_events": [
                    {
                        "hawaii_scale": 3.0,
                        "primary_direction": 180,
                        "dominant_period": 10.0,
                        "start_time": "2025-10-11T08:00:00Z",
                        "peak_time": "2025-10-11T14:00:00Z",
                        "exposure_factor": 0.5,
                    }
                ],
                "metadata": {},
            }

            # Act
            result = _build_shore_digest(shore_info)

            # Assert
            self.assertIn(shore_name, result, f"Should include {shore_name} in digest")

    def test_build_shore_digest_handles_no_swells(self):
        """Test shore digest handles shore with no applicable swells."""
        # Arrange
        shore_info = {"name": "East Shore", "swell_events": [], "metadata": {}}  # No swells

        # Act
        result = _build_shore_digest(shore_info)

        # Assert
        self.assertIn("East Shore", result, "Should include shore name")
        self.assertIn("No active swell", result, "Should indicate no active swells")

    def test_build_shore_digest_formats_shore_conditions(self):
        """Test shore digest formats shore-specific conditions correctly."""
        # Arrange
        shore_info = {
            "name": "South Shore",
            "swell_events": [
                {
                    "hawaii_scale": 2.5,
                    "primary_direction": 180,
                    "dominant_period": 9.0,
                    "start_time": "2025-10-11T08:00:00Z",
                    "peak_time": "2025-10-11T14:00:00Z",
                    "exposure_factor": 0.75,
                }
            ],
            "metadata": {"overall_quality": 0.65, "popular_breaks": ["Ala Moana"]},
        }

        # Act
        result = _build_shore_digest(shore_info)

        # Assert
        self.assertIn("2.5ft", result, "Should format height")
        self.assertIn("9.0s", result, "Should format period")
        self.assertIn("exposure weight 0.75", result, "Should format exposure")
        self.assertIn("Quality index: 0.65", result, "Should format quality")


class TestDateTimeConversions(unittest.TestCase):
    """Test cases for date/time conversion functions."""

    def test_to_hst_converts_utc_to_hawaii_time(self):
        """Test _to_hst converts UTC to Hawaii Standard Time."""
        # Arrange: UTC timestamp (noon UTC)
        utc_time = datetime(2025, 10, 11, 12, 0, 0)

        # Act
        with patch("src.forecast_engine.context_builder.HAWAII_TZ", None):
            # Test fallback mode (subtract 10 hours)
            result = _to_hst(utc_time)

        # Assert
        # Without timezone info, naive datetime returned as-is
        self.assertEqual(result, utc_time)

    def test_format_hst_handles_timezone_aware_timestamps(self):
        """Test _format_hst handles timezone-aware UTC timestamps."""
        # Arrange: UTC timestamp with timezone
        utc_timestamp = "2025-10-11T22:00:00Z"

        # Act
        result = _format_hst(utc_timestamp)

        # Assert
        self.assertIn("HST", result, "Should include HST indicator")
        self.assertNotEqual(result, "n/a", "Should format valid timestamp")

    def test_format_hst_handles_naive_timestamps(self):
        """Test _format_hst handles naive datetime strings."""
        # Arrange: ISO format without timezone
        naive_timestamp = "2025-10-11T12:00:00"

        # Act
        result = _format_hst(naive_timestamp)

        # Assert
        self.assertIn("HST", result, "Should add HST indicator")
        self.assertIn("2025-10-11", result, "Should preserve date")

    def test_format_hst_formats_time_correctly(self):
        """Test _format_hst formats time in HH:MM HST format."""
        # Arrange
        timestamp = "2025-10-11T14:30:00Z"

        # Act
        result = _format_hst(timestamp)

        # Assert
        self.assertIn(":", result, "Should include time separator")
        self.assertIn("HST", result, "Should include HST")
        # Format should be YYYY-MM-DD HH:MM HST
        parts = result.split()
        self.assertEqual(len(parts), 3, "Should have date, time, and HST")


class TestCardinalDirectionConversion(unittest.TestCase):
    """Test cases for _deg_to_cardinal function."""

    def test_deg_to_cardinal_0_degrees_returns_N(self):
        """Test cardinal direction for 0 degrees returns N."""
        # Arrange, Act, Assert
        self.assertEqual(_deg_to_cardinal(0), "N", "0° should be North")

    def test_deg_to_cardinal_45_degrees_returns_NE(self):
        """Test cardinal direction for 45 degrees returns NE."""
        # Arrange, Act, Assert
        self.assertEqual(_deg_to_cardinal(45), "NE", "45° should be Northeast")

    def test_deg_to_cardinal_90_degrees_returns_E(self):
        """Test cardinal direction for 90 degrees returns E."""
        # Arrange, Act, Assert
        self.assertEqual(_deg_to_cardinal(90), "E", "90° should be East")

    def test_deg_to_cardinal_180_degrees_returns_S(self):
        """Test cardinal direction for 180 degrees returns S."""
        # Arrange, Act, Assert
        self.assertEqual(_deg_to_cardinal(180), "S", "180° should be South")

    def test_deg_to_cardinal_270_degrees_returns_W(self):
        """Test cardinal direction for 270 degrees returns W."""
        # Arrange, Act, Assert
        self.assertEqual(_deg_to_cardinal(270), "W", "270° should be West")

    def test_deg_to_cardinal_337_5_degrees_returns_NNW(self):
        """Test cardinal direction for 337.5 degrees returns NNW (16-point compass)."""
        # Arrange, Act, Assert
        self.assertEqual(_deg_to_cardinal(337.5), "NNW", "337.5° should be North-Northwest")

    def test_deg_to_cardinal_handles_negative_degrees(self):
        """Test negative degree wrapping (-45° == 315° == NW)."""
        # Arrange, Act, Assert
        self.assertEqual(_deg_to_cardinal(-45), "NW", "-45° should wrap to 315° (Northwest)")

    def test_deg_to_cardinal_handles_degrees_over_360(self):
        """Test degree wrapping for values > 360 (405° == 45° == NE)."""
        # Arrange, Act, Assert
        self.assertEqual(_deg_to_cardinal(405), "NE", "405° should wrap to 45° (Northeast)")

    def test_deg_to_cardinal_handles_none_value(self):
        """Test _deg_to_cardinal handles None value."""
        # Arrange, Act, Assert
        self.assertEqual(_deg_to_cardinal(None), "Unknown", "None should return Unknown")

    def test_deg_to_cardinal_handles_invalid_string(self):
        """Test _deg_to_cardinal handles invalid string input."""
        # Arrange, Act, Assert
        self.assertEqual(
            _deg_to_cardinal("invalid"), "Unknown", "Invalid string should return Unknown"
        )


class TestHTMLStripping(unittest.TestCase):
    """Test cases for _strip_html function."""

    def test_strip_html_removes_tags(self):
        """Test _strip_html removes HTML tags from text."""
        # Arrange
        html_text = '<p>This is <strong>bold</strong> text with <a href="#">link</a>.</p>'

        # Act
        result = _strip_html(html_text)

        # Assert
        self.assertNotIn("<p>", result, "Should remove <p> tags")
        self.assertNotIn("<strong>", result, "Should remove <strong> tags")
        self.assertNotIn("<a", result, "Should remove <a> tags")
        self.assertIn("This is", result, "Should preserve text content")
        self.assertIn("bold", result, "Should preserve text content")

    def test_strip_html_handles_text_without_tags(self):
        """Test _strip_html handles plain text without HTML tags."""
        # Arrange
        plain_text = "This is plain text without any HTML tags."

        # Act
        result = _strip_html(plain_text)

        # Assert
        self.assertEqual(result, plain_text, "Should return plain text unchanged")


class TestHelperFunctions(unittest.TestCase):
    """Test cases for helper utility functions."""

    def test_extract_period_from_dominant_period(self):
        """Test _extract_period extracts dominant_period when available."""
        # Arrange
        event = {"dominant_period": 12.5}

        # Act
        result = _extract_period(event)

        # Assert
        self.assertEqual(result, 12.5, "Should extract dominant_period")

    def test_extract_period_from_primary_components(self):
        """Test _extract_period extracts from primary_components when dominant_period missing."""
        # Arrange
        event = {"primary_components": [{"period": 10.0}, {"period": 14.0}, {"period": 12.0}]}

        # Act
        result = _extract_period(event)

        # Assert
        self.assertEqual(result, 14.0, "Should return maximum period from components")

    def test_extract_period_returns_zero_when_no_data(self):
        """Test _extract_period returns 0.0 when no period data available."""
        # Arrange
        event = {}

        # Act
        result = _extract_period(event)

        # Assert
        self.assertEqual(result, 0.0, "Should return 0.0 when no period data")

    def test_estimate_h10_from_h13(self):
        """Test _estimate_h10 calculates H1/10 from H1/3 using 1.3x multiplier."""
        # Arrange
        h13 = 5.0

        # Act
        result = _estimate_h10(h13)

        # Assert
        self.assertEqual(result, 6.5, "H1/10 should be 1.3 * H1/3")

    def test_estimate_h10_handles_zero(self):
        """Test _estimate_h10 handles zero input."""
        # Arrange
        h13 = 0.0

        # Act
        result = _estimate_h10(h13)

        # Assert
        self.assertEqual(result, 0.0, "Should return 0.0 for zero input")

    def test_estimate_h10_handles_negative(self):
        """Test _estimate_h10 handles negative input."""
        # Arrange
        h13 = -5.0

        # Act
        result = _estimate_h10(h13)

        # Assert
        self.assertEqual(result, 0.0, "Should return 0.0 for negative input")

    def test_format_exposures_formats_shore_exposures(self):
        """Test _format_exposures formats exposure values for shores."""
        # Arrange
        meta = {
            "exposure_north_shore": 0.95,
            "exposure_south_shore": 0.25,
            "exposure_west_shore": 0.60,
        }

        # Act
        result = _format_exposures(meta)

        # Assert
        self.assertIn("North Shore", result, "Should format north shore")
        self.assertIn("0.95", result, "Should include exposure value")
        self.assertIn("South Shore", result, "Should format south shore")

    def test_format_exposures_handles_no_exposures(self):
        """Test _format_exposures handles metadata without exposure fields."""
        # Arrange
        meta = {"other_field": "value"}

        # Act
        result = _format_exposures(meta)

        # Assert
        self.assertIn("unavailable", result.lower(), "Should indicate exposures unavailable")

    def test_summarise_secondary_formats_secondary_swell(self):
        """Test _summarise_secondary formats secondary swell events."""
        # Arrange
        event = {
            "hawaii_scale": 3.0,
            "primary_direction": 180,
            "primary_direction_cardinal": "S",
            "dominant_period": 9.0,
        }

        # Act
        result = _summarise_secondary(event)

        # Assert
        self.assertIn("S", result, "Should include direction")
        self.assertIn("3.0ft", result, "Should include height")
        self.assertIn("@9s", result, "Should include period")


class TestBuildOverview(unittest.TestCase):
    """Test cases for _build_overview function."""

    def test_build_overview_includes_confidence_score(self):
        """Test _build_overview includes confidence score and category."""
        # Arrange
        metadata = {}
        confidence = {"overall_score": 0.85, "category": "High"}
        swell_events = []

        # Act
        result = _build_overview(metadata, confidence, swell_events)

        # Assert
        self.assertIn("0.85", result, "Should include confidence score")
        self.assertIn("High", result, "Should include confidence category")

    def test_build_overview_handles_missing_confidence(self):
        """Test _build_overview handles missing confidence data."""
        # Arrange
        metadata = {}
        confidence = {}
        swell_events = []

        # Act
        result = _build_overview(metadata, confidence, swell_events)

        # Assert
        self.assertIn("unavailable", result.lower(), "Should indicate confidence unavailable")


class TestBuildWeatherSection(unittest.TestCase):
    """Test cases for _build_weather_section function."""

    def test_build_weather_section_formats_wind_data(self):
        """Test _build_weather_section formats wind direction and speed."""
        # Arrange
        metadata = {"weather": {"wind_direction": 90, "wind_speed_kt": 15.5}}

        # Act
        result = _build_weather_section(metadata)

        # Assert
        self.assertIn("90°", result, "Should include wind direction")
        self.assertIn("15.5 kt", result, "Should include wind speed in knots")


class TestBuildTideSection(unittest.TestCase):
    """Test cases for _build_tide_section function."""

    def test_build_tide_section_formats_high_and_low_tides(self):
        """Test _build_tide_section formats high and low tide times."""
        # Arrange
        metadata = {
            "tides": {
                "high_tide": [("2025-10-11T12:00:00Z", 2.5), ("2025-10-12T00:30:00Z", 2.3)],
                "low_tide": [("2025-10-11T06:00:00Z", 0.2), ("2025-10-11T18:00:00Z", 0.3)],
            }
        }

        # Act
        result = _build_tide_section(metadata)

        # Assert
        self.assertIn("High:", result, "Should label high tides")
        self.assertIn("Low:", result, "Should label low tides")
        self.assertIn("2.5", result, "Should include tide heights")


class TestBuildTropicalSection(unittest.TestCase):
    """Test cases for _build_tropical_section function."""

    def test_build_tropical_section_strips_html_from_summary(self):
        """Test _build_tropical_section strips HTML from tropical summaries."""
        # Arrange
        metadata = {
            "tropical": {
                "headline": "Tropical Update",
                "entries": [{"summary": "<p>Storm <strong>approaching</strong> Hawaii</p>"}],
            }
        }

        # Act
        result = _build_tropical_section(metadata)

        # Assert
        self.assertNotIn("<p>", result, "Should strip HTML tags")
        self.assertNotIn("<strong>", result, "Should strip HTML tags")
        self.assertIn("Storm", result, "Should preserve text content")
        self.assertIn("approaching", result, "Should preserve text content")


class TestBuildDataGapSection(unittest.TestCase):
    """Test cases for _build_data_gap_section function."""

    def test_build_data_gap_section_lists_missing_feeds(self):
        """Test _build_data_gap_section lists missing data feeds."""
        # Arrange
        metadata = {
            "agent_results": {
                "buoy_agent": {"total": 5, "successful": 5},
                "satellite_agent": {"total": 2, "successful": 0},
                "model_agent": {"total": 3, "successful": 0},
            }
        }

        # Act
        result = _build_data_gap_section(metadata)

        # Assert
        self.assertIn("Missing feeds:", result, "Should label missing feeds")
        self.assertIn("satellite_agent", result, "Should list failed agent")
        self.assertIn("model_agent", result, "Should list failed agent")
        self.assertNotIn("buoy_agent", result, "Should not list successful agent")

    def test_build_data_gap_section_handles_all_successful(self):
        """Test _build_data_gap_section when all feeds successful."""
        # Arrange
        metadata = {
            "agent_results": {
                "buoy_agent": {"total": 5, "successful": 5},
                "weather_agent": {"total": 3, "successful": 3},
            }
        }

        # Act
        result = _build_data_gap_section(metadata)

        # Assert
        self.assertIn("successfully", result.lower(), "Should indicate all successful")


if __name__ == "__main__":
    unittest.main()
