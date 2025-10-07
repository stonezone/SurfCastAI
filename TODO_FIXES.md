# SurfCastAI Critical Fixes - Phase 1

## Issue Summary
Live testing revealed process hanging after GPT-5-mini image analysis due to visualization code accessing non-existent fields in swell event data.

## Root Cause Analysis

**Hanging Issue:**
- `ForecastVisualizer._build_swell_mix_chart()` accesses `event.get("dominant_period")` and `event.get("primary_direction_cardinal")`
- These fields don't exist in swell events (actual fields: `primary_components`, `primary_direction`, etc.)
- Attempting to format None with `f"{period:.0f}s"` causes crash/hang
- Similar issue in `_build_shore_focus_chart()` with shore_data structure

**Missing Data:**
- Weather agent not creating `weather_*.json` files
- Wave model downloads not creating `model_*.json` files
- OPeNDAP endpoints timing out (acceptable - use GIF charts instead)

## Phase 1 Tasks (PRIORITY ORDER)

### Task 1.1: Fix Visualization Field Access (CRITICAL)
**File:** `src/forecast_engine/visualization.py`

**Changes needed:**
1. Line 57: Replace `event.get("dominant_period")` with extraction from `primary_components[0]["period"]`
2. Line 56: Convert `primary_direction` (numeric) to cardinal direction or use numeric
3. Add null checks before formatting with `.0f`
4. Add try/except around chart generation to prevent hanging on error
5. Log errors instead of crashing

**Expected behavior:**
- Extract period from `event["primary_components"][0]["period"]` if exists
- Convert `event["primary_direction"]` to cardinal (N/NE/E/etc) or display numeric
- Handle None/null values gracefully
- Continue forecast even if visualization fails

### Task 1.2: Add Timeout and Error Handling to Forecast Generation
**File:** `src/forecast_engine/forecast_engine.py`

**Changes needed:**
1. Add asyncio timeout wrapper around `_call_openai_api()` calls (5 minutes max)
2. Save image analysis responses to debug file: `{bundle_id}/debug/image_analysis.txt`
3. Add progress logging every API call
4. Catch and log exceptions, return partial results on error

**Expected behavior:**
- Timeout prevents infinite hanging
- Image analysis saved even if full forecast fails
- Clear error messages with stack traces in logs

### Task 1.3: Fix Shore Data Structure Access
**File:** `src/forecast_engine/visualization.py`

**Changes needed:**
1. Line 89: Check if `shore_data` exists and has correct structure
2. Verify `forecast_data` has `locations` array (not `shore_data`)
3. Update to use `forecast_data["locations"]` array with `shore` field
4. Add defensive null checks

**Expected behavior:**
- Access correct data structure from fused_forecast.json
- Handle missing/malformed data gracefully

### Task 1.4: Add Progress Logging
**File:** `src/forecast_engine/forecast_formatter.py`

**Changes needed:**
1. Add log statements before/after `visualizer.generate_all()`
2. Add log statements before/after `history.build_summary()`
3. Log each format generation step (markdown, html, pdf)
4. Catch exceptions in each step and continue

**Expected behavior:**
- Clear visibility into which step is executing
- Partial output saved even if one format fails

## Phase 2 Tasks (SECONDARY)

### Task 2.1: Fix Weather Agent JSON Output
**File:** `src/agents/weather_agent.py`

**Investigation needed:**
- Determine why weather agent doesn't create `weather_*.json` files
- Check if data is downloaded but not formatted
- Add JSON output step if missing

### Task 2.2: Add Wave Model JSON Creation
**File:** `src/agents/model_agent.py`

**Changes needed:**
- Parse wave forecast GIF metadata if available
- OR create placeholder model_*.json from downloaded GIF files
- OR skip numerical model data and rely on GIF image analysis

### Task 2.3: Add Cost Tracking
**File:** `src/forecast_engine/forecast_engine.py`

**Changes needed:**
1. Parse token usage from OpenAI API responses (`response.usage.total_tokens`)
2. Log actual tokens used vs estimated
3. Calculate actual cost: (prompt_tokens * $0.00015 + completion_tokens * $0.0006) / 1000
4. Add to forecast metadata

## Success Criteria

**Phase 1 Complete When:**
- ✅ Forecast completes without hanging
- ✅ Visualization errors don't crash process
- ✅ Image analysis responses saved to debug file
- ✅ Full forecast output generated (markdown, html, json)
- ✅ Clear error messages if issues occur

**Phase 2 Complete When:**
- ✅ Weather data included in forecast
- ✅ Wave model data available (if feasible)
- ✅ Actual token costs logged

## Testing Plan

1. Run live test with current data bundle: `a696a045-b2a8-4423-91ca-05cc508ed7a4`
2. Verify forecast completes within 5 minutes
3. Check output directory for all formats
4. Read `debug/image_analysis.txt` to verify GPT-5-mini responses
5. Review forecast quality and GPT-5-mini insights
6. Document any remaining issues

## Implementation Notes

- Use python-pro agent for Task 1.1 (visualization fixes)
- Use python-pro agent for Task 1.2 (timeout handling)
- Use python-pro agent for Task 1.3 (shore data fixes)
- Use python-pro agent for Task 1.4 (logging)
- Test after each task completes
- STOP if any agent deviates from specified changes
