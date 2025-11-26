# SurfCastAI TODO - Action Items

**Last Updated**: 2025-11-23
**Quick Status**: ✅ API keys secured in code | ⚠️ User must rotate key | 🚨 Wave heights dangerously wrong

---

## 🔥 DO THIS NOW

### 1. Rotate Your Exposed API Key (5 min)

**What happened**: Your API key was committed to git and has been disabled.

**What I did**: Scrubbed exposed keys from 3 documentation files, created .env.example, verified .gitignore.

**What you need to do**:
```bash
# Get new API key
open https://platform.openai.com/api-keys

# Update .zshrc (or .env)
export OPENAI_API_KEY=sk-proj-YOUR-NEW-KEY-HERE

# Test
python src/main.py run --mode collect --model gpt-5-mini
```

---

### 2. Fix Dangerous Wave Height Bug (CRITICAL SAFETY ISSUE)

**The Problem**:
- North Shore: GPT says 16-25 ft → Actually 10-13 ft (60% over-estimate)
- South Shore: GPT says 18-28 ft → Actually 5-6 ft (400% over-estimate!)

**Why it matters**: Could send beginners into life-threatening conditions thinking it's huge when it's moderate.

**The Fix**: File `src/forecast_engine/data_manager.py` - Hawaiian scale conversion doesn't account for:
1. Refraction (waves lose energy wrapping): multiply by 0.6-0.85
2. Island shadowing (especially south/east): multiply by 0.3-0.7
3. Proper face height calculation

**See details**: [Hawaiian Scale Fix](#fix-hawaiian-scale) below

---

## 📋 HIGH PRIORITY (Do Next)

### 3. Add Swell Quality Ratings
**What**: Label swells as "Excellent 16s groundswell" vs "Poor 8s windswell"
**Why**: Users can't tell if conditions are clean or choppy
**Files**: `src/processing/data_fusion_system.py`, `src/forecast_engine/context_builder.py`

### 4. Add Spot Recommendations
**What**: "Pipeline firing (95% match)" instead of generic "North Shore good"
**Why**: Users want actionable "where to go" not generic conditions
**Files**: Create `src/forecast_engine/spot_recommendations.py`

### 5. Add West/East Shore Forecasts
**What**: Currently only North/South get detailed forecasts
**Why**: Missing 50% of island surf (west shore especially good in winter)
**Files**: `src/forecast_engine/forecast_engine.py`

### 6. Show Confidence Scores
**What**: Display "8.5/10 confidence" based on data quality
**Why**: System calculates it internally but hides it from users
**Files**: `src/forecast_engine/context_builder.py`

---

## 🔧 MEDIUM PRIORITY

### 7. Add Safety Warnings
**What**: Currents, reef hazards, skill level requirements
**Why**: My manual forecast had these, GPT forecast didn't
**Files**: Create `src/forecast_engine/safety_warnings.py`

### 8. Handle Missing Data Better
**What**: Fallback when spectral buoy data unavailable
**Why**: Currently can crash on edge cases
**Files**: `src/processing/data_fusion_system.py`

### 9. Validate vs Pat Caldwell
**What**: Compare forecasts to Pat's bulletins systematically
**Why**: No ground truth validation currently
**Files**: Create `scripts/validate_forecast.py`

---

## ✅ COMPLETED

- ✅ Code review fixes (5/5 done, 99.7% tests passing)
- ✅ API keys scrubbed from documentation
- ✅ .env.example created
- ✅ Manual surf forecast analysis (found the wave height bug)
- ✅ GPT comparison document

---

## <a name="fix-hawaiian-scale"></a>📖 Detailed Fix: Hawaiian Scale Conversion

### Current Problem

File: `src/forecast_engine/data_manager.py`

The conversion applies fixed amplification without accounting for location-specific factors.

### Required Changes

```python
# Location-specific factors
SHORE_FACTORS = {
    'north_shore': {
        'refraction': 0.85,  # NW swells wrap well around island
        'shadowing': 1.0,    # No shadowing from NW direction
    },
    'south_shore': {
        'refraction': 0.60,  # S swells lose significant energy wrapping
        'shadowing': 0.50,   # Island mass blocks/reduces south swell
    },
    'east_shore': {
        'refraction': 0.70,  # Trade swell refraction
        'shadowing': 0.60,   # Partial island shadowing
    },
    'west_shore': {
        'refraction': 0.75,  # Variable based on angle
        'shadowing': 0.80,   # Less shadowing than south
    }
}

def deepwater_to_hawaiian(h13_meters, shore):
    """
    Convert deepwater H1/3 to Hawaiian scale face height.

    Args:
        h13_meters: Significant wave height at buoy (meters)
        shore: 'north_shore' | 'south_shore' | 'east_shore' | 'west_shore'

    Returns:
        Hawaiian scale face height in feet
    """
    factors = SHORE_FACTORS[shore]

    # Step 1: Apply refraction loss as swell wraps around island
    nearshore_h13 = h13_meters * factors['refraction']

    # Step 2: Apply island shadowing (blocks/reduces swell)
    nearshore_h13 *= factors['shadowing']

    # Step 3: Convert H1/3 to face height (1.7x multiplier)
    face_height_m = nearshore_h13 * 1.7

    # Step 4: Convert meters to feet and apply Hawaiian scale (0.67x)
    hawaiian_ft = (face_height_m * 3.28084) * 0.67

    return hawaiian_ft
```

### Validation

Compare against:
- `output/manual_surf_forecast_20251123.md` (my analysis: North 10-13 ft, South 5-6 ft)
- Pat Caldwell bulletins in `docs/`
- NOAA Nearshore Wave Prediction System

### Tests

Add to `tests/unit/forecast_engine/test_data_manager.py`:
```python
def test_hawaiian_scale_north_shore():
    # NW swell: 2.5m deepwater → ~10-12 ft Hawaiian
    result = deepwater_to_hawaiian(2.5, 'north_shore')
    assert 10 <= result <= 13

def test_hawaiian_scale_south_shore():
    # S swell: 2.8m deepwater → ~5-6 ft Hawaiian (heavy shadowing)
    result = deepwater_to_hawaiian(2.8, 'south_shore')
    assert 5 <= result <= 7
```

---

## 📊 Priority Summary

**DO NOW**:
1. Rotate API key
2. Fix Hawaiian scale (safety critical)

**DO SOON** (improves forecasts):
3. Quality ratings (groundswell vs windswell)
4. Spot recommendations (Pipeline, Sunset, etc)
5. West/East shore coverage
6. Confidence scores

**DO EVENTUALLY** (nice to have):
7. Safety warnings
8. Edge case handling
9. Validation framework

---

## 📚 References

**Analysis Documents**:
- `output/manual_surf_forecast_20251123.md` - My manual analysis (baseline truth)
- `output/manual_vs_gpt_comparison.md` - Documents wave height bug
- `docs/CODE_REVIEW_FIXES.md` - Technical fixes completed

**Key Files to Edit**:
- `src/forecast_engine/data_manager.py` - Hawaiian scale conversion ⚠️
- `src/forecast_engine/context_builder.py` - Add quality/confidence
- `src/processing/data_fusion_system.py` - Swell quality classification

**Ground Truth**:
- `docs/Pat Caldwell _ Surf News Network Monday Oct 15, 2025.pdf`

---

**Questions?** Review the detailed comparison in `output/manual_vs_gpt_comparison.md`
