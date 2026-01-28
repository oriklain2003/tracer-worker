"""
PostgreSQL Provider for Real-time Flight Monitoring

Handles all PostgreSQL database operations for monitor.py with:
- Connection pooling
- Schema-aware queries (defaults to 'live' schema)
- Partitioned table support
- Bulk insert operations
- Type conversions
"""

import psycopg2
import psycopg2.extras
from psycopg2 import pool, sql
import json
import logging
import os
from typing import Dict, List, Optional, Any
from contextlib import contextmanager

logger = logging.getLogger(__name__)

# PostgreSQL connection configuration from environment variables
def get_pg_dsn() -> str:
    """Build PostgreSQL DSN from environment variables."""
    pg_host = os.getenv("PG_HOST", "tracer-db.cb80eku2emy0.eu-north-1.rds.amazonaws.com")
    pg_port = os.getenv("PG_PORT", "5432")
    pg_database = os.getenv("PG_DATABASE", "tracer")
    pg_user = os.getenv("PG_USER", "postgres")
    pg_password = os.getenv("PG_PASSWORD", "Warqi4-sywsow-zozfyc")
    
    return f"postgresql://{pg_user}:{pg_password}@{pg_host}:{pg_port}/{pg_database}"

PG_DSN = get_pg_dsn()

# Connection pool (thread-safe)
_connection_pool = None


def init_connection_pool(dsn: str = None, minconn: int = 2, maxconn: int = 10):
    """Initialize PostgreSQL connection pool."""
    global _connection_pool
    if dsn is None:
        dsn = get_pg_dsn()
    try:
        _connection_pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=minconn,
            maxconn=maxconn,
            dsn=dsn
        )
        logger.info(f"PostgreSQL connection pool initialized ({minconn}-{maxconn} connections)")
        return True
    except Exception as e:
        logger.error(f"Failed to initialize PostgreSQL connection pool: {e}")
        return False


@contextmanager
def get_connection():
    """Get a connection from the pool (context manager)."""
    if _connection_pool is None:
        init_connection_pool()
    
    conn = _connection_pool.getconn()
    try:
        yield conn
    finally:
        _connection_pool.putconn(conn)


def execute_query(query: str, params: tuple = None, fetch: bool = False, schema: str = 'live'):
    """Execute a query with automatic connection management."""
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(query, params)
            if fetch:
                return cursor.fetchall()
            conn.commit()


def save_flight_tracks(flight, is_anomaly: bool, schema: str = 'live') -> bool:
    """
    Save flight track points to PostgreSQL.
    
    Args:
        flight: FlightTrack object with points
        is_anomaly: Whether this is an anomaly flight
        schema: Schema name (default: 'live')
    
    Returns:
        bool: Success status
    """
    try:
        # Always save to normal_tracks table (all flights)
        table = 'normal_tracks'
        
        if not flight.points:
            logger.warning(f"No points to save for flight {flight.flight_id}")
            return False
        
        with get_connection() as conn:
            with conn.cursor() as cursor:
                # Prepare data for bulk insert
                data = []
                for p in flight.points:
                    data.append((
                        p.flight_id,
                        p.timestamp,
                        p.lat,
                        p.lon,
                        p.alt,
                        p.gspeed,
                        p.vspeed,
                        p.track,
                        p.squawk,
                        p.callsign,
                        p.source
                    ))
                
                # Use ON CONFLICT DO NOTHING to skip duplicates (same as SQLite INSERT OR IGNORE)
                insert_query = sql.SQL("""
                    INSERT INTO {}.{} 
                    (flight_id, timestamp, lat, lon, alt, gspeed, vspeed, track, squawk, callsign, source)
                    VALUES %s
                    ON CONFLICT (flight_id, timestamp) DO NOTHING
                """).format(
                    sql.Identifier(schema),
                    sql.Identifier(table)
                )
                
                # Use execute_values for bulk insert (much faster than executemany)
                psycopg2.extras.execute_values(
                    cursor,
                    insert_query,
                    data,
                    template="(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
                )
                
                conn.commit()
                logger.debug(f"Saved {len(data)} track points to PostgreSQL for {flight.flight_id}")
                return True
                
    except Exception as e:
        logger.error(f"Failed to save tracks to PostgreSQL for {flight.flight_id}: {e}")
        return False


