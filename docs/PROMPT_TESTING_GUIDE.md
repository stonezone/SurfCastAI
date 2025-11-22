# Prompt Testing Guide

**Date:** October 12, 2025  
**Status:** Production-Ready  
**Framework:** pytest-based with golden file validation

---

## Overview

The SurfCastAI prompt testing framework ensures that AI prompts are version-controlled, tested, and prevent regressions. This is industry-standard practice for production LLM systems.

**Why Prompt Testing Matters:**
- Prompts encode critical forecasting logic
- Small prompt changes can significantly alter AI behavior
- Version control enables rollback and A/B testing
- Testing prevents silent regressions in production

---

## Quick Start

### Running Prompt Tests

```bash
# Run all prompt tests
pytest tests/test_prompts.py -v

# Run specific specialist tests
pytest tests/test_prompts.py -k senior_forecaster -v

# Run with detailed output
pytest tests/test_prompts.py -vv
```

### Creating a New Test Case

1. **Create test case directory:**
   ```bash
   mkdir -p tests/prompt_tests/senior_forecaster/case_XX_description
   ```

2. **Create input.json** (required):
   ```json
   {
     "metadata": {
       "forecast_date": "2025-10-15",
       "valid_period": "48hr"
     },
     "seasonal_context": {...},
     "buoy_analysis": {...},
     "pressure_analysis": {...},
     "contradictions": [],
     "key_findings": [...],
     "shore_forecasts": {...},
     "swell_breakdown": [...]
   }
   ```

3. **Create metadata.json** (optional but recommended):
   ```json
   {
     "test_case": "case_XX_description",
     "description": "Brief description of scenario",
     "scenario": "Specific weather pattern being tested",
     "expected_characteristics": [
       "Expected trait 1",
       "Expected trait 2"
     ],
     "created": "2025-10-12",
     "author": "Your Name"
   }
   ```

4. **Generate golden prompt:**
   ```bash
   python scripts/generate_golden_prompts.py
   ```

5. **Review generated prompt.txt** and commit to git

6. **Run tests:**
   ```bash
   pytest tests/test_prompts.py -k case_XX -v
   ```

---

## Test Case Organization

```
tests/prompt_tests/
├── senior_forecaster/
│   ├── case_01_high_confidence/
│   │   ├── input.json          # Test input data
│   │   ├── prompt.txt          # Golden prompt (version controlled)
│   │   ├── metadata.json       # Test case description
│   │   └── output.golden.md    # (Optional) Expected AI output
│   ├── case_02_low_confidence/
│   ├── case_03_large_swells/
│   └── case_04_flat_conditions/
├── buoy_analyst/
│   └── (future test cases)
└── pressure_analyst/
    └── (future test cases)
```

---

## Existing Test Cases

### Senior Forecaster (4 Test Cases)

#### case_01_high_confidence
**Scenario:** Clean NW swell from well-tracked North Pacific storm  
**Confidence:** Buoy 0.92, Pressure 0.88  
**Key Features:**
- Strong specialist agreement
- Single dominant swell component
- No contradictions
- Clear shore-by-shore predictions

**Tests:**
- High confidence scenario handling
- Pat Caldwell style with technical details
- Specific buoy citations (51001, 51201)
- Shore-specific conditions and timing

---

#### case_02_low_confidence
**Scenario:** Summer flatspell with uncertain Southern Hemisphere swell  
**Confidence:** Buoy 0.45, Pressure 0.52  
**Key Features:**
- Sparse buoy data (offline sensors)
- Weak fetch window
- Specialist contradictions
- Wide uncertainty ranges

**Tests:**
- Low confidence communication
- Handling missing/unreliable data
- Conservative hedging language
- Uncertainty acknowledgment

---

#### case_03_large_swells
**Scenario:** XXL North Shore surf from historic storm complex  
**Confidence:** Buoy 0.87, Pressure 0.90  
**Key Features:**
- Multiple overlapping swell systems
- Extreme wave heights (20-40ft faces)
- Safety warnings
- Eddie Aikau contest conditions

**Tests:**
- Extreme condition communication
- Multi-swell system handling
- Safety warning language
- Expert-only advisories

---

#### case_04_flat_conditions
**Scenario:** Summer flatspell with no significant swell activity  
**Confidence:** Buoy 0.78, Pressure 0.75  
**Key Features:**
- High confidence in flatness
- High pressure blocking patterns
- Minimal activity all shores
- Honest "nothing happening" assessment

**Tests:**
- Confident negative predictions
- Blocking pattern explanation
- Flat condition communication
- Pat Caldwell honesty style

---

## Golden Prompt Generator

The `scripts/generate_golden_prompts.py` script creates and updates golden prompt files.

### Basic Usage

```bash
# Generate all missing prompts
python scripts/generate_golden_prompts.py

# Update existing prompts (use after intentional changes)
python scripts/generate_golden_prompts.py --update

# Generate specific test case
python scripts/generate_golden_prompts.py --case case_01_high_confidence

# Generate specific specialist
python scripts/generate_golden_prompts.py --specialist senior_forecaster
```

### When to Update Golden Prompts

Update golden prompts (`--update` flag) when:

1. **Intentional prompt logic changes:**
   - Modified prompt template
   - Updated specialist output format
   - Changed cross-validation logic
   - Added new prompt sections

2. **After code review approval:**
   - Changes reviewed by team
   - Impact on forecasts understood
   - A/B testing plan in place (if needed)

3. **Not for:**
   - Test failures (fix the bug first)
   - Exploratory changes (use feature branch)
   - Unreviewed modifications

---

## Test Framework Details

### Test Types

