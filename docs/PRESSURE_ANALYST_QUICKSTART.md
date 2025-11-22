# PressureAnalyst Quick Start Guide

## 30-Second Summary

PressureAnalyst analyzes pressure chart images using GPT vision to identify weather systems and predict swells for Hawaii.

## Installation Check

```bash
# Verify installation
python -c "from src.forecast_engine.specialists import PressureAnalyst; print('✅ Ready')"
```

## Minimal Example

```python
import asyncio
from src.forecast_engine.specialists import PressureAnalyst

async def main():
    analyst = PressureAnalyst()

    result = await analyst.analyze({
        'images': [
            '/path/to/chart_00z.png',
            '/path/to/chart_12z.png',
        ]
    })

    print(f"Confidence: {result.confidence:.2f}")
    print(f"Systems: {len(result.data['systems'])}")
    print(f"Swells: {len(result.data['predicted_swells'])}")

asyncio.run(main())
```

## Required Setup

```bash
# Set API key
export OPENAI_API_KEY='your-key-here'

# Or in Python
import os
os.environ['OPENAI_API_KEY'] = 'your-key-here'
```

## Input Requirements

**Minimum:**
- 2+ pressure chart images (PNG/JPEG)
- Files must exist on disk

**Optimal:**
- 6-8 images
- 6-hour intervals
- 24-48 hour coverage
- High resolution (1000x1000+)

## Output Structure

```python
result.confidence          # 0.0-1.0
result.data['systems']     # List of weather systems
result.data['predicted_swells']  # List of predicted swells
result.narrative          # 500-1000 word analysis
result.metadata           # Analysis details
```

## Common Use Cases

### Basic Analysis
```python
result = await analyst.analyze({'images': [...]})
```

### With Metadata
```python
result = await analyst.analyze({
    'images': [...],
    'metadata': {
        'chart_times': ['2025-10-07T00:00Z', ...],
        'region': 'North Pacific'
    }
})
```

### Extract Specific Data
```python
# Get all low-pressure systems
lows = [s for s in result.data['systems'] if s['type'] == 'low_pressure']

# Get high-confidence swells
good_swells = [s for s in result.data['predicted_swells'] if s['confidence'] > 0.7]

# Get systems with strong fetch
strong_fetch = [s for s in result.data['systems']
                if s.get('fetch', {}).get('quality') == 'strong']
```

## Error Handling

```python
try:
    result = await analyst.analyze(data)
except ValueError as e:
    print(f"Invalid input: {e}")
except Exception as e:
    print(f"Analysis failed: {e}")
```

## Testing

```bash
# Run test suite
python scripts/test_pressure_analyst.py

# Should see:
# ✅ All tests PASSED
```

## Configuration Options

```python
# Default (uses env vars)
analyst = PressureAnalyst()

# With config
from src.core.config import Config
config = Config('config.yaml')
analyst = PressureAnalyst(config)

# Manual settings
analyst = PressureAnalyst()
analyst.openai_model = 'gpt-5-mini'
analyst.max_tokens = 3000
```

## Performance Tips

1. **Batch images**: Process 6-8 images at once
2. **Use PNG**: Slightly better compression
3. **Cache results**: Save to avoid re-analysis
4. **Async calls**: Use asyncio.gather() for parallel analysis

## Troubleshooting

### "No valid image files found"
```python
from pathlib import Path
for img in images:
    print(f"{img}: {Path(img).exists()}")
```

### "OpenAI API error"
```python
# Check API key
import os
print(os.environ.get('OPENAI_API_KEY', 'Not set'))
```

### Low confidence scores
- Add more images (6+ recommended)
- Ensure 24+ hour temporal coverage
- Use high-quality chart images
- Verify clear pressure systems visible

## Integration Example

```python
async def generate_forecast(bundle_id):
    analyst = PressureAnalyst()

    # Get chart paths
    charts = sorted(glob.glob(f'data/{bundle_id}/charts/*.png'))

    # Analyze
    result = await analyst.analyze({'images': charts})

    # Use in forecast
    if result.confidence > 0.7:
        swells = result.data['predicted_swells']
        # Process swells...

    return result
```

## API Costs

GPT-5-mini vision:
- ~$0.10 per 6-image analysis
- ~$10-15/month for 100 forecasts
- Set budget alerts in OpenAI dashboard

## Next Steps

1. **Test**: Run `python scripts/test_pressure_analyst.py`
2. **Integrate**: Add to your forecast pipeline
3. **Monitor**: Check confidence scores
4. **Optimize**: Adjust image count/quality

## Full Documentation

- Usage Guide: `docs/pressure_analyst_usage.md`
- Implementation: `PRESSURE_ANALYST_IMPLEMENTATION.md`
- Code: `src/forecast_engine/specialists/pressure_analyst.py`

## Support

Issues? Check:
1. Test suite passes
2. API key configured
3. Image files exist
4. Python 3.8+ installed
5. OpenAI package installed: `pip install openai`

## Quick Wins

```python
# Get predicted swell arrivals
swells = result.data['predicted_swells']
for swell in swells:
    print(f"{swell['direction']} swell: {swell['estimated_height']}")
    print(f"  Arrival: {swell['arrival_time']}")
    print(f"  Period: {swell['estimated_period']}")
    print(f"  Confidence: {swell['confidence']}")
```

That's it! You're ready to analyze pressure charts. 🌊
