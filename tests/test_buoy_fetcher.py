"""
Unit tests for BuoyDataFetcher.

Tests NDBC data fetching, parsing, rate limiting, and integration with ValidationDatabase.
"""

import asyncio
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock

from src.validation.buoy_fetcher import BuoyDataFetcher
from src.core.http_client import DownloadResult
from src.validation.database import ValidationDatabase


# Sample NDBC data for testing
SAMPLE_NDBC_DATA = """#YY  MM DD hh mm WDIR WSPD GST  WVHT   DPD   APD MWD   PRES  ATMP  WTMP  DEWP  VIS PTDY  TIDE
#yr  mo dy hr mn degT m/s  m/s     m   sec   sec degT   hPa  degC  degC  degC  nmi  hPa    ft
2025 10 04 12 00  310  8.0  9.5  2.13  11.1   8.3 300 1015.2  24.5  25.1  22.3  8.0 -0.3  0.45
2025 10 04 11 30  315  7.5  9.0  2.29  10.8   8.1 305 1015.1  24.6  25.2  22.4  8.1 -0.2  0.48
2025 10 04 11 00  320  7.8  9.2  2.44  10.5   7.9 310 1015.0  24.7  25.3  22.5  8.2 -0.1  0.51
2025 10 04 10 30  318  8.2  9.8  2.59  10.2   7.7 308 1014.9  24.8  25.4  22.6  8.3  0.0  0.54
2025 10 04 10 00  322  8.5 10.1  2.74   9.9   7.5 312 1014.8  24.9  25.5  22.7  8.4  0.1  0.57
2025 10 04 09 30  325  8.8 10.4  2.89   MM    7.3 315 1014.7  25.0  25.6  22.8  8.5  0.2  0.60
2025 10 04 09 00   MM  9.0 10.6  3.05   9.3   7.1  MM 1014.6  25.1  25.7  22.9  8.6  0.3  0.63
"""


