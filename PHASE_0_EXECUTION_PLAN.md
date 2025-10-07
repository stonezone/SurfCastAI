# Phase 0 Execution Plan - IMMEDIATE ACTION
**Date:** October 5, 2025
**Duration:** This week (4-6 hours total)
**Status:** READY TO EXECUTE NOW

---

## What We're Doing

**Fix 4 current issues identified in DATA_PIPELINE_FIXES.md:**
1. Enable weather agent (currently 0 files)
2. Enable wave model agent (currently 0 files)
3. Add source attribution (GPT uncertain about data)
4. Document baseline metrics

**Why These First:**
- Already 80% implemented
- Quick wins (30 min - 1 hour each)
- Low risk
- GPT flagged these issues
- Establishes clean baseline

---

## Task 1: Enable Weather Agent (30 minutes)

**Problem:** Weather agent exists but not collecting data

**Diagnosis Steps:**
```bash
# Check if agent exists
ls -la src/agents/weather_agent.py

# Check config
grep -A 10 "weather" config.yaml

# Check if it's being called
grep -r "weather_agent" src/main.py src/collection/
```

**Fix:**
```yaml
# If disabled in config, enable:
data_sources:
  weather:
    enabled: true

# If missing sources, add NOAA weather URLs
```

**Test:**
```bash
python src/main.py run --mode collect
ls -la data/latest_bundle/weather/
# Should show >0 files
```

**Success Criteria:**
- [ ] Weather files collected
- [ ] No errors in logs
- [ ] Next forecast includes wind speed

---

## Task 2: Enable Wave Model Agent (30 minutes)

**Problem:** Wave model agent exists but not collecting data

**Diagnosis Steps:**
```bash
# Check if agent exists
ls -la src/agents/model_agent.py

# Check config
grep -A 10 "model" config.yaml

# Check if it's being called
grep -r "model_agent\|wave_model" src/main.py src/collection/
```

**Fix:**
```yaml
# Enable in config
data_sources:
  wave_models:
    enabled: true
```

**Test:**
```bash
python src/main.py run --mode collect
ls -la data/latest_bundle/models/
# Should show >0 files
```

**Success Criteria:**
- [ ] Model files collected
- [ ] Model data in fused_forecast.json
- [ ] No processing errors

---

## Task 3: Add Source Attribution (1-2 hours)

**Problem:** SwellEvents lack source provenance, GPT uncertain

**Changes Needed:**

### 3.1: Update SwellEvent Creation
```python
# src/processing/data_fusion_system.py
# Find where SwellEvents are created (around line 300-400)

# ADD source details to metadata:
event.metadata['source_details'] = {
    'buoy_id': buoy_id,
    'observation_time': latest.time,
    'data_quality': 'good',  # or calculate based on completeness
    'source_type': 'NDBC realtime'
}
```

### 3.2: Update Prompt Templates
```python
# src/forecast_engine/prompt_templates.py
# Update swell formatting to include source

# BEFORE:
f"- {direction} swell: {height} ft @ {period}s"

# AFTER:
source_info = swell.get('metadata', {}).get('source_details', {})
buoy_id = source_info.get('buoy_id', 'Unknown')
obs_time = source_info.get('observation_time', '')

f"- {direction} swell: {height} ft @ {period}s (Source: Buoy {buoy_id}, {obs_time})"
```

**Test:**
```bash
python src/main.py run --mode forecast
grep -i "Source: Buoy" output/latest/forecast_data.json
# Should show source attribution
```

**Success Criteria:**
- [ ] All swell events have source_details
- [ ] Forecasts display source attribution
- [ ] GPT stops complaining about uncertain data

---

## Task 4: Establish Baseline (2-3 hours over 7 days)

**Setup Automated Daily Forecasts:**
```bash
# Add to crontab or equivalent
# Run daily at 6 AM
0 6 * * * cd /Users/zackjordan/code/surfCastAI && python src/main.py run --mode full >> logs/daily_forecast.log 2>&1
```

