"""Numeric utility functions for safe data type conversions."""

import logging
from typing import Optional, Union

logger = logging.getLogger(__name__)


def safe_float(
    value: Union[str, float, int, None],
    min_val: Optional[float] = None,
    max_val: Optional[float] = None,
    field_name: str = "value"
) -> Optional[float]:
    """
    Safely convert a value to float with optional bounds validation.

    Handles various input types and edge cases including:
    - None values
    - Empty strings
    - Non-numeric strings
    - Already-numeric types (int, float)
    - Whitespace
    - String ranges like "10-15" (returns average)
    - Strings with units like "10 mph" (extracts numeric part)

    Args:
        value: Value to convert to float
        min_val: Minimum allowed value (inclusive). If specified, values below
                 this will return None with a warning logged.
        max_val: Maximum allowed value (inclusive). If specified, values above
                 this will return None with a warning logged.
        field_name: Name of the field for logging purposes (default: "value")

    Returns:
        Converted float value, or None if conversion fails or out of bounds

    Examples:
        >>> safe_float("3.14")
        3.14
        >>> safe_float("invalid", min_val=0.0)
        None
        >>> safe_float(None)
        None
        >>> safe_float("  2.5  ")
        2.5
        >>> safe_float("10-15")  # Range - returns average
        12.5
        >>> safe_float("10 mph")  # Unit string - extracts number
        10.0
        >>> safe_float(42.0, min_val=0.0, max_val=100.0)
        42.0
        >>> safe_float(-5.0, min_val=0.0, field_name="temperature")
        None  # Logs warning: "Rejecting temperature=-5.0: below minimum 0.0"
    """
    if value is None:
        return None

    try:
        # Handle different input types
        if isinstance(value, (int, float)):
            result = float(value)
        elif isinstance(value, str):
            value = value.strip()
            if not value:
                return None

            # Handle strings with units like "10 mph"
            if ' ' in value:
                value = value.split(' ')[0]

            # Handle range strings like "10-15"
            if '-' in value and not value.startswith('-'):
                # Avoid treating negative numbers as ranges
                parts = value.split('-')
                if len(parts) == 2:
                    try:
                        low = float(parts[0])
                        high = float(parts[1])
                        result = (low + high) / 2
                    except ValueError:
                        # If range parsing fails, try normal float conversion
                        result = float(value)
                else:
                    result = float(value)
            else:
                result = float(value)
        else:
            # Unsupported type
            return None

        # Check bounds if specified
        if min_val is not None and result < min_val:
            logger.warning(
                f"Rejecting {field_name}={result}: below minimum {min_val}"
            )
            return None

        if max_val is not None and result > max_val:
            logger.warning(
                f"Rejecting {field_name}={result}: above maximum {max_val}"
            )
            return None

        return result

    except (ValueError, TypeError):
        return None
