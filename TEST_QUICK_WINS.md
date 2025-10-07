# Test Coverage Quick Wins

## Objective
Maximize coverage improvement with minimum effort by targeting high-impact, easy-to-test modules.

## Impact Analysis: Where to Focus

### Coverage Impact Calculator
```
Module Impact Score = (Untested Lines × Criticality) / Test Difficulty

High Impact Modules:
1. forecast_engine.py:     474 lines × HIGH / MEDIUM = 🔥🔥🔥🔥🔥
2. forecast_formatter.py:  265 lines × HIGH / EASY   = 🔥🔥🔥🔥
3. data_fusion_system.py:  170 lines × HIGH / MEDIUM = 🔥🔥🔥
4. prompt_templates.py:    111 lines × MED  / EASY   = 🔥🔥
5. data_processor.py:       74 lines × HIGH / EASY   = 🔥🔥
```

## Quick Win Strategy: 3 High-Impact Tests

### Quick Win #1: Forecast Formatter Tests (Easy, High Impact)
**File:** `tests/unit/forecast_engine/test_forecast_formatter.py`
**Effort:** 2 hours
**Coverage Gain:** ~7% → 70% (+250 lines)
**Difficulty:** EASY (string manipulation, no API calls)

```python
import unittest
from unittest.mock import Mock, patch
from src.forecast_engine.forecast_formatter import ForecastFormatter
from datetime import datetime

class TestForecastFormatter(unittest.TestCase):

    def setUp(self):
        self.formatter = ForecastFormatter()
        self.sample_forecast = {
            'timestamp': datetime.now(),
            'text': 'North Shore: 8-12 ft waves from NW swell',
            'confidence': 0.85,
            'confidence_factors': {
                'model_consensus': 0.9,
                'data_completeness': 0.8
            },
            'shore_forecasts': {
                'north': {'summary': '8-12 ft', 'rating': 'excellent'},
                'south': {'summary': '2-4 ft', 'rating': 'fair'}
            },
            'swell_events': [
                {'direction': 320, 'height': 10, 'period': 14}
            ]
        }

    def test_format_markdown_basic(self):
        """Test markdown generation with complete data"""
        result = self.formatter.format_markdown(self.sample_forecast)

        # Check structure
        self.assertIn('# Oahu Surf Forecast', result)
        self.assertIn('North Shore', result)
        self.assertIn('8-12 ft', result)
        self.assertIn('Confidence:', result)

    def test_format_markdown_missing_data(self):
        """Test markdown handles missing data gracefully"""
        incomplete = {'text': 'Basic forecast', 'confidence': 0.5}
        result = self.formatter.format_markdown(incomplete)

        self.assertIn('Basic forecast', result)
        self.assertIsNotNone(result)

    def test_format_html_valid_structure(self):
        """Test HTML output is valid and contains CSS"""
        result = self.formatter.format_html(self.sample_forecast)

        # Check HTML structure
        self.assertIn('<!DOCTYPE html>', result)
        self.assertIn('<html', result)
        self.assertIn('</html>', result)
        self.assertIn('<style>', result)

        # Check content
        self.assertIn('North Shore', result)
        self.assertIn('8-12 ft', result)

    def test_format_html_responsive_css(self):
        """Test HTML includes responsive mobile CSS"""
        result = self.formatter.format_html(self.sample_forecast)

        self.assertIn('@media', result)
        self.assertIn('viewport', result.lower())

    def test_format_confidence_section(self):
        """Test confidence section formatting"""
        result = self.formatter._format_confidence_section(self.sample_forecast)

        self.assertIn('85%', result)
        self.assertIn('model_consensus', result.lower())

    def test_format_shore_breakdown(self):
        """Test shore-specific formatting"""
        result = self.formatter._format_shore_breakdown(
            self.sample_forecast['shore_forecasts']
        )

        self.assertIn('north', result.lower())
        self.assertIn('south', result.lower())
        self.assertIn('8-12 ft', result)

    def test_unicode_handling(self):
        """Test special character handling"""
        forecast = {
            'text': 'Waves: 8-12\' with 15° swell direction',
            'confidence': 0.8
        }
        result = self.formatter.format_markdown(forecast)

        # Should not raise encoding errors
        self.assertIn('8-12', result)

    def test_long_forecast_text(self):
        """Test handling of very long forecast text"""
        long_text = 'Wave ' * 1000  # 5000 chars
        forecast = {'text': long_text, 'confidence': 0.8}

        result = self.formatter.format_html(forecast)
        self.assertIn('Wave', result)

    @patch('src.forecast_engine.visualization.generate_swell_chart')
    def test_embed_visualizations(self, mock_chart):
        """Test chart embedding in HTML"""
        mock_chart.return_value = '/path/to/chart.png'

        result = self.formatter.format_html(
            self.sample_forecast,
            embed_charts=True
        )

        self.assertIn('img', result)
```

