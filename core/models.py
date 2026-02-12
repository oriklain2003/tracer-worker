from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass(slots=True)
class TrackPoint:
    """
    Track point with memory-optimized storage using __slots__.
    Reduces per-instance memory overhead by ~40 bytes.
    """
    flight_id: str
    timestamp: int
    lat: float
    lon: float
    alt: float
    gspeed: Optional[float] = None
    vspeed: Optional[float] = None
    track: Optional[float] = None
    squawk: Optional[str] = None
    callsign: Optional[str] = None
    source: Optional[str] = None


@dataclass
class FlightTrack:
    flight_id: str
    points: List[TrackPoint] = field(default_factory=list)

    def sorted_points(self) -> List[TrackPoint]:
        return sorted(self.points, key=lambda p: p.timestamp)


@dataclass
class FlightMetadata:
    origin: Optional[str] = None  # Origin airport code (e.g., "LLBG")
    planned_destination: Optional[str] = None
    planned_route: Optional[List[List[float]]] = None  # [[lat, lon], ...]
    # Additional fields for new rules:
    category: Optional[str] = None  # FR24 category (e.g., "passenger", "cargo", "Military_and_government")
    dest_lat: Optional[float] = None  # Destination airport latitude
    dest_lon: Optional[float] = None  # Destination airport longitude
    aircraft_type: Optional[str] = None  # ICAO type code (e.g., "A320", "B738")
    icao_hex: Optional[str] = None  # ICAO 24-bit address / hex code (e.g., "738065")
    aircraft_registration: Optional[str] = None  # Aircraft registration (e.g., "4X-EKA")
    callsign: Optional[str] = None  # Callsign from FR24 (e.g., "ELY001")

@dataclass
class RuleContext:
    track: FlightTrack
    metadata: Optional[FlightMetadata]
    repository: "FlightRepository"


@dataclass
class RuleResult:
    rule_id: int
    matched: bool
    summary: str
    details: Dict[str, object]

