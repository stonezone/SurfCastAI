"""
Unit tests for forecast parser

Tests the ForecastParser's ability to extract structured predictions
from markdown forecast files.

Author: SurfCastAI Team
Created: October 2025
"""

import pytest
from datetime import datetime
from pathlib import Path
from src.validation.forecast_parser import ForecastParser, ForecastPrediction


@pytest.fixture
def parser():
    """Create a forecast parser instance"""
    return ForecastParser()


@pytest.fixture
def sample_forecast_content():
    """Sample forecast markdown content for testing"""
    return """# Hawaii Surf Forecast
*Generated on October 06, 2025 at 23:50*

## Main Forecast

### Summary
North-facing shores building to **6-8 ft** Hawaiian scale on Oct 7.

### North Shore

Expected heights (Hawaiian scale) at exposed outer reef north shore: commonly **6-8 ft** Hawaiian-scale at peak.

## North Shore Forecast

Summary (Oct 6 → Oct 8, 2025)
- General size trend (Hawaiian): Building Oct 6 → peak Oct 7 → easing Oct 8.

Pipeline (Ehukai / Backdoor)
- Expected: **6-10 ft** Hawaiian (face roughly **12-20 ft**) at peak on Oct 7.

Sunset Beach
- Expected: **4-8 ft** Hawaiian (face roughly **8-16 ft**), variable depending on angle.

## South Shore Forecast

South Shore overview (2025-10-06 → 2025-10-08)
- Primary energy: SSE swell, 1.6 ft (Hawaiian) @ 13 s — modest but long enough period.

Ala Moana Bowls
- Expectation: the most consistent, punchy lines. **3-4 ft** faces on the bigger sets.

## Daily Forecast

Quick summary
- North Shore reefs: **2-4 ft** Hawaiian (occasional bigger sets to **5 ft** Hawaiian at peak breaks/sets).
- South Shore: **0-1 ft** Hawaiian (generally small/bumps).
"""


@pytest.fixture
def sample_forecast_file(tmp_path, sample_forecast_content):
    """Create a temporary forecast file for testing"""
    forecast_file = tmp_path / "forecast_20251006_235037.md"
    forecast_file.write_text(sample_forecast_content)
    return forecast_file


