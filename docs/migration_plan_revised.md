# SwellGuy to SurfCastAI Feature Migration Plan (REVISED)
**Comprehensive Integration Strategy**
**Date:** October 5, 2025
**Version:** 2.0 (Post-Review)

---

## Executive Summary

**Goal:** Port SwellGuy's most valuable features to SurfCastAI in measured, incremental phases

**Strategy:** Five-phase migration over 8-14 weeks
- **Phase 0:** Fix Current Issues + Baseline - 1 week, 4-6 hours ⭐ NEW
- **Phase 1:** Validation Framework - 2 weeks, 16-24 hours
- **Phase 2:** High-Value Data Sources - 2-3 weeks, 24-34 hours (expanded)
- **Phase 3:** Processing + Calibration - 2-3 weeks, 24-34 hours (expanded)
- **Phase 4:** Advanced Features (Optional) - 2-4 weeks, 30-50 hours

**Total Effort:** 64-124 hours (depending on phases completed)

**Key Principles:**
1. ✅ Fix existing issues BEFORE adding new features
2. ✅ Measure everything - establish clean baseline first
3. ✅ Maintain SurfCastAI's simplicity and production stability
4. ✅ Keep only features that improve accuracy >5%
5. ✅ Preserve cost efficiency (<$0.02/forecast target)
6. ✅ All phases are reversible

---

## Success Criteria

**Overall Goals:**
- [ ] Forecast accuracy improves >10% (MAE reduction)
- [ ] Cost remains <$0.02/forecast
- [ ] System complexity increases <50%
- [ ] Maintenance effort increases <30%
- [ ] Production stability maintained

**Phase-by-Phase:**
- **Phase 0:** Fix current data gaps, establish clean baseline
- **Phase 1:** Establish measurement infrastructure
- **Phase 2:** Add 3 critical data sources + attribution, improve accuracy >5%
- **Phase 3:** Add quality filtering + height calibration, improve accuracy another 5%
- **Phase 4:** Only if Phases 1-3 successful and accuracy >10% total

---

## ⭐ Phase 0: Fix Current Issues + Baseline (NEW)

**Duration:** 1 week
**Effort:** 4-6 hours
**Priority:** CRITICAL - DO THIS FIRST

### Why Phase 0 is Essential

**Current State Issues (from DATA_PIPELINE_FIXES.md):**
- ❌ Weather data: 0 files collected (agent disabled/failing)
- ❌ Wave model data: 0 files collected (agent disabled/failing)
- ❌ Missing source attribution (GPT uncertain about data reliability)
- ❌ Deep-water heights vs surf faces (7.5 ft vs 8-12 Hs mismatch)

**Why Fix These First:**
1. They're already 80% implemented in SurfCastAI
2. GPT flagged these in recent forecasts
3. Lower risk than adding new features
4. Establishes clean baseline for Phase 1 validation
5. Quick wins (4-6 hours total)

### 0.1 Enable Weather Agent (30 minutes)

**Current Issue:** Weather agent exists but not collecting data

**Fix:**
```bash
# Check config
grep -A 5 "weather_agent" config.yaml

# Enable in config.yaml
data_sources:
  weather:
    enabled: true
    sources:
      - "https://tgftp.nws.noaa.gov/data/forecasts/marine/..."

# Test collection
python src/main.py run --mode collect
ls data/latest_bundle/weather/
```

**Success Criteria:**
- [ ] Weather files collected (>0 files)
- [ ] Wind speed data available in forecasts
- [ ] No collection errors

---

### 0.2 Enable Wave Model Agent (30 minutes)

**Current Issue:** Wave model agent exists but not collecting data

**Fix:**
```bash
# Check config
grep -A 5 "model_agent" config.yaml

# Enable wave model sources
data_sources:
  models:
    enabled: true
    sources:
      - wavewatch3
      - swan

# Test collection
python src/main.py run --mode collect
ls data/latest_bundle/models/
```

**Success Criteria:**
- [ ] Model files collected (>0 files)
- [ ] Model data in fused_forecast.json
- [ ] No processing errors

