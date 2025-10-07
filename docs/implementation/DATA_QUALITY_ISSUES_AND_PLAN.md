# Data Quality Issues & Resolution Plan
**Analysis of forecast_20251004_113339**
**Date:** October 4, 2025

---

## 📋 Complete List of Data Concerns Mentioned by GPT

### Critical Issues (Missing Core Data)

**1. Swell Period Data Missing**
- **North Shore:** "periods are listed as 0 s"
- **South Shore:** "Periods were not supplied (0.0 s)"
- **Impact:** GPT had to assume periods (12-18s for groundswell, 6-9s for windswell)
- **Consequence:** "period assumptions matter a lot for hazard and surf quality"
- **Severity:** 🔴 CRITICAL - Period determines wave power, barrel quality, and safety

**2. Wind Data Corrupted/Invalid**
- **Everywhere:** "Wind: '60 at 0 kt' appears to be corrupted"
- **Impact:** GPT assumed "light ENE trades (roughly 60°) at 5–12 kt early"
- **Consequence:** Wind predictions are guesswork, affects condition forecasts
- **Severity:** 🔴 CRITICAL - Wind determines surf quality (glassy vs choppy)

**3. Tide Data Not Supplied**
- **North Shore:** "Tides: no tide data supplied"
- **Impact:** Only generic tide-window notes provided
- **Consequence:** Can't give specific session timing recommendations
- **Severity:** 🟡 HIGH - Tides critical for reef breaks, safety

### Moderate Issues (Incomplete/Uncertain Data)

**4. Satellite Imagery Failed**
- **Main Forecast:** "satellite imagery could not be processed (unsupported image upload error)"
- **Impact:** Forecasts rely only on pressure/wind charts
- **Consequence:** Missing visual confirmation of cloud patterns, systems
- **Severity:** 🟡 MODERATE - Still has pressure charts for analysis

**5. Weather/Synoptic Data Gaps**
- **North Shore:** "Weather: Unknown from supplied data"
- **South Shore:** "Weather uncertainty: no synoptic info provided"
- **Impact:** Can't predict local squalls, frontal passages
- **Consequence:** Wind forecasts less reliable
- **Severity:** 🟡 MODERATE - Can work around with pressure analysis

**6. Magnitude Uncertainty**
- **South Shore:** "If the supplied 5–6 ft Hawaiian numbers are accurate..."
- **South Shore:** "If those magnitudes are actually erroneous (common when periods/sources are missing)"
- **Impact:** Uncertainty about whether swell heights are correct
- **Consequence:** Size forecasts may be wrong
- **Severity:** 🔴 CRITICAL - Core prediction accuracy

**7. Live Data Not Available**
- **Daily:** "I don't have live data for 2025-10-04"
- **Impact:** Generic NW swell scenario instead of actual conditions
- **Consequence:** User must verify everything independently
- **Severity:** 🟡 MODERATE - This is expected for daily section

### Data Quality Flags Throughout

**8. Multiple Assumptions Noted**
- "What I'm assuming because your input is incomplete"
- "I'll state assumptions where I fill gaps so you know what's data vs. inferred"
- "Because periods weren't provided, treat the scenario as worst-case"
- "Use conservative interpretations for each break based on long- vs short-period scenarios"

**9. Validation Requests**
- "Check updated buoy periods and local cams before paddling"
- "Would you like me to update this with real-time buoy periods and a corrected wind observation?"
- "get updated period readings from the NN or local buoy"
- "Pull the latest buoy and model output to replace the missing period and wind-speed data"
- "Treat this as guidance — check Surfline/NOAA buoys, local cams and tide charts"

---

## 🔍 Root Cause Analysis

### Where is the data coming from?

Looking at the metadata:
```json
"source_data": {
  "swell_events": 9,
  "locations": 4
},
"data_source_scores": {
  "buoy": 0.9
}
```

**Only buoy data was successfully processed.** Missing:
- ❌ Weather data
- ❌ Wave model data  
- ❌ Satellite imagery

### What's happening in the pipeline?

1. **Data Collection** (`src/agents/`) - Appears to be working for buoys only
2. **Data Processing** (`src/processing/buoy_processor.py`) - Extracting swell events
3. **Swell Events** - Missing period data (showing 0.0 s)
4. **Wind Data** - Corrupted or placeholder ("60 at 0 kt")
5. **Forecast Engine** - GPT receives incomplete data, makes assumptions

---

## 🎯 Resolution Plan

### Phase 1: Diagnose Data Pipeline Issues (IMMEDIATE)

