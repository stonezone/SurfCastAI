# Validation Feedback System - Quick Reference

## Overview

The `ValidationFeedback` system analyzes recent forecast performance from the validation database and generates adaptive prompt context for GPT-5 to improve future forecasts.

**Key Features:**
- Queries recent validation data with configurable lookback window (default 7 days)
- Calculates per-shore MAE, RMSE, bias, and categorical accuracy
- Identifies systematic biases (over/underprediction)
- Generates actionable guidance for adaptive forecasting
- Type-safe Pydantic models with automatic validation

## Quick Start

```python
from src.utils.validation_feedback import ValidationFeedback

# Initialize with default settings (7-day lookback)
feedback = ValidationFeedback()

# Get recent performance report
report = feedback.get_recent_performance()

# Generate prompt context for GPT-5
adaptive_context = feedback.generate_prompt_context(report)

# Use in your forecast engine
system_prompt = base_prompt + '\n\n' + adaptive_context
```

## Data Models

### ShorePerformance

Per-shore performance metrics:

```python
class ShorePerformance(BaseModel):
    shore: str                      # Shore name (e.g., 'North Shore')
    validation_count: int           # Number of validations
    avg_mae: float                  # Average MAE in feet (1 decimal)
    avg_rmse: float                 # Average RMSE in feet (1 decimal)
    avg_bias: float                 # Average bias in feet (+ = over, - = under)
    categorical_accuracy: float     # Category accuracy (0.0-1.0, 2 decimals)
```

### PerformanceReport

Overall performance report:

```python
class PerformanceReport(BaseModel):
    report_date: str                         # ISO format timestamp
    lookback_days: int                       # Days analyzed
    overall_mae: float                       # Overall MAE across all shores
    overall_rmse: float                      # Overall RMSE across all shores
    overall_categorical: float               # Overall categorical accuracy
    shore_performance: List[ShorePerformance] # Per-shore breakdowns
    has_recent_data: bool                    # Whether data exists
```

## Usage Examples

### Basic Usage

```python
from src.utils.validation_feedback import ValidationFeedback

feedback = ValidationFeedback(db_path='data/validation.db', lookback_days=7)
report = feedback.get_recent_performance()

if report.has_recent_data:
    print(f"Overall MAE: {report.overall_mae:.1f} ft")

    for shore_perf in report.shore_performance:
        print(f"{shore_perf.shore}: MAE={shore_perf.avg_mae:.1f}, Bias={shore_perf.avg_bias:+.1f}")
else:
    print("No recent validation data available")
```

### Generate Adaptive Prompt Context

```python
feedback = ValidationFeedback()
report = feedback.get_recent_performance()
context = feedback.generate_prompt_context(report)

# Example output:
"""
RECENT FORECAST PERFORMANCE (Last 7 days, 49 validations):
Overall MAE: 1.2 ft (target: <2.0 ft) ✓
Overall RMSE: 1.5 ft
Categorical Accuracy: 85%

Per-Shore Performance:
- North Shore: MAE 0.8 ft, well-calibrated (minimal bias)
- South Shore: MAE 1.5 ft, overpredicting (+0.7 ft avg bias) ⚠️

ADAPTIVE GUIDANCE:
- South Shore forecasts have been running high. Be conservative with height predictions.
- North Shore predictions are accurate and well-calibrated. Maintain current approach.
"""
```

### Integration with ForecastEngine

```python
from src.forecast_engine.forecast_engine import ForecastEngine
from src.utils.validation_feedback import ValidationFeedback

class AdaptiveForecastEngine(ForecastEngine):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.feedback = ValidationFeedback()

    def generate_forecast(self, bundle_id: str) -> Dict[str, Any]:
        # Get recent performance
        report = self.feedback.get_recent_performance()
        adaptive_context = self.feedback.generate_prompt_context(report)

        # Append to system prompt
        if adaptive_context:
            self.system_prompt = self.base_prompt + '\n\n' + adaptive_context

        # Generate forecast as usual
        return super().generate_forecast(bundle_id)
```

### Custom Lookback Window

```python
# Use 14-day lookback for more stable metrics
feedback = ValidationFeedback(lookback_days=14)
report = feedback.get_recent_performance()

# Use 3-day lookback for rapid adaptation
feedback_short = ValidationFeedback(lookback_days=3)
report_short = feedback_short.get_recent_performance()
```

## Adaptive Guidance Rules

The system generates guidance based on these rules:

### Overall Performance
- **MAE > 2.5 ft**: Suggests reviewing data sources and being more conservative

### Per-Shore Bias Detection
- **Bias > +0.5 ft**: Identifies overprediction, suggests conservative approach
- **Bias < -0.5 ft**: Identifies underprediction, suggests upward adjustments
- **MAE < 1.5 ft AND |bias| ≤ 0.3 ft**: Reinforces good performance

### Categorical Accuracy
- **Overall categorical < 70%**: Suggests paying closer attention to size thresholds

## Bias Interpretation

### Bias Values
- **< 0.2 ft**: Well-calibrated (minimal bias)
- **0.2 - 0.5 ft**: Slight over/underprediction
- **> 0.5 ft**: Significant over/underprediction

### Bias Direction
- **Positive bias (+)**: Overpredicting (forecasts too high)
- **Negative bias (-)**: Underpredicting (forecasts too low)

