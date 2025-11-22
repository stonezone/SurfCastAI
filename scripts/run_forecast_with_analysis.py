#!/usr/bin/env python3
"""
Script to run the full SurfCastAI pipeline and analyze results with GPT-4.1.
"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

import dotenv

# Load environment variables
dotenv.load_dotenv()

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Import OpenAI for analysis
from openai import AsyncOpenAI

from src.core import Config, load_config
from src.main import run_pipeline, setup_logging


async def analyze_with_gpt41(forecast_path, logger):
    """
    Analyze a generated forecast with GPT-4.1.

    Args:
        forecast_path: Path to the forecast JSON data
        logger: Logger instance

    Returns:
        Analysis results
    """
    logger.info(f"Analyzing forecast with GPT-4.1: {forecast_path}")

    # Check if API key exists
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        logger.error("No OpenAI API key found in environment variables")
        return {"error": "No OpenAI API key found"}

    # Read forecast data
    try:
        with open(forecast_path) as f:
            forecast_data = json.load(f)
    except Exception as e:
        logger.error(f"Error reading forecast data: {e}")
        return {"error": f"Error reading forecast data: {e}"}

    # Initialize OpenAI client
    client = AsyncOpenAI(api_key=api_key)

    # Extract forecast text
    main_forecast = forecast_data.get("main_forecast", "")
    north_shore = forecast_data.get("north_shore", "")
    south_shore = forecast_data.get("south_shore", "")
    daily = forecast_data.get("daily", "")

    # Create analysis prompt
    prompt = f"""
As an expert surf forecaster with intimate knowledge of Hawaiian waters and surf conditions,
analyze the following surf forecast and provide detailed feedback:

MAIN FORECAST:
{main_forecast}

NORTH SHORE FORECAST:
{north_shore}

SOUTH SHORE FORECAST:
{south_shore}

DAILY FORECAST:
{daily}

Please analyze this forecast in the following areas:
1. Overall quality and accuracy based on your expertise
2. Comparison to Pat Caldwell's style and level of detail
3. Technical completeness (swell direction, height, period, timing)
4. Shore-specific accuracy for North and South shores
5. Clarity and usefulness for surfers of different experience levels
6. Suggestions for improvement

Also highlight any particularly strong sections or areas that need enhancement.
"""

    # Get analysis from GPT-4.1
    try:
        logger.info("Calling GPT-4.1 API")
        response = await client.chat.completions.create(
            model="gpt-4o",  # Updated to current model
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert Hawaiian surf forecaster with decades of experience, similar to Pat Caldwell. You deeply understand ocean dynamics, swell patterns, and local surf breaks. Analyze the forecast with technical precision and insider knowledge.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
            max_tokens=2000,
        )

        # Extract and return analysis
        analysis = response.choices[0].message.content
        logger.info("GPT-4.1 analysis completed successfully")

        # Save analysis to file
        analysis_path = Path(forecast_path).parent / "gpt41_analysis.txt"
        with open(analysis_path, "w") as f:
            f.write(analysis)

        return {"status": "success", "analysis": analysis, "analysis_path": str(analysis_path)}

    except Exception as e:
        logger.error(f"Error calling GPT-4.1 API: {e}")
        return {"error": f"Error calling GPT-4.1 API: {e}"}


async def run_full_pipeline():
    """Run the full pipeline and analyze the results."""
    # Load configuration
    config = load_config()

    # Set up logging
    logger = setup_logging(config)

    logger.info("Starting SurfCastAI full pipeline with GPT-4.1 analysis")

    try:
        # Run the pipeline
        logger.info("Running the forecast pipeline")

        # Use the existing bundle
        bundle_id = "bundle_20250608_080000"
        logger.info(f"Using existing bundle: {bundle_id}")

        # Run only the forecast part
        results = await run_pipeline(config, logger, "forecast", bundle_id)

        if "forecast" in results and results["forecast"]["status"] == "success":
            # Get the JSON data path
            if "json" in results["forecast"]:
                json_path = results["forecast"]["json"]

                # Analyze with GPT-4.1
                analysis_results = await analyze_with_gpt41(json_path, logger)

                if "error" in analysis_results:
                    logger.error(f"Analysis failed: {analysis_results['error']}")
                else:
                    logger.info(f"Analysis saved to: {analysis_results['analysis_path']}")
                    logger.info("Process completed successfully!")

                    # Print output locations for user
                    output_paths = {k: v for k, v in results["forecast"].items() if k != "status"}

                    print("\nForecast Generation Completed Successfully!")
                    print("\nOutput Files:")
                    for format_name, path in output_paths.items():
                        print(f"- {format_name.upper()}: {path}")

                    print(f"\nGPT-4.1 Analysis: {analysis_results['analysis_path']}")
                    print("\nView the HTML version for the best formatted experience.")
            else:
                logger.error("No JSON output found in forecast results")
        else:
            if "forecast" in results and "status" in results["forecast"]:
                logger.error(
                    f"Forecast generation failed: {results['forecast'].get('message', 'Unknown error')}"
                )
            else:
                logger.error("Forecast generation failed with unknown error")

    except Exception as e:
        logger.error(f"Error running pipeline: {e}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(run_full_pipeline()))
