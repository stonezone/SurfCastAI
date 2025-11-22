#!/usr/bin/env python3
"""
Spectral Analyzer for SurfCastAI.

This module parses NDBC .spec files to extract multiple swell components
from spectral wave data. NDBC provides two types of spectral data:

1. Spectral wave summary (.spec) - Pre-analyzed swell/wind wave components
2. Raw spectral data (.data_spec) - Full frequency-direction energy matrices

This implementation focuses on the commonly available spectral wave summary format,
with extensibility for raw spectral analysis if needed.
"""

import logging
from typing import List, Optional, Dict, Any
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field
from pydantic import BaseModel, Field, field_validator
import re


class SpectralPeak(BaseModel):
    """
    Represents a spectral peak (swell or wind wave component).

    Attributes:
        frequency_hz: Peak frequency in Hz
        period_seconds: Wave period (1/frequency)
        direction_degrees: Peak direction in degrees
        energy_density: Energy density in m²/Hz (estimated from height)
        height_meters: Significant height for this component
        directional_spread: Directional spread in degrees (estimated)
        confidence: Confidence score (0.0-1.0)
        component_type: Type of component ('swell' or 'wind_wave')
    """
    frequency_hz: float = Field(gt=0, description="Peak frequency in Hz")
    period_seconds: float = Field(ge=4.0, le=30.0, description="Wave period in seconds")
    direction_degrees: float = Field(ge=0, le=360, description="Peak direction")
    energy_density: float = Field(ge=0, description="Energy density m²/Hz")
    height_meters: float = Field(ge=0, description="Significant wave height")
    directional_spread: float = Field(ge=0, le=180, description="Directional spread")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score")
    component_type: str = Field(default="swell", description="'swell' or 'wind_wave'")

    @field_validator('direction_degrees', mode='before')
    @classmethod
    def normalize_direction(cls, v: float) -> float:
        """Normalize direction to [0, 360)."""
        return v % 360.0


class SpectralAnalysisResult(BaseModel):
    """
    Result of spectral analysis for a single observation.

    Attributes:
        buoy_id: NDBC buoy station ID
        timestamp: ISO 8601 timestamp of observation
        peaks: List of identified spectral peaks (sorted by energy, highest first)
        total_energy: Total wave energy (sum of all components)
        dominant_peak: Primary spectral component
        metadata: Additional metadata about the analysis
    """
    buoy_id: str = Field(min_length=1, description="Buoy station ID")
    timestamp: str = Field(description="ISO 8601 timestamp")
    peaks: List[SpectralPeak] = Field(default_factory=list, description="Identified peaks")
    total_energy: float = Field(ge=0, description="Total wave energy")
    dominant_peak: Optional[SpectralPeak] = Field(default=None, description="Primary component")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

    @field_validator('peaks')
    @classmethod
    def sort_peaks_by_energy(cls, v: List[SpectralPeak]) -> List[SpectralPeak]:
        """Ensure peaks are sorted by energy (highest first)."""
        return sorted(v, key=lambda p: p.energy_density, reverse=True)


