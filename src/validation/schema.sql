-- SurfCastAI Validation Database Schema
-- Stores forecast metadata, predictions, actual observations, and validation results

-- Forecast metadata table
CREATE TABLE IF NOT EXISTS forecasts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    forecast_id TEXT UNIQUE NOT NULL,
    created_at TIMESTAMP NOT NULL,
    bundle_id TEXT,
    model_version TEXT NOT NULL,
    total_tokens INTEGER,
    input_tokens INTEGER,
    output_tokens INTEGER,
    model_cost_usd REAL,
    generation_time_sec REAL,
    status TEXT
);

CREATE INDEX IF NOT EXISTS idx_forecasts_created ON forecasts(created_at);
CREATE INDEX IF NOT EXISTS idx_forecasts_bundle ON forecasts(bundle_id);

-- Predictions table - extracted from forecast text
CREATE TABLE IF NOT EXISTS predictions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    forecast_id TEXT NOT NULL,
    shore TEXT NOT NULL,
    forecast_time TIMESTAMP NOT NULL,
    valid_time TIMESTAMP NOT NULL,
    predicted_height REAL,
    predicted_period REAL,
    predicted_direction TEXT,
    predicted_category TEXT,
    confidence REAL,
    FOREIGN KEY (forecast_id) REFERENCES forecasts(forecast_id)
);

CREATE INDEX IF NOT EXISTS idx_predictions_forecast ON predictions(forecast_id);
CREATE INDEX IF NOT EXISTS idx_predictions_valid_time ON predictions(valid_time);

-- Actual observations from buoys
CREATE TABLE IF NOT EXISTS actuals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    buoy_id TEXT NOT NULL,
    observation_time TIMESTAMP NOT NULL,
    wave_height REAL,
    dominant_period REAL,
    direction REAL,
    source TEXT
);

CREATE INDEX IF NOT EXISTS idx_actuals_buoy_time ON actuals(buoy_id, observation_time);

-- Validation results - comparison of predictions vs actuals
CREATE TABLE IF NOT EXISTS validations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    forecast_id TEXT NOT NULL,
    prediction_id INTEGER NOT NULL,
    actual_id INTEGER NOT NULL,
    validated_at TIMESTAMP NOT NULL,
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
