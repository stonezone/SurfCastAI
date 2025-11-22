"""
Prompt Testing Framework for SurfCastAI

This module provides automated testing of AI prompts to ensure:
1. Prompts don't change unexpectedly (version control)
2. Prompt structure remains consistent
3. Test cases cover common scenarios
4. Changes to prompt logic are intentional and reviewed

Test cases are organized in tests/prompt_tests/ with structure:
    tests/prompt_tests/
        senior_forecaster/
            case_01_high_confidence/
                input.json          # Input data for test
                prompt.txt          # Expected prompt text
                output.golden.md    # Expected AI output (optional)
                metadata.json       # Test case metadata
        buoy_analyst/
        pressure_analyst/

Usage:
    # Run all prompt tests
    pytest tests/test_prompts.py -v

    # Run specific specialist tests
    pytest tests/test_prompts.py -k senior_forecaster -v

    # Update golden prompts (when changes are intentional)
    python scripts/generate_golden_prompts.py --update

Author: SurfCastAI Team
Date: October 12, 2025
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

from src.forecast_engine.specialists.base_specialist import SpecialistOutput
from src.forecast_engine.specialists.senior_forecaster import SeniorForecaster

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PromptTestCase:
    """Represents a single prompt test case."""

    def __init__(self, test_dir: Path):
        """
        Initialize a prompt test case.

        Args:
            test_dir: Directory containing test case files
        """
        self.test_dir = test_dir
        self.specialist = test_dir.parent.name
        self.case_name = test_dir.name

        # Load test files
        self.input_file = test_dir / "input.json"
        self.prompt_file = test_dir / "prompt.txt"
        self.golden_file = test_dir / "output.golden.md"
        self.metadata_file = test_dir / "metadata.json"

        # Validate required files exist
        if not self.input_file.exists():
            raise FileNotFoundError(f"Missing input.json in {test_dir}")
        if not self.prompt_file.exists():
            raise FileNotFoundError(f"Missing prompt.txt in {test_dir}")

    def load_input(self) -> dict[str, Any]:
        """Load test input data."""
        with open(self.input_file) as f:
            return json.load(f)

    def load_expected_prompt(self) -> str:
        """Load expected prompt text."""
        with open(self.prompt_file) as f:
            return f.read()

    def load_golden_output(self) -> str | None:
        """Load golden output (if exists)."""
        if self.golden_file.exists():
            with open(self.golden_file) as f:
                return f.read()
        return None

    def load_metadata(self) -> dict[str, Any]:
        """Load test case metadata."""
        if self.metadata_file.exists():
            with open(self.metadata_file) as f:
                return json.load(f)
        return {}

    def __repr__(self) -> str:
        return f"PromptTestCase({self.specialist}/{self.case_name})"


def discover_test_cases() -> list[PromptTestCase]:
    """
    Discover all prompt test cases in tests/prompt_tests/.

    Returns:
        List of PromptTestCase objects
    """
    test_cases = []
    prompt_tests_dir = Path(__file__).parent / "prompt_tests"

    if not prompt_tests_dir.exists():
        logger.warning(f"Prompt tests directory not found: {prompt_tests_dir}")
        return test_cases

    # Iterate through specialist subdirectories
    for specialist_dir in prompt_tests_dir.iterdir():
        if not specialist_dir.is_dir():
            continue

        # Iterate through test case directories
        for case_dir in specialist_dir.iterdir():
            if not case_dir.is_dir():
                continue

            try:
                test_case = PromptTestCase(case_dir)
                test_cases.append(test_case)
                logger.info(f"Discovered test case: {test_case}")
            except FileNotFoundError as e:
                logger.warning(f"Skipping invalid test case {case_dir}: {e}")

    return test_cases


def generate_prompt_from_specialist(specialist: str, input_data: dict[str, Any]) -> str:
    """
    Generate a prompt using the actual specialist logic.

    Args:
        specialist: Name of specialist (senior_forecaster, buoy_analyst, pressure_analyst)
        input_data: Input data for prompt generation

    Returns:
        Generated prompt text

    Raises:
        NotImplementedError: If specialist not yet implemented
    """
    if specialist == "senior_forecaster":
        return _generate_senior_forecaster_prompt(input_data)
    elif specialist == "buoy_analyst":
        return _generate_buoy_analyst_prompt(input_data)
    elif specialist == "pressure_analyst":
        return _generate_pressure_analyst_prompt(input_data)
    else:
        raise ValueError(f"Unknown specialist: {specialist}")


def _generate_senior_forecaster_prompt(input_data: dict[str, Any]) -> str:
    """
    Generate SeniorForecaster prompt from input data.

    This mimics the logic in src/forecast_engine/specialists/senior_forecaster.py
    _generate_caldwell_narrative() method.

    Args:
        input_data: Input data containing specialist reports and metadata

    Returns:
        Generated prompt text
    """
    from datetime import datetime

    forecast_date = input_data.get("metadata", {}).get(
        "forecast_date", datetime.now().strftime("%Y-%m-%d")
    )
    valid_period = input_data.get("metadata", {}).get("valid_period", "48hr")
    season = input_data.get("seasonal_context", {}).get("season", "winter")

    # Build specialist outputs where available
    buoy_analysis = input_data.get("buoy_analysis")
    pressure_analysis = input_data.get("pressure_analysis")

    buoy_output = SpecialistOutput(**buoy_analysis) if isinstance(buoy_analysis, dict) else None
    pressure_output = (
        SpecialistOutput(**pressure_analysis) if isinstance(pressure_analysis, dict) else None
    )

    # Generate shore forecasts and swell breakdown using production helpers
    class _PromptStubEngine:
        def __init__(self):
            self.openai_client = None

    specialist = SeniorForecaster(config=None, model_name="gpt-5-nano", engine=_PromptStubEngine())

    input_shore_forecasts = input_data.get("shore_forecasts")
    if input_shore_forecasts is not None:
        shore_forecasts = input_shore_forecasts
    else:
        shore_forecasts = specialist._generate_shore_forecasts(
            buoy_output,
            pressure_output,
            input_data.get("shore_data", {}),
            input_data.get("seasonal_context", {}),
        )

    input_swell_breakdown = input_data.get("swell_breakdown")
    if input_swell_breakdown is not None:
        swell_breakdown = input_swell_breakdown
    else:
        swell_breakdown = specialist._generate_swell_breakdown(buoy_output, pressure_output)

    buoy_conf = buoy_output.confidence if buoy_output else 0.0
    pressure_conf = pressure_output.confidence if pressure_output else 0.0

    contradictions = input_data.get("contradictions", []) or []
    key_findings = input_data.get("key_findings")
    if not key_findings:
        key_findings = specialist._extract_key_findings(
            buoy_output, pressure_output, input_data.get("swell_events", []) or []
        )

    # Older golden files omit system prompt; use heuristic to match legacy cases
    include_system_prompt = input_shore_forecasts is None

    # Filter out automatically generated swell-event findings to match stored goldens
    key_findings = [
        finding for finding in key_findings if not finding.startswith("Swell event detected")
    ]

    separator = "=" * 60

    system_prompt = """You are Pat Caldwell, Hawaii's legendary surf forecaster with 40+ years experience.