---

### 0.3 Add Source Attribution (1 hour)

**Current Issue:** SwellEvents lack source details, GPT uncertain

**Implementation:**
```python
# src/processing/data_fusion_system.py

# BEFORE:
event = SwellEvent(
    event_id=event_id,
    source="buoy",
    ...
)

# AFTER:
event = SwellEvent(
    event_id=event_id,
    source="buoy",
    metadata={
        'source_details': {
            'buoy_id': buoy_id,
            'observation_time': latest_time,
            'data_quality': quality_score,
            'source_type': 'NDBC_realtime'
        }
    },
    ...
)
```

**Update Prompt Templates:**
```python
# src/forecast_engine/prompt_templates.py

# Add source attribution to swell descriptions
f"- {direction} swell: {height} ft @ {period}s (Source: Buoy {buoy_id}, observed {time})"
```

**Success Criteria:**
- [ ] All swell events have source_details
- [ ] Forecasts show data provenance
- [ ] GPT stops complaining about uncertain data

---

### 0.4 Establish Baseline (2-3 hours)

**Run Period:** 7-14 days of clean forecasts

**Data to Collect:**
```yaml
baseline_metrics:
  # Automated
  avg_cost_per_forecast: $0.037
  avg_tokens: 24900
  avg_api_calls: 5
  collection_success_rate: 0.95

  # Manual (compare to Pat Caldwell or buoy obs)
  subjective_accuracy: "Good/Fair/Poor for 3-5 forecasts"
  common_errors: ["Wind speed missing", "Height scaling off"]
  success_patterns: ["Direction accurate", "Timing good"]
```

**Process:**
```bash
# Run daily forecasts for 1-2 weeks
for i in {1..14}; do
    python src/main.py run --mode full
    sleep 86400  # 24 hours
done

# Manually review 3-5 forecasts:
# - Compare to Pat Caldwell's forecasts
# - Compare to actual buoy observations
# - Note what works, what doesn't
```

**Success Criteria:**
- [ ] 7+ clean forecast runs
- [ ] Cost/token metrics documented
- [ ] Manual accuracy assessment complete
- [ ] Baseline documented in BASELINE_METRICS.md

---

## Phase 1: Validation Framework

**Duration:** 2 weeks
**Effort:** 16-24 hours
**Priority:** CRITICAL

**Prerequisites:** Phase 0 complete, clean baseline established

### 1.1 Validation Database (3 hours)

```python
# src/validation/forecast_tracker.py

CREATE TABLE forecasts (
    forecast_id TEXT PRIMARY KEY,
    created_at TIMESTAMP,
    model_version TEXT,
    total_tokens INTEGER,
    model_cost_usd REAL,
    forecast_text TEXT
);

CREATE TABLE predictions (
    forecast_id TEXT,
    valid_date DATE,
    shore TEXT,
    predicted_height_min REAL,
    predicted_height_max REAL,
    predicted_period_min REAL,
    predicted_period_max REAL,
    predicted_direction_min REAL,
    predicted_direction_max REAL
);

CREATE TABLE actuals (
    observation_date DATE,
    buoy_id TEXT,
    wave_height REAL,
    wave_period REAL,
    wave_direction REAL,
    data_source TEXT
);

CREATE TABLE validation_results (
    forecast_id TEXT,
    validation_date DATE,
    shore TEXT,
    mae_height REAL,
    mae_period REAL,
    mae_direction REAL,
    within_range_height BOOLEAN,
    within_range_period BOOLEAN,
    categorical_match BOOLEAN,
    accuracy_score REAL
);
```

### 1.2 Buoy Data Collector (3 hours)

```python
# src/validation/buoy_collector.py

class ValidationBuoyCollector:
    """Collect buoy data for validation (separate from forecast collection)"""

    VALIDATION_BUOYS = {
        '51201': 'NW Hawaii',
        '51202': 'Pauwela Molokai',
        '51001': 'NW Hawaii 350nm',
        '51101': 'Hilo'
    }

    async def collect_daily_observations(self, date=None):
        """Fetch observations for validation"""
        # Similar to existing buoy agent but for validation
        pass

    def store_observations(self, observations):
        """Store in validation database"""
        pass
```

