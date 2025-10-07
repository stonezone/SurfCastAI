# SurfCastAI - Project Completion Todo List
**Generated:** October 4, 2025  
**For:** Personal use - Claude Code execution  
**Project:** AI-Powered Surf Forecasting System for Oahu

---

## 📋 PROJECT STATUS

### What Works
✅ Professional Pat Caldwell-style surf forecasts  
✅ Multi-modal vision (pressure charts, satellite, SST)  
✅ Cost efficient: $0.0066 per forecast  
✅ 87% data collection success rate  
✅ GPT-5-nano and GPT-5-mini integration working

### What Needs Completion
⚠️ Actual token usage tracking (currently estimating)  
⚠️ External API endpoints broken (weather, wave models)  
⚠️ Production monitoring and health checks  
⚠️ Documentation updates  
💡 Optional optimizations and enhancements

---

## 🎯 PRIORITY 1: CORE FUNCTIONALITY

### 1.1 Implement Actual Token Usage Tracking
**Status:** Currently estimating token costs instead of tracking real usage  
**Time:** 1 hour  
**Impact:** HIGH - Need accurate cost data

**Current Problem:**
```python
# Estimating tokens instead of tracking actual usage
estimated_tokens = 3000 if detail == 'high' else 1500
```

**Solution:**
```python
# src/forecast_engine/forecast_engine.py - Update _call_openai_api()

# After getting response
if hasattr(response, 'usage') and response.usage:
    input_tokens = response.usage.prompt_tokens
    output_tokens = response.usage.completion_tokens
    
    # Calculate actual cost based on model
    if 'gpt-5-mini' in self.openai_model.lower():
        cost = (input_tokens * 0.00000025 + output_tokens * 0.000002)
    elif 'gpt-5-nano' in self.openai_model.lower():
        cost = (input_tokens * 0.00000005 + output_tokens * 0.0000004)
    elif 'gpt-5' in self.openai_model.lower():
        cost = (input_tokens * 0.00000125 + output_tokens * 0.00001)
    else:
        cost = 0
    
    # Accumulate totals
    self.total_input_tokens += input_tokens
    self.total_output_tokens += output_tokens
    self.total_cost += cost
    self.api_call_count += 1
    
    self.logger.info(
        f"API call #{self.api_call_count}: {input_tokens} input + "
        f"{output_tokens} output = ${cost:.6f} (total: ${self.total_cost:.6f})"
    )

# Save to forecast metadata
result['metadata']['api_usage'] = {
    'total_cost': round(self.total_cost, 6),
    'api_calls': self.api_call_count,
    'input_tokens': self.total_input_tokens,
    'output_tokens': self.total_output_tokens,
    'model': self.openai_model
}
```

---

### 1.2 Add Cost Alert Thresholds
**Status:** No alerts for high costs  
**Time:** 30 minutes  
**Impact:** MEDIUM - Useful for budget awareness

```python
# src/forecast_engine/forecast_engine.py - In generate_forecast()

# After forecast generation
if self.total_cost > 0.05:  # $0.05 per forecast threshold
    self.logger.warning(
        f"High cost alert: ${self.total_cost:.6f} exceeds $0.05 threshold"
    )
```

**Configuration:**
```yaml
# config/config.yaml - Add monitoring section
monitoring:
  cost_thresholds:
    warning: 0.02  # USD per forecast
    high: 0.05
    daily_limit: 1.00
    monthly_limit: 30.00
```

---

## 🟡 PRIORITY 2: EXTERNAL DATA SOURCES (Optional)

### 2.1 Fix Weather API Endpoints
**Status:** NWS gridpoint endpoints returning 404  
**Time:** 1-2 hours research  
**Impact:** LOW - System works fine without weather data

**Current Issue:**
```bash
# 404 errors
https://api.weather.gov/gridpoints/HNL/12,52/forecast
https://api.weather.gov/gridpoints/HNL/8,65/forecast
```

