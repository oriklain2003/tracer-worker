# Marine Data Pipeline Setup Guide

This guide explains how to set up and run the marine vessel tracking pipeline.

## Overview

The marine data pipeline connects to AISstream.io's WebSocket API to receive real-time ship position and voyage data, then stores it in PostgreSQL for analysis.

## Prerequisites

1. **AISstream.io API Key**: Sign up at https://aisstream.io/authenticate (free)
2. **PostgreSQL Database**: Access to the tracer PostgreSQL database
3. **Python Dependencies**: Install via `pip install -r requirements.txt`

## Setup Steps

### 1. Create Database Schema

Run the SQL schema creation script to create the `marine` schema and tables:

```bash
psql -h tracer-db.cb80eku2emy0.eu-north-1.rds.amazonaws.com -U postgres -d tracer -f create_marine_schema.sql
```

Or connect via any PostgreSQL client and run the contents of `create_marine_schema.sql`.

This creates:
- Schema: `marine`
- Table: `marine.vessel_positions` (partitioned by timestamp)
- Table: `marine.vessel_metadata`
- Appropriate indexes for efficient querying

### 2. Set Environment Variables

Create a `.env` file or export environment variables:

```bash
# Required
export AIS_STREAM_API_KEY="806cb56388d212f6d346775d69190649dc456907"
export PG_PASSWORD="your_database_password"

# Optional - defaults shown
export PG_HOST="tracer-db.cb80eku2emy0.eu-north-1.rds.amazonaws.com"
export PG_PORT="5432"
export PG_DATABASE="tracer"
export PG_USER="postgres"
export AIS_BATCH_SIZE="100"

# Optional - geographic filtering
# Default is global coverage: [[[-90, -180], [90, 180]]]
export AIS_BOUNDING_BOX='[[[-90, -180], [90, 180]]]'

# Optional - filter specific vessels by MMSI
# export AIS_FILTER_MMSI="368207620,367719770,211476060"
```

### 3. Install Dependencies

**Option A: Using uv (Recommended - Fast)**

```bash
# Install uv if not already installed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Run with uv (automatically handles dependencies)
cd tracer-worker
./run_marine_uv.sh
```

**Option B: Using pip**

```bash
cd tracer-worker
pip install -r requirements.txt
```

This will install:
- `websockets>=12.0` for WebSocket connectivity
- `psycopg2-binary` for PostgreSQL access
- Other existing dependencies

### 4. Run the Marine Monitor

**With uv (Recommended):**

```bash
./run_marine_uv.sh
```

**With Python:**

```bash
python run_marine_monitor.py
```

Or run directly:

```bash
python marine_monitor.py
```

The monitor will:
1. Connect to AISstream.io WebSocket
2. Subscribe to vessel position and static data messages
3. Process incoming messages in real-time
4. Batch insert positions to database (default: every 100 messages)
5. Update vessel metadata as received
6. Log statistics every 60 seconds
7. Automatically reconnect on connection loss

### 5. Verify Data

Check that data is being saved:

```sql
-- Count recent vessel positions (last hour)
SELECT COUNT(*) as position_count
FROM marine.vessel_positions
WHERE timestamp > NOW() - INTERVAL '1 hour';

-- View unique vessels tracked
SELECT COUNT(DISTINCT mmsi) as unique_vessels
FROM marine.vessel_positions
WHERE timestamp > NOW() - INTERVAL '1 hour';

-- View vessel metadata
SELECT mmsi, vessel_name, vessel_type_description, destination, last_updated
FROM marine.vessel_metadata
ORDER BY last_updated DESC
LIMIT 10;

-- Recent vessel positions with metadata
SELECT 
    vp.mmsi,
    vm.vessel_name,
    vm.vessel_type_description,
    vp.latitude,
    vp.longitude,
    vp.speed_over_ground,
    vp.navigation_status,
    vp.timestamp
FROM marine.vessel_positions vp
LEFT JOIN marine.vessel_metadata vm USING (mmsi)
WHERE vp.timestamp > NOW() - INTERVAL '1 hour'
ORDER BY vp.timestamp DESC
LIMIT 20;
```

## Architecture

### Components

1. **marine_models.py**: Data models (VesselPosition, VesselMetadata)
2. **marine_pg_provider.py**: Database operations
3. **marine_monitor.py**: WebSocket worker with reconnection logic
4. **run_marine_monitor.py**: Entry point script
5. **create_marine_schema.sql**: Database schema definition

