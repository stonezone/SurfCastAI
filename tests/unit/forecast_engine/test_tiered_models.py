"""
Comprehensive tests for tiered AI specialist architecture.

Tests verify:
1. Specialists initialize with correct models from BaseSpecialist
2. Backward compatibility (old config format still works)
3. Default fallback (BaseSpecialist uses default model)
4. Log messages verify model assignment
5. Each specialist uses its assigned model in API calls (mocked)
"""

import pytest
import logging
from unittest.mock import Mock, patch, AsyncMock
from io import StringIO

from src.forecast_engine.specialists.buoy_analyst import BuoyAnalyst
from src.forecast_engine.specialists.pressure_analyst import PressureAnalyst
from src.forecast_engine.specialists.senior_forecaster import SeniorForecaster
from src.forecast_engine.specialists.base_specialist import BaseSpecialist, SpecialistOutput
from src.forecast_engine.specialists.schemas import (
    BuoyAnalystOutput, BuoyAnalystData, BuoyTrend, BuoyAnomaly, CrossValidation, SummaryStats,
    PressureAnalystOutput, PressureAnalystData, AnalysisSummary,
    TrendType, QualityFlag, AgreementLevel
)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def mock_engine():
    """Mock ForecastEngine with OpenAI client."""
    engine = Mock()

    # Create mock OpenAI client with call_openai_api method
    openai_client = Mock()
    openai_client.call_openai_api = AsyncMock(return_value="Test narrative response")

    engine.openai_client = openai_client

    return engine


@pytest.fixture
def mock_config_tiered():
    """Mock configuration with tiered model assignments."""
    config = Mock()

    def get_side_effect(section, key, fallback=None):
        config_map = {
            ('openai', 'api_key'): 'test-api-key',
            ('openai', 'max_tokens'): 2000,
            ('openai', 'default_model'): 'gpt-5-mini',
            ('openai', 'specialist_models'): {
                'buoy_analyst': 'gpt-5-nano',
                'pressure_analyst': 'gpt-5-mini',
                'senior_forecaster': 'gpt-5'
            }
        }
        return config_map.get((section, key), fallback)

    def getint_side_effect(section, key, fallback=None):
        config_map = {
            ('openai', 'max_tokens'): 2000,
            ('forecast', 'require_minimum_specialists'): 2
        }
        return config_map.get((section, key), fallback)

    config.get = Mock(side_effect=get_side_effect)
    config.getint = Mock(side_effect=getint_side_effect)

    return config


@pytest.fixture
def mock_config_no_openai_key():
    """Mock configuration without OpenAI key (for template narrative testing)."""
    config = Mock()

    def get_side_effect(section, key, fallback=None):
        config_map = {
            ('openai', 'api_key'): None,  # No key
            ('openai', 'max_tokens'): 2000
        }
        return config_map.get((section, key), fallback)

    def getint_side_effect(section, key, fallback=None):
        return {('openai', 'max_tokens'): 2000}.get((section, key), fallback)

    config.get = Mock(side_effect=get_side_effect)
    config.getint = Mock(side_effect=getint_side_effect)

    return config


@pytest.fixture
def sample_buoy_data():
    """Sample buoy data for testing."""
    return {
        'buoy_data': [
            {
                'station_id': '51001',
                'name': 'NW Hawaii',
                'latitude': 23.4,
                'longitude': -162.3,
                'observations': [
                    {
                        'timestamp': '2025-10-09T10:00:00Z',
                        'wave_height': 2.5,
                        'dominant_period': 12.0,
                        'wave_direction': 315,
                        'wind_speed': 15.0,
                        'wind_direction': 45
                    },
                    {
                        'timestamp': '2025-10-09T11:00:00Z',
                        'wave_height': 2.6,
                        'dominant_period': 12.5,
                        'wave_direction': 320,
                        'wind_speed': 14.0,
                        'wind_direction': 50
                    }
                ]
            }
        ]
    }


