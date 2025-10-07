# Data Sources Comparison: SurfCastAI vs SwellGuy
**Generated:** October 5, 2025
**Purpose:** Identify data source gaps and improvement opportunities

---

## Executive Summary

**Today's SurfCastAI Forecast (forecast_20251005_002001):**
- **Data Sources:** 12 buoys only (weather/models FAILED)
- **Images to GPT:** 1 pressure chart
- **Input Tokens:** 7,197
- **Output Tokens:** 17,703
- **Total Tokens:** 24,900
- **API Calls:** 5
- **Cost:** $0.037
- **Model:** GPT-5-nano (primary) + GPT-5-mini (pressure analysis)

**SwellGuy's Approach:**
- **Data Sources:** 100+ URLs across 7 agent categories
- **Images to GPT:** 15-20+ charts (OPC, TGFTP, regional)
- **Estimated Tokens:** 50,000-80,000+ (based on image count + data)
- **Processing:** Specialized agents with GRIB2 processing
- **Model:** GPT-4.1

---

## Critical Finding: Stale Data Bundle

**The forecast used YESTERDAY's data bundle (Oct 4, 12:10pm) from BEFORE Phase 0 fixes!**

Bundle: `08257934-f741-4c90-8d68-92e811664fb7`
- Collected: 2025-10-04 22:10 UTC (Oct 4, 12:10pm HST)
- Weather agent: 0/2 successful (using old HNL grid - Phase 0 fixed this to HFO)
- Models agent: 0/3 successful (using old DODS URLs - Phase 0 fixed this)
- Satellite: 0/1 successful
- Charts: 1/5 successful

**This explains GPT-5's note:** "all swell periods are listed as 0.0 s"

---

## Detailed Data Source Comparison

### 1. Buoy Data ✅ Similar

**SurfCastAI:**
- 12 NDBC buoys (Hawaii region)
- Real-time data only
- JSON format
- Success rate: 92% (11/12)

**SwellGuy:**
- 12+ NDBC buoys (same stations)
- Real-time + historical context
- Enhanced buoy analyzer with trend detection
- Success rate: typically 95%+

**Verdict:** ✅ Comparable

---

### 2. Weather Forecasts ⚠️ SurfCastAI FAILING

**SurfCastAI (TODAY):**
- 0/2 weather files (FAILED)
- Source: NWS API gridpoints
- Issue: Using YESTERDAY's stale bundle with wrong HNL grid
- Phase 0 fixed this but wasn't used

**SwellGuy:**
- NWS zone forecasts (multiple Hawaii zones)
- NOAA TGFTP text bulletins
- Regional weather patterns
- Success rate: 90%+

**Gap:** Weather data completely missing from today's forecast

---

### 3. Wave Models ❌ SurfCastAI SEVERELY LIMITED

**SurfCastAI (TODAY):**
- 0/3 model files (FAILED)
- Attempted sources: NOMADS DODS (timeout), PacIOOS (wrong path)
- No GRIB2 processing capability
- Phase 0 fixed URLs but wasn't used

**SwellGuy:**
- **GRIB2 Processing:**
  - WaveWatch III (WW3) global model
  - GFS wave forecasts
  - wgrib2 tool extracts wave height, period, direction slices
  - grib2json converts to structured JSON

- **PacIOOS ERDDAP:**
  - High-resolution (1km) Hawaii model
  - SWAN model data
  - Structured queries for wave height (Thgt), period, direction

- **ECMWF Models:**
  - European wave model data
  - Long-range forecasts (10+ days)

**Gap:** SwellGuy provides 10-100x more model data with specialized GRIB2 processing

---

### 4. Forecast Charts ❌ SurfCastAI CRITICALLY LIMITED

**SurfCastAI (TODAY):**
- **1 pressure chart only** (0hr surface analysis)
- No wave height charts
- No wave period charts
- No forecast progression (24/48/96hr)
- Charts agent: 1/5 successful

**SwellGuy:**
- **20+ OPC Charts:**
  - Pacific surface analysis (current + 24/48/72/96hr)
  - Wave height forecasts (0/24/48/72/96hr)
  - Wave period forecasts (0/24/48/72/96hr)
  - 500mb upper air charts
  - Regional Pacific analysis

- **NOAA TGFTP Weather Fax:**
  - North Pacific storm tracking charts
  - Tropical system analysis
  - Wind/pressure analysis
  - Historical validation charts

