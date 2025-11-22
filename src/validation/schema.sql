-- SurfCastAI Validation Database Schema
-- Stores forecast metadata, predictions, actual observations, and validation results

-- Enable Write-Ahead Logging for better concurrency
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- Forecast metadata table
-- Timestamp format: ISO 8601 without microseconds or timezone (YYYY-MM-DD HH:MM:SS)
-- Example: '2025-10-11 12:00:00'
CREATE TABLE IF NOT EXISTS forecasts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    forecast_id TEXT UNIQUE NOT NULL,
    created_at TEXT NOT NULL CHECK (created_at GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9] [0-9][0-9]:[0-9][0-9]:[0-9][0-9]'),
    bundle_id TEXT,
    model_version TEXT NOT NULL,
    total_tokens INTEGER,
    input_tokens INTEGER,
    output_tokens INTEGER,
    model_cost_usd REAL,
    generation_time_sec REAL,
    status TEXT,
    confidence_report JSON  -- Phase 4: Structured confidence report with factors, breakdown, warnings
);

CREATE INDEX IF NOT EXISTS idx_forecasts_created ON forecasts(created_at);
CREATE INDEX IF NOT EXISTS idx_forecasts_bundle ON forecasts(bundle_id);

-- Predictions table - extracted from forecast text
-- Timestamp format: ISO 8601 without microseconds or timezone (YYYY-MM-DD HH:MM:SS)
CREATE TABLE IF NOT EXISTS predictions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    forecast_id TEXT NOT NULL,
    shore TEXT NOT NULL,
    forecast_time TEXT NOT NULL CHECK (forecast_time GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9] [0-9][0-9]:[0-9][0-9]:[0-9][0-9]'),
    valid_time TEXT NOT NULL CHECK (valid_time GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9] [0-9][0-9]:[0-9][0-9]:[0-9][0-9]'),
    predicted_height REAL,
    predicted_period REAL,
    predicted_direction TEXT,
    predicted_category TEXT,
    confidence REAL,
    FOREIGN KEY (forecast_id) REFERENCES forecasts(forecast_id)
);

CREATE INDEX IF NOT EXISTS idx_predictions_forecast ON predictions(forecast_id);
CREATE INDEX IF NOT EXISTS idx_predictions_valid_time ON predictions(valid_time);
-- Composite index for shore-specific time-range queries
-- Enables efficient queries like: WHERE shore='North Shore' AND valid_time BETWEEN ... ORDER BY valid_time
-- Order (shore, valid_time) matches query pattern: filter by shore first, then filter/sort by time
CREATE INDEX IF NOT EXISTS idx_predictions_shore_time ON predictions(shore, valid_time);

-- Actual observations from buoys
-- Timestamp format: ISO 8601 without microseconds or timezone (YYYY-MM-DD HH:MM:SS)
CREATE TABLE IF NOT EXISTS actuals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    buoy_id TEXT NOT NULL,
    observation_time TEXT NOT NULL CHECK (observation_time GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9] [0-9][0-9]:[0-9][0-9]:[0-9][0-9]'),
    wave_height REAL,
    dominant_period REAL,
    direction REAL,
    source TEXT
);

CREATE INDEX IF NOT EXISTS idx_actuals_buoy_time ON actuals(buoy_id, observation_time);

-- Validation results - comparison of predictions vs actuals
-- Timestamp format: ISO 8601 without microseconds or timezone (YYYY-MM-DD HH:MM:SS)
CREATE TABLE IF NOT EXISTS validations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    forecast_id TEXT NOT NULL,
    prediction_id INTEGER NOT NULL,
    actual_id INTEGER NOT NULL,
    validated_at TEXT NOT NULL CHECK (validated_at GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9] [0-9][0-9]:[0-9][0-9]:[0-9][0-9]'),
    height_error REAL,
    period_error REAL,
    direction_error REAL,
    category_match BOOLEAN,
    mae REAL,
    rmse REAL,
    FOREIGN KEY (forecast_id) REFERENCES forecasts(forecast_id),
    FOREIGN KEY (prediction_id) REFERENCES predictions(id),
    FOREIGN KEY (actual_id) REFERENCES actuals(id)
);

CREATE INDEX IF NOT EXISTS idx_validations_forecast ON validations(forecast_id);
-- Performance-critical index for time-windowed performance queries (adaptive prompt injection)
-- Without this index, queries perform full table scans (500ms @ 10K validations)
-- With index: <50ms for all performance queries combined
CREATE INDEX IF NOT EXISTS idx_validations_validated_at ON validations(validated_at);
