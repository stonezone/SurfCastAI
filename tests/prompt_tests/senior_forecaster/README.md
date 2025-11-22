# Senior Forecaster Prompt Tests

This directory contains test cases for validating the SeniorForecaster prompt generation logic.

## Purpose

The prompt testing framework prevents AI prompt regressions by:
- Validating that prompt generation logic produces consistent results
- Capturing golden reference prompts for comparison
- Detecting unintended changes to prompt templates or logic

## Directory Structure

Each subdirectory is one test case:

```
senior_forecaster/
├── README.md                    # This file
├── test_case_01_example/        # Example test case
│   ├── input.json              # Input data (Pydantic model data)
│   └── prompt.txt              # Golden reference prompt (expected output)
└── test_case_02_another/
    ├── input.json
    └── prompt.txt
```

## Test Case Format

### input.json

Contains the input data for `SeniorForecaster._generate_caldwell_narrative()`:

```json
{
  "buoy_analysis": {
    "confidence": 0.85,
    "data": {
      "trends": [...],
      "anomalies": [...],
      "quality_flags": {...},
      "cross_validation": {...},
      "summary_stats": {...}
    },
    "narrative": "Buoy analyst report...",
    "metadata": {}
  },
  "pressure_analysis": {
    "confidence": 0.90,
    "data": {
      "systems": [...],
      "predicted_swells": [...],
      "frontal_boundaries": [...],
      "analysis_summary": {...}
    },
    "narrative": "Pressure analyst report...",
    "metadata": {}
  },
  "swell_events": [...],
  "shore_data": {...},
  "seasonal_context": {
    "season": "winter",
    "typical_patterns": {...}
  },
  "metadata": {
    "forecast_date": "2025-10-09",
    "valid_period": "48hr"
  }
}
```

### prompt.txt

Contains the expected combined prompt (system_prompt + user_prompt) that should be generated:

```
You are Pat Caldwell, Hawaii's legendary surf forecaster with 40+ years experience.

Your writing style:
- Technical but accessible (explain the meteorology)
- Specific measurements (cite buoy numbers, pressure values, fetch distances)
...

[System prompt continues...]

[User prompt with data follows...]
```

## Creating a New Test Case

### Method 1: Manual Creation

1. Create a new directory with a descriptive name:
   ```bash
   mkdir -p tests/prompt_tests/senior_forecaster/test_case_winter_north_swell
   ```

2. Create `input.json` with test data:
   ```bash
   # Copy and modify an existing test case
   cp tests/prompt_tests/senior_forecaster/test_case_01_example/input.json \
      tests/prompt_tests/senior_forecaster/test_case_winter_north_swell/input.json

   # Edit the file with your test data
   ```

3. Generate the golden prompt:
   ```bash
   # Run the forecaster with your input data
   # Copy the generated prompt to prompt.txt
   ```

### Method 2: Using the Template Generator

The test file includes a utility function for generating test case templates:

```bash
python tests/test_prompts.py generate test_case_winter_north_swell
```

This creates:
- `test_case_winter_north_swell/input.json` (template)
- `test_case_winter_north_swell/prompt.txt` (template)

Then:
1. Edit `input.json` with actual test data
2. Run the forecaster to generate the actual prompt
3. Copy the generated prompt to `prompt.txt`
4. Run tests to verify: `pytest tests/test_prompts.py -v`

## Running Tests

```bash
# Run all prompt tests
pytest tests/test_prompts.py

# Run with verbose output
pytest tests/test_prompts.py -v

# Run a specific test case
pytest tests/test_prompts.py -k "test_case_01"

# Show diff output on failure
pytest tests/test_prompts.py -vv
```

## Test Output

When a test fails, you'll see:
- A unified diff showing the differences
- Line-by-line comparison of expected vs actual
- Instructions for updating the golden file (if intentional)

Example failure output:
```
FAILED tests/test_prompts.py::test_senior_forecaster_prompt_generation[test_case_01]

================================================================================
Prompt mismatch in test case: test_case_01
================================================================================

Generated prompt differs from golden prompt.txt:

--- test_case_01/prompt.txt (expected)
+++ test_case_01/generated (actual)
@@ -10,7 +10,7 @@
 - Technical but accessible (explain the meteorology)
-- Specific measurements (cite buoy numbers, pressure values, fetch distances)
++ Specific measurements (cite buoy readings, pressure values, fetch distances)

To update golden file (if changes are intentional):
  cat > tests/prompt_tests/senior_forecaster/test_case_01/prompt.txt <<'EOF'
[new prompt content]
EOF
```

## Updating Golden Files

When you intentionally change prompt generation logic:

1. Run tests and verify the changes in the diff output
2. If changes are correct, update the golden file:
   ```bash
   # The test output provides the exact command
   cat > tests/prompt_tests/senior_forecaster/test_case_01/prompt.txt <<'EOF'
   [copy new prompt here]
   EOF
   ```
3. Re-run tests to verify: `pytest tests/test_prompts.py`

## Best Practices

1. **Test Case Naming**: Use descriptive names that indicate what scenario is being tested
   - Good: `test_case_01_winter_nw_swell_high_confidence`
   - Bad: `test1`

2. **Coverage**: Create test cases for:
   - Different seasons (winter vs summer)
   - Different confidence levels
   - Contradictions between specialists
   - Edge cases (no buoy data, no pressure data)
   - High/low specialist agreement

3. **Golden Files**: Treat `prompt.txt` as source code
   - Review changes carefully before updating
   - Document why prompts changed in commit messages
   - Use version control to track prompt evolution

4. **Input Data**: Keep `input.json` realistic
   - Use actual data structures from specialist outputs
   - Include edge cases that might break prompt generation
   - Ensure Pydantic models validate successfully

## Troubleshooting

### "No test cases found"
- Make sure you're in the right directory
- Check that test case directories exist
- Verify each has both `input.json` and `prompt.txt`

### "Failed to convert input to Pydantic models"
- Validate `input.json` against Pydantic schemas
- Check for typos in field names
- Ensure enum values are valid strings

### "System prompt was not captured"
- Check that mock setup is correct
- Verify `engine.call_openai_api()` is being called
- Ensure async/await is handled properly

### Tests pass but prompt looks wrong
- Verify you're comparing the right parts of the prompt
- Check that system_prompt + user_prompt combination is correct
- Review the diff carefully

## Integration with CI/CD

Add to your CI pipeline:

```yaml
# .github/workflows/tests.yml
- name: Run prompt validation tests
  run: pytest tests/test_prompts.py -v --tb=short
```

This ensures prompt regressions are caught before deployment.

## See Also

- `/Users/zackjordan/code/surfCastAI/GEM_ROADMAP.md` - Phase 3 implementation plan
- `/Users/zackjordan/code/surfCastAI/src/forecast_engine/specialists/senior_forecaster.py` - SeniorForecaster implementation
- `/Users/zackjordan/code/surfCastAI/src/forecast_engine/specialists/schemas.py` - Pydantic schemas
