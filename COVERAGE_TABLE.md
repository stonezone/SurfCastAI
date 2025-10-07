# Test Coverage Summary - By Module

## Overall: 47% Coverage (3,095 of 6,517 lines)

### Critical Gaps (Below 60%)

| Module | Lines | Covered | Coverage | Priority | Impact |
|--------|-------|---------|----------|----------|--------|
| **forecast_engine.py** | 500 | 26 | 5% | 🔥🔥🔥🔥🔥 | CRITICAL |
| **forecast_formatter.py** | 285 | 20 | 7% | 🔥🔥🔥🔥 | CRITICAL |
| **prompt_templates.py** | 128 | 17 | 13% | 🔥🔥🔥 | HIGH |
| **local_generator.py** | 239 | 36 | 15% | 🔥🔥 | MEDIUM |
| **model_settings.py** | 26 | 12 | 46% | 🔥 | LOW |
| **visualization.py** | 124 | 67 | 54% | 🔥🔥 | MEDIUM |
| **data_processor.py** | 103 | 29 | 28% | 🔥🔥🔥 | HIGH |
| **hawaii_context.py** | 143 | 67 | 47% | 🔥🔥🔥 | HIGH |

### Modules Approaching Target (60-79%)

| Module | Lines | Covered | Coverage | Status |
|--------|-------|---------|----------|--------|
| data_fusion_system.py | 428 | 258 | 60% | ⚠ Close |
| weather_processor.py | 226 | 148 | 65% | ⚠ Close |
| buoy_data.py | 64 | 45 | 70% | ⚠ Close |
| http_client.py | 247 | 191 | 77% | ⚠ Close |
| database.py | 68 | 53 | 78% | ⚠ Close |
| buoy_processor.py | 248 | 197 | 79% | ⚠ Close |

### Modules Meeting Target (80%+)

| Module | Lines | Covered | Coverage | Status |
|--------|-------|---------|----------|--------|
| wave_model.py | 86 | 73 | 85% | ✓ Good |
| surf_observation.py | 21 | 18 | 86% | ✓ Good |
| buoy_fetcher.py | 110 | 96 | 87% | ✓ Good |
| forecast_parser.py | 226 | 196 | 87% | ✓ Good |
| weather_data.py | 93 | 82 | 88% | ✓ Good |
| exceptions.py | 25 | 22 | 88% | ✓ Good |
| config.py | 136 | 120 | 88% | ✓ Good |
| confidence_scorer.py | 151 | 135 | 89% | ✓ Good |
| wave_model_processor.py | 324 | 292 | 90% | ✓ Excellent |
| source_scorer.py | 175 | 161 | 92% | ✓ Excellent |
| historical.py | 74 | 69 | 93% | ✓ Excellent |
| forecast_validator.py | 174 | 161 | 93% | ✓ Excellent |
| security.py | 62 | 58 | 94% | ✓ Excellent |
| rate_limiter.py | 95 | 94 | 99% | ✓ Excellent |
| base_agent.py | 69 | 68 | 99% | ✓ Excellent |

### Untested Modules (0-20%)

| Module | Lines | Covered | Coverage | Category |
|--------|-------|---------|----------|----------|
| main.py | 413 | 0 | 0% | CLI Entry |
| web/app.py | 68 | 0 | 0% | Web Server |
| bundle_manager.py | 157 | 18 | 11% | Infrastructure |
| buoy_agent.py | 152 | 19 | 12% | Data Collection |
| satellite_agent.py | 155 | 19 | 12% | Data Collection |
| model_agent.py | 157 | 21 | 13% | Data Collection |
| metadata_tracker.py | 126 | 18 | 14% | Infrastructure |
| metar_agent.py | 137 | 21 | 15% | Data Collection |
| weather_agent.py | 92 | 14 | 15% | Data Collection |
| data_collector.py | 156 | 29 | 19% | Infrastructure |

## Test Statistics

- **Total Tests:** 322
- **Passing:** 297 (92.2%)
- **Failing:** 25 (7.8%)
- **Total Lines:** 6,517
- **Covered Lines:** 3,095
- **Coverage:** 47.5%

## Coverage by Category

| Category | Modules | Avg Coverage | Status |
|----------|---------|--------------|--------|
| Validation | 5 | 86% | ✓ Excellent |
| Processing | 12 | 73% | ⚠ Close |
| Forecast Engine | 7 | 33% | ✗ Critical Gap |
| Core Infrastructure | 6 | 51% | ⚠ Mixed |
| Data Collection Agents | 9 | 28% | ✗ Minimal |
| Utilities | 2 | 91% | ✓ Excellent |

## Priority Action Items

### Must Fix (Highest Impact)
1. forecast_engine.py (5% → 60% target) - 270 lines
2. forecast_formatter.py (7% → 70% target) - 180 lines
3. data_fusion_system.py (60% → 80% target) - 85 lines

### Should Fix (High Impact)
4. prompt_templates.py (13% → 80% target) - 85 lines
5. data_processor.py (28% → 80% target) - 54 lines
6. hawaii_context.py (47% → 75% target) - 40 lines

### Could Fix (Medium Impact)
7. weather_processor.py (65% → 80% target) - 34 lines
8. buoy_processor.py (79% → 85% target) - 15 lines
9. visualization.py (54% → 75% target) - 26 lines

## Effort vs Impact Analysis

### Quick Wins (5 hours, +7% coverage)
- forecast_formatter.py tests (2h, +63%)
- prompt_templates.py tests (1.5h, +67%)
- data_processor.py tests (1.5h, +52%)

### Medium Wins (8 hours, +11% coverage)
- forecast_engine.py tests (4h, +55%)
- data_fusion_system.py tests (2h, +20%)
- hawaii_context.py tests (2h, +28%)

### Comprehensive (15 hours, +20% coverage)
- All above + fix 25 failing tests
- Target: 67% overall coverage

## Conclusion

**Realistic Target:** 67% coverage in 13-15 hours
**Critical Gap:** Forecast engine (5% coverage)
**Strength:** Validation system (86% coverage)
**Not Worth It:** Agent unit tests (15h for 8% gain)