class SpectralAnalyzer:
    """
    Analyzer for NDBC spectral wave data.

    This class parses NDBC .spec files and extracts swell components.
    NDBC's spectral wave summary format provides pre-analyzed swell and
    wind wave components, which this analyzer converts into structured data.

    The analyzer can be extended to handle raw spectral matrices if needed.
    """

    # Directional mapping (NDBC uses compass directions)
    DIRECTION_MAP = {
        'N': 0, 'NNE': 22.5, 'NE': 45, 'ENE': 67.5,
        'E': 90, 'ESE': 112.5, 'SE': 135, 'SSE': 157.5,
        'S': 180, 'SSW': 202.5, 'SW': 225, 'WSW': 247.5,
        'W': 270, 'WNW': 292.5, 'NW': 315, 'NNW': 337.5,
        'MM': None  # Missing data
    }

    def __init__(
        self,
        min_period: float = 8.0,  # seconds
        max_period: float = 25.0,
        min_separation_period: float = 3.0,  # seconds between peaks
        min_separation_direction: float = 30.0,  # degrees between peaks
        energy_threshold: float = 0.1,  # 10% of dominant peak
        max_components: int = 5
    ):
        """
        Initialize spectral analyzer with detection parameters.

        Args:
            min_period: Minimum swell period to consider (seconds)
            max_period: Maximum swell period to consider (seconds)
            min_separation_period: Minimum period difference between peaks (seconds)
            min_separation_direction: Minimum directional difference between peaks (degrees)
            energy_threshold: Minimum energy as fraction of dominant peak
            max_components: Maximum number of components to extract
        """
        self.min_period = min_period
        self.max_period = max_period
        self.min_separation_period = min_separation_period
        self.min_separation_direction = min_separation_direction
        self.energy_threshold = energy_threshold
        self.max_components = max_components
        self.logger = logging.getLogger(__name__)

    def parse_spec_file(self, file_path: str) -> Optional[SpectralAnalysisResult]:
        """
        Parse NDBC .spec file and extract swell components.

        NDBC spectral wave summary format provides:
        - WVHT: Significant wave height (m)
        - SwH: Swell height (m)
        - SwP: Swell period (sec)
        - SwD: Swell direction
        - WWH: Wind wave height (m)
        - WWP: Wind wave period (sec)
        - WWD: Wind wave direction
        - APD: Average period (sec)
        - MWD: Mean wave direction (degT)

        Args:
            file_path: Path to .spec file

        Returns:
            SpectralAnalysisResult with identified peaks, or None if parsing fails
        """
        try:
            path = Path(file_path)
            if not path.exists():
                self.logger.error(f"Spec file not found: {file_path}")
                return None

            # Extract buoy ID from filename (e.g., "51201.spec" -> "51201")
            buoy_id = path.stem

            # Read and parse the file
            with open(path, 'r') as f:
                lines = f.readlines()

            if len(lines) < 3:
                self.logger.error(f"Spec file too short: {file_path}")
                return None

            # Parse the latest observation (first data line after headers)
            latest_obs = self._parse_observation_line(lines[2], buoy_id)

            if latest_obs is None:
                self.logger.warning(f"Failed to parse observation from {file_path}")
                return None

            return latest_obs

        except Exception as e:
            self.logger.error(f"Error parsing spec file {file_path}: {e}", exc_info=True)
            return None

    def _parse_observation_line(self, line: str, buoy_id: str) -> Optional[SpectralAnalysisResult]:
        """
        Parse a single observation line from .spec file.

        Format (space-delimited):
        YY MM DD hh mm WVHT SwH SwP WWH WWP SwD WWD STEEPNESS APD MWD

        Args:
            line: Data line to parse
            buoy_id: Buoy station ID

        Returns:
            SpectralAnalysisResult or None if parsing fails
        """
        try:
            parts = line.split()

            if len(parts) < 15:
                self.logger.warning(f"Insufficient fields in observation line (expected 15+, got {len(parts)}): {line.strip()}")
                return None

            # Parse timestamp
            year, month, day, hour, minute = map(int, parts[0:5])
            timestamp = datetime(year, month, day, hour, minute).isoformat() + 'Z'

            # Parse wave parameters
            wvht = self._safe_float(parts[5])  # Total significant wave height
            sw_height = self._safe_float(parts[6])  # Swell height
            sw_period = self._safe_float(parts[7])  # Swell period
            ww_height = self._safe_float(parts[8])  # Wind wave height
            ww_period = self._safe_float(parts[9])  # Wind wave period
            sw_dir_str = parts[10]  # Swell direction (compass)
            ww_dir_str = parts[11]  # Wind wave direction (compass)
            # parts[12] is STEEPNESS (not used)
            apd = self._safe_float(parts[13])  # Average period
            mwd = self._safe_float(parts[14])  # Mean wave direction (degrees)

            # Convert compass directions to degrees
            sw_dir = self._parse_direction(sw_dir_str)
            ww_dir = self._parse_direction(ww_dir_str)

            # Build list of spectral peaks
            peaks: List[SpectralPeak] = []

            # Add swell component if valid
            if (sw_height is not None and sw_height > 0 and
                sw_period is not None and self.min_period <= sw_period <= self.max_period and
                sw_dir is not None):

                swell_peak = self._create_spectral_peak(
                    height=sw_height,
                    period=sw_period,
                    direction=sw_dir,
                    component_type='swell'
                )
                peaks.append(swell_peak)

            # Add wind wave component if valid and sufficiently different
            if (ww_height is not None and ww_height > 0 and
                ww_period is not None and self.min_period <= ww_period <= self.max_period and
                ww_dir is not None):

                # Check if wind wave is sufficiently different from swell
                add_wind_wave = True

                if peaks:  # If we have swell component
                    period_diff = abs(sw_period - ww_period) if sw_period else float('inf')
                    dir_diff = self._directional_difference(sw_dir, ww_dir) if (sw_dir and ww_dir) else float('inf')

                    # Don't add if too similar to swell component
                    if (period_diff < self.min_separation_period or
                        dir_diff < self.min_separation_direction):
                        add_wind_wave = False

                if add_wind_wave:
                    wind_peak = self._create_spectral_peak(
                        height=ww_height,
                        period=ww_period,
                        direction=ww_dir,
                        component_type='wind_wave'
                    )
                    peaks.append(wind_peak)

            # Sort by energy (already handled by Pydantic validator, but explicit here)
            peaks = sorted(peaks, key=lambda p: p.energy_density, reverse=True)

            # Limit to max_components
            peaks = peaks[:self.max_components]

            # Calculate total energy
            total_energy = sum(p.energy_density for p in peaks)

            # Dominant peak is the first (highest energy)
            dominant_peak = peaks[0] if peaks else None

            # Build metadata
            metadata = {
                'total_wave_height': wvht,
                'average_period': apd,
                'mean_direction': mwd,
                'num_components': len(peaks),
                'source': 'ndbc_spec_summary'
            }

            return SpectralAnalysisResult(
                buoy_id=buoy_id,
                timestamp=timestamp,
                peaks=peaks,
                total_energy=total_energy,
                dominant_peak=dominant_peak,
                metadata=metadata
            )

        except Exception as e:
            self.logger.error(f"Error parsing observation line: {e}", exc_info=True)
            return None

    def _create_spectral_peak(
        self,
        height: float,
        period: float,
        direction: float,
        component_type: str
    ) -> SpectralPeak:
        """
        Create a SpectralPeak from wave parameters.

        Args:
            height: Significant wave height (m)
            period: Wave period (seconds)
            direction: Direction (degrees)
            component_type: 'swell' or 'wind_wave'

        Returns:
            SpectralPeak object
        """
        # Calculate frequency
        frequency = 1.0 / period

        # Estimate energy density from height
        # E ≈ (H_s^2) / (16 * bandwidth)
        # For typical spectral bandwidth ~0.03 Hz
        bandwidth = 0.03
        energy_density = (height ** 2) / (16 * bandwidth)

        # Estimate directional spread
        # Swell typically has narrower spread than wind waves
        if component_type == 'swell':
            directional_spread = 30.0  # degrees (narrower)
            confidence = 0.85
        else:
            directional_spread = 60.0  # degrees (broader)
            confidence = 0.75

        return SpectralPeak(
            frequency_hz=frequency,
            period_seconds=period,
            direction_degrees=direction,
            energy_density=energy_density,
            height_meters=height,
            directional_spread=directional_spread,
            confidence=confidence,
            component_type=component_type
        )

    def _parse_direction(self, dir_str: str) -> Optional[float]:
        """
        Parse compass direction string to degrees.

        Args:
            dir_str: Compass direction (e.g., 'N', 'NNE', 'SW')

        Returns:
            Direction in degrees (0-360) or None if invalid
        """
        dir_str = dir_str.strip().upper()
        return self.DIRECTION_MAP.get(dir_str)

    def _safe_float(self, value: str) -> Optional[float]:
        """
        Safely convert string to float.

        Args:
            value: String value

        Returns:
            Float value or None if conversion fails
        """
        try:
            val = float(value)
            # NDBC uses 99.0, 999.0, or MM for missing data
            if val >= 99.0:
                return None
            return val
        except (ValueError, TypeError):
            return None

    def _directional_difference(self, dir1: float, dir2: float) -> float:
        """
        Calculate minimum angular difference between two directions.

        Args:
            dir1: First direction (degrees)
            dir2: Second direction (degrees)

        Returns:
            Minimum angular difference (0-180 degrees)
        """
        diff = abs(dir1 - dir2)
        if diff > 180:
            diff = 360 - diff
        return diff


# Convenience function for integration
def analyze_spec_file(file_path: str, **kwargs) -> Optional[SpectralAnalysisResult]:
    """
    Convenience function to analyze a .spec file with default parameters.

    Args:
        file_path: Path to .spec file
        **kwargs: Optional parameters for SpectralAnalyzer

    Returns:
        SpectralAnalysisResult or None if parsing fails
    """
    analyzer = SpectralAnalyzer(**kwargs)
    return analyzer.parse_spec_file(file_path)
