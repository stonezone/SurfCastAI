"""
Main forecast engine for SurfCastAI.

This module contains the main forecast engine responsible for
generating comprehensive surf forecasts based on processed data.
"""

import asyncio
import copy
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from ..core.config import Config
from ..core.openai_client import OpenAIClient
from ..processing.models.swell_event import SwellForecast
from ..processing.storm_detector import StormDetector
from ..utils.prompt_loader import PromptLoader
from ..utils.swell_propagation import SwellPropagationCalculator
from ..utils.validation_feedback import ValidationFeedback
from .data_manager import ForecastDataManager
from .local_generator import LocalForecastGenerator
from .model_settings import ModelSettings
from .prompt_templates import PromptTemplates


class ForecastEngine:
    """
    Main forecast engine for generating surf forecasts.

    Features:
    - Converts processed data into comprehensive surf forecasts
    - Uses AI to generate natural language forecasts
    - Supports iterative refinement for improved quality
    - Includes specialized North/South shore analysis
    - Incorporates seasonal context into forecasts
    """

    def __init__(self, config: Config):
        """
        Initialize the forecast engine.

        Args:
            config: Application configuration
        """
        self.config = config
        self.logger = logging.getLogger("forecast.engine")

        # Set up templates
        templates_dir = self.config.get("forecast", "templates_dir", None)
        self.templates = PromptTemplates(templates_dir)
        self.prompt_loader = PromptLoader(
            templates_dir,
            logger=self.logger.getChild("prompt_loader"),
            fallback_provider=self.templates.get_all_templates,
        )

        if not self.prompt_loader.is_fallback_enabled():
            alias_map = {
                "caldwell_main": "caldwell",
                "caldwell": "caldwell",
                "north_shore": "north_shore",
                "south_shore": "south_shore",
                "daily": "daily",
            }
            replacements = self.prompt_loader.as_templates(alias_map)
            if replacements:
                self.templates.update_templates(replacements)

        # Load OpenAI configuration
        # Try config first, then fall back to environment variable
        self.openai_api_key = self.config.get("openai", "api_key") or os.environ.get(
            "OPENAI_API_KEY"
        )

        # Get model name and set appropriate max_tokens
        model_name = self.config.get("openai", "model", "gpt-5-nano")

        # Model-specific max_tokens limits
        model_limits = {
            "gpt-4o-mini": 16384,
            "gpt-4o": 16384,
            "gpt-4-turbo": 4096,
            "gpt-4": 8192,
            "gpt-5-nano": 32768,
            "gpt-5-mini": 32768,
            "gpt-5": 32768,
        }

        # Determine max_tokens: config value, or model-specific limit, or 4096 default
        config_max_tokens = self.config.getint("openai", "max_tokens", None)
        if config_max_tokens is not None:
            default_max_tokens = config_max_tokens
        else:
            default_max_tokens = model_limits.get(model_name, 4096)

        primary_config = {
            "name": model_name,
            "max_tokens": default_max_tokens,
            "verbosity": self.config.get("openai", "verbosity", "high"),
            "reasoning_effort": self.config.get("openai", "reasoning_effort", "medium"),
        }

        # GPT-5-nano only supports temperature=1 (default), skip for this model
        if "gpt-5" in model_name.lower():
            self.temperature = None  # Use model default
        else:
            self.temperature = self.config.getfloat("openai", "temperature", 0.7)
        self.primary_model_settings = ModelSettings.from_config(primary_config)
        self.openai_model = (
            self.primary_model_settings.name
        )  # Backwards compatibility for legacy callers
        self.max_tokens = self.primary_model_settings.max_output_tokens

        analysis_models_raw = self.config.get("openai", "analysis_models", []) or []
        self.analysis_model_settings = [
            ModelSettings.from_config(
                raw,
                defaults={
                    "max_tokens": self.primary_model_settings.max_output_tokens,
                    "verbosity": self.primary_model_settings.verbosity,
                    "reasoning_effort": self.primary_model_settings.reasoning_effort,
                },
            )
            for raw in analysis_models_raw
            if isinstance(raw, dict)
        ]

        self.use_local_generator = self.config.getboolean(
            "forecast", "use_local_generator", default=not bool(self.openai_api_key)
        )
        if self.use_local_generator:
            self.logger.info("Using local forecast generator (OpenAI disabled)")

        # Set up iterative refinement
        # Disable refinement for GPT-5 models - they work better with single strong prompts
        if "gpt-5" in model_name.lower():
            self.refinement_cycles = 0
            self.logger.info("Refinement cycles disabled for GPT-5 model")
        else:
            self.refinement_cycles = self.config.getint("forecast", "refinement_cycles", 2)
        self.quality_threshold = self.config.getfloat("forecast", "quality_threshold", 0.8)

        # Load image configuration
        self.max_images = self.config.getint("forecast", "max_images", 10)

        # Load image detail levels with defaults
        image_detail_config = self.config.get("forecast", "image_detail_levels", {})
        if not isinstance(image_detail_config, dict):
            image_detail_config = {}

        self.image_detail_pressure = image_detail_config.get("pressure_charts", "high")
        self.image_detail_wave = image_detail_config.get("wave_models", "auto")
        self.image_detail_satellite = image_detail_config.get("satellite", "auto")
        self.image_detail_sst = image_detail_config.get("sst_charts", "low")

        # Log image configuration
        self.logger.info(f"Image configuration: max_images={self.max_images}")
        self.logger.info(
            f"Image detail levels: pressure={self.image_detail_pressure}, "
            f"wave={self.image_detail_wave}, satellite={self.image_detail_satellite}, "
            f"sst={self.image_detail_sst}"
        )

        # Initialize OpenAI client
        self.openai_client = OpenAIClient(
            api_key=self.openai_api_key,
            model=self.openai_model,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            logger=self.logger.getChild("openai_client"),
        )

        # Initialize data manager
        self.data_manager = ForecastDataManager(
            max_images=self.max_images,
            image_detail_pressure=self.image_detail_pressure,
            image_detail_wave=self.image_detail_wave,
            image_detail_satellite=self.image_detail_satellite,
            image_detail_sst=self.image_detail_sst,
            logger=self.logger.getChild("data_manager"),
        )

        # Initialize storm detection components
        self.storm_detector = StormDetector()
        self.propagation_calc = SwellPropagationCalculator()

        # Initialize token budget enforcement (kept in ForecastEngine for orchestration)
        self.token_budget = self.config.getint("forecast", "token_budget", 150000)
        self.warn_threshold = self.config.getint("forecast", "warn_threshold", 200000)
        self.enable_budget_enforcement = self.config.getboolean(
            "forecast", "enable_budget_enforcement", True
        )
        self.estimated_tokens = 0

        # Log budget configuration
        self.logger.info(
            f"Token budget enforcement: {'enabled' if self.enable_budget_enforcement else 'disabled'}"
        )
        self.logger.info(
            f"Token budget: {self.token_budget}, Warning threshold: {self.warn_threshold}"
        )

        # Specialist team setup (optional - feature flag)
        self.use_specialist_team = self.config.getboolean("forecast", "use_specialist_team", False)

        if self.use_specialist_team:
            try:
                from .specialists import BuoyAnalyst, PressureAnalyst, SeniorForecaster

                buoy_config = self.config.get("specialists", "buoy", {})
                pressure_config = self.config.get("specialists", "pressure", {})

                # Get the model for each specialist from the config
                buoy_model = self.config.get_specialist_model("buoy_analyst")
                pressure_model = self.config.get_specialist_model("pressure_analyst")
                senior_model = self.config.get_specialist_model("senior_forecaster")

                # Instantiate specialists and PASS THE MODEL NAME + ENGINE REFERENCE
                # Engine reference enables cost tracking for specialist API calls
                self.buoy_analyst = (
                    BuoyAnalyst(config, model_name=buoy_model, engine=self)
                    if buoy_config.get("enabled", True)
                    else None
                )
                self.pressure_analyst = (
                    PressureAnalyst(config, model_name=pressure_model, engine=self)
                    if pressure_config.get("enabled", True)
                    else None
                )
                self.senior_forecaster = SeniorForecaster(
                    config, model_name=senior_model, engine=self
                )

                specialists_enabled = []
                if self.buoy_analyst:
                    specialists_enabled.append("BuoyAnalyst")
                if self.pressure_analyst:
                    specialists_enabled.append("PressureAnalyst")
                specialists_enabled.append("SeniorForecaster")

                self.logger.info(
                    f"Specialist team architecture enabled: {', '.join(specialists_enabled)}"
                )
            except ImportError as e:
                raise ImportError(
                    f"Failed to import specialists: {e}\n"
                    f"You have use_specialist_team=true in config but specialist modules cannot be imported.\n"
                    f"This is a critical error that would degrade forecast accuracy.\n"
                    f"Either fix the import error or set use_specialist_team=false in config."
                )
        else:
            self.logger.info("Using monolithic forecast generation (specialist team disabled)")
            self.buoy_analyst = None
            self.pressure_analyst = None
            self.senior_forecaster = None

        # Initialize validation feedback for adaptive learning
        try:
            self.validation_feedback = ValidationFeedback()
            self.logger.info("Validation feedback system initialized for adaptive learning")
        except Exception as e:
            self.logger.warning(f"Validation feedback unavailable: {e}")
            self.validation_feedback = None

    async def _reset_run_metrics(self) -> None:
        """Reset per-run tracking before generating a forecast."""
        await self.openai_client.reset_metrics()
        self.estimated_tokens = 0

    async def generate_forecast(self, swell_forecast: SwellForecast) -> dict[str, Any]:
        """
        Generate a complete surf forecast from processed data.

        Args:
            swell_forecast: Processed swell forecast data

        Returns:
            Dictionary containing generated forecasts
        """
        try:
            await self._reset_run_metrics()
            self.logger.info("Starting forecast generation")

            # Extract forecast information
            forecast_id = swell_forecast.forecast_id
            generated_time = datetime.now().isoformat()

            # Prepare forecast data
            forecast_data = self.data_manager.prepare_forecast_data(swell_forecast)

            # SPECIALIST WORKFLOW (when enabled):
            # If specialists are enabled, filter data before passing to them
            if self.use_specialist_team and (self.buoy_analyst or self.pressure_analyst):
                # Filter out excluded data before specialists receive it
                filtered_data = self.data_manager.filter_quality_data(forecast_data)

                # Call specialists with filtered data
                # buoy_analysis = await self.buoy_analyst.analyze(filtered_data) if self.buoy_analyst else None
                # pressure_analysis = await self.pressure_analyst.analyze(filtered_data) if self.pressure_analyst else None

                # Synthesize specialist reports
                # specialist_data = {
                #     'buoy_analysis': buoy_analysis,
                #     'pressure_analysis': pressure_analysis,
                #     **filtered_data
                # }
                # final_forecast = await self.senior_forecaster.analyze(specialist_data)
                #
                # Note: Currently using monolithic generation below.
                # When specialist workflow is fully implemented, it will replace
                # the individual _generate_* calls with senior_forecaster synthesis.

            # Generate main forecast
            main_forecast = await self._generate_main_forecast(forecast_data)

            # Generate shore-specific forecasts
            north_shore_forecast = await self._generate_shore_forecast("north_shore", forecast_data)
            south_shore_forecast = await self._generate_shore_forecast("south_shore", forecast_data)

            # Generate daily forecast
            daily_forecast = await self._generate_daily_forecast(forecast_data)

            # Get API usage metrics
            metrics = await self.openai_client.get_metrics()
            api_usage = {
                "total_cost": metrics["total_cost"],
                "api_calls": metrics["api_calls"],
                "input_tokens": metrics["input_tokens"],
                "output_tokens": metrics["output_tokens"],
                "model": self.openai_model,
            }
            cost_summary = (
                metrics["total_cost"],
                metrics["api_calls"],
                metrics["input_tokens"],
                metrics["output_tokens"],
            )

            # Merge raw metadata from the fusion stage with runtime metrics
            fused_metadata = copy.deepcopy(forecast_data.get("metadata", {}))
            fused_metadata["source_data"] = {
                "swell_events": len(swell_forecast.swell_events),
                "locations": len(swell_forecast.locations),
            }
            fused_metadata["confidence"] = forecast_data.get("confidence", {})
            fused_metadata["api_usage"] = api_usage

            # Carry forward helpful context artifacts if present
            if "seasonal_context" in forecast_data:
                fused_metadata.setdefault("seasonal_context", forecast_data["seasonal_context"])
            if "images" in forecast_data:
                fused_metadata.setdefault("images", forecast_data["images"])
            if "storm_arrivals" in forecast_data:
                fused_metadata.setdefault("storm_arrivals", forecast_data["storm_arrivals"])

            result = {
                "forecast_id": forecast_id,
                "generated_time": generated_time,
                "main_forecast": main_forecast,
                "north_shore": north_shore_forecast,
                "south_shore": south_shore_forecast,
                "daily": daily_forecast,
                "metadata": fused_metadata,
            }

            # Log final cost summary
            self.logger.info(
                f"Forecast complete - Total API cost: ${cost_summary[0]:.6f} "
                f"({cost_summary[1]} calls, {cost_summary[2]} input + {cost_summary[3]} output tokens)"
            )

            self.logger.info(f"Forecast generation completed for forecast ID: {forecast_id}")
            return result

        except Exception as e:
            self.logger.error(f"Error generating forecast: {e}")
            return {
                "error": str(e),
                "forecast_id": swell_forecast.forecast_id,
                "generated_time": datetime.now().isoformat(),
            }

    def _check_token_budget(self, estimated: int) -> tuple[bool, str]:
        """
        Check if estimated token usage fits within budget.

        Provides graceful degradation strategy:
        - If over warn_threshold: Fail (use local generator)
        - If over token_budget but under warn_threshold: Warn but proceed
        - If under token_budget: Proceed normally

        Args:
            estimated: Estimated token count

        Returns:
            Tuple of (within_budget: bool, message: str)
        """
        if not self.enable_budget_enforcement:
            return (True, "Budget enforcement disabled")

        # Hard limit check
        if estimated > self.warn_threshold:
            return (False, f"Estimated {estimated} tokens exceeds hard limit {self.warn_threshold}")

        # Budget warning check (but still allow)
        if estimated > self.token_budget:
            warning = (
                f"Estimated {estimated} tokens exceeds budget {self.token_budget} "
                f"but under hard limit {self.warn_threshold}"
            )
            self.logger.warning(warning)
            return (True, warning)

        # Within budget
        pct_used = (estimated / self.token_budget) * 100

        # Log warnings at thresholds
        if pct_used >= 90:
            self.logger.warning(
                f"Token usage at {pct_used:.1f}% of budget ({estimated}/{self.token_budget})"
            )
        elif pct_used >= 80:
            self.logger.info(
                f"Token usage at {pct_used:.1f}% of budget ({estimated}/{self.token_budget})"
            )

        return (True, f"Within budget: {estimated}/{self.token_budget} ({pct_used:.1f}%)")

    async def _generate_main_forecast(self, forecast_data: dict[str, Any]) -> str:
        """
        Generate the main comprehensive forecast.

        Args:
            forecast_data: Prepared forecast data

        Returns:
            Generated forecast text
        """
        if self.use_local_generator:
            generator = LocalForecastGenerator(forecast_data)
            return generator.build_main_forecast()

        # Estimate token usage and check budget
        self.estimated_tokens = self.data_manager.estimate_tokens(forecast_data)
        within_budget, budget_message = self._check_token_budget(self.estimated_tokens)

        self.logger.info(f"Token budget check: {budget_message}")

        if not within_budget:
            self.logger.error(f"Token budget exceeded: {budget_message}")
            self.logger.error("Falling back to local generator due to token limit")
            generator = LocalForecastGenerator(forecast_data)
            return generator.build_main_forecast()

        # Get images and select critical ones (using configured max_images)
        images = forecast_data.get("images", {})
        selected_images = self.data_manager.select_critical_images(images)

        # Log token estimation
        estimated_tokens = 0
        for img in selected_images:
            detail = img["detail"]
            if detail == "high":
                estimated_tokens += 3000
            elif detail == "auto":
                estimated_tokens += 1500
            elif detail == "low":
                estimated_tokens += 500

        if selected_images:
            self.logger.info(
                f"Token usage - Images: ~{estimated_tokens} tokens (estimated) from {len(selected_images)} images"
            )

        # Group selected images by type
        pressure_charts = [
            img["url"]
            for img in selected_images
            if img["type"] in ("pressure_chart", "pressure_forecast")
        ]
        satellite_imgs = [img["url"] for img in selected_images if img["type"] == "satellite"]
        wave_model_imgs = [img["url"] for img in selected_images if img["type"] == "wave_model"]
        sst_charts = [img["url"] for img in selected_images if img["type"] == "sst_chart"]

        # Create debug directory for saving image analysis
        bundle_id = forecast_data.get("metadata", {}).get("bundle_id")
        debug_dir = None
        if bundle_id:
            debug_dir = Path("data") / bundle_id / "debug"
            debug_dir.mkdir(exist_ok=True, parents=True)
            self.logger.info(f"Created debug directory: {debug_dir}")

        # Generate image analysis first (if images available)
        image_analysis = ""
        if pressure_charts:
            from .prompt_templates import PRESSURE_CHART_ANALYSIS_PROMPT

            try:
                self.logger.info(
                    f"Calling {self.openai_model} for pressure chart analysis ({len(pressure_charts)} charts)..."
                )
                # Get detail level for pressure charts
                pressure_detail = next(
                    (
                        img["detail"]
                        for img in selected_images
                        if img["type"] in ("pressure_chart", "pressure_forecast")
                    ),
                    "high",
                )
                analysis = await asyncio.wait_for(
                    self.openai_client.call_openai_api(
                        system_prompt=self.templates.get_template("caldwell").get(
                            "system_prompt", ""
                        ),
                        user_prompt=PRESSURE_CHART_ANALYSIS_PROMPT,
                        image_urls=pressure_charts,
                        detail=pressure_detail,
                    ),
                    timeout=300.0,
                )
                self.logger.info("Pressure chart analysis completed")

                # Save to debug file
                if debug_dir:
                    with open(debug_dir / "image_analysis_pressure.txt", "w") as f:
                        f.write(analysis)

                image_analysis += f"\n\nPRESSURE CHART ANALYSIS:\n{analysis}\n"

                # Detect storms from pressure analysis and calculate arrivals
                try:
                    storms = self.storm_detector.parse_pressure_analysis(
                        analysis, datetime.now().isoformat()
                    )
                    if storms:
                        arrivals = self.storm_detector.calculate_hawaii_arrivals(
                            storms, self.propagation_calc
                        )
                        forecast_data["storm_arrivals"] = arrivals
                        self.logger.info(
                            f"Detected {len(storms)} storm(s), calculated {len(arrivals)} arrival(s)"
                        )

                        # Log arrival details
                        for arrival in arrivals:
                            self.logger.info(
                                f"  {arrival['storm_id']}: {arrival['estimated_height_ft']:.1f}ft "
                                f"@ {arrival['estimated_period_seconds']:.1f}s arriving {arrival['arrival_time']}"
                            )
                    else:
                        self.logger.info("No storms detected in pressure analysis")
                except Exception as e:
                    self.logger.error(f"Error in storm detection: {e}", exc_info=True)
            except TimeoutError:
                self.logger.error("Pressure chart analysis timed out after 5 minutes")
                image_analysis += "\n\nPRESSURE CHART ANALYSIS: [TIMEOUT]\n"
            except Exception as e:
                self.logger.error(f"Error in pressure chart analysis: {e}")
                image_analysis += f"\n\nPRESSURE CHART ANALYSIS: [ERROR: {e}]\n"

        if satellite_imgs:
            from .prompt_templates import SATELLITE_IMAGE_ANALYSIS_PROMPT

            try:
                self.logger.info(
                    f"Calling {self.openai_model} for satellite image analysis ({len(satellite_imgs)} images)..."
                )
                # Get detail level for satellite images
                satellite_detail = next(
                    (img["detail"] for img in selected_images if img["type"] == "satellite"), "auto"
                )
                analysis = await asyncio.wait_for(
                    self.openai_client.call_openai_api(
                        system_prompt=self.templates.get_template("caldwell").get(
                            "system_prompt", ""
                        ),
                        user_prompt=SATELLITE_IMAGE_ANALYSIS_PROMPT,
                        image_urls=satellite_imgs,
                        detail=satellite_detail,
                    ),
                    timeout=300.0,
                )
                self.logger.info("Satellite image analysis completed")

                # Save to debug file
                if debug_dir:
                    with open(debug_dir / "image_analysis_satellite.txt", "w") as f:
                        f.write(analysis)

                image_analysis += f"\n\nSATELLITE IMAGERY ANALYSIS:\n{analysis}\n"
            except TimeoutError:
                self.logger.error("Satellite image analysis timed out after 5 minutes")
                image_analysis += "\n\nSATELLITE IMAGERY ANALYSIS: [TIMEOUT]\n"
            except Exception as e:
                self.logger.error(f"Error in satellite image analysis: {e}")
                image_analysis += f"\n\nSATELLITE IMAGERY ANALYSIS: [ERROR: {e}]\n"

        if wave_model_imgs:
            self.logger.info(f"Analyzing {len(wave_model_imgs)} wave model images")
            # Get detail level for wave models
            wave_detail = next(
                (img["detail"] for img in selected_images if img["type"] == "wave_model"), "high"
            )
            # Note: Wave model analysis prompt can be added later
            # For now, we just log that we have them available

        if sst_charts:
            from .prompt_templates import SST_CHART_ANALYSIS_PROMPT

            try:
                self.logger.info(
                    f"Calling {self.openai_model} for SST chart analysis ({len(sst_charts)} charts)..."
                )
                # Get detail level for SST charts
                sst_detail = next(
                    (img["detail"] for img in selected_images if img["type"] == "sst_chart"), "low"
                )
                analysis = await asyncio.wait_for(
                    self.openai_client.call_openai_api(
                        system_prompt=self.templates.get_template("caldwell").get(
                            "system_prompt", ""
                        ),
                        user_prompt=SST_CHART_ANALYSIS_PROMPT,
                        image_urls=sst_charts,
                        detail=sst_detail,
                    ),
                    timeout=300.0,
                )
                self.logger.info("SST chart analysis completed")

                # Save to debug file
                if debug_dir:
                    with open(debug_dir / "image_analysis_sst.txt", "w") as f:
                        f.write(analysis)

                image_analysis += f"\n\nSEA SURFACE TEMPERATURE ANALYSIS:\n{analysis}\n"
            except TimeoutError:
                self.logger.error("SST chart analysis timed out after 5 minutes")
                image_analysis += "\n\nSEA SURFACE TEMPERATURE ANALYSIS: [TIMEOUT]\n"
            except Exception as e:
                self.logger.error(f"Error in SST chart analysis: {e}")
                image_analysis += f"\n\nSEA SURFACE TEMPERATURE ANALYSIS: [ERROR: {e}]\n"

        # Now generate forecast with both text data AND image analysis
        prompt = self.templates.get_caldwell_prompt(forecast_data)
        if image_analysis:
            prompt = f"{prompt}\n\n{image_analysis}\n\nIntegrate the above image analysis into your forecast."

        # Add swell arrival predictions if available
        arrival_context = self._format_arrival_predictions(forecast_data)
        if arrival_context:
            prompt = f"{prompt}\n\n{arrival_context}\n\nIncorporate the above swell arrival predictions into your forecast timeline."

        # Get template
        template = self.templates.get_template("caldwell")
        system_prompt = template.get("system_prompt", "")

        # Add seasonal context to system prompt
        seasonal_context = forecast_data.get("seasonal_context", {})
        season = seasonal_context.get("current_season", "unknown")
        seasonal_patterns = seasonal_context.get("seasonal_patterns", {})

        system_prompt += f"\nCurrent Season: {season.title()}\n"
        system_prompt += f"Typical {season.title()} Patterns:\n"
        for shore, info in seasonal_patterns.items():
            system_prompt += (
                f"- {shore.replace('_', ' ').title()}: {info.get('typical_conditions', '')}\n"
            )

        # Add confidence information
        confidence = forecast_data.get("confidence", {})
        overall_confidence = confidence.get("overall_score", 0.7)

        system_prompt += f"\nOverall Forecast Confidence: {overall_confidence:.1f}/1.0\n"
        if overall_confidence < 0.6:
            system_prompt += (
                "Include appropriate language indicating lower confidence in the forecast.\n"
            )

        # Add adaptive context based on recent performance
        adaptive_context = self._get_adaptive_context()
        if adaptive_context:
            system_prompt += f"\n\n{adaptive_context}"

        # Generate forecast with timeout
        try:
            self.logger.info(f"Calling {self.openai_model} for main forecast generation...")
            forecast = await asyncio.wait_for(
                self.openai_client.call_openai_api(system_prompt, prompt), timeout=300.0
            )
            self.logger.info("Main forecast generation completed")
        except TimeoutError:
            self.logger.error("Main forecast generation timed out after 5 minutes")
            forecast = "Error: Forecast generation timed out. Please try again."
            return forecast
        except Exception as e:
            self.logger.error(f"Error in main forecast generation: {e}")
            forecast = f"Error generating forecast: {str(e)}"
            return forecast

        # Apply iterative refinement if enabled
        if self.refinement_cycles > 0:
            forecast = await self._refine_forecast(forecast, forecast_data)

        return forecast

    async def _generate_shore_forecast(self, shore: str, forecast_data: dict[str, Any]) -> str:
        """
        Generate a shore-specific forecast.

        Args:
            shore: Shore name ('north_shore' or 'south_shore')
            forecast_data: Prepared forecast data

        Returns:
            Generated shore-specific forecast text
        """
        if self.use_local_generator:
            generator = LocalForecastGenerator(forecast_data)
            return generator.build_shore_forecast(shore)

        # Generate prompt
        prompt = self.templates.get_shore_prompt(shore, forecast_data)

        # Add swell arrival predictions if available
        arrival_context = self._format_arrival_predictions(forecast_data)
        if arrival_context:
            prompt = f"{prompt}\n\n{arrival_context}"

        # Get template
        template_name = "north_shore" if "north" in shore.lower() else "south_shore"
        template = self.templates.get_template(template_name)
        system_prompt = template.get("system_prompt", "")

        # Add seasonal context to system prompt
        seasonal_context = forecast_data.get("seasonal_context", {})
        season = seasonal_context.get("current_season", "unknown")
        seasonal_patterns = seasonal_context.get("seasonal_patterns", {})

        if shore in seasonal_patterns:
            shore_info = seasonal_patterns[shore]
            system_prompt += f"\nCurrent Season: {season.title()}\n"
            system_prompt += (
                f"Typical {season.title()} Patterns for {shore.replace('_', ' ').title()}:\n"
            )
            system_prompt += (
                f"- Primary Swell Direction: {shore_info.get('primary_swell_direction', '')}\n"
            )
            system_prompt += f"- Typical Size Range: {shore_info.get('typical_size_range', '')}\n"
            system_prompt += f"- Typical Conditions: {shore_info.get('typical_conditions', '')}\n"

        # Add adaptive context
        adaptive_context = self._get_adaptive_context()
        if adaptive_context:
            system_prompt += f"\n\n{adaptive_context}"

        # Generate forecast with timeout
        try:
            self.logger.info(f"Calling {self.openai_model} for {shore} forecast generation...")
            forecast = await asyncio.wait_for(
                self.openai_client.call_openai_api(system_prompt, prompt), timeout=300.0
            )
            self.logger.info(f"{shore} forecast generation completed")
        except TimeoutError:
            self.logger.error(f"{shore} forecast generation timed out after 5 minutes")
            forecast = f"Error: {shore} forecast timed out. Please try again."
        except Exception as e:
            self.logger.error(f"Error in {shore} forecast generation: {e}")
            forecast = f"Error generating {shore} forecast: {str(e)}"

        return forecast

    async def _generate_daily_forecast(self, forecast_data: dict[str, Any]) -> str:
        """
        Generate a daily forecast.

        Args:
            forecast_data: Prepared forecast data

        Returns:
            Generated daily forecast text
        """
        if self.use_local_generator:
            generator = LocalForecastGenerator(forecast_data)
            return generator.build_daily_forecast()

        # Get template
        template = self.templates.get_template("daily")
        system_prompt = template.get("system_prompt", "")

        # Build prompt with enriched context
        prompt = self.templates.get_daily_prompt(forecast_data)

        # Add swell arrival predictions if available
        arrival_context = self._format_arrival_predictions(forecast_data)
        if arrival_context:
            prompt = f"{prompt}\n\n{arrival_context}"

        # Add adaptive context
        adaptive_context = self._get_adaptive_context()
        if adaptive_context:
            system_prompt += f"\n\n{adaptive_context}"

        # Generate forecast with timeout
        try:
            self.logger.info(f"Calling {self.openai_model} for daily forecast generation...")
            forecast = await asyncio.wait_for(
                self.openai_client.call_openai_api(system_prompt, prompt), timeout=300.0
            )
            self.logger.info("Daily forecast generation completed")
        except TimeoutError:
            self.logger.error("Daily forecast generation timed out after 5 minutes")
            forecast = "Error: Daily forecast timed out. Please try again."
        except Exception as e:
            self.logger.error(f"Error in daily forecast generation: {e}")
            forecast = f"Error generating daily forecast: {str(e)}"

        return forecast

    def _format_arrival_predictions(self, forecast_data: dict[str, Any]) -> str:
        """
        Format swell arrival predictions for inclusion in forecast prompt.

        Args:
            forecast_data: Prepared forecast data with storm_arrivals

        Returns:
            Formatted string describing predicted arrivals, or empty string if none
        """
        try:
            # Storm arrivals are stored directly in forecast_data (not metadata)
            # This is set by storm detection in _generate_main_forecast() after pressure analysis
            arrivals = forecast_data.get("storm_arrivals", [])

            if not arrivals:
                return ""

            lines = ["PHYSICS-BASED SWELL ARRIVAL PREDICTIONS:"]
            lines.append("(Based on storm tracking and deep water wave propagation)")
            lines.append("")

            for arrival in arrivals:
                # Format arrival time nicely
                from datetime import datetime

                arrival_dt = datetime.fromisoformat(arrival["arrival_time"].replace("Z", "+00:00"))
                arrival_str = arrival_dt.strftime("%A %B %d, %I:%M %p HST")

                # Format travel details
                travel_days = arrival["travel_time_hours"] / 24

                lines.append(
                    f"• {arrival['storm_id'].replace('_', ' ').title()}: "
                    f"{arrival['estimated_height_ft']:.0f}ft @ {arrival['estimated_period_seconds']:.0f}s "
                    f"arriving {arrival_str}"
                )
                lines.append(
                    f"  Distance: {arrival['distance_nm']:.0f}nm, "
                    f"Travel time: {travel_days:.1f} days "
                    f"(confidence: {arrival['confidence']:.0%})"
                )
                lines.append("")

            return "\n".join(lines)

        except Exception as e:
            self.logger.warning(f"Error formatting arrival predictions: {e}")
            return ""  # Graceful degradation

    def _get_adaptive_context(self) -> str:
        """
        Get adaptive prompt context based on recent forecast performance.

        Returns:
            Formatted context string for system prompt, or empty if unavailable
        """
        if not self.validation_feedback:
            return ""

        try:
            report = self.validation_feedback.get_recent_performance()
            if not report.has_recent_data:
                self.logger.debug("No recent validation data for adaptive context")
                return ""

            context = self.validation_feedback.generate_prompt_context(report)

            if context:
                self.logger.info(
                    f"Adaptive context generated: {report.lookback_days} days, "
                    f"{len(report.shore_performance)} shores, "
                    f"MAE={report.overall_mae:.2f}ft"
                )

            return context

        except Exception as e:
            self.logger.warning(f"Error generating adaptive context: {e}")
            return ""  # Graceful degradation

    async def _refine_forecast(self, initial_forecast: str, forecast_data: dict[str, Any]) -> str:
        """
        Apply iterative refinement to improve forecast quality.

        Args:
            initial_forecast: Initial generated forecast
            forecast_data: Forecast data for context

        Returns:
            Refined forecast text
        """
        if self.use_local_generator:
            return initial_forecast

        current_forecast = initial_forecast

        for i in range(self.refinement_cycles):
            self.logger.info(f"Starting refinement cycle {i+1}/{self.refinement_cycles}")

            # Create refinement prompt
            system_prompt = """
You are an expert surf forecaster who specializes in improving the quality and accuracy of surf forecasts.
Carefully review the provided forecast and improve it based on the following criteria:

1. Technical accuracy - ensure swell heights, periods, and directions are consistent and accurate
2. Clarity - make sure the forecast is easy to understand while maintaining technical detail
3. Completeness - ensure all relevant shores and time periods are covered
4. Consistency - check that the forecast is internally consistent throughout
5. Specificity - add precise details about timing, locations, and conditions where possible

The goal is to maintain the original style and voice while improving overall quality.
Do NOT add fictional data or contradict the original forecast's core information.
"""

            # Add specific improvement instructions based on refinement cycle
            if i == 0:
                system_prompt += "\nFocus particularly on technical accuracy and consistency.\n"
            elif i == 1:
                system_prompt += "\nFocus particularly on clarity and specificity of details.\n"

            # Add confidence indicators if confidence is low
            confidence = forecast_data.get("confidence", {}).get("overall_score", 0.7)
            if confidence < 0.6:
                system_prompt += "\nMake sure to include appropriate language indicating uncertainty where relevant.\n"

            # Create user prompt
            prompt = f"""
Please review and improve the following surf forecast:

---
{current_forecast}
---

Improve this forecast while maintaining its style and core information. Focus on technical accuracy, clarity, consistency, and specificity.
"""

            # Generate refined forecast with timeout
            try:
                self.logger.info(
                    f"Calling {self.openai_model} for refinement cycle {i+1}/{self.refinement_cycles}..."
                )
                refined_forecast = await asyncio.wait_for(
                    self.openai_client.call_openai_api(system_prompt, prompt), timeout=300.0
                )
                self.logger.info(f"Refinement cycle {i+1}/{self.refinement_cycles} completed")
                # Update current forecast for next cycle
                current_forecast = refined_forecast
            except TimeoutError:
                self.logger.error(
                    f"Refinement cycle {i+1}/{self.refinement_cycles} timed out after 5 minutes"
                )
                # Continue with current forecast, skip this refinement
                continue
            except Exception as e:
                self.logger.error(f"Error in refinement cycle {i+1}/{self.refinement_cycles}: {e}")
                # Continue with current forecast, skip this refinement
                continue

        return current_forecast