- **Chart Priority System:**
  - Priority 0: Critical surface models with isobars
  - Priority 1: Wave height/period forecasts
  - Priority 2: Supplementary analysis

**Gap:** SwellGuy provides 20x more visual data for GPT analysis

---

### 5. Satellite Imagery ❌ SurfCastAI FAILING

**SurfCastAI (TODAY):**
- 0/1 satellite images (FAILED)
- Source: GOES satellite
- No processing

**SwellGuy:**
- GOES satellite imagery
- Sea surface temperature (SST) analysis
- Cloud pattern recognition
- Storm structure visualization

**Gap:** No satellite data in today's forecast

---

### 6. Tropical Systems ❌ SurfCastAI MISSING

**SurfCastAI:**
- Not implemented

**SwellGuy:**
- Tropical system tracking agent
- NHC data integration
- Storm trajectory analysis
- South swell generation potential

**Gap:** Critical for South Shore forecasting during hurricane season

---

### 7. Additional SwellGuy Sources (Not in SurfCastAI)

**METAR Wind Observations:**
- Coastal wind measurements
- NOAA-COOPS stations
- Real-time conditions

**Tide Data:**
- Tidal predictions
- Affects surf quality timing
- Break-specific recommendations

**International Sources:**
- Australian BOM (Southern Hemisphere swells)
- ECMWF European models
- Global ensemble forecasts

**API Services:**
- Stormglass aggregated data
- Open-Meteo marine forecasts
- Windy Point Forecast API

---

## Token Usage Comparison

### SurfCastAI Today
```
Input:  7,197 tokens (buoy data + 1 pressure chart)
Output: 17,703 tokens (forecast text)
Total:  24,900 tokens
Cost:   $0.037
```

### SwellGuy Typical Forecast
```
Input:  50,000-80,000+ tokens (estimated)
  - 15-20 pressure/wave charts @ ~2,000 tokens each = 30,000-40,000
  - Structured buoy data = 5,000-10,000
  - GRIB2 model data (processed) = 10,000-20,000
  - Text forecasts/bulletins = 5,000-10,000

Output: ~25,000 tokens (comprehensive forecast)
Total:  75,000-105,000 tokens
Cost:   $0.15-$0.25+ (GPT-4.1 pricing)
```

**Key Insight:** SwellGuy uses 3-4x more data but generates more comprehensive forecasts

---

## Data Processing Capabilities

### SurfCastAI
- ✅ JSON buoy data parsing
- ✅ Basic data fusion
- ✅ Swell event detection
- ❌ No GRIB2 processing
- ❌ No chart scraping/parsing
- ❌ No image analysis beyond passing to GPT

### SwellGuy
- ✅ JSON buoy data parsing
- ✅ Advanced buoy trend analysis
- ✅ **GRIB2 Processing:**
  - wgrib2 extracts wave slices
  - grib2json converts to structured data
  - Parses wave height, period, direction grids

- ✅ **Chart Agents:**
  - BeautifulSoup scraping for OPC/WPC
  - Regex-based chart filtering (excludes logos/thumbnails)
  - Size validation (>25KB for meaningful charts)
  - Priority classification

- ✅ **North Pacific Analysis Module:**
  - Specialized storm tracking
  - Fetch-length calculations
  - Swell arrival timing predictions

---

## Network Resilience

### SurfCastAI
- Rate limiting
- Basic retry logic
- Single data source per agent

### SwellGuy
- **Enhanced Fetcher:**
  - Exponential backoff
  - User-Agent rotation
  - SSL exception handling

- **Fallback Manager:**
  - Alternative sources when primary fails
  - DNS resolution fallbacks
  - Comprehensive error logging

- **Prometheus Metrics:**
  - Success rate tracking
  - Performance monitoring
  - Source reliability scoring

---

## Recommendations for SurfCastAI

### Immediate (Can Do Now)
1. ✅ **Fix data collection** - Use Phase 0 fixes (already done, just need fresh bundle)
2. ✅ **Collect fresh data** - Run full collection with working weather/model agents
3. ⚠️ **Add more charts** - Expand chart collection to 15-20 OPC charts

### Short Term (Phase 1 Addition)
4. ⚠️ **Implement chart scraping agent** - OPC wave height/period charts critical
5. ⚠️ **Add satellite imagery** - GOES data essential for storm visualization
6. ⚠️ **Tropical system tracking** - Critical for South Shore during hurricane season

