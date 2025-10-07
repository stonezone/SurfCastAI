#!/usr/bin/env python3
"""
SurfCastAI: AI-Powered Oahu Surf Forecasting System
Main entry point for running the forecasting pipeline.
"""

import argparse
import asyncio
import logging
import sys
import json
from pathlib import Path
from typing import Dict, Any, List, Optional

from src.core import Config, load_config, DataCollector, BundleManager, MetadataTracker
from src.processing import BuoyProcessor, WeatherProcessor, WaveModelProcessor, DataFusionSystem
from src.forecast_engine import ForecastEngine, ForecastFormatter


def setup_logging(config: Config) -> logging.Logger:
    """
    Set up logging based on configuration.
    
    Args:
        config: Application configuration
        
    Returns:
        Root logger
    """
    log_level_str = config.get('general', 'log_level', 'INFO').upper()
    log_level = getattr(logging, log_level_str, logging.INFO)
    
    # Get log file path
    log_file = config.get('general', 'log_file', 'surfcastai.log')
    
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_file)
        ]
    )
    
    logger = logging.getLogger('surfcastai')
    logger.info(f"Logging initialized at level {log_level_str}")
    
    return logger


async def collect_data(config: Config, logger: logging.Logger) -> Dict[str, Any]:
    """
    Collect data from all enabled sources.
    
    Args:
        config: Application configuration
        logger: Logger instance
        
    Returns:
        Dictionary with collection results
    """
    logger.info("Starting data collection")
    
    # Create data collector
    collector = DataCollector(config)
    
    # Run collection
    results = await collector.collect_data(region="Hawaii")
    
    return results


