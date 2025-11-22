#!/usr/bin/env python3
"""
Golden Prompt Generator for SurfCastAI

This script generates and updates golden prompt files for prompt testing.
It creates the prompt.txt files that serve as version-controlled snapshots
of expected prompt output.

Usage:
    # Generate prompts for all test cases
    python scripts/generate_golden_prompts.py

    # Generate prompts for specific test case
    python scripts/generate_golden_prompts.py --case case_01_high_confidence

    # Update existing golden prompts (overwrites prompt.txt files)
    python scripts/generate_golden_prompts.py --update

    # Generate prompts for specific specialist
    python scripts/generate_golden_prompts.py --specialist senior_forecaster

Author: SurfCastAI Team
Date: October 12, 2025
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, Any, Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import prompt generation functions from test file
from tests.test_prompts import generate_prompt_from_specialist, discover_test_cases


def generate_golden_prompt(test_case_dir: Path, force_update: bool = False) -> bool:
    """
    Generate golden prompt file for a test case.

    Args:
        test_case_dir: Directory containing test case
        force_update: If True, overwrite existing prompt.txt

    Returns:
        True if successful, False otherwise
    """
    specialist = test_case_dir.parent.name
    case_name = test_case_dir.name

    input_file = test_case_dir / "input.json"
    prompt_file = test_case_dir / "prompt.txt"

    # Check if input.json exists
    if not input_file.exists():
        print(f"❌ Missing input.json in {test_case_dir}")
        return False

    # Check if prompt.txt already exists
    if prompt_file.exists() and not force_update:
        print(f"⏭️  Skipping {specialist}/{case_name} (prompt.txt already exists)")
        print(f"   Use --update to overwrite")
        return True

    try:
        # Load input data
        with open(input_file, 'r') as f:
            input_data = json.load(f)

        # Generate prompt
        print(f"🔄 Generating prompt for {specialist}/{case_name}...")
        prompt = generate_prompt_from_specialist(specialist, input_data)

        # Write prompt to file
        with open(prompt_file, 'w') as f:
            f.write(prompt)

        print(f"✅ Generated {prompt_file}")
        print(f"   Length: {len(prompt)} characters")
        return True

    except NotImplementedError as e:
        print(f"⚠️  {specialist}/{case_name}: {e}")
        return False
    except Exception as e:
        print(f"❌ Error generating prompt for {specialist}/{case_name}: {e}")
        return False


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Generate golden prompt files for SurfCastAI prompt tests",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate all missing prompts
  python scripts/generate_golden_prompts.py

  # Update all prompts (overwrites existing)
  python scripts/generate_golden_prompts.py --update

  # Generate specific case
  python scripts/generate_golden_prompts.py --case case_01_high_confidence

  # Generate specific specialist
  python scripts/generate_golden_prompts.py --specialist senior_forecaster
        """
    )

    parser.add_argument(
        '--update',
        action='store_true',
        help='Update existing prompt.txt files (overwrites)'
    )

    parser.add_argument(
        '--case',
        type=str,
        help='Generate only for specific test case name'
    )

    parser.add_argument(
        '--specialist',
        type=str,
        choices=['senior_forecaster', 'buoy_analyst', 'pressure_analyst'],
        help='Generate only for specific specialist'
    )

    args = parser.parse_args()

    # Discover test cases
    print("🔍 Discovering test cases...")
    test_cases = discover_test_cases()

    if not test_cases:
        print("❌ No test cases found in tests/prompt_tests/")
        print("   Create test cases first with input.json files")
        return 1

    print(f"Found {len(test_cases)} test cases\n")

    # Filter test cases if requested
    if args.case:
        test_cases = [tc for tc in test_cases if tc.case_name == args.case]
        if not test_cases:
            print(f"❌ No test case found with name: {args.case}")
            return 1

    if args.specialist:
        test_cases = [tc for tc in test_cases if tc.specialist == args.specialist]
        if not test_cases:
            print(f"❌ No test cases found for specialist: {args.specialist}")
            return 1

    # Generate prompts
    success_count = 0
    fail_count = 0
    skip_count = 0

    for test_case in test_cases:
        result = generate_golden_prompt(test_case.test_dir, force_update=args.update)
        if result:
            success_count += 1
        else:
            fail_count += 1

    # Print summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"✅ Success: {success_count}")
    print(f"❌ Failed:  {fail_count}")
    print(f"📊 Total:   {len(test_cases)}")

    if fail_count > 0:
        print("\n⚠️  Some prompts failed to generate. See errors above.")
        return 1

    print("\n✨ All prompts generated successfully!")
    print("\nNext steps:")
    print("  1. Review generated prompt.txt files")
    print("  2. Run prompt tests: pytest tests/test_prompts.py -v")
    print("  3. Commit prompt.txt files to version control")

    return 0


if __name__ == '__main__':
    sys.exit(main())
