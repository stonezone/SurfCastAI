#!/usr/bin/env python3
"""
Unit tests for SpectralAnalyzer.

Tests cover:
- Pydantic model validation
- .spec file parsing
- Swell/wind wave component extraction
- Peak detection and filtering
- Error handling
"""

import os
import tempfile
from datetime import datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.processing.spectral_analyzer import (
    SpectralAnalysisResult,
    SpectralAnalyzer,
    SpectralPeak,
    analyze_spec_file,
)


class TestSpectralPeakModel:
    """Tests for SpectralPeak Pydantic model."""

    def test_valid_peak_creation(self):
        """Test creating a valid spectral peak."""
        peak = SpectralPeak(
            frequency_hz=0.1,
            period_seconds=10.0,
            direction_degrees=315.0,
            energy_density=0.5,
            height_meters=1.5,
            directional_spread=30.0,
            confidence=0.85,
            component_type="swell",
        )

        assert peak.frequency_hz == 0.1
        assert peak.period_seconds == 10.0
        assert peak.direction_degrees == 315.0
        assert peak.component_type == "swell"

    def test_period_validation_lower_bound(self):
        """Test period validation rejects values < 4.0s."""
        with pytest.raises(ValidationError):
            SpectralPeak(
                frequency_hz=0.3,
                period_seconds=3.0,  # Too short
                direction_degrees=0,
                energy_density=0.1,
                height_meters=0.5,
                directional_spread=30.0,
                confidence=0.8,
            )

    def test_period_validation_upper_bound(self):
        """Test period validation rejects values > 30.0s."""
        with pytest.raises(ValidationError):
            SpectralPeak(
                frequency_hz=0.02,
                period_seconds=35.0,  # Too long
                direction_degrees=0,
                energy_density=0.1,
                height_meters=0.5,
                directional_spread=30.0,
                confidence=0.8,
            )

    def test_direction_normalization(self):
        """Test direction is normalized to [0, 360)."""
        peak = SpectralPeak(
            frequency_hz=0.1,
            period_seconds=10.0,
            direction_degrees=400.0,  # > 360
            energy_density=0.5,
            height_meters=1.5,
            directional_spread=30.0,
            confidence=0.85,
        )

        assert peak.direction_degrees == 40.0  # 400 % 360

    def test_confidence_bounds(self):
        """Test confidence must be in [0, 1]."""
        with pytest.raises(ValidationError):
            SpectralPeak(
                frequency_hz=0.1,
                period_seconds=10.0,
                direction_degrees=0,
                energy_density=0.5,
                height_meters=1.5,
                directional_spread=30.0,
                confidence=1.5,  # > 1.0
            )


class TestSpectralAnalysisResultModel:
    """Tests for SpectralAnalysisResult Pydantic model."""

    def test_valid_result_creation(self):
        """Test creating a valid analysis result."""
        peak1 = SpectralPeak(
            frequency_hz=0.095,
            period_seconds=10.5,
            direction_degrees=315.0,
            energy_density=1.0,
            height_meters=2.0,
            directional_spread=30.0,
            confidence=0.85,
        )

        peak2 = SpectralPeak(
            frequency_hz=0.1,
            period_seconds=10.0,
            direction_degrees=0,
            energy_density=0.5,
            height_meters=1.0,
            directional_spread=60.0,
            confidence=0.75,
        )

        result = SpectralAnalysisResult(
            buoy_id="51201",
            timestamp="2025-10-10T12:00:00Z",
            peaks=[peak1, peak2],
            total_energy=1.5,
            dominant_peak=peak1,
        )

        assert result.buoy_id == "51201"
        assert len(result.peaks) == 2
        assert result.dominant_peak == peak1

    def test_peaks_sorted_by_energy(self):
        """Test peaks are automatically sorted by energy (highest first)."""
        peak_low = SpectralPeak(
            frequency_hz=0.1,
            period_seconds=10.0,
            direction_degrees=0,
            energy_density=0.3,  # Lower energy
            height_meters=1.0,
            directional_spread=60.0,
            confidence=0.75,
        )

        peak_high = SpectralPeak(
            frequency_hz=0.095,
            period_seconds=10.5,
            direction_degrees=315.0,
            energy_density=1.0,  # Higher energy
            height_meters=2.0,
            directional_spread=30.0,
            confidence=0.85,
        )

        # Pass in wrong order
        result = SpectralAnalysisResult(
            buoy_id="51201",
            timestamp="2025-10-10T12:00:00Z",
            peaks=[peak_low, peak_high],  # Low first
            total_energy=1.3,
            dominant_peak=peak_high,
        )

        # Should be sorted with high energy first
        assert result.peaks[0] == peak_high
        assert result.peaks[1] == peak_low


