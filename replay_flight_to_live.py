"""
Flight Replay Script - Research → Live with Real-time Simulation

Simulates how anomalies appear in live monitoring by replaying flights from 
the research schema into the live schema with real-time delays between points.

Features:
- Load flight from research.flight_tracks or research.normal_tracks (fallback)
- Bulk insert points up to a specified timestamp instantly
- Replay remaining points with real-time delays preserved
- Adjust timestamps to appear as "happening now"
- Run anomaly pipeline incrementally
- Save all data to live schema

Usage:
    python replay_flight_to_live.py 3d7211ef
    python replay_flight_to_live.py 3d7211ef --start-timestamp 1707580800
    python replay_flight_to_live.py 3d7211ef --start-timestamp 1707580800 --interval 10
"""

from __future__ import annotations

import sys
import time
import json
import logging
import argparse
import uuid
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import psycopg2.extras

# Add root to path for imports
sys.path.append(str(Path(__file__).resolve().parent))

from anomaly_pipeline import AnomalyPipeline
from core.models import FlightTrack, TrackPoint, FlightMetadata
from pg_provider import (
    get_connection, 
    init_connection_pool,
    save_flight_tracks,
    save_flight_metadata,
    save_anomaly_report
)

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
MIN_POINTS_FOR_ANALYSIS = 20  # Minimum points needed for anomaly detection