**Investigation Steps:**
1. Research correct NWS API gridpoint coordinates for Oahu
2. Test alternative endpoints:
   ```bash
   # Try point-based lookup
   curl -A "SurfCastAI/1.0" https://api.weather.gov/points/21.3099,-157.8581
   ```
3. Update config.yaml with working endpoints
4. Verify weather JSON files are created

**Decision:** DEFER - Not critical, system generates excellent forecasts without it

---

### 2.2 Fix Wave Model DODS Timeouts
**Status:** NOMADS DODS servers timing out  
**Time:** 2 hours  
**Impact:** LOW - GIF analysis compensates

**Current Issue:**
```bash
# Timeouts after 30s
https://nomads.ncep.noaa.gov:9090/dods/gfs_0p25
https://nomads.ncep.noaa.gov:9090/dods/wave_multi_1.glo_0.16
```

**Options:**
1. Increase timeout for DODS endpoints (currently 30s)
2. Implement retry logic with exponential backoff
3. Add fallback to GIF-only analysis (already working)

**Decision:** DEFER - GIF analysis via GPT-5-mini provides sufficient data

---

### 2.3 Fix SWAN Model Endpoint
**Status:** PacIOOS URL returning 404  
**Time:** 30 minutes  
**Impact:** LOW

**Current Issue:**
```bash
# 404 error
https://www.pacioos.hawaii.edu/wave-model/swan-oahu/
```

**Tasks:**
- Find new PacIOOS SWAN model endpoint
- Check https://www.pacioos.hawaii.edu/voyager/
- Update config.yaml

**Decision:** DEFER - Not critical

---

## 🟢 PRIORITY 3: PRODUCTION READINESS

### 3.1 Add Health Check Endpoint
**Status:** Missing  
**Time:** 1 hour  
**Impact:** MEDIUM - Useful for monitoring

**Implementation:**
```python
# src/web/app.py - Add health check route

from datetime import datetime
from pathlib import Path
import shutil

@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring."""
    data_dir = Path("data")
    output_dir = Path("output")
    
    # Get latest bundle
    bundles = sorted(data_dir.glob("*"), key=lambda x: x.stat().st_mtime, reverse=True)
    latest_bundle = bundles[0].name if bundles else None
    
    # Get latest forecast
    forecasts = sorted(output_dir.glob("*"), key=lambda x: x.stat().st_mtime, reverse=True)
    latest_forecast = forecasts[0].name if forecasts else None
    
    # Check disk space
    disk_usage = shutil.disk_usage(data_dir)
    disk_free_gb = disk_usage.free / (1024**3)
    
    # Calculate success rate
    success_rate = 0.87  # Default
    if latest_bundle:
        metadata_path = data_dir / latest_bundle / "metadata.json"
        if metadata_path.exists():
            import json
            with open(metadata_path) as f:
                metadata = json.load(f)
                stats = metadata.get('stats', {})
                total = stats.get('total_files', 1)
                successful = stats.get('successful_files', 0)
                success_rate = successful / total if total > 0 else 0
    
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "latest_bundle": latest_bundle,
        "latest_forecast": latest_forecast,
        "disk_free_gb": round(disk_free_gb, 2),
        "data_collection_rate": round(success_rate, 2),
        "version": "1.0.0"
    }
```

**Test:**
```bash
uvicorn src.web.app:app --reload
curl http://localhost:8000/health
```

---

### 3.2 Create Deployment Guide
**Status:** Missing  
**Time:** 30 minutes  
**Impact:** MEDIUM

**Create:** `DEPLOYMENT.md`

```markdown
# SurfCastAI Deployment Guide

## Scheduled Forecasts

### Cron Setup (macOS/Linux)
```bash
# Daily at 6am Hawaii time
0 6 * * * cd /path/to/surfCastAI && source venv/bin/activate && python src/main.py run --mode full >> logs/cron.log 2>&1
```

### Manual Run
```bash
cd /path/to/surfCastAI
source venv/bin/activate
python src/main.py run --mode full
```

## Monitoring

### Health Check
```bash
curl http://localhost:8000/health
```

### Logs
- Application: `logs/surfcastai.log`
- Cron: `logs/cron.log`

### Cost Tracking
Check forecast metadata: `output/<forecast_id>/metadata.json`

## Backup Strategy
- Daily: `data/` directory (raw bundles)
- Weekly: `output/` directory (forecasts)

## Troubleshooting
- API timeouts: Check network connectivity
- High costs: Review model usage in metadata.json
- Data collection failures: External APIs may be down (not our bug)
```

