"""
Surf observation data model for ground truth validation.
"""

from datetime import datetime
from typing import Optional
from dataclasses import dataclass


@dataclass
class SurfObservation:
    """
    Ground truth surf observation from a specific location.
    
    Attributes:
        location: Surf break name (e.g., "Sunset Beach", "Pipeline")
        time: Observation time (HST)
        hawaiian_scale: Observed wave height in Hawaiian scale (feet)
        face_height: Observed face height in feet (optional)
        period: Observed period in seconds (optional, estimated)
        direction: Observed swell direction (optional, estimated)
        conditions: Text description (e.g., "clean", "choppy", "blown out")
        observer: Observer name/ID
        confidence: Observer confidence (0-1, based on experience)
        notes: Additional notes
    """
    location: str
    time: datetime
    hawaiian_scale: float
    face_height: Optional[float] = None
    period: Optional[float] = None
    direction: Optional[str] = None
    conditions: Optional[str] = None
    observer: str = "unknown"
    confidence: float = 0.8
    notes: Optional[str] = None
    
    def to_dict(self):
        """Convert to dictionary."""
        return {
            'location': self.location,
            'time': self.time.isoformat(),
            'hawaiian_scale': self.hawaiian_scale,
            'face_height': self.face_height,
            'period': self.period,
            'direction': self.direction,
            'conditions': self.conditions,
            'observer': self.observer,
            'confidence': self.confidence,
            'notes': self.notes
        }
    
    @classmethod
    def from_dict(cls, data: dict):
        """Create from dictionary."""
        data['time'] = datetime.fromisoformat(data['time'])
        return cls(**data)