**Why This Wins:**
- No API mocking required
- Simple string validation
- High line count impact
- Tests output quality directly

---

### Quick Win #2: Prompt Templates Tests (Easy, Medium Impact)
**File:** `tests/unit/forecast_engine/test_prompt_templates.py`
**Effort:** 1.5 hours
**Coverage Gain:** ~13% → 80% (+110 lines)
**Difficulty:** EASY (template rendering, no I/O)

```python
import unittest
from src.forecast_engine.prompt_templates import PromptTemplates
from datetime import datetime

class TestPromptTemplates(unittest.TestCase):

    def setUp(self):
        self.templates = PromptTemplates()
        self.sample_data = {
            'buoy_data': [{'station': '51001', 'wave_height': 8.5}],
            'model_data': [{'model': 'WW3', 'forecast_height': 9.0}],
            'weather_data': {'wind_speed': 15, 'direction': 'NE'},
            'season': 'winter',
            'shore': 'north'
        }

    def test_get_initial_prompt_renders(self):
        """Test initial prompt template renders without errors"""
        prompt = self.templates.get_initial_prompt(self.sample_data)

        self.assertIsInstance(prompt, str)
        self.assertGreater(len(prompt), 100)

    def test_get_initial_prompt_includes_data(self):
        """Test prompt includes provided data"""
        prompt = self.templates.get_initial_prompt(self.sample_data)

        self.assertIn('51001', prompt)
        self.assertIn('8.5', prompt)
        self.assertIn('WW3', prompt)

    def test_get_initial_prompt_seasonal_context(self):
        """Test seasonal context in prompts"""
        winter_prompt = self.templates.get_initial_prompt(
            {**self.sample_data, 'season': 'winter'}
        )
        summer_prompt = self.templates.get_initial_prompt(
            {**self.sample_data, 'season': 'summer'}
        )

        # Winter should mention north shore focus
        self.assertIn('north', winter_prompt.lower())

        # Summer should mention south shore focus
        self.assertIn('south', summer_prompt.lower())

    def test_get_refinement_prompt(self):
        """Test refinement prompt generation"""
        original = "North Shore: 8-12 ft"
        feedback = "Add more detail about swell periods"

        prompt = self.templates.get_refinement_prompt(original, feedback)

        self.assertIn(original, prompt)
        self.assertIn(feedback, prompt)

    def test_get_shore_specific_prompt_north(self):
        """Test north shore specific prompt"""
        prompt = self.templates.get_shore_specific_prompt(
            'north', self.sample_data
        )

        self.assertIn('north', prompt.lower())
        self.assertIn('pipeline', prompt.lower() or
                      'sunset' in prompt.lower())

    def test_get_shore_specific_prompt_south(self):
        """Test south shore specific prompt"""
        prompt = self.templates.get_shore_specific_prompt(
            'south', self.sample_data
        )

        self.assertIn('south', prompt.lower())

    def test_pat_caldwell_style_examples(self):
        """Test prompts include Pat Caldwell style examples"""
        prompt = self.templates.get_initial_prompt(self.sample_data)

        # Should include Hawaiian surfing terminology
        has_style_indicators = any(term in prompt.lower() for term in [
            'faces', 'sets', 'periods', 'swell', 'direction'
        ])
        self.assertTrue(has_style_indicators)

    def test_template_with_missing_data(self):
        """Test template handles missing data fields"""
        minimal_data = {'season': 'winter'}

        # Should not raise exception
        prompt = self.templates.get_initial_prompt(minimal_data)
        self.assertIsInstance(prompt, str)

    def test_template_special_characters(self):
        """Test template escaping of special characters"""
        data_with_special = {
            **self.sample_data,
            'notes': 'Waves > 10\' with "excellent" conditions'
        }

        prompt = self.templates.get_initial_prompt(data_with_special)
        self.assertIn('10', prompt)
```

