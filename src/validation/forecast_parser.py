"""
Forecast Parser for SurfCastAI

Parses generated forecast markdown files to extract structured predictions
for validation against observed buoy data.

Author: SurfCastAI Team
Created: October 2025
"""

import re
import logging
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict


logger = logging.getLogger(__name__)


@dataclass
class ForecastPrediction:
    """Structured forecast prediction extracted from markdown"""
    shore: str  # "North Shore" or "South Shore"
    forecast_time: datetime  # When forecast was issued
    valid_time: datetime  # When prediction is valid for
    day_number: int  # Day 1, 2, 3, etc.

    # Height data (Hawaiian scale)
    height: float  # Average height in feet
    height_min: Optional[float] = None  # Minimum height in feet
    height_max: Optional[float] = None  # Maximum height in feet

    # Period data
    period: Optional[float] = None  # Average period in seconds
    period_min: Optional[float] = None  # Minimum period
    period_max: Optional[float] = None  # Maximum period

    # Direction and category
    direction: Optional[str] = None  # NW, N, NE, etc.
    category: Optional[str] = None  # small, moderate, large, extra_large

    # Confidence
    confidence: float = 0.5  # Parsing confidence (0-1)

    def to_dict(self) -> Dict:
        """Convert to dictionary with ISO format timestamps"""
        data = asdict(self)
        data['forecast_time'] = self.forecast_time.isoformat()
        data['valid_time'] = self.valid_time.isoformat()
        return data


