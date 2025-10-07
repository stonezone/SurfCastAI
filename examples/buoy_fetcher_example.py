#!/usr/bin/env python3
"""
Example usage of BuoyDataFetcher for validation.

Demonstrates:
1. Fetching buoy observations from NDBC
2. Saving observations to ValidationDatabase
3. Handling errors and missing data
4. Rate limiting and async operations
"""

import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from validation.buoy_fetcher import BuoyDataFetcher
from validation.database import ValidationDatabase


async def fetch_and_save_observations():
    """Fetch buoy observations and save to database."""

    # Define time range (last 24 hours)
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(hours=24)

    print(f"Fetching buoy observations from {start_time} to {end_time}")
    print(f"Time range: {(end_time - start_time).total_seconds() / 3600:.1f} hours")

    # Initialize database
    db = ValidationDatabase("data/validation.db")
    print(f"\nInitialized validation database")

    # Fetch observations for both shores
    async with BuoyDataFetcher() as fetcher:
        print("\n" + "="*60)
        print("NORTH SHORE OBSERVATIONS")
        print("="*60)

        north_obs = await fetcher.fetch_observations(
            'north_shore', start_time, end_time
        )

        print(f"\nFetched {len(north_obs)} observations from North Shore buoys")
        print(f"Buoys: {set(o['buoy_id'] for o in north_obs)}")

        # Display sample observations
        if north_obs:
            print(f"\nSample observations (first 3):")
            for obs in north_obs[:3]:
                print(f"  {obs['buoy_id']} @ {obs['observation_time']}: "
                      f"{obs['wave_height']:.1f}ft @ {obs['dominant_period']}s "
                      f"from {obs['direction']}°" if obs['direction'] else "N/A")

        # Save to database
        saved_count = 0
        for obs in north_obs:
            try:
                db.save_actual(
                    buoy_id=obs['buoy_id'],
                    observation_time=obs['observation_time'],
                    wave_height=obs['wave_height'],
                    dominant_period=obs['dominant_period'],
                    direction=obs['direction'],
                    source=obs['source']
                )
                saved_count += 1
            except Exception as e:
                print(f"Error saving observation: {e}")

        print(f"\nSaved {saved_count} North Shore observations to database")

        print("\n" + "="*60)
        print("SOUTH SHORE OBSERVATIONS")
        print("="*60)

        south_obs = await fetcher.fetch_observations(
            'south_shore', start_time, end_time
        )

        print(f"\nFetched {len(south_obs)} observations from South Shore buoys")
        print(f"Buoys: {set(o['buoy_id'] for o in south_obs)}")

        # Display sample observations
        if south_obs:
            print(f"\nSample observations (first 3):")
            for obs in south_obs[:3]:
                print(f"  {obs['buoy_id']} @ {obs['observation_time']}: "
                      f"{obs['wave_height']:.1f}ft @ {obs['dominant_period']}s "
                      f"from {obs['direction']}°" if obs['direction'] else "N/A")

        # Save to database
        saved_count = 0
        for obs in south_obs:
            try:
                db.save_actual(
                    buoy_id=obs['buoy_id'],
                    observation_time=obs['observation_time'],
                    wave_height=obs['wave_height'],
                    dominant_period=obs['dominant_period'],
                    direction=obs['direction'],
                    source=obs['source']
                )
                saved_count += 1
            except Exception as e:
                print(f"Error saving observation: {e}")

        print(f"\nSaved {saved_count} South Shore observations to database")

    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    total_obs = len(north_obs) + len(south_obs)
    print(f"Total observations fetched: {total_obs}")
    print(f"  North Shore: {len(north_obs)}")
    print(f"  South Shore: {len(south_obs)}")
    print(f"\nData saved to: {db.db_path}")


async def demonstrate_error_handling():
    """Demonstrate error handling for invalid inputs."""

    print("\n" + "="*60)
    print("ERROR HANDLING DEMONSTRATION")
    print("="*60)

    async with BuoyDataFetcher() as fetcher:
        # Test invalid shore name
        print("\n1. Testing invalid shore name...")
        try:
            await fetcher.fetch_observations(
                'invalid_shore',
                datetime.utcnow() - timedelta(hours=1),
                datetime.utcnow()
            )
        except ValueError as e:
            print(f"   Caught expected error: {e}")

        # Test narrow time window with no data
        print("\n2. Testing empty time window...")
        empty_start = datetime(2020, 1, 1, 0, 0)
        empty_end = datetime(2020, 1, 1, 0, 1)
        obs = await fetcher.fetch_observations(
            'north_shore', empty_start, empty_end
        )
        print(f"   No observations in old time range: {len(obs)} results")


if __name__ == '__main__':
    print("BuoyDataFetcher Example")
    print("=" * 60)
    print("This example demonstrates fetching NDBC buoy observations")
    print("for forecast validation.")
    print("=" * 60)

    # Run main example
    asyncio.run(fetch_and_save_observations())

    # Run error handling demo
    asyncio.run(demonstrate_error_handling())

    print("\n" + "="*60)
    print("Example complete!")
    print("="*60)