class TestSpectralAnalyzer:
    """Tests for SpectralAnalyzer class."""

    def test_initialization_default_params(self):
        """Test analyzer initialization with defaults."""
        analyzer = SpectralAnalyzer()

        assert analyzer.min_period == 8.0
        assert analyzer.max_period == 25.0
        assert analyzer.min_separation_period == 3.0
        assert analyzer.min_separation_direction == 30.0
        assert analyzer.energy_threshold == 0.1
        assert analyzer.max_components == 5

    def test_initialization_custom_params(self):
        """Test analyzer initialization with custom parameters."""
        analyzer = SpectralAnalyzer(
            min_period=10.0, max_period=20.0, min_separation_period=5.0, max_components=3
        )

        assert analyzer.min_period == 10.0
        assert analyzer.max_period == 20.0
        assert analyzer.min_separation_period == 5.0
        assert analyzer.max_components == 3

    def test_parse_direction_valid(self):
        """Test parsing valid compass directions."""
        analyzer = SpectralAnalyzer()

        assert analyzer._parse_direction("N") == 0.0
        assert analyzer._parse_direction("NE") == 45.0
        assert analyzer._parse_direction("S") == 180.0
        assert analyzer._parse_direction("NW") == 315.0

    def test_parse_direction_missing(self):
        """Test parsing missing data marker."""
        analyzer = SpectralAnalyzer()

        assert analyzer._parse_direction("MM") is None

    def test_parse_direction_invalid(self):
        """Test parsing invalid direction."""
        analyzer = SpectralAnalyzer()

        assert analyzer._parse_direction("INVALID") is None

    def test_safe_float_valid(self):
        """Test safe float conversion with valid input."""
        analyzer = SpectralAnalyzer()

        assert analyzer._safe_float("1.5") == 1.5
        assert analyzer._safe_float("10.0") == 10.0

    def test_safe_float_missing_data(self):
        """Test safe float with NDBC missing data markers."""
        analyzer = SpectralAnalyzer()

        assert analyzer._safe_float("99.0") is None
        assert analyzer._safe_float("999.0") is None

    def test_safe_float_invalid(self):
        """Test safe float with invalid input."""
        analyzer = SpectralAnalyzer()

        assert analyzer._safe_float("MM") is None
        assert analyzer._safe_float("INVALID") is None

    def test_directional_difference_simple(self):
        """Test directional difference calculation."""
        analyzer = SpectralAnalyzer()

        # Simple case
        assert analyzer._directional_difference(0, 45) == 45.0
        assert analyzer._directional_difference(45, 0) == 45.0

    def test_directional_difference_wrap_around(self):
        """Test directional difference wraps correctly."""
        analyzer = SpectralAnalyzer()

        # Wrap around case (350° to 10° = 20°, not 340°)
        assert analyzer._directional_difference(350, 10) == 20.0
        assert analyzer._directional_difference(10, 350) == 20.0

    def test_directional_difference_opposite(self):
        """Test opposite directions."""
        analyzer = SpectralAnalyzer()

        # Opposite directions
        assert analyzer._directional_difference(0, 180) == 180.0
        assert analyzer._directional_difference(90, 270) == 180.0