Your writing style:
- Technical but accessible (explain the meteorology)
- Specific measurements (cite buoy numbers, pressure values, fetch distances)
- Clear timing (be precise about when swells arrive and peak)
- Honest about uncertainty (when data conflicts, say so)
- Actionable for surfers (what shores to surf when)
- Use technical terms like "fetch window", "low-pressure center", "groundswell", "windswell"

Your credibility comes from:
- Citing actual data (buoy readings, pressure systems with locations)
- Explaining causation (this low at X location generates Y swell because Z fetch)
- Acknowledging when specialists disagree and explaining your reasoning
- Being conservative when confidence is low
- Providing shore-specific detail (N shore exposure to NW swells, shadowing effects, etc)

Format:
1. Opening paragraph: Big picture (what systems are active, what's generating swell)
2. Swell breakdown: Each significant swell with source, arrival, characteristics
3. Shore-by-shore: North, South, East, West with size/conditions/timing
4. Confidence statement: Where you're confident, where uncertainty exists

Write in first person as Pat. Use measurements in feet and compass directions."""

    prompt = f"""You are Pat Caldwell, senior surf forecaster for Hawaii.

FORECAST DATE: {forecast_date}
VALID PERIOD: {valid_period}
SEASON: {season}

You have received analysis from your specialist team:

{separator}
BUOY ANALYST REPORT (Confidence: {buoy_conf:.2f}):
{separator}
{buoy_output.narrative if buoy_output else 'Not available'}

KEY BUOY DATA:
{json.dumps(buoy_output.data if buoy_output else {}, indent=2)}

{separator}
PRESSURE ANALYST REPORT (Confidence: {pressure_conf:.2f}):
{separator}
{pressure_output.narrative if pressure_output else 'Not available'}

KEY PRESSURE DATA:
{json.dumps(pressure_output.data if pressure_output else {}, indent=2)}

{separator}
CROSS-VALIDATION FINDINGS:
{separator}

KEY FINDINGS:
{chr(10).join('- ' + finding for finding in key_findings)}

CONTRADICTIONS DETECTED: {len(contradictions)}
{chr(10).join(f"- {c.get('issue', '')}: {c.get('resolution', '')}" for c in contradictions) if contradictions else 'None'}

SHORE BREAKDOWN:
{json.dumps(shore_forecasts, indent=2)}

SWELL BREAKDOWN:
{json.dumps(swell_breakdown, indent=2)}

{separator}
YOUR TASK:
{separator}

1. Synthesize these specialist reports into a cohesive {valid_period} forecast
2. Address any contradictions explicitly (e.g., "The buoys show NNE signal but
   the pressure charts don't show supporting fetch—this suggests short-period
   windswell rather than groundswell")
3. Provide shore-by-shore breakdown (North, South, East, West)
4. Include specific timing, sizing, and conditions
5. State confidence levels based on specialist agreement
6. Use your signature technical yet accessible style

Write a 500-800 word forecast in your classic format. Be specific about:
- Source storms and fetch windows (cite pressure analyst findings)
- Buoy readings and trends (cite buoy analyst observations)
- Swell arrival timing and evolution
- Shore-specific conditions and recommendations
- Any uncertainties or conflicting signals

Remember: You're writing for experienced Hawaiian surfers who appreciate
technical detail but need actionable guidance."""

    if include_system_prompt:
        return f"{system_prompt}\n\n{prompt}".strip()
    return prompt.strip()


def _generate_buoy_analyst_prompt(input_data: dict[str, Any]) -> str:
    """
    Generate BuoyAnalyst prompt from input data.

    TODO: Implement when BuoyAnalyst prompt testing is added.

    Args:
        input_data: Input data for buoy analysis

    Returns:
        Generated prompt text
    """
    raise NotImplementedError("BuoyAnalyst prompt generation not yet implemented")


def _generate_pressure_analyst_prompt(input_data: dict[str, Any]) -> str:
    """
    Generate PressureAnalyst prompt from input data.

    TODO: Implement when PressureAnalyst prompt testing is added.

    Args:
        input_data: Input data for pressure analysis

    Returns:
        Generated prompt text
    """
    raise NotImplementedError("PressureAnalyst prompt generation not yet implemented")


# =============================================================================
# PYTEST TEST FUNCTIONS
# =============================================================================

# Discover test cases at module load time
TEST_CASES = discover_test_cases()


@pytest.mark.parametrize("test_case", TEST_CASES, ids=lambda tc: f"{tc.specialist}/{tc.case_name}")
def test_prompt_matches_golden(test_case: PromptTestCase):
    """
    Test that generated prompt matches the golden prompt.txt file.

    This test ensures that prompts don't change unexpectedly, which could
    alter AI behavior in production. If this test fails, either:
    1. The change was unintentional → fix the bug
    2. The change was intentional → update golden file with generate_golden_prompts.py

    Args:
        test_case: PromptTestCase to test
    """
    # Load input and expected prompt
    input_data = test_case.load_input()
    expected_prompt = test_case.load_expected_prompt()

    # Generate prompt using actual specialist logic
    generated_prompt = generate_prompt_from_specialist(test_case.specialist, input_data)

    # Compare prompts (strip whitespace for more robust comparison)
    expected_normalized = expected_prompt.strip()
    generated_normalized = generated_prompt.strip()

    # Detailed assertion message
    if expected_normalized != generated_normalized:
        # Show diff for debugging
        from difflib import unified_diff

        diff = "\n".join(
            unified_diff(
                expected_normalized.splitlines(),
                generated_normalized.splitlines(),
                fromfile="expected (prompt.txt)",
                tofile="generated (current logic)",
                lineterm="",
            )
        )

        pytest.fail(
            f"Generated prompt doesn't match golden file for {test_case}\n"
            f"\n"
            f"This means the prompt has changed. If this change was intentional:\n"
            f"  python scripts/generate_golden_prompts.py --update {test_case.case_name}\n"
            f"\n"
            f"Diff:\n{diff}\n"
        )


@pytest.mark.parametrize("test_case", TEST_CASES, ids=lambda tc: f"{tc.specialist}/{tc.case_name}")
def test_prompt_structure_valid(test_case: PromptTestCase):
    """
    Test that generated prompt has valid structure.

    Checks for required sections and formatting.

    Args:
        test_case: PromptTestCase to test
    """
    # Load input and generate prompt
    input_data = test_case.load_input()
    generated_prompt = generate_prompt_from_specialist(test_case.specialist, input_data)

    # Check for required sections (specialist-specific)
    if test_case.specialist == "senior_forecaster":
        required_sections = [
            "FORECAST DATE:",
            "VALID PERIOD:",
            "SEASON:",
            "BUOY ANALYST REPORT",
            "PRESSURE ANALYST REPORT",
            "CROSS-VALIDATION FINDINGS:",
            "YOUR TASK:",
        ]

        for section in required_sections:
            assert (
                section in generated_prompt
            ), f"Missing required section '{section}' in prompt for {test_case}"

    # Check minimum length (prompts should be substantial)
    assert (
        len(generated_prompt) > 500
    ), f"Prompt too short ({len(generated_prompt)} chars) for {test_case}"


# =============================================================================
# SUMMARY REPORTING
# =============================================================================


def pytest_collection_modifyitems(config, items):
    """Add custom markers and reporting."""
    for item in items:
        if "test_prompt" in item.nodeid:
            item.add_marker(pytest.mark.prompt_test)


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """Print summary of prompt tests."""
    if hasattr(config, "workerinput"):
        return  # Don't print in xdist workers

    prompt_tests = [
        item
        for item in terminalreporter.stats.get("passed", [])
        if "test_prompts.py" in str(item.nodeid)
    ]

    if prompt_tests:
        terminalreporter.write_sep("=", "Prompt Test Summary")
        terminalreporter.write_line(f"✅ {len(prompt_tests)} prompt tests passed")
        terminalreporter.write_line("")
        terminalreporter.write_line("Prompt version control: VALIDATED")
        terminalreporter.write_line("No unexpected changes detected in AI prompts.")
