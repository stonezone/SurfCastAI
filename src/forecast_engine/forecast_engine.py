"""
Main forecast engine for SurfCastAI.

This module contains the main forecast engine responsible for
generating comprehensive surf forecasts based on processed data.
"""

import asyncio
import logging
import os
import json
from typing import Dict, List, Any, Optional, Union, Tuple
from datetime import datetime, timedelta
from pathlib import Path

from .prompt_templates import PromptTemplates
from .local_generator import LocalForecastGenerator
from .model_settings import ModelSettings
from ..processing.models.swell_event import SwellForecast, SwellEvent, ForecastLocation
from ..core.config import Config


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
        self.logger = logging.getLogger('forecast.engine')
        
        # Set up templates
        templates_dir = self.config.get('forecast', 'templates_dir', None)
        self.templates = PromptTemplates(templates_dir)
        
        # Load OpenAI configuration
        # Try config first, then fall back to environment variable
        self.openai_api_key = self.config.get('openai', 'api_key') or os.environ.get('OPENAI_API_KEY')
        primary_config = {
            "name": self.config.get('openai', 'model', 'gpt-5-nano'),
            "max_tokens": self.config.getint('openai', 'max_tokens', 32768),
            "verbosity": self.config.get('openai', 'verbosity', 'high'),
            "reasoning_effort": self.config.get('openai', 'reasoning_effort', 'medium'),
        }

        # GPT-5-nano only supports temperature=1 (default), skip for this model
        model_name = self.config.get('openai', 'model', 'gpt-5-nano')
        if 'gpt-5' in model_name.lower():
            self.temperature = None  # Use model default
        else:
            self.temperature = self.config.getfloat('openai', 'temperature', 0.7)
        self.primary_model_settings = ModelSettings.from_config(primary_config)
        self.openai_model = self.primary_model_settings.name  # Backwards compatibility for legacy callers
        self.max_tokens = self.primary_model_settings.max_output_tokens

        analysis_models_raw = self.config.get('openai', 'analysis_models', []) or []
        self.analysis_model_settings = [
            ModelSettings.from_config(raw, defaults={
                "max_tokens": self.primary_model_settings.max_output_tokens,
                "verbosity": self.primary_model_settings.verbosity,
                "reasoning_effort": self.primary_model_settings.reasoning_effort,
            })
            for raw in analysis_models_raw
            if isinstance(raw, dict)
        ]

        self.use_local_generator = self.config.getboolean(
            'forecast',
            'use_local_generator',
            default=not bool(self.openai_api_key)
        )
        if self.use_local_generator:
            self.logger.info('Using local forecast generator (OpenAI disabled)')

        # Set up iterative refinement
        # Disable refinement for GPT-5 models - they work better with single strong prompts
        model_name = self.config.get('openai', 'model', 'gpt-5-nano')
        if 'gpt-5' in model_name.lower():
            self.refinement_cycles = 0
            self.logger.info('Refinement cycles disabled for GPT-5 model')
        else:
            self.refinement_cycles = self.config.getint('forecast', 'refinement_cycles', 2)
        self.quality_threshold = self.config.getfloat('forecast', 'quality_threshold', 0.8)
        
        # Initialize cost tracking
        self.total_cost = 0.0
        self.api_call_count = 0
        self.total_input_tokens = 0
        self.total_output_tokens = 0
    
    async def generate_forecast(self, swell_forecast: SwellForecast) -> Dict[str, Any]:
        """
        Generate a complete surf forecast from processed data.
        
        Args:
            swell_forecast: Processed swell forecast data
            
        Returns:
            Dictionary containing generated forecasts
        """
        try:
            self.logger.info("Starting forecast generation")
            
            # Extract forecast information
            forecast_id = swell_forecast.forecast_id
            generated_time = datetime.now().isoformat()
            
            # Prepare forecast data
            forecast_data = self._prepare_forecast_data(swell_forecast)
            
            # Generate main forecast
            main_forecast = await self._generate_main_forecast(forecast_data)
            
            # Generate shore-specific forecasts
            north_shore_forecast = await self._generate_shore_forecast('north_shore', forecast_data)
            south_shore_forecast = await self._generate_shore_forecast('south_shore', forecast_data)
            
            # Generate daily forecast
            daily_forecast = await self._generate_daily_forecast(forecast_data)
            
            # Combine results
            result = {
                'forecast_id': forecast_id,
                'generated_time': generated_time,
                'main_forecast': main_forecast,
                'north_shore': north_shore_forecast,
                'south_shore': south_shore_forecast,
                'daily': daily_forecast,
                'metadata': {
                    'source_data': {
                        'swell_events': len(swell_forecast.swell_events),
                        'locations': len(swell_forecast.locations)
                    },
                    'confidence': forecast_data.get('confidence', {}),
                    'api_usage': {
                        'total_cost': round(self.total_cost, 6),
                        'api_calls': self.api_call_count,
                        'input_tokens': self.total_input_tokens,
                        'output_tokens': self.total_output_tokens,
                        'model': self.openai_model
                    }
                }
            }
            
            # Log final cost summary
            self.logger.info(
                f"Forecast complete - Total API cost: ${self.total_cost:.6f} "
                f"({self.api_call_count} calls, {self.total_input_tokens} input + {self.total_output_tokens} output tokens)"
            )
            
            self.logger.info(f"Forecast generation completed for forecast ID: {forecast_id}")
            return result
            
        except Exception as e:
            self.logger.error(f"Error generating forecast: {e}")
            return {
                'error': str(e),
                'forecast_id': swell_forecast.forecast_id,
                'generated_time': datetime.now().isoformat()
            }
    
    def _prepare_forecast_data(self, swell_forecast: SwellForecast) -> Dict[str, Any]:
        """
        Prepare data for forecast generation.
        
        Args:
            swell_forecast: Processed swell forecast data
            
        Returns:
            Dictionary with prepared data for templates
        """
        # Calculate date range
        start_date = datetime.now().strftime('%Y-%m-%d')
        end_date = (datetime.now() + timedelta(days=2)).strftime('%Y-%m-%d')
        
        # Extract confidence data
        confidence = swell_forecast.metadata.get('confidence', {})
        
        # Prepare swell events
        swell_events = []
        for event in swell_forecast.swell_events:
            swell_events.append({
                'event_id': event.event_id,
                'start_time': event.start_time,
                'peak_time': event.peak_time,
                'end_time': event.end_time,
                'primary_direction': event.primary_direction,
                'primary_direction_cardinal': event.primary_direction_cardinal,
                'significance': event.significance,
                'hawaii_scale': event.hawaii_scale,
                'source': event.source,
                'dominant_period': event.dominant_period,
                'primary_components': [{
                    'height': c.height,
                    'period': c.period,
                    'direction': c.direction,
                    'confidence': c.confidence,
                    'source': c.source
                } for c in event.primary_components]
            })
        
        # Prepare shore data
        shore_data = {}
        for location in swell_forecast.locations:
            shore_name = location.shore.lower().replace(' ', '_')
            
            # Get shore-specific swell events
            shore_events = []
            for event in location.swell_events:
                shore_events.append({
                    'event_id': event.event_id,
                    'start_time': event.start_time,
                    'peak_time': event.peak_time,
                    'end_time': event.end_time,
                    'primary_direction': event.primary_direction,
                    'primary_direction_cardinal': event.primary_direction_cardinal,
                    'significance': event.significance,
                    'hawaii_scale': event.hawaii_scale,
                    'source': event.source,
                    'dominant_period': event.dominant_period,
                    'exposure_factor': event.metadata.get(f'exposure_{shore_name}', 0.5),
                    'primary_components': [{
                        'height': c.height,
                        'period': c.period,
                        'direction': c.direction,
                        'confidence': c.confidence,
                        'source': c.source
                    } for c in event.primary_components]
                })
            
            shore_data[shore_name] = {
                'name': location.shore,
                'swell_events': shore_events,
                'metadata': location.metadata,
                'latitude': location.latitude,
                'longitude': location.longitude,
                'facing_direction': location.facing_direction
            }
        
        # Determine primary shores based on activity
        primary_shores = []
        if shore_data.get('north_shore', {}).get('swell_events'):
            primary_shores.append('North Shore')
        if shore_data.get('south_shore', {}).get('swell_events'):
            primary_shores.append('South Shore')
        
        # Prepare forecast data
        forecast_data = {
            'forecast_id': swell_forecast.forecast_id,
            'start_date': start_date,
            'end_date': end_date,
            'region': 'Oahu',
            'shores': primary_shores,
            'swell_events': swell_events,
            'shore_data': shore_data,
            'confidence': confidence,
            'metadata': swell_forecast.metadata
        }

        # Add seasonal context
        forecast_data['seasonal_context'] = self._get_seasonal_context()

        # Collect available images from bundle
        bundle_id = swell_forecast.metadata.get('bundle_id')
        images = self._collect_bundle_images(bundle_id) if bundle_id else {}
        forecast_data['images'] = images

        return forecast_data
    
    def _collect_bundle_images(self, bundle_id: str) -> Dict[str, List[str]]:
        """
        Collect image paths from bundle directories.

        Args:
            bundle_id: Bundle identifier

        Returns:
            Dict with keys: 'pressure_charts', 'satellite', 'wave_models', 'sst_charts'
        """
        from pathlib import Path
        import json

        bundle_path = Path('data') / bundle_id
        images = {
            'pressure_charts': [],
            'satellite': [],
            'wave_models': [],
            'sst_charts': []
        }

        # Collect chart images and separate SST charts
        charts_dir = bundle_path / 'charts'
        if charts_dir.exists():
            metadata_file = charts_dir / 'metadata.json'
            if metadata_file.exists():
                try:
                    with open(metadata_file) as f:
                        chart_metadata = json.load(f)
                        for item in chart_metadata:
                            if item.get('status') == 'success' and item.get('file_path'):
                                file_path = item['file_path']
                                # Separate SST charts from pressure charts
                                if 'sst' in file_path.lower() or 'sea_surface_temp' in file_path.lower():
                                    images['sst_charts'].append(file_path)
                                else:
                                    images['pressure_charts'].append(file_path)
                except Exception as e:
                    self.logger.warning(f"Failed to read chart metadata: {e}")

        # Collect satellite images
        satellite_dir = bundle_path / 'satellite' / 'satellite'
        if satellite_dir.exists():
            try:
                for img_path in list(satellite_dir.glob('*.png')) + list(satellite_dir.glob('*.jpg')):
                    images['satellite'].append(str(img_path))
            except Exception as e:
                self.logger.warning(f"Failed to collect satellite images: {e}")

        # Collect wave model images
        model_dir = bundle_path / 'models'
        if model_dir.exists():
            try:
                for img_path in list(model_dir.glob('*.png')) + list(model_dir.glob('*.jpg')):
                    images['wave_models'].append(str(img_path))
            except Exception as e:
                self.logger.warning(f"Failed to collect wave model images: {e}")

        total_images = sum(len(v) for v in images.values())
        self.logger.info(f"Collected images: {total_images} total (pressure: {len(images['pressure_charts'])}, sst: {len(images['sst_charts'])}, satellite: {len(images['satellite'])}, wave_models: {len(images['wave_models'])})")
        return images

    def _select_critical_images(self, images: Dict[str, List[str]], max_images: int = 6) -> List[Dict[str, Any]]:
        """
        Select most valuable images within token budget.

        OPTIMIZED FOR TEMPORAL EVOLUTION ANALYSIS (GPT-5 Vision):
        Focus on DEPTH (temporal sequences) over variety to enable AI insights
        humans can't achieve - simultaneous analysis of complete temporal evolution.

        Priority:
        1. Pressure chart evolution (high detail) - 4 images (0hr, 24hr, 48hr, 96hr)
           Track lows, highs, fronts over time to identify system movement patterns
        2. Wave forecast evolution (auto detail) - 4 images (0hr, 24hr, 48hr, 96hr)
           Validate fetch predictions and swell propagation over time
        3. Satellite imagery (auto detail) - 1 image
           Latest cloud patterns for system validation
        4. SST anomaly (low detail) - 1 image
           Storm intensity context (low detail sufficient for anomaly patterns)

        Args:
            images: Dict with keys 'pressure_charts', 'satellite', 'wave_models', 'sst_charts'
            max_images: Maximum number of images to select (default: 6, hard cap: 10)

        Returns:
            List of dicts: [{"url": "...", "detail": "high/auto/low", "type": "pressure_chart/satellite/wave_model/sst"}, ...]
        """
        # Enforce hard cap (GPT-5 limit)
        max_images = min(max_images, 10)
        selected = []

        # Priority 1: Pressure chart evolution - 4 images at high detail
        # 0hr, 24hr, 48hr, 96hr surface forecasts showing system movement
        pressure_charts = images.get('pressure_charts', [])
        for i, chart in enumerate(pressure_charts[:4]):
            selected.append({
                'url': chart,
                'detail': 'high',
                'type': 'pressure_chart',
                'description': f'Pressure forecast T+{i*24}hr'
            })
            if len(selected) >= max_images:
                return selected

        # Priority 2: Wave forecast evolution - 4 images at auto detail
        # 0hr, 24hr, 48hr, 96hr wave heights/directions validating pressure systems
        wave_models = images.get('wave_models', [])
        for i, wave in enumerate(wave_models[:4]):
            selected.append({
                'url': wave,
                'detail': 'auto',
                'type': 'wave_model',
                'description': f'Wave model T+{i*24}hr'
            })
            if len(selected) >= max_images:
                return selected

        # Priority 3: Satellite imagery - 1 image at auto detail
        # Latest cloud patterns for validation
        satellite_imgs = images.get('satellite', [])
        if satellite_imgs:
            selected.append({
                'url': satellite_imgs[0],
                'detail': 'auto',
                'type': 'satellite',
                'description': 'Latest satellite imagery'
            })
            if len(selected) >= max_images:
                return selected

        # Priority 4: SST anomaly - 1 image at low detail
        # Affects storm intensity - low detail sufficient for anomaly patterns
        sst_charts = images.get('sst_charts', [])
        if sst_charts:
            selected.append({
                'url': sst_charts[0],
                'detail': 'low',
                'type': 'sst_chart',
                'description': 'Sea surface temperature anomaly'
            })

        return selected[:max_images]

    def _get_seasonal_context(self) -> Dict[str, Any]:
        """
        Get seasonal context information.
        
        Returns:
            Dictionary with seasonal context
        """
        now = datetime.now()
        month = now.month
        
        # Determine season
        if 11 <= month <= 12 or 1 <= month <= 3:
            season = 'winter'
        elif 4 <= month <= 5:
            season = 'spring'
        elif 6 <= month <= 8:
            season = 'summer'
        else:  # 9, 10
            season = 'fall'
        
        # Seasonal patterns
        seasonal_info = {
            'winter': {
                'north_shore': {
                    'primary_swell_direction': 'NW',
                    'typical_size_range': '4-12+ feet (Hawaiian)',
                    'quality': 'High',
                    'consistency': 'High',
                    'typical_conditions': 'Consistent NW to N swells with varying wind conditions. Prime season for North Shore with frequent large swells.'
                },
                'south_shore': {
                    'primary_swell_direction': 'Background S',
                    'typical_size_range': '0-2 feet (Hawaiian)',
                    'quality': 'Low',
                    'consistency': 'Low',
                    'typical_conditions': 'Generally flat with occasional small background swells. Not prime season for South Shore.'
                }
            },
            'summer': {
                'north_shore': {
                    'primary_swell_direction': 'Background NW',
                    'typical_size_range': '0-3 feet (Hawaiian)',
                    'quality': 'Low',
                    'consistency': 'Low',
                    'typical_conditions': 'Generally flat with occasional small background swells. Not prime season for North Shore.'
                },
                'south_shore': {
                    'primary_swell_direction': 'S to SW',
                    'typical_size_range': '2-5+ feet (Hawaiian)',
                    'quality': 'High',
                    'consistency': 'High',
                    'typical_conditions': 'Consistent S to SW swells with generally favorable trade winds. Prime season for South Shore.'
                }
            },
            'spring': {
                'north_shore': {
                    'primary_swell_direction': 'NW to N',
                    'typical_size_range': '3-8 feet (Hawaiian)',
                    'quality': 'Medium-High',
                    'consistency': 'Medium',
                    'typical_conditions': 'Transition season with decreasing NW swells but generally good conditions with lighter winds.'
                },
                'south_shore': {
                    'primary_swell_direction': 'S',
                    'typical_size_range': '1-3+ feet (Hawaiian)',
                    'quality': 'Medium',
                    'consistency': 'Medium',
                    'typical_conditions': 'Beginning of south swell season with increasing activity and size.'
                }
            },
            'fall': {
                'north_shore': {
                    'primary_swell_direction': 'NW to WNW',
                    'typical_size_range': '2-6+ feet (Hawaiian)',
                    'quality': 'Medium',
                    'consistency': 'Medium',
                    'typical_conditions': 'Early season NW swells begin to arrive. Transition period with improving conditions as winter approaches.'
                },
                'south_shore': {
                    'primary_swell_direction': 'S to SSW',
                    'typical_size_range': '1-3 feet (Hawaiian)',
                    'quality': 'Medium-Low',
                    'consistency': 'Medium-Low',
                    'typical_conditions': 'End of south swell season with decreasing activity and size.'
                }
            }
        }
        
        return {
            'current_season': season,
            'month': month,
            'seasonal_patterns': seasonal_info[season]
        }
    
    async def _generate_main_forecast(self, forecast_data: Dict[str, Any]) -> str:
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

        # Get images and select critical ones
        # Using 10 images to maximize GPT-5 vision insight extraction
        images = forecast_data.get('images', {})
        selected_images = self._select_critical_images(images, max_images=10)

        # Log token estimation
        estimated_tokens = 0
        for img in selected_images:
            detail = img['detail']
            if detail == 'high':
                estimated_tokens += 3000
            elif detail == 'auto':
                estimated_tokens += 1500
            elif detail == 'low':
                estimated_tokens += 500

        if selected_images:
            self.logger.info(f"Token usage - Images: ~{estimated_tokens} tokens (estimated) from {len(selected_images)} images")

        # Group selected images by type
        pressure_charts = [img['url'] for img in selected_images if img['type'] in ('pressure_chart', 'pressure_forecast')]
        satellite_imgs = [img['url'] for img in selected_images if img['type'] == 'satellite']
        wave_model_imgs = [img['url'] for img in selected_images if img['type'] == 'wave_model']
        sst_charts = [img['url'] for img in selected_images if img['type'] == 'sst_chart']

        # Create debug directory for saving image analysis
        bundle_id = forecast_data.get('metadata', {}).get('bundle_id')
        debug_dir = None
        if bundle_id:
            debug_dir = Path('data') / bundle_id / 'debug'
            debug_dir.mkdir(exist_ok=True, parents=True)
            self.logger.info(f"Created debug directory: {debug_dir}")

        # Generate image analysis first (if images available)
        image_analysis = ""
        if pressure_charts:
            from .prompt_templates import PRESSURE_CHART_ANALYSIS_PROMPT
            try:
                self.logger.info(f"Calling GPT-5-mini for pressure chart analysis ({len(pressure_charts)} charts)...")
                # Get detail level for pressure charts
                pressure_detail = next((img['detail'] for img in selected_images if img['type'] in ('pressure_chart', 'pressure_forecast')), 'high')
                analysis = await asyncio.wait_for(
                    self._call_openai_api(
                        system_prompt=self.templates.get_template('caldwell').get('system_prompt', ''),
                        user_prompt=PRESSURE_CHART_ANALYSIS_PROMPT,
                        image_urls=pressure_charts,
                        detail=pressure_detail
                    ),
                    timeout=300.0
                )
                self.logger.info("Pressure chart analysis completed")

                # Save to debug file
                if debug_dir:
                    with open(debug_dir / 'image_analysis_pressure.txt', 'w') as f:
                        f.write(analysis)

                image_analysis += f"\n\nPRESSURE CHART ANALYSIS:\n{analysis}\n"
            except asyncio.TimeoutError:
                self.logger.error("Pressure chart analysis timed out after 5 minutes")
                image_analysis += "\n\nPRESSURE CHART ANALYSIS: [TIMEOUT]\n"
            except Exception as e:
                self.logger.error(f"Error in pressure chart analysis: {e}")
                image_analysis += f"\n\nPRESSURE CHART ANALYSIS: [ERROR: {e}]\n"

        if satellite_imgs:
            from .prompt_templates import SATELLITE_IMAGE_ANALYSIS_PROMPT
            try:
                self.logger.info(f"Calling GPT-5-mini for satellite image analysis ({len(satellite_imgs)} images)...")
                # Get detail level for satellite images
                satellite_detail = next((img['detail'] for img in selected_images if img['type'] == 'satellite'), 'auto')
                analysis = await asyncio.wait_for(
                    self._call_openai_api(
                        system_prompt=self.templates.get_template('caldwell').get('system_prompt', ''),
                        user_prompt=SATELLITE_IMAGE_ANALYSIS_PROMPT,
                        image_urls=satellite_imgs,
                        detail=satellite_detail
                    ),
                    timeout=300.0
                )
                self.logger.info("Satellite image analysis completed")

                # Save to debug file
                if debug_dir:
                    with open(debug_dir / 'image_analysis_satellite.txt', 'w') as f:
                        f.write(analysis)

                image_analysis += f"\n\nSATELLITE IMAGERY ANALYSIS:\n{analysis}\n"
            except asyncio.TimeoutError:
                self.logger.error("Satellite image analysis timed out after 5 minutes")
                image_analysis += "\n\nSATELLITE IMAGERY ANALYSIS: [TIMEOUT]\n"
            except Exception as e:
                self.logger.error(f"Error in satellite image analysis: {e}")
                image_analysis += f"\n\nSATELLITE IMAGERY ANALYSIS: [ERROR: {e}]\n"

        if wave_model_imgs:
            self.logger.info(f"Analyzing {len(wave_model_imgs)} wave model images")
            # Get detail level for wave models
            wave_detail = next((img['detail'] for img in selected_images if img['type'] == 'wave_model'), 'high')
            # Note: Wave model analysis prompt can be added later
            # For now, we just log that we have them available

        if sst_charts:
            from .prompt_templates import SST_CHART_ANALYSIS_PROMPT
            try:
                self.logger.info(f"Calling GPT-5-mini for SST chart analysis ({len(sst_charts)} charts)...")
                # Get detail level for SST charts
                sst_detail = next((img['detail'] for img in selected_images if img['type'] == 'sst_chart'), 'low')
                analysis = await asyncio.wait_for(
                    self._call_openai_api(
                        system_prompt=self.templates.get_template('caldwell').get('system_prompt', ''),
                        user_prompt=SST_CHART_ANALYSIS_PROMPT,
                        image_urls=sst_charts,
                        detail=sst_detail
                    ),
                    timeout=300.0
                )
                self.logger.info("SST chart analysis completed")

                # Save to debug file
                if debug_dir:
                    with open(debug_dir / 'image_analysis_sst.txt', 'w') as f:
                        f.write(analysis)

                image_analysis += f"\n\nSEA SURFACE TEMPERATURE ANALYSIS:\n{analysis}\n"
            except asyncio.TimeoutError:
                self.logger.error("SST chart analysis timed out after 5 minutes")
                image_analysis += "\n\nSEA SURFACE TEMPERATURE ANALYSIS: [TIMEOUT]\n"
            except Exception as e:
                self.logger.error(f"Error in SST chart analysis: {e}")
                image_analysis += f"\n\nSEA SURFACE TEMPERATURE ANALYSIS: [ERROR: {e}]\n"

        # Now generate forecast with both text data AND image analysis
        prompt = self.templates.get_caldwell_prompt(forecast_data)
        if image_analysis:
            prompt = f"{prompt}\n\n{image_analysis}\n\nIntegrate the above image analysis into your forecast."

        # Get template
        template = self.templates.get_template('caldwell')
        system_prompt = template.get('system_prompt', '')

        # Add seasonal context to system prompt
        seasonal_context = forecast_data.get('seasonal_context', {})
        season = seasonal_context.get('current_season', 'unknown')
        seasonal_patterns = seasonal_context.get('seasonal_patterns', {})

        system_prompt += f"\nCurrent Season: {season.title()}\n"
        system_prompt += f"Typical {season.title()} Patterns:\n"
        for shore, info in seasonal_patterns.items():
            system_prompt += f"- {shore.replace('_', ' ').title()}: {info.get('typical_conditions', '')}\n"

        # Add confidence information
        confidence = forecast_data.get('confidence', {})
        overall_confidence = confidence.get('overall_score', 0.7)

        system_prompt += f"\nOverall Forecast Confidence: {overall_confidence:.1f}/1.0\n"
        if overall_confidence < 0.6:
            system_prompt += "Include appropriate language indicating lower confidence in the forecast.\n"

        # Generate forecast with timeout
        try:
            self.logger.info("Calling GPT-5-nano for main forecast generation...")
            forecast = await asyncio.wait_for(
                self._call_openai_api(system_prompt, prompt),
                timeout=300.0
            )
            self.logger.info("Main forecast generation completed")
        except asyncio.TimeoutError:
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
    
    async def _generate_shore_forecast(self, shore: str, forecast_data: Dict[str, Any]) -> str:
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
        
        # Get template
        template_name = 'north_shore' if 'north' in shore.lower() else 'south_shore'
        template = self.templates.get_template(template_name)
        system_prompt = template.get('system_prompt', '')
        
        # Add seasonal context to system prompt
        seasonal_context = forecast_data.get('seasonal_context', {})
        season = seasonal_context.get('current_season', 'unknown')
        seasonal_patterns = seasonal_context.get('seasonal_patterns', {})
        
        if shore in seasonal_patterns:
            shore_info = seasonal_patterns[shore]
            system_prompt += f"\nCurrent Season: {season.title()}\n"
            system_prompt += f"Typical {season.title()} Patterns for {shore.replace('_', ' ').title()}:\n"
            system_prompt += f"- Primary Swell Direction: {shore_info.get('primary_swell_direction', '')}\n"
            system_prompt += f"- Typical Size Range: {shore_info.get('typical_size_range', '')}\n"
            system_prompt += f"- Typical Conditions: {shore_info.get('typical_conditions', '')}\n"

        # Generate forecast with timeout
        try:
            self.logger.info(f"Calling GPT-5-nano for {shore} forecast generation...")
            forecast = await asyncio.wait_for(
                self._call_openai_api(system_prompt, prompt),
                timeout=300.0
            )
            self.logger.info(f"{shore} forecast generation completed")
        except asyncio.TimeoutError:
            self.logger.error(f"{shore} forecast generation timed out after 5 minutes")
            forecast = f"Error: {shore} forecast timed out. Please try again."
        except Exception as e:
            self.logger.error(f"Error in {shore} forecast generation: {e}")
            forecast = f"Error generating {shore} forecast: {str(e)}"

        return forecast
    
    async def _generate_daily_forecast(self, forecast_data: Dict[str, Any]) -> str:
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
        template = self.templates.get_template('daily')
        system_prompt = template.get('system_prompt', '')
        
        # Build prompt
        start_date = forecast_data.get('start_date', datetime.now().strftime('%Y-%m-%d'))
        region = forecast_data.get('region', 'Oahu')
        
        # Extract significant swell events
        swell_events = forecast_data.get('swell_events', [])
        swell_description = ""
        
        if swell_events:
            # Get the most significant event
            main_event = max(swell_events, key=lambda e: e.get('significance', 0))
            # Convert numeric direction to cardinal
            direction_deg = main_event.get('primary_direction', 0)
            if direction_deg is not None:
                dirs = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
                       "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
                direction = dirs[round(direction_deg / 22.5) % 16]
            else:
                direction = "NW"

            swell_description = f"with a {direction} swell"

        prompt = f"Generate a daily surf forecast for {region} for {start_date}, {swell_description}."

        # Generate forecast with timeout
        try:
            self.logger.info("Calling GPT-5-nano for daily forecast generation...")
            forecast = await asyncio.wait_for(
                self._call_openai_api(system_prompt, prompt),
                timeout=300.0
            )
            self.logger.info("Daily forecast generation completed")
        except asyncio.TimeoutError:
            self.logger.error("Daily forecast generation timed out after 5 minutes")
            forecast = "Error: Daily forecast timed out. Please try again."
        except Exception as e:
            self.logger.error(f"Error in daily forecast generation: {e}")
            forecast = f"Error generating daily forecast: {str(e)}"

        return forecast
    
    async def _refine_forecast(self, initial_forecast: str, forecast_data: Dict[str, Any]) -> str:
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
            confidence = forecast_data.get('confidence', {}).get('overall_score', 0.7)
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
                self.logger.info(f"Calling GPT-5-nano for refinement cycle {i+1}/{self.refinement_cycles}...")
                refined_forecast = await asyncio.wait_for(
                    self._call_openai_api(system_prompt, prompt),
                    timeout=300.0
                )
                self.logger.info(f"Refinement cycle {i+1}/{self.refinement_cycles} completed")
                # Update current forecast for next cycle
                current_forecast = refined_forecast
            except asyncio.TimeoutError:
                self.logger.error(f"Refinement cycle {i+1}/{self.refinement_cycles} timed out after 5 minutes")
                # Continue with current forecast, skip this refinement
                continue
            except Exception as e:
                self.logger.error(f"Error in refinement cycle {i+1}/{self.refinement_cycles}: {e}")
                # Continue with current forecast, skip this refinement
                continue
        
        return current_forecast
    
    async def _call_openai_api(
        self,
        system_prompt: str,
        user_prompt: str,
        image_urls: Optional[List[str]] = None,
        detail: str = "auto"
    ) -> str:
        """
        Call the OpenAI API to generate text with optional image inputs.

        Args:
            system_prompt: System prompt for the model
            user_prompt: User prompt containing specific request
            image_urls: Optional list of image URLs/paths (max 10)
            detail: Image resolution - "auto", "low", or "high"

        Returns:
            Generated text
        """
        # Import here to avoid dependency if OpenAI is not available
        try:
            from openai import AsyncOpenAI
        except ImportError:
            self.logger.error("OpenAI package not installed. Please install it with: pip install openai")
            return "Error: OpenAI package not installed."
        
        try:
            # Log prompt details for debugging
            self.logger.debug(f"System prompt length: {len(system_prompt)} chars")
            self.logger.debug(f"User prompt length: {len(user_prompt)} chars")
            self.logger.debug(f"User prompt preview: {user_prompt[:500]}...")
            
            # Initialize client
            client = AsyncOpenAI(api_key=self.openai_api_key)

            # Build message content
            if image_urls:
                # Multimodal message with images
                content = [{"type": "text", "text": user_prompt}]

                for url in image_urls[:10]:  # GPT-5 limit: 10 images
                    # Convert local paths to base64 data URLs
                    if url.startswith('data/'):
                        import base64
                        from pathlib import Path
                        try:
                            image_data = base64.b64encode(Path(url).read_bytes()).decode()
                            ext = Path(url).suffix.lower()
                            mime_type = {'.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.gif': 'image/gif'}.get(ext, 'image/png')
                            url = f"data:{mime_type};base64,{image_data}"
                        except Exception as e:
                            self.logger.warning(f"Failed to load image {url}: {e}")
                            continue

                    content.append({
                        "type": "image_url",
                        "image_url": {"url": url, "detail": detail}
                    })

                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": content}
                ]
            else:
                # Text-only message (legacy)
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]

            # Call API (prefer modern parameter, gracefully fall back for legacy models)
            request_kwargs = {
                "model": self.openai_model,
                "messages": messages,
            }
            
            # Only add temperature if specified (GPT-5 models use default)
            if self.temperature is not None:
                request_kwargs["temperature"] = self.temperature

            try:
                response = await client.chat.completions.create(
                    **request_kwargs,
                    max_completion_tokens=self.max_tokens
                )
            except Exception as call_error:
                error_text = str(call_error).lower()
                if (
                    "max_completion_tokens" in error_text
                    and any(keyword in error_text for keyword in ("unsupported", "unrecognized", "unknown"))
                ):
                    self.logger.debug(
                        "max_completion_tokens unsupported for model %s; retrying with max_tokens",
                        self.openai_model,
                    )
                    response = await client.chat.completions.create(
                        **request_kwargs,
                        max_tokens=self.max_tokens
                    )
                else:
                    raise
            
            # Extract and return content
            if response.choices and response.choices[0].message:
                content = response.choices[0].message.content
                self.logger.debug(f"API response content type: {type(content)}, value: {repr(content)}")
                
                # Track token usage and costs
                if hasattr(response, 'usage') and response.usage:
                    input_tokens = response.usage.prompt_tokens
                    output_tokens = response.usage.completion_tokens
                    
                    # Calculate cost based on model pricing
                    # GPT-5 pricing: https://openai.com/pricing
                    if 'gpt-5-mini' in self.openai_model.lower():
                        # GPT-5-mini: $0.25/1M input, $2.00/1M output
                        cost = (input_tokens * 0.00000025 + output_tokens * 0.000002)
                    elif 'gpt-5-nano' in self.openai_model.lower():
                        # GPT-5-nano: $0.05/1M input, $0.40/1M output
                        cost = (input_tokens * 0.00000005 + output_tokens * 0.0000004)
                    elif 'gpt-5' in self.openai_model.lower():
                        # GPT-5: $1.25/1M input, $10.00/1M output
                        cost = (input_tokens * 0.00000125 + output_tokens * 0.00001)
                    else:
                        # Default to GPT-4 pricing if unknown
                        cost = (input_tokens * 0.00001 + output_tokens * 0.00003)
                    
                    # Accumulate totals
                    self.total_input_tokens += input_tokens
                    self.total_output_tokens += output_tokens
                    self.total_cost += cost
                    self.api_call_count += 1
                    
                    self.logger.info(
                        f"API call #{self.api_call_count}: {input_tokens} input + {output_tokens} output tokens = ${cost:.6f} "
                        f"(total: ${self.total_cost:.6f})"
                    )
                else:
                    self.logger.warning("No usage data returned from API")
                
                if content is None:
                    self.logger.error("API returned None for content")
                    return ""
                return content.strip()
            else:
                self.logger.error("No content returned from OpenAI API")
                return ""
                
        except Exception as e:
            self.logger.error(f"Error calling OpenAI API: {e}")
            return f"Error generating forecast: {str(e)}"