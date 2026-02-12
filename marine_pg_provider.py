"""
PostgreSQL Provider for Marine Vessel Tracking

Handles all PostgreSQL database operations for marine_monitor.py with:
- Reuses connection pool from pg_provider.py
- Batch insert operations for performance
- Upsert for vessel metadata
- Type conversions and error handling
"""

import psycopg2
import psycopg2.extras
from psycopg2 import sql
import logging
from typing import List, Dict, Any
from datetime import datetime

# Import connection management from existing pg_provider
from pg_provider import get_connection, init_connection_pool

logger = logging.getLogger(__name__)


def save_vessel_positions(positions: List[Dict[str, Any]], schema: str = 'marine') -> bool:
    """
    Save vessel position reports to PostgreSQL in batch.
    
    Args:
        positions: List of position dictionaries with fields:
            - mmsi (str)
            - timestamp (datetime)
            - latitude (float)
            - longitude (float)
            - speed_over_ground (float, optional)
            - course_over_ground (float, optional)
            - heading (int, optional)
            - navigation_status (str, optional)
            - rate_of_turn (float, optional)
            - position_accuracy (bool, optional)
            - message_type (int, optional)
        schema: Schema name (default: 'marine')
    
    Returns:
        bool: Success status
    """
    if not positions:
        logger.warning("No positions to save")
        return False
    
    try:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                # Prepare data for bulk insert
                data = []
                for p in positions:
                    data.append((
                        p['mmsi'],
                        p['timestamp'],
                        p['latitude'],
                        p['longitude'],
                        p.get('speed_over_ground'),
                        p.get('course_over_ground'),
                        p.get('heading'),
                        p.get('navigation_status'),
                        p.get('rate_of_turn'),
                        p.get('position_accuracy'),
                        p.get('message_type')
                    ))
                
                # Use ON CONFLICT DO NOTHING to skip duplicates
                insert_query = sql.SQL("""
                    INSERT INTO {}.vessel_positions 
                    (mmsi, timestamp, latitude, longitude, speed_over_ground, 
                     course_over_ground, heading, navigation_status, rate_of_turn,
                     position_accuracy, message_type)
                    VALUES %s
                    ON CONFLICT (id, timestamp) DO NOTHING
                """).format(sql.Identifier(schema))
                
                # Use execute_values for bulk insert (much faster than executemany)
                psycopg2.extras.execute_values(
                    cursor,
                    insert_query,
                    data,
                    template="(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
                )
                
                conn.commit()
                logger.info(f"Saved {len(data)} vessel positions to PostgreSQL")
                return True
                
    except Exception as e:
        logger.error(f"Failed to save vessel positions to PostgreSQL: {e}")
        return False


def save_vessel_position(position: Dict[str, Any], schema: str = 'marine') -> bool:
    """
    Save a single vessel position report to PostgreSQL.
    For small batches, consider using save_vessel_positions() instead.
    
    Args:
        position: Position dictionary
        schema: Schema name (default: 'marine')
    
    Returns:
        bool: Success status
    """
    return save_vessel_positions([position], schema=schema)


def save_vessel_metadata(metadata: Dict[str, Any], schema: str = 'marine') -> bool:
    """
    Save or update vessel metadata to PostgreSQL (UPSERT).
    
    Args:
        metadata: Dictionary with vessel metadata:
            - mmsi (str, required)
            - vessel_name (str, optional)
            - callsign (str, optional)
            - imo_number (str, optional)
            - vessel_type (int, optional)
            - vessel_type_description (str, optional)
            - length (int, optional)
            - width (int, optional)
            - draught (float, optional)
            - destination (str, optional)
            - eta (datetime, optional)
            - cargo_type (int, optional)
            - dimension_to_bow (int, optional)
            - dimension_to_stern (int, optional)
            - dimension_to_port (int, optional)
            - dimension_to_starboard (int, optional)
            - position_fixing_device (int, optional)
        schema: Schema name (default: 'marine')
    
    Returns:
        bool: Success status
    """
    try:
        mmsi = metadata.get('mmsi')
        if not mmsi:
            logger.warning("Cannot save vessel metadata without MMSI")
            return False
        
        with get_connection() as conn:
            with conn.cursor() as cursor:
                # UPSERT: Insert new or update existing record
                # Update last_updated timestamp and increment position report count
                upsert_query = sql.SQL("""
                    INSERT INTO {}.vessel_metadata (
                        mmsi, vessel_name, callsign, imo_number, vessel_type, 
                        vessel_type_description, length, width, draught, destination, 
                        eta, cargo_type, dimension_to_bow, dimension_to_stern, 
                        dimension_to_port, dimension_to_starboard, position_fixing_device,
                        first_seen, last_updated, total_position_reports
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW(), 0
                    )
                    ON CONFLICT (mmsi) DO UPDATE SET
                        vessel_name = COALESCE(EXCLUDED.vessel_name, {}.vessel_metadata.vessel_name),
                        callsign = COALESCE(EXCLUDED.callsign, {}.vessel_metadata.callsign),
                        imo_number = COALESCE(EXCLUDED.imo_number, {}.vessel_metadata.imo_number),
                        vessel_type = COALESCE(EXCLUDED.vessel_type, {}.vessel_metadata.vessel_type),
                        vessel_type_description = COALESCE(EXCLUDED.vessel_type_description, {}.vessel_metadata.vessel_type_description),
                        length = COALESCE(EXCLUDED.length, {}.vessel_metadata.length),
                        width = COALESCE(EXCLUDED.width, {}.vessel_metadata.width),
                        draught = COALESCE(EXCLUDED.draught, {}.vessel_metadata.draught),
                        destination = COALESCE(EXCLUDED.destination, {}.vessel_metadata.destination),
                        eta = COALESCE(EXCLUDED.eta, {}.vessel_metadata.eta),
                        cargo_type = COALESCE(EXCLUDED.cargo_type, {}.vessel_metadata.cargo_type),
                        dimension_to_bow = COALESCE(EXCLUDED.dimension_to_bow, {}.vessel_metadata.dimension_to_bow),
                        dimension_to_stern = COALESCE(EXCLUDED.dimension_to_stern, {}.vessel_metadata.dimension_to_stern),
                        dimension_to_port = COALESCE(EXCLUDED.dimension_to_port, {}.vessel_metadata.dimension_to_port),
                        dimension_to_starboard = COALESCE(EXCLUDED.dimension_to_starboard, {}.vessel_metadata.dimension_to_starboard),
                        position_fixing_device = COALESCE(EXCLUDED.position_fixing_device, {}.vessel_metadata.position_fixing_device),
                        last_updated = NOW()
                """).format(
                    sql.Identifier(schema),
                    sql.Identifier(schema),
                    sql.Identifier(schema),
                    sql.Identifier(schema),
                    sql.Identifier(schema),
                    sql.Identifier(schema),
                    sql.Identifier(schema),
                    sql.Identifier(schema),
                    sql.Identifier(schema),
                    sql.Identifier(schema),
                    sql.Identifier(schema),
                    sql.Identifier(schema),
                    sql.Identifier(schema),
                    sql.Identifier(schema),
                    sql.Identifier(schema),
                    sql.Identifier(schema),
                    sql.Identifier(schema)
                )
                
                cursor.execute(upsert_query, (
                    mmsi,
                    metadata.get('vessel_name'),
                    metadata.get('callsign'),
                    metadata.get('imo_number'),
                    metadata.get('vessel_type'),
                    metadata.get('vessel_type_description'),
                    metadata.get('length'),
                    metadata.get('width'),
                    metadata.get('draught'),
                    metadata.get('destination'),
                    metadata.get('eta'),
                    metadata.get('cargo_type'),
                    metadata.get('dimension_to_bow'),
                    metadata.get('dimension_to_stern'),
                    metadata.get('dimension_to_port'),
                    metadata.get('dimension_to_starboard'),
                    metadata.get('position_fixing_device')
                ))
                
                conn.commit()
                logger.debug(f"Saved/updated metadata for vessel {mmsi}")
                return True
                
    except Exception as e:
        logger.error(f"Failed to save vessel metadata for {metadata.get('mmsi')}: {e}")
        return False


