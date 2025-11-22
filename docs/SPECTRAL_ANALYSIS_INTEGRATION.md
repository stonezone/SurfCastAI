# Spectral Analysis Integration Guide

## Overview

The `SpectralAnalyzer` module provides robust parsing and analysis of NDBC spectral wave data (.spec files), extracting multiple swell components with validated Pydantic models.

## Quick Start

### Basic Usage

```python
from src.processing.spectral_analyzer import analyze_spec_file

# Parse a .spec file with default parameters
result = analyze_spec_file('data/www_ndbc_noaa_gov/51201.spec')

if result:
    print(f"Buoy: {result.buoy_id}")
    print(f"Components: {len(result.peaks)}")
    print(f"Dominant: {result.dominant_peak.height_meters}m @ {result.dominant_peak.period_seconds}s")
```

### Custom Parameters

```python
from src.processing.spectral_analyzer import SpectralAnalyzer

analyzer = SpectralAnalyzer(
    min_period=10.0,              # Only consider long-period swell (default: 8.0s)
    max_period=20.0,              # Maximum period (default: 25.0s)
    min_separation_period=4.0,    # Minimum period difference between peaks (default: 3.0s)
    min_separation_direction=45.0, # Minimum directional difference (default: 30.0°)
    max_components=3              # Maximum number of components (default: 5)
)

result = analyzer.parse_spec_file('path/to/file.spec')
```

## Data Models

### SpectralPeak

Represents a single swell or wind wave component:

```python
class SpectralPeak(BaseModel):
    frequency_hz: float           # Peak frequency (Hz)
    period_seconds: float         # Wave period (4.0-30.0s)
    direction_degrees: float      # Direction (0-360°, auto-normalized)
    energy_density: float         # Energy density (m²/Hz)
    height_meters: float          # Significant height (m)
    directional_spread: float     # Directional spread (degrees)
    confidence: float             # Confidence score (0.0-1.0)
    component_type: str           # 'swell' or 'wind_wave'
```

**Validation:**
- Period: 4.0s ≤ period ≤ 30.0s
- Direction: Automatically normalized to [0, 360)
- Confidence: 0.0 ≤ confidence ≤ 1.0

### SpectralAnalysisResult

Complete analysis result for a single observation:

```python
class SpectralAnalysisResult(BaseModel):
    buoy_id: str                     # NDBC buoy station ID
    timestamp: str                   # ISO 8601 timestamp
    peaks: List[SpectralPeak]        # Sorted by energy (highest first)
    total_energy: float              # Total wave energy
    dominant_peak: Optional[SpectralPeak]  # Primary component
    metadata: Dict[str, Any]         # Additional data
```

**Automatic Features:**
- Peaks are automatically sorted by energy (highest first)
- Dominant peak is set to the highest energy component
- Metadata includes total wave height, average period, mean direction

## Integration with DataFusionSystem

The SpectralAnalyzer can be integrated into `DataFusionSystem._extract_buoy_events()` to extract multiple swell components from .spec files:

### Example Integration

```python
from src.processing.spectral_analyzer import SpectralAnalyzer

class DataFusionSystem:
    def __init__(self, config: Config):
        super().__init__(config)
        self.spectral_analyzer = SpectralAnalyzer(
            min_period=8.0,  # Match existing min_period from config
            max_components=5
        )

    def _extract_buoy_events_with_spectral(self, buoy_data_list: List[BuoyData]) -> List[SwellEvent]:
        """Enhanced buoy event extraction using spectral analysis."""
        events = []

        for buoy_data in buoy_data_list:
            # Try spectral analysis if .spec file available
            spec_path = f"data/www_ndbc_noaa_gov/{buoy_data.station_id}.spec"
            spectral_result = self.spectral_analyzer.parse_spec_file(spec_path)

            if spectral_result and spectral_result.peaks:
                # Create event from spectral analysis
                event = self._create_event_from_spectral(spectral_result, buoy_data)
                events.append(event)
            else:
                # Fall back to existing single-component extraction
                event = self._extract_single_component_event(buoy_data)
                if event:
                    events.append(event)

        return events

    def _create_event_from_spectral(
        self,
        spectral_result: SpectralAnalysisResult,
        buoy_data: BuoyData
    ) -> SwellEvent:
        """Create SwellEvent with multiple components from spectral analysis."""
        dominant = spectral_result.dominant_peak

        event = SwellEvent(
            event_id=f"buoy_{spectral_result.buoy_id}_{spectral_result.timestamp[:10]}",
            start_time=spectral_result.timestamp,
            peak_time=spectral_result.timestamp,
            primary_direction=dominant.direction_degrees,
            significance=self._calculate_significance(dominant.height_meters, dominant.period_seconds),
            hawaii_scale=self._convert_to_hawaii_scale(dominant.height_meters),
            source="buoy_spectral",
            metadata={
                "station_id": spectral_result.buoy_id,
                "buoy_name": buoy_data.name,
                "confidence": dominant.confidence,
                "type": "observed_spectral",
                "num_components": len(spectral_result.peaks),
                "total_energy": spectral_result.total_energy
            }
        )

        # Add all spectral peaks as primary/secondary components
        for i, peak in enumerate(spectral_result.peaks):
            component = SwellComponent(
                height=peak.height_meters,
                period=peak.period_seconds,
                direction=peak.direction_degrees,
                confidence=peak.confidence,
                source="buoy_spectral",
                metadata={
                    "component_type": peak.component_type,
                    "energy_density": peak.energy_density,
                    "directional_spread": peak.directional_spread
                }
            )

            if i == 0:
                event.primary_components.append(component)
            else:
                event.secondary_components.append(component)

        return event
```

## NDBC .spec File Format

The SpectralAnalyzer parses NDBC's "spectral wave summary" format, which provides pre-analyzed swell and wind wave components:

### Format Structure

```
#YY  MM DD hh mm WVHT  SwH  SwP  WWH  WWP SwD WWD  STEEPNESS  APD MWD
#yr  mo dy hr mn    m    m  sec    m  sec  -  degT     -      sec degT
2025 10 11 03 56  1.2  0.6 11.1  1.1  9.9   N NNE    AVERAGE  8.4  12
```

### Field Definitions

| Field | Description | Units |
|-------|-------------|-------|
| YY MM DD hh mm | Timestamp | Year, Month, Day, Hour, Minute |
| WVHT | Total significant wave height | meters |
| SwH | Swell height | meters |
| SwP | Swell period | seconds |
| WWH | Wind wave height | meters |
| WWP | Wind wave period | seconds |
| SwD | Swell direction | compass (N, NE, etc.) |
| WWD | Wind wave direction | compass |
| STEEPNESS | Wave steepness category | text |
| APD | Average period | seconds |
| MWD | Mean wave direction | degrees true |

### Missing Data Markers

NDBC uses the following markers for missing/invalid data:
- `99.0`, `999.0`: Missing numeric value
- `MM`: Missing direction

The SpectralAnalyzer automatically filters these out.

## Component Filtering

The analyzer applies intelligent filtering to extract meaningful swell components:

### Swell Component Criteria
- Period: `min_period` ≤ period ≤ `max_period`
- Height: > 0 meters
- Direction: Valid compass direction
- Component type: "swell"
- Confidence: 0.85 (high confidence for observed data)

### Wind Wave Component Criteria
- Period: `min_period` ≤ period ≤ `max_period`
- Height: > 0 meters
- Direction: Valid compass direction
- Separation: Must differ from swell by:
  - Period: ≥ `min_separation_period` seconds
  - Direction: ≥ `min_separation_direction` degrees
- Component type: "wind_wave"
- Confidence: 0.75 (slightly lower than swell)

### Sorting and Limiting
- Peaks are sorted by energy density (highest first)
- Limited to `max_components` (default: 5)
- Dominant peak is always the highest energy component

## Physics-Based Calculations

### Energy Density Estimation

The analyzer estimates spectral energy density from significant wave height:

```
E ≈ H_s² / (16 × Δf)
```

Where:
- `E` = Energy density (m²/Hz)
- `H_s` = Significant wave height (m)
- `Δf` = Spectral bandwidth ≈ 0.03 Hz (typical for buoy observations)

### Directional Spread

Estimated based on component type:
- **Swell**: 30° (narrow directional spread)
- **Wind waves**: 60° (broader directional spread)

These values reflect typical ocean wave characteristics.

## Error Handling

The analyzer provides robust error handling:

### File Not Found
```python
result = analyzer.parse_spec_file('/nonexistent/file.spec')
# result = None
```

### Parse Errors
```python
# Logs error with traceback, returns None
result = analyzer.parse_spec_file('corrupted.spec')
# result = None
```

### Missing Data
```python
# Automatically filters components with missing/invalid data
# Returns SpectralAnalysisResult with available components
result = analyzer.parse_spec_file('partial_data.spec')
# result.peaks may be empty if no valid components
```

## Testing

Comprehensive unit tests are available:

```bash
# Run all spectral analyzer tests
pytest tests/unit/processing/test_spectral_analyzer.py -v

# Run specific test class
pytest tests/unit/processing/test_spectral_analyzer.py::TestSpectralPeakModel -v

# Run with coverage
pytest tests/unit/processing/test_spectral_analyzer.py --cov=src/processing/spectral_analyzer
```

### Test Coverage

- ✅ Pydantic model validation (period, direction, confidence)
- ✅ .spec file parsing (valid, missing data, malformed)
- ✅ Component extraction (swell, wind waves, filtering)
- ✅ Peak detection and sorting
- ✅ Error handling (file not found, parse errors)
- ✅ Real-world data validation

## Performance Considerations

- **File I/O**: Reads entire file into memory (typical .spec files are ~50KB)
- **Parsing**: O(n) for n lines in file
- **Sorting**: O(m log m) for m components (typically m ≤ 5)
- **Validation**: Pydantic validation adds minimal overhead

**Typical Performance:**
- Parse time: <10ms per file
- Memory: ~1KB per SpectralAnalysisResult

## Future Enhancements

### Raw Spectral Matrix Support

The current implementation focuses on NDBC's pre-analyzed spectral wave summary format. For raw spectral energy matrices (if available), the architecture supports extension:

```python
def parse_raw_spectral_matrix(self, file_path: str) -> Optional[SpectralAnalysisResult]:
    """
    Parse raw frequency-direction energy density matrix.

    Algorithm:
    1. Load spectral matrix (frequency × direction)
    2. Apply Gaussian smoothing (reduce noise)
    3. Find local maxima (scipy.signal.find_peaks_2d)
    4. Filter by energy threshold
    5. Calculate component heights from energy integrals
    6. Sort by energy and apply separation criteria
    """
    pass  # To be implemented when raw spectral data becomes available
```

### Directional Spectrum Analysis

For full directional spectra:
- 2D peak finding with prominence thresholds
- Bandwidth integration for height calculation
- Directional moment calculations for spread estimation

## References

- [NDBC Technical Documentation](https://www.ndbc.noaa.gov/docs/)
- [Spectral Wave Data Formats](https://www.ndbc.noaa.gov/measdes.shtml)
- Ocean Wave Spectra (Tucker & Pitt, 2001)

## Support

For issues or questions:
1. Check test suite: `tests/unit/processing/test_spectral_analyzer.py`
2. Run demo script: `python scripts/demo_spectral_analyzer.py`
3. Review source code: `src/processing/spectral_analyzer.py`