class TestSpecFileParsing:
    """Tests for .spec file parsing."""

    @pytest.fixture
    def temp_spec_file(self):
        """Create a temporary .spec file for testing."""
        content = """#YY  MM DD hh mm WVHT  SwH  SwP  WWH  WWP SwD WWD  STEEPNESS  APD MWD
#yr  mo dy hr mn    m    m  sec    m  sec  -  degT     -      sec degT
2025 10 10 12 00  1.5  0.8 10.5  1.0  9.9 NNE  N    AVERAGE  8.5  15
2025 10 10 11 30  1.4  0.7 10.5  1.1  9.9  N   N    AVERAGE  8.3  10
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".spec", delete=False) as f:
            f.write(content)
            temp_path = f.name

        yield temp_path

        # Cleanup
        if os.path.exists(temp_path):
            os.remove(temp_path)

    def test_parse_valid_spec_file(self, temp_spec_file):
        """Test parsing a valid .spec file."""
        analyzer = SpectralAnalyzer()
        result = analyzer.parse_spec_file(temp_spec_file)

        assert result is not None
        assert len(result.peaks) > 0
        assert result.timestamp == "2025-10-10T12:00:00Z"
        assert result.total_energy > 0
        assert result.dominant_peak is not None

    def test_parse_spec_file_not_found(self):
        """Test parsing non-existent file."""
        analyzer = SpectralAnalyzer()
        result = analyzer.parse_spec_file("/nonexistent/file.spec")

        assert result is None

    def test_parse_spec_file_extracts_both_components(self, temp_spec_file):
        """Test that both swell and wind wave components are extracted."""
        analyzer = SpectralAnalyzer()
        result = analyzer.parse_spec_file(temp_spec_file)

        assert result is not None

        # Should have swell component
        swell_peaks = [p for p in result.peaks if p.component_type == "swell"]
        assert len(swell_peaks) >= 1

        # Swell should have period ~10.5s
        assert any(10.0 <= p.period_seconds <= 11.0 for p in swell_peaks)

    @pytest.fixture
    def spec_file_missing_data(self):
        """Create .spec file with missing data."""
        content = """#YY  MM DD hh mm WVHT  SwH  SwP  WWH  WWP SwD WWD  STEEPNESS  APD MWD
#yr  mo dy hr mn    m    m  sec    m  sec  -  degT     -      sec degT
2025 10 10 12 00  1.5  99.0  MM  1.0  9.9  MM  N    AVERAGE  8.5  15
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".spec", delete=False) as f:
            f.write(content)
            temp_path = f.name

        yield temp_path

        if os.path.exists(temp_path):
            os.remove(temp_path)

    def test_parse_spec_file_handles_missing_data(self, spec_file_missing_data):
        """Test parsing handles missing data markers (99.0, MM)."""
        analyzer = SpectralAnalyzer()
        result = analyzer.parse_spec_file(spec_file_missing_data)

        assert result is not None

        # Swell component should be excluded (missing height and direction)
        swell_peaks = [p for p in result.peaks if p.component_type == "swell"]
        assert len(swell_peaks) == 0

    @pytest.fixture
    def spec_file_short_period(self):
        """Create .spec file with period below minimum threshold."""
        content = """#YY  MM DD hh mm WVHT  SwH  SwP  WWH  WWP SwD WWD  STEEPNESS  APD MWD
#yr  mo dy hr mn    m    m  sec    m  sec  -  degT     -      sec degT
2025 10 10 12 00  1.0  0.5  6.0  0.8  5.0  N   N    AVERAGE  5.5  10
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".spec", delete=False) as f:
            f.write(content)
            temp_path = f.name

        yield temp_path

        if os.path.exists(temp_path):
            os.remove(temp_path)

    def test_parse_spec_file_filters_short_period(self, spec_file_short_period):
        """Test that components with period < min_period are filtered."""
        analyzer = SpectralAnalyzer(min_period=8.0)
        result = analyzer.parse_spec_file(spec_file_short_period)

        assert result is not None

        # Both swell (6.0s) and wind wave (5.0s) should be filtered
        assert len(result.peaks) == 0

    @pytest.fixture
    def spec_file_similar_components(self):
        """Create .spec file with very similar swell and wind wave."""
        content = """#YY  MM DD hh mm WVHT  SwH  SwP  WWH  WWP SwD WWD  STEEPNESS  APD MWD