def increment_vessel_position_count(mmsi: str, count: int = 1, schema: str = 'marine') -> bool:
    """
    Increment the total position reports counter for a vessel.
    
    Args:
        mmsi: Vessel MMSI
        count: Number to increment by (default: 1)
        schema: Schema name (default: 'marine')
    
    Returns:
        bool: Success status
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                update_query = sql.SQL("""
                    UPDATE {}.vessel_metadata 
                    SET total_position_reports = total_position_reports + %s,
                        last_updated = NOW()
                    WHERE mmsi = %s
                """).format(sql.Identifier(schema))
                
                cursor.execute(update_query, (count, mmsi))
                conn.commit()
                return True
                
    except Exception as e:
        logger.error(f"Failed to increment position count for vessel {mmsi}: {e}")
        return False


def get_vessel_metadata(mmsi: str, schema: str = 'marine') -> Dict[str, Any]:
    """
    Retrieve vessel metadata from PostgreSQL.
    
    Args:
        mmsi: Vessel MMSI
        schema: Schema name (default: 'marine')
    
    Returns:
        dict: Vessel metadata or empty dict if not found
    """
    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                select_query = sql.SQL("""
                    SELECT * FROM {}.vessel_metadata WHERE mmsi = %s
                """).format(sql.Identifier(schema))
                
                cursor.execute(select_query, (mmsi,))
                result = cursor.fetchone()
                return dict(result) if result else {}
                
    except Exception as e:
        logger.error(f"Failed to retrieve vessel metadata for {mmsi}: {e}")
        return {}


def get_recent_vessel_positions(mmsi: str, hours: int = 24, schema: str = 'marine') -> List[Dict[str, Any]]:
    """
    Retrieve recent position reports for a vessel.
    
    Args:
        mmsi: Vessel MMSI
        hours: Number of hours to look back (default: 24)
        schema: Schema name (default: 'marine')
    
    Returns:
        list: List of position dictionaries, ordered by timestamp DESC
    """
    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                select_query = sql.SQL("""
                    SELECT * FROM {}.vessel_positions 
                    WHERE mmsi = %s 
                    AND timestamp > NOW() - INTERVAL '%s hours'
                    ORDER BY timestamp DESC
                """).format(sql.Identifier(schema))
                
                cursor.execute(select_query, (mmsi, hours))
                results = cursor.fetchall()
                return [dict(row) for row in results]
                
    except Exception as e:
        logger.error(f"Failed to retrieve positions for vessel {mmsi}: {e}")
        return []


def check_marine_schema_exists(schema: str = 'marine') -> bool:
    """Check if marine schema exists in PostgreSQL."""
    try:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT schema_name 
                    FROM information_schema.schemata 
                    WHERE schema_name = %s
                """, (schema,))
                exists = cursor.fetchone() is not None
                if exists:
                    logger.info(f"Marine schema '{schema}' exists")
                else:
                    logger.warning(f"Marine schema '{schema}' does not exist. Run create_marine_schema.sql")
                return exists
    except Exception as e:
        logger.error(f"Failed to check marine schema existence: {e}")
        return False