**1.1 Check Buoy Processor Period Extraction**
```bash
# Verify buoy spectral data is being read correctly
# File: src/processing/buoy_processor.py
# Issue: Swell events showing period = 0.0 s
```
**Actions:**
- [ ] Read `src/processing/buoy_processor.py` 
- [ ] Find swell event detection logic
- [ ] Check if spectral period (SwP/DPD) is being extracted
- [ ] Verify it's being included in swell event output
- [ ] Test with sample buoy file to see actual vs extracted periods

**1.2 Check Wind Data Source**
```bash
# Wind showing "60 at 0 kt" - likely placeholder or parsing error
# Should be actual wind speed/direction from buoys or weather
```
**Actions:**
- [ ] Check where wind data comes from (buoys? weather agent?)
- [ ] Verify wind parsing in data processors
- [ ] Check if wind is being included in fused forecast data
- [ ] Test with sample data to see actual wind values

**1.3 Verify Data Fusion**
```bash
# File: src/processing/data_fusion_system.py
# Check if all collected data is making it to final output
```
**Actions:**
- [ ] Check what fields are included in fused_forecast.json
- [ ] Verify swell events include: height, period, direction
- [ ] Verify wind data is present and formatted correctly
- [ ] Check tide data integration (if supported)

### Phase 2: Fix Missing Data Sources (HIGH PRIORITY)

**2.1 Enable Weather Data Collection**
```bash
# Metadata shows: "weather": 0 files found
# Weather agent not collecting or failing
```
**Actions:**
- [ ] Check `src/agents/weather_agent.py` status
- [ ] Verify weather URLs in config are active
- [ ] Test weather data collection manually
- [ ] Add weather data to data fusion pipeline
- [ ] Include wind forecasts in final output

**2.2 Enable Wave Model Data**
```bash
# Metadata shows: "model": 0 files found
# Wave model agent not collecting
```
**Actions:**
- [ ] Check `src/agents/model_agent.py` implementation
- [ ] Verify wave model URLs (WaveWatch III, etc.)
- [ ] Test model data collection
- [ ] Add model swell forecasts to fusion
- [ ] Use model data to validate/supplement buoy observations

**2.3 Fix Satellite Image Processing**
```bash
# Error: "satellite imagery could not be processed (unsupported image upload error)"
# We already fixed the download in satellite_agent.py
# Need to verify GPT-5 can now process the images
```
**Actions:**
- [ ] Verify satellite agent is downloading actual images (not .php files)
- [ ] Check image format (should be JPG/PNG, not HTML)
- [ ] Test GPT-5-mini image analysis with downloaded satellite images
- [ ] Include satellite analysis in forecast context

### Phase 3: Add Missing Data Types (MEDIUM PRIORITY)

**3.1 Tide Data Integration**
```bash
# GPT notes: "Tides: no tide data supplied"
# Need tide predictions for surf timing
```
**Actions:**
- [ ] Research tide prediction APIs (NOAA CO-OPS?)
- [ ] Create tide data agent or add to existing agent
- [ ] Extract tide times for key locations (Honolulu, Haleiwa, etc.)
- [ ] Include tide schedule in forecast output
- [ ] Format: Low 6:07 AM (0.17 ft), High 12:34 PM (1.8 ft), etc.

**3.2 Enhanced Weather Data**
```bash
# Need more than just wind - precipitation, cloud cover, fronts
```
**Actions:**
- [ ] Add synoptic analysis (high/low pressure systems)
- [ ] Include precipitation forecasts
- [ ] Add cloud cover predictions
- [ ] Include any weather warnings/advisories

### Phase 4: Data Validation & Quality Checks (HIGH PRIORITY)

**4.1 Validate Swell Event Magnitudes**
```bash
# GPT questioned: "If the supplied 5–6 ft Hawaiian numbers are accurate..."
# Need sanity checks on extracted swell heights
```
**Actions:**
- [ ] Add validation: Compare extracted heights to historical ranges
- [ ] Flag suspicious values (e.g., 20 ft Hawaiian south swell in October = unlikely)
- [ ] Cross-reference: Buoy data vs. wave model predictions
- [ ] Confidence scoring based on data consistency

**4.2 Add Data Completeness Checks**
```bash
# Before sending to GPT, verify all required fields present
```
**Actions:**
- [ ] Check: All swell events have height, period, direction
- [ ] Check: Wind data has speed and direction
- [ ] Check: Timestamps are valid and recent
- [ ] Warn user if data is stale (>6 hours old)
- [ ] Lower confidence score if data is incomplete

**4.3 Add Source Attribution**
```bash
# Track which buoy/model/source each data point came from
```
**Actions:**
- [ ] Label each swell event with source (e.g., "Buoy 51001")
- [ ] Include collection timestamp
- [ ] Note data quality (e.g., "High confidence - recent observation")
- [ ] Pass source info to GPT for transparency in forecast