**Manual Tracking (once daily for 7 days):**
```yaml
# Create BASELINE_LOG.md and track:

Date: 2025-10-05
Cost: $0.037
Tokens: 24900
API Calls: 5
Collection Success: 12/12 buoys
Weather Files: 0  # BEFORE fix
Model Files: 0    # BEFORE fix
Errors: None
Notes: Fixed period bug, forecasts look good

Date: 2025-10-06  # AFTER Phase 0 fixes
Cost: $0.042  # Might increase with weather/model data
Tokens: 28000
Weather Files: 5  # AFTER fix ✓
Model Files: 3    # AFTER fix ✓
Quick Accuracy Check: Compared to Caldwell's forecast - direction/timing match, height within 20%
```

**Deliverable:**
```markdown
# BASELINE_METRICS.md

## Pre-Phase-0 Baseline (Oct 5, 2025)
- Cost: $0.037/forecast
- Tokens: ~25,000
- Collection: 12 buoys, 0 weather, 0 models
- Known Issues: Missing wind speed, period bug (FIXED), no source attribution

## Post-Phase-0 Results (Oct 12, 2025)
- Cost: $0.045/forecast (+22%)
- Tokens: ~29,000 (+16%)
- Collection: 12 buoys, 5 weather files, 3 model files
- Improvements: Wind speed available, source attribution, more data sources
- Accuracy: Manually compared 3 forecasts to Caldwell - good alignment
```

**Success Criteria:**
- [ ] 7 forecasts generated
- [ ] Before/after metrics documented
- [ ] Manual accuracy assessment complete
- [ ] Decision made: Does this justify Phase 1?

---

## Execution Order

**TODAY (October 5):**
1. Task 1: Enable weather agent (30 min)
2. Task 2: Enable wave model agent (30 min)
3. Task 3: Add source attribution (1-2 hours)
4. Run test forecast with fixes (10 min)
5. Review results

**THIS WEEK (Oct 5-12):**
1. Set up daily forecast automation
2. Run forecasts daily
3. Quick manual checks (5 min/day)
4. Compare 2-3 forecasts to Pat Caldwell's

**END OF WEEK (Oct 12):**
1. Document baseline metrics
2. Assess impact
3. DECISION: Proceed to Phase 1 validation framework? Or stop here?

---

## Success Metrics

**Minimum Success (Continue to Phase 1):**
- [ ] Weather/model agents working
- [ ] Source attribution visible in forecasts
- [ ] Cost still <$0.05/forecast
- [ ] No major errors
- [ ] Forecasts subjectively better

**Strong Success (Definitely do Phase 1):**
- [ ] GPT stops complaining about missing data
- [ ] Forecasts include wind speeds
- [ ] Source attribution improves GPT confidence
- [ ] Manual comparison shows good accuracy
- [ ] Cost <$0.05/forecast

**Failure (Stop, rollback):**
- [ ] Agents fail to collect data
- [ ] Cost >$0.10/forecast
- [ ] Forecasts worse than before
- [ ] System unstable

---

## Rollback Plan

If Phase 0 fails:
```bash
# Disable agents in config
data_sources:
  weather:
    enabled: false
  wave_models:
    enabled: false

# Remove source attribution commits
git checkout HEAD~3 -- src/processing/data_fusion_system.py
git checkout HEAD~3 -- src/forecast_engine/prompt_templates.py

# Verify rollback
python src/main.py run --mode forecast
```

---

## Agent Supervision Protocol

**My Role:** Supervisor enforcing plan adherence

**Agent Roles:**
- **Python-pro agent:** Implement source attribution code
- **Backend-architect agent:** Review data flow changes
- **Debugger agent:** Fix any issues that arise

**STOP Conditions:**
- Agent suggests adding features not in Phase 0
- Agent wants to refactor unrelated code
- Agent proposes "while we're here" improvements
- Changes exceed 1-hour scope per task

**Enforcement:**
1. Review agent's plan BEFORE execution
2. If deviation detected → STOP
3. Redirect agent to Phase 0 tasks only
4. No scope creep allowed

---

## Next Steps After Phase 0

**If successful (Week of Oct 12):**
- Review migration_plan_revised.md Phase 1
- Decide: Build validation framework? Or iterate on Phase 0?
- User decides based on results

**If unsuccessful:**
- Rollback changes
- Analyze what failed
- Reconsider migration approach

---

**This is the execution plan. Start NOW.**