class TestBuoyDataFetcher:
    """Test suite for BuoyDataFetcher."""

    @pytest.fixture
    def mock_http_client(self):
        """Create mock HTTP client."""
        client = AsyncMock()
        client.download = AsyncMock()
        return client

    @pytest.fixture
    def fetcher(self, mock_http_client):
        """Create BuoyDataFetcher with mocked HTTP client."""
        return BuoyDataFetcher(http_client=mock_http_client)

    def test_initialization(self):
        """Test BuoyDataFetcher initialization."""
        fetcher = BuoyDataFetcher()

        assert fetcher.timeout == 30
        assert fetcher.RATE_LIMIT == 0.5
        assert fetcher._owns_client is True

    def test_initialization_with_custom_client(self, mock_http_client):
        """Test initialization with custom HTTP client."""
        fetcher = BuoyDataFetcher(http_client=mock_http_client, timeout=60)

        assert fetcher.timeout == 60
        assert fetcher.http_client == mock_http_client
        assert fetcher._owns_client is False

    def test_buoy_mapping(self):
        """Test buoy mapping constants."""
        assert 'north_shore' in BuoyDataFetcher.BUOY_MAPPING
        assert 'south_shore' in BuoyDataFetcher.BUOY_MAPPING
        assert '51001' in BuoyDataFetcher.BUOY_MAPPING['north_shore']
        assert '51101' in BuoyDataFetcher.BUOY_MAPPING['north_shore']
        assert '51003' in BuoyDataFetcher.BUOY_MAPPING['south_shore']
        assert '51004' in BuoyDataFetcher.BUOY_MAPPING['south_shore']

    @pytest.mark.asyncio
    async def test_fetch_observations_invalid_shore(self, fetcher):
        """Test fetch_observations with invalid shore name."""
        start_time = datetime(2025, 10, 4, 0, 0)
        end_time = datetime(2025, 10, 4, 23, 59)

        with pytest.raises(ValueError, match="Invalid shore"):
            await fetcher.fetch_observations('invalid_shore', start_time, end_time)

    @pytest.mark.asyncio
    async def test_fetch_observations_success(self, fetcher, mock_http_client):
        """Test successful observation fetching."""
        start_time = datetime(2025, 10, 4, 9, 0)
        end_time = datetime(2025, 10, 4, 12, 0)

        # Mock successful download
        result = DownloadResult("http://example.com", success=True)
        result.content = SAMPLE_NDBC_DATA.encode('utf-8')
        mock_http_client.download.return_value = result

        observations = await fetcher.fetch_observations(
            'north_shore', start_time, end_time
        )

        # Should have observations from 2 buoys (51001, 51101)
        assert len(observations) > 0
        assert mock_http_client.download.call_count == 2  # Two buoys

        # Check observation structure
        obs = observations[0]
        assert 'buoy_id' in obs
        assert 'observation_time' in obs
        assert 'wave_height' in obs
        assert 'dominant_period' in obs
        assert 'direction' in obs
        assert 'source' in obs
        assert obs['source'] == 'NDBC'

    @pytest.mark.asyncio
    async def test_fetch_observations_with_error(self, fetcher, mock_http_client):
        """Test observation fetching with partial errors."""
        start_time = datetime(2025, 10, 4, 9, 0)
        end_time = datetime(2025, 10, 4, 12, 0)

        # Mock one success and one failure
        success_result = DownloadResult("http://example.com", success=True)
        success_result.content = SAMPLE_NDBC_DATA.encode('utf-8')

        failure_result = DownloadResult("http://example.com", success=False)
        failure_result.error = "Connection timeout"

        mock_http_client.download.side_effect = [success_result, failure_result]

        observations = await fetcher.fetch_observations(
            'north_shore', start_time, end_time
        )

        # Should still have observations from successful buoy
        assert len(observations) > 0

    def test_parse_buoy_data(self, fetcher):
        """Test NDBC data parsing."""
        start_time = datetime(2025, 10, 4, 9, 0)
        end_time = datetime(2025, 10, 4, 12, 0)

        observations = fetcher._parse_buoy_data(
            '51201', SAMPLE_NDBC_DATA, start_time, end_time
        )

        # Should have 7 observations total
        assert len(observations) == 7

        # _parse_buoy_data returns observations in file order (newest first in NDBC files)
        # First observation should be 12:00 (newest)
        obs = observations[0]
        assert obs['buoy_id'] == '51201'
        assert obs['observation_time'] == datetime(2025, 10, 4, 12, 0)
        assert obs['source'] == 'NDBC'

        # Check wave height conversion (meters to feet) for 12:00 observation
        # 2.13m = 6.99 ft
        assert obs['wave_height'] is not None
        expected_ft = 2.13 * 3.28084
        assert abs(obs['wave_height'] - expected_ft) < 0.01

        # Check period and direction for 12:00
        assert obs['dominant_period'] == 11.1
        assert obs['direction'] == 300

        # Check oldest observation (9:00) - should be last in list
        oldest_obs = observations[-1]
        assert oldest_obs['observation_time'] == datetime(2025, 10, 4, 9, 0)
        # 9:00 has wave height 3.05m = 10.0066 ft, period 9.3, direction MM
        assert abs(oldest_obs['wave_height'] - 10.0) < 0.1
        assert oldest_obs['dominant_period'] == 9.3
        assert oldest_obs['direction'] is None  # MM in data

        # Check observation with missing period (9:30)
        obs_with_missing = [o for o in observations if o['observation_time'] == datetime(2025, 10, 4, 9, 30)][0]
        assert obs_with_missing['dominant_period'] is None  # MM in data

    def test_parse_buoy_data_time_filtering(self, fetcher):
        """Test that parsing correctly filters by time range."""
        # Narrow time window
        start_time = datetime(2025, 10, 4, 11, 0)
        end_time = datetime(2025, 10, 4, 11, 30)

        observations = fetcher._parse_buoy_data(
            '51201', SAMPLE_NDBC_DATA, start_time, end_time
        )

        # Should only have observations in the time window
        assert len(observations) == 2
        for obs in observations:
            assert start_time <= obs['observation_time'] <= end_time

    def test_parse_buoy_data_missing_values(self, fetcher):
        """Test handling of MM (missing) values."""
        start_time = datetime(2025, 10, 4, 0, 0)
        end_time = datetime(2025, 10, 4, 23, 59)

        observations = fetcher._parse_buoy_data(
            '51201', SAMPLE_NDBC_DATA, start_time, end_time
        )

        # Find observation with missing period
        obs_missing_period = [
            o for o in observations
            if o['observation_time'] == datetime(2025, 10, 4, 9, 30)
        ][0]
        assert obs_missing_period['dominant_period'] is None

        # Find observation with missing direction
        obs_missing_dir = [
            o for o in observations
            if o['observation_time'] == datetime(2025, 10, 4, 9, 0)
        ][0]
        assert obs_missing_dir['direction'] is None

    def test_parse_buoy_data_empty(self, fetcher):
        """Test parsing empty or malformed data."""
        start_time = datetime(2025, 10, 4, 0, 0)
        end_time = datetime(2025, 10, 4, 23, 59)

        # Empty data
        observations = fetcher._parse_buoy_data('51201', '', start_time, end_time)
        assert len(observations) == 0

        # Only headers
        header_only = """#YY  MM DD hh mm WDIR WSPD GST  WVHT   DPD   APD MWD
#yr  mo dy hr mn degT m/s  m/s     m   sec   sec degT"""
        observations = fetcher._parse_buoy_data('51201', header_only, start_time, end_time)
        assert len(observations) == 0

    def test_parse_buoy_data_units_conversion(self, fetcher):
        """Test proper conversion of units (meters to feet)."""
        start_time = datetime(2025, 10, 4, 0, 0)
        end_time = datetime(2025, 10, 4, 23, 59)

        observations = fetcher._parse_buoy_data(
            '51201', SAMPLE_NDBC_DATA, start_time, end_time
        )

        # Check specific conversion: 2.13m = 6.99 ft
        obs = [o for o in observations if o['observation_time'] == datetime(2025, 10, 4, 12, 0)][0]
        expected_ft = 2.13 * 3.28084
        assert abs(obs['wave_height'] - expected_ft) < 0.01

    @pytest.mark.asyncio
    async def test_rate_limiting(self):
        """Test that rate limiting is applied."""
        # Create fetcher without mock to test rate limiter setup
        fetcher = BuoyDataFetcher()

        # Verify rate limiter configuration
        assert fetcher.http_client.rate_limiter.default_config.requests_per_second == 0.5

        # Clean up
        await fetcher.close()

    @pytest.mark.asyncio
    async def test_context_manager(self, mock_http_client):
        """Test async context manager."""
        async with BuoyDataFetcher(http_client=mock_http_client) as fetcher:
            assert fetcher is not None

    @pytest.mark.asyncio
    async def test_integration_with_database(self, tmp_path):
        """Test integration with ValidationDatabase."""
        # Create temporary database
        db_path = tmp_path / "test_validation.db"
        db = ValidationDatabase(str(db_path))

        # Create mock HTTP client
        mock_client = AsyncMock()
        result = DownloadResult("http://example.com", success=True)
        result.content = SAMPLE_NDBC_DATA.encode('utf-8')
        mock_client.download.return_value = result

        # Fetch observations
        fetcher = BuoyDataFetcher(http_client=mock_client)
        start_time = datetime(2025, 10, 4, 11, 0)
        end_time = datetime(2025, 10, 4, 12, 0)

        observations = await fetcher.fetch_observations(
            'north_shore', start_time, end_time
        )

        # Save to database
        actual_ids = []
        for obs in observations:
            actual_id = db.save_actual(
                buoy_id=obs['buoy_id'],
                observation_time=obs['observation_time'],
                wave_height=obs['wave_height'],
                dominant_period=obs['dominant_period'],
                direction=obs['direction'],
                source=obs['source']
            )
            actual_ids.append(actual_id)

        # Verify saves
        assert len(actual_ids) > 0
        assert all(isinstance(aid, int) for aid in actual_ids)

    def test_url_template(self):
        """Test NDBC URL template formatting."""
        buoy_id = '51201'
        url = BuoyDataFetcher.NDBC_URL_TEMPLATE.format(buoy_id=buoy_id)
        assert url == "https://www.ndbc.noaa.gov/data/realtime2/51201.txt"

    def test_parse_data_accuracy(self, fetcher):
        """Test parsing accuracy (90%+ requirement)."""
        start_time = datetime(2025, 10, 4, 0, 0)
        end_time = datetime(2025, 10, 4, 23, 59)

        observations = fetcher._parse_buoy_data(
            '51201', SAMPLE_NDBC_DATA, start_time, end_time
        )

        # Sample data has 7 data rows
        # All 7 should be parsed (100% success rate)
        total_rows = len(SAMPLE_NDBC_DATA.strip().split('\n')) - 2  # Subtract header rows
        assert total_rows == 7
        assert len(observations) == 7

        # Verify all observations have required fields
        for obs in observations:
            assert obs['buoy_id'] is not None
            assert obs['observation_time'] is not None
            assert obs['wave_height'] is not None  # Required field
            assert obs['source'] == 'NDBC'

        # Calculate accuracy: parsed / total
        accuracy = len(observations) / total_rows
        assert accuracy >= 0.90, f"Parsing accuracy {accuracy:.2%} < 90%"