### Phase 5: Improve GPT Input Format (MEDIUM PRIORITY)

**5.1 Structured Data Format**
```bash
# Instead of GPT inferring from incomplete data, give clear structure
```
**Format to provide:**
```json
{
  "swell_events": [
    {
      "height_meters": 2.3,
      "height_hawaiian": 7.5,
      "period_seconds": 13.0,
      "direction_degrees": 332,
      "direction_label": "NNW",
      "arrival_time": "2025-10-04T21:20:00Z",
      "source": "Buoy 51201",
      "confidence": "high"
    }
  ],
  "wind": {
    "speed_knots": 12,
    "direction_degrees": 60,
    "direction_label": "ENE",
    "forecast_time": "2025-10-05T06:00:00Z",
    "trend": "increasing to 17 kt by afternoon"
  },
  "tides": [
    {
      "time": "2025-10-05T06:07:00Z",
      "height_feet": 0.17,
      "type": "low"
    },
    {
      "time": "2025-10-05T12:34:00Z", 
      "height_feet": 1.85,
      "type": "high"
    }
  ]
}
```

**5.2 Update Prompts to Handle Missing Data**
```bash
# Instead of GPT making assumptions, explicit instructions
```
**Prompt updates:**
- "If period data is missing, state this clearly and DO NOT make assumptions"
- "If wind data is 0 kt, this is invalid - request updated data"
- "Always flag when making assumptions vs. using actual data"
- "Use ONLY provided data - do not infer missing values"

---

## 📊 Priority Matrix

| Issue | Severity | Impact | Effort | Priority |
|-------|----------|--------|--------|----------|
| Missing swell periods | 🔴 Critical | Forecast accuracy | Low | **P0 - DO FIRST** |
| Invalid wind data | 🔴 Critical | Condition forecasts | Low | **P0 - DO FIRST** |
| Magnitude validation | 🔴 Critical | Size predictions | Medium | **P1 - NEXT** |
| Weather data missing | 🟡 High | Wind forecasts | Medium | **P1 - NEXT** |
| Wave model missing | 🟡 High | Forecast confidence | Medium | **P2 - SOON** |
| Satellite processing | 🟡 Moderate | Visual confirmation | Low (fixed) | **P2 - TEST** |
| Tide data missing | 🟡 Moderate | Timing guidance | Medium | **P3 - LATER** |
| Data completeness checks | 🟡 High | Overall quality | Low | **P1 - NEXT** |

---

## ✅ Immediate Action Items (Do Now)

**Step 1: Diagnose Buoy Processor**
```bash
# Check why periods are showing 0.0 s
python -c "
from src.processing.buoy_processor import BuoyProcessor
# Test with sample buoy file
# Print extracted swell events
# Verify period field is populated
"
```

**Step 2: Check Latest Data Bundle**
```bash
# Look at most recent fused_forecast.json
cat data/08257934-f741-4c90-8d68-92e811664fb7/processed/fused_forecast.json | jq '.swell_events[] | {height, period, direction}'

# Should show actual periods, not 0.0
```

**Step 3: Trace Wind Data**
```bash
# Find where "60 at 0 kt" comes from
grep -r "60.*0.*kt" data/
# Check wind field in buoy files
# Verify wind extraction logic
```

**Step 4: Quick Win - Satellite Fix**
```bash
# We already fixed satellite download
# Just verify it worked
ls -lh data/www_star_nesdis_noaa_gov/*.jpg
# Should see actual JPG images, not .php files
```

---

## 📈 Success Metrics

After fixes, the forecast should:

✅ **No GPT assumptions** - All data fields populated with real values
✅ **No "periods not supplied"** - All swell events have actual periods
✅ **Valid wind data** - Real speed/direction, not "0 kt"
✅ **Tide times included** - Specific low/high tide schedule
✅ **Weather context** - Synoptic analysis from weather data
✅ **Source attribution** - Each data point labeled with source
✅ **Confidence scoring** - Based on data completeness and quality
✅ **No validation warnings** - Data passes sanity checks

---

## 🚀 Next Steps

**After you review this plan:**

1. I'll read `buoy_processor.py` to diagnose period extraction
2. Check actual buoy files to see what data is available
3. Trace the data pipeline from collection → processing → fusion → GPT
4. Fix the highest priority issues (P0: periods, wind)
5. Test with a fresh forecast run
6. Iterate until all data concerns are resolved

**Ready for your input on:**
- Which issues to tackle first?
- Any specific data sources you want prioritized?
- Should I start with diagnostics or jump straight to fixes?
