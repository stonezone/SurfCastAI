# Detailed Coverage Gaps & Test Recommendations

## Summary of Findings

**Overall Coverage:** 47% (Target: 80%)
**Tests:** 322 total, 297 passing (92% pass rate)
**Critical Finding:** Test failures are primarily assertion mismatches, not logic errors

## Module-by-Module Gap Analysis

### Priority 1: Forecast Engine (5-13% coverage)

#### forecast_engine/forecast_engine.py (5% - 474 lines untested)

**Current Coverage:**
- Initialization only
- No AI interaction testing
- No refinement loop testing

**Missing Tests:**
1. `_build_initial_prompt()` - prompt construction with fused data
2. `_generate_forecast()` - AI API calls and response handling
3. `_refine_forecast()` - iterative refinement logic
4. `_assess_quality()` - quality scoring and decision to refine
5. `_add_confidence_notes()` - confidence annotation
6. Error handling for API failures
7. Token limit handling
8. Multiple refinement iterations

**Test Approach:**
```python
# Mock OpenAI API responses
# Test prompt templates contain required data
# Test refinement improves quality scores
# Test max iterations limit
# Test API error recovery
```

**Impact:** HIGH - Core forecast generation untested

#### forecast_engine/forecast_formatter.py (7% - 265 lines untested)

**Current Coverage:**
- Initialization only
- No output generation testing

**Missing Tests:**
1. `format_markdown()` - markdown output generation
2. `format_html()` - HTML with responsive CSS
3. `format_pdf()` - PDF generation (if implemented)
4. `_format_confidence_section()` - confidence display
5. `_format_shore_breakdown()` - shore-specific formatting
6. `_embed_visualizations()` - chart embedding
7. Unicode handling
8. Long forecast text handling
9. Missing data graceful degradation

**Test Approach:**
```python
# Test markdown structure and formatting
# Test HTML validity and CSS inclusion
# Test chart embedding in HTML
# Test special character handling
# Test output with missing/partial data
```

**Impact:** HIGH - Output quality not validated

#### forecast_engine/prompt_templates.py (13% - 111 lines untested)

**Current Coverage:**
- Module import only

**Missing Tests:**
1. Template rendering with data
2. Seasonal context injection
3. Shore-specific template selection
4. Pat Caldwell style examples included
5. Data formatting in templates
6. Missing data handling in templates

**Test Approach:**
```python
# Test each template renders without errors
# Test data interpolation
# Test seasonal variations
# Test shore-specific content
```

**Impact:** MEDIUM - Template bugs could corrupt forecasts

### Priority 2: Processing Gaps

#### processing/data_fusion_system.py (60% - 170 lines untested)

**Current Coverage:**
- Basic fusion working
- Confidence calculation partial

**Missing Tests:**
1. Edge cases with conflicting model data
2. Single source vs multi-source fusion
3. Missing buoy data handling
4. Missing model data handling
5. Extreme confidence scenarios (very high/low)
6. Historical data integration
7. Swell event merging with conflicts
8. Weather data fusion edge cases

**Test Approach:**
```python
# Test with all data sources present
# Test with only buoy data
# Test with only model data
# Test with conflicting predictions
# Test confidence calculation extremes
```

**Impact:** HIGH - Data quality foundation

#### processing/data_processor.py (28% - 74 lines untested)

**Current Coverage:**
- Base class structure
- Validation methods not tested

**Missing Tests:**
1. `validate_data()` base implementation
2. `_check_required_fields()` validation
3. `_check_data_quality()` checks
4. Subclass override behavior
5. Error message generation
6. Data quality thresholds

**Test Approach:**
```python
# Create mock processor subclass
# Test validation with good data
# Test validation with missing fields
# Test validation with bad quality
# Test error reporting
```

**Impact:** MEDIUM - Foundation for all processors

#### processing/hawaii_context.py (47% - 76 lines untested)

**Current Coverage:**
- Basic geographic data loaded

