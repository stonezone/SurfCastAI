# PressureAnalyst Usage Guide

## Overview

The `PressureAnalyst` specialist uses GPT vision API to analyze pressure chart images and extract weather system information for surf forecasting.

## Features

- **Multi-Image Analysis**: Process 4-8 pressure charts in temporal sequence
- **System Detection**: Identify low and high-pressure systems
- **Fetch Analysis**: Calculate fetch direction, distance, duration, and quality
- **Swell Prediction**: Predict swell arrival timing and characteristics
- **Physics-Based Calculations**: Use deep water wave theory for travel time estimates
- **Confidence Scoring**: Based on data completeness, consistency, and quality

## Basic Usage

```python
import asyncio
from src.forecast_engine.specialists import PressureAnalyst

async def analyze_pressure_charts():
    # Initialize analyst
    analyst = PressureAnalyst(config=None)

    # Prepare input data
    data = {
        'images': [
            '/path/to/chart_00z.png',
            '/path/to/chart_06z.png',
            '/path/to/chart_12z.png',
            '/path/to/chart_18z.png',
        ],
        'metadata': {
            'chart_times': [
                '2025-10-07T00:00Z',
                '2025-10-07T06:00Z',
                '2025-10-07T12:00Z',
                '2025-10-07T18:00Z',
            ],
            'region': 'North Pacific'
        }
    }

    # Run analysis
    result = await analyst.analyze(data)

    # Access results
    print(f"Confidence: {result.confidence}")
    print(f"Systems detected: {len(result.data['systems'])}")
    print(f"Predicted swells: {len(result.data['predicted_swells'])}")
    print(f"\nNarrative:\n{result.narrative}")

# Run
asyncio.run(analyze_pressure_charts())
```

## Input Format

### Required Fields

```python
data = {
    'images': [
        '/absolute/path/to/chart1.png',
        '/absolute/path/to/chart2.png',
        # 4-8 images recommended for best results
    ]
}
```

### Optional Fields

```python
data = {
    'images': [...],
    'metadata': {
        'chart_times': [
            '2025-10-07T00:00Z',
            '2025-10-07T06:00Z',
            # ISO 8601 timestamps
        ],
        'region': 'North Pacific'  # Geographic context
    }
}
```

## Output Schema

```python
SpecialistOutput(
    confidence=0.85,  # 0.0-1.0
    data={
        'systems': [
            {
                'type': 'low_pressure',
                'location': '45N 160W',
                'pressure_mb': 990,
                'movement': 'SE at 25kt',
                'intensification': 'strengthening',
                'fetch': {
                    'direction': 'NNE',
                    'distance_nm': 1200,
                    'duration_hrs': 36,
                    'quality': 'strong'
                }
            }
        ],
        'predicted_swells': [
            {
                'source_system': 'low_45N_160W',
                'direction': 'NNE',
                'arrival_time': '2025-10-07T10:00-12:00Z',
                'estimated_height': '7-9ft',
                'estimated_period': '13-15s',
                'confidence': 0.75,
                'travel_time_hrs': 47.5,  # Physics-based calculation
                'distance_nm': 1200,
                'fetch_quality': 'strong'
            }
        ],
        'frontal_boundaries': [
            {
                'type': 'cold_front',
                'location': 'approaching from NW',
                'timing': '2025-10-07T18:00Z'
            }
        ],
        'analysis_summary': {
            'num_low_pressure': 2,
            'num_high_pressure': 1,
            'num_predicted_swells': 3,
            'region': 'North Pacific'
        }
    },
    narrative="Comprehensive analysis of pressure patterns...",
    metadata={
        'num_images': 6,
        'analysis_method': 'gpt_vision',
        'model': 'gpt-5-mini',
        'timestamp': '2025-10-07T12:00:00',
        'region': 'North Pacific',
        'chart_times': [...]
    }
)
```

## Configuration

### Using Config Object

```python
from src.core.config import Config

config = Config('config.yaml')
analyst = PressureAnalyst(config)
```

### Using Environment Variables

```python
import os

os.environ['OPENAI_API_KEY'] = 'your-api-key'
analyst = PressureAnalyst()
```

### Config File Format

