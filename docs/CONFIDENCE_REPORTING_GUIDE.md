# Confidence Reporting Guide

## Overview

SurfCastAI now provides detailed, structured confidence reports for every forecast. This guide explains how to access and interpret confidence information.

## Accessing Confidence Reports

### From Forecast Metadata

```python
from src.processing.data_fusion_system import DataFusionSystem
from src.processing.models.confidence import ConfidenceReport

# After running data fusion
fusion_system = DataFusionSystem(config)
result = fusion_system.process(data)
forecast = result.data

# Access full ConfidenceReport (Pydantic model)
report_dict = forecast.metadata['confidence_report']
report = ConfidenceReport(**report_dict)

# Access individual values
overall_score = report.overall_score  # 0.0-1.0
category = report.category            # 'high', 'medium', or 'low'
factors = report.factors              # Dict of contributing factors
breakdown = report.breakdown          # Dict of source-level scores
warnings = report.warnings            # List of quality warnings
```

### Backward Compatible Access

```python
# Legacy format (still supported)
confidence = forecast.metadata['confidence']
score = confidence['overall_score']
category = confidence['category']
```

## Understanding Confidence Scores

### Overall Score (0.0 - 1.0)

The overall confidence score is a weighted combination of five factors:

| Score Range | Category | Interpretation |
|-------------|----------|----------------|
| 0.7 - 1.0   | high     | Strong data quality, high reliability |
| 0.4 - 0.7   | medium   | Acceptable quality, some uncertainty |
| 0.0 - 0.4   | low      | Poor quality, significant uncertainty |

### Contributing Factors

Each factor is scored 0.0-1.0 and contributes to the overall score:

1. **model_consensus** (30% weight)
   - Agreement between different wave models
   - High variance = low consensus
   - Example: 0.90 = models agree closely on wave heights

2. **source_reliability** (25% weight)
   - Average reliability of all data sources
   - Based on freshness, completeness, and accuracy
   - Example: 0.85 = sources are recent and complete

3. **data_completeness** (20% weight)
   - Percentage of expected data sources received
   - Expected: buoys, models, charts, satellite
   - Example: 0.75 = 3 out of 4 data types available

4. **forecast_horizon** (15% weight)
   - Confidence decreases with forecast distance
   - Formula: max(0.5, 1.0 - days * 0.1)
   - Example: 0.80 for 2-day forecast

5. **historical_accuracy** (10% weight)
   - Recent forecast performance vs observations
   - Based on validation database (if available)
   - Example: 0.70 = default when no validation data

### Source Breakdown

Source-level confidence scores show reliability by data type:

```python
breakdown = {
    'buoy_confidence': 0.90,      # Average of all buoy sources
    'pressure_confidence': 0.80,  # Weather/pressure analysis sources
    'model_confidence': 0.85      # Wave model sources
}
```

## Interpreting Warnings

The system generates quality warnings when issues are detected:

### Common Warnings

| Warning | Meaning | Action |
|---------|---------|--------|
| "Very low forecast confidence..." | Overall score < 0.4 | Review all data sources |
| "Low forecast confidence..." | Overall score < 0.6 | Use forecast with caution |
| "Significant disagreement between models" | Model consensus < 0.5 | Check individual model outputs |
| "Limited data sources available" | Data completeness < 0.5 | Verify data collection |
| "Some sources have low reliability" | Source reliability < 0.6 | Check source freshness |
| "No buoy data available" | Zero buoys | Consider delaying forecast |
| "Limited buoy data (only 1 buoy)" | One buoy | Seek additional validation |
| "No model data available" | Zero models | Data collection issue |
| "Long forecast horizon (X days)" | Horizon > 5 days | Reduced confidence expected |

## Using Log Output

### Standard Log Format

```
INFO - Confidence: 0.85 (high) - buoy_confidence: 0.90, model_confidence: 0.85, pressure_confidence: 0.80
```

### Detailed Summary

```python
# Print detailed breakdown to console
print(report.to_detailed_summary())
```

Output:
```
Overall Confidence: 0.85 (high)

Source Breakdown:
  - buoy_confidence: 0.90
  - model_confidence: 0.85
  - pressure_confidence: 0.80

Contributing Factors:
  - data_completeness: 0.80
  - forecast_horizon: 0.90
  - historical_accuracy: 0.80
  - model_consensus: 0.90
  - source_reliability: 0.85

Warnings:
  - Limited buoy data (only 1 buoy)
```

## Display Formatting

### For Web/HTML Output

```python
from src.processing.confidence_scorer import format_confidence_for_display

# Generate markdown-formatted display
display_text = format_confidence_for_display(report)
```