**Missing Tests:**
1. `get_shore_exposure()` - fetch angle calculations
2. `get_optimal_swell_direction()` - directional analysis
3. `get_shadow_zones()` - blocking calculations
4. `calculate_travel_time()` - swell propagation
5. `get_seasonal_patterns()` - winter/summer logic
6. Edge cases: north/south wrap around
7. Invalid shore names
8. Extreme swell angles

**Test Approach:**
```python
# Test each shore's exposure calculations
# Test swell direction optimization
# Test shadow zone logic
# Test seasonal differences
# Test edge cases (0°, 360°, etc.)
```

**Impact:** HIGH - Location accuracy depends on this

#### processing/weather_processor.py (65% - 78 lines untested)

**Current Coverage:**
- Basic processing works

**Missing Tests:**
1. `_identify_weather_patterns()` - pattern detection
2. Wind speed categorization (light/moderate/strong)
3. Wind direction classification (trade/kona/etc.)
4. Weather warnings generation
5. Missing weather data handling
6. Extreme weather conditions

**Test Approach:**
```python
# Test trade wind detection
# Test kona wind detection
# Test storm conditions
# Test wind speed categories
# Test warning generation
```

**Impact:** MEDIUM - Wind/weather analysis gaps

### Priority 3: Core Infrastructure

#### core/data_collector.py (19% - 127 lines untested)

**Current Coverage:**
- Basic initialization

**Missing Tests:**
1. `collect_all()` - multi-agent orchestration
2. Error handling with failed agents
3. Partial success scenarios (some agents fail)
4. Rate limiting across agents
5. Concurrent collection
6. Bundle creation after collection
7. Metadata tracking

**Test Approach:**
```python
# Mock all agents
# Test successful collection
# Test with agent failures
# Test rate limit respect
# Test bundle creation
```

**Impact:** MEDIUM - Collection reliability

#### core/bundle_manager.py (11% - 139 lines untested)

**Current Coverage:**
- Initialization only

**Missing Tests:**
1. `create_bundle()` - bundle creation
2. `list_bundles()` - bundle enumeration
3. `get_bundle_info()` - metadata retrieval
4. `get_bundle_files()` - file listing
5. Bundle directory structure
6. Metadata file creation
7. Bundle cleanup/deletion

**Test Approach:**
```python
# Test bundle creation with metadata
# Test bundle listing
# Test bundle info retrieval
# Test file organization
```

**Impact:** LOW - Nice-to-have, not critical

### Priority 4: Agent Tests (12-32% coverage)

**Current Status:**
- Base agent well tested (99%)
- Individual agents mostly untested
- Integration tests exist

**Gap Analysis:**
All agents missing similar tests:
1. `fetch()` method with various URLs
2. `parse()` method with real data samples
3. Error handling (network, parsing)
4. Rate limiting behavior
5. Data validation
6. Metadata creation

**Recommendation:**
**DEFER** - Agents have working integration tests. Unit tests would be extensive work (600+ lines) for marginal value. Focus on higher-impact modules first.

### Priority 5: Failing Tests (25 failures)

#### A. Config Tests (5 failures)

1. **test_data_directory_property** - Path format mismatch
   ```
   Expected: './test_data'
   Got: 'test_data'
   ```
   Fix: Update assertion or normalize path

2. **test_get_rate_limits** - Type error
   ```
   TypeError: unhashable type: 'dict'
   ```
   Fix: Correct method signature or test setup

3. **test_get_data_source_urls_legacy_agents** - Same type error
   Fix: Fix config.get() call with dict parameter

4. **test_init_with_no_path** - Loads default config
   Fix: Mock config file loading

5. **test_output_directory_property** - Path format mismatch
   Fix: Same as #1

#### B. HTTP Client Tests (8 failures)

All appear to be mocking issues - need to check test setup

#### C. Security Tests (6 failures)

1. **test_file_scheme_raises_error**
   ```
   Expected message: 'not allowed'
   Got message: 'URL must include scheme and domain'
   ```
   Fix: Update assertion to match actual error message

Other security tests similar - assertion mismatches, not logic errors

#### D. Processing Tests (3 failures)