### Medium Term (Phase 2+)
7. ⚠️ **GRIB2 processing** - Access to WW3/GFS model data (requires wgrib2, grib2json)
8. ⚠️ **ERDDAP integration** - High-res PacIOOS Hawaii models
9. ⚠️ **Enhanced network resilience** - Fallback sources, better error handling
10. ⚠️ **North Pacific analysis module** - Specialized storm tracking logic

### Advanced (Future)
11. ⚠️ **International sources** - BOM, ECMWF for long-range forecasts
12. ⚠️ **API integrations** - Stormglass, Windy, Open-Meteo
13. ⚠️ **METAR/COOPS integration** - Real-time wind observations
14. ⚠️ **Tide data integration** - Break-specific timing recommendations

---

## Cost/Benefit Analysis

### Adding OPC Charts (15-20 images)
- **Cost increase:** +$0.05-$0.10/forecast (~$0.12 total)
- **Token increase:** +30,000-40,000 tokens
- **Benefit:** GPT sees wave evolution, can predict timing/size accurately
- **Priority:** HIGH - Critical for accurate forecasting

### Adding GRIB2 Processing
- **Cost increase:** +$0.02-$0.05/forecast
- **Token increase:** +10,000-20,000 tokens
- **Setup:** Requires wgrib2, grib2json installation
- **Benefit:** Access to numerical model data, long-range predictions
- **Priority:** MEDIUM - Important but requires tooling

### Adding Tropical Tracking
- **Cost increase:** +$0.01-$0.02/forecast
- **Token increase:** +2,000-5,000 tokens
- **Benefit:** Critical for South Shore during hurricane season
- **Priority:** MEDIUM-HIGH - Seasonal importance

---

## Next Steps

1. **Run fresh data collection NOW** with Phase 0 fixes
   ```bash
   python src/main.py run --mode collect
   python src/main.py run --mode forecast
   ```

2. **Verify Phase 0 fixes working:**
   - Weather agent: Should collect 2 HFO grid files
   - Models agent: Should collect 2 PacIOOS files
   - Charts agent: Should collect 5+ charts

3. **Compare token usage** before/after adding more data

4. **Review swellguy's chart_agents.py** for OPC scraping implementation

5. **Prioritize additions** based on:
   - Forecast accuracy impact
   - Implementation difficulty
   - Cost increase
   - Your validation results over next 7 days

---

## SwellGuy Files to Study

**For chart collection:**
- `/Users/zackjordan/code/swellguy/agents/chart_agents.py` (294 lines)
- `/Users/zackjordan/code/swellguy/DATA_SOURCES_REGISTRY.md` (436 lines)

**For model processing:**
- `/Users/zackjordan/code/swellguy/agents/model_agents.py`
- `/Users/zackjordan/code/swellguy/processing/` (GRIB2 processing)

**For data integration:**
- `/Users/zackjordan/code/swellguy/analysis/pacific_forecast_analyzer.py` (3042 lines!)
- `/Users/zackjordan/code/swellguy/collector.py` (592 lines)

**For prompt engineering:**
- `/Users/zackjordan/code/swellguy/prompts.json`

---

## Conclusion

**The Gap:**
- SwellGuy uses 100+ data sources vs SurfCastAI's ~15 sources
- SwellGuy provides 20x more visual data (20+ charts vs 1 chart)
- SwellGuy processes GRIB2 models vs SurfCastAI has no model processing
- SwellGuy uses 3-4x more tokens but generates more comprehensive forecasts

**The Opportunity:**
- Phase 0 fixed critical bugs but today's forecast used stale pre-fix data
- Fresh collection with Phase 0 fixes should improve weather/model data
- Adding 15-20 OPC charts would dramatically improve forecast quality
- Token usage would increase 2-3x but remain cost-effective (<$0.15/forecast)

**The Priority:**
1. ✅ Run fresh collection NOW (verify Phase 0 fixes working)
2. ⚠️ Add OPC chart scraping (critical for wave evolution visibility)
3. ⚠️ Add satellite imagery (storm structure visualization)
4. ⚠️ Add tropical tracking (South Shore swells)
5. ⚠️ Consider GRIB2 processing (long-range accuracy)

**Bottom Line:** You want to "throw as much data as possible at GPT" - SwellGuy shows the way with 100+ sources and 20+ charts. The cost increase is minimal ($0.037 → $0.12-$0.15) for dramatically better forecasts.