#yr  mo dy hr mn    m    m  sec    m  sec  -  degT     -      sec degT
2025 10 10 12 00  1.5  0.8 10.5  0.7 10.0 NNE NNE    AVERAGE  10.2  22
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".spec", delete=False) as f:
            f.write(content)
            temp_path = f.name

        yield temp_path

        if os.path.exists(temp_path):
            os.remove(temp_path)

    def test_parse_spec_file_merges_similar_components(self, spec_file_similar_components):
        """Test that similar swell/wind wave components are not duplicated."""
        analyzer = SpectralAnalyzer(min_separation_period=3.0, min_separation_direction=30.0)
        result = analyzer.parse_spec_file(spec_file_similar_components)

        assert result is not None

        # Should only have 1 component (swell), wind wave filtered as too similar
        # (period diff = 0.5s < 3.0s, direction same)
        assert len(result.peaks) == 1
        assert result.peaks[0].component_type == "swell"


class TestCreateSpectralPeak:
    """Tests for _create_spectral_peak method."""

    def test_create_swell_peak(self):
        """Test creating swell component peak."""
        analyzer = SpectralAnalyzer()

        peak = analyzer._create_spectral_peak(
            height=1.5, period=12.0, direction=315.0, component_type="swell"
        )

        assert peak.height_meters == 1.5
        assert peak.period_seconds == 12.0
        assert peak.direction_degrees == 315.0
        assert peak.component_type == "swell"
        assert peak.frequency_hz == pytest.approx(1.0 / 12.0)
        assert peak.directional_spread == 30.0  # Swell = narrow
        assert peak.confidence == 0.85

    def test_create_wind_wave_peak(self):
        """Test creating wind wave component peak."""
        analyzer = SpectralAnalyzer()

        peak = analyzer._create_spectral_peak(
            height=1.0, period=8.0, direction=45.0, component_type="wind_wave"
        )

        assert peak.component_type == "wind_wave"
        assert peak.directional_spread == 60.0  # Wind waves = broader
        assert peak.confidence == 0.75

    def test_energy_density_calculation(self):
        """Test energy density is calculated correctly."""
        analyzer = SpectralAnalyzer()

        peak = analyzer._create_spectral_peak(
            height=2.0, period=10.0, direction=0, component_type="swell"
        )

        # E ≈ H_s^2 / (16 * bandwidth)
        # E ≈ 4.0 / (16 * 0.03) = 4.0 / 0.48 ≈ 8.33
        expected_energy = (2.0**2) / (16 * 0.03)
        assert peak.energy_density == pytest.approx(expected_energy, rel=0.01)


class TestConvenienceFunction:
    """Tests for analyze_spec_file convenience function."""

    @pytest.fixture
    def valid_spec_file(self):
        """Create a valid .spec file."""
        content = """#YY  MM DD hh mm WVHT  SwH  SwP  WWH  WWP SwD WWD  STEEPNESS  APD MWD
#yr  mo dy hr mn    m    m  sec  m  sec  -  degT     -      sec degT
2025 10 10 15 00  2.0  1.2 14.0  1.1  9.0  NW  N    AVERAGE  11.5  320
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".spec", delete=False) as f:
            f.write(content)
            temp_path = f.name

        yield temp_path

        if os.path.exists(temp_path):
            os.remove(temp_path)

    def test_convenience_function_default_params(self, valid_spec_file):
        """Test convenience function with default parameters."""
        result = analyze_spec_file(valid_spec_file)

        assert result is not None
        assert len(result.peaks) > 0

    def test_convenience_function_custom_params(self, valid_spec_file):
        """Test convenience function with custom parameters."""
        result = analyze_spec_file(valid_spec_file, min_period=10.0, max_components=2)

        assert result is not None
        assert len(result.peaks) <= 2


class TestRealWorldData:
    """Integration tests with real .spec file data."""

    def test_parse_real_spec_file_if_exists(self):
        """Test parsing real .spec file from data directory (if available)."""
        # Path to real data file
        spec_path = Path("/Users/zackjordan/code/surfCastAI/data/www_ndbc_noaa_gov/51201.spec")

        if not spec_path.exists():
            pytest.skip("Real .spec file not available")

        analyzer = SpectralAnalyzer()
        result = analyzer.parse_spec_file(str(spec_path))

        # Basic validation
        assert result is not None
        assert result.buoy_id == "51201"
        assert len(result.timestamp) > 0
        assert result.total_energy >= 0

        # Should have at least one component
        assert len(result.peaks) > 0

        # Dominant peak should be the highest energy
        if result.dominant_peak:
            assert result.dominant_peak == result.peaks[0]
