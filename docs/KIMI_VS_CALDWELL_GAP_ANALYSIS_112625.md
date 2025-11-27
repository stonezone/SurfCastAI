# Kimi K2 vs Pat Caldwell Gap Analysis - November 26, 2025

## Executive Summary

This document compares SurfCastAI's Kimi K2-generated forecast against Pat Caldwell's professional forecast for November 26-30, 2025. **Critical gaps identified** that require immediate attention.

## Data Sources Compared

| Source | Description | Status |
|--------|-------------|--------|
| **Pat Caldwell (SNN)** | Professional meteorologist, 40+ years experience | Reference standard |
| **Kimi K2 (SurfCastAI)** | AI forecast from `forecast_20251126_020113` | Test subject |

## Critical Inconsistencies Found

### 1. CRITICAL: Sunday 11/30 Giant Swell Underestimate

| Metric | Pat Caldwell | Kimi K2 | Gap | Severity |
|--------|-------------|---------|-----|----------|
| H1/3 | **30 ft** | 14.7 ft | -15.3 ft | **CRITICAL** |
| H1/10 (faces) | **40 ft** | 19.1 ft | **-20.9 ft** | **CRITICAL** |
| Period | 17s | 13.8s | -3.2s | High |
| Direction | WNW | WNW 299 | OK | - |
| Assessment | "GIANT - Full Waimea" | "filling" | **WRONG** | **CRITICAL** |

**Root Cause**: WW3 model feeds are offline (0/4 success rate). Extended forecasts beyond 3 days rely heavily on wave model propagation data that is currently unavailable.

### 2. HIGH: Friday 11/28 Trend Wrong

| Metric | Pat Caldwell | Kimi K2 | Issue |
|--------|-------------|---------|-------|
| H1/3 | 10 ft (DOWN) | 13.2 ft (holding) | Trend direction wrong |
| H1/10 | 15 ft | 17.2 ft | +2.2 ft overestimate |
| Trend | Declining | Holding steady | **WRONG** |

**Root Cause**: Without model guidance, LLM extrapolates current buoy conditions forward instead of recognizing the typical NW swell decay pattern.

### 3. HIGH: Saturday 11/29 Timing Wrong

| Metric | Pat Caldwell | Kimi K2 | Issue |
|--------|-------------|---------|-------|
| Day assessment | **LULL** (6-7 ft H1/3) | XL jump (25 ft H1/10) | **TIMING OFF BY 24 HOURS** |

**Root Cause**: The Saturday night/Sunday giant swell arrival is being conflated with Saturday daytime. Caldwell correctly identifies Saturday as a lull before the Sunday bomb.

### 4. MODERATE: Missing Storm Backstory

**What Caldwell provides:**
- "968 mb low deepened near 50N, 170E"
- "2400 nm from Hawaii"
- "Hurricane force winds validated by ASCAT"
- "Punchbowl fetch aiming directly at Hawaii"

**What Kimi K2 provides:**
- "Aleutian fetch 1681 nm away"
- Generic "70% confidence" statement
- No specific pressure values
- No satellite validation references

**Root Cause**: The Caldwell template requests storm backstory, but the underlying data digest may not include parsed pressure chart data with specific mb values and locations.

### 5. MODERATE: Missing Historical Context

**What Caldwell provides:**
- "On this day, November 26, in the Goddard-Caldwell database (since 1968), the average H1/10 is 7.0 ft"
- "Today's forecast of X ft is above/below average"

**What Kimi K2 provides:**
- Historical context IS in the data digest (verified)
- But NOT appearing in the final forecast output

**Root Cause**: The LLM is receiving the historical context but not incorporating it into the summary as instructed. The prompt template requests this but enforcement is weak.

## Data Feed Status (from forecast_data.json)

| Agent | Success Rate | Issue |
|-------|--------------|-------|
| **models** | **0/4 (0%)** | **CRITICAL - WW3 offline** |
| buoys | 20/21 (95%) | OK |
| altimetry | 1/1 (100%) | OK |
| charts | 11/15 (73%) | Some charts missing |
| All others | 100% | OK |

## Quantitative Comparison Table

| Date | Pat Caldwell H1/10 | Kimi K2 H1/10 | Gap | Status |
|------|-------------------|---------------|-----|--------|
| Wed 11/26 | 18 ft | 16.6 ft | -1.4 ft | OK |
| Thu 11/27 | 20 ft | 17.2 ft | -2.8 ft | Minor gap |
| Fri 11/28 | 15 ft (DOWN) | 17.2 ft (holding) | +2.2 ft, **trend wrong** | **HIGH** |
| Sat 11/29 | 6-7 ft H1/3 (LULL) | 25 ft H1/10 by night | **timing wrong** | **HIGH** |
| **Sun 11/30** | **40 ft (GIANT)** | **19.1 ft** | **-20.9 ft** | **CRITICAL** |
| Mon 12/01 | 25 ft | Not in 3-day forecast | N/A | - |

