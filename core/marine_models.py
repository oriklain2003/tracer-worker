"""
Marine Data Models

Dataclasses for vessel tracking data from AISstream.io.
Uses __slots__ for memory optimization following the pattern in models.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from datetime import datetime


@dataclass(slots=True)
class VesselPosition:
    """
    Vessel position report from AIS (message types 1, 2, 3, 18).
    Memory-optimized storage using __slots__.
    """
    mmsi: str  # Maritime Mobile Service Identity (unique vessel identifier)
    timestamp: datetime
    latitude: float
    longitude: float
    speed_over_ground: Optional[float] = None  # knots
    course_over_ground: Optional[float] = None  # degrees (0-360)
    heading: Optional[int] = None  # degrees (0-359)
    navigation_status: Optional[str] = None  # e.g., "Under way using engine"
    rate_of_turn: Optional[float] = None  # degrees per minute
    position_accuracy: Optional[bool] = None  # True = high (<10m), False = low (>10m)
    message_type: Optional[int] = None  # AIS message type (1, 2, 3, 18, etc.)
    
    @classmethod
    def from_ais_message(cls, msg: dict) -> Optional[VesselPosition]:
        """
        Parse AIS message JSON into VesselPosition dataclass.
        
        Example message structure from AISstream.io:
        {
            "MessageType": "PositionReport",
            "MetaData": {"MMSI": "368207620", "ShipName": "VESSEL_NAME", ...},
            "Message": {
                "PositionReport": {
                    "Latitude": 37.8,
                    "Longitude": -122.4,
                    "Sog": 12.3,
                    "Cog": 45.6,
                    "TrueHeading": 48,
                    "NavigationalStatus": 0,
                    "RateOfTurn": -2.5,
                    "PositionAccuracy": true,
                    "Timestamp": "2026-02-12T10:30:00Z"
                }
            }
        }
        """
        try:
            metadata = msg.get("MetaData", {})
            message = msg.get("Message", {})
            position_report = message.get("PositionReport", {})
            
            if not position_report:
                return None
            
            mmsi = str(metadata.get("MMSI", ""))
            if not mmsi:
                return None
            
            # Parse timestamp
            timestamp_val = position_report.get("Timestamp")
            if timestamp_val:
                # Handle both ISO string format and Unix timestamp (integer)
                if isinstance(timestamp_val, str):
                    # ISO format with timezone
                    timestamp = datetime.fromisoformat(timestamp_val.replace('Z', '+00:00'))
                elif isinstance(timestamp_val, (int, float)):
                    # Validate it's a reasonable Unix timestamp (after 2000-01-01)
                    # Unix timestamp for 2000-01-01 is 946684800
                    if timestamp_val > 946684800:
                        # Unix timestamp - use utcfromtimestamp for UTC time
                        timestamp = datetime.utcfromtimestamp(timestamp_val)
                    else:
                        # Invalid timestamp, likely a field number or other value
                        # Use current time instead
                        timestamp = datetime.utcnow()
                else:
                    timestamp = datetime.utcnow()
            else:
                timestamp = datetime.utcnow()
            
            # Navigation status mapping
            nav_status_map = {
                0: "Under way using engine",
                1: "At anchor",
                2: "Not under command",
                3: "Restricted manoeuvrability",
                4: "Constrained by her draught",
                5: "Moored",
                6: "Aground",
                7: "Engaged in fishing",
                8: "Under way sailing",
                9: "Reserved for HSC",
                10: "Reserved for WIG",
                11: "Reserved",
                12: "Reserved",
                13: "Reserved",
                14: "AIS-SART",
                15: "Not defined"
            }
            
            nav_status_code = position_report.get("NavigationalStatus")
            nav_status = nav_status_map.get(nav_status_code, "Unknown") if nav_status_code is not None else None
            
            return cls(
                mmsi=mmsi,
                timestamp=timestamp,
                latitude=position_report.get("Latitude"),
                longitude=position_report.get("Longitude"),
                speed_over_ground=position_report.get("Sog"),  # Speed Over Ground
                course_over_ground=position_report.get("Cog"),  # Course Over Ground
                heading=position_report.get("TrueHeading"),
                navigation_status=nav_status,
                rate_of_turn=position_report.get("RateOfTurn"),
                position_accuracy=position_report.get("PositionAccuracy"),
                message_type=message.get("MessageType", 1)
            )
        except Exception as e:
            # Log parse errors but don't crash
            import logging
            logging.getLogger(__name__).error(f"Failed to parse vessel position: {e}")
            return None


@dataclass(slots=True)
class VesselMetadata:
    """
    Vessel static data and voyage information from AIS (message types 5, 24).
    Updated less frequently than position reports (typically every 6 minutes).
    """
    mmsi: str
    vessel_name: Optional[str] = None
    callsign: Optional[str] = None
    imo_number: Optional[str] = None  # International Maritime Organization number
    vessel_type: Optional[int] = None  # AIS ship type code
    vessel_type_description: Optional[str] = None
    length: Optional[int] = None  # meters (total length)
    width: Optional[int] = None  # meters (beam)
    draught: Optional[float] = None  # meters (draft)
    destination: Optional[str] = None
    eta: Optional[datetime] = None  # Estimated time of arrival
    cargo_type: Optional[int] = None
    dimension_to_bow: Optional[int] = None  # meters
    dimension_to_stern: Optional[int] = None  # meters
    dimension_to_port: Optional[int] = None  # meters
    dimension_to_starboard: Optional[int] = None  # meters
    position_fixing_device: Optional[int] = None  # 1=GPS, 2=GLONASS, etc.
    
    @classmethod
    def from_ais_message(cls, msg: dict) -> Optional[VesselMetadata]:
        """
        Parse AIS static data message JSON into VesselMetadata dataclass.
        
        Example message structure from AISstream.io:
        {
            "MessageType": "ShipStaticData",
            "MetaData": {"MMSI": "368207620", "ShipName": "EVER GIVEN", ...},
            "Message": {
                "ShipStaticData": {
                    "Name": "EVER GIVEN",
                    "CallSign": "HPEM",
                    "ImoNumber": 9811000,
                    "Type": 70,
                    "Dimension": {
                        "A": 143,
                        "B": 107,
                        "C": 12,
                        "D": 11
                    },
                    "Draught": 14.5,
                    "Destination": "SINGAPORE",
                    "Eta": {"Month": 3, "Day": 15, "Hour": 14, "Minute": 30},
                    "FixType": 1
                }
            }
        }
        """
        try:
            metadata = msg.get("MetaData", {})
            message = msg.get("Message", {})
            static_data = message.get("ShipStaticData", {})
            
            if not static_data:
                return None
            
            mmsi = str(metadata.get("MMSI", ""))
            if not mmsi:
                return None
            
            # Ship type mapping (subset of common types)
            ship_type_map = {
                0: "Not available",
                20: "Wing in ground",
                21: "Wing in ground (hazardous category A)",
                22: "Wing in ground (hazardous category B)",
                23: "Wing in ground (hazardous category C)",
                24: "Wing in ground (hazardous category D)",
                30: "Fishing",
                31: "Towing",
                32: "Towing (large)",
                33: "Dredging or underwater ops",
                34: "Diving ops",
                35: "Military ops",
                36: "Sailing",
                37: "Pleasure craft",
                40: "High speed craft",
                50: "Pilot vessel",
                51: "Search and rescue",
                52: "Tug",
                53: "Port tender",
                54: "Anti-pollution equipment",
                55: "Law enforcement",
                58: "Medical transport",
                59: "Noncombatant ship",
                60: "Passenger",
                61: "Passenger (hazardous category A)",
                62: "Passenger (hazardous category B)",
                63: "Passenger (hazardous category C)",
                64: "Passenger (hazardous category D)",
                70: "Cargo",
                71: "Cargo (hazardous category A)",
                72: "Cargo (hazardous category B)",
                73: "Cargo (hazardous category C)",
                74: "Cargo (hazardous category D)",
                80: "Tanker",
                81: "Tanker (hazardous category A)",
                82: "Tanker (hazardous category B)",
                83: "Tanker (hazardous category C)",
                84: "Tanker (hazardous category D)",
                90: "Other",
            }
            
            vessel_type_code = static_data.get("Type")
            vessel_type_desc = ship_type_map.get(vessel_type_code, "Unknown") if vessel_type_code is not None else None
            
            # Parse dimensions
            dimension = static_data.get("Dimension", {})
            dim_a = dimension.get("A")  # Distance to bow from reference point
            dim_b = dimension.get("B")  # Distance to stern from reference point
            dim_c = dimension.get("C")  # Distance to port from reference point
            dim_d = dimension.get("D")  # Distance to starboard from reference point
            
            # Calculate total length and width
            length = (dim_a + dim_b) if dim_a and dim_b else None
            width = (dim_c + dim_d) if dim_c and dim_d else None
            
            # Parse ETA
            eta = None
            eta_dict = static_data.get("Eta", {})
            if eta_dict and all(k in eta_dict for k in ["Month", "Day", "Hour", "Minute"]):
                try:
                    # Assume current year if not specified
                    current_year = datetime.utcnow().year
                    eta = datetime(
                        current_year,
                        eta_dict["Month"],
                        eta_dict["Day"],
                        eta_dict["Hour"],
                        eta_dict["Minute"]
                    )
                except (ValueError, KeyError):
                    eta = None
            
            # IMO number
            imo = static_data.get("ImoNumber")
            imo_str = str(imo) if imo else None
            
            return cls(
                mmsi=mmsi,
                vessel_name=static_data.get("Name"),
                callsign=static_data.get("CallSign"),
                imo_number=imo_str,
                vessel_type=vessel_type_code,
                vessel_type_description=vessel_type_desc,
                length=length,
                width=width,
                draught=static_data.get("Draught"),
                destination=static_data.get("Destination"),
                eta=eta,
                cargo_type=static_data.get("CargoType"),
                dimension_to_bow=dim_a,
                dimension_to_stern=dim_b,
                dimension_to_port=dim_c,
                dimension_to_starboard=dim_d,
                position_fixing_device=static_data.get("FixType")
            )
        except Exception as e:
            # Log parse errors but don't crash
            import logging
            logging.getLogger(__name__).error(f"Failed to parse vessel metadata: {e}")
            return None