### 1.3 Validation Runner (4 hours)

```python
# src/validation/validator.py

class ForecastValidator:
    """Validate forecasts against actual conditions"""

    def extract_predictions_from_forecast(self, forecast_text):
        """Parse forecast text to extract numeric predictions"""
        # Use regex or GPT to extract:
        # - Height ranges (e.g., "8-12 ft")
        # - Period ranges (e.g., "11-13s")
        # - Directions (e.g., "NNW 320-340°")
        pass

    def match_to_actuals(self, predictions, actuals):
        """Match forecast predictions to buoy observations"""
        pass

    def calculate_metrics(self, predictions, actuals):
        """Calculate MAE, accuracy scores"""
        return {
            'mae_height': 1.2,
            'mae_period': 1.5,
            'within_range_pct': 0.73,
            'accuracy_score': 0.78
        }
```

### 1.4 CLI Integration (1 hour)

```bash
# New commands in src/main.py

python src/main.py validate --days 7    # Run validation for past 7 days
python src/main.py accuracy --days 30   # Show accuracy report
python src/main.py baseline             # Show baseline metrics
```

### 1.5 Monitoring Dashboard (5 hours)

```python
# src/monitoring/dashboard.py

class MonitoringDashboard:
    """Real-time system health monitoring"""

    def get_health_status(self):
        return {
            'status': 'healthy|degraded|unhealthy',
            'collection_success_rate': 0.95,
            'avg_forecast_cost': 0.037,
            'accuracy_trend': 'improving|stable|degrading',
            'active_alerts': []
        }
```

**Success Criteria:**
- [ ] Validation database operational
- [ ] Buoy data collected daily
- [ ] Accuracy metrics calculated
- [ ] Baseline MAE established
- [ ] Monitoring dashboard accessible

---

## Phase 2: High-Value Data Sources

**Duration:** 2-3 weeks
**Effort:** 24-34 hours (expanded from 20-30)
**Priority:** HIGH

**Prerequisites:** Phase 1 complete, baseline measured

### 2.1 NOAA Text Bulletins (6-8 hours)

```python
# src/agents/noaa_text_agent.py

PRODUCTS = {
    'OSO': 'Open Ocean Forecast',
    'OFFSHORE': 'Offshore Waters Forecast',
    'COASTAL': 'Coastal Waters Forecast',
    'HFO_DISCUSSION': 'HFO Forecaster Discussion',
    'TWOCP': 'Tropical Outlook Central Pacific'
}

async def fetch_all_bulletins(bundle_path):
    """Fetch NOAA text products"""
    for product_id, name in PRODUCTS.items():
        url = f'https://tgftp.nws.noaa.gov/data/raw/{product_id}'
        text = await fetch(url)
        save(bundle_path / 'noaa_text' / f'{product_id}.txt', text)
```

**Value:** +2-3% accuracy improvement expected

---

### 2.2 OPC Surface Analysis Charts (4-6 hours)

```python
# src/agents/opc_chart_agent.py

CHARTS = {
    'surface_analysis': 'Current surface analysis',
    'surface_24hr': '24hr surface forecast',
    'surface_48hr': '48hr surface forecast',
    'surface_96hr': '96hr surface forecast'
}

async def fetch_opc_charts(bundle_path):
    """Fetch OPC pressure charts"""
    for chart_id, name in CHARTS.items():
        url = f'https://ocean.weather.gov/P_sfc_{chart_id}_color.png'
        image = await fetch(url)
        save(bundle_path / 'charts' / 'opc' / f'{chart_id}.png', image)
```

**Value:** +1-2% accuracy improvement expected

---

### 2.3 ⭐ Enhanced Source Attribution (4 hours) - NEW

**Why Added:** Addresses current GPT uncertainty about data reliability

