"""Validation database management."""
import sqlite3
import logging
import json
import time
from pathlib import Path
from typing import Optional, Dict, Any, List, Union
from datetime import datetime
from contextlib import contextmanager

logger = logging.getLogger(__name__)

# ISO 8601 format for all timestamps (without microseconds or timezone)
# Example: '2025-10-11 12:00:00'
TIMESTAMP_FORMAT = '%Y-%m-%d %H:%M:%S'

# Database connection configuration
DB_TIMEOUT = 30.0  # Timeout in seconds for database operations
MAX_RETRIES = 3    # Maximum number of retry attempts
RETRY_DELAY = 0.1  # Initial retry delay in seconds (exponential backoff)
RETRY_BACKOFF_MULTIPLIER = 2.0  # Multiply delay by this for each retry


def format_timestamp(dt: Union[datetime, str, float, int]) -> str:
    """Convert datetime to ISO 8601 string format.

    Args:
        dt: datetime object, ISO 8601 string, or Unix timestamp (float/int)

    Returns:
        ISO 8601 formatted string (YYYY-MM-DD HH:MM:SS)
    """
    # Handle Unix timestamps (float/int)
    if isinstance(dt, (float, int)):
        if dt > 1000000000:  # Likely a Unix timestamp
            dt_obj = datetime.fromtimestamp(dt)
            return dt_obj.strftime(TIMESTAMP_FORMAT)

    # Handle strings
    if isinstance(dt, str):
        # If already a string, parse and reformat to ensure consistency
        # Handle various ISO 8601 formats (with T, with Z, with microseconds)
        dt_str = dt.replace('T', ' ').replace('Z', '').split('.')[0]
        try:
            dt_obj = datetime.strptime(dt_str, TIMESTAMP_FORMAT)
            return dt_obj.strftime(TIMESTAMP_FORMAT)
        except ValueError:
            # If parsing fails, try to parse as-is
            return dt_str

    # Handle datetime objects
    return dt.strftime(TIMESTAMP_FORMAT)


def parse_timestamp(timestamp_str: str) -> datetime:
    """Parse ISO 8601 string to datetime object.

    Args:
        timestamp_str: ISO 8601 formatted string

    Returns:
        datetime object
    """
    # Handle legacy Unix timestamps (float/int as string)
    try:
        # Try parsing as Unix timestamp first
        timestamp_float = float(timestamp_str)
        if timestamp_float > 1000000000:  # Likely a Unix timestamp
            return datetime.fromtimestamp(timestamp_float)
    except (ValueError, TypeError):
        pass

    # Parse as ISO 8601 string
    # Handle various formats (with T, with Z, with microseconds)
    clean_str = timestamp_str.replace('T', ' ').replace('Z', '').split('.')[0]
    return datetime.strptime(clean_str, TIMESTAMP_FORMAT)


def connect_with_retry(
    db_path: str,
    timeout: float = DB_TIMEOUT,
    max_retries: int = MAX_RETRIES,
    retry_delay: float = RETRY_DELAY
) -> sqlite3.Connection:
    """
    Connect to SQLite database with retry logic for transient failures.

    Args:
        db_path: Path to database file
        timeout: Connection timeout in seconds
        max_retries: Maximum retry attempts
        retry_delay: Initial delay between retries (seconds)

    Returns:
        sqlite3.Connection object

    Raises:
        sqlite3.Error: If connection fails after all retries
    """
    last_error = None
    current_delay = retry_delay

    for attempt in range(max_retries):
        try:
            conn = sqlite3.connect(db_path, timeout=timeout)
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("PRAGMA journal_mode = WAL")
            return conn
        except (sqlite3.OperationalError, sqlite3.DatabaseError) as e:
            last_error = e
            error_msg = str(e).lower()

            # Only retry on transient errors
            if any(keyword in error_msg for keyword in ['locked', 'busy', 'timeout', 'disk i/o']):
                if attempt < max_retries - 1:
                    logger.warning(
                        f"Database connection attempt {attempt + 1}/{max_retries} failed: {e}. "
                        f"Retrying in {current_delay:.2f}s..."
                    )
                    time.sleep(current_delay)
                    current_delay *= RETRY_BACKOFF_MULTIPLIER
                    continue

            # Non-transient error or last attempt - raise immediately
            raise

    # All retries exhausted
    raise sqlite3.OperationalError(
        f"Failed to connect to database after {max_retries} attempts: {last_error}"
    )


