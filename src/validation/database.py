"""Validation database management."""
import sqlite3
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime

logger = logging.getLogger(__name__)


class ValidationDatabase:
    """Manages SQLite database for forecast validation."""

    def __init__(self, db_path: str = "data/validation.db"):
        """Initialize database connection.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(exist_ok=True, parents=True)
        self._init_database()

    def _init_database(self) -> None:
        """Initialize database with schema from schema.sql."""
        schema_path = Path(__file__).parent / "schema.sql"

        with sqlite3.connect(self.db_path) as conn:
            # Read and execute schema
            if schema_path.exists():
                with open(schema_path) as f:
                    conn.executescript(f.read())
                logger.info(f"Initialized validation database: {self.db_path}")
            else:
                logger.warning(f"Schema file not found: {schema_path}")

    def save_forecast(self, forecast_data: Dict[str, Any]) -> str:
        """Save forecast metadata to database.

        Args:
            forecast_data: Dictionary containing forecast metadata with keys:
                - forecast_id: Unique identifier for the forecast
                - generated_time: Timestamp when forecast was generated
                - metadata: Dict with source_data, api_usage, generation_time

        Returns:
            forecast_id: The ID of the saved forecast
        """
        metadata = forecast_data.get('metadata', {})
        api_usage = metadata.get('api_usage', {})

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO forecasts (
                    forecast_id, created_at, bundle_id, model_version,
                    total_tokens, input_tokens, output_tokens, model_cost_usd,
                    generation_time_sec, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                forecast_data.get('forecast_id'),
                forecast_data.get('generated_time'),
                metadata.get('source_data', {}).get('bundle_id'),
                api_usage.get('model', 'gpt-5-mini'),
                api_usage.get('input_tokens', 0) + api_usage.get('output_tokens', 0),
                api_usage.get('input_tokens', 0),
                api_usage.get('output_tokens', 0),
                api_usage.get('total_cost', 0.0),
                metadata.get('generation_time', 0.0),
                'completed'
            ))
            conn.commit()

        logger.info(f"Saved forecast {forecast_data.get('forecast_id')} to database")
        return forecast_data.get('forecast_id')

    def save_prediction(
        self,
        forecast_id: str,
        shore: str,
        forecast_time: datetime,
        valid_time: datetime,
        predicted_height: Optional[float] = None,
        predicted_period: Optional[float] = None,
        predicted_direction: Optional[str] = None,
        predicted_category: Optional[str] = None,
        confidence: float = 0.7
    ) -> int:
        """Save a single prediction to database.

        Args:
            forecast_id: ID of the parent forecast
            shore: Shore name (e.g., 'North Shore', 'South Shore')
            forecast_time: When the forecast was made
            valid_time: When the prediction is valid for
            predicted_height: Predicted wave height in feet
            predicted_period: Predicted wave period in seconds
            predicted_direction: Predicted wave direction (e.g., 'NW', 'S')
            predicted_category: Predicted surf category (e.g., 'flat', 'small', 'moderate')
            confidence: Confidence score (0-1)

        Returns:
            prediction_id: The ID of the saved prediction
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO predictions (
                    forecast_id, shore, forecast_time, valid_time,
                    predicted_height, predicted_period, predicted_direction,
                    predicted_category, confidence
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                forecast_id,
                shore,
                forecast_time,
                valid_time,
                predicted_height,
                predicted_period,
                predicted_direction,
                predicted_category,
                confidence
            ))
            conn.commit()
            prediction_id = cursor.lastrowid

        logger.debug(f"Saved prediction {prediction_id} for forecast {forecast_id}")
        return prediction_id

    def save_predictions(
        self,
        forecast_id: str,
        predictions: List[Dict[str, Any]]
    ) -> None:
        """Save multiple forecast predictions to database.

        Args:
            forecast_id: ID of the parent forecast
            predictions: List of prediction dictionaries with keys:
                - shore: Shore name
                - forecast_time: When forecast was made
                - valid_time: When prediction is valid for
                - height: Predicted height (optional)
                - period: Predicted period (optional)
                - direction: Predicted direction (optional)
                - category: Predicted category (optional)
                - confidence: Confidence score (optional, default 0.7)
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            for pred in predictions:
                cursor.execute("""
                    INSERT INTO predictions (
                        forecast_id, shore, forecast_time, valid_time,
                        predicted_height, predicted_period, predicted_direction,
                        predicted_category, confidence
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    forecast_id,
                    pred.get('shore'),
                    pred.get('forecast_time'),
                    pred.get('valid_time'),
                    pred.get('height'),
                    pred.get('period'),
                    pred.get('direction'),
                    pred.get('category'),
                    pred.get('confidence', 0.7)
                ))
            conn.commit()

        logger.info(f"Saved {len(predictions)} predictions for forecast {forecast_id}")

    def save_actual(
        self,
        buoy_id: str,
        observation_time: datetime,
        wave_height: Optional[float] = None,
        dominant_period: Optional[float] = None,
        direction: Optional[float] = None,
        source: str = 'NDBC'
    ) -> int:
        """Save actual buoy observation to database.

        Args:
            buoy_id: Buoy identifier (e.g., '51201')
            observation_time: Time of observation
            wave_height: Observed wave height in feet
            dominant_period: Observed dominant period in seconds
            direction: Observed wave direction in degrees
            source: Data source (e.g., 'NDBC', 'CDIP')

        Returns:
            actual_id: The ID of the saved observation
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO actuals (
                    buoy_id, observation_time, wave_height,
                    dominant_period, direction, source
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (
                buoy_id,
                observation_time,
                wave_height,
                dominant_period,
                direction,
                source
            ))
            conn.commit()
            actual_id = cursor.lastrowid

        logger.debug(f"Saved actual observation {actual_id} for buoy {buoy_id}")
        return actual_id

    def save_validation(
        self,
        forecast_id: str,
        prediction_id: int,
        actual_id: int,
        height_error: Optional[float] = None,
        period_error: Optional[float] = None,
        direction_error: Optional[float] = None,
        category_match: Optional[bool] = None,
        mae: Optional[float] = None,
        rmse: Optional[float] = None
    ) -> int:
        """Save validation result comparing prediction to actual.

        Args:
            forecast_id: ID of the forecast being validated
            prediction_id: ID of the prediction record
            actual_id: ID of the actual observation record
            height_error: Absolute error in height (ft)
            period_error: Absolute error in period (sec)
            direction_error: Absolute error in direction (degrees)
            category_match: Whether predicted category matched actual
            mae: Mean absolute error
            rmse: Root mean squared error

        Returns:
            validation_id: The ID of the saved validation
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO validations (
                    forecast_id, prediction_id, actual_id, validated_at,
                    height_error, period_error, direction_error,
                    category_match, mae, rmse
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                forecast_id,
                prediction_id,
                actual_id,
                datetime.now(),
                height_error,
                period_error,
                direction_error,
                category_match,
                mae,
                rmse
            ))
            conn.commit()
            validation_id = cursor.lastrowid

        logger.info(f"Saved validation {validation_id} for forecast {forecast_id}")
        return validation_id

    def get_forecasts_needing_validation(
        self,
        hours_after: int = 24
    ) -> List[Dict[str, Any]]:
        """Get forecasts that need validation (24+ hours old).

        Args:
            hours_after: Minimum hours after forecast creation to validate

        Returns:
            List of forecast dictionaries with forecast_id, created_at, bundle_id
        """
        cutoff = datetime.now().timestamp() - (hours_after * 3600)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT f.forecast_id, f.created_at, f.bundle_id
                FROM forecasts f
                LEFT JOIN validations v ON f.forecast_id = v.forecast_id
                WHERE f.created_at < ?
                AND v.id IS NULL
                ORDER BY f.created_at DESC
            """, (cutoff,))

            results = []
            for row in cursor.fetchall():
                results.append({
                    'forecast_id': row[0],
                    'created_at': row[1],
                    'bundle_id': row[2]
                })

        return results