async def process_data(config: Config, logger: logging.Logger, bundle_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Process collected data.
    
    Args:
        config: Application configuration
        logger: Logger instance
        bundle_id: Optional bundle ID to process (uses latest if not provided)
        
    Returns:
        Dictionary with processing results
    """
    logger.info("Starting data processing")
    
    # Get bundle manager
    bundle_manager = BundleManager(config.data_directory)
    
    # Get bundle path
    if bundle_id is None:
        bundle_id = bundle_manager.get_latest_bundle()
        if bundle_id is None:
            logger.error("No bundles found")
            return {
                "status": "error",
                "message": "No data bundles found"
            }
    
    logger.info(f"Processing bundle: {bundle_id}")
    
    # Get bundle metadata
    metadata = bundle_manager.get_bundle_metadata(bundle_id)
    if metadata is None:
        logger.error(f"Bundle {bundle_id} not found or has no metadata")
        return {
            "status": "error",
            "message": f"Bundle {bundle_id} not found or has no metadata"
        }
    
    def _load_agent_json(agent_name: str, pattern: str) -> List[Dict[str, Any]]:
        agent_path = Path(config.data_directory) / bundle_id / agent_name
        payloads: List[Dict[str, Any]] = []
        if agent_path.exists():
            for file_path in agent_path.glob(pattern):
                try:
                    with open(file_path, 'r') as fh:
                        data = json.load(fh)
                        # If the JSON is a list, extend; otherwise append
                        if isinstance(data, list):
                            payloads.extend(data)
                        else:
                            payloads.append(data)
                except Exception as exc:
                    logger.warning(f"Failed to load {file_path}: {exc}")
        return payloads

    # Process buoy data
    logger.info("Processing buoy data")
    buoy_processor = BuoyProcessor(config)
    logger.info(f"BuoyProcessor created: {type(buoy_processor)}, has process_bundle: {hasattr(buoy_processor, 'process_bundle')}")
    logger.info(f"Calling process_bundle with bundle_id={bundle_id}, pattern='**/buoy_*.json'")
    buoy_results = buoy_processor.process_bundle(bundle_id, "**/buoy_*.json")
    logger.info(f"process_bundle returned: {type(buoy_results)}, length={len(buoy_results)}")
    
    # Process weather data
    logger.info("Processing weather data")
    weather_processor = WeatherProcessor(config)
    weather_results = weather_processor.process_bundle(bundle_id, "weather/weather_*.json")
    
    # Process model data
    logger.info("Processing wave model data")
    wave_model_processor = WaveModelProcessor(config)
    model_results = wave_model_processor.process_bundle(bundle_id, "models/model_*.*")
    
    # Load supplemental agent outputs
    metar_data = _load_agent_json('metar', 'metar_*.json')
    tide_data = _load_agent_json('tides', 'tide_*.json')
    tropical_data = _load_agent_json('tropical', 'tropical_outlook.json')
    chart_data = _load_agent_json('charts', '*.json')
    
    # Fuse the data
    logger.info("Fusing data from multiple sources")
    logger.info(f"Buoy results: {len(buoy_results)} total, {sum(1 for r in buoy_results if r.success)} successful")
    fusion_system = DataFusionSystem(config)
    
    # Prepare data for fusion
    fusion_data = {
        "metadata": metadata,
        "buoy_data": [result.data for result in buoy_results if result.success],
        "weather_data": [result.data for result in weather_results if result.success],
        "model_data": [result.data for result in model_results if result.success],
        "metar_data": metar_data,
        "tide_data": tide_data,
        "tropical_data": tropical_data,
        "chart_data": chart_data
    }
    
    # Process fusion
    fusion_result = fusion_system.process(fusion_data)
    
    # Create processing results
    results = {
        "status": "success" if fusion_result.success else "error",
        "bundle_id": bundle_id,
        "buoy_results": {
            "total": len(buoy_results),
            "successful": sum(1 for r in buoy_results if r.success)
        },
        "weather_results": {
            "total": len(weather_results),
            "successful": sum(1 for r in weather_results if r.success)
        },
        "model_results": {
            "total": len(model_results),
            "successful": sum(1 for r in model_results if r.success)
        },
        "fusion_result": fusion_result.success
    }
    
    # Save fused data
    if fusion_result.success:
        # Create directory for processed data
        processed_dir = Path(config.data_directory) / bundle_id / "processed"
        processed_dir.mkdir(exist_ok=True)
        
        # Save fused data
        fusion_path = processed_dir / "fused_forecast.json"
        fusion_system.save_result(fusion_result, fusion_path, overwrite=True)
        
        results["fusion_path"] = str(fusion_path)
    else:
        results["fusion_error"] = fusion_result.error
    
    return results


async def generate_forecast(config: Config, logger: logging.Logger, bundle_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Generate forecast based on collected data.
    
    Args:
        config: Application configuration
        logger: Logger instance
        bundle_id: Optional bundle ID to use (uses latest if not provided)
        
    Returns:
        Dictionary with forecast results
    """
    logger.info("Starting forecast generation")
    
    # Get bundle manager
    bundle_manager = BundleManager(config.data_directory)
    
    # Get bundle path
    if bundle_id is None:
        bundle_id = bundle_manager.get_latest_bundle()
        if bundle_id is None:
            logger.error("No bundles found")
            return {
                "status": "error",
                "message": "No data bundles found"
            }
    
    logger.info(f"Using bundle: {bundle_id}")
    
    # Check for processed forecast data
    processed_dir = Path(config.data_directory) / bundle_id / "processed"
    fusion_path = processed_dir / "fused_forecast.json"
    
    if not fusion_path.exists():
        logger.error(f"Processed data not found: {fusion_path}")
        return {
            "status": "error",
            "message": f"Processed data not found. Run data processing first."
        }
    
    # Load processed data
    logger.info(f"Loading processed data from {fusion_path}")
    with open(fusion_path, 'r') as f:
        try:
            # Try to parse as JSON
            fusion_data = json.loads(f.read())
            # Convert to SwellForecast object
            from src.processing.models import dict_to_swell_forecast
            fusion_data = dict_to_swell_forecast(fusion_data)
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON in {fusion_path}")
            return {
                "status": "error",
                "message": f"Invalid JSON in processed data file"
            }
    
    # Create forecast engine
    logger.info("Creating forecast engine")
    forecast_engine = ForecastEngine(config)
    
    # Generate forecast
    logger.info("Generating forecast")
    forecast = await forecast_engine.generate_forecast(fusion_data)
    
    # Check for errors
    if 'error' in forecast:
        logger.error(f"Forecast generation failed: {forecast['error']}")
        return {
            "status": "error",
            "message": f"Forecast generation failed: {forecast['error']}"
        }
    
    # Format forecast
    logger.info("Formatting forecast")
    formatter = ForecastFormatter(config)
    formatted = formatter.format_forecast(forecast)
    
    # Return results
    return {
        "status": "success",
        "bundle_id": bundle_id,
        "forecast_id": forecast.get('forecast_id'),
        "formats": formatted
    }


async def run_pipeline(config: Config, logger: logging.Logger, mode: str, bundle_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Run the forecasting pipeline.
    
    Args:
        config: Application configuration
        logger: Logger instance
        mode: Operation mode (collect, process, forecast, full)
        bundle_id: Optional bundle ID to use (uses latest if not provided)
        
    Returns:
        Dictionary with pipeline results
    """
    results = {}
    
    if mode in ['collect', 'full']:
        collection_results = await collect_data(config, logger)
        results['collection'] = collection_results
        # Use the newly created bundle for subsequent steps
        bundle_id = collection_results.get('bundle_id')
    
    if mode in ['process', 'forecast', 'full']:
        processing_results = await process_data(config, logger, bundle_id)
        results['processing'] = processing_results
    
    if mode in ['forecast', 'full']:
        forecast_results = await generate_forecast(config, logger, bundle_id)
        results['forecast'] = forecast_results
    
    return results


def list_bundles(config: Config) -> None:
    """List all available data bundles."""
    bundle_manager = BundleManager(config.data_directory)
    bundles = bundle_manager.list_bundles()
    
    print(f"Found {len(bundles)} data bundles:")
    for i, bundle in enumerate(bundles):
        timestamp = bundle.get('timestamp', 'unknown')
        bundle_id = bundle.get('bundle_id', 'unknown')
        
        # Extract bundle statistics
        stats = bundle.get('stats', {})
        total_files = stats.get('total_files', 0)
        successful = stats.get('successful_files', 0)
        
        print(f"{i+1}. {bundle_id} - {timestamp}")
        print(f"   Files: {successful}/{total_files} successful")
        
        # Show error if present
        if 'error' in bundle:
            print(f"   Error: {bundle['error']}")
        
        print()


def bundle_info(config: Config, bundle_id: Optional[str] = None) -> None:
    """Display detailed information about a specific bundle."""
    bundle_manager = BundleManager(config.data_directory)
    
    if bundle_id is None:
        bundle_id = bundle_manager.get_latest_bundle()
        if bundle_id is None:
            print("No bundles found")
            return
        print(f"Using latest bundle: {bundle_id}")
    
    metadata = bundle_manager.get_bundle_metadata(bundle_id)
    if metadata is None:
        print(f"Bundle {bundle_id} not found or has no metadata")
        return
    
    # Print basic information
    print(f"Bundle ID: {bundle_id}")
    print(f"Timestamp: {metadata.get('timestamp', 'unknown')}")
    print(f"Region: {metadata.get('region', 'unknown')}")
    
    # Print statistics
    stats = metadata.get('stats', {})
    print("\nStatistics:")
    print(f"  Total files: {stats.get('total_files', 0)}")
    print(f"  Successful files: {stats.get('successful_files', 0)}")
    print(f"  Failed files: {stats.get('failed_files', 0)}")
    print(f"  Total size: {stats.get('total_size_mb', 0):.2f} MB")
    
    # Print agent results
    agent_results = metadata.get('agent_results', {})
    print("\nAgent Results:")
    for agent, results in agent_results.items():
        print(f"  {agent}:")
        if 'error' in results:
            print(f"    Error: {results['error']}")
        else:
            print(f"    Files: {results.get('successful', 0)}/{results.get('total', 0)} successful")
            print(f"    Success rate: {results.get('success_rate', 0):.1f}%")
    
    # Print file list
    print("\nFile list available with --files option")

def bundle_files(config: Config, bundle_id: Optional[str] = None) -> None:
    """Display file list for a specific bundle."""
    bundle_manager = BundleManager(config.data_directory)
    
    if bundle_id is None:
        bundle_id = bundle_manager.get_latest_bundle()
        if bundle_id is None:
            print("No bundles found")
            return
        print(f"Using latest bundle: {bundle_id}")
    
    files = bundle_manager.get_bundle_file_list(bundle_id)
    if not files:
        print(f"No files found in bundle {bundle_id}")
        return
    
    print(f"Files in bundle {bundle_id}:")
    for i, file_info in enumerate(files):
        name = file_info.get('name', 'unknown')
        path = file_info.get('path', 'unknown')
        size = file_info.get('size_bytes', 0)
        status = file_info.get('status', 'unknown')
        
        print(f"{i+1}. {name} ({size} bytes) - {status}")
        print(f"   Path: {path}")
        
        # Show error if present
        if 'error' in file_info:
            print(f"   Error: {file_info['error']}")
        
        # Only show first 20 files, then summarize
        if i >= 19 and len(files) > 20:
            print(f"\n... and {len(files) - 20} more files")
            break
        
        print()

async def validate_forecast_cmd(config: Config, forecast_id: str) -> None:
    """
    Validate a specific forecast against actual observations.
    
    Args:
        config: Application configuration
        forecast_id: ID of forecast to validate
    """
    from src.validation import ValidationDatabase, ForecastValidator
    
    print(f"\nValidating forecast: {forecast_id}")
    print("=" * 60)
    
    # Initialize database and validator
    db_path = config.get('validation', 'database_path', 'data/validation.db')
    database = ValidationDatabase(db_path)
    validator = ForecastValidator(database)
    
    try:
        # Run validation
        results = await validator.validate_forecast(forecast_id, hours_after=24)
        
        # Print results
        print(f"\nForecast ID: {results['forecast_id']}")
        print(f"Validated at: {results['validated_at']}")
        print(f"Predictions validated: {results['predictions_validated']}/{results['predictions_total']}")
        
        if 'error' in results:
            print(f"\nError: {results['error']}")
            return
        
        # Print metrics
        metrics = results.get('metrics', {})
        print("\nMetrics:")
        print(f"  MAE (Mean Absolute Error):        {metrics.get('mae', 0):.2f} ft  (target: < 2.0 ft)")
        print(f"  RMSE (Root Mean Square Error):    {metrics.get('rmse', 0):.2f} ft  (target: < 2.5 ft)")
        print(f"  Categorical Accuracy:              {metrics.get('categorical_accuracy', 0)*100:.1f}%  (target: > 75%)")
        print(f"  Direction Accuracy:                {metrics.get('direction_accuracy', 0)*100:.1f}%  (target: > 80%)")
        print(f"  Sample Size:                       {metrics.get('sample_size', 0)} matches")
        
        # Print pass/fail status
        print("\nValidation Status:")
        mae_pass = metrics.get('mae', float('inf')) < 2.0
        rmse_pass = metrics.get('rmse', float('inf')) < 2.5
        cat_pass = metrics.get('categorical_accuracy', 0) > 0.75
        dir_pass = metrics.get('direction_accuracy', 0) > 0.80
        
        print(f"  MAE < 2.0 ft:          {'✓ PASS' if mae_pass else '✗ FAIL'}")
        print(f"  RMSE < 2.5 ft:         {'✓ PASS' if rmse_pass else '✗ FAIL'}")
        print(f"  Categorical > 75%:     {'✓ PASS' if cat_pass else '✗ FAIL'}")
        print(f"  Direction > 80%:       {'✓ PASS' if dir_pass else '✗ FAIL'}")
        
        overall_pass = mae_pass and rmse_pass and cat_pass and dir_pass
        print(f"\nOverall: {'✓ PASS' if overall_pass else '✗ FAIL'}")
        
    except ValueError as e:
        print(f"\nError: {e}")
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        logging.getLogger('surfcastai').error(f"Validation error: {e}", exc_info=True)


async def validate_all_forecasts_cmd(config: Config, hours_after: int = 24) -> None:
    """
    Validate all forecasts that are ready for validation.
    
    Args:
        config: Application configuration
        hours_after: Minimum hours after forecast before validating
    """
    from src.validation import ValidationDatabase, ForecastValidator
    
    print(f"\nValidating all forecasts ({hours_after}+ hours old)")
    print("=" * 60)
    
    # Initialize database and validator
    db_path = config.get('validation', 'database_path', 'data/validation.db')
    database = ValidationDatabase(db_path)
    validator = ForecastValidator(database)
    
    # Get forecasts needing validation
    forecasts = database.get_forecasts_needing_validation(hours_after=hours_after)
    
    if not forecasts:
        print(f"\nNo forecasts found that need validation (must be {hours_after}+ hours old)")
        return
    
    print(f"\nFound {len(forecasts)} forecast(s) to validate:\n")
    
    # Validate each forecast
    results_summary = []
    
    for i, forecast in enumerate(forecasts, 1):
        forecast_id = forecast['forecast_id']
        created_at = forecast['created_at']
        
        print(f"{i}. Validating {forecast_id} (created {created_at})...")
        
        try:
            results = await validator.validate_forecast(forecast_id, hours_after=hours_after)
            
            metrics = results.get('metrics', {})
            results_summary.append({
                'forecast_id': forecast_id,
                'success': 'error' not in results,
                'mae': metrics.get('mae'),
                'rmse': metrics.get('rmse'),
                'categorical_accuracy': metrics.get('categorical_accuracy'),
                'direction_accuracy': metrics.get('direction_accuracy'),
                'sample_size': metrics.get('sample_size', 0)
            })
            
            print(f"   ✓ Validated: MAE={metrics.get('mae', 0):.2f}ft, "
                  f"RMSE={metrics.get('rmse', 0):.2f}ft, "
                  f"Cat={metrics.get('categorical_accuracy', 0)*100:.0f}%, "
                  f"n={metrics.get('sample_size', 0)}")
            
        except Exception as e:
            print(f"   ✗ Error: {e}")
            results_summary.append({
                'forecast_id': forecast_id,
                'success': False,
                'error': str(e)
            })
    
    # Print summary
    print("\n" + "=" * 60)
    print("Validation Summary:")
    print("=" * 60)
    
    successful = [r for r in results_summary if r['success']]
    failed = [r for r in results_summary if not r['success']]
    
    print(f"\nTotal forecasts: {len(results_summary)}")
    print(f"Successfully validated: {len(successful)}")
    print(f"Failed: {len(failed)}")
    
    if successful:
        # Calculate aggregate metrics
        mae_values = [r['mae'] for r in successful if r.get('mae') is not None]
        rmse_values = [r['rmse'] for r in successful if r.get('rmse') is not None]
        cat_values = [r['categorical_accuracy'] for r in successful if r.get('categorical_accuracy') is not None]
        dir_values = [r['direction_accuracy'] for r in successful if r.get('direction_accuracy') is not None]
        
        if mae_values:
            print(f"\nAggregate Metrics:")
            print(f"  Average MAE:  {sum(mae_values)/len(mae_values):.2f} ft")
            print(f"  Average RMSE: {sum(rmse_values)/len(rmse_values):.2f} ft")
            if cat_values:
                print(f"  Average Categorical Accuracy: {sum(cat_values)/len(cat_values)*100:.1f}%")
            if dir_values:
                print(f"  Average Direction Accuracy: {sum(dir_values)/len(dir_values)*100:.1f}%")


async def accuracy_report_cmd(config: Config, days: int = 30) -> None:
    """
    Generate accuracy report for recent forecasts.
    
    Args:
        config: Application configuration
        days: Number of days to include in report
    """
    from src.validation import ValidationDatabase
    import sqlite3
    
    print(f"\nAccuracy Report (Last {days} Days)")
    print("=" * 60)
    
    # Initialize database
    db_path = config.get('validation', 'database_path', 'data/validation.db')
    database = ValidationDatabase(db_path)
    
    # Calculate cutoff timestamp
    cutoff = datetime.now().timestamp() - (days * 86400)
    
    with sqlite3.connect(database.db_path) as conn:
        cursor = conn.cursor()
        
        # Get validation statistics
        cursor.execute("""
            SELECT 
                COUNT(DISTINCT f.forecast_id) as total_forecasts,
                COUNT(v.id) as total_validations,
                AVG(v.mae) as avg_mae,
                AVG(v.rmse) as avg_rmse,
                AVG(CASE WHEN v.category_match = 1 THEN 1.0 ELSE 0.0 END) as categorical_accuracy,
                AVG(CASE WHEN v.direction_error <= 22.5 THEN 1.0 ELSE 0.0 END) as direction_accuracy
            FROM forecasts f
            INNER JOIN validations v ON f.forecast_id = v.forecast_id
            WHERE f.created_at >= ?
        """, (cutoff,))
        
        row = cursor.fetchone()
        
        if not row or row[0] == 0:
            print(f"\nNo validated forecasts found in the last {days} days.")
            return
        
        total_forecasts = row[0]
        total_validations = row[1]
        avg_mae = row[2]
        avg_rmse = row[3]
        categorical_accuracy = row[4]
        direction_accuracy = row[5]
        
        print(f"\nOverview:")
        print(f"  Period: Last {days} days")
        print(f"  Validated Forecasts: {total_forecasts}")
        print(f"  Total Validations: {total_validations}")
        print(f"  Average Predictions per Forecast: {total_validations/total_forecasts:.1f}")
        
        print(f"\nAccuracy Metrics:")
        print(f"  MAE (Mean Absolute Error):     {avg_mae:.2f} ft  (target: < 2.0 ft)")
        print(f"  RMSE (Root Mean Square Error): {avg_rmse:.2f} ft  (target: < 2.5 ft)")
        print(f"  Categorical Accuracy:          {categorical_accuracy*100:.1f}%  (target: > 75%)")
        print(f"  Direction Accuracy:            {direction_accuracy*100:.1f}%  (target: > 80%)")
        
        # Performance assessment
        mae_pass = avg_mae < 2.0
        rmse_pass = avg_rmse < 2.5
        cat_pass = categorical_accuracy > 0.75
        dir_pass = direction_accuracy > 0.80
        
        print(f"\nPerformance Assessment:")
        print(f"  MAE Target:         {'✓ PASS' if mae_pass else '✗ FAIL'}")
        print(f"  RMSE Target:        {'✓ PASS' if rmse_pass else '✗ FAIL'}")
        print(f"  Categorical Target: {'✓ PASS' if cat_pass else '✗ FAIL'}")
        print(f"  Direction Target:   {'✓ PASS' if dir_pass else '✗ FAIL'}")
        
        # Get per-shore breakdown
        cursor.execute("""
            SELECT 
                p.shore,
                COUNT(v.id) as validations,
                AVG(v.mae) as avg_mae,
                AVG(v.rmse) as avg_rmse,
                AVG(CASE WHEN v.category_match = 1 THEN 1.0 ELSE 0.0 END) as categorical_accuracy
            FROM predictions p
            INNER JOIN validations v ON p.id = v.prediction_id
            INNER JOIN forecasts f ON p.forecast_id = f.forecast_id
            WHERE f.created_at >= ?
            GROUP BY p.shore
        """, (cutoff,))
        
        shore_stats = cursor.fetchall()
        
        if shore_stats:
            print(f"\nPer-Shore Breakdown:")
            for shore, validations, mae, rmse, cat_acc in shore_stats:
                print(f"\n  {shore}:")
                print(f"    Validations: {validations}")
                print(f"    MAE:  {mae:.2f} ft")
                print(f"    RMSE: {rmse:.2f} ft")
                print(f"    Categorical Accuracy: {cat_acc*100:.1f}%")
        
        # Get recent forecast details
        cursor.execute("""
            SELECT 
                f.forecast_id,
                f.created_at,
                COUNT(v.id) as validations,
                AVG(v.mae) as avg_mae,
                AVG(v.rmse) as avg_rmse
            FROM forecasts f
            INNER JOIN validations v ON f.forecast_id = v.forecast_id
            WHERE f.created_at >= ?
            GROUP BY f.forecast_id
            ORDER BY f.created_at DESC
            LIMIT 10
        """, (cutoff,))
        
        recent_forecasts = cursor.fetchall()
        
        if recent_forecasts:
            print(f"\nRecent Forecasts:")
            print(f"  {'Forecast ID':<40} {'Date':<20} {'n':<4} {'MAE':<6} {'RMSE':<6}")
            print(f"  {'-'*40} {'-'*20} {'-'*4} {'-'*6} {'-'*6}")
            for forecast_id, created_at, validations, mae, rmse in recent_forecasts:
                # Format timestamp
                if isinstance(created_at, str):
                    dt = datetime.fromisoformat(created_at)
                else:
                    dt = datetime.fromtimestamp(created_at)
                date_str = dt.strftime('%Y-%m-%d %H:%M')
                
                print(f"  {forecast_id:<40} {date_str:<20} {validations:<4} {mae:<6.2f} {rmse:<6.2f}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="SurfCastAI: AI-Powered Oahu Surf Forecasting System")
    parser.add_argument('--config', '-c', help="Path to configuration file")
    
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')
    
    # Run command
    run_parser = subparsers.add_parser('run', help='Run the forecasting pipeline')
    run_parser.add_argument('--mode', '-m', choices=['collect', 'process', 'forecast', 'full'], 
                         default='full', help="Operation mode")
    run_parser.add_argument('--bundle', '-b', help="Specific bundle ID to use")
    
    # List bundles command
    list_parser = subparsers.add_parser('list', help='List available data bundles')
    
    # Bundle info command
    info_parser = subparsers.add_parser('info', help='Show bundle information')
    info_parser.add_argument('--bundle', '-b', help="Specific bundle ID to use")
    
    # Bundle files command
    files_parser = subparsers.add_parser('files', help='List files in a bundle')
    files_parser.add_argument('--bundle', '-b', help="Specific bundle ID to use")
    
    # Validation commands
    validate_parser = subparsers.add_parser('validate', help='Validate a specific forecast')
    validate_parser.add_argument('--forecast', '-f', required=True, help="Forecast ID to validate")
    
    validate_all_parser = subparsers.add_parser('validate-all', help='Validate all pending forecasts')
    validate_all_parser.add_argument('--hours-after', type=int, default=24, 
                                     help="Minimum hours after forecast before validating (default: 24)")
    
    accuracy_report_parser = subparsers.add_parser('accuracy-report', help='Generate accuracy report')
    accuracy_report_parser.add_argument('--days', type=int, default=30, 
                                        help="Number of days to include in report (default: 30)")
    
    # Parse arguments
    args = parser.parse_args()
    
    # Load configuration
    config = load_config(args.config)
    
    # Set up logging
    logger = setup_logging(config)
    
    logger.info(f"Starting SurfCastAI with command: {args.command}")
    
    try:
        # Execute command
        if args.command == 'run':
            # Run the pipeline
            results = asyncio.run(run_pipeline(config, logger, args.mode, args.bundle))
            
            # Print summary
            if 'collection' in results:
                collection = results['collection']
                print("\nData Collection Summary:")
                print(f"  Bundle ID: {collection.get('bundle_id', 'unknown')}")
                stats = collection.get('stats', {})
                print(f"  Total files: {stats.get('total_files', 0)}")
                print(f"  Successful files: {stats.get('successful_files', 0)}")
                print(f"  Failed files: {stats.get('failed_files', 0)}")
            
            if 'processing' in results:
                processing = results['processing']
                print("\nData Processing Summary:")
                print(f"  Status: {processing.get('status', 'unknown')}")
            
            if 'forecast' in results:
                forecast = results['forecast']
                print("\nForecast Generation Summary:")
                print(f"  Status: {forecast.get('status', 'unknown')}")
            
            print("\nSurfCastAI completed successfully!")
            return 0
            
        elif args.command == 'list':
            # List available bundles
            list_bundles(config)
            return 0
            
        elif args.command == 'info':
            # Show bundle information
            bundle_info(config, args.bundle)
            return 0
            
        elif args.command == 'files':
            # List files in a bundle
            bundle_files(config, args.bundle)
            return 0
            
        elif args.command == 'validate':
            # Validate a specific forecast
            asyncio.run(validate_forecast_cmd(config, args.forecast))
            return 0
            
        elif args.command == 'validate-all':
            # Validate all pending forecasts
            asyncio.run(validate_all_forecasts_cmd(config, args.hours_after))
            return 0
            
        elif args.command == 'accuracy-report':
            # Generate accuracy report
            asyncio.run(accuracy_report_cmd(config, args.days))
            return 0
            
        else:
            # No command specified, show help
            parser.print_help()
            return 1
            
    except Exception as e:
        logger.error(f"Error running SurfCastAI: {e}", exc_info=True)
        print(f"\nError: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
