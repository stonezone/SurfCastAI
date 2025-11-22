# Prompt Testing Quick Start

**TL;DR**: Framework for testing AI prompt generation to prevent regressions.

## Quick Start

### Run Tests
```bash
pytest tests/test_prompts.py -v
```

### Create a Test Case
```bash
# Generate template
python tests/test_prompts.py generate my_test_case

# Edit the files
cd tests/prompt_tests/senior_forecaster/my_test_case
vim input.json     # Add test data
vim prompt.txt     # Add expected prompt

# Run test
pytest tests/test_prompts.py -k my_test_case -v
```

## What Gets Tested

The framework validates that `SeniorForecaster._generate_caldwell_narrative()` generates the correct prompts for OpenAI API.

- ✅ System prompt (Pat Caldwell style instructions)
- ✅ User prompt (formatted data from specialists)
- ✅ Pydantic model integration
- ✅ No actual API calls (fully mocked)

## Test Case Structure

```
tests/prompt_tests/senior_forecaster/
└── my_test_case/
    ├── input.json    # Input data (buoy_analysis, pressure_analysis, etc.)
    └── prompt.txt    # Expected combined prompt (system + user)
```

## Common Commands

```bash
# Run all tests
pytest tests/test_prompts.py

# Run with verbose output
pytest tests/test_prompts.py -v

# Run specific test
pytest tests/test_prompts.py -k "test_case_01"

# Generate new test case
python tests/test_prompts.py generate test_case_name
```

## When Tests Fail

You'll see a diff showing what changed:

```diff
--- test_case_01/prompt.txt (expected)
+++ test_case_01/generated (actual)
@@ -10,7 +10,7 @@
-- Specific measurements (cite buoy numbers, pressure values)
++ Specific measurements (cite buoy readings, pressure values)
```

If the change is intentional, update the golden file:
```bash
# Test output provides the exact command
cat > tests/prompt_tests/senior_forecaster/test_case_01/prompt.txt <<'EOF'
[paste new prompt here]
EOF
```

## Test Case Format

### input.json
```json
{
  "buoy_analysis": {
    "confidence": 0.85,
    "data": { "trends": [...], ... },
    "narrative": "Buoy report...",
    "metadata": {}
  },
  "pressure_analysis": {
    "confidence": 0.90,
    "data": { "systems": [...], ... },
    "narrative": "Pressure report...",
    "metadata": {}
  },
  "swell_events": [...],
  "shore_data": {...},
  "seasonal_context": {"season": "winter"},
  "metadata": {
    "forecast_date": "2025-10-09",
    "valid_period": "48hr"
  }
}
```

### prompt.txt
```
You are Pat Caldwell, Hawaii's legendary surf forecaster...

[System prompt continues...]

[User prompt with data follows...]
```

## Integration with CI/CD

Add to GitHub Actions:
```yaml
- name: Prompt validation tests
  run: pytest tests/test_prompts.py -v --tb=short
```

## Documentation

- **Full Guide**: `tests/PROMPT_TESTING_GUIDE.md`
- **Directory README**: `tests/prompt_tests/senior_forecaster/README.md`
- **Test Code**: `tests/test_prompts.py` (well-commented)

## Troubleshooting

| Issue | Solution |
|-------|----------|
| No tests run | Create test case directories |
| Pydantic errors | Validate JSON against schemas |
| Mock not working | Check async/await syntax |
| Can't generate template | Run as: `python tests/test_prompts.py generate <name>` |

## Example Workflow

```bash
# 1. Generate template
python tests/test_prompts.py generate test_winter_scenario

# 2. Edit input with real data
cd tests/prompt_tests/senior_forecaster/test_winter_scenario
vim input.json

# 3. Run forecaster manually to generate prompt
# (or use existing forecast output)

# 4. Copy prompt to golden file
cat > prompt.txt <<'EOF'
[paste prompt here]
EOF

# 5. Run test
cd /Users/zackjordan/code/surfCastAI
pytest tests/test_prompts.py -k test_winter_scenario -v

# 6. Commit test case
git add tests/prompt_tests/senior_forecaster/test_winter_scenario
git commit -m "Add prompt test for winter scenario"
```

## Key Points

- 🎯 **Purpose**: Prevent prompt regressions
- 🚀 **Fast**: No API calls, fully mocked
- 📊 **Clear**: Unified diffs show exact changes
- 🔧 **Easy**: Template generator included
- 📚 **Documented**: Comprehensive guides

---

**See Also**:
- `tests/PROMPT_TESTING_GUIDE.md` - Full implementation details
- `tests/prompt_tests/senior_forecaster/README.md` - Test case format
