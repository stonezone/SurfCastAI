# SurfCastAI Testing Framework

This directory contains tests for the SurfCastAI project, focusing on ensuring proper functionality and performance of all components.

## Test Components

1. **Unit Tests** - Test individual components in isolation
   - Located in `tests/unit/`
   - Organized by module (core, agents, processing, forecast_engine)
   - Run with `python -m unittest discover -s tests`

2. **Integration Tests** - Test interaction between components
   - Located in `tests/integration/` (to be implemented)
   - Run with `python -m unittest discover -s tests/integration`

3. **Forecast Engine Tests** - Comprehensive tests for the forecast generation system
   - Located at project root in `test_forecast_engine.py`
   - Run with `python test_forecast_engine.py`

4. **Benchmarks** - Performance tests to identify bottlenecks
   - Located at project root in `benchmark_forecast_engine.py`
   - Run with `python benchmark_forecast_engine.py`

## Test Configuration

Tests use a separate configuration file:
- Located at `config/test_config.yaml`
- Created automatically by `setup.sh`
- Uses reduced iterations and simplified settings for faster tests

## Running Tests

To run all unit tests:
```bash
python -m unittest discover -s tests
```

To run a specific test module:
```bash
python -m unittest tests.unit.forecast_engine.test_formatter
```

To run the forecast engine test:
```bash
python test_forecast_engine.py
```

To run benchmarks:
```bash
# Run all benchmarks
python benchmark_forecast_engine.py

# Benchmark just the forecast engine
python benchmark_forecast_engine.py --component engine

# Benchmark just the formatter
python benchmark_forecast_engine.py --component formatter

# Run with more iterations
python benchmark_forecast_engine.py --iterations 5
```

## Adding New Tests

1. **Unit Tests**:
   - Create a new file in the appropriate module directory
   - Use the `unittest` framework
   - Follow the naming convention: `test_component_name.py`

2. **Integration Tests**:
   - Create a new file in `tests/integration/`
   - Use the `unittest` framework
   - Focus on testing component interactions

3. **Benchmarks**:
   - Add new benchmark functions to `benchmark_forecast_engine.py`
   - Follow the existing pattern for consistent reporting

## Test Data

Test data is generated programmatically in most cases, using realistic but simplified examples.

For the forecast engine, synthetic swell events and forecast locations are created in `create_test_swell_forecast()` function in `test_forecast_engine.py`.

## Validation

The test framework includes content validation for generated forecasts, ensuring:
- All required sections are present
- Sections have sufficient detail
- Shore-specific information is included
- Directional and timing information is present

Results of validation are logged and can be found in the log files.