def load_flight_from_research(
    flight_id: str, 
    source_schema: str = 'feedback'
) -> Tuple[List[Dict], Dict, Optional[Dict]]:
    """
    Load flight tracks and metadata from source schema.
    
    Tries anomaly_tracks first, then falls back to normal_tracks and flight_tracks.
    
    Args:
        flight_id: Flight ID to load
        source_schema: Schema name (default: 'research')
        
    Returns:
        (track_points, metadata_dict, anomaly_report_dict)
    """
    logger.info(f"Loading flight {flight_id} from {source_schema} schema...")
    
    with get_connection() as conn:
        with conn.cursor() as cursor:
            # Try anomaly_tracks first
            cursor.execute(f"""
                SELECT flight_id, timestamp, lat, lon, alt, gspeed, vspeed, 
                       track, squawk, callsign, source
                FROM {source_schema}.flight_tracks
                WHERE flight_id = %s
                ORDER BY timestamp ASC
            """, (flight_id,))
            
            rows = cursor.fetchall()
            table_source = f"{source_schema}.flight_tracks"
            
            # If not found, try normal_tracks
            if not rows:
                logger.info(f"Flight not found in flight_tracks, trying normal_tracks...")
                cursor.execute(f"""
                    SELECT flight_id, timestamp, lat, lon, alt, gspeed, vspeed, 
                           track, squawk, callsign, source
                    FROM {source_schema}.normal_tracks
                    WHERE flight_id = %s
                    ORDER BY timestamp ASC
                """, (flight_id,))
                
                rows = cursor.fetchall()
                table_source = f"{source_schema}.normal_tracks"
            
            if not rows:
                logger.error(f"No track points found for flight {flight_id} in {source_schema} schema")
                return [], {}, None
            
            logger.info(f"✓ Loaded {len(rows)} track points from {table_source}")
            
            # Convert rows to point dictionaries
            points = []
            for row in rows:
                points.append({
                    'flight_id': row[0],
                    'timestamp': int(row[1]),
                    'lat': float(row[2]),
                    'lon': float(row[3]),
                    'alt': float(row[4]) if row[4] is not None else 0.0,
                    'gspeed': float(row[5]) if row[5] is not None else None,
                    'vspeed': float(row[6]) if row[6] is not None else None,
                    'track': float(row[7]) if row[7] is not None else None,
                    'squawk': str(row[8]) if row[8] is not None else None,
                    'callsign': row[9],
                    'source': row[10]
                })
            
            # Load metadata from flight_metadata
            cursor.execute(f"""
                SELECT 
                    callsign, flight_number, airline, airline_code,
                    aircraft_type, aircraft_model, aircraft_registration,
                    origin_airport, origin_lat, origin_lon,
                    destination_airport, dest_lat, dest_lon,
                    first_seen_ts, last_seen_ts, scheduled_departure, scheduled_arrival,
                    flight_duration_sec, total_distance_nm, total_points,
                    min_altitude_ft, max_altitude_ft, avg_altitude_ft, cruise_altitude_ft,
                    min_speed_kts, max_speed_kts, avg_speed_kts,
                    start_lat, start_lon, end_lat, end_lon,
                    squawk_codes, emergency_squawk_detected,
                    is_anomaly, is_military, military_type, flight_phase_summary,
                    nearest_airport_start, nearest_airport_end, crossed_borders,
                    signal_loss_events, data_quality_score, category
                FROM {source_schema}.flight_metadata
                WHERE flight_id = %s
                LIMIT 1
            """, (flight_id,))
            
            meta_row = cursor.fetchone()
            
            if meta_row:
                metadata = {
                    'flight_id': flight_id,
                    'callsign': meta_row[0],
                    'flight_number': meta_row[1],
                    'airline': meta_row[2],
                    'airline_code': meta_row[3],
                    'aircraft_type': meta_row[4],
                    'aircraft_model': meta_row[5],
                    'aircraft_registration': meta_row[6],
                    'origin_airport': meta_row[7],
                    'origin_lat': meta_row[8],
                    'origin_lon': meta_row[9],
                    'destination_airport': meta_row[10],
                    'dest_lat': meta_row[11],
                    'dest_lon': meta_row[12],
                    'first_seen_ts': meta_row[13],
                    'last_seen_ts': meta_row[14],
                    'scheduled_departure': meta_row[15],
                    'scheduled_arrival': meta_row[16],
                    'flight_duration_sec': meta_row[17],
                    'total_distance_nm': meta_row[18],
                    'total_points': meta_row[19],
                    'min_altitude_ft': meta_row[20],
                    'max_altitude_ft': meta_row[21],
                    'avg_altitude_ft': meta_row[22],
                    'cruise_altitude_ft': meta_row[23],
                    'min_speed_kts': meta_row[24],
                    'max_speed_kts': meta_row[25],
                    'avg_speed_kts': meta_row[26],
                    'start_lat': meta_row[27],
                    'start_lon': meta_row[28],
                    'end_lat': meta_row[29],
                    'end_lon': meta_row[30],
                    'squawk_codes': meta_row[31],
                    'emergency_squawk_detected': meta_row[32],
                    'is_anomaly': meta_row[33],
                    'is_military': meta_row[34],
                    'military_type': meta_row[35],
                    'flight_phase_summary': meta_row[36],
                    'nearest_airport_start': meta_row[37],
                    'nearest_airport_end': meta_row[38],
                    'crossed_borders': meta_row[39],
                    'signal_loss_events': meta_row[40],
                    'data_quality_score': meta_row[41],
                    'category': meta_row[42],
                    'created_at': int(datetime.now().timestamp()),
                    'updated_at': int(datetime.now().timestamp())
                }
                logger.info(f"✓ Loaded metadata: {metadata.get('callsign')} | "
                           f"{metadata.get('origin_airport')} → {metadata.get('destination_airport')}")
            else:
                logger.warning(f"No metadata found for flight {flight_id}, using minimal metadata")
                metadata = {
                    'flight_id': flight_id,
                    'callsign': points[0].get('callsign'),
                    'origin_airport': None,
                    'destination_airport': None,
                    'is_anomaly': False,
                    'created_at': int(datetime.now().timestamp()),
                    'updated_at': int(datetime.now().timestamp())
                }
            
            # Try to load anomaly report if available
            anomaly_report = None
            cursor.execute(f"""
                SELECT full_report
                FROM {source_schema}.anomaly_reports
                WHERE flight_id = %s
                LIMIT 1
            """, (flight_id,))
            
            report_row = cursor.fetchone()
            if report_row and report_row[0]:
                anomaly_report = report_row[0] if isinstance(report_row[0], dict) else json.loads(report_row[0])
                logger.info(f"✓ Loaded existing anomaly report")
            
            return points, metadata, anomaly_report