def save_flight_metadata(metadata: Dict, schema: str = 'live') -> bool:
    """
    Save flight metadata to PostgreSQL.
    
    Args:
        metadata: Dictionary with flight metadata
        schema: Schema name (default: 'live')
    
    Returns:
        bool: Success status
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                # Since flight_metadata is partitioned, we can't use ON CONFLICT
                # Delete existing record first, then insert (same as INSERT OR REPLACE)
                delete_query = sql.SQL("""
                    DELETE FROM {}.flight_metadata WHERE flight_id = %s
                """).format(sql.Identifier(schema))
                
                cursor.execute(delete_query, (metadata['flight_id'],))
                
                # Now insert the new metadata
                insert_query = sql.SQL("""
                    INSERT INTO {}.flight_metadata (
                        flight_id, callsign, flight_number, airline, airline_code,
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
                        signal_loss_events, data_quality_score,
                        created_at, updated_at, category
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                """).format(sql.Identifier(schema))
                
                cursor.execute(insert_query, (
                    metadata['flight_id'], metadata.get('callsign'), metadata.get('flight_number'),
                    metadata.get('airline'), metadata.get('airline_code'),
                    metadata.get('aircraft_type'), metadata.get('aircraft_model'), 
                    metadata.get('aircraft_registration'),
                    metadata.get('origin_airport'), metadata.get('origin_lat'), metadata.get('origin_lon'),
                    metadata.get('destination_airport'), metadata.get('dest_lat'), metadata.get('dest_lon'),
                    metadata.get('first_seen_ts'), metadata.get('last_seen_ts'),
                    metadata.get('scheduled_departure'), metadata.get('scheduled_arrival'),
                    metadata.get('flight_duration_sec'), metadata.get('total_distance_nm'), 
                    metadata.get('total_points'),
                    metadata.get('min_altitude_ft'), metadata.get('max_altitude_ft'),
                    metadata.get('avg_altitude_ft'), metadata.get('cruise_altitude_ft'),
                    metadata.get('min_speed_kts'), metadata.get('max_speed_kts'), metadata.get('avg_speed_kts'),
                    metadata.get('start_lat'), metadata.get('start_lon'), 
                    metadata.get('end_lat'), metadata.get('end_lon'),
                    metadata.get('squawk_codes'), metadata.get('emergency_squawk_detected'),
                    metadata.get('is_anomaly', False), metadata.get('is_military'), 
                    metadata.get('military_type'),
                    metadata.get('flight_phase_summary'),
                    metadata.get('nearest_airport_start'), metadata.get('nearest_airport_end'),
                    metadata.get('crossed_borders'), metadata.get('signal_loss_events'),
                    metadata.get('data_quality_score'), metadata.get('created_at'), 
                    metadata.get('updated_at'),
                    metadata.get('category')
                ))
                
                conn.commit()
                logger.debug(f"Saved metadata to PostgreSQL for {metadata['flight_id']}")
                return True
                
    except Exception as e:
        logger.error(f"Failed to save metadata to PostgreSQL for {metadata.get('flight_id')}: {e}")
        return False


def save_anomaly_report(report: dict, timestamp: int, metadata: Dict, schema: str = 'live') -> bool:
    """
    Save anomaly report to PostgreSQL.
    
    Args:
        report: Anomaly report dictionary
        timestamp: Report timestamp
        metadata: Flight metadata dictionary
        schema: Schema name (default: 'live')
    
    Returns:
        bool: Success status
    """
    try:
        flight_id = report["summary"]["flight_id"]
        is_anom = report["summary"]["is_anomaly"]
        
        # Extract severity scores
        sev_cnn = 0.0
        if "layer_4_deep_cnn" in report and "severity" in report["layer_4_deep_cnn"]:
            sev_cnn = report["layer_4_deep_cnn"]["severity"]
        
        sev_dense = 0.0
        if "layer_3_deep_dense" in report and "severity" in report["layer_3_deep_dense"]:
            sev_dense = report["layer_3_deep_dense"]["severity"]
        
        # Extract rule matches
        matched_rule_ids = None
        matched_rule_names = None
        matched_rule_categories = None
        
        rules_layer = report.get("layer_1_rules", {})
        if rules_layer:
            matched_rules = rules_layer.get("report", {}).get("matched_rules", [])
            if matched_rules:
                rule_ids = [str(r.get("id")) for r in matched_rules if r.get("id")]
                rule_names = [r.get("name", "") for r in matched_rules if r.get("name")]
                rule_cats = [r.get("category", "") for r in matched_rules if r.get("category")]
                
                matched_rule_ids = ", ".join(rule_ids)
                matched_rule_names = ", ".join(rule_names)
                matched_rule_categories = ", ".join(set(rule_cats))
        
        # Determine geographic region
        geographic_region = None
        if metadata.get('crossed_borders'):
            regions = metadata['crossed_borders'].split(',')
            geographic_region = regions[0] if regions else None
        
        nearest_airport = metadata.get('nearest_airport_end') or metadata.get('nearest_airport_start')
        
        with get_connection() as conn:
            with conn.cursor() as cursor:
                # Since anomaly_reports is partitioned by timestamp, we can't use UNIQUE(flight_id)
                # Instead, DELETE existing report and INSERT new one (same as INSERT OR REPLACE)
                delete_query = sql.SQL("""
                    DELETE FROM {}.anomaly_reports WHERE flight_id = %s
                """).format(sql.Identifier(schema))
                
                cursor.execute(delete_query, (flight_id,))
                
                # Now insert the new report
                insert_query = sql.SQL("""
                    INSERT INTO {}.anomaly_reports (
                        flight_id, timestamp, is_anomaly, severity_cnn, severity_dense, full_report,
                        callsign, airline, origin_airport, destination_airport, aircraft_type,
                        flight_duration_sec, max_altitude_ft, avg_speed_kts, nearest_airport,
                        geographic_region, is_military,
                        matched_rule_ids, matched_rule_names, matched_rule_categories
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                """).format(sql.Identifier(schema))
                
                cursor.execute(insert_query, (
                    flight_id, timestamp, is_anom, sev_cnn, sev_dense, 
                    json.dumps(report),
                    metadata.get('callsign'), metadata.get('airline'),
                    metadata.get('origin_airport'), metadata.get('destination_airport'),
                    metadata.get('aircraft_type'), metadata.get('flight_duration_sec'),
                    metadata.get('max_altitude_ft'), metadata.get('avg_speed_kts'),
                    nearest_airport, geographic_region, metadata.get('is_military', False),
                    matched_rule_ids, matched_rule_names, matched_rule_categories
                ))
                
                conn.commit()
                logger.debug(f"Saved anomaly report to PostgreSQL for {flight_id}")
                return True
                
    except Exception as e:
        logger.error(f"Failed to save report to PostgreSQL: {e}")
        return False


def check_schema_exists(schema: str = 'live') -> bool:
    """Check if schema exists in PostgreSQL."""
    try:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT schema_name 
                    FROM information_schema.schemata 
                    WHERE schema_name = %s
                """, (schema,))
                return cursor.fetchone() is not None
    except Exception as e:
        logger.error(f"Failed to check schema existence: {e}")
        return False


def test_connection() -> bool:
    """Test PostgreSQL connection."""
    try:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT 1")
                result = cursor.fetchone()
                logger.info(f"PostgreSQL connection test successful: {result}")
                return True
    except Exception as e:
        logger.error(f"PostgreSQL connection test failed: {e}")
        return False
