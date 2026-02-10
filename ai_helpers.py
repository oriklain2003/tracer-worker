"""
AI Helper Functions for Flight Anomaly Classification

Provides utility functions for:
- Generating flight map visualizations
- Formatting flight summaries for LLM consumption
- Extracting proximity events from anomaly reports
"""
from __future__ import annotations

import logging
from typing import Dict, List, Optional, Any
import base64
import io

logger = logging.getLogger(__name__)


def generate_flight_map(flight_data: List[Dict], width: int = 800, height: int = 600) -> Optional[bytes]:
    """
    Generate PNG map image bytes from flight track points.
    
    Args:
        flight_data: List of track point dictionaries with 'lat', 'lon' keys
        width: Image width in pixels (default: 800)
        height: Image height in pixels (default: 600)
    
    Returns:
        bytes: PNG image bytes, or None if generation fails
    """
    if not flight_data or len(flight_data) < 2:
        logger.warning("Insufficient flight data for map generation")
        return None
    
    try:
        from staticmap import StaticMap, Line, CircleMarker
        
        m = StaticMap(width, height)
        
        # Extract valid coordinates
        valid_points = [
            (p.get('lon'), p.get('lat')) 
            for p in flight_data
            if p.get('lat') is not None and p.get('lon') is not None
        ]
        
        if len(valid_points) < 2:
            logger.warning("Not enough valid coordinates for map generation")
            return None
        
        # Add flight path line
        line = Line(valid_points, 'blue', 3)
        m.add_line(line)
        
        # Add start marker (green)
        start = CircleMarker(valid_points[0], 'green', 12)
        m.add_marker(start)
        
        # Add end marker (red)
        end = CircleMarker(valid_points[-1], 'red', 12)
        m.add_marker(end)
        
        # Render and return as bytes
        image = m.render()
        buffer = io.BytesIO()
        image.save(buffer, format='PNG')
        buffer.seek(0)
        
        return buffer.getvalue()
        
    except ImportError:
        logger.error("staticmap library not installed - cannot generate map")
        return None
    except Exception as e:
        logger.error(f"Failed to generate flight map: {e}")
        return None


def generate_flight_map_base64(flight_data: List[Dict], width: int = 800, height: int = 600) -> Optional[str]:
    """
    Generate PNG map image as base64 string.
    
    Args:
        flight_data: List of track point dictionaries
        width: Image width in pixels
        height: Image height in pixels
    
    Returns:
        str: Base64-encoded PNG image, or None if generation fails
    """
    image_bytes = generate_flight_map(flight_data, width, height)
    if image_bytes:
        return base64.b64encode(image_bytes).decode('utf-8')
    return None