class ForecastParser:
    """Parser for SurfCastAI forecast markdown files"""

    # Regex patterns for extracting forecast data
    PATTERNS = {
        # Height patterns
        'height_range': re.compile(r'(\d+)[–-](\d+)\s*(?:ft|feet)', re.IGNORECASE),
        'height_single': re.compile(r'(\d+)\s*(?:ft|feet)', re.IGNORECASE),
        'height_hawaiian': re.compile(r'\*\*(\d+)[–-](\d+)\s*ft\*\*\s*Hawaiian', re.IGNORECASE),

        # Period patterns
        'period_range': re.compile(r'(\d+)[–-](\d+)\s*(?:s|sec|second)', re.IGNORECASE),
        'period_single': re.compile(r'(\d+)\s*(?:s|sec|second)', re.IGNORECASE),

        # Direction patterns
        'direction': re.compile(r'\b(N|NNE|NE|ENE|E|ESE|SE|SSE|S|SSW|SW|WSW|W|WNW|NW|NNW)\b'),

        # Date patterns
        'date_day': re.compile(r'(?:Day\s*(\d+)|Oct(?:ober)?\s*(\d+))', re.IGNORECASE),
        'forecast_date': re.compile(r'\*Generated on ([A-Za-z]+ \d+, \d{4}) at (\d+:\d+)'),

        # Shore section headers
        'north_shore': re.compile(r'^#+\s*North Shore', re.MULTILINE | re.IGNORECASE),
        'south_shore': re.compile(r'^#+\s*South Shore', re.MULTILINE | re.IGNORECASE),

        # Category indicators
        'category': re.compile(r'\b(small|moderate|large|extra\s*large)\b', re.IGNORECASE),
    }

    # Category thresholds (Hawaiian scale)
    CATEGORY_THRESHOLDS = {
        'small': (0, 4),
        'moderate': (4, 8),
        'large': (8, 12),
        'extra_large': (12, 100),
    }

    def __init__(self):
        """Initialize forecast parser"""
        self.logger = logging.getLogger(self.__class__.__name__)

    def parse_forecast_file(self, file_path: Path) -> List[ForecastPrediction]:
        """
        Parse a forecast markdown file and extract structured predictions.

        Args:
            file_path: Path to forecast markdown file

        Returns:
            List of ForecastPrediction objects

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If file format is invalid
        """
        if not file_path.exists():
            raise FileNotFoundError(f"Forecast file not found: {file_path}")

        self.logger.info(f"Parsing forecast file: {file_path}")

        # Read file content
        content = file_path.read_text(encoding='utf-8')

        # Extract forecast timestamp
        forecast_time = self._extract_forecast_time(content, file_path)

        # Split into shore sections
        sections = self._split_shore_sections(content)

        # Parse each section
        predictions = []
        for shore, section_text in sections.items():
            shore_predictions = self._parse_shore_section(
                shore, section_text, forecast_time
            )
            predictions.extend(shore_predictions)

        self.logger.info(f"Extracted {len(predictions)} predictions from {file_path.name}")
        return predictions

    def _extract_forecast_time(self, content: str, file_path: Path) -> datetime:
        """
        Extract forecast issue time from content or filename.

        Args:
            content: Markdown content
            file_path: Path to file (fallback for timestamp)

        Returns:
            Forecast timestamp
        """
        # Try to extract from content
        match = self.PATTERNS['forecast_date'].search(content)
        if match:
            date_str = match.group(1)
            time_str = match.group(2)
            try:
                # Parse date and time
                dt = datetime.strptime(f"{date_str} {time_str}", "%B %d, %Y %H:%M")
                self.logger.debug(f"Extracted forecast time from content: {dt}")
                return dt
            except ValueError as e:
                self.logger.warning(f"Failed to parse date from content: {e}")

        # Fallback: extract from filename (e.g., forecast_20251006_235037.md)
        filename = file_path.stem
        match = re.search(r'(\d{8})_(\d{6})', filename)
        if match:
            date_str = match.group(1)
            time_str = match.group(2)
            try:
                dt = datetime.strptime(f"{date_str}{time_str}", "%Y%m%d%H%M%S")
                self.logger.debug(f"Extracted forecast time from filename: {dt}")
                return dt
            except ValueError as e:
                self.logger.warning(f"Failed to parse date from filename: {e}")

        # Last resort: use file modification time
        dt = datetime.fromtimestamp(file_path.stat().st_mtime)
        self.logger.warning(f"Using file modification time as forecast time: {dt}")
        return dt

    def _split_shore_sections(self, content: str) -> Dict[str, str]:
        """
        Split content into North Shore and South Shore sections.

        Args:
            content: Full markdown content

        Returns:
            Dictionary with 'North Shore' and 'South Shore' keys
        """
        sections = {}

        # Find North Shore section
        north_match = self.PATTERNS['north_shore'].search(content)
        if north_match:
            north_start = north_match.start()

            # Find end of North Shore section (next major header or South Shore)
            south_match = self.PATTERNS['south_shore'].search(content[north_start:])
            if south_match:
                north_end = north_start + south_match.start()
                sections['North Shore'] = content[north_start:north_end]
                sections['South Shore'] = content[north_end:]
            else:
                sections['North Shore'] = content[north_start:]

        # If no clear sections found, try to extract from daily forecast
        if not sections:
            self.logger.warning("Could not find clear shore sections, parsing entire content")
            sections['North Shore'] = content

        return sections

    def _parse_shore_section(
        self,
        shore: str,
        section_text: str,
        forecast_time: datetime
    ) -> List[ForecastPrediction]:
        """
        Parse a single shore section to extract daily predictions.

        Args:
            shore: Shore name ("North Shore" or "South Shore")
            section_text: Section markdown text
            forecast_time: Forecast issue time

        Returns:
            List of predictions for this shore
        """
        predictions = []

        # Split into lines for analysis
        lines = section_text.split('\n')

        # Track current day context
        current_day = 1
        current_date = forecast_time.date()
        seen_predictions = set()  # Track unique predictions to avoid duplicates

        for i, line in enumerate(lines):
            # Check for day markers
            day_match = self.PATTERNS['date_day'].search(line)
            if day_match:
                day_num = day_match.group(1) or day_match.group(2)
                if day_num:
                    current_day = int(day_num)
                    # Calculate valid date (assume October for Oct X format)
                    if day_match.group(2):  # Oct X format
                        day_of_month = int(day_match.group(2))
                        current_date = forecast_time.replace(day=day_of_month).date()
                    else:  # Day X format
                        current_date = (forecast_time + timedelta(days=current_day - 1)).date()

            # Look for height patterns
            height_data = self._extract_height(line)
            if not height_data:
                continue

            # Skip if this looks like a detailed technical line (too many numbers)
            # Focus on summary forecast lines
            if not self._is_forecast_summary_line(line):
                continue

            # Create unique key to avoid duplicate predictions
            pred_key = (
                shore,
                current_day,
                height_data.get('height_min'),
                height_data.get('height_max'),
            )
            if pred_key in seen_predictions:
                continue
            seen_predictions.add(pred_key)

            # Build prediction
            prediction = ForecastPrediction(
                shore=shore,
                forecast_time=forecast_time,
                valid_time=datetime.combine(current_date, datetime.min.time()),
                day_number=current_day,
                height=height_data['height'],
                height_min=height_data.get('height_min'),
                height_max=height_data.get('height_max'),
            )

            # Extract additional data from same line
            prediction.period, prediction.period_min, prediction.period_max = self._extract_period(line)
            prediction.direction = self._extract_direction(line)
            prediction.category = self._determine_category(height_data['height'], line)
            prediction.confidence = self._calculate_confidence(height_data, prediction)

            predictions.append(prediction)
            self.logger.debug(
                f"Parsed {shore} Day {current_day}: "
                f"{prediction.height_min}-{prediction.height_max}ft, "
                f"{prediction.period}s, {prediction.direction}"
            )

        return predictions

    def _is_forecast_summary_line(self, line: str) -> bool:
        """
        Determine if a line is a forecast summary (vs technical detail).

        Args:
            line: Line of text

        Returns:
            True if this looks like a forecast summary line
        """
        # Skip lines with bullets that look like component breakdowns
        if re.search(r'^\s*[-•]\s*(?:N|NNE|NE|NW|NNW|SSE)\s*@', line):
            return False

        # Skip lines that start with numbers (component lists)
        if re.match(r'^\s*\d+\)', line):
            return False

        # Look for summary indicators
        summary_indicators = [
            r'Expected:?\s*\*\*',  # Expected: **6-8 ft**
            r'commonly\s*\*\*',    # commonly **6-8 ft**
            r'Timing/size:',       # Timing/size: essentially quiet
            r'size will be',       # size will be modest
            r'Overall:',           # Overall: small
        ]

        for pattern in summary_indicators:
            if re.search(pattern, line, re.IGNORECASE):
                return True

        # If line has Hawaiian in it, it's likely a summary
        if 'Hawaiian' in line and 'ft' in line:
            return True

        # If it's a simple sentence with height and period, likely a summary
        if re.search(r'\d+[-–]\d+\s*(?:ft|feet).*\d+[-–]\d+\s*(?:s|sec)', line, re.IGNORECASE):
            # But not if it has @ symbol (component)
            if '@' not in line:
                return True

        return False

    def _extract_height(self, text: str) -> Optional[Dict[str, float]]:
        """
        Extract height information from text.

        Args:
            text: Line of text

        Returns:
            Dictionary with height, height_min, height_max or None
        """
        # Try Hawaiian scale range (most specific)
        match = self.PATTERNS['height_hawaiian'].search(text)
        if match:
            height_min = float(match.group(1))
            height_max = float(match.group(2))
            return {
                'height': (height_min + height_max) / 2,
                'height_min': height_min,
                'height_max': height_max,
            }

        # Try general height range
        match = self.PATTERNS['height_range'].search(text)
        if match:
            height_min = float(match.group(1))
            height_max = float(match.group(2))
            return {
                'height': (height_min + height_max) / 2,
                'height_min': height_min,
                'height_max': height_max,
            }

        # Try single height value
        match = self.PATTERNS['height_single'].search(text)
        if match:
            height = float(match.group(1))
            return {
                'height': height,
                'height_min': height,
                'height_max': height,
            }

        return None

    def _extract_period(self, text: str) -> Tuple[Optional[float], Optional[float], Optional[float]]:
        """
        Extract period information from text.

        Args:
            text: Line of text

        Returns:
            Tuple of (period, period_min, period_max)
        """
        # Try period range
        match = self.PATTERNS['period_range'].search(text)
        if match:
            period_min = float(match.group(1))
            period_max = float(match.group(2))
            period = (period_min + period_max) / 2
            return period, period_min, period_max

        # Try single period
        match = self.PATTERNS['period_single'].search(text)
        if match:
            period = float(match.group(1))
            return period, period, period

        return None, None, None

    def _extract_direction(self, text: str) -> Optional[str]:
        """
        Extract swell direction from text.

        Args:
            text: Line of text

        Returns:
            Direction string (e.g., "NW", "N") or None
        """
        match = self.PATTERNS['direction'].search(text)
        if match:
            return match.group(1)
        return None

    def _determine_category(self, height: float, text: str) -> str:
        """
        Determine wave category from height and text.

        Args:
            height: Wave height in feet (Hawaiian scale)
            text: Line of text (may contain explicit category)

        Returns:
            Category string
        """
        # Try to find explicit category in text
        match = self.PATTERNS['category'].search(text)
        if match:
            category = match.group(1).lower().replace(' ', '_')
            return category

        # Infer from height thresholds
        for category, (min_h, max_h) in self.CATEGORY_THRESHOLDS.items():
            if min_h <= height < max_h:
                return category

        return 'moderate'  # Default fallback

    def _calculate_confidence(
        self,
        height_data: Dict[str, float],
        prediction: ForecastPrediction
    ) -> float:
        """
        Calculate parsing confidence based on extracted data completeness.

        Args:
            height_data: Height extraction results
            prediction: Built prediction object

        Returns:
            Confidence score (0-1)
        """
        confidence = 0.5  # Base confidence

        # Boost for having height range
        if height_data.get('height_min') and height_data.get('height_max'):
            confidence += 0.2

        # Boost for having period
        if prediction.period:
            confidence += 0.15

        # Boost for having direction
        if prediction.direction:
            confidence += 0.1

        # Boost for having category
        if prediction.category:
            confidence += 0.05

        return min(confidence, 1.0)

    def parse_multiple_forecasts(
        self,
        forecast_dir: Path
    ) -> Dict[str, List[ForecastPrediction]]:
        """
        Parse all forecast files in a directory.

        Args:
            forecast_dir: Directory containing forecast markdown files

        Returns:
            Dictionary mapping forecast filenames to prediction lists
        """
        if not forecast_dir.exists():
            raise FileNotFoundError(f"Forecast directory not found: {forecast_dir}")

        results = {}
        forecast_files = sorted(forecast_dir.glob('forecast_*.md'))

        self.logger.info(f"Found {len(forecast_files)} forecast files in {forecast_dir}")

        for file_path in forecast_files:
            try:
                predictions = self.parse_forecast_file(file_path)
                results[file_path.name] = predictions
            except Exception as e:
                self.logger.error(f"Failed to parse {file_path.name}: {e}", exc_info=True)
                results[file_path.name] = []

        total_predictions = sum(len(p) for p in results.values())
        self.logger.info(f"Parsed {total_predictions} total predictions from {len(results)} files")

        return results


