# Quick Start Guide - PostgreSQL Monitor

Get the PostgreSQL-based monitor running in 3 simple steps.

## Prerequisites

✅ Migration script has been run (data in `live` schema)  
✅ PostgreSQL accessible at: `tracer-db.cb80eku2emy0.eu-north-1.rds.amazonaws.com`

## Step 1: Install Dependencies

```bash
cd c:\Users\macab\Desktop\fiveair\anomaly-last\repo\monitor
pip install psycopg2-binary
```

## Step 2: Test Connection

```bash
python test_postgres_connection.py
```

**Expected:** All 6 tests should pass ✓

## Step 3: Run Monitor

```bash
python monitor.py
```

**That's it!** The monitor is now running and saving to PostgreSQL.

---

## What the Monitor Does

Every 4 seconds:
1. Fetches live flights from FlightRadar24
2. Analyzes tracks for anomalies (6 detection layers)
3. Saves data to PostgreSQL `live` schema:
   - Track points → `normal_tracks`
   - Flight info → `flight_metadata`
   - Detections → `anomaly_reports`

## Verify It's Working

### Check Logs
```bash
tail -f live_monitor.log
```

Look for:
- `PostgreSQL connected successfully (schema: live)`
- `New flight tracked: [ID] ([CALLSIGN])`
- `Saved X track points to PostgreSQL`

### Check Database
```sql
-- Connect to database
psql -h tracer-db.cb80eku2emy0.eu-north-1.rds.amazonaws.com -U postgres -d tracer

-- Check recent data (last hour)
SELECT COUNT(*) FROM live.normal_tracks 
WHERE timestamp > extract(epoch from now() - interval '1 hour');

-- Check active flights
SELECT DISTINCT callsign, COUNT(*) as points
FROM live.normal_tracks
WHERE timestamp > extract(epoch from now() - interval '10 minutes')
GROUP BY callsign
ORDER BY points DESC;

-- Check for anomalies detected
SELECT flight_id, callsign, is_anomaly, matched_rule_names
FROM live.anomaly_reports
WHERE timestamp > extract(epoch from now() - interval '1 hour')
AND is_anomaly = true;
```

## Troubleshooting

### ❌ "psycopg2 not found"
```bash
pip install psycopg2-binary
```

### ❌ "Schema 'live' does not exist"
Run the migration script first to create the schema.

### ❌ "Connection refused"
Check:
- Database is running
- Correct host/port in connection string
- Network/firewall allows connection
- VPN is connected (if required)

### ❌ Monitor exits immediately
Check `live_monitor.log` for error details.

## Configuration

### Change Schema
Edit in 3 files:
- `monitor.py` line 598: `self.schema = 'live'`
- `pg_provider.py` line 18: `PG_DSN = "..."`
- `core/pg_db.py` line 18: default schema

### Change Poll Interval
Edit `monitor.py` line 66:
```python
POLL_INTERVAL = 4  # seconds between updates
```

### Change Region
Edit `monitor.py` lines 60-63:
```python
MIN_LAT = TRAIN_SOUTH  # From core.config
MAX_LAT = TRAIN_NORTH
MIN_LON = TRAIN_WEST
MAX_LON = TRAIN_EAST
```

## Performance Notes

- **Connection pooling**: 2-10 connections maintained
- **Bulk inserts**: Track points saved in batches
- **Partitioning**: Data auto-routed to monthly partitions
- **Deduplication**: Automatic via `ON CONFLICT DO NOTHING`

## Monitoring Tips

### CPU Usage
Monitor should use ~10-20% CPU during active tracking

### Memory Usage
Typical: 200-500 MB depending on active flights

### Network
~50-100 KB/s for API calls + database writes

### Database Growth
Approximately:
- 100 flights/day × 500 points/flight = 50,000 rows/day
- ~5 MB/day in `normal_tracks` table
- ~150 MB/month (before compression)

## Files Reference

| File | Purpose |
|------|---------|
| `monitor.py` | Main monitoring script |
| `pg_provider.py` | PostgreSQL database operations |
| `core/pg_db.py` | Repository for rule engine |
| `anomaly_pipeline.py` | 6-layer detection system |
| `test_postgres_connection.py` | Verify setup |
| `live_monitor.log` | Application logs |

## Stopping the Monitor

Press `Ctrl+C` to stop gracefully.

The monitor will:
1. Complete current API call
2. Save buffered data
3. Close database connections
4. Exit cleanly

## Running in Background

### Windows (using pythonw)
```bash
start /B pythonw monitor.py
```

### Linux/Mac (using nohup)
```bash
nohup python monitor.py > output.log 2>&1 &
```

### Using screen (Linux/Mac)
```bash
screen -S monitor
python monitor.py
# Detach with Ctrl+A, D
# Reattach with: screen -r monitor
```

### Using PM2 (Node.js process manager)
```bash
pm2 start monitor.py --interpreter python3 --name flight-monitor
pm2 logs flight-monitor
pm2 stop flight-monitor
```

## Getting Help

1. **Check logs**: `live_monitor.log`
2. **Test connection**: `python test_postgres_connection.py`
3. **Review docs**: `POSTGRES_MIGRATION_README.md`
4. **Check database**: Query `live` schema tables

---

## Summary Commands

```bash
# Install
pip install psycopg2-binary

# Test
python test_postgres_connection.py

# Run
python monitor.py

# Monitor
tail -f live_monitor.log

# Query Database
psql -h tracer-db.cb80eku2emy0.eu-north-1.rds.amazonaws.com -U postgres -d tracer
```

**That's all you need!** 🚀
