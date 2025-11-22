"""
Storm Detector for SurfCastAI.

Extracts storm information from GPT-5 pressure chart analysis text
and calculates swell arrival times at Hawaii.

This module parses unstructured text from AI analysis of pressure charts
to identify storms, their characteristics, and predict when resulting
swells will reach Hawaii.
"""

import re
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timezone
from pydantic import BaseModel, Field, field_validator, ConfigDict

from ..utils.swell_propagation import SwellPropagationCalculator, HAWAII_LAT, HAWAII_LON

logger = logging.getLogger(__name__)


class StormInfo(BaseModel):
    """
    Information about a detected storm from pressure chart analysis.
    
    Attributes:
        storm_id: Unique identifier (e.g., "kamchatka_20251008_001")
        location: Geographic coordinates {'lat': float, 'lon': float}
        wind_speed_kt: Wind speed in knots
        central_pressure_mb: Central pressure in millibars (optional)
        fetch_nm: Fetch length in nautical miles (optional)
        duration_hours: Storm duration in hours (optional)
        detection_time: ISO timestamp when storm was detected
        source: Source of detection (default: "pressure_chart_analysis")
        confidence: Confidence score 0.0-1.0
    """
    model_config = ConfigDict(frozen=False)
    
    storm_id: str = Field(..., description="Unique storm identifier")
    location: Dict[str, float] = Field(..., description="Storm coordinates (lat, lon)")
    wind_speed_kt: float = Field(..., gt=0, description="Wind speed in knots")
    central_pressure_mb: Optional[float] = Field(None, ge=900.0, le=1100.0, description="Central pressure in mb")
    fetch_nm: Optional[float] = Field(None, gt=0, description="Fetch length in nautical miles")
    duration_hours: Optional[float] = Field(None, gt=0, description="Storm duration in hours")
    detection_time: str = Field(..., description="ISO timestamp of detection")
    source: str = Field(default="pressure_chart_analysis", description="Detection source")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    
    @field_validator('location')
    @classmethod
    def validate_location(cls, v: Dict[str, float]) -> Dict[str, float]:
        """Validate location has lat and lon keys with valid ranges."""
        if 'lat' not in v or 'lon' not in v:
            raise ValueError("Location must contain 'lat' and 'lon' keys")
        if not (-90 <= v['lat'] <= 90):
            raise ValueError(f"Invalid latitude: {v['lat']}")
        if not (-180 <= v['lon'] <= 180):
            raise ValueError(f"Invalid longitude: {v['lon']}")
        return v