---

### 3.3 Add Automated Cleanup
**Status:** Data accumulates indefinitely  
**Time:** 30 minutes  
**Impact:** LOW - Prevents disk space issues

**Implementation:**
```python
# src/utils/cleanup.py - New file

from pathlib import Path
from datetime import datetime, timedelta
import shutil

def cleanup_old_bundles(data_dir: Path, days_to_keep: int = 30):
    """Remove data bundles older than specified days."""
    cutoff_date = datetime.now() - timedelta(days=days_to_keep)
    
    for bundle_dir in data_dir.glob("*"):
        if not bundle_dir.is_dir():
            continue
            
        bundle_time = datetime.fromtimestamp(bundle_dir.stat().st_mtime)
        if bundle_time < cutoff_date:
            shutil.rmtree(bundle_dir)
            print(f"Removed old bundle: {bundle_dir.name}")

def cleanup_old_forecasts(output_dir: Path, days_to_keep: int = 90):
    """Remove forecasts older than specified days."""
    cutoff_date = datetime.now() - timedelta(days=days_to_keep)
    
    for forecast_dir in output_dir.glob("*"):
        if not forecast_dir.is_dir():
            continue
            
        forecast_time = datetime.fromtimestamp(forecast_dir.stat().st_mtime)
        if forecast_time < cutoff_date:
            shutil.rmtree(forecast_dir)
            print(f"Removed old forecast: {forecast_dir.name}")

if __name__ == "__main__":
    cleanup_old_bundles(Path("data"), days_to_keep=30)
    cleanup_old_forecasts(Path("output"), days_to_keep=90)
```

**Add to cron:**
```bash
# Weekly cleanup on Sunday at 3am
0 3 * * 0 cd /path/to/surfCastAI && source venv/bin/activate && python src/utils/cleanup.py >> logs/cleanup.log 2>&1
```

---

## 💡 PRIORITY 4: ENHANCEMENTS

### 4.1 Optimize Image Selection Strategy
**Status:** Using 10 images, can optimize  
**Time:** 2 hours  
**Impact:** LOW - System working well

**Current Strategy:**
```python
selected_images = self._select_critical_images(images, max_images=10)
```

**Optimization:**
Focus on temporal evolution sequences for better pattern detection:

```python
def _select_critical_images(self, images: Dict[str, List[str]], max_images: int = 8) -> List[Dict[str, Any]]:
    """
    Optimized for temporal evolution analysis.
    
    Priority:
    1. Pressure evolution: 0hr, 24hr, 48hr, 96hr (HIGH detail)
    2. Wave models: 0hr, 48hr, 96hr (AUTO detail)
    3. Satellite: Latest (AUTO detail)
    4. SST: Latest (LOW detail)
    
    Total: 8-9 images, ~15K tokens
    """
    selected = []
    
    # Pressure chart temporal sequence
    pressure_charts = images.get('pressure_charts', [])
    for i, offset in enumerate([0, 24, 48, 96]):
        if i < len(pressure_charts):
            selected.append({
                'url': pressure_charts[i],
                'detail': 'high',
                'type': 'pressure_chart',
                'time_offset': offset,
                'description': f'Surface pressure T+{offset}hr'
            })
    
    # Wave model evolution
    wave_models = images.get('wave_models', [])
    for i, offset in enumerate([0, 48, 96]):
        if i < len(wave_models):
            selected.append({
                'url': wave_models[i],
                'detail': 'auto',
                'type': 'wave_model',
                'time_offset': offset,
                'description': f'Wave forecast T+{offset}hr'
            })
    
    # Latest satellite
    satellite = images.get('satellite', [])
    if satellite:
        selected.append({
            'url': satellite[0],
            'detail': 'auto',
            'type': 'satellite',
            'description': 'Latest satellite'
        })
    
    # SST anomaly (context only)
    sst = images.get('sst_charts', [])
    if sst:
        selected.append({
            'url': sst[0],
            'detail': 'low',
            'type': 'sst_chart',
            'description': 'SST anomaly'
        })
    
    return selected[:max_images]
```

