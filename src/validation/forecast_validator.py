"""
Forecast validation engine - compares predictions to ground truth observations.
"""

import logging
from datetime import datetime, timedelta
from typing import Any

from .buoy_fetcher import BuoyDataFetcher


class ForecastValidator:
    """
    Validates forecast accuracy by comparing predictions to actual buoy observations.

    Calculates metrics:
    - MAE (Mean Absolute Error): Target < 2 feet Hawaiian scale
    - RMSE (Root Mean Square Error): Target < 2.5 feet
    - Categorical Accuracy: Target 75% correct (small/moderate/large/extra_large)
    - Direction Accuracy: Target 80% within 22.5 degrees
    """

    # Shore to buoy mapping
    SHORE_BUOYS = {
        "North Shore": ["51001", "51101"],  # NW Hawaii, NW Molokai
        "South Shore": ["51003", "51004"],  # SE Hawaii buoys
    }

    # Category thresholds (Hawaiian scale feet)
    CATEGORY_THRESHOLDS = {
        "small": (0, 4),
        "moderate": (4, 8),
        "large": (8, 12),
        "extra_large": (12, 100),
    }

    # Direction tolerance (degrees)
    DIRECTION_TOLERANCE = 22.5

    def __init__(self, database: "ValidationDatabase"):
        """
        Initialize validator.

        Args:
            database: ValidationDatabase instance for storing results
        """
        self.database = database
        self.logger = logging.getLogger(self.__class__.__name__)

    async def validate_forecast(self, forecast_id: str, hours_after: int = 24) -> dict[str, Any]:
        """
        Validate a forecast by comparing predictions to actual observations.

        Args:
            forecast_id: Unique identifier for the forecast to validate
            hours_after: Minimum hours after forecast before validating (default: 24)

        Returns:
            Dictionary with validation results:
                - forecast_id: ID of validated forecast
                - validated_at: Timestamp of validation
                - metrics: Dict with MAE, RMSE, categorical_accuracy, direction_accuracy
                - predictions_validated: Number of predictions validated
                - predictions_total: Total predictions in forecast
                - validations: List of individual validation records

        Raises:
            ValueError: If forecast not found or too recent
        """
        self.logger.info(f"Validating forecast {forecast_id} (min {hours_after}h after)")

        # Step 1: Get forecast and predictions from database
        forecast_data = await self._get_forecast_data(forecast_id, hours_after)
        if not forecast_data:
            raise ValueError(f"Forecast {forecast_id} not found or too recent")

        predictions = forecast_data["predictions"]
        forecast_time = forecast_data["forecast_time"]

        self.logger.info(f"Found {len(predictions)} predictions for forecast {forecast_id}")

        # Step 2: Fetch actual observations from buoys
        actuals = await self._fetch_actual_observations(predictions)

        if not actuals:
            self.logger.warning("No actual observations found for validation")
            return {
                "forecast_id": forecast_id,
                "validated_at": datetime.now().isoformat(),
                "error": "No actual observations available",
                "predictions_validated": 0,
                "predictions_total": len(predictions),
            }

        self.logger.info(f"Found {len(actuals)} actual observations")

        # Step 3: Match predictions to actuals
        matches = self._match_predictions_to_actuals(predictions, actuals)

        self.logger.info(f"Matched {len(matches)} prediction-actual pairs")

        if not matches:
            self.logger.warning("No matches found between predictions and actuals")
            return {
                "forecast_id": forecast_id,
                "validated_at": datetime.now().isoformat(),
                "error": "No matches between predictions and observations",
                "predictions_validated": 0,
                "predictions_total": len(predictions),
            }

        # Step 4: Calculate metrics
        metrics = self._calculate_metrics(matches)

        self.logger.info(
            f"Calculated metrics: MAE={metrics['mae']:.2f}, RMSE={metrics['rmse']:.2f}"
        )

        # Step 5: Save validation results to database
        validation_records = []
        for match in matches:
            pred = match["prediction"]
            actual = match["actual"]

            # Calculate individual errors
            height_error = (
                abs(pred["height"] - actual["wave_height"])
                if pred.get("height") and actual.get("wave_height")
                else None
            )
            period_error = (
                abs(pred["period"] - actual["dominant_period"])
                if pred.get("period") and actual.get("dominant_period")
                else None
            )

            # Direction error (handle wraparound)
            direction_error = None
            if pred.get("direction") and actual.get("direction"):
                pred_dir = self._direction_to_degrees(pred["direction"])
                actual_dir = actual["direction"]
                if pred_dir is not None and actual_dir is not None:
                    direction_error = self._angular_difference(pred_dir, actual_dir)

            # Category match
            pred_category = pred.get("category")
            actual_category = self._categorize_height(actual.get("wave_height"))
            category_match = (
                (pred_category == actual_category) if pred_category and actual_category else None
            )

            # Save validation to database
            validation_id = self.database.save_validation(
                forecast_id=forecast_id,
                prediction_id=pred["id"],
                actual_id=actual["id"],
                height_error=height_error,
                period_error=period_error,
                direction_error=direction_error,
                category_match=category_match,
                mae=metrics["mae"],
                rmse=metrics["rmse"],
            )

            validation_records.append(
                {
                    "validation_id": validation_id,
                    "prediction_id": pred["id"],
                    "actual_id": actual["id"],
                    "height_error": height_error,
                    "period_error": period_error,
                    "direction_error": direction_error,
                    "category_match": category_match,
                }
            )

        # Return validation summary
        return {
            "forecast_id": forecast_id,
            "validated_at": datetime.now().isoformat(),
            "metrics": metrics,
            "predictions_validated": len(matches),
            "predictions_total": len(predictions),
            "validations": validation_records,
        }

    async def _get_forecast_data(self, forecast_id: str, hours_after: int) -> dict[str, Any] | None:
        """
        Get forecast and predictions from database.

        Args:
            forecast_id: Forecast ID
            hours_after: Minimum hours after forecast

        Returns:
            Dictionary with forecast data and predictions, or None if not found/too recent
        """
        import sqlite3

        with sqlite3.connect(self.database.db_path) as conn:
            cursor = conn.cursor()

            # Get forecast metadata
            cursor.execute(
                """
                SELECT forecast_id, created_at
                FROM forecasts
                WHERE forecast_id = ?
            """,
                (forecast_id,),
            )

            row = cursor.fetchone()
            if not row:
                self.logger.error(f"Forecast {forecast_id} not found")
                return None

            forecast_id_db, created_at = row

            # Check if forecast is old enough
            forecast_time = (
                datetime.fromisoformat(created_at)
                if isinstance(created_at, str)
                else datetime.fromtimestamp(created_at)
            )
            hours_since = (datetime.now() - forecast_time).total_seconds() / 3600

            if hours_since < hours_after:
                self.logger.error(
                    f"Forecast {forecast_id} too recent: {hours_since:.1f}h < {hours_after}h"
                )
                return None

            # Get predictions
            cursor.execute(
                """
                SELECT id, shore, forecast_time, valid_time,
                       predicted_height, predicted_period, predicted_direction,
                       predicted_category, confidence
                FROM predictions
                WHERE forecast_id = ?
            """,
                (forecast_id,),
            )

            predictions = []
            for row in cursor.fetchall():
                predictions.append(
                    {
                        "id": row[0],
                        "shore": row[1],
                        "forecast_time": (
                            datetime.fromisoformat(row[2])
                            if isinstance(row[2], str)
                            else datetime.fromtimestamp(row[2])
                        ),
                        "valid_time": (
                            datetime.fromisoformat(row[3])
                            if isinstance(row[3], str)
                            else datetime.fromtimestamp(row[3])
                        ),
                        "height": row[4],
                        "period": row[5],
                        "direction": row[6],
                        "category": row[7],
                        "confidence": row[8],
                    }
                )

            return {
                "forecast_id": forecast_id_db,
                "forecast_time": forecast_time,
                "predictions": predictions,
            }

    async def _fetch_actual_observations(
        self, predictions: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """
        Fetch actual buoy observations for the prediction time ranges.

        Args:
            predictions: List of prediction dictionaries

        Returns:
            List of actual observation dictionaries with database IDs
        """

        # Determine time range to fetch
        if not predictions:
            return []

        valid_times = [p["valid_time"] for p in predictions if p.get("valid_time")]
        if not valid_times:
            return []

        start_time = min(valid_times) - timedelta(hours=2)  # 2h buffer before
        end_time = max(valid_times) + timedelta(hours=2)  # 2h buffer after

        # Determine which shores we need
        shores = set(p["shore"] for p in predictions if p.get("shore"))

        # Fetch observations for each shore
        all_observations = []

        async with BuoyDataFetcher() as fetcher:
            for shore in shores:
                # Normalize shore name
                shore_key = shore.lower().replace(" ", "_")
                if shore_key not in ["north_shore", "south_shore"]:
                    self.logger.warning(f"Unknown shore: {shore}, skipping")
                    continue

                try:
                    observations = await fetcher.fetch_observations(
                        shore=shore_key, start_time=start_time, end_time=end_time
                    )

                    # Save observations to database and add IDs
                    for obs in observations:
                        actual_id = self.database.save_actual(
                            buoy_id=obs["buoy_id"],
                            observation_time=obs["observation_time"],
                            wave_height=obs.get("wave_height"),
                            dominant_period=obs.get("dominant_period"),
                            direction=obs.get("direction"),
                            source=obs.get("source", "NDBC"),
                        )
                        obs["id"] = actual_id
                        obs["shore"] = shore  # Add shore for matching

                    all_observations.extend(observations)

                except Exception as e:
                    self.logger.error(
                        f"Error fetching observations for {shore}: {e}", exc_info=True
                    )

        return all_observations

    def _match_predictions_to_actuals(
        self, predictions: list[dict[str, Any]], actuals: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """
        Match predictions to actual observations by time window and shore.

        Args:
            predictions: List of prediction dictionaries
            actuals: List of actual observation dictionaries

        Returns:
            List of matched pairs: [{'prediction': pred, 'actual': actual}, ...]
        """
        matches = []
        time_window = timedelta(hours=2)  # Match within 2 hours

        for pred in predictions:
            if not pred.get("valid_time") or not pred.get("height"):
                continue

            best_match = None
            best_time_diff = None

            for actual in actuals:
                # Must be same shore
                if pred.get("shore") != actual.get("shore"):
                    continue

                # Must have observation time and wave height
                if not actual.get("observation_time") or not actual.get("wave_height"):
                    continue

                # Calculate time difference
                time_diff = abs(pred["valid_time"] - actual["observation_time"])

                # Must be within time window
                if time_diff > time_window:
                    continue

                # Keep closest match
                if best_time_diff is None or time_diff < best_time_diff:
                    best_match = actual
                    best_time_diff = time_diff

            if best_match:
                matches.append(
                    {
                        "prediction": pred,
                        "actual": best_match,
                        "time_diff_hours": best_time_diff.total_seconds() / 3600,
                    }
                )

        return matches

    def _calculate_metrics(self, matches: list[dict[str, Any]]) -> dict[str, float]:
        """
        Calculate validation metrics from matched prediction-actual pairs.

        Args:
            matches: List of matched pairs

        Returns:
            Dictionary with metrics:
                - mae: Mean Absolute Error (feet)
                - rmse: Root Mean Square Error (feet)
                - categorical_accuracy: Fraction of correct categories (0-1)
                - direction_accuracy: Fraction within tolerance (0-1)
                - sample_size: Number of matches
        """
        if not matches:
            return {
                "mae": None,
                "rmse": None,
                "categorical_accuracy": None,
                "direction_accuracy": None,
                "sample_size": 0,
            }

        # Height errors
        height_errors = []
        for match in matches:
            pred_height = match["prediction"].get("height")
            actual_height = match["actual"].get("wave_height")
            if pred_height is not None and actual_height is not None:
                error = pred_height - actual_height
                height_errors.append(error)

        # Calculate MAE and RMSE
        mae = None
        rmse = None
        if height_errors:
            mae = sum(abs(e) for e in height_errors) / len(height_errors)
            rmse = (sum(e**2 for e in height_errors) / len(height_errors)) ** 0.5

        # Categorical accuracy
        category_matches = []
        for match in matches:
            pred_category = match["prediction"].get("category")
            actual_height = match["actual"].get("wave_height")
            actual_category = self._categorize_height(actual_height)

            if pred_category and actual_category:
                category_matches.append(pred_category == actual_category)

        categorical_accuracy = None
        if category_matches:
            categorical_accuracy = sum(category_matches) / len(category_matches)

        # Direction accuracy
        direction_matches = []
        for match in matches:
            pred_direction = match["prediction"].get("direction")
            actual_direction = match["actual"].get("direction")

            if pred_direction and actual_direction:
                pred_deg = self._direction_to_degrees(pred_direction)
                if pred_deg is not None:
                    angle_diff = self._angular_difference(pred_deg, actual_direction)
                    direction_matches.append(angle_diff <= self.DIRECTION_TOLERANCE)

        direction_accuracy = None
        if direction_matches:
            direction_accuracy = sum(direction_matches) / len(direction_matches)

        return {
            "mae": mae,
            "rmse": rmse,
            "categorical_accuracy": categorical_accuracy,
            "direction_accuracy": direction_accuracy,
            "sample_size": len(matches),
        }

    def _categorize_height(self, height: float | None) -> str | None:
        """
        Categorize wave height into size category.

        Args:
            height: Wave height in feet (Hawaiian scale)

        Returns:
            Category string or None
        """
        if height is None:
            return None

        for category, (min_h, max_h) in self.CATEGORY_THRESHOLDS.items():
            if min_h <= height < max_h:
                return category

        return "extra_large"  # Default for very large waves

    def _direction_to_degrees(self, direction: str) -> float | None:
        """
        Convert compass direction string to degrees.

        Args:
            direction: Compass direction (e.g., 'N', 'NW', 'SSE')

        Returns:
            Degrees (0-360) or None if invalid
        """
        direction_map = {
            "N": 0,
            "NNE": 22.5,
            "NE": 45,
            "ENE": 67.5,
            "E": 90,
            "ESE": 112.5,
            "SE": 135,
            "SSE": 157.5,
            "S": 180,
            "SSW": 202.5,
            "SW": 225,
            "WSW": 247.5,
            "W": 270,
            "WNW": 292.5,
            "NW": 315,
            "NNW": 337.5,
        }

        return direction_map.get(direction.upper())

    def _angular_difference(self, angle1: float, angle2: float) -> float:
        """
        Calculate smallest angular difference between two angles.

        Args:
            angle1: First angle in degrees
            angle2: Second angle in degrees

        Returns:
            Absolute angular difference (0-180 degrees)
        """
        diff = abs(angle1 - angle2)
        if diff > 180:
            diff = 360 - diff
        return diff  # Failing