def delete_flight_from_live(flight_id: str, dest_schema: str = 'live') -> bool:
    """
    Delete all existing data for a flight_id from the destination schema.
    
    Args:
        flight_id: Flight ID to delete
        dest_schema: Destination schema (default: 'live')
        
    Returns:
        bool: Success status
    """
    logger.info(f"Cleaning up existing data for {flight_id} in {dest_schema} schema...")
    
    try:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                # Delete from all related tables
                tables = ['ai_classifications', 'anomaly_reports', 'normal_tracks', 'flight_metadata']
                
                for table in tables:
                    try:
                        cursor.execute(f"""
                            DELETE FROM {dest_schema}.{table} WHERE flight_id = %s
                        """, (flight_id,))
                        deleted = cursor.rowcount
                        if deleted > 0:
                            logger.info(f"  Deleted {deleted} rows from {dest_schema}.{table}")
                    except Exception as e:
                        logger.warning(f"  Could not delete from {dest_schema}.{table}: {e}")
                
                conn.commit()
                logger.info(f"✓ Cleanup complete for {flight_id}")
                return True
                
    except Exception as e:
        logger.error(f"Failed to clean up flight {flight_id}: {e}")
        return False


def bulk_insert_points(
    points: List[Dict], 
    time_offset: int, 
    dest_schema: str = 'live'
) -> bool:
    """
    Bulk insert track points with adjusted timestamps.
    
    Args:
        points: List of point dictionaries
        time_offset: Offset to add to original timestamps
        dest_schema: Destination schema (default: 'live')
        
    Returns:
        bool: Success status
    """
    if not points:
        return True
    
    logger.info(f"Bulk inserting {len(points)} points to {dest_schema}.normal_tracks...")
    
    try:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                # Prepare data with adjusted timestamps
                data = []
                for p in points:
                    adjusted_ts = p['timestamp'] + time_offset
                    data.append((
                        p['flight_id'],
                        adjusted_ts,
                        p['lat'],
                        p['lon'],
                        p['alt'],
                        p['gspeed'],
                        p['vspeed'],
                        p['track'],
                        p['squawk'],
                        p['callsign'],
                        p['source']
                    ))
                
                # Bulk insert using execute_values
                insert_query = f"""
                    INSERT INTO {dest_schema}.normal_tracks 
                    (flight_id, timestamp, lat, lon, alt, gspeed, vspeed, track, squawk, callsign, source)
                    VALUES %s
                    ON CONFLICT (flight_id, timestamp) DO NOTHING
                """
                
                psycopg2.extras.execute_values(
                    cursor,
                    insert_query,
                    data,
                    template="(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
                )
                
                conn.commit()
                logger.info(f"✓ Bulk insert complete")
                return True
                
    except Exception as e:
        logger.error(f"Failed to bulk insert points: {e}")
        return False