---

### 4.2 Add Model Fallback
**Status:** Single model, no redundancy  
**Time:** 2 hours  
**Impact:** LOW - Current model reliable

**Implementation:**
```python
async def _call_openai_api_with_fallback(self, system_prompt: str, user_prompt: str, **kwargs):
    """
    Call API with automatic fallback.
    
    Hierarchy: gpt-5-nano → gpt-5-mini → gpt-5
    """
    models = [
        ("gpt-5-nano", {"reasoning": {"effort": "medium"}}),
        ("gpt-5-mini", {"reasoning": {"effort": "high"}}),
        ("gpt-5", {"reasoning": {"effort": "high"}})
    ]
    
    for model_name, extra_params in models:
        try:
            self.logger.info(f"Trying {model_name}")
            return await self._call_openai_api(
                system_prompt, user_prompt, 
                model=model_name,
                **{**kwargs, **extra_params}
            )
        except Exception as e:
            self.logger.warning(f"{model_name} failed: {e}")
            if model_name == models[-1][0]:
                raise
            continue
```

---

### 4.3 Add Performance Profiling
**Status:** No profiling  
**Time:** 1 hour  
**Impact:** LOW

**Implementation:**
```python
# src/utils/profiler.py

import time
import functools
import logging

logger = logging.getLogger('profiler')

def profile(func):
    """Profile async function execution time."""
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        start = time.time()
        try:
            result = await func(*args, **kwargs)
            elapsed = time.time() - start
            logger.info(f"{func.__name__}: {elapsed:.2f}s")
            return result
        except Exception as e:
            elapsed = time.time() - start
            logger.error(f"{func.__name__} failed after {elapsed:.2f}s: {e}")
            raise
    return wrapper

# Usage
from src.utils.profiler import profile

@profile
async def generate_forecast(self, swell_forecast):
    # ... existing code ...
```

---

### 4.4 Improve Test Coverage
**Status:** Basic tests exist  
**Time:** 4 hours  
**Impact:** LOW - System stable

**Add Tests:**
```python
# tests/test_cost_tracking.py

import pytest
from unittest.mock import AsyncMock, Mock, patch

@pytest.mark.asyncio
async def test_actual_token_usage_tracking():
    """Test real token usage is tracked, not estimated."""
    config = Mock()
    engine = ForecastEngine(config)
    engine.openai_model = "gpt-5-nano"
    
    with patch('openai.AsyncOpenAI') as mock_client:
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="Test"))]
        mock_response.usage = Mock(
            prompt_tokens=1000,
            completion_tokens=500
        )
        
        mock_client.return_value.chat.completions.create = AsyncMock(
            return_value=mock_response
        )
        
        await engine._call_openai_api("system", "user")
        
        # Verify actual usage tracked
        assert engine.total_input_tokens == 1000
        assert engine.total_output_tokens == 500
        
        # Verify cost calculation
        expected_cost = (1000 * 0.00000005) + (500 * 0.0000004)
        assert abs(engine.total_cost - expected_cost) < 0.000001

@pytest.mark.asyncio
async def test_cost_alert_threshold():
    """Test high cost alerts trigger."""
    config = Mock()
    engine = ForecastEngine(config)
    engine.total_cost = 0.06  # Above 0.05 threshold
    
    with patch.object(engine.logger, 'warning') as mock_warn:
        await engine.generate_forecast(Mock())
        
        # Verify warning logged
        mock_warn.assert_called_once()
        assert "$0.06" in str(mock_warn.call_args)
```

