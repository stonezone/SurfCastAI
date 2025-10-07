"""
Buoy data fetcher for validation against NDBC real-time observations.

Fetches actual wave observations from NDBC buoys to validate forecast accuracy.
Uses async HTTP requests with proper rate limiting and error handling.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from urllib.parse import urlparse

import aiohttp

from ..core.http_client import HTTPClient
from ..core.rate_limiter import RateLimiter, RateLimitConfig


logger = logging.getLogger(__name__)


class BuoyDataFetcher:
    """
    Fetches real-time buoy observations from NDBC for forecast validation.

    Buoy mappings:
    - North Shore: 51001 (NW Hawaii), 51101 (NW Molokai)
    - South Shore: 51003 (SE Hawaii), 51004 (SE Hawaii)

    Data source: NDBC real-time2 text files
    Format: Space-delimited with header rows
    Rate limit: 0.5 requests/second (NDBC courtesy limit)
    """

    # Buoy IDs mapped to shores
    BUOY_MAPPING = {
        'north_shore': ['51001', '51101'],  # NW Hawaii, NW Molokai
        'south_shore': ['51003', '51004']    # SE Hawaii buoys
    }

    # NDBC data URL template
    NDBC_URL_TEMPLATE = "https://www.ndbc.noaa.gov/data/realtime2/{buoy_id}.txt"

    # Rate limit: 0.5 requests/second as per NDBC courtesy
    RATE_LIMIT = 0.5  # requests per second

    def __init__(
        self,
        http_client: Optional[HTTPClient] = None,
        rate_limiter: Optional[RateLimiter] = None,
        timeout: int = 30
    ):
        """
        Initialize buoy data fetcher.

        Args:
            http_client: Optional HTTPClient instance (will create if None)
            rate_limiter: Optional RateLimiter instance (will create if None)
            timeout: Request timeout in seconds
        """
        self.timeout = timeout

        # Create rate limiter with NDBC-specific limits
        if rate_limiter is None:
            rate_limiter = RateLimiter(
                default_config=RateLimitConfig(
                    requests_per_second=self.RATE_LIMIT,
                    burst_size=2  # Small burst for efficiency
                )
            )

        # Create HTTP client if not provided
        if http_client is None:
            self.http_client = HTTPClient(
                rate_limiter=rate_limiter,
                timeout=timeout,
                max_concurrent=5,
                user_agent="SurfCastAI-Validation/1.0"
            )
            self._owns_client = True
        else:
            self.http_client = http_client
            self._owns_client = False

    async def fetch_observations(
        self,
        shore: str,
        start_time: datetime,
        end_time: datetime
    ) -> List[Dict]:
        """
        Fetch buoy observations for a specific shore and time range.

        Args:
            shore: Shore name ('north_shore' or 'south_shore')
            start_time: Start of time range (inclusive)
            end_time: End of time range (inclusive)

        Returns:
            List of observation dictionaries with keys:
                - buoy_id: Buoy identifier
                - observation_time: Time of observation
                - wave_height: Wave height in feet
                - dominant_period: Dominant wave period in seconds
                - direction: Wave direction in degrees
                - source: Data source ('NDBC')

        Raises:
            ValueError: If shore name is invalid
        """
        # Validate shore name
        if shore not in self.BUOY_MAPPING:
            raise ValueError(
                f"Invalid shore '{shore}'. "
                f"Must be one of: {list(self.BUOY_MAPPING.keys())}"
            )

        # Get buoy IDs for this shore
        buoy_ids = self.BUOY_MAPPING[shore]

        logger.info(
            f"Fetching buoy data for {shore} "
            f"from {start_time.isoformat()} to {end_time.isoformat()}"
        )

        # Fetch data from all buoys for this shore
        tasks = [
            self._fetch_buoy_data(buoy_id, start_time, end_time)
            for buoy_id in buoy_ids
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Flatten results and filter out errors
        all_observations = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(
                    f"Error fetching buoy {buoy_ids[i]}: {result}"
                )
                continue
            all_observations.extend(result)

        # Sort by observation time
        all_observations.sort(key=lambda x: x['observation_time'])

        logger.info(
            f"Fetched {len(all_observations)} observations for {shore} "
            f"from {len(buoy_ids)} buoys"
        )

        return all_observations

    async def _fetch_buoy_data(
        self,
        buoy_id: str,
        start_time: datetime,
        end_time: datetime
    ) -> List[Dict]:
        """
        Fetch and parse data from a single buoy.

        Args:
            buoy_id: NDBC buoy identifier (e.g., '51201')
            start_time: Start of time range
            end_time: End of time range

        Returns:
            List of observation dictionaries
        """
        url = self.NDBC_URL_TEMPLATE.format(buoy_id=buoy_id)

        logger.debug(f"Fetching data from buoy {buoy_id}: {url}")

        try:
            # Download buoy data using HTTPClient
            result = await self.http_client.download(url, save_to_disk=False)

            if not result.success:
                logger.warning(
                    f"Failed to fetch buoy {buoy_id}: {result.error}"
                )
                return []

            # Decode content
            text = result.content.decode('utf-8', errors='replace')

            # Parse buoy data
            observations = self._parse_buoy_data(
                buoy_id, text, start_time, end_time
            )

            logger.debug(
                f"Parsed {len(observations)} observations from buoy {buoy_id}"
            )

            return observations

        except Exception as e:
            logger.error(f"Error fetching buoy {buoy_id}: {e}", exc_info=True)
            return []

    def _parse_buoy_data(
        self,
        buoy_id: str,
        text: str,
        start_time: datetime,
        end_time: datetime
    ) -> List[Dict]:
        """
        Parse NDBC text format into observation dictionaries.

        NDBC format:
        - Line 1: Column names (e.g., YY MM DD hh mm WDIR WSPD GST WVHT DPD APD MWD...)
        - Line 2: Units (e.g., yr mo dy hr mn degT m/s m/s m sec sec degT...)
        - Lines 3+: Data rows (space-delimited, 'MM' for missing values)

        Columns we need:
        - Columns 0-4: YY MM DD hh mm (timestamp)
        - Column 8: WVHT (significant wave height in meters)
        - Column 9: DPD (dominant wave period in seconds)
        - Column 11: MWD (mean wave direction in degrees)

        Args:
            buoy_id: Buoy identifier
            text: Raw NDBC text data
            start_time: Filter observations after this time
            end_time: Filter observations before this time

        Returns:
            List of parsed observation dictionaries
        """
        observations = []
        lines = text.strip().split('\n')

        if len(lines) < 3:
            logger.warning(f"Insufficient data from buoy {buoy_id}")
            return observations

        # Parse header to find column indices
        header = lines[0].split()
        units_line = lines[1].split()

        # Log header for debugging
        logger.debug(f"Buoy {buoy_id} header: {header}")

        # Find column indices (with fallback defaults)
        try:
            wvht_idx = header.index('WVHT') if 'WVHT' in header else 8
            dpd_idx = header.index('DPD') if 'DPD' in header else 9
            mwd_idx = header.index('MWD') if 'MWD' in header else 11
        except ValueError as e:
            logger.warning(
                f"Column not found in buoy {buoy_id} header: {e}. "
                f"Using default indices."
            )
            wvht_idx, dpd_idx, mwd_idx = 8, 9, 11

        # Parse data rows (skip header rows)
        for line_num, line in enumerate(lines[2:], start=3):
            try:
                # Split on whitespace
                fields = line.split()

                # Ensure we have enough fields
                min_fields = max(wvht_idx, dpd_idx, mwd_idx) + 1
                if len(fields) < min_fields:
                    logger.debug(
                        f"Buoy {buoy_id} line {line_num}: "
                        f"insufficient fields ({len(fields)} < {min_fields})"
                    )
                    continue

                # Parse timestamp (fields 0-4: YY MM DD hh mm)
                year = int(fields[0])
                month = int(fields[1])
                day = int(fields[2])
                hour = int(fields[3])
                minute = int(fields[4])

                # Handle 2-digit vs 4-digit year
                if year < 100:
                    year += 2000

                observation_time = datetime(year, month, day, hour, minute)

                # Filter by time range
                if observation_time < start_time or observation_time > end_time:
                    continue

                # Parse wave parameters (handle 'MM' for missing)
                wave_height_m = fields[wvht_idx]
                dominant_period = fields[dpd_idx]
                direction = fields[mwd_idx]

                # Convert missing values to None
                wave_height_m = None if wave_height_m == 'MM' else float(wave_height_m)
                dominant_period = None if dominant_period == 'MM' else float(dominant_period)
                direction = None if direction == 'MM' else float(direction)

                # Convert wave height from meters to feet
                wave_height_ft = wave_height_m * 3.28084 if wave_height_m else None

                # Skip observation if critical fields are missing
                if wave_height_ft is None:
                    logger.debug(
                        f"Buoy {buoy_id} at {observation_time}: "
                        f"missing wave height, skipping"
                    )
                    continue

                # Create observation dictionary
                observation = {
                    'buoy_id': buoy_id,
                    'observation_time': observation_time,
                    'wave_height': wave_height_ft,
                    'dominant_period': dominant_period,
                    'direction': direction,
                    'source': 'NDBC'
                }

                observations.append(observation)

            except (ValueError, IndexError) as e:
                logger.debug(
                    f"Buoy {buoy_id} line {line_num}: "
                    f"parse error: {e}"
                )
                continue

        logger.info(
            f"Parsed {len(observations)} valid observations from buoy {buoy_id} "
            f"in time range {start_time.isoformat()} to {end_time.isoformat()}"
        )

        return observations

    async def close(self):
        """Close HTTP client if we own it."""
        if self._owns_client:
            await self.http_client.close()

    async def __aenter__(self):
        """Context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        await self.close()