def format_flight_summary(metadata: Dict, flight_data: List[Dict] = None) -> str:
    """
    Format flight details for LLM consumption.
    
    Args:
        metadata: Flight metadata dictionary with fields like:
            - flight_id, callsign, flight_number
            - airline, aircraft_type, aircraft_model, aircraft_registration
            - origin_airport, destination_airport
            - Various statistics (altitude, speed, duration, etc.)
        flight_data: Optional list of track points
    
    Returns:
        str: Formatted flight summary text
    """
    lines = ["=== FLIGHT SUMMARY ==="]
    
    # Basic identification
    if metadata.get("callsign"):
        lines.append(f"Callsign: {metadata['callsign']}")
    if metadata.get("flight_number"):
        lines.append(f"Flight Number: {metadata['flight_number']}")
    if metadata.get("flight_id"):
        lines.append(f"Flight ID: {metadata['flight_id']}")
    if metadata.get("airline"):
        lines.append(f"Airline/Operator: {metadata['airline']}")
    
    # Aircraft information
    aircraft_info = []
    if metadata.get("aircraft_model"):
        aircraft_info.append(metadata["aircraft_model"])
    if metadata.get("aircraft_type"):
        aircraft_info.append(f"[{metadata['aircraft_type']}]")
    if metadata.get("aircraft_registration"):
        aircraft_info.append(f"(Reg: {metadata['aircraft_registration']})")
    if aircraft_info:
        lines.append(f"Aircraft: {' '.join(aircraft_info)}")
    
    # Origin/Destination
    if metadata.get("origin_airport"):
        lines.append(f"Origin: {metadata['origin_airport']}")
    if metadata.get("destination_airport"):
        lines.append(f"Destination: {metadata['destination_airport']}")
    
    # Flight statistics
    if metadata.get("flight_duration_sec"):
        duration_min = metadata['flight_duration_sec'] / 60
        lines.append(f"Duration: {duration_min:.1f} minutes")
    
    if metadata.get("max_altitude_ft"):
        lines.append(f"Max Altitude: {metadata['max_altitude_ft']:,} ft")
    
    if metadata.get("avg_speed_kts"):
        lines.append(f"Avg Speed: {metadata['avg_speed_kts']:.1f} knots")
    
    # Track info
    if flight_data and len(flight_data) > 0:
        lines.append("")
        lines.append("=== TRACK INFO ===")
        lines.append(f"Total Track Points: {len(flight_data)}")
    elif metadata.get("total_points"):
        lines.append("")
        lines.append("=== TRACK INFO ===")
        lines.append(f"Total Track Points: {metadata['total_points']}")
    
    # Military/Emergency flags
    if metadata.get("is_military"):
        military_type = metadata.get("military_type", "Unknown")
        lines.append(f"\n⚠️ Military Aircraft: {military_type}")
    
    if metadata.get("emergency_squawk_detected"):
        lines.append("\n🚨 Emergency Squawk Detected")
    
    return "\n".join(lines)


def extract_proximity_events(anomaly_report: Dict) -> List[Dict]:
    """
    Extract proximity events from matched rules in anomaly report.
    
    Args:
        anomaly_report: Anomaly report dictionary from pipeline
    
    Returns:
        List of proximity event dictionaries
    """
    proximity_events = []
    
    try:
        # Check layer_1_rules for matched rules
        layer1 = anomaly_report.get('layer_1_rules', {})
        layer1_report = layer1.get('report', {})
        matched_rules = layer1_report.get('matched_rules', [])
        
        for rule in matched_rules:
            # Check if this is a proximity rule (id 4 or name contains proximity/התקרבות)
            is_proximity_rule = (
                rule.get('id') == 4 or 
                'proximity' in str(rule.get('name', '')).lower() or 
                'התקרבות' in str(rule.get('name', ''))
            )
            
            if is_proximity_rule:
                events = rule.get('details', {}).get('events', [])
                if events:
                    for event in events:
                        if isinstance(event, dict):
                            proximity_events.append(event)
        
        logger.debug(f"Extracted {len(proximity_events)} proximity events from anomaly report")
        
    except Exception as e:
        logger.error(f"Failed to extract proximity events: {e}")
    
    return proximity_events