### Data Flow

```
AISstream.io WebSocket
    ↓ (JSON messages)
MarineMonitor.process_message()
    ↓ (parse & validate)
VesselPosition / VesselMetadata dataclasses
    ↓ (batch for positions)
marine_pg_provider functions
    ↓ (SQL insert/upsert)
PostgreSQL marine schema
```

### Message Types

- **PositionReport** (AIS types 1, 2, 3, 18): Real-time vessel positions
- **ShipStaticData** (AIS type 5): Vessel metadata and voyage information

## Configuration Options

### Bounding Boxes

Filter vessels by geographic region. Format: `[[[south_lat, west_lon], [north_lat, east_lon]], ...]`

Examples:

```bash
# Global coverage (default)
export AIS_BOUNDING_BOX='[[[-90, -180], [90, 180]]]'

# Mediterranean Sea
export AIS_BOUNDING_BOX='[[[30, -6], [46, 37]]]'

# Multiple regions
export AIS_BOUNDING_BOX='[[[30, -6], [46, 37]], [[50, -130], [72, -55]]]'
```

### MMSI Filtering

Track specific vessels by their MMSI codes:

```bash
export AIS_FILTER_MMSI="368207620,367719770,211476060"
```

### Batch Size

Control how many position reports are batched before database insert:

```bash
export AIS_BATCH_SIZE="100"  # Default
export AIS_BATCH_SIZE="50"   # More frequent inserts, higher DB load
export AIS_BATCH_SIZE="500"  # Less frequent inserts, lower DB load
```

## Monitoring

The monitor logs statistics every 60 seconds:

```
========================================================
Marine Monitor Statistics
========================================================
Running time: 3600 seconds
Messages received: 12540
Positions saved: 12000
Metadata records saved: 128
Unique vessels tracked: 345
Message rate: 3.48 msg/sec
Errors: 0
========================================================
```

Logs are written to:
- Console (stdout)
- File: `marine_monitor.log`

## Graceful Shutdown

Press `Ctrl+C` to stop the monitor gracefully. It will:
1. Flush any remaining batched positions
2. Close the WebSocket connection
3. Log final statistics

## Troubleshooting

### Connection Issues

If WebSocket connection fails:
- Check API key is valid
- Check internet connectivity
- Monitor will auto-reconnect with exponential backoff

### Database Issues

If database inserts fail:
- Verify marine schema exists (run `create_marine_schema.sql`)
- Check database credentials
- Verify PostgreSQL is accessible
- Check connection pool settings in `pg_provider.py`

### No Data Appearing

If no vessels are being tracked:
- Check bounding box covers desired area
- Verify AISstream.io API key is active
- Some areas may have low vessel traffic
- Try global coverage: `[[[-90, -180], [90, 180]]]`

## Performance

### Database Partitioning

The `vessel_positions` table is partitioned by timestamp (monthly). Create new partitions as needed:

```sql
-- Create partition for March 2026
CREATE TABLE IF NOT EXISTS marine.vessel_positions_2026_03 
PARTITION OF marine.vessel_positions
FOR VALUES FROM ('2026-03-01') TO ('2026-04-01');
```

### Batch Processing

- Default batch size: 100 positions
- Positions are batched in memory before database insert
- Adjust `AIS_BATCH_SIZE` based on message volume and database load

### Connection Pooling

- Reuses existing connection pool from `pg_provider.py`
- Default: 2-10 connections
- Thread-safe for concurrent operations

## Integration with Existing System

The marine pipeline follows the same patterns as the flight tracking system:

- Similar structure to `monitor.py` (flight tracking)
- Uses same connection pool as flight data
- Follows same dataclass patterns (`core/models.py`)
- Compatible logging and error handling
- Can run alongside flight tracking without conflicts

## Future Enhancements

Potential additions (not yet implemented):

- Anomaly detection for marine vessels
- Vessel trajectory analysis
- Integration with anomaly-prod UI
- Historical data archival (similar to research schema)
- Marine traffic heatmaps
- Port traffic analysis

## API Documentation

For more details on AIS message formats and AISstream.io API:
- https://aisstream.io/documentation
- AIS message types: https://gpsd.gitlab.io/gpsd/AIVDM.html
