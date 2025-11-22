# Prompt Testing Framework

## Overview

This directory contains automated tests for AI prompts used in SurfCastAI. Prompt testing is a critical practice for production LLM systems, ensuring that prompt changes don't introduce regressions or unexpected behavior changes.

## Directory Structure

```
tests/prompt_tests/
├── README.md (this file)
├── senior_forecaster/
│   ├── test_case_01_high_confidence/
│   │   ├── input.json
│   │   └── prompt.txt
│   ├── test_case_02_low_confidence/
│   │   ├── input.json
│   │   └── prompt.txt
│   └── ... (more test cases)
└── ... (future: buoy_analyst/, pressure_analyst/)
```

## Test Case Structure

Each test case is a directory containing:

### Required Files

1. **`input.json`** - Input data for the prompt
   - Contains all data needed to generate the prompt
   - For SeniorForecaster: buoy_analysis, pressure_analysis, shore_forecasts, etc.
   - Must be valid JSON matching the expected schema

2. **`prompt.txt`** - The "golden" generated prompt
   - The expected output after processing input.json
   - Version controlled to detect unintended prompt changes
   - Updated manually when prompt changes are intentional and reviewed

### Optional Files

3. **`output.golden.md`** - Expected AI model output (future use)
   - For validating AI responses against known-good outputs
   - Requires live API calls or mock responses
   - Not implemented in initial version

## Running Tests

```bash
# Run all prompt tests
pytest tests/test_prompts.py

# Run tests for specific specialist
pytest tests/test_prompts.py -k senior_forecaster

# Verbose output showing diffs
pytest tests/test_prompts.py -v
```

## How Tests Work

1. Test runner discovers all test cases by scanning subdirectories
2. For each test case:
   - Loads `input.json`
   - Generates prompt using actual application logic
   - Compares generated prompt to `prompt.txt`
   - Fails if prompts don't match (indicates unintended change)

## Adding New Test Cases

### Step 1: Create Test Case Directory

```bash
mkdir tests/prompt_tests/senior_forecaster/test_case_XX_description
```

### Step 2: Create input.json

Create input data matching the specialist's expected schema:

```json
{
  "buoy_analysis": {
    "confidence": 0.85,
    "narrative": "Strong NW swell showing...",
    "data": { ... }
  },
  "pressure_analysis": {
    "confidence": 0.90,
    "narrative": "Deep Aleutian low...",
    "data": { ... }
  },
  "shore_forecasts": { ... },
  "swell_breakdown": [ ... ],
  "seasonal_context": { ... },
  "metadata": {
    "forecast_date": "2025-10-15",
    "valid_period": "48-hour"
  }
}
```

### Step 3: Generate Initial prompt.txt

Run the test to generate the initial prompt:

```bash
# This will fail but show the generated prompt
pytest tests/test_prompts.py::test_senior_forecaster_prompts -v

# Copy the generated prompt to prompt.txt
# (Or use a helper script when available)
```

### Step 4: Review and Commit

1. Review the generated prompt for correctness
2. Commit both `input.json` and `prompt.txt` to version control
3. Future changes to prompt logic will be caught by tests

## Updating Golden Files

When you intentionally change prompt generation logic:

1. **Review the change carefully** - Prompt changes affect AI output
2. **Run tests to see diffs** - `pytest tests/test_prompts.py -v`
3. **Update golden files** - If changes are correct:
   ```bash
   # Update specific test case (manual process for now)
   # Copy new generated prompt to prompt.txt
   ```
4. **Document the change** - In commit message, explain why prompt changed
5. **Monitor AI output** - After deploying, verify forecasts remain high quality

## Test Scenarios

### SeniorForecaster Test Cases

Recommended scenarios to cover:

1. **High Confidence** - All data sources agree, strong signals
2. **Low Confidence** - Missing data, source disagreement
3. **No Swells** - Flat conditions, minimal activity
4. **Large NW Swell** - Winter scenario, big North Shore surf
5. **Multiple Swells** - Overlapping swell trains
6. **Contradictions** - Buoy vs model disagreement
7. **Missing Data** - Partial buoy coverage, degraded confidence
8. **Summer Pattern** - Small south swells, trade winds
9. **Winter Pattern** - North swells, variable winds
10. **Mixed Conditions** - Multiple shores active

## Benefits

- **Prevent Regressions** - Catch unintended prompt changes before production
- **Version Control** - Prompts are tracked like code
- **Documentation** - Test cases serve as examples of expected behavior
- **Confidence** - Deploy prompt changes knowing they're validated
- **Debugging** - When AI output degrades, check if prompts changed

## Future Enhancements

- Helper script to update golden files after review
- AI output validation (output.golden.md comparison)
- CI/CD integration for automated prompt validation
- Prompt diff visualization tool
- Performance benchmarking for prompt generation

## References

- **GEM_ROADMAP.md** - Phase 3 implementation details
- **src/forecast_engine/specialists/** - Prompt generation logic
- **tests/test_prompts.py** - Test runner implementation

---

**Last Updated:** 2025-10-10
**Status:** Framework implemented, test cases in development
