"""
Realtime Flight Monitor

Fetches live flights from FlightRadar24, analyzes them for anomalies using
the AnomalyPipeline, and saves results to live_research.db with the same
schema as research_replay.py (research_new.db).

Features:
- Saves to live_research.db with full metadata schema
- Uses INSERT OR IGNORE for track points (no duplicates)
- Updates anomaly reports per flight (INSERT OR REPLACE)
- Cleans up stale flights (not seen in 10 minutes)
- Calculates comprehensive flight metadata
"""

from __future__ import annotations

import sys
import time
import json
import logging
import io
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Add root to path for imports
sys.path.append(str(Path(__file__).resolve().parent.parent))
FILTER_EXCLUDED_PREFIXES = ("4XC", "4XB", "CHLE", "4XA", "HMR")

from fr24sdk.client import Client
from fr24sdk.models.geographic import Boundary
from anomaly_pipeline import AnomalyPipeline
from core.models import FlightTrack, TrackPoint, FlightMetadata
from core.config import TRAIN_NORTH, TRAIN_SOUTH, TRAIN_EAST, TRAIN_WEST
from core.geodesy import haversine_nm
from core.military_detection import is_military

# Set up logging BEFORE importing PostgreSQL provider
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')),
        logging.FileHandler("live_monitor.log", encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# Import PostgreSQL provider
try:
    from pg_provider import (
        save_flight_metadata as pg_save_metadata,
        save_flight_tracks as pg_save_tracks,
        save_anomaly_report as pg_save_report,
        init_connection_pool,
        check_schema_exists,
        test_connection
    )
    PG_AVAILABLE = True
    logger.info("PostgreSQL provider loaded successfully")
except ImportError as e:
    PG_AVAILABLE = False
    logger.error(f"PostgreSQL provider not available: {e}")
    sys.exit(1)  # Exit if PostgreSQL is not available

# --- Configuration ---
# Use absolute path relative to this script's location
SCRIPT_DIR = Path(__file__).resolve().parent
DB_PATH = SCRIPT_DIR / "live_research.db"

# Use the EXACT bounding box used for training to avoid OOD data
MIN_LAT = TRAIN_SOUTH
MAX_LAT = TRAIN_NORTH
MIN_LON = TRAIN_WEST
MAX_LON = TRAIN_EAST

API_TOKEN = "019aca50-8288-7260-94b5-6d82fbeb351c|dC21vuw2bsf2Y43qAlrBKb7iSM9ibqSDT50x3giN763b577b"

# Optimized polling strategy to reduce FR24 API costs
DISCOVERY_SCAN_INTERVAL = 45  # Full bbox scan to find NEW flights (seconds)
UPDATE_SCAN_INTERVAL = 8  # Quick position updates for tracked flights (seconds)
MIN_POINTS_FOR_ANALYSIS = 20  # Need some history for ML models
STALE_FLIGHT_TIMEOUT = 600  # 10 minutes - remove flights not seen

# ============================================================================
# AIRPORTS DATA - Loaded from docs/airports.csv for origin/destination calculation
# ============================================================================

_AIRPORTS_DATA: List[Dict] = []
_AIRPORTS_BY_CODE: Dict[str, Dict] = {}  # For quick lookup by ICAO/IATA code

def _load_airports_data():
    """Load airports from docs/airports.csv for origin/destination calculation."""
    global _AIRPORTS_DATA, _AIRPORTS_BY_CODE
    if _AIRPORTS_DATA:
        return  # Already loaded
    
    import csv
    
    # Always use airports.csv relative to this file in ./docs/airports.csv
    airports_path = Path(__file__).parent / "docs" / "airports.csv"
    
    if not airports_path.exists():
        logger.warning(f"Airports data not found at {airports_path}")
        return
    
    try:
        with open(airports_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Skip airports without valid coordinates
                try:
                    lat = float(row.get('latitude_deg', ''))
                    lon = float(row.get('longitude_deg', ''))
                except (ValueError, TypeError):
                    continue
                
                # Skip closed airports
                airport_type = row.get('type', '')
                if airport_type == 'closed':
                    continue
                
                # Get airport codes
                icao_code = row.get('ident') or row.get('icao_code')
                iata_code = row.get('iata_code')
                
                airport_data = {
                    "ident": row.get("ident"),
                    "icao_code": icao_code,
                    "iata_code": iata_code,
                    "name": row.get("name"),
                    "type": airport_type,
                    "lat": lat,
                    "lon": lon,
                    "country": row.get("iso_country"),
                    "municipality": row.get("municipality"),
                }
                
                _AIRPORTS_DATA.append(airport_data)
                
                # Index by codes for quick lookup
                if icao_code:
                    _AIRPORTS_BY_CODE[icao_code] = airport_data
                if iata_code:
                    _AIRPORTS_BY_CODE[iata_code] = airport_data
        
        logger.info(f"Loaded {len(_AIRPORTS_DATA)} airports for origin/destination calculation")
    except Exception as e:
        logger.error(f"Failed to load airports data: {e}")


# Legacy fallback - Known Airports Database (Major airports in the region)
KNOWN_AIRPORTS = {
    "LLBG": {"name": "Ben Gurion", "lat": 32.0114, "lon": 34.8867, "country": "Israel"},
    "LLET": {"name": "Eilat Ramon", "lat": 29.7231, "lon": 35.0128, "country": "Israel"},
    "LLHA": {"name": "Haifa", "lat": 32.8094, "lon": 35.0428, "country": "Israel"},
    "LLOV": {"name": "Ovda", "lat": 29.9403, "lon": 34.9358, "country": "Israel"},
    "LLRM": {"name": "Ramon", "lat": 30.7761, "lon": 35.0358, "country": "Israel"},
    "LLHZ": {"name": "Herzliya", "lat": 32.1856, "lon": 34.8408, "country": "Israel"},
    "LLIB": {"name": "Sde Dov", "lat": 32.1147, "lon": 34.7822, "country": "Israel"},
    "OJAI": {"name": "Amman", "lat": 31.7226, "lon": 35.9932, "country": "Jordan"},
    "OJAM": {"name": "Marka", "lat": 31.9727, "lon": 35.9916, "country": "Jordan"},
    "OJAQ": {"name": "Aqaba", "lat": 29.6117, "lon": 35.0181, "country": "Jordan"},
    "OLBA": {"name": "Beirut", "lat": 33.8209, "lon": 35.4884, "country": "Lebanon"},
    "OSDI": {"name": "Damascus", "lat": 33.4114, "lon": 36.5156, "country": "Syria"},
    "HEAR": {"name": "Cairo", "lat": 30.1219, "lon": 31.4056, "country": "Egypt"},
    "HETB": {"name": "Taba", "lat": 29.5878, "lon": 34.7781, "country": "Egypt"},
    "HECA": {"name": "Cairo Int'l", "lat": 30.1219, "lon": 31.4056, "country": "Egypt"},
    "LCLK": {"name": "Larnaca", "lat": 34.875, "lon": 33.6249, "country": "Cyprus"},
    "LCPH": {"name": "Paphos", "lat": 34.718, "lon": 32.4857, "country": "Cyprus"},
    "LTAI": {"name": "Antalya", "lat": 36.8987, "lon": 30.8005, "country": "Turkey"},
}


def get_airport_by_code(code: str) -> Optional[Dict]:
    """Get airport info by ICAO or IATA code."""
    _load_airports_data()
    
    # Try CSV data first
    if code in _AIRPORTS_BY_CODE:
        return _AIRPORTS_BY_CODE[code]
    
    # Fallback to legacy dict
    if code in KNOWN_AIRPORTS:
        info = KNOWN_AIRPORTS[code]
        return {"icao_code": code, "lat": info["lat"], "lon": info["lon"], "name": info["name"]}
    
    return None


def find_nearest_airport(lat: float, lon: float, max_distance_nm: float = 10.0) -> Optional[Tuple[str, Dict, float]]:
    """
    Find the nearest airport to a given coordinate using airports.csv.
    Returns (icao_code, airport_data, distance_nm) or None if not found within range.
    """
    _load_airports_data()
    
    nearest = None
    min_dist = float('inf')
    
    # First try the comprehensive airports.csv data
    if _AIRPORTS_DATA:
        for airport in _AIRPORTS_DATA:
            dist = haversine_nm(lat, lon, airport["lat"], airport["lon"])
            if dist < min_dist and dist <= max_distance_nm:
                min_dist = dist
                code = airport.get("icao_code") or airport.get("iata_code") or airport.get("ident")
                nearest = (code, airport, dist)
    else:
        # Fallback to legacy KNOWN_AIRPORTS if CSV not loaded
        for icao, info in KNOWN_AIRPORTS.items():
            dist = haversine_nm(lat, lon, info["lat"], info["lon"])
            if dist < min_dist and dist <= max_distance_nm:
                min_dist = dist
                nearest = (icao, info, dist)
    
    return nearest


def detect_country(lat: float, lon: float) -> str:
    """Rough country detection based on lat/lon boundaries."""
    if 29.5 <= lat <= 33.3 and 34.3 <= lon <= 35.9:
        return "Israel"
    elif 33.0 <= lat <= 34.7 and 35.1 <= lon <= 36.7:
        return "Lebanon"
    elif 32.3 <= lat <= 37.3 and 35.7 <= lon <= 42.4:
        return "Syria"
    elif 29.2 <= lat <= 33.4 and 34.9 <= lon <= 39.3:
        return "Jordan"
    elif 22.0 <= lat <= 31.7 and 24.7 <= lon <= 36.9:
        return "Egypt"
    elif 34.6 <= lat <= 35.7 and 32.3 <= lon <= 34.6:
        return "Cyprus"
    else:
        return "Unknown"


class FlightMetadataCalculator:
    """Calculate comprehensive metadata for a flight track."""
    
    # Common airlines mapping (ICAO code -> Full name)
    AIRLINE_MAP = {
        'ELY': 'El Al', 'ISR': 'Israir', 'AIZ': 'Arkia',
        'RYR': 'Ryanair', 'BAW': 'British Airways', 'DLH': 'Lufthansa',
        'AFR': 'Air France', 'UAE': 'Emirates', 'QTR': 'Qatar Airways',
        'THY': 'Turkish Airlines', 'RJA': 'Royal Jordanian',
        'MEA': 'Middle East Airlines', 'WZZ': 'Wizz Air',
        'JZR': 'Jazeera Airways', 'SAS': 'Scandinavian Airlines',
        'WMT': 'Wizz Air Malta', 'SVA': 'Saudia', 'MSR': 'EgyptAir',
        'ETD': 'Etihad Airways', 'GFA': 'Gulf Air', 'KAC': 'Kuwait Airways',
        'OMA': 'Oman Air', 'FDB': 'flydubai', 'ABY': 'Air Arabia',
        'PGT': 'Pegasus Airlines', 'AEE': 'Aegean Airlines',
        'TRA': 'Transavia', 'EZY': 'easyJet', 'VLG': 'Vueling'
    }
    
    @staticmethod
    def calculate(flight: FlightTrack, fr24_summary: Optional[Dict] = None, icao_hex: Optional[str] = None) -> Dict:
        """Calculate all metadata for a flight."""
        points = flight.sorted_points()
        if not points:
            return {}
        
        # Basic identification
        callsign = next((p.callsign for p in points if p.callsign), None)
        aircraft_registration = fr24_summary.get("reg") if fr24_summary else None
        category = fr24_summary.get("category") if fr24_summary else None
        
        # Military detection
        is_military_flag, military_org_info = is_military(
            callsign=callsign, 
            aircraft_registration=aircraft_registration,
            category=category
        )
        
        # Time range
        first_ts = points[0].timestamp
        last_ts = points[-1].timestamp
        duration_sec = last_ts - first_ts
        
        # Position
        start_lat, start_lon = points[0].lat, points[0].lon
        end_lat, end_lon = points[-1].lat, points[-1].lon
        
        # Airport detection - try multiple possible field names from FR24 API
        origin_airport_code = None
        origin_airport_data = None
        dest_airport_code = None
        dest_airport_data = None
        
        if fr24_summary:
            # Try multiple possible field names for origin (FR24 API can use different naming)
            origin_airport_code = (
                fr24_summary.get("orig_icao") or 
                fr24_summary.get("orig_iata") or 
                fr24_summary.get("origin_icao") or
                fr24_summary.get("origin_iata") or
                fr24_summary.get("schd_from") or
                fr24_summary.get("origin") or
                fr24_summary.get("departure_airport") or
                fr24_summary.get("dep_icao") or
                fr24_summary.get("dep_iata")
            )
            # Try multiple possible field names for destination
            dest_airport_code = (
                fr24_summary.get("dest_icao") or 
                fr24_summary.get("dest_iata") or 
                fr24_summary.get("destination_icao") or
                fr24_summary.get("destination_iata") or
                fr24_summary.get("schd_to") or
                fr24_summary.get("destination") or
                fr24_summary.get("arrival_airport") or
                fr24_summary.get("arr_icao") or
                fr24_summary.get("arr_iata")
            )
            
            # Look up airport data from airports.csv
            if origin_airport_code:
                origin_airport_data = get_airport_by_code(origin_airport_code)
            
            if dest_airport_code:
                dest_airport_data = get_airport_by_code(dest_airport_code)
            
            # Debug log what fields are actually available
            logger.debug(f"FR24 summary fields for airport detection: {list(fr24_summary.keys())}")
        
        # Fallback to coordinate-based detection
        if not origin_airport_code:
            nearest_origin = find_nearest_airport(start_lat, start_lon, max_distance_nm=10.0)
            if nearest_origin:
                origin_airport_code = nearest_origin[0]
                origin_airport_data = nearest_origin[1]
        
        if not dest_airport_code:
            nearest_dest = find_nearest_airport(end_lat, end_lon, max_distance_nm=10.0)
            if nearest_dest:
                dest_airport_code = nearest_dest[0]
                dest_airport_data = nearest_dest[1]
        
        # Altitude statistics
        altitudes = [p.alt for p in points if p.alt is not None]
        min_alt = min(altitudes) if altitudes else None
        max_alt = max(altitudes) if altitudes else None
        avg_alt = sum(altitudes) / len(altitudes) if altitudes else None
        
        cruise_altitudes = [a for a in altitudes if a > 10000]
        cruise_alt = sum(cruise_altitudes) / len(cruise_altitudes) if cruise_altitudes else None
        
        # Speed statistics
        speeds = [p.gspeed for p in points if p.gspeed is not None]
        min_speed = min(speeds) if speeds else None
        max_speed = max(speeds) if speeds else None
        avg_speed = sum(speeds) / len(speeds) if speeds else None
        
        # Distance calculation
        total_distance = 0.0
        for i in range(len(points) - 1):
            total_distance += haversine_nm(
                points[i].lat, points[i].lon,
                points[i + 1].lat, points[i + 1].lon
            )
        
        # Squawk analysis
        squawks = set()
        emergency_squawk = False
        for p in points:
            if p.squawk:
                squawks.add(p.squawk)
                if p.squawk in ['7500', '7600', '7700']:
                    emergency_squawk = True
        
        # Flight phases
        phases = FlightMetadataCalculator._calculate_phases(points)
        
        # Geographic context
        countries = set()
        for p in points[::max(1, len(points)//20)]:
            country = detect_country(p.lat, p.lon)
            if country != "Unknown":
                countries.add(country)
        
        # Signal quality
        signal_loss_events = FlightMetadataCalculator._detect_signal_loss(points)
        expected_points = duration_sec // 10 if duration_sec > 0 else len(points)
        data_quality = min(1.0, len(points) / max(1, expected_points)) if expected_points > 0 else 1.0
        
        # Parse airline info
        airline = None
        airline_code = None
        aircraft_type = None
        aircraft_model = None
        scheduled_departure = None
        scheduled_arrival = None
        flight_number = callsign
        category = None
        
        if fr24_summary:
            # Airline code - try multiple possible field names
            airline_code = (
                fr24_summary.get("operating_as") or 
                fr24_summary.get("painted_as") or
                fr24_summary.get("airline_icao") or
                fr24_summary.get("airline_iata") or
                fr24_summary.get("airline_code") or
                fr24_summary.get("operator")
            )
            # Aircraft info - try multiple possible field names
            aircraft_type = (
                fr24_summary.get("type") or 
                fr24_summary.get("aircraft_code") or
                fr24_summary.get("equip") or
                fr24_summary.get("aircraft_type")
            )
            aircraft_model = (
                fr24_summary.get("type") or 
                fr24_summary.get("aircraft") or
                fr24_summary.get("aircraft_model")
            )
            aircraft_registration = (
                fr24_summary.get("reg") or 
                fr24_summary.get("registration") or
                fr24_summary.get("aircraft_registration")
            )
            # Schedule info
            scheduled_departure = (
                fr24_summary.get("datetime_takeoff") or
                fr24_summary.get("schd_dep") or
                fr24_summary.get("scheduled_departure") or
                fr24_summary.get("act_dep") or
                fr24_summary.get("actual_departure")
            )
            scheduled_arrival = (
                fr24_summary.get("datetime_landed") or
                fr24_summary.get("schd_arr") or
                fr24_summary.get("scheduled_arrival") or
                fr24_summary.get("act_arr") or
                fr24_summary.get("actual_arrival")
            )
            # Flight number
            flight_number = (
                fr24_summary.get("flight") or 
                fr24_summary.get("flight_number") or
                fr24_summary.get("flight_iata") or
                fr24_summary.get("flight_icao") or
                callsign
            )
            # Callsign - try multiple field names
            fr24_callsign = (
                fr24_summary.get("callsign") or
                fr24_summary.get("call_sign") or
                fr24_summary.get("cs")
            )
            if fr24_callsign:
                callsign = fr24_callsign
            # Category
            category = fr24_summary.get("category")
        
        if airline_code and not airline:
            airline = FlightMetadataCalculator.AIRLINE_MAP.get(airline_code, airline_code)
        
        if not airline and callsign and len(callsign) >= 3:
            fallback_airline_code = callsign[:3].upper()
            airline = FlightMetadataCalculator.AIRLINE_MAP.get(fallback_airline_code, fallback_airline_code)
            if not airline_code:
                airline_code = fallback_airline_code
        
        # Extract hex from FR24 summary if not passed explicitly
        hex_code = icao_hex
        if not hex_code and fr24_summary:
            hex_code = fr24_summary.get("hex")
        
        return {
            'flight_id': flight.flight_id,
            'callsign': callsign,
            'flight_number': flight_number,
            'airline': airline,
            'airline_code': airline_code,
            'aircraft_type': aircraft_type,
            'aircraft_model': aircraft_model,
            'aircraft_registration': aircraft_registration,
            'icao_hex': hex_code,
            'origin_airport': origin_airport_code,
            'origin_lat': origin_airport_data['lat'] if origin_airport_data else start_lat,
            'origin_lon': origin_airport_data['lon'] if origin_airport_data else start_lon,
            'destination_airport': dest_airport_code,
            'dest_lat': dest_airport_data['lat'] if dest_airport_data else end_lat,
            'dest_lon': dest_airport_data['lon'] if dest_airport_data else end_lon,
            'first_seen_ts': first_ts,
            'last_seen_ts': last_ts,
            'scheduled_departure': scheduled_departure,
            'scheduled_arrival': scheduled_arrival,
            'flight_duration_sec': duration_sec,
            'total_distance_nm': round(total_distance, 2),
            'total_points': len(points),
            'min_altitude_ft': min_alt,
            'max_altitude_ft': max_alt,
            'avg_altitude_ft': round(avg_alt, 2) if avg_alt else None,
            'cruise_altitude_ft': round(cruise_alt, 2) if cruise_alt else None,
            'min_speed_kts': min_speed,
            'max_speed_kts': max_speed,
            'avg_speed_kts': round(avg_speed, 2) if avg_speed else None,
            'start_lat': start_lat,
            'start_lon': start_lon,
            'end_lat': end_lat,
            'end_lon': end_lon,
            'squawk_codes': ','.join(sorted(squawks)) if squawks else None,
            'emergency_squawk_detected': emergency_squawk,
            'is_military': is_military_flag,
            'military_type': military_org_info if is_military_flag else None,
            'flight_phase_summary': json.dumps(phases),
            'nearest_airport_start': origin_airport_code,
            'nearest_airport_end': dest_airport_code,
            'crossed_borders': ','.join(sorted(countries)) if countries else None,
            'signal_loss_events': signal_loss_events,
            'data_quality_score': round(data_quality, 3),
            'created_at': int(time.time()),
            'updated_at': int(time.time()),
            'category': category
        }
    
    @staticmethod
    def _calculate_phases(points: List[TrackPoint]) -> Dict[str, int]:
        """Classify flight phases based on altitude and position."""
        phases = {
            'ground': 0, 'departure': 0, 'cruise': 0,
            'approach': 0, 'holding': 0, 'unknown': 0
        }
        
        if len(points) < 2:
            return phases
        
        for i in range(len(points) - 1):
            p = points[i]
            duration = points[i + 1].timestamp - p.timestamp
            
            if p.alt is None:
                phases['unknown'] += duration
                continue
            
            if p.alt < 500:
                phases['ground'] += duration
            elif p.alt > 10000 and (p.vspeed is None or abs(p.vspeed) < 500):
                phases['cruise'] += duration
            elif p.alt < 10000 and p.vspeed and p.vspeed > 500:
                phases['departure'] += duration
            elif p.vspeed and p.vspeed < -500:
                phases['approach'] += duration
            else:
                phases['unknown'] += duration
        
        return phases
    
    @staticmethod
    def _detect_signal_loss(points: List[TrackPoint]) -> int:
        """Count signal loss events (gaps > 2 minutes)."""
        if len(points) < 2:
            return 0
        
        loss_count = 0
        for i in range(len(points) - 1):
            gap = points[i + 1].timestamp - points[i].timestamp
            if gap >= 120:
                loss_count += 1
        
        return loss_count


class FlightState:
    """Tracks the history of a single flight in memory."""
    
    def __init__(self, flight_id: str):
        self.flight_id = flight_id
        self.points: List[TrackPoint] = []
        self.last_update = 0.0
        self.last_analyzed_count = 0
        self.was_anomaly = False  # Track if previously flagged as anomaly
        self.fr24_summary: Optional[Dict] = None  # FR24 summary data for metadata
        self.full_track_loaded = False  # Track if we've loaded the full historical track
        self.icao_hex: Optional[str] = None  # ICAO 24-bit hex address from FR24

    def add_point(self, point: TrackPoint):
        """Add a new point if timestamp is newer than the last one."""
        if not self.points or point.timestamp > self.points[-1].timestamp:
            self.points.append(point)
            self.last_update = time.time()

    def to_flight_track(self) -> FlightTrack:
        return FlightTrack(flight_id=self.flight_id, points=self.points)


class RealtimeMonitor:
    def __init__(self):
        self.client = Client(api_token=API_TOKEN)
        self.boundary = Boundary(
            north=MAX_LAT,
            south=MIN_LAT,
            west=MIN_LON,
            east=MAX_LON
        )
        self.active_flights: Dict[str, FlightState] = {}
        self.schema = 'live'  # PostgreSQL schema for live monitoring
        self.db_path = DB_PATH  # Legacy path reference
        self.setup_db()
        
        # Initialize anomaly pipeline with PostgreSQL enabled
        self.pipeline = AnomalyPipeline(use_postgres=True)
        
        # Initialize AI Classifier (optional - requires GEMINI_API_KEY)
        gemini_api_key = os.getenv("GEMINI_API_KEY", "AIzaSyBArSFAlxqm-9q1hWbaNgeT7f3WMOqF5Go")
        if gemini_api_key:
            try:
                from ai_classify import AIClassifier
                self.ai_classifier = AIClassifier(gemini_api_key, schema=self.schema)
                logger.info("✨ AI Classifier initialized successfully")
            except Exception as e:
                logger.warning(f"Failed to initialize AI Classifier: {e}")
                self.ai_classifier = None
        else:
            self.ai_classifier = None
            logger.info("AI Classification disabled (GEMINI_API_KEY not set)")
        
        # Track last discovery scan time for optimized polling
        self.last_discovery_scan = 0.0
        self.scan_cycle_count = 0  # For logging stats

    def setup_db(self):
        """Initialize PostgreSQL connection and verify schema."""
        # Initialize connection pool
        if not init_connection_pool():
            logger.error("Failed to initialize PostgreSQL connection pool")
            sys.exit(1)
        
        # Test connection
        if not test_connection():
            logger.error("PostgreSQL connection test failed")
            sys.exit(1)
        
        # Check if schema exists
        if not check_schema_exists(self.schema):
            logger.error(f"PostgreSQL schema '{self.schema}' does not exist. Run migration script first!")
            sys.exit(1)
        
        logger.info(f"PostgreSQL connected successfully (schema: {self.schema})")

    def save_tracks(self, flight: FlightTrack, is_anomaly: bool):
        """Save track points to PostgreSQL."""
        try:
            success = pg_save_tracks(flight, is_anomaly, schema=self.schema)
            if not success:
                logger.error(f"Failed to save tracks for {flight.flight_id}")
        except Exception as e:
            logger.error(f"Error saving tracks to PostgreSQL: {e}", exc_info=True)

    def save_metadata(self, metadata: Dict):
        """Save flight metadata to PostgreSQL."""
        try:
            success = pg_save_metadata(metadata, schema=self.schema)
            if not success:
                logger.error(f"Failed to save metadata for {metadata.get('flight_id')}")
        except Exception as e:
            logger.error(f"Error saving metadata to PostgreSQL: {e}", exc_info=True)

    def save_report(self, report: dict, timestamp: int, metadata: Dict):
        """Save anomaly report to PostgreSQL."""
        try:
            success = pg_save_report(report, timestamp, metadata, schema=self.schema)
            if not success:
                logger.error(f"Failed to save report for {report['summary']['flight_id']}")
        except Exception as e:
            logger.error(f"Error saving report to PostgreSQL: {e}", exc_info=True)

    def cleanup_stale_flights(self):
        """Remove flights from memory that haven't been seen recently."""
        now = time.time()
        to_remove = []
        
        for fid, state in self.active_flights.items():
            if now - state.last_update > STALE_FLIGHT_TIMEOUT:
                to_remove.append(fid)
        
        for fid in to_remove:
            del self.active_flights[fid]
            logger.info(f"Dropped stale flight: {fid}")
        
        return len(to_remove)

    def is_monitoring_active(self) -> bool:
        """Check if monitoring is active by querying public.monitor_status table."""
        try:
            from pg_provider import get_connection
            with get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT is_active FROM public.monitor_status LIMIT 1")
                    result = cursor.fetchone()
                    if result:
                        return bool(result[0])
                    else:
                        logger.warning("No monitor_status record found, defaulting to inactive")
                        return False
        except Exception as e:
            logger.error(f"Failed to check monitor status: {e}")
            return False

    def discovery_scan(self):
        """
        Full bbox scan to discover NEW flights.
        This is the expensive operation - only do periodically.
        """
        logger.info("🔍 DISCOVERY SCAN: Fetching all flights in bounding box...")
        response = self.client.live.flight_positions.get_full(
            bounds=self.boundary,
            altitude_ranges=["1000-50000"]
        )
        time.sleep(1)
        live_data = response.model_dump()["data"]
        
        new_flights = 0
        updated_flights = 0
        
        logger.info(f"Found {len(live_data)} flights in bounding box")
        
        for item in live_data:
            flight_id = item["fr24_id"]
            
            # Check callsign prefixes
            if item.get("callsign"):
                callsign = item["callsign"].strip().upper()
                if callsign.startswith(FILTER_EXCLUDED_PREFIXES):
                    continue
            
            # Check if this is a NEW flight
            is_new_flight = flight_id not in self.active_flights
            
            if is_new_flight:
                new_flights += 1
                self.active_flights[flight_id] = FlightState(flight_id)
                logger.info(f"✨ NEW FLIGHT: {flight_id} ({item.get('callsign', 'N/A')})")
                
                # Fetch full historical track for new flight ONLY
                self._load_full_track(flight_id)
                
                # Fetch flight summary for metadata
                self._load_flight_summary(flight_id)
            else:
                updated_flights += 1
            
            # Add current position to state
            state = self.active_flights[flight_id]
            
            # Capture hex code (ICAO 24-bit address) from FR24 live data
            if item.get("hex") and not state.icao_hex:
                state.icao_hex = item["hex"]
                logger.debug(f"Captured hex {state.icao_hex} for {flight_id}")
            
            self._add_position_point(state, item)
        
        self.last_discovery_scan = time.time()
        logger.info(f"✅ Discovery scan complete: {new_flights} new, {updated_flights} updated")
        return new_flights, updated_flights
    
    def update_scan(self):
        """
        Quick position updates for flights we're already tracking.
        This reuses the bbox scan but skips expensive full track fetches.
        """
        logger.info("⚡ UPDATE SCAN: Refreshing positions for tracked flights...")
        response = self.client.live.flight_positions.get_full(
            bounds=self.boundary,
            altitude_ranges=["1000-50000"]
        )
        time.sleep(1)
        live_data = response.model_dump()["data"]
        current_ids = set()
        updated_count = 0
        
        for item in live_data:
            flight_id = item["fr24_id"]
            current_ids.add(flight_id)
            
            # Check callsign prefixes
            if item.get("callsign"):
                callsign = item["callsign"].strip().upper()
                if callsign.startswith(FILTER_EXCLUDED_PREFIXES):
                    continue
            
            # Only update tracked flights - ignore new ones until next discovery scan
            if flight_id in self.active_flights:
                state = self.active_flights[flight_id]
                
                # Capture hex code if not yet captured
                if item.get("hex") and not state.icao_hex:
                    state.icao_hex = item["hex"]
                
                self._add_position_point(state, item)
                updated_count += 1
        
        # Mark flights no longer in bbox (but don't delete yet - they might return)
        missing = set(self.active_flights.keys()) - current_ids
        if missing:
            logger.debug(f"{len(missing)} flights temporarily out of view")
        
        logger.info(f"✅ Update scan complete: {updated_count} positions updated")
        return updated_count
    
    def _load_full_track(self, flight_id: str):
        """Load complete historical track for a flight (expensive operation)."""
        try:
            hist_resp = self.client.flight_tracks.get(flight_id=flight_id)
            time.sleep(1)
            if hist_resp:
                flight_data = hist_resp.model_dump()["data"][0]
                track_points = flight_data.get("tracks", [])
                
                for tp in track_points:
                    ts_str = tp["timestamp"]
                    if isinstance(ts_str, str):
                        ts_hist = int(datetime.fromisoformat(ts_str.replace("Z", "+00:00")).timestamp())
                    else:
                        ts_hist = ts_str
                    
                    p_hist = TrackPoint(
                        flight_id=flight_id,
                        timestamp=ts_hist,
                        lat=tp["lat"],
                        lon=tp["lon"],
                        alt=tp["alt"],
                        gspeed=tp.get("gspeed"),
                        vspeed=tp.get("vspeed"),
                        track=tp.get("track"),
                        squawk=str(tp.get("squawk")) if tp.get("squawk") else None,
                        callsign=tp.get("callsign"),
                        source=tp.get("source"),
                    )
                    self.active_flights[flight_id].add_point(p_hist)
                
                self.active_flights[flight_id].full_track_loaded = True
                logger.info(f"📥 Loaded {len(track_points)} historical points for {flight_id}")
        except Exception as e:
            logger.warning(f"Could not fetch history for {flight_id}: {e}")
    
    def _load_flight_summary(self, flight_id: str):
        """Load flight summary metadata (origin, dest, aircraft type, etc)."""
        try:
            summary_resp = self.client.flight_summary.get_full(flight_ids=[flight_id])
            time.sleep(1)
            if summary_resp:
                summary_data = summary_resp.model_dump()["data"]
                if summary_data:
                    self.active_flights[flight_id].fr24_summary = summary_data[0]
                    fr24_sum = self.active_flights[flight_id].fr24_summary
                    
                    # Extract key metadata for logging
                    callsign = fr24_sum.get("callsign") or fr24_sum.get("call_sign") or fr24_sum.get("cs")
                    flight_number = fr24_sum.get("flight") or fr24_sum.get("flight_number")
                    aircraft_reg = fr24_sum.get("reg") or fr24_sum.get("registration")
                    aircraft_type = fr24_sum.get("type") or fr24_sum.get("aircraft_code")
                    origin = fr24_sum.get("orig_icao") or fr24_sum.get("origin_icao") or fr24_sum.get("schd_from")
                    dest = fr24_sum.get("dest_icao") or fr24_sum.get("destination_icao") or fr24_sum.get("schd_to")
                    
                    # Capture hex code from summary if not already set
                    hex_code = fr24_sum.get("hex")
                    if hex_code and not self.active_flights[flight_id].icao_hex:
                        self.active_flights[flight_id].icao_hex = hex_code
                    
                    logger.info(f"📋 Loaded summary for {flight_id}: {callsign} | {flight_number} | "
                               f"{aircraft_type} ({aircraft_reg}) | {origin}→{dest} | hex={hex_code}")
        except Exception as e:
            logger.debug(f"Could not fetch summary for {flight_id}: {e}")
    
    def _add_position_point(self, state: FlightState, item: Dict):
        """Add a position point to flight state."""
        # Parse timestamp
        ts = item.get("timestamp")
        if isinstance(ts, str):
            ts = int(datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp())
        
        # Get callsign from FR24 summary if available, otherwise from item
        fr24_summary = state.fr24_summary
        callsign = (fr24_summary.get("callsign") if fr24_summary else None) or item.get("callsign")
        
        # Create new point
        point = TrackPoint(
            flight_id=state.flight_id,
            timestamp=ts or int(time.time()),
            lat=item["lat"],
            lon=item["lon"],
            alt=item.get("alt", 0),
            gspeed=item.get("gspeed"),
            vspeed=item.get("vspeed"),
            track=item.get("track"),
            squawk=item.get("squawk"),
            callsign=callsign,
            source=item.get("source")
        )
        state.add_point(point)
    
    def fetch_and_process(self):
        """
        Optimized fetch strategy:
        - Full discovery scan every 45s (finds new flights, loads their full tracks)
        - Quick update scan every 8s (just position updates for tracked flights)
        This reduces API costs dramatically while keeping data fresh.
        """
        try:
            self.scan_cycle_count += 1
            current_time = time.time()
            time_since_discovery = current_time - self.last_discovery_scan
            
            # Decide which type of scan to do
            if time_since_discovery >= DISCOVERY_SCAN_INTERVAL:
                # Time for expensive discovery scan
                new_count, update_count = self.discovery_scan()
            else:
                # Quick update scan for existing flights only
                update_count = self.update_scan()
                new_count = 0
            
            # Process all tracked flights for anomaly detection
            analyzed_count = 0
            for flight_id, state in list(self.active_flights.items()):
                # Check if ready for analysis (every 5 new points)
                if len(state.points) >= MIN_POINTS_FOR_ANALYSIS:
                    if len(state.points) - state.last_analyzed_count >= 5:
                        # Check if we have at least 10 points above 5000 ft
                        points_above_5000 = sum(1 for p in state.points if p.alt is not None and p.alt > 5000)
                        if points_above_5000 < 10:
                            logger.debug(f"Skipping {flight_id}: only {points_above_5000} points above 5000 ft (need 10)")
                            continue
                        
                        # Run Pipeline
                        track = state.to_flight_track()
                        
                        # Calculate comprehensive metadata dict with FR24 summary
                        metadata_dict = FlightMetadataCalculator.calculate(
                            track, fr24_summary=state.fr24_summary, icao_hex=state.icao_hex
                        )
                        
                        # Convert dict to FlightMetadata object for rule engine
                        # The rule engine needs origin, destination, route, hex, and more
                        metadata_obj = FlightMetadata(
                                origin=metadata_dict.get('origin_airport'),
                                planned_destination=metadata_dict.get('destination_airport'),
                                category=metadata_dict.get('category'),
                                dest_lat=metadata_dict.get('dest_lat'),
                                dest_lon=metadata_dict.get('dest_lon'),
                                aircraft_type=metadata_dict.get('aircraft_type'),
                                icao_hex=metadata_dict.get('icao_hex'),
                                aircraft_registration=metadata_dict.get('aircraft_registration'),
                                callsign=metadata_dict.get('callsign'),
                        )
                        
                        # Run analysis with FlightMetadata object
                        report = self.pipeline.analyze(track, metadata=metadata_obj)
                        is_anomaly = report["summary"]["is_anomaly"]
                        
                        # Add anomaly flag to metadata dict for saving
                        metadata_dict['is_anomaly'] = is_anomaly
                        
                        # Save comprehensive metadata dict
                        self.save_metadata(metadata_dict)
                        
                        # Save tracks
                        self.save_tracks(track, is_anomaly)
                        
                        # Save/update report
                        last_ts = track.points[-1].timestamp if track.points else int(time.time())
                        self.save_report(report, last_ts, metadata_dict)
                        
                        # Trigger AI classification for anomalies (async, non-blocking)
                        if is_anomaly and self.ai_classifier:
                            # Convert track points to dictionaries for AI classifier
                            flight_data_dicts = [
                                {
                                    "timestamp": p.timestamp,
                                    "lat": p.lat,
                                    "lon": p.lon,
                                    "alt": p.alt,
                                    "gspeed": p.gspeed,
                                    "vspeed": p.vspeed,
                                    "track": p.track,
                                    "squawk": p.squawk,
                                    "callsign": p.callsign
                                }
                                for p in track.points
                            ]
                            
                            # Trigger async classification
                            self.ai_classifier.classify_async(
                                flight_id=flight_id,
                                flight_data=flight_data_dicts,
                                anomaly_report=report,
                                metadata=metadata_dict
                            )
                            logger.info(f"🤖 Triggered AI classification for {flight_id}")
                        
                        # Log status change
                        if is_anomaly and not state.was_anomaly:
                            logger.warning(f" ANOMALY DETECTED: {flight_id} ({metadata_dict.get('callsign', 'N/A')})")
                        elif not is_anomaly and state.was_anomaly:
                            logger.info(f"✅ ANOMALY CLEARED: {flight_id} now normal")
                        
                        state.was_anomaly = is_anomaly
                        state.last_analyzed_count = len(state.points)
                        analyzed_count += 1
            
            # Cleanup stale flights
            removed = self.cleanup_stale_flights()
            
            # Log cycle summary
            logger.info(f"📊 Cycle #{self.scan_cycle_count} complete: "
                       f"{len(self.active_flights)} active flights | "
                       f"{analyzed_count} analyzed | "
                       f"{removed} removed | "
                       f"Next discovery in {int(DISCOVERY_SCAN_INTERVAL - time_since_discovery)}s")
            
        except Exception as e:
            logger.error(f"Fetch loop error: {e}", exc_info=True)

    def run(self):
        """Main monitoring loop with optimized two-phase scanning."""
        logger.info("=" * 80)
        logger.info("🚀 Starting Optimized Realtime Monitor")
        logger.info("=" * 80)
        logger.info(f"📍 Bounding Box: Lat {MIN_LAT}-{MAX_LAT}, Lon {MIN_LON}-{MAX_LON}")
        logger.info(f"⏱️  Discovery Scan: Every {DISCOVERY_SCAN_INTERVAL}s (finds new flights + full tracks)")
        logger.info(f"⚡ Update Scan: Every {UPDATE_SCAN_INTERVAL}s (position updates only)")
        logger.info(f"🗑️  Stale Timeout: {STALE_FLIGHT_TIMEOUT}s")
        logger.info(f"💰 Cost Savings: ~{int(DISCOVERY_SCAN_INTERVAL/UPDATE_SCAN_INTERVAL)}x fewer expensive API calls")
        logger.info("=" * 80)
        
        # Track heartbeat and errors for health monitoring
        last_heartbeat = time.time()
        consecutive_errors = 0
        max_consecutive_errors = 5
        
        while True:
            try:
                # Heartbeat log every 5 minutes
                if time.time() - last_heartbeat >= 300:
                    logger.info(f"💓 HEARTBEAT: Service alive. Active flights: {len(self.active_flights)}, "
                               f"Scan cycle: {self.scan_cycle_count}, Consecutive errors: {consecutive_errors}")
                    last_heartbeat = time.time()
                
                # Check if monitoring is active
                try:
                    is_active = self.is_monitoring_active()
                except Exception as e:
                    logger.error(f"Failed to check monitor status: {e}. Assuming inactive.", exc_info=True)
                    is_active = False
                
                if is_active:
                    self.fetch_and_process()
                    consecutive_errors = 0  # Reset error counter on success
                    time.sleep(UPDATE_SCAN_INTERVAL)
                else:
                    logger.info("Monitor is inactive, sleeping...")
                    time.sleep(UPDATE_SCAN_INTERVAL)
                    
            except KeyboardInterrupt:
                logger.info("Received keyboard interrupt, shutting down...")
                break
            except Exception as e:
                consecutive_errors += 1
                logger.error(f"CRITICAL ERROR in main loop (error {consecutive_errors}/{max_consecutive_errors}): {e}", 
                           exc_info=True)
                
                if consecutive_errors >= max_consecutive_errors:
                    logger.critical(f"Too many consecutive errors ({consecutive_errors}). Exiting...")
                    break
                
                # Back off exponentially on errors
                sleep_time = min(60, UPDATE_SCAN_INTERVAL * (2 ** consecutive_errors))
                logger.info(f"Sleeping {sleep_time}s before retry...")
                time.sleep(sleep_time)
        
        # Cleanup on exit
        logger.info("Shutting down monitor...")
        if self.ai_classifier:
            self.ai_classifier.shutdown(wait=True)
        logger.info("Monitor shutdown complete")


if __name__ == "__main__":
    monitor = RealtimeMonitor()
    monitor.run()
