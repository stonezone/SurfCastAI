# Storm Detector Usage Guide

## Overview

The `StormDetector` module extracts storm information from GPT-5 pressure chart analysis text and calculates swell arrival times at Hawaii.

## Features

- **Robust Text Parsing**: Extracts storm data from unstructured GPT-5 output
- **Geographic Flexibility**: Handles multiple coordinate formats (45°N, 45.5N, etc.)
- **Parameter Inference**: Estimates missing storm characteristics using empirical relationships
- **Swell Propagation**: Calculates arrival times and wave heights at Hawaii
- **Pydantic Validation**: Type-safe data models with automatic validation

## Quick Start

```python
from src.processing.storm_detector import StormDetector
from datetime import datetime, timezone

# Initialize detector
detector = StormDetector()

# Sample GPT-5 pressure chart analysis
analysis_text = """
The North Pacific shows a deepening low-pressure system
near Kamchatka at approximately 45°N 155°E. Central pressure
is forecast to drop below 970 mb. Storm-force winds of
50 knots are expected, with a large fetch over 600 nautical miles.
This system is expected to persist for 72 hours.
"""

# Parse for storms
timestamp = datetime.now(timezone.utc).isoformat()
storms = detector.parse_pressure_analysis(analysis_text, timestamp)

# Calculate Hawaii arrivals
arrivals = detector.calculate_hawaii_arrivals(storms)

# Display results
for arrival in arrivals:
    print(f"Storm: {arrival['storm_id']}")
    print(f"Arrival: {arrival['arrival_time']}")
    print(f"Estimated: {arrival['estimated_height_ft']}ft @ {arrival['estimated_period_seconds']:.1f}s")
```

## Data Models

### StormInfo (Pydantic Model)

```python
class StormInfo(BaseModel):
    storm_id: str                          # "kamchatka_20251008_001"
    location: Dict[str, float]             # {'lat': 45.0, 'lon': 155.0}
    wind_speed_kt: float                   # 50.0 (knots)
    central_pressure_mb: Optional[float]   # 970.0 (millibars)
    fetch_nm: Optional[float]              # 600.0 (nautical miles)
    duration_hours: Optional[float]        # 72.0 (hours)
    detection_time: str                    # ISO timestamp
    source: str                            # "pressure_chart_analysis"
    confidence: float                      # 0.0-1.0
```

**Validation:**
- Latitude: -90 to 90 degrees
- Longitude: -180 to 180 degrees
- Wind speed: > 0 knots
- Central pressure: 900-1100 mb (if provided)
- Confidence: 0.0-1.0

## Supported Text Patterns

### Coordinates

```
"Storm at 45°N 155°E"
"Low at 45.5N, 155.2E"
"System at approximately 45°N 155°E"
"latitude 45N longitude 155E"
```

### Wind Speed

```
"winds of 50 knots"
"50kt winds"
"storm-force winds" (defaults to 50kt)
"gale-force winds" (defaults to 40kt)
```

### Central Pressure

```
"central pressure 970 mb"
"pressure of 985 millibars"
"dropping to 965mb"
"drop below 970 mb"
```

### Fetch Length

```
"fetch of 600 nautical miles"
"600nm fetch"
```

### Duration

```
"duration of 72 hours"
"lasting 48 hours"
"36-hour storm"
"persist for 60 hours"
```

## Regional Detection

The detector can infer approximate coordinates from named regions:

- **kamchatka**: (50.0°N, 157.0°E)
- **kuril**: (46.0°N, 152.0°E)
- **aleutian**: (52.0°N, 175.0°W)
- **gulf_alaska**: (55.0°N, 145.0°W)
- **tasman**: (42.0°S, 158.0°E)
- **southern_ocean**: (50.0°S, 140.0°E)
- **new_zealand**: (45.0°S, 170.0°E)

Example:
```
"Deepening low near Kamchatka with strong winds"
→ Infers coordinates: (50.0°N, 157.0°E)
```

## Arrival Predictions

The `calculate_hawaii_arrivals()` method returns detailed arrival information:

