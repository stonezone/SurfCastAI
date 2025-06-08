#!/usr/bin/env python3
"""
Benchmark script for the forecast engine.
This script measures the performance of the forecast engine and identifies
potential bottlenecks.
"""

import asyncio
import logging
import sys
import time
import json
import os
from pathlib import Path
import tracemalloc
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from src.core import Config, load_config
from src.forecast_engine import ForecastEngine, ForecastFormatter
from test_forecast_engine import create_test_swell_forecast, setup_logging


async def benchmark_forecast_generation(config, logger, iterations=3):
    """
    Benchmark the forecast generation process.
    
    Args:
        config: Application configuration
        logger: Logger instance
        iterations: Number of iterations to run for benchmarking
        
    Returns:
        Dictionary with benchmark results
    """
    logger.info(f"Starting forecast engine benchmark with {iterations} iterations")
    
    # Create engine
    engine = ForecastEngine(config)
    
    # Create test data
    swell_forecast = create_test_swell_forecast()
    
    # Track metrics
    generation_times = []
    memory_usages = []
    response_lengths = []
    
    # Run benchmark
    for i in range(iterations):
        logger.info(f"Running benchmark iteration {i+1}/{iterations}")
        
        # Start memory tracking
        tracemalloc.start()
        
        # Measure time
        start_time = time.time()
        
        # Generate forecast
        forecast = await engine.generate_forecast(swell_forecast)
        
        # Measure elapsed time
        elapsed_time = time.time() - start_time
        generation_times.append(elapsed_time)
        
        # Get memory usage
        current, peak = tracemalloc.get_traced_memory()
        memory_usages.append(peak / 1024 / 1024)  # Convert to MB
        tracemalloc.stop()
        
        # Check response size
        total_length = sum(len(str(v)) for v in forecast.values())
        response_lengths.append(total_length)
        
        logger.info(f"Iteration {i+1} completed in {elapsed_time:.2f} seconds")
        logger.info(f"Peak memory usage: {peak / 1024 / 1024:.2f} MB")
        logger.info(f"Response size: {total_length} characters")
        
        # Wait between iterations to avoid rate limiting
        if i < iterations - 1:
            await asyncio.sleep(1)
    
    # Calculate statistics
    avg_time = sum(generation_times) / len(generation_times)
    min_time = min(generation_times)
    max_time = max(generation_times)
    
    avg_memory = sum(memory_usages) / len(memory_usages)
    max_memory = max(memory_usages)
    
    avg_length = sum(response_lengths) / len(response_lengths)
    
    # Compile results
    results = {
        "timestamp": datetime.now().isoformat(),
        "iterations": iterations,
        "generation_time": {
            "average": avg_time,
            "min": min_time,
            "max": max_time,
        },
        "memory_usage_mb": {
            "average": avg_memory,
            "max": max_memory,
        },
        "response_size": {
            "average": avg_length,
        },
        "openai_model": config.get('openai', 'model', 'unknown'),
        "refinement_cycles": config.getint('forecast', 'refinement_cycles', 0)
    }
    
    # Log summary
    logger.info(f"Benchmark completed")
    logger.info(f"Average generation time: {avg_time:.2f} seconds")
    logger.info(f"Average memory usage: {avg_memory:.2f} MB")
    logger.info(f"Average response size: {avg_length:.0f} characters")
    
    # Save results to file
    benchmark_dir = Path(config.get('general', 'output_directory', './output')) / "benchmarks"
    benchmark_dir.mkdir(parents=True, exist_ok=True)
    
    result_file = benchmark_dir / f"forecast_benchmark_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(result_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    logger.info(f"Benchmark results saved to {result_file}")
    
    return results