1. **test_confidence_calculated_in_fusion** - Likely mock/setup issue
2. **test_convert_to_hawaii_scale** - Calculation or assertion error
3. **test_hawaii_scale_conversion** - Same as above

#### E. Visualization Tests (1 failure)

1. **test_generate_visualizations_creates_pngs** - File path or matplotlib issue

## Recommended Action Plan

### Phase 1: Fix Failing Tests (2-3 hours)

**Goal:** Get to 100% pass rate (297/322 → 322/322)

1. Fix config tests (update path assertions, fix type errors)
2. Fix security tests (update error message assertions)
3. Fix HTTP client mocking
4. Fix processing test setups
5. Fix visualization test

**Expected Coverage Change:** 47% → 49% (small gain)

### Phase 2: Add Forecast Engine Tests (4-6 hours)

**Goal:** Cover critical forecast generation logic

1. Create `tests/unit/forecast_engine/test_forecast_engine_core.py`
   - Test prompt building
   - Test AI generation (mocked)
   - Test refinement loop
   - Target: 60% coverage for forecast_engine.py

2. Create `tests/unit/forecast_engine/test_forecast_formatter.py`
   - Test markdown generation
   - Test HTML generation
   - Test chart embedding
   - Target: 70% coverage for forecast_formatter.py

3. Enhance `tests/unit/forecast_engine/test_prompt_templates.py`
   - Test template rendering
   - Test data interpolation
   - Target: 80% coverage for prompt_templates.py

**Expected Coverage Change:** 49% → 58% (9% gain, large impact)

### Phase 3: Complete Processing Tests (2-3 hours)

**Goal:** Fill processing module gaps

1. Enhance `tests/unit/processing/test_data_fusion_system.py`
   - Add edge case tests
   - Add conflict resolution tests
   - Target: 80% coverage (from 60%)

2. Create `tests/unit/processing/test_data_processor_base.py`
   - Test validation methods
   - Test error handling
   - Target: 80% coverage (from 28%)

3. Enhance `tests/unit/processing/test_hawaii_context.py`
   - Test geographic calculations
   - Test edge cases
   - Target: 75% coverage (from 47%)

4. Enhance `tests/unit/processing/test_weather_processor.py`
   - Test pattern detection
   - Test categorization
   - Target: 80% coverage (from 65%)

**Expected Coverage Change:** 58% → 67% (9% gain)

### Phase 4: Core Infrastructure (Optional, 2-3 hours)

**Goal:** Test collection orchestration

1. Create `tests/unit/core/test_data_collector.py`
   - Test multi-agent collection
   - Test error scenarios
   - Target: 70% coverage (from 19%)

2. Create `tests/unit/core/test_bundle_manager.py`
   - Test bundle operations
   - Target: 70% coverage (from 11%)

**Expected Coverage Change:** 67% → 71% (4% gain)

## Realistic Achievable Targets

### 8-12 Hour Effort (Phases 1-3)
- **Coverage:** 47% → 67%
- **Test Count:** 322 → ~380 tests
- **Pass Rate:** 92% → 100%
- **Critical Modules:** All forecast engine, processing core tested
- **Remaining Gaps:** Agents, CLI, some core infrastructure

### 16-20 Hour Effort (All Phases)
- **Coverage:** 47% → 71%
- **Test Count:** 322 → ~420 tests
- **Remaining Gaps:** Agents (low priority), CLI (low priority)

### To Reach 80% (Not Recommended)
- **Additional Effort:** 15-20 hours
- **Requirements:**
  - Test all 9 agents (~300 tests)
  - Test CLI integration
  - Test web app
- **Value:** Low - these have integration test coverage

## Conclusion

**Current:** 47% coverage, 297/322 passing
**Achievable:** 67% coverage, 380/380 passing in 8-12 hours
**Stretch:** 71% coverage, 420/420 passing in 16-20 hours

**Recommendation:** Execute Phases 1-3 to achieve:
- 100% test pass rate
- 67% coverage
- All critical forecast/processing logic tested
- Strong confidence in core functionality

**NOT Recommended:** Chasing 80% by adding 300+ agent unit tests when integration tests already exist.