class TestForecastParser:
    """Test suite for ForecastParser"""

    def test_parser_initialization(self, parser):
        """Test parser initializes correctly"""
        assert parser is not None
        assert hasattr(parser, 'PATTERNS')
        assert hasattr(parser, 'CATEGORY_THRESHOLDS')

    def test_extract_forecast_time_from_content(self, parser, sample_forecast_content):
        """Test extracting forecast time from content"""
        file_path = Path("forecast_20251006_235037.md")
        forecast_time = parser._extract_forecast_time(sample_forecast_content, file_path)

        assert forecast_time is not None
        assert isinstance(forecast_time, datetime)
        assert forecast_time.year == 2025
        assert forecast_time.month == 10
        assert forecast_time.day == 6

    def test_extract_forecast_time_from_filename(self, parser, tmp_path):
        """Test extracting forecast time from filename when content fails"""
        content = "# Forecast\nNo date in content"
        file_path = tmp_path / "forecast_20251006_120000.md"
        file_path.write_text(content)

        forecast_time = parser._extract_forecast_time(content, file_path)

        assert forecast_time is not None
        assert forecast_time.year == 2025
        assert forecast_time.month == 10
        assert forecast_time.day == 6
        assert forecast_time.hour == 12

    def test_split_shore_sections(self, parser, sample_forecast_content):
        """Test splitting content into shore sections"""
        sections = parser._split_shore_sections(sample_forecast_content)

        assert 'North Shore' in sections
        assert 'South Shore' in sections
        assert 'Pipeline' in sections['North Shore']
        assert 'Ala Moana' in sections['South Shore']

    def test_extract_height_range(self, parser):
        """Test extracting height ranges"""
        test_cases = [
            ("Expected **6-8 ft** Hawaiian scale", {'height': 7.0, 'height_min': 6.0, 'height_max': 8.0}),
            ("commonly 4-6 ft Hawaiian", {'height': 5.0, 'height_min': 4.0, 'height_max': 6.0}),
            ("Expected: **10-12 ft** Hawaiian", {'height': 11.0, 'height_min': 10.0, 'height_max': 12.0}),
        ]

        for text, expected in test_cases:
            result = parser._extract_height(text)
            assert result is not None
            assert result['height'] == expected['height']
            assert result['height_min'] == expected['height_min']
            assert result['height_max'] == expected['height_max']

    def test_extract_height_single(self, parser):
        """Test extracting single height values"""
        text = "approximately 5 ft Hawaiian"
        result = parser._extract_height(text)

        assert result is not None
        assert result['height'] == 5.0
        assert result['height_min'] == 5.0
        assert result['height_max'] == 5.0

    def test_extract_height_none(self, parser):
        """Test extracting height from text with no height"""
        text = "Clear conditions with light winds"
        result = parser._extract_height(text)
        assert result is None

    def test_extract_period_range(self, parser):
        """Test extracting period ranges"""
        test_cases = [
            ("14-16 second periods", (15.0, 14.0, 16.0)),
            ("Period: 12-14 s", (13.0, 12.0, 14.0)),
            ("10-12 sec NW swell", (11.0, 10.0, 12.0)),
        ]

        for text, expected in test_cases:
            period, period_min, period_max = parser._extract_period(text)
            assert period == expected[0]
            assert period_min == expected[1]
            assert period_max == expected[2]

    def test_extract_period_single(self, parser):
        """Test extracting single period values"""
        text = "13 s swell arriving"
        period, period_min, period_max = parser._extract_period(text)

        assert period == 13.0
        assert period_min == 13.0
        assert period_max == 13.0

    def test_extract_direction(self, parser):
        """Test extracting swell directions"""
        test_cases = [
            ("NW swell building", "NW"),
            ("Direction: NNE", "NNE"),
            ("from the N", "N"),
            ("SSE pulse arriving", "SSE"),
        ]

        for text, expected in test_cases:
            direction = parser._extract_direction(text)
            assert direction == expected

    def test_extract_direction_none(self, parser):
        """Test direction extraction when no direction present"""
        text = "Building swell with no direction"
        direction = parser._extract_direction(text)
        assert direction is None

    def test_determine_category_from_height(self, parser):
        """Test category determination from height thresholds"""
        test_cases = [
            (2.0, "small"),
            (5.0, "moderate"),
            (9.0, "large"),
            (15.0, "extra_large"),
        ]

        for height, expected in test_cases:
            category = parser._determine_category(height, "")
            assert category == expected

    def test_determine_category_from_text(self, parser):
        """Test category determination from explicit text"""
        test_cases = [
            ("small waves expected", "small"),
            ("moderate conditions", "moderate"),
            ("large surf building", "large"),
            ("extra large swell", "extra_large"),
        ]

        for text, expected in test_cases:
            category = parser._determine_category(5.0, text)
            assert category == expected

    def test_calculate_confidence(self, parser):
        """Test confidence calculation"""
        # Base confidence
        height_data = {'height': 5.0}
        prediction = ForecastPrediction(
            shore="North Shore",
            forecast_time=datetime.now(),
            valid_time=datetime.now(),
            day_number=1,
            height=5.0
        )
        confidence = parser._calculate_confidence(height_data, prediction)
        assert confidence == 0.5

        # With height range
        height_data = {'height': 5.0, 'height_min': 4.0, 'height_max': 6.0}
        confidence = parser._calculate_confidence(height_data, prediction)
        assert confidence == 0.7

        # With period
        prediction.period = 12.0
        confidence = parser._calculate_confidence(height_data, prediction)
        assert confidence == 0.85

        # With direction
        prediction.direction = "NW"
        confidence = parser._calculate_confidence(height_data, prediction)
        assert confidence == 0.95

        # With category
        prediction.category = "moderate"
        confidence = parser._calculate_confidence(height_data, prediction)
        assert confidence == 1.0

    def test_is_forecast_summary_line(self, parser):
        """Test identification of forecast summary lines"""
        # Should be summary lines
        summary_lines = [
            "Expected: **6-8 ft** Hawaiian scale",
            "commonly **4-6 ft** Hawaiian-scale",
            "Timing/size: essentially quiet",
            "Overall: small",
            "Building to 8-10 ft with 14-16 s periods",
        ]

        for line in summary_lines:
            assert parser._is_forecast_summary_line(line), f"Failed to identify summary: {line}"

        # Should NOT be summary lines
        detail_lines = [
            "- N @ 6.9 ft, 11.0 s — arrival/peak 2025-10-06",
            "1) N @ 6.9 ft, 11 s (moderate effect)",
            "• NNE @ 6.6 ft, 7.0 s and NNE @ 6.9 ft",
        ]

        for line in detail_lines:
            assert not parser._is_forecast_summary_line(line), f"Incorrectly identified as summary: {line}"

    def test_parse_forecast_file(self, parser, sample_forecast_file):
        """Test parsing a complete forecast file"""
        predictions = parser.parse_forecast_file(sample_forecast_file)

        assert len(predictions) > 0
        assert all(isinstance(p, ForecastPrediction) for p in predictions)

        # Check that we have predictions for both shores
        shores = {p.shore for p in predictions}
        assert "North Shore" in shores

        # Check prediction structure
        for pred in predictions:
            assert pred.shore in ["North Shore", "South Shore"]
            assert pred.height > 0
            assert pred.height_min is not None
            assert pred.height_max is not None
            assert 0 <= pred.confidence <= 1.0

    def test_parse_forecast_file_not_found(self, parser):
        """Test handling of missing forecast file"""
        with pytest.raises(FileNotFoundError):
            parser.parse_forecast_file(Path("nonexistent.md"))

    def test_prediction_to_dict(self):
        """Test converting prediction to dictionary"""
        prediction = ForecastPrediction(
            shore="North Shore",
            forecast_time=datetime(2025, 10, 6, 23, 50),
            valid_time=datetime(2025, 10, 7, 0, 0),
            day_number=1,
            height=7.0,
            height_min=6.0,
            height_max=8.0,
            period=14.0,
            direction="NW",
            category="moderate",
            confidence=0.95
        )

        pred_dict = prediction.to_dict()

        assert isinstance(pred_dict, dict)
        assert pred_dict['shore'] == "North Shore"
        assert pred_dict['height'] == 7.0
        assert pred_dict['direction'] == "NW"
        assert 'forecast_time' in pred_dict
        assert 'valid_time' in pred_dict

    def test_parse_multiple_forecasts(self, parser, tmp_path):
        """Test parsing multiple forecast files"""
        # Create multiple forecast files
        for i in range(3):
            forecast_file = tmp_path / f"forecast_2025100{i}_120000.md"
            forecast_file.write_text(f"""
# Forecast {i}
## North Shore
Expected **{4+i*2}-{6+i*2} ft** Hawaiian scale
""")

        results = parser.parse_multiple_forecasts(tmp_path)

        assert len(results) == 3
        assert all(isinstance(predictions, list) for predictions in results.values())

    def test_parse_multiple_forecasts_directory_not_found(self, parser):
        """Test handling of missing directory"""
        with pytest.raises(FileNotFoundError):
            parser.parse_multiple_forecasts(Path("nonexistent_dir"))

    def test_deduplication(self, parser, tmp_path):
        """Test that duplicate predictions are filtered"""
        content = """
# Forecast
## North Shore
Expected **6-8 ft** Hawaiian scale on Oct 7
Expected **6-8 ft** Hawaiian scale on Oct 7
Expected **6-8 ft** Hawaiian scale on Oct 7
"""
        forecast_file = tmp_path / "forecast_test.md"
        forecast_file.write_text(content)

        predictions = parser.parse_forecast_file(forecast_file)

        # Should only have one prediction despite three identical lines
        north_shore_preds = [p for p in predictions if p.shore == "North Shore"]
        assert len(north_shore_preds) == 1

    def test_multi_day_parsing(self, parser, tmp_path):
        """Test parsing multi-day forecasts"""
        content = """
# Forecast
## North Shore

Day 1 (Oct 6): **4-6 ft** Hawaiian scale
Day 2 (Oct 7): **6-8 ft** Hawaiian scale
Day 3 (Oct 8): **8-10 ft** Hawaiian scale
"""
        forecast_file = tmp_path / "forecast_20251006_000000.md"
        forecast_file.write_text(content)

        predictions = parser.parse_forecast_file(forecast_file)

        # Should have predictions for 3 days
        day_numbers = {p.day_number for p in predictions}
        assert 1 in day_numbers
        assert 2 in day_numbers
        assert 3 in day_numbers

    def test_graceful_malformed_handling(self, parser, tmp_path):
        """Test graceful handling of malformed content"""
        malformed_content = """
# Broken Forecast
Some random text with no structure
Numbers like 123 and 456 but no real data
## North Shore maybe?
More random text
"""
        forecast_file = tmp_path / "malformed.md"
        forecast_file.write_text(malformed_content)

        # Should not crash, may return empty or minimal predictions
        predictions = parser.parse_forecast_file(forecast_file)
        assert isinstance(predictions, list)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