async def benchmark_formatting(config, logger, iterations=3):
    """
    Benchmark the forecast formatting process.
    
    Args:
        config: Application configuration
        logger: Logger instance
        iterations: Number of iterations to run for benchmarking
        
    Returns:
        Dictionary with benchmark results
    """
    logger.info(f"Starting formatter benchmark with {iterations} iterations")
    
    # Create engine and formatter
    engine = ForecastEngine(config)
    formatter = ForecastFormatter(config)
    
    # Create test data
    swell_forecast = create_test_swell_forecast()
    
    # Generate a forecast to format
    logger.info("Generating a forecast for formatting benchmark")
    forecast = await engine.generate_forecast(swell_forecast)
    
    # Track metrics
    format_times = {}
    memory_usages = {}
    
    # Get active formats
    formats = config.get('forecast', 'formats', 'markdown,html,pdf').split(',')
    
    # Run benchmark for each format separately
    for fmt in formats:
        logger.info(f"Benchmarking {fmt} format")
        
        # Set single format for testing
        config._config.set('forecast', 'formats', fmt)
        
        format_times[fmt] = []
        memory_usages[fmt] = []
        
        for i in range(iterations):
            # Start memory tracking
            tracemalloc.start()
            
            # Measure time
            start_time = time.time()
            
            # Format forecast
            formatted = formatter.format_forecast(forecast)
            
            # Measure elapsed time
            elapsed_time = time.time() - start_time
            format_times[fmt].append(elapsed_time)
            
            # Get memory usage
            current, peak = tracemalloc.get_traced_memory()
            memory_usages[fmt].append(peak / 1024 / 1024)  # Convert to MB
            tracemalloc.stop()
            
            logger.info(f"Iteration {i+1} completed in {elapsed_time:.2f} seconds")
            logger.info(f"Peak memory usage: {peak / 1024 / 1024:.2f} MB")
            
            # Wait between iterations
            if i < iterations - 1:
                await asyncio.sleep(0.5)
    
    # Restore original formats
    config._config.set('forecast', 'formats', ','.join(formats))
    
    # Calculate statistics
    results = {
        "timestamp": datetime.now().isoformat(),
        "iterations": iterations,
    }
    
    for fmt in formats:
        avg_time = sum(format_times[fmt]) / len(format_times[fmt])
        min_time = min(format_times[fmt])
        max_time = max(format_times[fmt])
        
        avg_memory = sum(memory_usages[fmt]) / len(memory_usages[fmt])
        max_memory = max(memory_usages[fmt])
        
        results[fmt] = {
            "time_seconds": {
                "average": avg_time,
                "min": min_time,
                "max": max_time,
            },
            "memory_usage_mb": {
                "average": avg_memory,
                "max": max_memory,
            }
        }
        
        logger.info(f"{fmt} format - Average time: {avg_time:.2f} seconds, Average memory: {avg_memory:.2f} MB")
    
    # Save results to file
    benchmark_dir = Path(config.get('general', 'output_directory', './output')) / "benchmarks"
    benchmark_dir.mkdir(parents=True, exist_ok=True)
    
    result_file = benchmark_dir / f"formatter_benchmark_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(result_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    logger.info(f"Benchmark results saved to {result_file}")
    
    return results


async def main():
    """Main function."""
    # Load configuration
    config = load_config()
    
    # Set up logging
    logger = setup_logging(config)
    
    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser(description="Benchmark the SurfCastAI forecast engine.")
    parser.add_argument('--component', '-c', choices=['engine', 'formatter', 'both'], default='both',
                      help="Component to benchmark")
    parser.add_argument('--iterations', '-i', type=int, default=3,
                      help="Number of iterations for benchmark")
    
    args = parser.parse_args()
    
    try:
        # Run benchmarks
        if args.component in ['engine', 'both']:
            await benchmark_forecast_generation(config, logger, args.iterations)
        
        if args.component in ['formatter', 'both']:
            await benchmark_formatting(config, logger, args.iterations)
        
        logger.info("Benchmarks completed successfully")
        return 0
        
    except Exception as e:
        logger.error(f"Error running benchmarks: {e}")
        logger.error(traceback.format_exc())
        return 1


if __name__ == "__main__":
    asyncio.run(main())