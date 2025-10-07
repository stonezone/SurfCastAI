# Forecast Parser Documentation

## Overview

The `ForecastParser` module extracts structured predictions from SurfCastAI's natural language forecast markdown files. This enables automated validation of forecast accuracy against observed buoy data.

## Purpose

- Parse forecast markdown to extract height, period, direction predictions
- Convert natural language forecasts to structured data
- Enable automated forecast validation and accuracy tracking
- Support multi-day, multi-shore forecast analysis

## Architecture

### Core Components

1. **ForecastParser** - Main parsing engine
   - Pattern-based text extraction using regex
   - Shore section splitting
   - Multi-day forecast tracking
   - Deduplication and filtering

2. **ForecastPrediction** - Structured prediction data class
   - Shore identification (North/South)
   - Forecast and valid timestamps
   - Height metrics (min, max, average)
   - Period metrics (min, max, average)
   - Direction and category
   - Confidence scoring

### Data Flow

```
Forecast Markdown
       |
       v
ForecastParser.parse_forecast_file()
       |
       v
Split into shore sections
       |
       v
Extract predictions per section
       |
       v
Filter and deduplicate
       |
       v
List[ForecastPrediction]
```

## Usage

### Basic Usage

```python
from pathlib import Path
from src.validation.forecast_parser import ForecastParser

# Initialize parser
parser = ForecastParser()

# Parse a single forecast file
forecast_path = Path('output/forecast_20251006_235037/forecast_20251006_235037.md')
predictions = parser.parse_forecast_file(forecast_path)

# Access prediction data
for pred in predictions:
    print(f"{pred.shore} Day {pred.day_number}: "
          f"{pred.height_min}-{pred.height_max}ft, "
          f"{pred.period}s, {pred.direction}")
```

### Parse Multiple Files

```python
# Parse all forecasts in a directory
forecast_dir = Path('output/forecast_20251006_235037')
results = parser.parse_multiple_forecasts(forecast_dir)

for filename, predictions in results.items():
    print(f"{filename}: {len(predictions)} predictions")
```

### Convenience Function

```python
from src.validation import parse_forecast

# Quick parsing with dictionary output
predictions = parse_forecast('path/to/forecast.md')
for pred in predictions:
    print(pred['shore'], pred['height'], pred['direction'])
```

### Export to JSON

```python
import json

predictions = parser.parse_forecast_file(forecast_path)

# Convert to dictionaries
data = [p.to_dict() for p in predictions]

# Save as JSON
with open('predictions.json', 'w') as f:
    json.dump(data, f, indent=2)
```

## Prediction Data Structure

### ForecastPrediction Fields

| Field | Type | Description |
|-------|------|-------------|
| `shore` | str | "North Shore" or "South Shore" |
| `forecast_time` | datetime | When forecast was issued |
| `valid_time` | datetime | When prediction is valid for |
| `day_number` | int | Day 1, 2, 3, etc. |
| `height` | float | Average wave height (Hawaiian scale) |
| `height_min` | float | Minimum height in range |
| `height_max` | float | Maximum height in range |
| `period` | float | Average period in seconds |
| `period_min` | float | Minimum period in range |
| `period_max` | float | Maximum period in range |
| `direction` | str | Swell direction (N, NW, NE, etc.) |
| `category` | str | Wave category (small, moderate, large, extra_large) |
| `confidence` | float | Parsing confidence (0-1) |

### Category Thresholds (Hawaiian Scale)

- **small**: 0-4 feet
- **moderate**: 4-8 feet
- **large**: 8-12 feet
- **extra_large**: 12+ feet

## Parsing Rules

### Height Extraction

The parser recognizes multiple height patterns:

1. **Hawaiian scale range**: `**6-8 ft** Hawaiian scale`
2. **General range**: `4-6 feet`, `10-12 ft`
3. **Single value**: `approximately 5 ft`

Average height is calculated as `(min + max) / 2`.

### Period Extraction

Period patterns recognized:

1. **Range**: `14-16 second periods`, `12-14 s`
2. **Single value**: `13 s swell`

### Direction Extraction

Recognizes standard compass directions:
- Primary: N, S, E, W
- Secondary: NE, NW, SE, SW
- Tertiary: NNE, NNW, ENE, ESE, SSE, SSW, WSW, WNW

### Shore Section Detection

Detects shore-specific forecasts using headers:
- `## North Shore Forecast`
- `## South Shore Forecast`
- `### North Shore`
- `### South Shore`

### Multi-Day Parsing

Recognizes day markers:
- `Day 1 (Oct 6):`
- `Oct 7:`
- Day numbers increment automatically

### Summary Line Filtering

Focuses on forecast summary lines, filtering out:
- Component breakdowns (lines with `@` symbol)
- Numbered technical lists (`1)`, `2)`, etc.)
- Bullet-point details (`- N @ 6.9 ft`)

Prioritizes lines with:
- "Expected" or "commonly" keywords
- Hawaiian scale references
- Complete height + period patterns

### Deduplication

Prevents duplicate predictions by tracking:
- Shore name
- Day number
- Height range (min, max)

Only unique combinations are added to results.

## Confidence Scoring