def build_proximity_context(proximity_events: List[Dict]) -> str:
    """
    Build formatted proximity context text for LLM.
    
    Args:
        proximity_events: List of proximity event dictionaries
    
    Returns:
        str: Formatted proximity context text
    """
    if not proximity_events:
        return ""
    
    lines = ["\n=== ⚠️ PROXIMITY ALERT - THIS FLIGHT HAS PROXIMITY EVENTS ==="]
    
    # Generate summary statistics
    total_events = len(proximity_events)
    other_aircraft = set()
    distances = []
    alt_diffs = []
    
    for event in proximity_events:
        callsign = event.get('other_callsign') or event.get('other_flight') or 'Unknown'
        if callsign != 'Unknown':
            other_aircraft.add(callsign)
        
        if event.get('distance_nm') is not None:
            try:
                distances.append(float(event['distance_nm']))
            except (ValueError, TypeError):
                pass
        
        if event.get('altitude_diff_ft') is not None:
            try:
                alt_diffs.append(float(event['altitude_diff_ft']))
            except (ValueError, TypeError):
                pass
    
    # Summary section
    lines.append("\nSUMMARY:")
    lines.append(f"  Total proximity events: {total_events}")
    lines.append(f"  Other aircraft involved: {', '.join(other_aircraft) if other_aircraft else 'Unknown'}")
    
    if distances:
        lines.append(f"  Distance range: {min(distances):.1f} - {max(distances):.1f} NM (min: {min(distances):.1f} NM)")
    if alt_diffs:
        lines.append(f"  Altitude diff range: {min(alt_diffs):.0f} - {max(alt_diffs):.0f} ft")
    
    # Sample up to 5 events (evenly distributed if more than 5)
    if total_events <= 5:
        sampled_events = proximity_events
    else:
        # Sample evenly: first, last, and 3 from middle
        indices = [0]
        step = (total_events - 1) / 4
        for i in range(1, 4):
            indices.append(int(i * step))
        indices.append(total_events - 1)
        sampled_events = [proximity_events[i] for i in indices]
    
    lines.append(f"\nSAMPLED EVENTS ({len(sampled_events)} of {total_events}):")
    for i, event in enumerate(sampled_events, 1):
        other_callsign = event.get('other_callsign') or event.get('other_flight') or 'Unknown'
        distance_nm = event.get('distance_nm', 'Unknown')
        altitude_diff = event.get('altitude_diff_ft', 'Unknown')
        timestamp = event.get('timestamp', 'Unknown')
        
        lines.append(f"  #{i}: {other_callsign} | Dist: {distance_nm} NM | Alt Diff: {altitude_diff} ft | TS: {timestamp}")
    
    lines.append("\nWhen analyzing, consider these proximity events and the other aircraft involved.")
    
    return "\n".join(lines)


def build_anomaly_context(anomaly_report: Dict, metadata: Dict, flight_data: List[Dict]) -> str:
    """
    Build complete context string for AI classification.
    
    Args:
        anomaly_report: Anomaly report from pipeline
        metadata: Flight metadata dictionary
        flight_data: List of track point dictionaries
    
    Returns:
        str: Complete formatted context for LLM
    """
    context_parts = []
    
    # Flight summary
    flight_summary = format_flight_summary(metadata, flight_data)
    context_parts.append(flight_summary)
    
    # Time range
    if flight_data and len(flight_data) >= 2:
        ts0 = flight_data[0].get("timestamp")
        ts1 = flight_data[-1].get("timestamp")
        if ts0 and ts1:
            try:
                from datetime import datetime, timezone
                iso0 = datetime.fromtimestamp(int(ts0), tz=timezone.utc).isoformat()
                iso1 = datetime.fromtimestamp(int(ts1), tz=timezone.utc).isoformat()
                context_parts.append(f"\n=== TIME RANGE ===\nStart: {ts0} ({iso0})\nEnd: {ts1} ({iso1})")
            except Exception:
                context_parts.append(f"\n=== TIME RANGE ===\nStart: {ts0}\nEnd: {ts1}")
    
    # Anomaly analysis
    if anomaly_report:
        context_parts.append("\n=== ANOMALY ANALYSIS ===")
        
        summary = anomaly_report.get('summary', {})
        if summary:
            context_parts.append(f"Is Anomaly: {summary.get('is_anomaly', 'Unknown')}")
            context_parts.append(f"Confidence Score: {summary.get('confidence_score', 'N/A')}%")
            triggers = summary.get('triggers', [])
            if triggers:
                context_parts.append(f"Triggers: {', '.join(triggers)}")
        
        # Extract matched rules
        layer1 = anomaly_report.get('layer_1_rules', {})
        layer1_report = layer1.get('report', {})
        matched_rules = layer1_report.get('matched_rules', [])
        
        if matched_rules:
            context_parts.append("\n=== MATCHED RULES ===")
            for rule in matched_rules:
                rule_name = rule.get('name', f"Rule {rule.get('id')}")
                rule_summary = rule.get('summary', '')
                if rule_summary:
                    context_parts.append(f"  - {rule_name}: {rule_summary}")
                else:
                    context_parts.append(f"  - {rule_name}")
        
        # Add proximity context if applicable
        proximity_events = extract_proximity_events(anomaly_report)
        if proximity_events:
            proximity_text = build_proximity_context(proximity_events)
            context_parts.append(proximity_text)
    
    return "\n".join(context_parts)