## Command-Line Demo

```bash
# Run demonstration with default settings
python scripts/demo_validation_feedback.py

# Use custom lookback window
python scripts/demo_validation_feedback.py --lookback 14

# Use custom database path
python scripts/demo_validation_feedback.py --db-path /path/to/validation.db
```

## Database Requirements

The system queries these tables from `validation.db`:

### Required Tables
- `forecasts`: Forecast metadata with `forecast_id`, `created_at`
- `predictions`: Forecast predictions with `shore`, `forecast_time`, `valid_time`
- `actuals`: Observed buoy data with `observation_time`, `wave_height`
- `validations`: Comparison results with `mae`, `rmse`, `height_error`, `category_match`

### Key Fields
- `validations.validated_at`: Used for lookback window filtering
- `validations.height_error`: Signed error (predicted - actual) for bias calculation
- `validations.mae`: Mean absolute error per validation
- `validations.category_match`: Boolean for categorical accuracy

## Error Handling

The system gracefully handles common issues:

### Missing Database
```python
feedback = ValidationFeedback(db_path='nonexistent.db')
report = feedback.get_recent_performance()
# Returns empty report with has_recent_data=False
```

### No Recent Data
```python
feedback = ValidationFeedback(lookback_days=7)
report = feedback.get_recent_performance()
if not report.has_recent_data:
    print("No validation data in last 7 days")
```

### Database Errors
```python
try:
    report = feedback.get_recent_performance()
except sqlite3.Error as e:
    logger.error(f"Database error: {e}")
```

## Testing

### Unit Tests
```bash
# Run unit tests (26 tests)
pytest tests/unit/utils/test_validation_feedback.py -v
```

### Integration Tests
```bash
# Run integration tests with realistic scenarios (6 tests)
pytest tests/integration/test_validation_feedback_integration.py -v
```

### Test Coverage
- Pydantic model validation (field types, ranges, rounding)
- Database queries with various data patterns
- Bias detection accuracy
- Guidance generation logic
- Lookback window filtering
- Edge cases (no data, single shore, old data)

## Best Practices

### 1. Regular Updates
Run validation after each forecast cycle to keep feedback current:

```python
# After generating forecasts
feedback = ValidationFeedback(lookback_days=7)
report = feedback.get_recent_performance()

# Use report for next forecast cycle
```

### 2. Appropriate Lookback Window
- **3-7 days**: Rapid adaptation to recent patterns
- **7-14 days**: Balance between recency and stability
- **14-30 days**: More stable metrics, slower to adapt

### 3. Bias Thresholds
Adjust bias thresholds based on your accuracy requirements:

```python
# For high-precision forecasting
BIAS_WARNING_THRESHOLD = 0.3  # ft

# For standard forecasting
BIAS_WARNING_THRESHOLD = 0.5  # ft (default)
```

### 4. Logging
Monitor performance trends over time:

```python
import logging

logging.basicConfig(level=logging.INFO)
feedback = ValidationFeedback()
report = feedback.get_recent_performance()

if report.has_recent_data:
    logger.info(f"Performance: MAE={report.overall_mae:.1f}ft, "
                f"Validations={sum(sp.validation_count for sp in report.shore_performance)}")
```

## Performance Metrics

### MAE Targets
- **< 1.5 ft**: Excellent
- **< 2.0 ft**: Good (target)
- **< 2.5 ft**: Acceptable
- **> 2.5 ft**: Needs improvement

### Categorical Accuracy Targets
- **> 85%**: Excellent
- **> 70%**: Good
- **> 60%**: Acceptable
- **< 60%**: Needs improvement

## Future Enhancements

Potential improvements for future versions:

1. **Time-of-Day Analysis**: Track performance by forecast hour
2. **Weather Pattern Correlation**: Link bias to specific weather conditions
3. **Confidence Weighting**: Weight recent validations more heavily
4. **Trend Detection**: Identify improving/degrading performance over time
5. **Multi-Metric Optimization**: Balance MAE, RMSE, and categorical accuracy
6. **Automated Threshold Tuning**: Dynamically adjust bias thresholds

## Troubleshooting

### Issue: Empty Report Despite Recent Forecasts

**Cause**: Validations not yet created (need 24+ hours of observations)

**Solution**:
```bash
# Wait for observations, then run validation
python scripts/validate_forecasts.py
```

### Issue: Unexpected Bias Values

**Cause**: Check that `height_error` is correctly calculated as (predicted - actual)

**Solution**:
```python
# Verify height_error calculation in validation script
height_error = predicted_height - actual_height  # Should be signed
```

### Issue: Categorical Accuracy Always 0 or 1

**Cause**: Category matching logic may need refinement

**Solution**: Review category thresholds in validation script

## References

- **Implementation**: `/Users/zackjordan/code/surfCastAI/src/utils/validation_feedback.py`
- **Unit Tests**: `/Users/zackjordan/code/surfCastAI/tests/unit/utils/test_validation_feedback.py`
- **Integration Tests**: `/Users/zackjordan/code/surfCastAI/tests/integration/test_validation_feedback_integration.py`
- **Demo Script**: `/Users/zackjordan/code/surfCastAI/scripts/demo_validation_feedback.py`
- **Database Schema**: `/Users/zackjordan/code/surfCastAI/src/validation/schema.sql`