## Recommended Fixes

### Priority 1: Fix WW3 Model Feeds (CRITICAL)

The NOMADS endpoints are returning 404. Need to:
1. Check current NOMADS path structure (may have changed)
2. Add alternative endpoints (FTPPRD, AWS mirror)
3. Implement date fallback logic (try today, then yesterday)

```yaml
# Potential fix in config/config.yaml
models:
  urls:
    - "https://nomads.ncep.noaa.gov/pub/data/nccf/com/wave/prod/multi_1.{date}/points/hawaii/wvprbl_hi.{date}.t{hour}z.csv"
    - "https://ftpprd.ncep.noaa.gov/data/nccf/com/wave/prod/multi_1.{date}/points/hawaii/wvprbl_hi.{date}.t{hour}z.csv"
    # Add AWS backup:
    - "https://noaa-gfs-bdp-pds.s3.amazonaws.com/..."
```

### Priority 2: Enforce Historical Context in Output

The Caldwell template requests historical context but the LLM ignores it. Options:
1. Make it a required section with validation
2. Add explicit instruction: "YOU MUST include the phrase 'On this day, [date]...' in the SUMMARY section"
3. Post-process check for missing historical context

### Priority 3: Add Extended Forecast Uncertainty

When model data is unavailable, the forecast should:
1. Clearly state "Extended forecast (5+ days) has HIGH UNCERTAINTY due to missing model guidance"
2. Not attempt to predict specific heights beyond buoy-validated window
3. Reference that "models showing significant event" without specifying exact heights

### Priority 4: Add Pressure Chart Parsing

To get storm backstory details (mb values, distances):
1. OCR the surface analysis charts being downloaded
2. Or add text-based pressure data from GFS/NAM outputs
3. Parse ASCAT satellite wind data when available

## Test Validation Plan

After fixes are applied, rerun forecast and verify:
1. [ ] Sunday 11/30 shows H1/10 > 30 ft (within 5 ft of Caldwell)
2. [ ] Friday 11/28 shows declining trend
3. [ ] Saturday 11/29 shows lull before Sunday event
4. [ ] Historical context appears in SUMMARY section
5. [ ] Storm backstory includes pressure values when available
6. [ ] Model feed success rate > 50%

## GPT-5-Mini Comparison (Added)

After fixing the API key issue (.env had stale key), gpt-5-mini forecast was generated successfully.

**Cost**: $0.058 (8 API calls, 25,462 input + 25,609 output tokens)

### GPT-5-Mini vs Pat Caldwell

| Date | Pat Caldwell H1/10 | GPT-5-Mini H1/10 | Gap | Status |
|------|-------------------|------------------|-----|--------|
| Wed 11/26 | 18 ft | 16.6 ft | -1.4 ft | OK |
| Thu 11/27 | 20 ft | 17.2 ft | -2.8 ft | Minor |
| Fri 11/28 | 15 ft (DOWN) | 17.2 ft (holding) | **TREND WRONG** | HIGH |
| **Sun 11/30** | **40 ft (GIANT)** | **NOT IN FORECAST** | **MISSING** | **CRITICAL** |

### Same Issues as Kimi K2

Both models show identical gaps:
1. **Sunday 11/30 GIANT swell completely missing** - forecast only covers Wed-Fri (3 days)
2. **Friday decline not captured** - both show holding instead of dropping
3. **No historical context** ("On this day, 11/26...") despite template requesting it
4. **No storm backstory** (968 mb, 2400 nm) despite template requesting it

### Root Cause Confirmed

**WW3 model feeds offline (0/4)** is the critical data gap affecting both models:
- Without wave model data, the system cannot predict events 4+ days out
- The Sunday 11/30 GIANT swell is completely invisible to the AI
- This is a **data problem, not a model problem**

### Kimi vs GPT-5-Mini Direct Comparison

| Metric | Kimi K2 | GPT-5-Mini | Winner |
|--------|---------|------------|--------|
| Cost | $0.00 (free tier) | $0.058 | Kimi |
| Wed 11/26 H1/10 | 16.6 ft | 16.6 ft | Tie |
| Thu 11/27 H1/10 | 17.2 ft | 17.2 ft | Tie |
| Fri trend | Wrong (holding) | Wrong (holding) | Tie |
| Sunday giant | 19.1 ft (wrong) | Not mentioned | Kimi (at least tried) |
| Historical context | Missing | Missing | Tie |
| Storm backstory | Partial (1681nm) | Missing | Kimi |

**Conclusion**: Both models perform nearly identically on the same data. The gaps are **data-driven, not model-driven**. Fix the WW3 feeds first.

---

*Generated: 2025-11-26*
*Updated: 2025-11-26 with GPT-5-Mini comparison*
*Reference: Pat Caldwell @ Surf News Network 11/26/25*
*Test Subject: SurfCastAI forecast_20251126_020113*
