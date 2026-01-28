# PostgreSQL Migration for Real-time Monitor

This document describes the migration of `monitor.py` from SQLite to PostgreSQL.

## Overview

The real-time flight monitor now uses PostgreSQL as the primary database for:
- Flight track storage
- Flight metadata
- Anomaly reports

All data is saved to the `live` schema in PostgreSQL, matching the structure created by your migration script.

## Changes Made

### 1. New Files Created

- **`pg_provider.py`**: PostgreSQL database provider with connection pooling
  - `save_flight_tracks()`: Save track points to `normal_tracks` table
  - `save_flight_metadata()`: Save metadata to `flight_metadata` table
  - `save_anomaly_report()`: Save reports to `anomaly_reports` table
  - Connection pooling for thread-safe operations
  - Automatic schema awareness (defaults to 'live')

- **`core/pg_db.py`**: PostgreSQL version of FlightRepository
  - Compatible with SQLite FlightRepository interface
  - Used by anomaly pipeline rule engine
  - Supports spatial queries for proximity rules

### 2. Modified Files

- **`monitor.py`**: Main monitoring script
  - Removed SQLite setup and operations
  - Now uses PostgreSQL exclusively via `pg_provider`
  - Verifies schema exists on startup
  - Initializes connection pool
  - Pipeline configured to use PostgreSQL repository

- **`anomaly_pipeline.py`**: Anomaly detection pipeline
  - Added PostgreSQL support with `use_postgres` parameter
  - Falls back to SQLite if PostgreSQL unavailable
  - Rule engine now queries PostgreSQL for proximity checks

### 3. Removed Code

- SQLite database initialization (`setup_db` method simplified)
- SQLite fallback save methods (`_save_tracks_sqlite`, `_save_metadata_sqlite`, `_save_report_sqlite`)
- `sqlite3` import (no longer needed)

## Database Schema

The monitor uses the `live` schema in PostgreSQL with these tables:

### 1. `normal_tracks`
Stores all flight track points (partitioned by month):
- `flight_id`, `timestamp`, `lat`, `lon`, `alt`
- `gspeed`, `vspeed`, `track`, `squawk`, `callsign`, `source`
- Primary key: `(flight_id, timestamp)`

### 2. `flight_metadata`
Stores comprehensive flight information:
- Identification: `callsign`, `flight_number`, `airline`, `aircraft_type`
- Airports: `origin_airport`, `destination_airport`
- Statistics: `total_points`, `flight_duration_sec`, `total_distance_nm`
- Altitude/Speed: `min/max/avg_altitude_ft`, `cruise_altitude_ft`
- Flags: `is_anomaly`, `is_military`, `emergency_squawk_detected`
- Primary key: `flight_id`

### 3. `anomaly_reports`
Stores anomaly detection results:
- `flight_id`, `timestamp`, `is_anomaly`
- `severity_cnn`, `severity_dense`
- `full_report` (JSONB with all detection layer results)
- Rule matches: `matched_rule_ids`, `matched_rule_names`
- Context: `airline`, `aircraft_type`, `geographic_region`

## Installation

### 1. Install Dependencies

```bash
pip install -r requirements_postgres.txt
```

Or install psycopg2 directly:

```bash
pip install psycopg2-binary
```

### 2. Verify Migration

Ensure the migration script has been run and the `live` schema exists:

```bash
python migrate_sqlite_to_postgres.py
```

### 3. Configure Connection

The PostgreSQL DSN is currently hardcoded in both `pg_provider.py` and `core/pg_db.py`:

```python
PG_DSN = "postgresql://postgres:Warqi4-sywsow-zozfyc@tracer-db.cb80eku2emy0.eu-north-1.rds.amazonaws.com:5432/tracer"
```

**Security Note**: Consider moving credentials to environment variables or a secure config file.

## Running the Monitor

The monitor will now automatically:

1. Connect to PostgreSQL on startup
2. Verify the `live` schema exists
3. Initialize connection pool (2-10 connections)
4. Save all data to PostgreSQL in real-time

```bash
python monitor.py
```

### Startup Checks

The monitor performs these checks on startup:
- ✓ PostgreSQL provider loaded
- ✓ Connection pool initialized
- ✓ Connection test successful
- ✓ Schema 'live' exists
- ✓ PostgreSQL repository connected (for rule engine)

If any check fails, the monitor will exit with an error message.

## Performance Notes

### Connection Pooling
- 2-10 persistent connections maintained
- Thread-safe for concurrent operations
- Automatic connection recycling

### Bulk Inserts
- Track points use `execute_values()` for efficient bulk inserts
- Deduplication handled via `ON CONFLICT DO NOTHING`

### Partitioned Tables
- `normal_tracks` partitioned by month on `timestamp` column
- Automatic partition routing for inserts
- Efficient queries within time ranges

### Indexes
Created by migration script:
- B-tree indexes on: `timestamp`, `flight_id`, `callsign`, `airline`
- BRIN index on partition key for range scans
- Composite indexes for common query patterns

## Troubleshooting

### Connection Errors

If you see "PostgreSQL provider not available":
1. Check psycopg2 is installed: `pip list | grep psycopg2`
2. Verify database is accessible: `psql -h tracer-db.cb80eku2emy0.eu-north-1.rds.amazonaws.com -U postgres -d tracer`
3. Check firewall/security group settings

### Schema Not Found

If you see "schema 'live' does not exist":
1. Run the migration script first
2. Verify schema creation: `SELECT schema_name FROM information_schema.schemata;`

### Performance Issues

If inserts are slow:
1. Check connection pool size in `pg_provider.py`
2. Verify indexes exist: `\d live.normal_tracks` in psql
3. Monitor partition creation for new months

## Comparison: SQLite vs PostgreSQL

| Feature | SQLite (Old) | PostgreSQL (New) |
|---------|-------------|------------------|
| Connection | Single file | Connection pool |
| Concurrency | File locking | Row-level locking |
| Scalability | Limited | Unlimited |
| Partitioning | Not supported | Monthly partitions |
| Type system | Dynamic | Strong typing |
| JSON support | Limited | JSONB with indexing |
| Backup | File copy | pg_dump/WAL |
| Remote access | Not supported | Native support |

## Future Enhancements

### Recommended Improvements

1. **Environment Variables**: Move credentials to `.env` file
2. **Schema Versioning**: Track schema migrations with Alembic
3. **Monitoring**: Add PostgreSQL performance metrics
4. **Replication**: Set up read replicas for queries
5. **Archival**: Implement automatic partition archival for old data
6. **Analytics**: Add materialized views for common aggregations

### Optional Features

- Query caching with Redis
- Time-series optimization with TimescaleDB extension
- Full-text search on flight metadata
- PostGIS extension for advanced spatial queries

## Support

For issues or questions:
1. Check PostgreSQL logs: `tail -f /var/log/postgresql/postgresql.log`
2. Monitor connections: `SELECT * FROM pg_stat_activity WHERE datname = 'tracer';`
3. Check table sizes: `SELECT pg_size_pretty(pg_total_relation_size('live.normal_tracks'));`

## Rollback (If Needed)

To temporarily revert to SQLite:

1. In `monitor.py`, change imports:
```python
PG_AVAILABLE = False  # Force disable
```

2. In `anomaly_pipeline.py`:
```python
self.pipeline = AnomalyPipeline(use_postgres=False)
```

However, the SQLite save methods have been removed, so you would need to restore them from git history.