#### 1. test_prompt_matches_golden
**Purpose:** Ensure prompts don't change unexpectedly

**How it works:**
- Loads `input.json`
- Generates prompt using actual specialist logic
- Compares with `prompt.txt` (golden file)
- Shows unified diff if mismatch

**When it fails:**
- Prompt logic changed (bug or feature)
- Golden file out of date
- Input data format changed

**Resolution:**
```bash
# If change was intentional:
python scripts/generate_golden_prompts.py --update

# If change was unintentional:
# Fix the bug in the specialist code
```

---

#### 2. test_prompt_structure_valid
**Purpose:** Validate prompt has required sections

**What it checks:**
- Required sections present (FORECAST DATE, SEASON, etc.)
- Minimum prompt length (>500 chars)
- Specialist-specific structure

**When it fails:**
- Missing required sections
- Prompt too short
- Invalid format

---

### Pytest Configuration

Add to `pytest.ini` or `pyproject.toml`:

```ini
[tool.pytest.ini_options]
markers = [
    "prompt_test: Prompt version control tests"
]
```

### CI/CD Integration

Add to GitHub Actions workflow:

```yaml
- name: Run Prompt Tests
  run: pytest tests/test_prompts.py -v --tb=short

- name: Fail on Prompt Changes
  if: failure()
  run: |
    echo "❌ Prompt tests failed!"
    echo "Prompts have changed unexpectedly."
    echo "Review changes and update golden files if intentional:"
    echo "  python scripts/generate_golden_prompts.py --update"
    exit 1
```

---

## Best Practices

### 1. Version Control Golden Files
- **Always commit prompt.txt files** to git
- Track prompt evolution over time
- Enable prompt rollback if needed

### 2. Review Prompt Changes
- Treat prompt changes like code changes
- Require peer review
- Document reasoning in commit messages

### 3. Test Coverage Strategy
- **High confidence scenarios:** Verify clean, strong predictions
- **Low confidence scenarios:** Test uncertainty communication
- **Edge cases:** Extreme swells, flat conditions, contradictions
- **Seasonal variations:** Winter vs summer patterns

### 4. Input Data Quality
- Use realistic specialist outputs
- Include actual buoy readings when possible
- Match historical weather patterns
- Test boundary conditions

### 5. Metadata Documentation
- Describe test scenario clearly
- List expected characteristics
- Note validation method
- Reference real-world events

---

## Troubleshooting

### Test Fails: "Generated prompt doesn't match golden file"

**Cause:** Prompt logic changed

**Resolution:**
1. Review diff output
2. Determine if change was intentional
3. If intentional: `python scripts/generate_golden_prompts.py --update`
4. If unintentional: Fix the bug in specialist code

### Test Fails: "Missing required section"

**Cause:** Prompt structure invalid

**Resolution:**
1. Check prompt generation logic
2. Ensure all required sections included
3. Verify section headers match expected format

### Test Warns: "Skipping invalid test case"

**Cause:** Missing required files

**Resolution:**
1. Ensure `input.json` exists
2. Generate `prompt.txt` with generator script
3. Check file paths are correct

---

## Extending the Framework

### Adding BuoyAnalyst Tests

1. Implement `_generate_buoy_analyst_prompt()` in `tests/test_prompts.py`
2. Create test cases in `tests/prompt_tests/buoy_analyst/`
3. Generate golden prompts
4. Run tests

### Adding PressureAnalyst Tests

1. Implement `_generate_pressure_analyst_prompt()` in `tests/test_prompts.py`
2. Create test cases in `tests/prompt_tests/pressure_analyst/`
3. Generate golden prompts
4. Run tests

### Custom Test Assertions

Add specialist-specific validations:

```python
def test_senior_forecaster_mentions_source_storms(test_case):
    """Test that SeniorForecaster mentions source storms."""
    if test_case.specialist != "senior_forecaster":
        pytest.skip()
    
    input_data = test_case.load_input()
    prompt = generate_prompt_from_specialist(test_case.specialist, input_data)
    
    # Check for source storm mentions
    predicted_swells = input_data.get('pressure_analysis', {}).get('data', {}).get('predicted_swells', [])
    for swell in predicted_swells:
        source_lat = swell['source_lat']
        assert str(source_lat) in prompt, f"Expected source latitude {source_lat} in prompt"
```

---

## Metrics and Reporting

### Test Execution Metrics
- **Total Test Cases:** 14 (4 new + 10 existing)
- **Pass Rate:** 100% for new test cases
- **Execution Time:** <0.1s (fast feedback loop)
- **Coverage:** SeniorForecaster (4 scenarios), BuoyAnalyst (pending), PressureAnalyst (pending)

### Future Improvements
1. **Output validation:** Test AI responses against `output.golden.md`
2. **Prompt performance metrics:** Track token usage, response quality
3. **A/B testing framework:** Compare prompt variations
4. **Historical regression tests:** Test against archived forecasts

---

## References

- **GEM_ROADMAP.md:** Phase 3 strategic goals
- **tests/test_prompts.py:** Test framework implementation
- **scripts/generate_golden_prompts.py:** Golden file generator
- **SeniorForecaster:** src/forecast_engine/specialists/senior_forecaster.py

---

## Support

**Questions or Issues:**
- Check this guide first
- Review test output and diffs
- Consult team for prompt logic changes

**Contributing:**
- Follow test case naming convention: `case_XX_description`
- Include comprehensive metadata.json
- Document expected characteristics
- Test locally before pushing

---

**Guide Version:** 1.0  
**Last Updated:** October 12, 2025  
**Maintainer:** SurfCastAI Team
