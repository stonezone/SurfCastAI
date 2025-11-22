# Test Coverage Quick Reference
**Last Updated:** 2025-10-14

## TL;DR - Critical Findings

**DOCUMENTATION CLAIM:** "90 tests, 100% passing, 93% coverage"
**ACTUAL REALITY:** 1,017 tests, 96.6% passing (35 failures), 66% coverage

**COVERAGE GAP:** -27 percentage points (66% vs 93% claimed)

---

## Quick Stats

| Metric | Claimed | Actual | Status |
|--------|---------|--------|--------|
| Total Tests | 90 | 1,017 | +927 tests |
| Pass Rate | 100% | 96.6% | 35 failures |
| Overall Coverage | 93% | 66% | -27 points |
| Quick Wins Tests | 90, 100% | 98, 99% | ACCURATE |
| Quick Wins Coverage | 93% | 91% | ACCURATE |

---

## Immediate Action Items (Week 1)

### 1. Fix 19 Outdated Test Assertions
```bash
# HTTP Client (8 failures)
pytest tests/unit/core/test_http_client.py -v

# Security (6 failures)
pytest tests/unit/utils/test_security.py -v

# Config (5 failures)
pytest tests/unit/core/test_config.py -v
```

**Root Cause:** Test assertions don't match evolved implementation
**Expected Impact:** 96.6% → 98.1% pass rate

---

### 2. Regenerate 12 Golden Snapshots
```bash
# Regenerate senior forecaster snapshots
pytest tests/test_prompts.py --update-snapshots
```

**Root Cause:** SeniorForecaster output format changed (Pydantic/Quick Wins)
**Expected Impact:** 98.1% → 99.8% pass rate

---

### 3. Update CLAUDE.md Documentation
**Current (INCORRECT):**
```markdown
- "90 tests, 100% passing, 93% coverage"
```

**Corrected:**
```markdown
- **Total Tests:** 1,017 (96.6% passing, 35 failing)
- **Quick Wins Tests:** 98 (99% passing)
- **Overall Coverage:** 66% (target: 90%)
- **Quick Wins Coverage:** 91% (exceeds 90% target)
```

---

## Critical Coverage Gaps

### TIER 1 - Production Blockers (<50%)

| File | Coverage | Missing | Priority |
|------|----------|---------|----------|
| forecast_engine.py | 29% | 288 | CRITICAL |
| main.py | 14% | 438 | CRITICAL |
| metadata_tracker.py | 14% | 108 | CRITICAL |
| hawaii_context.py | 47% | 76 | CRITICAL |
| prompt_templates.py | 34% | 104 | CRITICAL |
| data_processor.py | 28% | 74 | CRITICAL |

### TIER 2 - Below Target (50-80%)

| File | Coverage | Missing | Priority |
|------|----------|---------|----------|
| data_fusion_system.py | 57% | 225 | HIGH |
| bundle_manager.py | 58% | 119 | HIGH |
| data_collector.py | 66% | 54 | MEDIUM |
| forecast_formatter.py | 65% | 101 | MEDIUM |
| http_client.py | 78% | 54 | HIGH (8 tests failing!) |

---

## Test Execution Commands

### Run Full Suite
```bash
pytest tests/ -v --tb=short
```

### Run with Coverage
```bash
pytest tests/ --cov=src --cov-report=term-missing --cov-report=html
```

### Run Quick Wins Only
```bash
pytest tests/unit/processing/test_storm_detector.py \
       tests/unit/utils/test_validation_feedback.py \
       tests/integration/test_validation_feedback_integration.py \
       tests/unit/processing/test_spectral_analyzer.py -v
```

### View Coverage Report
```bash
open htmlcov/index.html  # macOS
```

---

## Failing Tests Breakdown (35 total)

| Category | Count | % | Root Cause |
|----------|-------|---|------------|
| Prompt Snapshots | 12 | 34.3% | Stale golden snapshots |
| HTTP Client | 8 | 22.9% | Async mock setup wrong |
| Security | 6 | 17.1% | Test assertions outdated |
| Config | 5 | 14.3% | Test assertions outdated |
| Data Fusion | 3 | 8.6% | Formula changed |
| Wave Model | 1 | 2.9% | Formula changed |

---

## Path to 90% Coverage (12-week roadmap)

| Weeks | Task | Coverage Gain | Cumulative |
|-------|------|---------------|------------|
| 1-2 | Fix failing tests | +0% | 66% |
| 3-4 | Test ForecastEngine (29%→80%) | +2% | 68% |
| 5-6 | Test DataFusionSystem (57%→85%) | +1.5% | 69.5% |
| 7-8 | Test main.py (14%→70%) | +3% | 72.5% |
| 9-10 | Test BundleManager (58%→85%) | +1% | 73.5% |
| 11-12 | Add agent smoke tests | +5% | 78.5% |
| Ongoing | Fill remaining gaps | +11.5% | **90%** |

**Total Effort:** 8-10 weeks (2-3 months)

---

## Risk Summary

### Production Risks (HIGH)
- ForecastEngine (29%) - Core logic largely untested
- DataFusionSystem (57%) - Multi-source integration gaps
- HTTPClient (78% + 8 failing tests) - Network layer broken

### Operational Risks (MEDIUM)
- main.py (14%) - CLI commands minimally tested
- BundleManager (58%) - Data lifecycle gaps
- 35 failing tests - Mask real regressions

### Technical Debt (MEDIUM)
- 12 stale golden snapshots
- 19 outdated test assertions
- Documentation 27 points off reality

---

## What's Working Well

- Quick Wins features: 91% avg coverage (storm, spectral, validation)
- Specialist system: 87% avg coverage (buoy, pressure, senior)
- Pydantic schemas: 100% coverage
- Test infrastructure: 1,017 tests, fast execution (15.93s)
- Validation system: 87-95% coverage

---

## Grade: C+ (72/100)

**Current State:** Good specialist testing, poor core testing
**Achievable (3mo):** A- (90/100) with focused effort

---

## Full Report
See: `/Users/zackjordan/code/surfCastAI/TEST_COVERAGE_ANALYSIS_REPORT.md`