```yaml
openai:
  api_key: your-api-key-here
  model: gpt-5-mini
  max_tokens: 3000
```

## Advanced Features

### Swell Travel Time Calculation

The analyst uses deep water wave physics to calculate swell travel time:

```
Group Velocity: Cg = g × T / (4π)
Travel Time: t = distance / Cg

Where:
- g = 9.81 m/s² (gravity)
- T = wave period (seconds)
- distance = great circle distance (meters)
```

Example:
- Distance: 1000 nm (1,852,000 m)
- Period: 14 seconds
- Group Velocity: ~11 m/s
- Travel Time: ~47 hours

### Confidence Scoring

Confidence is calculated from three factors:

1. **Completeness** (20% weight): Number of images
   - 6+ images: 1.0
   - 4-5 images: 0.8
   - 2-3 images: 0.6
   - 1 image: 0.4

2. **Consistency** (30% weight): Fetch quality
   - Strong fetch: 1.0
   - Moderate fetch: 0.7
   - Weak fetch: 0.4

3. **Quality** (50% weight): Swell prediction confidence
   - Based on AI confidence scores
   - Temporal coverage bonus: +10% for 24+ hour span

### Error Handling

```python
try:
    result = await analyst.analyze(data)
except ValueError as e:
    print(f"Input validation error: {e}")
except Exception as e:
    print(f"Analysis error: {e}")
```

## Integration with Forecast Engine

```python
from src.forecast_engine.specialists import PressureAnalyst, BuoyAnalyst

async def generate_forecast(bundle_id):
    # Initialize specialists
    pressure_analyst = PressureAnalyst(config)
    buoy_analyst = BuoyAnalyst(config)

    # Prepare pressure chart data
    chart_paths = glob.glob(f'data/{bundle_id}/charts/*.png')
    pressure_data = {
        'images': sorted(chart_paths),
        'metadata': {
            'region': 'North Pacific'
        }
    }

    # Run analysis
    pressure_result = await pressure_analyst.analyze(pressure_data)

    # Use results in forecast generation
    return {
        'pressure_analysis': pressure_result.data,
        'confidence': pressure_result.confidence
    }
```

## Best Practices

1. **Image Quality**: Use high-resolution pressure charts (1000x1000+ pixels)
2. **Temporal Coverage**: 6-8 images covering 24-48 hours is optimal
3. **Image Sequence**: Order images chronologically (earliest to latest)
4. **File Formats**: PNG and JPEG recommended for best API compatibility
5. **API Key Security**: Use environment variables or secure config files

## Troubleshooting

### No valid images found

```python
# Check image paths exist
from pathlib import Path

for img_path in data['images']:
    if not Path(img_path).exists():
        print(f"Missing: {img_path}")
```

### Vision API timeout

```python
# Reduce number of images or increase timeout
analyst.max_tokens = 5000  # Allow more completion tokens
```

### Low confidence scores

```python
# Check:
# 1. Number of images (6+ recommended)
# 2. Image quality and clarity
# 3. Temporal coverage (24+ hours)
# 4. Clear pressure systems in charts
```

## Testing

Run the test suite:

```bash
python scripts/test_pressure_analyst.py
```

Test with real data:

```bash
# Find a bundle with pressure charts
python src/main.py list

# Test with specific bundle
python scripts/test_pressure_analyst.py --bundle <bundle_id>
```

## API Cost Estimation

GPT-5-mini vision API costs (approximate):

- Input tokens: ~500-1000 per image
- Output tokens: ~2000-3000 per analysis
- Cost per analysis: $0.05-0.15 (6 images)

For production use:
- ~100 forecasts/month
- ~600 images analyzed
- Estimated cost: ~$10-15/month

## Performance

Typical analysis times:
- 4 images: 10-15 seconds
- 6 images: 15-20 seconds
- 8 images: 20-30 seconds

Factors affecting performance:
- Image file size
- Image resolution
- Network latency to OpenAI API
- API load/rate limits

## Future Enhancements

Planned improvements:
1. Caching of analyzed charts
2. Batch processing for multiple regions
3. Historical pattern matching
4. Integration with satellite imagery
5. Real-time system tracking