```python
# Extend src/processing/data_fusion_system.py

class SourceAttributor:
    """Add detailed source attribution to all data"""

    def attribute_swell_event(self, event, sources):
        """Add comprehensive source info"""
        event.metadata['attribution'] = {
            'primary_sources': [
                {
                    'type': 'buoy',
                    'id': '51201',
                    'observation_time': '2025-10-05T12:00Z',
                    'reliability_score': 0.95,
                    'data_quality': 'excellent'
                }
            ],
            'supporting_sources': [...],
            'confidence_basis': 'Multi-buoy agreement + model validation'
        }
```

**Value:** +1% accuracy improvement expected (GPT more confident)

---

### 2.4 Extended NDBC Buoy Coverage (3-4 hours)

**Current Buoys:** 51001, 51002, 51004, 51101, 51201, 51202, 51207, 51211, 51212

**Buoys to Add:**
```python
ADDITIONAL_BUOYS = {
    '46001': 'Gulf of Alaska (850nm NW)',        # Early North Pacific warning
    '46002': 'Oregon Coast (220nm NW)',           # North Pacific tracking
    '46005': 'Washington Coast (300nm NW)',       # North Pacific tracking
    '46006': 'SE Papa (600nm NW)',                # Long-range North Pacific
    '51003': 'South of Kauai',                    # South swell early warning
    '51004': 'SE Hawaii'                          # Additional south coverage
}
```

**Why These:** Provide 24-48 hour early warning for swell arrivals

**Value:** +1% accuracy improvement expected

**Phase 2 Total Expected Improvement:** +5-7% accuracy

---

## Phase 3: Processing Enhancements + Calibration

**Duration:** 2-3 weeks
**Effort:** 24-34 hours (expanded from 20-30)
**Priority:** MEDIUM

**Prerequisites:** Phase 2 complete, accuracy improved >5%

### 3.1 Buoy Quality Analysis (8-10 hours)

```python
# src/processing/buoy_quality.py

class BuoyQualityAnalyzer:
    """Analyze buoy data quality"""

    def analyze_reading(self, buoy_id, reading, historical_stats):
        """
        Quality checks:
        - Range validation (height 0-20m, period 3-25s)
        - Temporal consistency (no sudden jumps)
        - Statistical outliers (>3σ from mean)
        - Missing data penalties
        - Cross-buoy validation
        """
        return {
            'quality_score': 0.0-1.0,
            'quality_category': 'excellent|good|fair|poor',
            'issues': ['Missing wind speed', 'Period outlier'],
            'reliable': True/False,
            'use_for_forecast': True/False
        }
```

**Value:** +2-3% accuracy improvement expected

---

### 3.2 ⭐ Height Calibration System (6-8 hours) - NEW

**Why Added:** Addresses deep-water vs surf face height mismatch

```python
# src/processing/height_calibration.py

class HeightCalibrator:
    """Convert deep-water swell heights to surf face heights"""

    def calibrate_for_shore(self, deep_water_height, period, direction, shore):
        """
        Apply shoaling, refraction, exposure adjustments

        Based on:
        - Wave period (longer period = more efficient energy transfer)
        - Shore angle vs swell direction (refraction factor)
        - Bathymetry (shoaling coefficient)
        - Exposure factor (shadowing from other islands)
        """

        # Shoaling factor (waves grow in shallow water)
        shoaling = self._calculate_shoaling(period, depth_profile)

        # Refraction factor (angle of approach)
        refraction = self._calculate_refraction(direction, shore_angle)

        # Exposure factor (island shadowing)
        exposure = shore_data['exposure_factor']

        # Hawaiian scale conversion
        surf_height = deep_water_height * shoaling * refraction * exposure

        # Face height (approximately 2x Hawaiian for reporting)
        face_height = surf_height * 2.0

        return {
            'hawaiian_scale': surf_height,
            'face_height': face_height,
            'calibration_confidence': 0.85
        }
```