```python
{
    'storm_id': 'kamchatka_20251008_001',
    'storm_location': {'lat': 45.0, 'lon': 155.0},
    'storm_wind_speed_kt': 50.0,
    'storm_central_pressure_mb': 970.0,
    'detection_time': '2025-10-08T12:00:00Z',
    'arrival_time': '2025-10-12T08:30:00Z',      # When swell arrives
    'travel_time_hours': 92.5,
    'travel_time_days': 3.9,
    'distance_nm': 2739,                         # Distance traveled
    'estimated_period_seconds': 16.2,            # Wave period
    'estimated_height_ft': 5.8,                  # Wave height
    'group_velocity_knots': 29.6,                # Wave travel speed
    'confidence': 0.9
}
```

## Parameter Estimation

If storm characteristics are missing, the detector estimates them:

### Fetch Estimation (from wind speed)
- **50+ kt**: 600 nm (large storm)
- **40-49 kt**: 400 nm (medium storm)
- **< 40 kt**: 250 nm (small storm)

### Duration Estimation (from pressure)
- **< 970 mb**: 72 hours (deep low)
- **970-990 mb**: 48 hours (medium low)
- **> 990 mb**: 36 hours (weak low)

## Integration with Forecast Engine

```python
from src.processing.storm_detector import StormDetector
from src.forecast_engine.forecast_engine import ForecastEngine

# In ForecastEngine, after pressure chart analysis:
detector = StormDetector()
storms = detector.parse_pressure_analysis(
    pressure_analysis_text,
    timestamp=datetime.now(timezone.utc).isoformat()
)

# Get Hawaii arrivals
arrivals = detector.calculate_hawaii_arrivals(storms)

# Use in forecast context
for arrival in arrivals:
    arrival_date = datetime.fromisoformat(arrival['arrival_time'])
    forecast_context += f"""
    - {arrival['storm_id']}:
      Expected arrival {arrival_date.strftime('%A %B %d')},
      ~{arrival['estimated_height_ft']}ft @ {arrival['estimated_period_seconds']:.0f}s
      (confidence: {arrival['confidence']:.0%})
    """
```

## Error Handling

The detector handles errors gracefully:

```python
# Empty text → empty list (no exception)
storms = detector.parse_pressure_analysis("", timestamp)
assert storms == []

# No storms detected → empty list
storms = detector.parse_pressure_analysis("Clear skies today", timestamp)
assert storms == []

# Invalid coordinates → skipped (logged)
# Missing parameters → estimated
# Pydantic validation errors → logged, storm skipped
```

## Confidence Scoring

Confidence is calculated based on data availability:

- **Base**: 0.5
- **Explicit coordinates**: +0.2
- **Central pressure specified**: +0.15
- **Fetch length specified**: +0.1
- **Duration specified**: +0.05

**Examples:**
- Coordinates only: 0.7
- Coordinates + pressure: 0.85
- All parameters: 1.0

## Testing

Run the comprehensive test suite:

```bash
pytest tests/unit/processing/test_storm_detector.py -v
```

**Coverage:**
- 28 unit tests
- Pydantic model validation
- Text parsing (multiple formats)
- Parameter estimation
- Arrival calculations
- Integration with SwellPropagationCalculator

## Example Output

```
============================================================
DETECTED STORMS
============================================================

Storm ID: kuril_20251008_001
Location: 45.0°N 155.0°E
Wind Speed: 50.0 kt
Central Pressure: 970.0 mb
Fetch: 600.0 nm
Duration: 72.0 hours
Confidence: 1.00

============================================================
HAWAII ARRIVAL PREDICTIONS
============================================================

Storm: kuril_20251008_001
Arrival: Sunday October 12, 08:30 AM UTC
Travel Time: 3.9 days
Distance: 2739 nm
Estimated: 5.8ft @ 16.2s
Confidence: 1.00
============================================================
```

## File Locations

- **Implementation**: `/Users/zackjordan/code/surfCastAI/src/processing/storm_detector.py`
- **Tests**: `/Users/zackjordan/code/surfCastAI/tests/unit/processing/test_storm_detector.py`
- **Swell Propagation**: `/Users/zackjordan/code/surfCastAI/src/utils/swell_propagation.py`

## Performance Notes

- Regex patterns are pre-compiled for efficiency
- No external API calls (pure computation)
- Typical parse time: < 10ms per analysis
- Scales linearly with number of detected storms
