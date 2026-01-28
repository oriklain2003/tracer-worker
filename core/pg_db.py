"""
PostgreSQL-based FlightRepository

Provides the same interface as the SQLite FlightRepository but uses PostgreSQL.
"""
from __future__ import annotations

import psycopg2
import psycopg2.extras
from psycopg2 import sql
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Generator, Iterable, List, Optional

from .models import FlightTrack, TrackPoint


@dataclass
class PgDbConfig:
    """PostgreSQL database configuration."""
    dsn: str
    schema: str = "live"
    table: str = "normal_tracks"


class PgFlightRepository:
    """PostgreSQL-based flight repository with the same interface as SQLite version."""
    
    def __init__(self, config: Optional[PgDbConfig] = None):
        if config is None:
            # Default configuration
            config = PgDbConfig(
                dsn="postgresql://postgres:Warqi4-sywsow-zozfyc@tracer-db.cb80eku2emy0.eu-north-1.rds.amazonaws.com:5432/tracer",
                schema="live",
                table="normal_tracks"
            )
        self._config = config

    @contextmanager
    def _connection(self) -> Generator[psycopg2.extensions.connection, None, None]:
        """Context manager for PostgreSQL connections."""
        conn = psycopg2.connect(self._config.dsn)
        try:
            yield conn
        finally:
            conn.close()

    def fetch_flight(self, flight_id: str) -> FlightTrack:
        """Fetch all points for a specific flight."""
        with self._connection() as conn:
            with conn.cursor() as cursor:
                query = sql.SQL("""
                    SELECT flight_id, timestamp, lat, lon, alt, gspeed, vspeed, track, squawk, callsign, source
                    FROM {}.{}
                    WHERE flight_id = %s
                    ORDER BY timestamp ASC
                """).format(
                    sql.Identifier(self._config.schema),
                    sql.Identifier(self._config.table)
                )
                cursor.execute(query, (flight_id,))
                points = [self._row_to_point(row) for row in cursor.fetchall()]
                return FlightTrack(flight_id=flight_id, points=points)

    def iter_flights(self, limit: Optional[int] = None, min_points: int = 2) -> Iterable[FlightTrack]:
        """Iterate over all flights with at least min_points."""
        with self._connection() as conn:
            with conn.cursor() as cursor:
                # First, get flight IDs with enough points
                query = sql.SQL("""
                    SELECT flight_id, COUNT(*) as cnt
                    FROM {}.{}
                    GROUP BY flight_id
                    HAVING COUNT(*) >= %s
                    ORDER BY COUNT(*) DESC
                    {limit_clause}
                """).format(
                    sql.Identifier(self._config.schema),
                    sql.Identifier(self._config.table),
                    limit_clause=sql.SQL(f"LIMIT {int(limit)}") if limit else sql.SQL("")
                )
                cursor.execute(query, (min_points,))
                flight_ids = [row[0] for row in cursor.fetchall()]
        
        # Fetch each flight
        for flight_id in flight_ids:
            yield self.fetch_flight(flight_id)

    def fetch_points_between(self, start_ts: int, end_ts: int) -> List[TrackPoint]:
        """Fetch all track points within a timestamp range."""
        with self._connection() as conn:
            with conn.cursor() as cursor:
                query = sql.SQL("""
                    SELECT flight_id, timestamp, lat, lon, alt, gspeed, vspeed, track, squawk, callsign, source
                    FROM {}.{}
                    WHERE timestamp BETWEEN %s AND %s
                    ORDER BY timestamp ASC
                """).format(
                    sql.Identifier(self._config.schema),
                    sql.Identifier(self._config.table)
                )
                cursor.execute(query, (start_ts, end_ts))
                return [self._row_to_point(row) for row in cursor.fetchall()]

    def fetch_tracks_in_box(self, min_lat: float, max_lat: float, min_lon: float, max_lon: float) -> List[FlightTrack]:
        """Fetch all flight tracks that have points within the specified bounding box."""
        flight_ids = self.fetch_flight_ids_in_box(min_lat, max_lat, min_lon, max_lon)
        return [self.fetch_flight(fid) for fid in flight_ids]

    def fetch_flight_ids_in_box(self, min_lat: float, max_lat: float, min_lon: float, max_lon: float) -> List[str]:
        """Fetch flight IDs that have at least one point within the specified bounding box."""
        with self._connection() as conn:
            with conn.cursor() as cursor:
                query = sql.SQL("""
                    SELECT DISTINCT flight_id
                    FROM {}.{}
                    WHERE lat BETWEEN %s AND %s
                      AND lon BETWEEN %s AND %s
                """).format(
                    sql.Identifier(self._config.schema),
                    sql.Identifier(self._config.table)
                )
                cursor.execute(query, (min_lat, max_lat, min_lon, max_lon))
                return [row[0] for row in cursor.fetchall()]

    @staticmethod
    def _row_to_point(row) -> TrackPoint:
        """Convert database row to TrackPoint object."""
        (
            flight_id,
            timestamp,
            lat,
            lon,
            alt,
            gspeed,
            vspeed,
            track,
            squawk,
            callsign,
            source,
        ) = row
        return TrackPoint(
            flight_id=flight_id or "UNKNOWN",
            timestamp=int(timestamp),
            lat=float(lat),
            lon=float(lon),
            alt=float(alt or 0.0),
            gspeed=float(gspeed) if gspeed is not None else None,
            vspeed=float(vspeed) if vspeed is not None else None,
            track=float(track) if track is not None else None,
            squawk=str(squawk) if squawk is not None else None,
            callsign=callsign,
            source=source,
        )
