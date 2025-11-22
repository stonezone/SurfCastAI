# Contributing to SurfCastAI

Thank you for your interest in contributing to SurfCastAI! This document provides guidelines and workflows for contributing to the project.

## Table of Contents

- [Getting Started](#getting-started)
- [Development Workflow](#development-workflow)
- [Testing](#testing)
- [Prompt Testing Framework](#prompt-testing-framework)
- [Code Style](#code-style)
- [Pull Request Process](#pull-request-process)

---

## Getting Started

### Prerequisites

- Python 3.11+
- pip and virtualenv
- Git
- OpenAI API key (for AI-powered features)

### Initial Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/yourusername/surfCastAI.git
   cd surfCastAI
   ```

2. **Create virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment:**
   ```bash
   cp config/config.example.yaml config/config.yaml
   # Edit config.yaml with your settings
   ```

5. **Set up API keys:**
   ```bash
   cp .env.example .env
   # Add your OPENAI_API_KEY to .env
   ```

---

## Development Workflow

### Branch Strategy

- `master` - Production-ready code
- `develop` - Integration branch for features
- `feature/*` - New features
- `fix/*` - Bug fixes
- `docs/*` - Documentation updates

### Making Changes

1. **Create a feature branch:**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes** following code style guidelines

3. **Write tests** for new functionality

4. **Run tests locally:**
   ```bash
   pytest tests/ -v
   ```

5. **Commit with descriptive messages:**
   ```bash
   git commit -m "feat: Add new buoy data validation

   - Implement bounds checking for wave height
   - Add period validation (4-30s range)
   - Include comprehensive unit tests"
   ```

---

## Testing

### Running Tests

```bash
# Run all tests
pytest tests/

# Run with coverage
pytest tests/ --cov=src --cov-report=html

# Run specific test file
pytest tests/test_prompts.py -v

# Run tests matching pattern
pytest tests/ -k "buoy" -v
```

### Writing Tests

- Place unit tests in `tests/unit/`
- Place integration tests in `tests/integration/`
- Use descriptive test names: `test_buoy_data_validates_wave_height_bounds()`
- Follow AAA pattern: Arrange, Act, Assert

---

## Prompt Testing Framework

**Important:** The prompt testing framework prevents AI prompt regressions by validating that prompt generation logic produces consistent, expected outputs.

### Overview

SurfCastAI uses a **golden file testing approach** for AI prompts:
- **Test Cases** are in `tests/prompt_tests/senior_forecaster/`
- Each test case contains:
  - `input.json` - Input data for the prompt
  - `prompt.txt` - Golden reference prompt (expected output)
- Tests auto-discover and validate all test cases

### Running Prompt Tests

```bash
# Run all prompt tests
pytest tests/test_prompts.py -v

# Run specific test case
pytest tests/test_prompts.py -k "test_case_01" -v

# Show detailed diffs on failure
pytest tests/test_prompts.py -vv
```

### Creating New Prompt Test Cases

#### Step 1: Generate Template

```bash
python tests/test_prompts.py generate test_case_XX_description
```

This creates:
```
tests/prompt_tests/senior_forecaster/test_case_XX_description/
├── input.json (template)
└── prompt.txt (template)
```

#### Step 2: Edit input.json

Populate `input.json` with realistic test data:

```json
{
  "buoy_analysis": {
    "confidence": 0.85,
    "narrative": "Strong NW swell building at buoys...",
    "data": {
      "trends": [...],
      "anomalies": [...],
      "key_observations": [...]
    },
    "metadata": {
      "buoys_analyzed": ["51001", "51201", "51202"],
      "analysis_timestamp": "2025-10-15T08:00:00Z"
    }
  },
  "pressure_analysis": {
    "confidence": 0.90,
    "narrative": "Deep Aleutian low generating NW swell...",
    "data": {
      "systems": [...],
      "swells_generated": [...],
      "fronts": []
    },
    "metadata": {...}
  },
  "shore_forecasts": {
    "north": {...},
    "south": {...},
    "east": {...},
    "west": {...}
  },
  "swell_breakdown": [
    {
      "direction": "NW (320°)",
      "period": "14-16s",
      "height": "8-12ft",
      "source": "Aleutian low",
      "arrival": "2025-10-16 06:00",
      "confidence": 0.85
    }
  ],
  "seasonal_context": {
    "season": "winter",
    "typical_pattern": "North Pacific storms",
    "current_phase": "early season"
  },
  "metadata": {
    "forecast_date": "2025-10-15",
    "valid_period": "48-hour",
    "region": "Oahu"
  }
}
```

#### Step 3: Generate Golden Prompt

```bash
python scripts/generate_golden_prompts.py
```

This generates `prompt.txt` files for all test cases based on current prompt logic.

#### Step 4: Review and Commit

1. **Review generated prompt:**
   ```bash
   cat tests/prompt_tests/senior_forecaster/test_case_XX_description/prompt.txt
   ```

2. **Verify it looks correct** (proper formatting, data included, etc.)

3. **Run test to confirm:**
   ```bash
   pytest tests/test_prompts.py::test_senior_forecaster_prompt_generation[test_case_XX_description] -v
   ```

4. **Commit both files:**
   ```bash
   git add tests/prompt_tests/senior_forecaster/test_case_XX_description/
   git commit -m "test: Add prompt test case for [description]"
   ```

### Updating Golden Files

When you **intentionally** change prompt generation logic:

1. **Update the code** (e.g., modify `_generate_caldwell_narrative()`)

2. **Run tests** to see which prompts changed:
   ```bash
   pytest tests/test_prompts.py -v
   ```

3. **Review the diffs carefully:**
   - Test output shows exact differences
   - Verify changes are intentional and correct

4. **Regenerate golden files:**
   ```bash
   python scripts/generate_golden_prompts.py
   ```

5. **Verify updated prompts:**
   ```bash
   pytest tests/test_prompts.py -v
   ```

6. **Commit with clear explanation:**
   ```bash
   git add tests/prompt_tests/
   git commit -m "chore: Update golden prompts for improved swell timing clarity

   Refined the swell arrival timing language to be more precise.
   All tests pass with updated golden files."
   ```

### Best Practices

#### Test Case Scenarios to Cover

- **High Confidence** - All sources agree, strong signals
- **Low Confidence** - Missing data, source disagreement
- **No Swells** - Flat conditions, minimal activity
- **Large Swells** - Major winter swell events
- **Multiple Swells** - Overlapping swell trains
- **Contradictions** - Buoy vs model disagreement
- **Missing Data** - Partial buoy coverage
- **Seasonal Patterns** - Winter NW, summer south swells

#### Data Quality

- Use **realistic buoy numbers**: 51001, 51201, 51202, 51207, etc.
- Use **realistic wave parameters** for Hawaii:
  - Wave heights: 0.5m - 6.0m (1-20ft faces)
  - Periods: 7s - 20s
  - Directions: NW (310-330°), S (170-200°), E (75-90°)
- Ensure **data consistency** across buoy_analysis and pressure_analysis
- Include **cross-validation** data (agreement scores, contradictions)

#### When Tests Fail

If a prompt test fails unexpectedly:

1. **Check if prompt change was intentional:**
   - Did you modify prompt generation code?
   - Did you update Pydantic schemas?
   - Did you change internal data processing?

2. **Review the diff:**
   - What exactly changed?
   - Is the new prompt better or worse?
   - Does it maintain Pat Caldwell's style?

3. **If unintentional:**
   - Investigate what caused the change
   - Fix the regression
   - Ensure tests pass

4. **If intentional:**
   - Follow "Updating Golden Files" workflow above
   - Document why the change improves prompts
   - Get code review approval

### Why Prompt Testing Matters

1. **Prevents Silent Regressions** - Code changes can subtly alter AI prompts
2. **Documents Expected Behavior** - Golden files serve as prompt specifications
3. **Enables Safe Refactoring** - Confidence when improving code structure
4. **Quality Assurance** - Ensures prompts remain high-quality and consistent
5. **Industry Best Practice** - Standard for production LLM systems

---

## Code Style

### Python Style Guide

- Follow **PEP 8** style guidelines
- Use **type hints** for function signatures
- Write **docstrings** for all public functions and classes
- Keep functions **focused and small** (Single Responsibility Principle)

### Naming Conventions

- `snake_case` for functions, variables, modules
- `PascalCase` for classes
- `UPPER_CASE` for constants
- Descriptive names over abbreviations

### Example

```python
from typing import List, Optional
from datetime import datetime

def calculate_confidence_score(
    buoy_data: List[BuoyObservation],
    model_data: List[ModelPrediction],
    threshold: float = 0.7
) -> float:
    """
    Calculate confidence score based on data quality and agreement.

    Args:
        buoy_data: List of buoy observations
        model_data: List of model predictions
        threshold: Minimum confidence threshold (default: 0.7)

    Returns:
        Confidence score between 0.0 and 1.0

    Raises:
        ValueError: If input data is empty
    """
    if not buoy_data or not model_data:
        raise ValueError("Input data cannot be empty")

    # Calculate agreement between sources
    agreement_score = _calculate_agreement(buoy_data, model_data)

    # Apply quality weighting
    quality_factor = _assess_data_quality(buoy_data)

    return min(1.0, agreement_score * quality_factor)
```

---

## Pull Request Process

### Before Submitting

- [ ] All tests pass locally
- [ ] New code has unit tests
- [ ] Prompt tests updated if prompts changed
- [ ] Code follows style guidelines
- [ ] Documentation updated if needed
- [ ] Commit messages are clear and descriptive

### PR Checklist

1. **Create PR** with descriptive title and detailed description
2. **Link related issues** using "Fixes #123" or "Relates to #456"
3. **Request review** from maintainers
4. **Address feedback** promptly and professionally
5. **Keep PR focused** - one feature/fix per PR
6. **Update PR** if base branch changes

### PR Template

```markdown
## Description
[Clear description of what this PR does]

## Motivation
[Why is this change necessary?]

## Changes
- [List of specific changes made]
- [Include file paths if helpful]

## Testing
- [ ] All existing tests pass
- [ ] Added new tests for new functionality
- [ ] Manually tested [describe scenarios]

## Checklist
- [ ] Code follows project style guidelines
- [ ] Documentation updated
- [ ] Prompt tests updated (if applicable)
- [ ] No breaking changes (or documented if necessary)

## Screenshots/Examples
[If applicable, add screenshots or examples of new functionality]

## Related Issues
Fixes #123
Relates to #456
```

---

## Questions?

- **General questions:** Open a GitHub Discussion
- **Bug reports:** Open a GitHub Issue with reproduction steps
- **Security issues:** Email security@surfcastai.com (do not open public issue)

---

**Thank you for contributing to SurfCastAI!** 🌊🏄

*Last Updated: 2025-10-10*