Confidence scores (0-1) reflect data completeness:

| Component | Boost | Total |
|-----------|-------|-------|
| Base | - | 0.50 |
| Height range | +0.20 | 0.70 |
| Period data | +0.15 | 0.85 |
| Direction | +0.10 | 0.95 |
| Category | +0.05 | 1.00 |

Higher confidence indicates more complete data extraction.

## Performance

### Parsing Success Rate

Testing on recent forecasts:
- **Success rate**: 100% (20/20 sections)
- **Average predictions per file**: 10-15
- **Parse time**: <100ms per file

### Coverage

Successfully extracts from:
- Multi-day forecasts (Day 1, 2, 3)
- Both North and South Shore sections
- Technical and narrative forecast styles
- Mixed format forecasts

## Error Handling

### Graceful Failures

The parser handles errors gracefully:

```python
try:
    predictions = parser.parse_forecast_file(path)
except FileNotFoundError:
    print(f"File not found: {path}")
except ValueError as e:
    print(f"Invalid format: {e}")
```

### Logging

Parser logs:
- File parsing progress (INFO)
- Extracted prediction counts (INFO)
- Section detection warnings (WARNING)
- Parsing failures (ERROR with traceback)

Configure logging level:

```python
import logging
logging.basicConfig(level=logging.INFO)
```

## Testing

### Unit Tests

Comprehensive test suite in `tests/test_forecast_parser.py`:

- Pattern extraction (height, period, direction)
- Shore section splitting
- Multi-day parsing
- Confidence calculation
- Deduplication
- Malformed content handling

Run tests:

```bash
pytest tests/test_forecast_parser.py -v
```

### Integration Testing

Test on actual forecasts:

```bash
python -m src.validation.forecast_parser output/forecast_20251006_235037/forecast_20251006_235037.md
```

## Examples

See `examples/parse_forecast_example.py` for:
- Single file parsing
- Directory parsing
- JSON export
- Summary statistics

Run example:

```bash
python examples/parse_forecast_example.py
python examples/parse_forecast_example.py <forecast_file.md>
python examples/parse_forecast_example.py <forecast_directory>
```

## Integration with Validation System

The parser integrates with the validation database:

```python
from src.validation import ValidationDatabase, ForecastParser

# Parse forecast
parser = ForecastParser()
predictions = parser.parse_forecast_file(forecast_path)

# Store in validation database
db = ValidationDatabase()
for pred in predictions:
    db.store_forecast_prediction(
        forecast_id=forecast_path.stem,
        shore=pred.shore,
        valid_time=pred.valid_time,
        predicted_height=pred.height,
        predicted_period=pred.period,
        predicted_direction=pred.direction,
    )
```

## Limitations

### Current Limitations

1. **Format dependency**: Requires markdown with clear shore sections
2. **English only**: Pattern matching assumes English text
3. **Hawaiian scale**: Assumes heights in Hawaiian scale (face height / 2)
4. **Date parsing**: Limited to October forecasts (hardcoded month)

### Known Issues

1. Day numbers may be incorrect if forecast doesn't include explicit dates
2. Some detailed technical sections may be parsed as summaries
3. Period extraction may fail for non-standard formats

### Future Enhancements

1. Support for face height in addition to Hawaiian scale
2. Improved date parsing for any month/year
3. Multi-language support
4. Machine learning for summary detection
5. Confidence-based filtering of low-quality extractions

## API Reference

### ForecastParser

#### `__init__()`
Initialize the parser with predefined patterns and thresholds.

#### `parse_forecast_file(file_path: Path) -> List[ForecastPrediction]`
Parse a single forecast markdown file.

**Args:**
- `file_path`: Path to forecast markdown file

**Returns:**
- List of ForecastPrediction objects

**Raises:**
- `FileNotFoundError`: If file doesn't exist
- `ValueError`: If format is invalid

#### `parse_multiple_forecasts(forecast_dir: Path) -> Dict[str, List[ForecastPrediction]]`
Parse all forecast files in a directory.

**Args:**
- `forecast_dir`: Directory containing forecast markdown files

**Returns:**
- Dictionary mapping filenames to prediction lists

**Raises:**
- `FileNotFoundError`: If directory doesn't exist

### ForecastPrediction

#### `to_dict() -> Dict`
Convert prediction to dictionary with ISO format timestamps.

**Returns:**
- Dictionary with all prediction fields

### Convenience Functions

#### `parse_forecast(forecast_path: str) -> List[Dict]`
Quick parsing with dictionary output.

**Args:**
- `forecast_path`: Path to forecast file

**Returns:**
- List of prediction dictionaries

## Contributing

To extend the parser:

1. Add new patterns to `PATTERNS` dictionary
2. Create extraction method (e.g., `_extract_tide()`)
3. Update `_parse_shore_section()` to call new method
4. Add fields to `ForecastPrediction` dataclass
5. Update confidence calculation if needed
6. Add unit tests for new functionality

## License

Part of the SurfCastAI project.

## Support

For issues or questions:
1. Check existing tests for usage examples
2. Review example scripts in `examples/`
3. Enable debug logging for detailed output
4. File issues with sample forecast and error message

---

*Last updated: October 2025*