@contextmanager
def immediate_transaction(conn: sqlite3.Connection):
    """
    Context manager for IMMEDIATE transactions (write operations).

    Acquires exclusive write lock immediately, preventing write conflicts.
    Use for: INSERT, UPDATE, DELETE operations.

    Args:
        conn: Database connection

    Yields:
        Connection with active transaction

    Example:
        with immediate_transaction(conn):
            conn.execute("INSERT INTO forecasts ...")
    """
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


@contextmanager
def deferred_transaction(conn: sqlite3.Connection):
    """
    Context manager for DEFERRED transactions (read operations).

    Lock acquired only when needed. Use for read-only operations.

    Args:
        conn: Database connection

    Yields:
        Connection with active transaction

    Example:
        with deferred_transaction(conn):
            rows = conn.execute("SELECT * FROM forecasts").fetchall()
    """
    conn.execute("BEGIN DEFERRED")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


@contextmanager
def extended_timeout_connection(db_path: str, timeout: float = 60.0):
    """
    Context manager for database operations that need extended timeout.

    Use for bulk inserts, complex queries, or maintenance operations.

    Args:
        db_path: Path to database file
        timeout: Extended timeout in seconds (default 60s)

    Example:
        with extended_timeout_connection(db_path) as conn:
            conn.executemany("INSERT ...", large_batch)
    """
    conn = connect_with_retry(db_path, timeout=timeout)
    try:
        yield conn
    finally:
        conn.close()


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

        conn = connect_with_retry(str(self.db_path))
        conn.execute("BEGIN EXCLUSIVE")  # Exclusive lock for schema initialization
        try:
            # Read and execute schema
            if schema_path.exists():
                with open(schema_path) as f:
                    conn.executescript(f.read())
                logger.info(f"Initialized validation database: {self.db_path}")
            else:
                logger.warning(f"Schema file not found: {schema_path}")

            # Migration: Add confidence_report column if it doesn't exist (Phase 4)
            try:
                cursor = conn.cursor()
                cursor.execute("PRAGMA table_info(forecasts)")
                columns = [row[1] for row in cursor.fetchall()]

                if 'confidence_report' not in columns:
                    cursor.execute("ALTER TABLE forecasts ADD COLUMN confidence_report JSON")
                    logger.info("Added confidence_report column to forecasts table (Phase 4 migration)")
            except Exception as e:
                logger.warning(f"Could not add confidence_report column (may already exist): {e}")

            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def save_forecast(self, forecast_data: Dict[str, Any]) -> str:
        """Save forecast metadata to database.

        Args:
            forecast_data: Dictionary containing forecast metadata with keys:
                - forecast_id: Unique identifier for the forecast
                - generated_time: Timestamp when forecast was generated
                - metadata: Dict with source_data, api_usage, generation_time, confidence_report

        Returns:
            forecast_id: The ID of the saved forecast
        """
        metadata = forecast_data.get('metadata', {})
        api_usage = metadata.get('api_usage', {})

        # Phase 4: Extract confidence report for JSON storage
        confidence_report = metadata.get('confidence_report')
        confidence_report_json = None
        if confidence_report:
            # confidence_report is already a dict from model_dump()
            confidence_report_json = json.dumps(confidence_report)

        conn = connect_with_retry(str(self.db_path))

        try:
            with immediate_transaction(conn):
                cursor = conn.cursor()

                # Convert generated_time to ISO 8601 format
                generated_time = forecast_data.get('generated_time')
                if generated_time:
                    created_at = format_timestamp(generated_time)
                else:
                    created_at = format_timestamp(datetime.now())

                cursor.execute("""
                    INSERT INTO forecasts (
                        forecast_id, created_at, bundle_id, model_version,
                        total_tokens, input_tokens, output_tokens, model_cost_usd,
                        generation_time_sec, status, confidence_report
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    forecast_data.get('forecast_id'),
                    created_at,
                    metadata.get('source_data', {}).get('bundle_id'),
                    api_usage.get('model', 'gpt-5-mini'),
                    api_usage.get('input_tokens', 0) + api_usage.get('output_tokens', 0),
                    api_usage.get('input_tokens', 0),
                    api_usage.get('output_tokens', 0),
                    api_usage.get('total_cost', 0.0),
                    metadata.get('generation_time', 0.0),
                    'completed',
                    confidence_report_json  # Phase 4: Store structured confidence report as JSON
                ))
                logger.info(f"Saved forecast {forecast_data.get('forecast_id')} to database")
        except Exception as e:
            logger.error(f"Failed to save forecast {forecast_data.get('forecast_id')}: {e}")
            raise
        finally:
            conn.close()

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
        conn = connect_with_retry(str(self.db_path))

        try:
            with immediate_transaction(conn):
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
                    format_timestamp(forecast_time),
                    format_timestamp(valid_time),
                    predicted_height,
                    predicted_period,
                    predicted_direction,
                    predicted_category,
                    confidence
                ))
                prediction_id = cursor.lastrowid
                logger.debug(f"Saved prediction {prediction_id} for forecast {forecast_id}")
        except Exception as e:
            logger.error(f"Failed to save prediction for forecast {forecast_id}: {e}")
            raise
        finally:
            conn.close()

        return prediction_id

    def save_predictions(
        self,
        forecast_id: str,
        predictions: List[Dict[str, Any]]
    ) -> None:
        """Save multiple forecast predictions to database using batch insert.

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
        conn = connect_with_retry(str(self.db_path), timeout=60.0)  # Extended timeout for batch

        try:
            with immediate_transaction(conn):
                cursor = conn.cursor()

                # Prepare batch data for executemany
                batch_data = [
                    (
                        forecast_id,
                        pred.get('shore'),
                        format_timestamp(pred.get('forecast_time')),
                        format_timestamp(pred.get('valid_time')),
                        pred.get('height'),
                        pred.get('period'),
                        pred.get('direction'),
                        pred.get('category'),
                        pred.get('confidence', 0.7)
                    )
                    for pred in predictions
                ]

                cursor.executemany("""
                    INSERT INTO predictions (
                        forecast_id, shore, forecast_time, valid_time,
                        predicted_height, predicted_period, predicted_direction,
                        predicted_category, confidence
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, batch_data)

                logger.info(f"Saved {len(predictions)} predictions for forecast {forecast_id}")
        except Exception as e:
            logger.error(f"Batch prediction insert failed for forecast {forecast_id}: {e}")
            raise
        finally:
            conn.close()

    def get_forecast(self, forecast_id: str) -> Optional[Dict[str, Any]]:
        """Fetch a single forecast row by ID."""
        with connect_with_retry(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM forecasts WHERE forecast_id = ?",
                (forecast_id,)
            )
            row = cursor.fetchone()
            if row is None:
                logger.warning("Forecast %s not found", forecast_id)
                return None
            return dict(row)

    def get_predictions_for_forecast(self, forecast_id: str) -> List[Dict[str, Any]]:
        """Return predictions associated with a forecast."""
        with connect_with_retry(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM predictions WHERE forecast_id = ? ORDER BY valid_time",
                (forecast_id,)
            )
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

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
        conn = connect_with_retry(str(self.db_path))

        try:
            with immediate_transaction(conn):
                cursor = conn.cursor()

                cursor.execute("""
                    INSERT INTO actuals (
                        buoy_id, observation_time, wave_height,
                        dominant_period, direction, source
                    ) VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    buoy_id,
                    format_timestamp(observation_time),
                    wave_height,
                    dominant_period,
                    direction,
                    source
                ))
                actual_id = cursor.lastrowid
                logger.debug(f"Saved actual observation {actual_id} for buoy {buoy_id}")
        except Exception as e:
            logger.error(f"Failed to save actual observation for buoy {buoy_id}: {e}")
            raise
        finally:
            conn.close()

        return actual_id

    def save_actuals(
        self,
        actuals: List[Dict[str, Any]]
    ) -> None:
        """Save multiple buoy observations to database using batch insert.

        Args:
            actuals: List of actual observation dictionaries with keys:
                - buoy_id: Buoy identifier
                - observation_time: Time of observation
                - wave_height: Observed wave height (optional)
                - dominant_period: Observed dominant period (optional)
                - direction: Observed wave direction (optional)
                - source: Data source (optional, default 'NDBC')
        """
        conn = connect_with_retry(str(self.db_path), timeout=60.0)  # Extended timeout for batch

        try:
            with immediate_transaction(conn):
                cursor = conn.cursor()

                # Prepare batch data for executemany
                batch_data = [
                    (
                        actual.get('buoy_id'),
                        format_timestamp(actual.get('observation_time')),
                        actual.get('wave_height'),
                        actual.get('dominant_period'),
                        actual.get('direction'),
                        actual.get('source', 'NDBC')
                    )
                    for actual in actuals
                ]

                cursor.executemany("""
                    INSERT INTO actuals (
                        buoy_id, observation_time, wave_height,
                        dominant_period, direction, source
                    ) VALUES (?, ?, ?, ?, ?, ?)
                """, batch_data)

                logger.info(f"Saved {len(actuals)} actual observations")
        except Exception as e:
            logger.error(f"Batch actual insert failed: {e}")
            raise
        finally:
            conn.close()

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
        conn = connect_with_retry(str(self.db_path))

        try:
            with immediate_transaction(conn):
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
                    format_timestamp(datetime.now()),
                    height_error,
                    period_error,
                    direction_error,
                    category_match,
                    mae,
                    rmse
                ))
                validation_id = cursor.lastrowid
                logger.info(f"Saved validation {validation_id} for forecast {forecast_id}")
        except Exception as e:
            logger.error(f"Failed to save validation for forecast {forecast_id}: {e}")
            raise
        finally:
            conn.close()

        return validation_id

    def save_validations(
        self,
        validations: List[Dict[str, Any]]
    ) -> None:
        """Save multiple validation results to database using batch insert.

        Args:
            validations: List of validation dictionaries with keys:
                - forecast_id: ID of the forecast being validated
                - prediction_id: ID of the prediction record
                - actual_id: ID of the actual observation record
                - height_error: Absolute error in height (optional)
                - period_error: Absolute error in period (optional)
                - direction_error: Absolute error in direction (optional)
                - category_match: Whether predicted category matched actual (optional)
                - mae: Mean absolute error (optional)
                - rmse: Root mean squared error (optional)
        """
        conn = connect_with_retry(str(self.db_path), timeout=60.0)  # Extended timeout for batch

        try:
            with immediate_transaction(conn):
                cursor = conn.cursor()

                # Get current timestamp for all validations
                validated_at = format_timestamp(datetime.now())

                # Prepare batch data for executemany
                batch_data = [
                    (
                        val.get('forecast_id'),
                        val.get('prediction_id'),
                        val.get('actual_id'),
                        validated_at,
                        val.get('height_error'),
                        val.get('period_error'),
                        val.get('direction_error'),
                        val.get('category_match'),
                        val.get('mae'),
                        val.get('rmse')
                    )
                    for val in validations
                ]

                cursor.executemany("""
                    INSERT INTO validations (
                        forecast_id, prediction_id, actual_id, validated_at,
                        height_error, period_error, direction_error,
                        category_match, mae, rmse
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, batch_data)

                logger.info(f"Saved {len(validations)} validation results")
        except Exception as e:
            logger.error(f"Batch validation insert failed: {e}")
            raise
        finally:
            conn.close()

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
        # Calculate cutoff time and format as ISO 8601 string
        from datetime import timedelta
        cutoff_dt = datetime.now() - timedelta(hours=hours_after)
        cutoff = format_timestamp(cutoff_dt)

        with connect_with_retry(str(self.db_path)) as conn:
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

    def checkpoint_wal(self) -> None:
        """Checkpoint the WAL file to move data to main database."""
        with connect_with_retry(str(self.db_path)) as conn:
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            logger.info("WAL checkpoint completed")