class TestBuoyDataFetcherLive:
    """
    Live integration tests (requires network access).

    These tests are marked with 'live' and can be skipped in CI/CD.
    Run with: pytest -m live
    """

    @pytest.mark.live
    @pytest.mark.asyncio
    async def test_fetch_real_buoy_data(self):
        """Test fetching real data from NDBC (requires network)."""
        # Use last 24 hours
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=24)

        async with BuoyDataFetcher() as fetcher:
            observations = await fetcher.fetch_observations(
                'north_shore', start_time, end_time
            )

            # Should have at least some observations
            assert len(observations) > 0

            # Verify structure
            for obs in observations:
                assert obs['buoy_id'] in ['51001', '51101']
                assert obs['source'] == 'NDBC'
                assert obs['wave_height'] is not None
                assert start_time <= obs['observation_time'] <= end_time

    @pytest.mark.live
    @pytest.mark.asyncio
    async def test_rate_limit_enforcement(self):
        """Test that rate limiting is enforced on real requests."""
        import time

        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=1)

        async with BuoyDataFetcher() as fetcher:
            start = time.time()

            # Fetch from north shore (2 buoys: 51001, 51101)
            north_obs = await fetcher.fetch_observations(
                'north_shore', start_time, end_time
            )

            elapsed = time.time() - start

            # With 0.5 req/s rate limit, 2 requests should take at least 2 seconds
            # (0, 2 seconds for 2 requests)
            min_expected_time = 2.0
            assert elapsed >= min_expected_time, (
                f"Rate limiting not enforced: {elapsed:.1f}s < {min_expected_time}s"
            )

            # Verify we got some data
            assert len(north_obs) > 0