**Why This Wins:**
- Pure string operations
- No external dependencies
- Fast execution
- Good line coverage per test

---

### Quick Win #3: Data Processor Base Tests (Easy, High Impact)
**File:** `tests/unit/processing/test_data_processor_base.py`
**Effort:** 1.5 hours
**Coverage Gain:** ~28% → 80% (+50 lines)
**Difficulty:** EASY (validation logic, no I/O)

```python
import unittest
from src.processing.data_processor import DataProcessor

class MockProcessor(DataProcessor):
    """Mock processor for testing base class"""

    def process(self, data):
        return data

    def get_required_fields(self):
        return ['field1', 'field2']

class TestDataProcessor(unittest.TestCase):

    def setUp(self):
        self.processor = MockProcessor()

    def test_validate_data_with_valid_input(self):
        """Test validation passes with valid data"""
        data = {'field1': 'value1', 'field2': 'value2'}

        is_valid, errors = self.processor.validate_data(data)

        self.assertTrue(is_valid)
        self.assertEqual(len(errors), 0)

    def test_validate_data_missing_required_field(self):
        """Test validation fails with missing required field"""
        data = {'field1': 'value1'}  # Missing field2

        is_valid, errors = self.processor.validate_data(data)

        self.assertFalse(is_valid)
        self.assertIn('field2', str(errors))

    def test_validate_data_all_fields_missing(self):
        """Test validation fails with empty data"""
        data = {}

        is_valid, errors = self.processor.validate_data(data)

        self.assertFalse(is_valid)
        self.assertGreater(len(errors), 0)

    def test_check_required_fields(self):
        """Test required field checking"""
        data = {'field1': 'value1'}

        missing = self.processor._check_required_fields(data)

        self.assertIn('field2', missing)
        self.assertNotIn('field1', missing)

    def test_check_data_quality_thresholds(self):
        """Test data quality threshold checking"""
        # High quality data
        good_data = {
            'field1': 'value1',
            'field2': 'value2',
            'quality_score': 0.95
        }

        is_good_quality = self.processor._check_data_quality(good_data)
        self.assertTrue(is_good_quality)

        # Low quality data
        bad_data = {
            'field1': 'value1',
            'field2': 'value2',
            'quality_score': 0.3
        }

        is_good_quality = self.processor._check_data_quality(bad_data)
        self.assertFalse(is_good_quality)

    def test_error_message_generation(self):
        """Test error message formatting"""
        errors = ['Missing field1', 'Invalid field2']

        message = self.processor._format_error_message(errors)

        self.assertIn('field1', message)
        self.assertIn('field2', message)

    def test_validate_with_none_input(self):
        """Test validation handles None input"""
        is_valid, errors = self.processor.validate_data(None)

        self.assertFalse(is_valid)
        self.assertGreater(len(errors), 0)

    def test_validate_with_wrong_type(self):
        """Test validation handles wrong data type"""
        is_valid, errors = self.processor.validate_data("not a dict")

        self.assertFalse(is_valid)
        self.assertIn('type', str(errors).lower())
```

**Why This Wins:**
- Foundation for all processors
- Simple validation logic
- No mocking needed
- High conceptual importance

---

## Combined Impact: 3 Test Files = 5 Hours