**Calibration Tables:**
```python
# Empirical coefficients from surf science literature
SHOALING_COEFFICIENTS = {
    '8s': 1.2,
    '10s': 1.4,
    '12s': 1.6,
    '15s': 1.9,
    '18s': 2.2
}

REFRACTION_FACTORS = {
    'direct_hit': 1.0,      # Swell perpendicular to shore
    '30deg_angle': 0.85,
    '60deg_angle': 0.50,
    '90deg_angle': 0.10
}
```

**Value:** +1-2% accuracy improvement + eliminates height confusion

---

### 3.3 Source Reliability Tracking (4-6 hours)

```python
# src/processing/source_reliability.py

class SourceReliabilityTracker:
    """Track source reliability over time"""

    def get_reliability_scores(self, days=30):
        """Get reliability metrics for all sources"""
        return {
            'buoy_51201': {
                'success_rate': 0.95,
                'avg_response_time_ms': 850,
                'data_quality_avg': 0.92,
                'trend': 'stable'
            },
            'weather_api': {
                'success_rate': 0.87,
                'avg_response_time_ms': 1450,
                'trend': 'degrading'
            }
        }
```

**Value:** +1% accuracy improvement expected

**Phase 3 Total Expected Improvement:** +4-6% accuracy

---

## Phase 4: Advanced Features (Optional)

**Duration:** 2-4 weeks
**Effort:** 30-50 hours
**Priority:** LOW

**Decision Criteria - Only proceed if ALL of:**
- [ ] Phases 1-3 improved accuracy >10%
- [ ] Cost still <$0.02/forecast
- [ ] Have 30+ hours available
- [ ] Clear evidence features add value

**Recommendation:** Probably skip Phase 4
- SurfCastAI's simplicity is a strength
- GPT-5 handles complexity well
- Diminishing returns likely
- Better to optimize what you have

---

## Revised Timeline

### Week 1: Phase 0 - Fix & Baseline
- [ ] Enable weather agent (30 min)
- [ ] Enable wave model agent (30 min)
- [ ] Add source attribution (1 hour)
- [ ] Run 7-14 daily forecasts (automated)
- [ ] Manual accuracy assessment (2 hours)
- [ ] Document baseline (1 hour)

### Week 2-3: Phase 1 - Validation Framework
- [ ] Create validation database (3 hours)
- [ ] Implement buoy collector (3 hours)
- [ ] Build validation runner (4 hours)
- [ ] Add CLI commands (1 hour)
- [ ] Create monitoring dashboard (5 hours)
- [ ] Run first accuracy report

**DECISION CHECKPOINT:** Validation working? Baseline established? → Proceed to Phase 2

### Week 4-5: Phase 2 - High-Value Data
- [ ] Add NOAA text bulletins (6-8 hours)
- [ ] Add OPC charts (4-6 hours)
- [ ] Enhance source attribution (4 hours)
- [ ] Extend buoy coverage (3-4 hours)
- [ ] Run comparison tests

**DECISION CHECKPOINT:** Accuracy improved >5%? Cost <$0.015? → Proceed to Phase 3

### Week 6-7: Phase 3 - Processing + Calibration
- [ ] Add buoy quality analysis (8-10 hours)
- [ ] Implement height calibration (6-8 hours)
- [ ] Add source reliability tracking (4-6 hours)
- [ ] Run comprehensive validation

**DECISION CHECKPOINT:** Total improvement >10%? Cost <$0.02? → Success! Or Phase 4?

### Week 8: Review & Optimize
- [ ] Remove features that don't help
- [ ] Optimize what remains
- [ ] Final validation
- [ ] Production deployment

---

## Success Metrics & Checkpoints

### After Phase 0 (Week 1)
**Metrics:**
- [ ] Weather files collected (>0)
- [ ] Model files collected (>0)
- [ ] Source attribution in forecasts
- [ ] Baseline documented

**Decision:** Proceed to Phase 1 ✓

---

### After Phase 1 (Week 3)
**Metrics:**
- [ ] Validation system operational
- [ ] Baseline MAE calculated
- [ ] Monitoring dashboard working