def parse_forecast(forecast_path: str) -> List[Dict]:
    """
    Convenience function to parse a single forecast file.

    Args:
        forecast_path: Path to forecast markdown file

    Returns:
        List of prediction dictionaries
    """
    parser = ForecastParser()
    predictions = parser.parse_forecast_file(Path(forecast_path))
    return [p.to_dict() for p in predictions]


if __name__ == '__main__':
    # Example usage
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    if len(sys.argv) < 2:
        print("Usage: python forecast_parser.py <forecast_file_or_directory>")
        sys.exit(1)

    path = Path(sys.argv[1])
    parser = ForecastParser()

    if path.is_file():
        # Parse single file
        predictions = parser.parse_forecast_file(path)
        print(f"\nExtracted {len(predictions)} predictions:")
        for pred in predictions:
            print(f"  {pred.shore} Day {pred.day_number}: "
                  f"{pred.height_min}-{pred.height_max}ft, "
                  f"{pred.period}s, {pred.direction}, "
                  f"category={pred.category}, confidence={pred.confidence:.2f}")

    elif path.is_dir():
        # Parse directory
        results = parser.parse_multiple_forecasts(path)
        print(f"\nParsed {len(results)} forecast files:")
        for filename, predictions in results.items():
            print(f"  {filename}: {len(predictions)} predictions")

    else:
        print(f"Error: {path} is not a file or directory")
        sys.exit(1)