| Test File | Effort | Coverage Gain | Lines Added |
|-----------|--------|---------------|-------------|
| test_forecast_formatter.py | 2h | +63% (7%→70%) | ~250 lines |
| test_prompt_templates.py | 1.5h | +67% (13%→80%) | ~110 lines |
| test_data_processor_base.py | 1.5h | +52% (28%→80%) | ~50 lines |
| **TOTAL** | **5h** | **+410 lines covered** | **+60 tests** |

**Overall Coverage Impact:** 47% → 54% (+7 percentage points)

---

## Medium-Effort, High-Impact Additions

### Option 4: Forecast Engine Core (Medium Difficulty)
**File:** `tests/unit/forecast_engine/test_forecast_engine_core.py`
**Effort:** 3-4 hours
**Coverage Gain:** 5% → 60% (+270 lines)
**Difficulty:** MEDIUM (requires API mocking)

**Key Tests:**
```python
@patch('openai.ChatCompletion.create')
def test_generate_forecast_success(self, mock_openai):
    """Test successful forecast generation"""
    mock_openai.return_value = Mock(
        choices=[Mock(message=Mock(content='Forecast text'))]
    )

    result = self.engine.generate_forecast(self.fused_data)

    self.assertIsNotNone(result)
    self.assertIn('text', result)

def test_build_initial_prompt_with_data(self):
    """Test prompt construction includes all data"""
    prompt = self.engine._build_initial_prompt(self.fused_data)

    self.assertIn('buoy', prompt)
    self.assertIn('model', prompt)
    self.assertGreater(len(prompt), 500)
```

---

## Lowest-Effort Wins (1 hour each)

### Fix Failing Tests (Immediate Impact)
**Effort:** 2-3 hours total
**Coverage Gain:** 0% (but fixes 25 failures)
**Impact:** 92% → 100% pass rate

**Priority Fixes:**
1. Config tests - update path assertions
2. Security tests - fix error message strings
3. HTTP client - fix mock setup
4. Processing tests - fix test data

---

## Recommended Execution Order

### Day 1: Quick Wins (5 hours)
1. test_forecast_formatter.py (2h)
2. test_prompt_templates.py (1.5h)
3. test_data_processor_base.py (1.5h)

**Result:** 47% → 54% coverage, +60 tests

### Day 2: Fix Failures + Medium Win (6 hours)
4. Fix 25 failing tests (2-3h)
5. test_forecast_engine_core.py (3-4h)

**Result:** 54% → 62% coverage, 100% pass rate

### Day 3: Processing Gaps (3 hours)
6. Enhance test_data_fusion_system.py (1.5h)
7. Enhance test_hawaii_context.py (1.5h)

**Result:** 62% → 67% coverage

---

## Total Investment vs Return

**Time Investment:** 14 hours over 3 days
**Coverage Improvement:** 47% → 67% (+20 percentage points)
**Test Additions:** ~100 new tests
**Pass Rate:** 92% → 100%
**Critical Modules Covered:** All forecast generation and core processing

**ROI:** Excellent - achieves comprehensive coverage of critical path with reasonable effort.

---

## Not Recommended: Long-Tail Efforts

**Agent Unit Tests** - 15-20 hours for 8% coverage gain
- Agents already have integration tests
- Low incremental value
- High maintenance burden

**CLI Integration Tests** - 5-10 hours for 3% coverage gain
- main.py is CLI orchestration
- Manual testing more practical
- Low failure risk

**Bundle Manager Tests** - 2-3 hours for 4% coverage gain
- Non-critical infrastructure
- Low usage in forecast path
- Can defer

---

## Conclusion

**Recommended Quick Win Strategy:**
1. Add 3 easy test files (5 hours)
2. Fix 25 failing tests (2-3 hours)
3. Add forecast engine tests (3-4 hours)
4. Fill processing gaps (3 hours)

**Total:** 13-15 hours
**Result:** 67% coverage with 100% pass rate
**Value:** Comprehensive testing of all critical forecast generation logic

This beats chasing 80% through low-value agent tests by 10-15 hours while providing better quality assurance for the core forecast generation pipeline.