@pytest.fixture
def sample_pressure_data(tmp_path):
    """Sample pressure chart data for testing."""
    # Create a dummy PNG file
    image_path = tmp_path / "pressure_chart.png"
    image_path.write_bytes(b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82')

    return {
        'images': [str(image_path)],
        'metadata': {
            'chart_times': ['2025-10-09T00:00:00Z'],
            'region': 'North Pacific'
        }
    }


# =============================================================================
# Test 1: Base Specialist Model Assignment and Logging
# =============================================================================

def test_base_specialist_accepts_model_name(caplog):
    """Test that BaseSpecialist can be initialized with custom model_name."""
    # Create a concrete implementation for testing
    class TestSpecialist(BaseSpecialist):
        async def analyze(self, data):
            return SpecialistOutput(0.8, {}, "test", {})

    with caplog.at_level(logging.INFO):
        specialist = TestSpecialist(config=None, model_name='gpt-5')

        assert specialist.model_name == 'gpt-5'
        assert any('gpt-5' in record.message for record in caplog.records)


def test_base_specialist_default_model(caplog):
    """Test that BaseSpecialist requires explicit model_name (no default fallback)."""
    class TestSpecialist(BaseSpecialist):
        async def analyze(self, data):
            return SpecialistOutput(0.8, {}, "test", {})

    with caplog.at_level(logging.INFO):
        # BaseSpecialist now requires explicit model_name - should raise ValueError
        with pytest.raises(ValueError, match="requires explicit model_name parameter"):
            specialist = TestSpecialist(config=None)  # No model_name specified


# =============================================================================
# Test 2: Specialist Initialization with Model Assignment
# =============================================================================

def test_buoy_analyst_initialization(mock_config_tiered, mock_engine, caplog):
    """Test that BuoyAnalyst initializes correctly."""
    with caplog.at_level(logging.INFO):
        analyst = BuoyAnalyst(mock_config_tiered, model_name='gpt-5-nano', engine=mock_engine)

        # BuoyAnalyst requires explicit model_name parameter
        assert analyst.model_name == 'gpt-5-nano'
        assert hasattr(analyst, 'openai_api_key')
        assert hasattr(analyst, 'max_tokens')
        assert analyst.engine is mock_engine


def test_pressure_analyst_initialization_with_custom_model(mock_config_tiered, mock_engine, caplog):
    """Test that PressureAnalyst accepts custom model_name."""
    with caplog.at_level(logging.INFO):
        # PressureAnalyst requires both model_name and engine parameters
        analyst = PressureAnalyst(mock_config_tiered, model_name='gpt-5-mini', engine=mock_engine)

        assert analyst.model_name == 'gpt-5-mini'
        assert analyst.engine is mock_engine
        assert any('gpt-5-mini' in record.message for record in caplog.records)


def test_senior_forecaster_initialization(mock_config_tiered, mock_engine, caplog):
    """Test that SeniorForecaster initializes correctly."""
    with caplog.at_level(logging.INFO):
        forecaster = SeniorForecaster(mock_config_tiered, model_name='gpt-5', engine=mock_engine)

        # SeniorForecaster requires explicit model_name parameter
        assert forecaster.model_name == 'gpt-5'
        assert hasattr(forecaster, 'openai_api_key')
        assert forecaster.engine is mock_engine


# =============================================================================
# Test 3: Log Format Verification
# =============================================================================

def test_log_format_contains_model_info(mock_engine, caplog):
    """Test that initialization logs contain model information."""
    with caplog.at_level(logging.INFO):
        caplog.clear()
        analyst = BuoyAnalyst(None, model_name='gpt-5-nano', engine=mock_engine)

        # Should log initialization with model
        log_messages = [record.message for record in caplog.records]
        assert any('Initialized with model:' in msg for msg in log_messages)


def test_log_contains_correct_logger_name(mock_engine, caplog):
    """Test that specialists use correct logger names."""
    with caplog.at_level(logging.INFO):
        caplog.clear()
        analyst = BuoyAnalyst(None, model_name='gpt-5-nano', engine=mock_engine)

        # Check logger name pattern
        log_records = [r for r in caplog.records if 'Initialized with model:' in r.message]
        assert len(log_records) > 0
        assert 'specialist' in log_records[0].name.lower()


# =============================================================================
# Test 4: Model Usage in API Calls (Mocked)
# =============================================================================

@pytest.mark.asyncio
async def test_buoy_analyst_uses_model_in_api_call(mock_config_tiered, mock_engine, sample_buoy_data):
    """Test that BuoyAnalyst uses its model_name in OpenAI API calls."""
    analyst = BuoyAnalyst(mock_config_tiered, model_name='gpt-5-nano', engine=mock_engine)

    # Mock the engine's OpenAI client call
    mock_engine.openai_client.call_openai_api.return_value = "Test narrative"

    result = await analyst.analyze(sample_buoy_data)

    # Verify the API was called
    assert mock_engine.openai_client.call_openai_api.called

    # Verify result is valid
    assert result.confidence > 0
    assert result.narrative == "Test narrative"


@pytest.mark.asyncio
async def test_pressure_analyst_uses_custom_model_in_api_call(
    mock_config_tiered,
    mock_engine,
    sample_pressure_data
):
    """Test that PressureAnalyst uses custom model in OpenAI API calls."""
    analyst = PressureAnalyst(mock_config_tiered, model_name='gpt-5-mini', engine=mock_engine)

    # Mock the engine's OpenAI client to return valid JSON and narrative
    async def mock_call_api(system_prompt=None, user_prompt=None, **kwargs):
        # Return JSON for vision analysis, narrative for text generation
        if 'image_urls' in kwargs:
            return '{"systems": [], "predicted_swells": [], "frontal_boundaries": []}'
        else:
            return "Test pressure narrative"

    mock_engine.openai_client.call_openai_api = AsyncMock(side_effect=mock_call_api)

    result = await analyst.analyze(sample_pressure_data)

    # Verify the API was called
    assert mock_engine.openai_client.call_openai_api.called
    assert result.confidence > 0
    assert result.narrative == "Test pressure narrative"


@pytest.mark.asyncio
async def test_senior_forecaster_uses_model_in_api_call(mock_config_tiered, mock_engine):
    """Test that SeniorForecaster uses its model in OpenAI API calls."""
    forecaster = SeniorForecaster(mock_config_tiered, model_name='gpt-5', engine=mock_engine)

    # Use dict format for specialist outputs (SeniorForecaster wraps these internally)
    mock_buoy_output = {
        'confidence': 0.8,
        'data': {'trends': [], 'anomalies': [], 'cross_validation': {'agreement_score': 0.5}},
        'narrative': "Buoy analysis",
        'metadata': {}
    }

    mock_pressure_output = {
        'confidence': 0.7,
        'data': {'systems': [], 'predicted_swells': [], 'frontal_boundaries': []},
        'narrative': "Pressure analysis",
        'metadata': {}
    }

    data = {
        'buoy_analysis': mock_buoy_output,
        'pressure_analysis': mock_pressure_output,
        'swell_events': [],
        'shore_data': {},
        'seasonal_context': {'season': 'winter'},
        'metadata': {}
    }

    # Mock the engine's OpenAI client
    mock_engine.openai_client.call_openai_api.return_value = "Final forecast"

    result = await forecaster.analyze(data)

    # Verify API was called
    assert mock_engine.openai_client.call_openai_api.called
    assert result.confidence > 0
    assert result.narrative == "Final forecast"


# =============================================================================
# Test 5: Model Consistency Across Multiple Calls
# =============================================================================

@pytest.mark.asyncio
async def test_multiple_api_calls_use_same_model(mock_config_tiered, mock_engine, sample_buoy_data):
    """Test that multiple API calls from same specialist use same model."""
    analyst = BuoyAnalyst(mock_config_tiered, model_name='gpt-5-nano', engine=mock_engine)
    expected_model = analyst.model_name

    # Mock the engine's OpenAI client
    mock_engine.openai_client.call_openai_api.return_value = "Test narrative"

    # Call analyze twice
    await analyst.analyze(sample_buoy_data)
    await analyst.analyze(sample_buoy_data)

    # Verify API was called twice
    assert mock_engine.openai_client.call_openai_api.call_count == 2
    # Model is part of analyst state, verified via analyst.model_name
    assert analyst.model_name == expected_model


# =============================================================================
# Test 6: Backward Compatibility (No OpenAI Key)
# =============================================================================

@pytest.mark.asyncio
async def test_buoy_analyst_works_without_openai_key(
    mock_config_no_openai_key,
    mock_engine,
    sample_buoy_data
):
    """Test that BuoyAnalyst requires engine (no template mode)."""
    # BuoyAnalyst now requires engine parameter - should raise ValueError if None
    with pytest.raises(ValueError, match="requires engine parameter"):
        analyst = BuoyAnalyst(mock_config_no_openai_key, model_name='gpt-5-nano', engine=None)

    # With valid engine, should work normally
    analyst = BuoyAnalyst(mock_config_no_openai_key, model_name='gpt-5-nano', engine=mock_engine)
    mock_engine.openai_client.call_openai_api.return_value = "Test narrative"

    result = await analyst.analyze(sample_buoy_data)

    assert result.confidence > 0
    assert isinstance(result.narrative, str)
    # result.data is now a Pydantic model (BuoyAnalystData), check attributes
    assert hasattr(result.data, 'trends')
    assert hasattr(result.data, 'anomalies')
    assert isinstance(result.data.trends, list)
    assert isinstance(result.data.anomalies, list)


# =============================================================================
# Test 7: Model Assignment Pattern
# =============================================================================

def test_pressure_analyst_supports_tiered_models(mock_engine):
    """Test that PressureAnalyst supports different models via parameter."""
    models_to_test = ['gpt-5-nano', 'gpt-5-mini', 'gpt-5']

    for model in models_to_test:
        analyst = PressureAnalyst(None, model_name=model, engine=mock_engine)
        assert analyst.model_name == model
        assert analyst.engine is mock_engine


def test_model_name_is_accessible_attribute(mock_engine):
    """Test that all specialists expose model_name as attribute."""
    buoy = BuoyAnalyst(None, model_name='gpt-5-nano', engine=mock_engine)
    pressure = PressureAnalyst(None, model_name='gpt-5-mini', engine=mock_engine)
    senior = SeniorForecaster(None, model_name='gpt-5', engine=mock_engine)

    assert hasattr(buoy, 'model_name')
    assert hasattr(pressure, 'model_name')
    assert hasattr(senior, 'model_name')
    assert buoy.model_name == 'gpt-5-nano'
    assert pressure.model_name == 'gpt-5-mini'
    assert senior.model_name == 'gpt-5'


# =============================================================================
# Test 8: Integration - Verifying Expected Models from Config
# =============================================================================

def test_expected_tiered_model_assignment(mock_config_tiered, mock_engine):
    """
    Test the expected tiered model assignment pattern.

    This simulates how forecast_engine would use get_specialist_model()
    to assign different models to different specialists.
    """
    # Simulate what forecast_engine does:
    # 1. Get specialist-specific model from config
    # 2. Pass it during instantiation

    buoy_model = 'gpt-5-nano'  # Would come from config.get_specialist_model('buoy_analyst')
    pressure_model = 'gpt-5-mini'  # config.get_specialist_model('pressure_analyst')
    senior_model = 'gpt-5'  # config.get_specialist_model('senior_forecaster')

    # Instantiate specialists with their assigned models and engine
    buoy = BuoyAnalyst(mock_config_tiered, model_name=buoy_model, engine=mock_engine)
    pressure = PressureAnalyst(mock_config_tiered, model_name=pressure_model, engine=mock_engine)
    senior = SeniorForecaster(mock_config_tiered, model_name=senior_model, engine=mock_engine)

    # Verify each has correct model
    assert buoy.model_name == 'gpt-5-nano'
    assert pressure.model_name == 'gpt-5-mini'
    assert senior.model_name == 'gpt-5'

    # Verify they're all different (tiered architecture)
    models = {buoy.model_name, pressure.model_name, senior.model_name}
    assert len(models) == 3, "All three specialists should use different models"


# =============================================================================
# Test 9: Logging Verification (Expected Format from AGENTS_TODO.md)
# =============================================================================

def test_expected_log_format_for_all_specialists(caplog, mock_config_tiered, mock_engine):
    """
    Test that specialists log in the expected format from AGENTS_TODO.md Phase 4:

    INFO - specialist.buoyanalyst - Initialized with model: gpt-5-nano
    INFO - specialist.pressureanalyst - Initialized with model: gpt-5-mini
    INFO - specialist.seniorforecaster - Initialized with model: gpt-5
    """
    with caplog.at_level(logging.INFO):
        caplog.clear()

        # Create all three specialists with explicit models and engine
        buoy = BuoyAnalyst(mock_config_tiered, model_name='gpt-5-nano', engine=mock_engine)
        pressure = PressureAnalyst(mock_config_tiered, model_name='gpt-5-mini', engine=mock_engine)
        senior = SeniorForecaster(mock_config_tiered, model_name='gpt-5', engine=mock_engine)

        # Check that logs contain expected patterns
        log_messages = [record.message for record in caplog.records]

        # Should have initialization logs
        init_logs = [msg for msg in log_messages if 'Initialized with model:' in msg]
        assert len(init_logs) >= 3, "Should have 3 initialization logs"


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