def save_single_point(point: Dict, time_offset: int, dest_schema: str = 'live') -> bool:
    """
    Insert a single track point with adjusted timestamp.
    
    Args:
        point: Point dictionary
        time_offset: Offset to add to original timestamp
        dest_schema: Destination schema (default: 'live')
        
    Returns:
        bool: Success status
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                adjusted_ts = point['timestamp'] + time_offset
                
                cursor.execute(f"""
                    INSERT INTO {dest_schema}.normal_tracks 
                    (flight_id, timestamp, lat, lon, alt, gspeed, vspeed, track, squawk, callsign, source)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (flight_id, timestamp) DO NOTHING
                """, (
                    point['flight_id'],
                    adjusted_ts,
                    point['lat'],
                    point['lon'],
                    point['alt'],
                    point['gspeed'],
                    point['vspeed'],
                    point['track'],
                    point['squawk'],
                    point['callsign'],
                    point['source']
                ))
                
                conn.commit()
                return True
                
    except Exception as e:
        logger.error(f"Failed to insert single point: {e}")
        return False


def replay_flight(
    flight_id: str,
    start_timestamp: Optional[int] = None,
    start_point: Optional[int] = None,
    interval: int = 5,
    source_schema: str = 'feedback',
    dest_schema: str = 'live',
    dry_run: bool = False,
    use_new_id: bool = True
) -> bool:
    """
    Replay a flight from research schema to live schema with real-time simulation.
    
    Args:
        flight_id: Flight ID to replay from source schema
        start_timestamp: Optional timestamp to start real-time replay from
        start_point: Optional point number to start real-time replay from (0-based index)
        interval: Points interval for anomaly analysis
        source_schema: Source schema name
        dest_schema: Destination schema name
        dry_run: If True, show what would be done without inserting
        use_new_id: If True, generate a new UUID4 for the flight in live schema
        
    Returns:
        bool: Success status
    """
    # Generate new flight ID if requested
    original_flight_id = flight_id
    if use_new_id:
        # Generate a new UUID4-based flight ID
        new_flight_id = str(uuid.uuid4())[:8]  # Use first 8 chars for brevity
        logger.info("="*80)
        logger.info("FLIGHT REPLAY TO LIVE - REAL-TIME SIMULATION")
        logger.info("="*80)
        logger.info(f"Source Flight ID: {original_flight_id}")
        logger.info(f"New Flight ID (live): {new_flight_id}")
        logger.info(f"Source Schema: {source_schema}")
        logger.info(f"Destination Schema: {dest_schema}")
        if start_point is not None:
            logger.info(f"Start Point: Point #{start_point}")
        elif start_timestamp:
            logger.info(f"Start Timestamp: {start_timestamp}")
        else:
            logger.info(f"Start: Beginning of flight")
        logger.info(f"Analysis Interval: Every {interval} points")
        logger.info(f"Dry Run: {dry_run}")
        logger.info("="*80)
        flight_id = new_flight_id  # Use new ID for all operations
    else:
        logger.info("="*80)
        logger.info("FLIGHT REPLAY TO LIVE - REAL-TIME SIMULATION")
        logger.info("="*80)
        logger.info(f"Flight ID: {flight_id}")
        logger.info(f"Source Schema: {source_schema}")
        logger.info(f"Destination Schema: {dest_schema}")
        if start_point is not None:
            logger.info(f"Start Point: Point #{start_point}")
        elif start_timestamp:
            logger.info(f"Start Timestamp: {start_timestamp}")
        else:
            logger.info(f"Start: Beginning of flight")
        logger.info(f"Analysis Interval: Every {interval} points")
        logger.info(f"Dry Run: {dry_run}")
        logger.info("="*80)
    
    # Load flight data from research schema using original ID
    points, metadata, anomaly_report = load_flight_from_research(original_flight_id, source_schema)
    
    if not points:
        logger.error("No points loaded, aborting replay")
        return False
    
    # Calculate time offset to shift timestamps to "now"
    first_original_ts = points[0]['timestamp']
    current_time = int(time.time())
    base_time_offset = current_time - first_original_ts
    
    logger.info(f"\nFlight Details:")
    logger.info(f"  Total Points: {len(points)}")
    logger.info(f"  First Point: {datetime.fromtimestamp(first_original_ts).strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"  Last Point: {datetime.fromtimestamp(points[-1]['timestamp']).strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"  Duration: {(points[-1]['timestamp'] - first_original_ts) / 60:.1f} minutes")
    logger.info(f"  Callsign: {metadata.get('callsign', 'N/A')}")
    logger.info(f"  Route: {metadata.get('origin_airport', '???')} → {metadata.get('destination_airport', '???')}")
    
    # Convert start_point to start_timestamp if provided
    if start_point is not None:
        if start_point < 0 or start_point >= len(points):
            logger.error(f"Invalid start point {start_point}. Must be between 0 and {len(points)-1}")
            return False
        start_timestamp = points[start_point]['timestamp']
        logger.info(f"\nConverted point #{start_point} to timestamp {start_timestamp}")
        logger.info(f"  Timestamp: {datetime.fromtimestamp(start_timestamp).strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Split points into bulk insert and real-time replay
    bulk_points = []
    realtime_points = []
    
    if start_timestamp:
        # Validate start timestamp
        if start_timestamp < first_original_ts or start_timestamp > points[-1]['timestamp']:
            logger.error(f"Invalid start timestamp {start_timestamp}. Must be between "
                        f"{first_original_ts} and {points[-1]['timestamp']}")
            return False
        
        # Split points
        for i, point in enumerate(points):
            if point['timestamp'] < start_timestamp:
                bulk_points.append(point)
            else:
                realtime_points.append(point)
        
        logger.info(f"\nReplay Strategy:")
        if start_point is not None:
            logger.info(f"  Phase 1 (Bulk Insert): {len(bulk_points)} points (0 to {start_point-1})")
            logger.info(f"  Phase 2 (Real-time): {len(realtime_points)} points (from point #{start_point} onwards)")
        else:
            logger.info(f"  Phase 1 (Bulk Insert): {len(bulk_points)} points before timestamp {start_timestamp}")
            logger.info(f"  Phase 2 (Real-time): {len(realtime_points)} points from timestamp onwards")
        
        # Calculate time offset for bulk points (should be in the past relative to now)
        if bulk_points:
            time_diff_from_start = start_timestamp - first_original_ts
            bulk_time_offset = current_time - start_timestamp
    else:
        realtime_points = points
        logger.info(f"\nReplay Strategy:")
        logger.info(f"  All {len(points)} points will be replayed in real-time")
    
    if dry_run:
        logger.info("\n⚠️  DRY RUN MODE - No data will be inserted")
        logger.info("="*80)
        return True
    
    # Update all points with new flight_id
    if use_new_id:
        logger.info(f"\nUpdating all points with new flight ID: {flight_id}")
        for point in points:
            point['flight_id'] = flight_id
        metadata['flight_id'] = flight_id
    
    # Clean up existing data only if using same ID
    if not use_new_id:
        if not delete_flight_from_live(flight_id, dest_schema):
            logger.warning("Failed to clean up existing data, continuing anyway...")
    
    # Phase 1: Bulk insert
    if bulk_points:
        logger.info("\n" + "="*80)
        logger.info("PHASE 1: BULK INSERT")
        logger.info("="*80)
        
        if not bulk_insert_points(bulk_points, bulk_time_offset, dest_schema):
            logger.error("Bulk insert failed, aborting replay")
            return False
        
        logger.info(f"✓ {len(bulk_points)} points inserted instantly")
        
        # Calculate time range for bulk inserted points
        first_bulk_adjusted = bulk_points[0]['timestamp'] + bulk_time_offset
        last_bulk_adjusted = bulk_points[-1]['timestamp'] + bulk_time_offset
        logger.info(f"  Time range: {datetime.fromtimestamp(first_bulk_adjusted).strftime('%H:%M:%S')} to "
                   f"{datetime.fromtimestamp(last_bulk_adjusted).strftime('%H:%M:%S')}")
    
    # Save initial metadata (will be updated after anomaly detection)
    # Adjust all timestamp fields to the new "now" time
    # Use bulk_time_offset if we have bulk points, otherwise use base_time_offset
    if bulk_points:
        metadata['first_seen_ts'] = points[0]['timestamp'] + bulk_time_offset
        # Last seen will be updated later as we replay real-time points
        if realtime_points:
            # We'll update last_seen_ts as we go
            metadata['last_seen_ts'] = bulk_points[-1]['timestamp'] + bulk_time_offset
        else:
            metadata['last_seen_ts'] = points[-1]['timestamp'] + bulk_time_offset
    else:
        metadata['first_seen_ts'] = points[0]['timestamp'] + base_time_offset
        metadata['last_seen_ts'] = points[-1]['timestamp'] + base_time_offset
    
    # Also adjust scheduled times if they exist and are numeric
    if metadata.get('scheduled_departure') and isinstance(metadata['scheduled_departure'], (int, float)):
        metadata['scheduled_departure'] = metadata['scheduled_departure'] + base_time_offset
    if metadata.get('scheduled_arrival') and isinstance(metadata['scheduled_arrival'], (int, float)):
        metadata['scheduled_arrival'] = metadata['scheduled_arrival'] + base_time_offset
    
    # Convert datetime to timestamp for PostgreSQL
    metadata['created_at'] = int(datetime.now().timestamp())
    metadata['updated_at'] = int(datetime.now().timestamp())
    
    # Initialize is_anomaly to False (will be set to True only when anomaly detected)
    metadata['is_anomaly'] = False
    
    if not save_flight_metadata(metadata, dest_schema):
        logger.warning("Failed to save initial metadata, continuing anyway...")
    
    # Phase 2: Real-time replay with anomaly detection
    if realtime_points:
        logger.info("\n" + "="*80)
        logger.info("PHASE 2: REAL-TIME REPLAY")
        logger.info("="*80)
        logger.info(f"Starting real-time replay of {len(realtime_points)} points...")
        logger.info(f"Press Ctrl+C to stop gracefully\n")
        
        # Initialize anomaly pipeline
        try:
            pipeline = AnomalyPipeline(use_postgres=True)
            logger.info("✓ Anomaly pipeline initialized")
        except Exception as e:
            logger.error(f"Failed to initialize anomaly pipeline: {e}")
            return False
        
        # Create FlightMetadata object for pipeline
        flight_metadata = None
        if metadata.get('origin_airport') or metadata.get('destination_airport'):
            flight_metadata = FlightMetadata(
                origin=metadata.get('origin_airport'),
                planned_destination=metadata.get('destination_airport'),
                planned_route=None
            )
        
        # Accumulated points for incremental analysis
        accumulated_points = []
        
        # Add bulk points to accumulated if any
        if bulk_points:
            for bp in bulk_points:
                accumulated_points.append(TrackPoint(
                    flight_id=bp['flight_id'],
                    timestamp=bp['timestamp'] + bulk_time_offset,
                    lat=bp['lat'],
                    lon=bp['lon'],
                    alt=bp['alt'],
                    gspeed=bp['gspeed'],
                    vspeed=bp['vspeed'],
                    track=bp['track'],
                    squawk=bp['squawk'],
                    callsign=bp['callsign'],
                    source=bp['source']
                ))
        
        anomaly_detected = False
        first_anomaly_point = None
        
        try:
            prev_timestamp = realtime_points[0]['timestamp'] if realtime_points else None
            
            for i, point in enumerate(realtime_points, start=1):
                # Calculate delay from previous point (real-time simulation)
                if i > 1 and prev_timestamp:
                    delay_sec = point['timestamp'] - prev_timestamp
                    if delay_sec > 0:
                        if delay_sec > 60:
                            logger.info(f"⏰ Waiting {delay_sec/60:.1f} minutes before next point...")
                        elif delay_sec > 10:
                            logger.info(f"⏰ Waiting {delay_sec:.0f} seconds before next point...")
                        else:
                            logger.debug(f"⏰ Waiting {delay_sec:.1f} seconds...")
                        time.sleep(delay_sec)
                
                prev_timestamp = point['timestamp']
                
                # Insert point with current timestamp
                current_ts = int(time.time())
                point_time_offset = current_ts - point['timestamp']
                
                if not save_single_point(point, point_time_offset, dest_schema):
                    logger.warning(f"Failed to insert point {i}, continuing...")
                
                # Add to accumulated points
                track_point = TrackPoint(
                    flight_id=point['flight_id'],
                    timestamp=current_ts,
                    lat=point['lat'],
                    lon=point['lon'],
                    alt=point['alt'],
                    gspeed=point['gspeed'],
                    vspeed=point['vspeed'],
                    track=point['track'],
                    squawk=point['squawk'],
                    callsign=point['callsign'],
                    source=point['source']
                )
                accumulated_points.append(track_point)
                
                # Run anomaly analysis at intervals
                total_points_so_far = len(bulk_points) + i
                
                if len(accumulated_points) >= MIN_POINTS_FOR_ANALYSIS and i % interval == 0:
                    logger.info(f"\n[Point {total_points_so_far}/{len(points)}] " + 
                               f"{datetime.fromtimestamp(current_ts).strftime('%H:%M:%S')} | "
                               f"Lat {point['lat']:.4f}, Lon {point['lon']:.4f}, Alt {point['alt']:.0f}ft")
                    
                    # Create flight track for analysis
                    flight_track = FlightTrack(flight_id=flight_id, points=accumulated_points.copy())
                    
                    try:
                        # Run pipeline
                        report = pipeline.analyze(flight_track, metadata=flight_metadata)
                        
                        is_anomaly = report['summary']['is_anomaly']
                        confidence = report['summary'].get('confidence_score', 0)
                        triggers = report['summary'].get('triggers', [])
                        
                        if is_anomaly:
                            if not anomaly_detected:
                                logger.warning("\n" + "#"*80)
                                logger.warning("🚨🚨🚨 ANOMALY DETECTED! 🚨🚨🚨")
                                logger.warning(f"   Point: {total_points_so_far}/{len(points)}")
                                logger.warning(f"   Time: {datetime.fromtimestamp(current_ts).strftime('%Y-%m-%d %H:%M:%S')}")
                                logger.warning(f"   Position: Lat {point['lat']:.4f}, Lon {point['lon']:.4f}, Alt {point['alt']:.0f}ft")
                                logger.warning(f"   Confidence: {confidence:.1f}%")
                                logger.warning(f"   Triggered by: {', '.join(triggers)}")
                                logger.warning("#"*80 + "\n")
                                anomaly_detected = True
                                first_anomaly_point = total_points_so_far
                            else:
                                logger.warning(f"🚨 Anomaly continues at point {total_points_so_far} (confidence: {confidence:.1f}%)")
                            
                            # Save anomaly report
                            logger.info(f"💾 Saving anomaly report to {dest_schema}.anomaly_reports...")
                            if save_anomaly_report(report, current_ts, metadata, dest_schema):
                                logger.info(f"✓ Anomaly report saved successfully")
                            else:
                                logger.error(f"✗ Failed to save anomaly report!")
                            
                            # Update metadata to mark as anomaly (ONLY when anomaly is detected)
                            metadata['is_anomaly'] = True
                            metadata['last_seen_ts'] = current_ts  # Update to current point's timestamp
                            metadata['updated_at'] = int(datetime.now().timestamp())
                            logger.info(f"💾 Updating metadata to mark as anomaly...")
                            if save_flight_metadata(metadata, dest_schema):
                                logger.info(f"✓ Metadata updated (is_anomaly=True)")
                            else:
                                logger.error(f"✗ Failed to update metadata!")
                            
                        else:
                            logger.info(f"✓ Normal at point {total_points_so_far} (confidence: {confidence:.1f}%)")
                        
                    except Exception as e:
                        logger.error(f"Error during anomaly analysis: {e}", exc_info=True)
                else:
                    # Just log progress without analysis
                    if i % 10 == 0:
                        logger.debug(f"Point {total_points_so_far}/{len(points)} inserted")
            
            # Final metadata update with last point's timestamp
            if realtime_points:
                final_ts = int(time.time())
                metadata['last_seen_ts'] = final_ts
                metadata['updated_at'] = int(datetime.now().timestamp())
                logger.info(f"\n💾 Saving final metadata update...")
                if save_flight_metadata(metadata, dest_schema):
                    logger.info(f"✓ Final metadata saved (is_anomaly={metadata['is_anomaly']})")
                else:
                    logger.error(f"✗ Failed to save final metadata!")
            
            # Final summary
            logger.info("\n" + "="*80)
            logger.info("REPLAY COMPLETE")
            logger.info("="*80)
            logger.info(f"Total Points Replayed: {len(points)}")
            logger.info(f"  Bulk Inserted: {len(bulk_points)}")
            logger.info(f"  Real-time: {len(realtime_points)}")
            
            if anomaly_detected:
                logger.info(f"\n✓ Anomaly detected at point {first_anomaly_point}")
            else:
                logger.info(f"\n✓ No anomalies detected during replay")
            
            logger.info("="*80)
            
            return True
            
        except KeyboardInterrupt:
            logger.warning("\n\n⚠️  Replay interrupted by user")
            logger.info(f"Progress: {i}/{len(realtime_points)} real-time points processed")
            return False
    
    return True


def main():
    """Main entry point for the replay script."""
    parser = argparse.ArgumentParser(
        description="Replay flights from research schema to live schema with real-time simulation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Replay entire flight in real-time
  python replay_flight_to_live.py 3d7211ef
  
  # Start replay from specific timestamp (bulk insert earlier points)
  python replay_flight_to_live.py 3d7211ef --start-timestamp 1707580800
  
  # Custom analysis interval
  python replay_flight_to_live.py 3d7211ef --interval 10
  
  # Dry run to see what would happen
  python replay_flight_to_live.py 3d7211ef --start-timestamp 1707580800 --dry-run
"""
    )
    
    parser.add_argument(
        'flight_id',
        help='Flight ID from research schema to replay'
    )
    
    parser.add_argument(
        '--start-timestamp',
        type=int,
        help='Unix timestamp to start real-time replay from (earlier points inserted instantly)'
    )
    
    parser.add_argument(
        '--start-point',
        type=int,
        help='Point number to start real-time replay from (0-based index, earlier points inserted instantly)'
    )
    
    parser.add_argument(
        '--interval',
        type=int,
        default=5,
        help='Points interval for anomaly analysis (default: 5)'
    )
    
    parser.add_argument(
        '--source-schema',
        default='feedback',
        help='Source schema name (default: feedback)'
    )
    
    parser.add_argument(
        '--dest-schema',
        default='live',
        help='Destination schema name (default: live)'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be done without actually inserting data'
    )
    
    parser.add_argument(
        '--use-original-id',
        action='store_true',
        help='Use original flight ID instead of generating new UUID (will delete existing data)'
    )
    
    args = parser.parse_args()
    
    # Validate mutually exclusive options
    if args.start_timestamp and args.start_point:
        logger.error("Cannot use both --start-timestamp and --start-point. Choose one.")
        return 1
    
    # Initialize database connection pool
    if not init_connection_pool():
        logger.error("Failed to initialize PostgreSQL connection pool")
        return 1
    
    # Run replay
    success = replay_flight(
        flight_id=args.flight_id,
        start_timestamp=args.start_timestamp,
        start_point=args.start_point,
        interval=args.interval,
        source_schema=args.source_schema,
        dest_schema=args.dest_schema,
        dry_run=args.dry_run,
        use_new_id=not args.use_original_id  # Default: use new ID
    )
    
    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())