**Decision:** Proceed to Phase 2 ✓

---

### After Phase 2 (Week 5)
**Metrics:**
- [ ] Accuracy improved >5%?
- [ ] Cost <$0.015/forecast?
- [ ] New sources reliable (>80%)?

**Decisions:**
- If accuracy +5-10%: Proceed to Phase 3 ✓
- If accuracy +2-5%: Consider stopping
- If accuracy unchanged: Remove additions, investigate
- If accuracy decreased: Rollback immediately ⚠️

---

### After Phase 3 (Week 7)
**Metrics:**
- [ ] Total improvement >10%?
- [ ] Cost <$0.02/forecast?
- [ ] Height calibration working?

**Decisions:**
- If accuracy +10-15%: Success! Deploy ✅
- If accuracy +7-10%: Good, keep
- If accuracy +5-7%: Consider removing Phase 3
- If cost >$0.02: Optimize or remove features

---

## Expected Outcomes

### Conservative Scenario
- Phase 0: +0% (fixes baseline)
- Phase 1: +0% (measurement only)
- Phase 2: +4% accuracy
- Phase 3: +3% accuracy
- **Total: +7% improvement, cost $0.010/forecast**

### Target Scenario
- Phase 0: +0% (fixes baseline)
- Phase 1: +0% (measurement only)
- Phase 2: +6% accuracy
- Phase 3: +5% accuracy
- **Total: +11% improvement, cost $0.017/forecast**

### Optimistic Scenario
- Phase 0: +0% (fixes baseline)
- Phase 1: +0% (measurement only)
- Phase 2: +7% accuracy
- Phase 3: +6% accuracy
- **Total: +13% improvement, cost $0.020/forecast**

---

## Risk Mitigation

### Risk: Skipping Phase 0
**Impact:** Building on flawed foundation, wasted effort
**Mitigation:** Phase 0 is mandatory, quick wins, low risk

### Risk: Complexity Spiral
**Mitigation:** Strict phase gates, rollback if too complex

### Risk: Cost Explosion
**Mitigation:** Monitor costs constantly, $0.02 hard limit

### Risk: Accuracy Doesn't Improve
**Mitigation:** Measure after each phase, rollback if no gain

---

## Changes from Original Plan

### Added:
1. ✅ **Phase 0** - Fix current issues before adding features
2. ✅ **Source attribution** (Phase 2.3) - Addresses GPT uncertainty
3. ✅ **Height calibration** (Phase 3.2) - Eliminates deep-water vs surf face confusion
4. ✅ **Clarified buoy coverage** - Specified which buoys to add
5. ✅ **Extended timeline** - 8-14 weeks (was 8-12)
6. ✅ **Increased effort** - 64-124 hours (was 56-114)

### Why These Changes:
- Phase 0 provides clean baseline for validation
- Fixes existing issues before adding complexity
- Source attribution addresses current forecast quality issues
- Height calibration eliminates confusion in height reporting
- More realistic timeline accounts for baseline establishment

---

## Summary

This **revised plan** provides a measured, reversible path to enhance SurfCastAI:

**Strengths:**
- ✅ Fixes current issues FIRST (Phase 0)
- ✅ Establishes clean baseline before measuring
- ✅ Incremental and reversible
- ✅ Data-driven decisions
- ✅ Clear success criteria
- ✅ Maintains production stability

**Timeline:** 8-14 weeks (1 week longer for Phase 0)

**Effort:** 64-124 hours total (8-10 hours more for Phase 0 + enhancements)

**Expected Result:**
- +7-13% accuracy improvement
- Cost <$0.02/forecast
- Height reporting matches Pat Caldwell's style
- Source-attributed, confident forecasts

**Next Steps:**
1. ✅ Execute Phase 0 (THIS WEEK)
2. ✅ Establish baseline metrics
3. ✅ Proceed to Phase 1 (Week 2)
4. ✅ Let data guide decisions

---

**Document Version:** 2.0 (Revised)
**Created:** October 5, 2025
**Status:** Ready for vibe-check and execution
