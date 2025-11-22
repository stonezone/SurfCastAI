# Prompt Testing Quickstart

**5-minute guide to SurfCastAI prompt testing**

---

## Quick Commands

```bash
# Run all prompt tests
pytest tests/test_prompts.py -v

# Create new test case
mkdir tests/prompt_tests/senior_forecaster/case_XX_name
# Add input.json (see template below)

# Generate golden prompt
python scripts/generate_golden_prompts.py

# Update golden prompts (after intentional changes)
python scripts/generate_golden_prompts.py --update
```

---

## Test Case Template

**File:** `tests/prompt_tests/senior_forecaster/case_XX_name/input.json`

```json
{
  "metadata": {
    "forecast_date": "2025-10-15",
    "valid_period": "48hr"
  },
  "seasonal_context": {
    "season": "winter"
  },
  "buoy_analysis": {
    "confidence": 0.85,
    "narrative": "Your specialist narrative here...",
    "data": {}
  },
  "pressure_analysis": {
    "confidence": 0.80,
    "narrative": "Your specialist narrative here...",
    "data": {}
  },
  "contradictions": [],
  "key_findings": ["Finding 1", "Finding 2"],
  "shore_forecasts": {},
  "swell_breakdown": []
}
```

---

## What Tests Check

✅ **Prompt Stability:** Prompts don't change unexpectedly
✅ **Structure Validity:** Required sections present
✅ **Format Consistency:** Prompts follow template
✅ **Version Control:** Changes tracked in git

---

## When Tests Fail

### "Generated prompt doesn't match golden file"

**Meaning:** Prompt logic changed

**Fix:**
```bash
# If change was intentional:
python scripts/generate_golden_prompts.py --update
git add tests/prompt_tests/
git commit -m "Update prompts: reason for change"

# If change was unintentional:
# Fix the bug in specialist code
```

---

## Best Practices

1. **Always review diffs** before updating golden files
2. **Commit prompt.txt files** to version control
3. **Document changes** in commit messages
4. **Test locally** before pushing

---

## Example Test Cases

- **case_01_high_confidence:** Clean NW swell, strong agreement
- **case_02_low_confidence:** Uncertain data, contradictions
- **case_03_large_swells:** XXL conditions, safety warnings
- **case_04_flat_conditions:** High confidence in flatness

---

## Full Documentation

See `docs/PROMPT_TESTING_GUIDE.md` for comprehensive documentation.

---

**Quick Reference:** tests/test_prompts.py | scripts/generate_golden_prompts.py
