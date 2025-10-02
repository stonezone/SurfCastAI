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
    weather_results = weather_processor.process_bundle(bundle_id, "weather_*.json")
    
    # Process model data
    logger.info("Processing wave model data")
    wave_model_processor = WaveModelProcessor(config)
    model_results = wave_model_processor.process_bundle(bundle_id, "model_*.json")
    
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