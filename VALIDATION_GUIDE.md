# SurfCastAI Validation System Guide

## Table of Contents

- [Overview](#overview)
- [How It Works](#how-it-works)
- [Running Validations](#running-validations)
- [Understanding Metrics](#understanding-metrics)
- [Accuracy Targets](#accuracy-targets)
- [Interpreting Results](#interpreting-results)
- [Database Schema](#database-schema)
- [Troubleshooting](#troubleshooting)
- [Best Practices](#best-practices)

## Overview

The SurfCastAI validation system automatically measures forecast accuracy by comparing predicted surf conditions against actual buoy observations. This enables continuous monitoring of forecast quality and drives iterative improvements.

### Key Features

- **Automated Validation:** Compares forecasts against real buoy data 24+ hours after generation
- **Multiple Metrics:** MAE, RMSE, categorical accuracy, direction accuracy
- **Per-Shore Analysis:** Separate validation for North Shore, South Shore, West Shore, East Shore
- **Historical Tracking:** SQLite database stores all validation results for trend analysis
- **Command-Line Interface:** Easy-to-use CLI commands for validation and reporting

### Why Validation Matters

Surf forecasting is inherently challenging due to:
- Complex wave dynamics (refraction, shadowing, fetch)
- Multiple overlapping swells
- Data sparsity (limited buoy coverage)
- Model uncertainties (weather, wave models)

Automated validation enables:
- **Objective Quality Assessment:** Quantifiable accuracy metrics
- **Continuous Improvement:** Identify weak points and track progress
- **Confidence Calibration:** Align confidence scores with actual performance
- **Source Weighting:** Optimize data fusion based on reliability

## How It Works

### Validation Workflow

```
1. FORECAST GENERATION
   └─> Predictions extracted and stored in database
       (forecast_id, shore, predicted height, period, direction)

2. WAITING PERIOD
   └─> System waits 24+ hours for conditions to develop

3. OBSERVATION FETCHING
   └─> Buoy data collected for matching timeframe
       (51201 for North, 51202 for South, etc.)

4. ACCURACY CALCULATION
   └─> Multiple metrics computed:
       - MAE (Mean Absolute Error)
       - RMSE (Root Mean Square Error)
       - Categorical Accuracy (size category match)
       - Direction Accuracy (within 22.5°)

5. RESULT STORAGE
   └─> Validation results saved to database
       Available for reporting and analysis
```

### Data Flow

```
ForecastParser
    ↓
    Extracts predictions from forecast text
    ↓
ValidationDatabase
    ↓
    Stores predictions with forecast_id
    ↓
ForecastValidator (after 24+ hours)
    ↓
    Fetches actual buoy observations
    ↓
BuoyDataFetcher
    ↓
    Returns wave height, period, direction
    ↓
Validation Metrics Computed
    ↓
Results stored in database
```

## Running Validations

### CLI Commands

#### Validate a Specific Forecast

```bash
python src/main.py validate --forecast forecast_20251007_120000
```

**Output:**
```
Validating forecast: forecast_20251007_120000
============================================================

Forecast ID: forecast_20251007_120000
Validated at: 2025-10-08 14:30:00
Predictions validated: 4/4

Metrics:
  MAE (Mean Absolute Error):        1.45 ft  (target: < 2.0 ft)
  RMSE (Root Mean Square Error):    1.78 ft  (target: < 2.5 ft)
  Categorical Accuracy:              75.0%  (target: > 75%)
  Direction Accuracy:                100.0%  (target: > 80%)
  Sample Size:                       4 matches

Validation Status:
  MAE < 2.0 ft:          ✓ PASS
  RMSE < 2.5 ft:         ✓ PASS
  Categorical > 75%:     ✓ PASS
  Direction > 80%:       ✓ PASS

Overall: ✓ PASS
```

#### Validate All Pending Forecasts

```bash
# Validate all forecasts that are 24+ hours old
python src/main.py validate-all

# Use custom waiting period
python src/main.py validate-all --hours-after 48
```

**Output:**
```
Validating all forecasts (24+ hours old)
============================================================

Found 3 forecast(s) to validate:

1. Validating forecast_20251005_060000 (created 2025-10-05 06:00)...
   ✓ Validated: MAE=1.82ft, RMSE=2.15ft, Cat=80%, n=4

2. Validating forecast_20251006_060000 (created 2025-10-06 06:00)...
   ✓ Validated: MAE=1.23ft, RMSE=1.54ft, Cat=100%, n=4

3. Validating forecast_20251007_060000 (created 2025-10-07 06:00)...
   ✓ Validated: MAE=2.15ft, RMSE=2.67ft, Cat=75%, n=4

============================================================
Validation Summary:
============================================================

Total forecasts: 3
Successfully validated: 3
Failed: 0

Aggregate Metrics:
  Average MAE:  1.73 ft
  Average RMSE: 2.12 ft
  Average Categorical Accuracy: 85.0%
  Average Direction Accuracy: 91.7%
```

#### Generate Accuracy Report

```bash
# Report for last 30 days
python src/main.py accuracy-report --days 30

# Report for last 7 days
python src/main.py accuracy-report --days 7
```

**Output:**
```
Accuracy Report (Last 30 Days)
============================================================

Overview:
  Period: Last 30 days
  Validated Forecasts: 15
  Total Validations: 60
  Average Predictions per Forecast: 4.0

Accuracy Metrics:
  MAE (Mean Absolute Error):     1.68 ft  (target: < 2.0 ft)
  RMSE (Root Mean Square Error): 2.07 ft  (target: < 2.5 ft)
  Categorical Accuracy:          81.7%  (target: > 75%)
  Direction Accuracy:            88.3%  (target: > 80%)

Performance Assessment:
  MAE Target:         ✓ PASS
  RMSE Target:        ✓ PASS
  Categorical Target: ✓ PASS
  Direction Target:   ✓ PASS

Per-Shore Breakdown:

  North Shore:
    Validations: 15
    MAE:  1.52 ft
    RMSE: 1.89 ft
    Categorical Accuracy: 86.7%

  South Shore:
    Validations: 15
    MAE:  1.85 ft
    RMSE: 2.25 ft
    Categorical Accuracy: 76.7%

  West Shore:
    Validations: 15
    MAE:  1.62 ft
    RMSE: 2.01 ft
    Categorical Accuracy: 80.0%

  East Shore:
    Validations: 15
    MAE:  1.73 ft
    RMSE: 2.13 ft
    Categorical Accuracy: 83.3%
```

## Understanding Metrics

### MAE (Mean Absolute Error)

**Definition:** Average absolute difference between predicted and observed wave heights.

**Formula:** `MAE = (1/n) * Σ|predicted - observed|`

**Interpretation:**
- MAE = 0: Perfect predictions
- MAE = 1.0: Average error of 1 foot
- MAE = 2.0: Average error of 2 feet (accuracy target threshold)

**Example:**
```
Predictions: [6 ft, 8 ft, 5 ft]
Observations: [7 ft, 7 ft, 6 ft]
Errors: [1 ft, 1 ft, 1 ft]
MAE = (1 + 1 + 1) / 3 = 1.0 ft ✓ GOOD
```

**Why It Matters:** MAE is easy to interpret (average error in feet) and treats all errors equally. It's the most intuitive metric for everyday use.

### RMSE (Root Mean Square Error)

**Definition:** Square root of the average squared difference between predicted and observed values.

**Formula:** `RMSE = sqrt((1/n) * Σ(predicted - observed)²)`

**Interpretation:**
- RMSE = 0: Perfect predictions
- RMSE ≥ MAE: Always true (equality only if all errors are identical)
- RMSE >> MAE: Large outlier errors present

**Example:**
```
Predictions: [6 ft, 8 ft, 5 ft]
Observations: [7 ft, 7 ft, 9 ft]
Errors: [1 ft, 1 ft, 4 ft]
Squared Errors: [1, 1, 16]
RMSE = sqrt((1 + 1 + 16) / 3) = sqrt(6) = 2.45 ft
```

**Why It Matters:** RMSE penalizes large errors more heavily than small errors. A forecast with one 5-foot error is worse than five 1-foot errors. This is important for safety and planning.

### Categorical Accuracy

**Definition:** Percentage of forecasts where the predicted size category matches the observed category.

**Categories:**
- **Flat:** 0-2 ft
- **Small:** 2-4 ft
- **Moderate:** 4-6 ft
- **Good:** 6-10 ft
- **Large:** 10-15 ft
- **Very Large:** 15-20 ft
- **XXL:** 20+ ft

**Interpretation:**
- 100%: All size categories correct
- 75%: 3 out of 4 shores predicted correctly
- 0%: No correct category predictions

**Example:**
```
North Shore: Predicted 8 ft (Good), Observed 7 ft (Good) → ✓
South Shore: Predicted 3 ft (Small), Observed 5 ft (Moderate) → ✗
West Shore: Predicted 4 ft (Moderate), Observed 4.5 ft (Moderate) → ✓
East Shore: Predicted 2 ft (Small), Observed 2.5 ft (Small) → ✓

Categorical Accuracy = 3/4 = 75% → Target Met
```

**Why It Matters:** For many surfers, the size category matters more than exact height. "6-8 ft" vs "8-10 ft" is less important than "Good" vs "Large".

### Direction Accuracy

**Definition:** Percentage of forecasts where predicted swell direction is within 22.5° of observed direction.

**Tolerance:** ±22.5° (one cardinal/ordinal direction)

**Interpretation:**
- 100%: All directions correct within tolerance
- 80%: Target threshold (4 out of 5 correct)
- 0%: All directions off by more than 22.5°

**Example:**
```
Predicted: 330° (NNW)
Observed: 340° (NNW)
Error: 10° → ✓ PASS (within 22.5°)

Predicted: 320° (NW)
Observed: 350° (N)
Error: 30° → ✗ FAIL (exceeds 22.5°)
```

**Direction Reference:**
```
N    = 0° / 360°     E    = 90°        S    = 180°       W    = 270°
NNE  = 22.5°         ESE  = 112.5°     SSW  = 202.5°     WNW  = 292.5°
NE   = 45°           SE   = 135°       SW   = 225°       NW   = 315°
ENE  = 67.5°         SSE  = 157.5°     WSW  = 247.5°     NNW  = 337.5°
```

**Why It Matters:** Swell direction determines which beaches get waves. A 10° error in direction can mean the difference between good surf and flat conditions.

## Accuracy Targets

### Production Targets

These targets represent production-quality forecasting accuracy:

| Metric | Target | Baseline | Notes |
|--------|--------|----------|-------|
| **MAE** | < 2.0 ft | N/A | Average error in wave height |
| **RMSE** | < 2.5 ft | N/A | Penalizes large errors |
| **Categorical** | > 75% | Random = 14% | Size category correct |
| **Direction** | > 80% | Random = 6% | Within 22.5° |

### Target Rationale

**MAE < 2.0 ft:**
- Provides actionable forecast (distinguishes flat/small/good/large)
- Typical error range for experienced human forecasters
- Allows for effective session planning

**RMSE < 2.5 ft:**
- Controls for large outlier errors
- Ensures safety margin (no surprise XXL days predicted as moderate)
- Balances RMSE penalty with real-world variability

**Categorical > 75%:**
- Better than random (14% for 7 categories)
- Matches or exceeds typical surf forecast services
- Provides reliable size class for trip planning

**Direction > 80%:**
- Better than random (6% for 16 directions within 22.5°)
- Critical for beach-specific recommendations
- Allows for accurate shadow/refraction predictions

### Baseline Comparison

**Random Guessing Performance:**
- MAE: ~8 ft (assuming 0-16 ft uniform distribution)
- Categorical Accuracy: ~14% (1/7 categories)
- Direction Accuracy: ~6% (1/16 directions)

**SurfCastAI Improvement:**
- MAE: 4x better than random
- Categorical: 5x better than random
- Direction: 13x better than random

## Interpreting Results

### Pass/Fail Status

Each validation run shows pass/fail for each metric:

```
Validation Status:
  MAE < 2.0 ft:          ✓ PASS
  RMSE < 2.5 ft:         ✓ PASS
  Categorical > 75%:     ✗ FAIL
  Direction > 80%:       ✓ PASS

Overall: ✗ FAIL (1/4 metrics failed)
```

**Overall PASS:** All four metrics meet targets
**Overall FAIL:** One or more metrics below target

### Understanding Failures

**MAE/RMSE Failure:**
- Wave height predictions systematically off
- Check buoy data quality (missing observations?)
- Review model data (was swell event correctly detected?)
- Verify shore-specific calibration

**Categorical Failure:**
- Size categories incorrect (e.g., predicting "Good" when actually "Small")
- Often due to wave period errors (long period = larger faces)
- Check period predictions in forecast
- Review Hawaiian scale conversion (face height = 2x wave height)

**Direction Failure:**
- Swell direction off by more than 22.5°
- Check wind direction vs swell direction (local wind waves?)
- Review buoy MWD (Mean Wave Direction) data quality
- Verify compass direction calculations (wrap-around at 360°)

### Per-Shore Analysis

Different shores have different challenges:

**North Shore:**
- Winter: Large NW-N swells, high confidence
- Summer: Small south swells wrap around, low confidence
- Best validation: October-April

**South Shore:**
- Summer: Long-period south swells, moderate confidence
- Winter: Small NW wrap, low confidence
- Best validation: May-September

**West Shore:**
- Shadowed by Kauai/Niihau for most NW swells
- Exposed to W-WNW swells
- Complex refraction patterns

**East Shore:**
- Trade wind swells year-round
- NE swells in winter
- Most consistent conditions

### Trend Analysis

Track metrics over time to identify patterns:

```bash
# Weekly trends
python src/main.py accuracy-report --days 7
python src/main.py accuracy-report --days 14
python src/main.py accuracy-report --days 21
python src/main.py accuracy-report --days 30
```

**Improving Trends:** MAE/RMSE decreasing over time
- System is learning and improving
- Data fusion weights optimized
- Confidence calibration accurate

**Degrading Trends:** MAE/RMSE increasing over time
- Data quality issues (buoy failures?)
- Seasonal mismatch (summer forecasts worse than winter?)
- Model drift (OpenAI model changed?)

## Database Schema

### Tables

#### `forecasts`
Stores metadata for each forecast:
```sql
CREATE TABLE forecasts (
    forecast_id TEXT PRIMARY KEY,
    created_at REAL NOT NULL,
    bundle_id TEXT,
    model TEXT,
    confidence REAL
)
```

#### `predictions`
Stores individual shore predictions:
```sql
CREATE TABLE predictions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    forecast_id TEXT NOT NULL,
    shore TEXT NOT NULL,
    predicted_height REAL NOT NULL,
    predicted_period REAL,
    predicted_direction REAL,
    FOREIGN KEY (forecast_id) REFERENCES forecasts(forecast_id)
)
```

#### `validations`
Stores validation results:
```sql
CREATE TABLE validations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prediction_id INTEGER NOT NULL,
    forecast_id TEXT NOT NULL,
    validated_at REAL NOT NULL,
    observed_height REAL NOT NULL,
    observed_period REAL,
    observed_direction REAL,
    mae REAL NOT NULL,
    rmse REAL NOT NULL,
    height_error REAL NOT NULL,
    period_error REAL,
    direction_error REAL,
    category_match INTEGER NOT NULL,
    FOREIGN KEY (prediction_id) REFERENCES predictions(id),
    FOREIGN KEY (forecast_id) REFERENCES forecasts(forecast_id)
)
```

### Querying the Database

```python
import sqlite3

# Connect to database
conn = sqlite3.connect('data/validation.db')
cursor = conn.cursor()

# Get all forecasts
cursor.execute("SELECT * FROM forecasts ORDER BY created_at DESC")
forecasts = cursor.fetchall()

# Get validation statistics
cursor.execute("""
    SELECT
        AVG(mae) as avg_mae,
        AVG(rmse) as avg_rmse,
        AVG(category_match) as categorical_accuracy
    FROM validations
    WHERE validated_at >= ?
""", (cutoff_timestamp,))
stats = cursor.fetchone()

conn.close()
```

## Troubleshooting

### Validation Fails: No Predictions Found

**Problem:**
```
Error: No predictions found for forecast forecast_20251007_120000
```

**Cause:** ForecastParser couldn't extract predictions from forecast text

**Solution:**
1. Check forecast file exists: `cat output/forecast_20251007_120000/forecast_*.md`
2. Verify forecast format matches expected structure (North Shore/South Shore sections)
3. Check logs: `tail -100 logs/surfcastai.log | grep -i parser`
4. Re-run forecast generation if needed

### Validation Fails: No Buoy Data

**Problem:**
```
Error: No buoy observations found for shore North Shore at 2025-10-08 06:00
```

**Cause:** Buoy data unavailable for the forecast time window

**Solution:**
1. Check buoy status: Visit https://www.ndbc.noaa.gov/station_page.php?station=51201
2. Verify buoy is operational (not under maintenance)
3. Try wider time window: `--hours-after 48` instead of 24
4. Check BuoyDataFetcher logs for HTTP errors

### Database Corruption

**Problem:**
```
sqlite3.DatabaseError: database disk image is malformed
```

**Solution:**
```bash
# Backup existing database
cp data/validation.db data/validation.db.backup

# Try repair
sqlite3 data/validation.db "PRAGMA integrity_check;"

# If repair fails, delete and recreate
rm data/validation.db
python src/main.py validate-all  # Recreates database
```

### Metrics Don't Match Expectations

**Problem:** MAE/RMSE seem too high or too low

**Solution:**
1. Check buoy-forecast time alignment (are you comparing same time windows?)
2. Verify unit conversions (meters vs feet)
3. Review observed data: `sqlite3 data/validation.db "SELECT * FROM validations LIMIT 10;"`
4. Compare against manual calculations for spot check

## Best Practices

### Validation Frequency

**Daily Validation:**
```bash
# Add to crontab (runs at 8 PM daily)
0 20 * * * cd /path/to/surfCastAI && python src/main.py validate-all >> logs/validation.log 2>&1
```

**Weekly Reports:**
```bash
# Sunday evening summary
0 20 * * 0 cd /path/to/surfCastAI && python src/main.py accuracy-report --days 7 | mail -s "Weekly Forecast Accuracy" you@example.com
```

### Minimum Sample Size

- **Per forecast:** Validate at least 4 predictions (one per shore)
- **Aggregate:** Minimum 10-15 forecasts for reliable statistics
- **Seasonal:** Track winter/summer separately (different swell regimes)

### Seasonal Considerations

**Winter (October-April):**
- Emphasize North Shore validation
- Expect lower South Shore confidence
- Target: MAE < 2.0 for North Shore

**Summer (May-September):**
- Emphasize South Shore validation
- Expect lower North Shore confidence
- Target: MAE < 2.0 for South Shore

### Data Quality Checks

Before validating, verify:
1. Forecast contains predictions for all shores
2. Buoys are operational (check NDBC status)
3. Time window is reasonable (24-48 hours)
4. No major weather events (hurricanes) that invalidate assumptions

### Continuous Improvement

Use validation results to:
1. **Tune Data Fusion Weights:** Increase weight for reliable sources
2. **Calibrate Confidence Scores:** Match forecast confidence to actual accuracy
3. **Identify Weak Spots:** Focus development on high-error scenarios
4. **Track Progress:** Monitor metrics over time to verify improvements

### Example Validation Workflow

```bash
# 1. Generate forecast
python src/main.py run --mode full

# 2. Wait 24-48 hours

# 3. Validate all pending forecasts
python src/main.py validate-all

# 4. Review results
python src/main.py accuracy-report --days 7

# 5. Investigate failures (if any)
sqlite3 data/validation.db "
    SELECT f.forecast_id, p.shore, v.mae, v.category_match
    FROM validations v
    JOIN predictions p ON v.prediction_id = p.id
    JOIN forecasts f ON p.forecast_id = f.forecast_id
    WHERE v.mae > 2.0
    ORDER BY v.mae DESC
    LIMIT 10;
"

# 6. Iterate and improve
```

## Summary

The SurfCastAI validation system provides:
- **Automated accuracy tracking** against real buoy observations
- **Multiple metrics** (MAE, RMSE, categorical, direction)
- **Production targets** (MAE < 2.0 ft, RMSE < 2.5 ft, etc.)
- **Per-shore analysis** for targeted improvements
- **Historical database** for trend analysis
- **Easy CLI commands** for daily validation workflows

By consistently validating forecasts and tracking metrics over time, SurfCastAI continuously improves its forecasting accuracy and provides actionable, reliable surf predictions for Oahu.