**Run Tests:**
```bash
pytest tests/ -v --cov=src --cov-report=html
open htmlcov/index.html
```

---

## 📚 PRIORITY 5: DOCUMENTATION

### 5.1 Update README
**Status:** Needs minor updates  
**Time:** 30 minutes  
**Impact:** LOW

**Key Sections to Update:**
```markdown
## Cost Estimation

Typical forecast (~$0.005-0.01):
- Data collection: Free (public APIs)
- Image analysis (8-10 images): ~15K tokens
- Text generation: ~5K tokens
- Total: ~20K tokens = $0.005 with gpt-5-nano

Annual cost (daily forecasts): ~$1.83/year
```

---

### 5.2 Document Image Analysis Strategy
**Status:** Not documented  
**Time:** 30 minutes  
**Impact:** LOW

**Add to README or ARCHITECTURE.md:**
```markdown
## Image Analysis Strategy

### Why Temporal Evolution?
Instead of variety (one of each type), we prioritize depth:
- 4 pressure charts (0hr, 24hr, 48hr, 96hr) track system movement
- 3 wave models validate pressure predictions
- Satellite provides cloud pattern validation
- SST provides storm intensity context

This lets GPT-5 detect patterns humans miss by analyzing
complete system evolution simultaneously.

### Detail Levels
- HIGH: Pressure charts (need fine detail for fronts/lows)
- AUTO: Wave models, satellite (balanced quality/cost)
- LOW: SST (anomaly patterns only)

Result: ~15K tokens, optimal for 256K context window
```

---

## 🎯 EXECUTION PLAN

### Week 1: Core Functionality
**Day 1:**
- [ ] Implement actual token usage tracking (1 hour)
- [ ] Add cost alerts (30 min)
- [ ] Test and verify accuracy (30 min)

**Day 2:**
- [ ] Add health check endpoint (1 hour)
- [ ] Create deployment guide (30 min)
- [ ] Test health check (15 min)

**Day 3:**
- [ ] Add automated cleanup (30 min)
- [ ] Update README (30 min)
- [ ] Full system test (1 hour)

### Week 2: Enhancements (Optional)
- [ ] Optimize image selection (2 hours)
- [ ] Add model fallback (2 hours)
- [ ] Add performance profiling (1 hour)
- [ ] Improve test coverage (4 hours)

### External APIs: As Needed
- [ ] Research weather API fix (1-2 hours)
- [ ] Fix wave model timeouts (2 hours)
- [ ] Fix SWAN endpoint (30 min)

---

## ✅ DEFINITION OF DONE

### Core Complete When:
- [ ] Actual token usage tracked (not estimated)
- [ ] Cost alerts configured and tested
- [ ] Health check endpoint working
- [ ] Deployment guide created
- [ ] Automated cleanup running
- [ ] README updated

### Fully Complete When:
- [ ] All enhancements implemented
- [ ] External APIs fixed (optional)
- [ ] Test coverage improved
- [ ] Documentation complete

---

## 📊 SUCCESS METRICS

### Performance
- [ ] <5 minute forecast generation
- [ ] <$0.02 per forecast cost
- [ ] 95%+ daily success rate

### Quality
- [ ] Professional forecast quality maintained
- [ ] Accurate cost tracking
- [ ] All critical systems monitored

---

## 🤝 NOTES FOR CLAUDE CODE

### Project Context
- Personal surf forecasting for Oahu, Hawaii
- Theory: AI ingests more data → superior forecasts
- Using gpt-5-nano/mini for cost efficiency
- System already working, just needs polish

### Priority
1. Token tracking (most important)
2. Monitoring/health checks
3. Cleanup automation
4. Everything else optional

### Testing
- Use gpt-5-nano (cheapest)
- Verify cost calculations accurate
- Test health endpoint
- Full end-to-end run

---

**Generated:** October 4, 2025  
**Version:** 2.0 (Personal Use Focused)  
**Status:** Ready for Execution