Output:
```markdown
**Forecast Confidence: HIGH** (0.85)

**Confidence Factors:**
- Model Consensus: 0.90
- Source Reliability: 0.85
- Data Completeness: 0.80
- Forecast Horizon: 0.90
- Historical Accuracy: 0.80

**Source Breakdown:**
- Buoy Confidence: 0.90
- Model Confidence: 0.85
- Pressure Confidence: 0.80

**Warnings:**
- Limited buoy data (only 1 buoy)
```

## Programmatic Use

### Filtering Low-Confidence Forecasts

```python
if report.overall_score < 0.4:
    print("WARNING: Very low confidence forecast")
    # Send alert, delay publication, etc.
```

### Checking Specific Issues

```python
# Check for model disagreement
if report.factors['model_consensus'] < 0.5:
    print("Models disagree - review individual model outputs")

# Check data availability
if 'No buoy data available' in report.warnings:
    print("No buoy observations - forecast based on models only")
```

### Monitoring Trends

```python
# Store in validation database for trend analysis
from src.validation.database import ValidationDatabase

db = ValidationDatabase(db_path)
db.save_forecast(
    forecast_id=forecast.forecast_id,
    confidence_report=report.model_dump()  # Serialize for storage
)

# Later: analyze confidence trends over time
recent_reports = db.get_confidence_history(days=7)
avg_confidence = sum(r['overall_score'] for r in recent_reports) / len(recent_reports)
```

## Best Practices

### 1. Always Check Warnings

Before using a forecast, review the warnings list:

```python
if report.warnings:
    for warning in report.warnings:
        logger.warning(f"Forecast quality issue: {warning}")
```

### 2. Set Confidence Thresholds

Define minimum confidence levels for different use cases:

```python
CONFIDENCE_THRESHOLDS = {
    'public_forecast': 0.6,    # Require medium confidence
    'internal_review': 0.4,    # Allow low confidence
    'high_stakes': 0.8         # Require high confidence
}

if report.overall_score < CONFIDENCE_THRESHOLDS['public_forecast']:
    # Don't publish to public
    send_internal_review_only()
```

### 3. Monitor Source Breakdown

Track which sources are reliable:

```python
if report.breakdown.get('buoy_confidence', 0) < 0.5:
    alert_ops_team("Buoy data quality issues")
```

### 4. Log Confidence with Every Forecast

The system automatically logs confidence summaries at INFO level. Ensure your logging configuration captures this:

```python
# In your logging config
logging.getLogger('processing.confidence_scorer').setLevel(logging.INFO)
```

## Troubleshooting

### Low Confidence Scores

**Symptom:** `overall_score < 0.4`

**Diagnosis:**
1. Check `report.warnings` for specific issues
2. Review `report.factors` to identify weak areas
3. Check `report.breakdown` for source-level problems

**Common Causes:**
- Missing buoy data
- Stale data (low freshness scores)
- Model disagreement
- Long forecast horizons
- Incomplete data collection

### Unexpected Warnings

**Symptom:** Warnings appear despite good data

**Diagnosis:**
1. Check factor thresholds in `confidence_scorer.py`
2. Review source scoring logic
3. Verify data collection timing

### Missing Breakdown Values

**Symptom:** `report.breakdown` is empty or missing keys

**Cause:** No sources of that type (e.g., no buoy data collected)

**Solution:** Verify data collection agents are running

## API Reference

### ConfidenceReport Model

```python
class ConfidenceReport(BaseModel):
    overall_score: float  # 0.0-1.0
    category: str         # 'high', 'medium', 'low'
    factors: Dict[str, float]
    breakdown: Dict[str, float]
    warnings: List[str]

    @staticmethod
    def categorize_score(score: float) -> str:
        """Convert numeric score to category."""

    def to_log_summary(self) -> str:
        """Generate concise log summary."""

    def to_detailed_summary(self) -> str:
        """Generate detailed multi-line summary."""

    def model_dump(self) -> dict:
        """Serialize to dictionary (Pydantic method)."""
```

### ConfidenceScorer

```python
class ConfidenceScorer:
    def calculate_confidence(
        self,
        fusion_data: Dict[str, Any],
        forecast_horizon_days: int = 2
    ) -> ConfidenceReport:
        """Calculate overall confidence score."""
```

### Helper Functions

```python
def format_confidence_for_display(report: ConfidenceReport) -> str:
    """Format report for user-friendly display."""
```

---

**Last Updated:** October 10, 2025
**Version:** Phase 4 Implementation