class StormDetector:
    """
    Detects and extracts storm information from pressure chart analysis text.
    
    Features:
    - Robust regex-based parsing of GPT-5 output
    - Geographic coordinate extraction (multiple formats)
    - Storm characteristic inference (wind speed, pressure, fetch)
    - Integration with SwellPropagationCalculator for arrival predictions
    - Graceful degradation (returns empty list if no storms found)
    """
    
    # Regular expression patterns for storm detection
    COORDINATE_PATTERNS = [
        # Pattern: "45°N 155°E" or "45N 155E"
        r'(\d+(?:\.\d+)?)\s*°?\s*([NS])\s+(\d+(?:\.\d+)?)\s*°?\s*([EW])',
        # Pattern: "at 45.5N, 155.2E"
        r'at\s+(\d+(?:\.\d+)?)\s*([NS])[,\s]+(\d+(?:\.\d+)?)\s*([EW])',
        # Pattern: "latitude 45N longitude 155E"
        r'latitude\s+(\d+(?:\.\d+)?)\s*([NS]).*?longitude\s+(\d+(?:\.\d+)?)\s*([EW])',
        # Pattern: "45.5°N, 155.2°E"
        r'(\d+(?:\.\d+)?)\s*°\s*([NS])\s*,\s*(\d+(?:\.\d+)?)\s*°\s*([EW])',
    ]
    
    WIND_SPEED_PATTERNS = [
        r'wind[s]?\s+(?:of\s+)?(\d+(?:\.\d+)?)\s*(?:kt|knots?|kts)',
        r'(\d+(?:\.\d+)?)\s*(?:kt|knots?|kts)\s+winds?',
        r'storm[- ]force\s+winds?\s+(?:of\s+)?(\d+(?:\.\d+)?)',
        r'gale[- ]force.*?(\d+(?:\.\d+)?)\s*(?:kt|knots?)',
    ]
    
    PRESSURE_PATTERNS = [
        r'(?:central\s+)?pressure\s+(?:of\s+)?(\d+(?:\.\d+)?)\s*(?:mb|millibars?|hPa)',
        r'(\d+(?:\.\d+)?)\s*(?:mb|millibars?|hPa)\s+(?:central\s+)?pressure',
        r'drop(?:ping)?\s+(?:to\s+)?(?:below\s+)?(\d+(?:\.\d+)?)\s*(?:mb|millibars?)',
    ]
    
    FETCH_PATTERNS = [
        r'fetch\s+(?:of\s+)?(\d+(?:\.\d+)?)\s*(?:nm|nautical\s+miles?)',
        r'(\d+(?:\.\d+)?)\s*(?:nm|nautical\s+miles?)\s+fetch',
    ]
    
    DURATION_PATTERNS = [
        r'duration\s+(?:of\s+)?(\d+(?:\.\d+)?)\s*(?:hours?|hrs?)',
        r'lasting\s+(\d+(?:\.\d+)?)\s*(?:hours?|hrs?)',
        r'(\d+(?:\.\d+)?)[- ](?:hour|hr)s?\s+(?:storm|system|event)',
        r'(?:for|over)\s+(\d+(?:\.\d+)?)\s*(?:hours?|hrs?)',
        r'persist(?:ing|s?)?\s+(?:for\s+)?(?:at\s+least\s+)?(\d+(?:\.\d+)?)\s*(?:hours?|hrs?)',
    ]
    
    # Named storm regions for identification
    STORM_REGIONS = {
        'kamchatka': (50.0, 157.0),
        'kuril': (46.0, 152.0),
        'aleutian': (52.0, -175.0),
        'gulf_alaska': (55.0, -145.0),
        'tasman': (-42.0, 158.0),
        'southern_ocean': (-50.0, 140.0),
        'new_zealand': (-45.0, 170.0),
    }
    
    def __init__(self):
        """Initialize storm detector with swell propagation calculator."""
        self.logger = logging.getLogger(__name__)
        self.propagation_calc = SwellPropagationCalculator()
        self._compile_patterns()
    
    def _compile_patterns(self) -> None:
        """Compile regex patterns for efficiency."""
        self.coord_re = [re.compile(p, re.IGNORECASE) for p in self.COORDINATE_PATTERNS]
        self.wind_re = [re.compile(p, re.IGNORECASE) for p in self.WIND_SPEED_PATTERNS]
        self.pressure_re = [re.compile(p, re.IGNORECASE) for p in self.PRESSURE_PATTERNS]
        self.fetch_re = [re.compile(p, re.IGNORECASE) for p in self.FETCH_PATTERNS]
        self.duration_re = [re.compile(p, re.IGNORECASE) for p in self.DURATION_PATTERNS]
    
    def parse_pressure_analysis(
        self,
        analysis_text: str,
        timestamp: str
    ) -> List[StormInfo]:
        """
        Parse GPT-5 pressure chart analysis for storm information.
        
        Looks for patterns like:
        - "Low pressure system at 45°N 155°E with central pressure 970mb"
        - "Storm-force winds of 50 knots"
        - "Deepening low near Kamchatka"
        
        Args:
            analysis_text: Raw text from GPT-5 pressure chart analysis
            timestamp: ISO timestamp when analysis was generated
        
        Returns:
            List of detected StormInfo objects (empty if none found)
        """
        if not analysis_text or not analysis_text.strip():
            self.logger.warning("Empty analysis text provided")
            return []
        
        self.logger.info(f"Parsing pressure analysis ({len(analysis_text)} chars)")
        
        # Split into sentences/sections for parsing
        sections = self._split_into_sections(analysis_text)
        
        storms: List[StormInfo] = []
        storm_counter = 0
        
        for section in sections:
            # Look for storm indicators
            if not self._has_storm_indicators(section):
                continue
            
            # Extract coordinates
            coords = self._extract_coordinates(section)
            if not coords:
                # Try to infer from named regions
                coords = self._infer_from_region(section)
            
            if not coords:
                self.logger.debug(f"No coordinates found in section: {section[:100]}")
                continue
            
            # Extract storm characteristics
            wind_speed = self._extract_wind_speed(section)
            pressure = self._extract_pressure(section)
            fetch = self._extract_fetch(section)
            duration = self._extract_duration(section)
            
            # Calculate confidence based on available data
            confidence = self._calculate_confidence(
                coords, wind_speed, pressure, fetch, duration
            )
            
            # Generate storm ID
            storm_counter += 1
            storm_id = self._generate_storm_id(coords, timestamp, storm_counter)
            
            try:
                storm = StormInfo(
                    storm_id=storm_id,
                    location={'lat': coords[0], 'lon': coords[1]},
                    wind_speed_kt=wind_speed,
                    central_pressure_mb=pressure,
                    fetch_nm=fetch,
                    duration_hours=duration,
                    detection_time=timestamp,
                    source="pressure_chart_analysis",
                    confidence=confidence
                )
                
                # Estimate missing parameters
                storm = self.estimate_missing_parameters(storm)
                
                storms.append(storm)
                self.logger.info(
                    f"Detected storm: {storm_id} at {coords[0]:.1f}°N {coords[1]:.1f}°E, "
                    f"{wind_speed}kt, confidence={confidence:.2f}"
                )
            except Exception as e:
                self.logger.error(f"Failed to create StormInfo: {e}")
                continue
        
        self.logger.info(f"Detected {len(storms)} storms from analysis")
        return storms
    
    def _split_into_sections(self, text: str) -> List[str]:
        """Split text into logical sections (sentences or paragraphs)."""
        # Split on sentence boundaries or double newlines
        sections = re.split(r'[.!?]\s+|\n\n+', text)
        return [s.strip() for s in sections if s.strip()]
    
    def _has_storm_indicators(self, text: str) -> bool:
        """Check if text contains storm-related keywords."""
        indicators = [
            'storm', 'low pressure', 'low-pressure', 'depression',
            'cyclone', 'gale', 'fetch', 'deepening', 'intensify',
            'wind', 'pressure system', 'low at', 'low near'
        ]
        text_lower = text.lower()
        return any(indicator in text_lower for indicator in indicators)
    
    def _extract_coordinates(self, text: str) -> Optional[Tuple[float, float]]:
        """
        Extract geographic coordinates from text.
        
        Returns:
            Tuple of (latitude, longitude) or None if not found
        """
        for pattern in self.coord_re:
            match = pattern.search(text)
            if match:
                groups = match.groups()
                lat = float(groups[0])
                lat_dir = groups[1].upper()
                lon = float(groups[2])
                lon_dir = groups[3].upper()
                
                # Apply hemisphere
                if lat_dir == 'S':
                    lat = -lat
                if lon_dir == 'W':
                    lon = -lon
                
                # Validate ranges
                if -90 <= lat <= 90 and -180 <= lon <= 180:
                    return (lat, lon)
        
        return None
    
    def _infer_from_region(self, text: str) -> Optional[Tuple[float, float]]:
        """Infer approximate coordinates from named regions."""
        text_lower = text.lower()
        for region, coords in self.STORM_REGIONS.items():
            if region in text_lower:
                self.logger.debug(f"Inferred coordinates from region: {region}")
                return coords
        return None
    
    def _extract_wind_speed(self, text: str) -> float:
        """Extract wind speed in knots (returns default if not found)."""
        for pattern in self.wind_re:
            match = pattern.search(text)
            if match:
                speed = float(match.group(1))
                if 10 <= speed <= 150:  # Reasonable range
                    return speed
        
        # Default based on storm descriptors
        text_lower = text.lower()
        if 'storm-force' in text_lower or 'storm force' in text_lower:
            return 50.0  # Storm force winds (48-63 kt)
        elif 'gale' in text_lower:
            return 40.0  # Gale force winds (34-47 kt)
        elif 'strong' in text_lower:
            return 35.0  # Strong winds
        
        return 40.0  # Conservative default
    
    def _extract_pressure(self, text: str) -> Optional[float]:
        """Extract central pressure in millibars."""
        for pattern in self.pressure_re:
            match = pattern.search(text)
            if match:
                pressure = float(match.group(1))
                if 900 <= pressure <= 1050:  # Reasonable range for storms
                    return pressure
        return None
    
    def _extract_fetch(self, text: str) -> Optional[float]:
        """Extract fetch length in nautical miles."""
        for pattern in self.fetch_re:
            match = pattern.search(text)
            if match:
                fetch = float(match.group(1))
                if 50 <= fetch <= 2000:  # Reasonable range
                    return fetch
        return None
    
    def _extract_duration(self, text: str) -> Optional[float]:
        """Extract storm duration in hours."""
        for pattern in self.duration_re:
            match = pattern.search(text)
            if match:
                duration = float(match.group(1))
                if 6 <= duration <= 240:  # 6 hours to 10 days
                    return duration
        
        # Infer from descriptors
        text_lower = text.lower()
        if 'long-lived' in text_lower or 'persistent' in text_lower:
            return 72.0  # 3 days
        elif 'brief' in text_lower or 'short' in text_lower:
            return 24.0  # 1 day
        
        return None
    
    def _calculate_confidence(
        self,
        coords: Optional[Tuple[float, float]],
        wind_speed: Optional[float],
        pressure: Optional[float],
        fetch: Optional[float],
        duration: Optional[float]
    ) -> float:
        """
        Calculate confidence score based on available data.
        
        Higher confidence when more parameters are explicitly found.
        """
        confidence = 0.5  # Base confidence
        
        if coords:
            confidence += 0.2  # Explicit coordinates found
        if pressure:
            confidence += 0.15  # Central pressure specified
        if fetch:
            confidence += 0.1  # Fetch length specified
        if duration:
            confidence += 0.05  # Duration specified
        
        return min(1.0, confidence)
    
    def _generate_storm_id(
        self,
        coords: Tuple[float, float],
        timestamp: str,
        counter: int
    ) -> str:
        """Generate unique storm identifier."""
        lat, lon = coords

        # Try to match to known region
        region = 'unknown'
        min_dist = float('inf')
        for region_name, region_coords in self.STORM_REGIONS.items():
            dist = ((lat - region_coords[0]) ** 2 + (lon - region_coords[1]) ** 2) ** 0.5
            if dist < min_dist:
                min_dist = dist
                region = region_name  # Keep closest region name

        # Extract date from timestamp
        try:
            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            date_str = dt.strftime('%Y%m%d')
        except Exception:
            date_str = 'unknown'

        return f"{region}_{date_str}_{counter:03d}"

    def summarise_upper_air(self, products: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Aggregate upper-air chart metadata keyed by pressure level."""
        summary: Dict[str, Any] = {}
        for entry in products or []:
            level = str(entry.get('analysis_level') or entry.get('level') or 'unknown')
            bucket = summary.setdefault(level, {
                'product_type': entry.get('product_type'),
                'products': []
            })
            bucket['products'].append({
                'source_id': entry.get('source_id'),
                'description': entry.get('description'),
                'file_path': entry.get('file_path'),
                'retrieved_at': entry.get('timestamp') or entry.get('retrieved_at')
            })

        return summary

    def summarise_climatology(self, references: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Summarize climatology manifests for forecast context injection."""
        summary: Dict[str, Any] = {}
        for entry in references or []:
            source_id = entry.get('source_id') or entry.get('name')
            if not source_id:
                continue

            summary[source_id] = {
                'format': entry.get('format') or entry.get('type'),
                'description': entry.get('description'),
                'file_path': entry.get('file_path'),
                'line_count': entry.get('line_count'),
                'record_count': entry.get('record_count'),
                'source_url': entry.get('source_url')
            }

        return summary
    
    def estimate_missing_parameters(self, storm: StormInfo) -> StormInfo:
        """
        Fill in missing fetch/duration using defaults or empirical relationships.
        
        Args:
            storm: StormInfo with potentially missing parameters
        
        Returns:
            StormInfo with estimated parameters filled in
        """
        # Estimate fetch from wind speed if missing
        if storm.fetch_nm is None:
            # Empirical relationship: stronger storms have larger fetch
            # Typical fetch: 200-800nm for Pacific storms
            if storm.wind_speed_kt >= 50:
                storm.fetch_nm = 600.0  # Large storm
            elif storm.wind_speed_kt >= 40:
                storm.fetch_nm = 400.0  # Medium storm
            else:
                storm.fetch_nm = 250.0  # Small storm
            self.logger.debug(f"Estimated fetch: {storm.fetch_nm}nm from wind speed {storm.wind_speed_kt}kt")
        
        # Estimate duration from pressure if missing
        if storm.duration_hours is None:
            if storm.central_pressure_mb and storm.central_pressure_mb < 970:
                storm.duration_hours = 72.0  # Deep low = long-lived (3 days)
            elif storm.central_pressure_mb and storm.central_pressure_mb < 990:
                storm.duration_hours = 48.0  # Medium low (2 days)
            else:
                storm.duration_hours = 36.0  # Default (1.5 days)
            self.logger.debug(f"Estimated duration: {storm.duration_hours}hrs from pressure {storm.central_pressure_mb}mb")
        
        return storm
    
    def calculate_hawaii_arrivals(
        self,
        storms: List[StormInfo],
        propagation_calc: Optional[SwellPropagationCalculator] = None
    ) -> List[Dict[str, Any]]:
        """
        For each storm, calculate swell arrival time at Hawaii.
        
        Args:
            storms: List of detected storms
            propagation_calc: Optional custom propagation calculator (uses default if None)
        
        Returns:
            List of arrival predictions with timing, height estimates, and confidence
        """
        if not storms:
            return []
        
        calc = propagation_calc or self.propagation_calc
        arrivals = []
        
        for storm in storms:
            try:
                # Parse detection time
                detection_time = datetime.fromisoformat(
                    storm.detection_time.replace('Z', '+00:00')
                )
                
                # Estimate period from storm characteristics
                period = calc.estimate_period_from_storm(
                    wind_speed_kt=storm.wind_speed_kt,
                    fetch_length_nm=storm.fetch_nm,
                    duration_hours=storm.duration_hours
                )
                
                # Calculate arrival at Hawaii
                arrival_time, details = calc.calculate_arrival(
                    source_lat=storm.location['lat'],
                    source_lon=storm.location['lon'],
                    period_seconds=period,
                    generation_time=detection_time,
                    target_lat=HAWAII_LAT,
                    target_lon=HAWAII_LON
                )
                
                # Estimate wave height (rough empirical formula)
                # Height decreases with distance and increases with wind speed
                distance_factor = max(0.3, 1.0 - (details['distance_nm'] / 5000))
                wind_factor = storm.wind_speed_kt / 50.0  # Normalize to 50kt
                estimated_height_ft = 8.0 * wind_factor * distance_factor
                
                arrival = {
                    'storm_id': storm.storm_id,
                    'storm_location': storm.location,
                    'storm_wind_speed_kt': storm.wind_speed_kt,
                    'storm_central_pressure_mb': storm.central_pressure_mb,
                    'detection_time': storm.detection_time,
                    'arrival_time': arrival_time.isoformat(),
                    'travel_time_hours': details['travel_time_hours'],
                    'travel_time_days': details['travel_time_hours'] / 24,
                    'distance_nm': details['distance_nm'],
                    'estimated_period_seconds': period,
                    'estimated_height_ft': round(estimated_height_ft, 1),
                    'group_velocity_knots': details['group_velocity_knots'],
                    'confidence': storm.confidence,
                }
                
                arrivals.append(arrival)
                
                self.logger.info(
                    f"Storm {storm.storm_id}: "
                    f"Arrival {arrival_time.strftime('%Y-%m-%d %H:%M UTC')}, "
                    f"~{estimated_height_ft:.1f}ft @ {period:.1f}s, "
                    f"travel={details['travel_time_hours']/24:.1f}d"
                )
                
            except Exception as e:
                self.logger.error(f"Failed to calculate arrival for storm {storm.storm_id}: {e}")
                continue
        
        # Sort by arrival time
        arrivals.sort(key=lambda x: x['arrival_time'])
        
        return arrivals


def example_usage():
    """Example of using the storm detector with sample text."""
    detector = StormDetector()
    
    # Sample GPT-5 pressure chart analysis
    analysis_text = """
    The pressure chart shows a significant deepening low-pressure system
    near Kamchatka at approximately 45°N 155°E. Central pressure is 
    forecast to drop below 970 mb by October 9th. Storm-force winds of
    50 knots are expected, with a large fetch over 600 nautical miles.
    This system should persist for 72+ hours, generating long-period
    northwest swell.
    
    Additionally, a secondary low at 50N 165E shows gale-force winds
    of 40 knots with moderate fetch around 400nm.
    """
    
    timestamp = datetime.now(timezone.utc).isoformat()
    
    # Parse for storms
    storms = detector.parse_pressure_analysis(analysis_text, timestamp)
    
    print(f"\n{'='*60}")
    print("DETECTED STORMS")
    print(f"{'='*60}")
    for storm in storms:
        print(f"\nStorm ID: {storm.storm_id}")
        print(f"Location: {storm.location['lat']:.1f}°N {storm.location['lon']:.1f}°E")
        print(f"Wind Speed: {storm.wind_speed_kt} kt")
        print(f"Central Pressure: {storm.central_pressure_mb} mb")
        print(f"Fetch: {storm.fetch_nm} nm")
        print(f"Duration: {storm.duration_hours} hours")
        print(f"Confidence: {storm.confidence:.2f}")
    
    # Calculate Hawaii arrivals
    arrivals = detector.calculate_hawaii_arrivals(storms)
    
    print(f"\n{'='*60}")
    print("HAWAII ARRIVAL PREDICTIONS")
    print(f"{'='*60}")
    for arrival in arrivals:
        arrival_dt = datetime.fromisoformat(arrival['arrival_time'])
        print(f"\nStorm: {arrival['storm_id']}")
        print(f"Arrival: {arrival_dt.strftime('%A %B %d, %I:%M %p UTC')}")
        print(f"Travel Time: {arrival['travel_time_days']:.1f} days")
        print(f"Distance: {arrival['distance_nm']:.0f} nm")
        print(f"Estimated: {arrival['estimated_height_ft']}ft @ {arrival['estimated_period_seconds']:.1f}s")
        print(f"Confidence: {arrival['confidence']:.2f}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    example_usage()
