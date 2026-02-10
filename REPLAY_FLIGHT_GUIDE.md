# Flight Replay Guide - Research → Live

## Overview

The `replay_flight_to_live.py` script simulates how anomalies appear in the live monitoring system by replaying historical flights from the research schema into the live schema with real-time delays between points.

This is useful for:
- **Demos**: Show how anomalies are detected in real-time
- **Testing**: Validate anomaly detection pipeline behavior
- **Training**: Train operators on the live monitoring interface
- **Debugging**: Reproduce specific anomaly detection scenarios

## How It Works

```
Research Schema          Replay Script           Live Schema
─────────────────        ─────────────────       ─────────────
anomaly_tracks    ──┐
                    ├──> Load Flight Data ──> Delete Existing ──> Bulk Insert ──> Real-time Replay
normal_tracks     ──┘    + metadata              (cleanup)        (instant)       (with delays)
                         + anomaly report                                               │
                                                                                        │
                                                                                  Run Pipeline
                                                                                  Detect Anomalies
                                                                                  Save to live.*
```

### Key Features

1. **Two-Phase Insertion**:
   - **Phase 1 (Bulk)**: Instantly insert all points before a specified timestamp
   - **Phase 2 (Real-time)**: Replay remaining points with actual time delays

2. **Timestamp Adjustment**: All timestamps are shifted to appear as "happening now"

3. **Incremental Anomaly Detection**: The anomaly pipeline analyzes the flight incrementally, just like live monitoring

4. **Progress Logging**: Real-time progress with anomaly alerts

## Quick Start

### Basic Usage

Replay entire flight in real-time:
```bash
python replay_flight_to_live.py 3d7211ef
```

### Jump to Specific Point

Bulk insert points up to a timestamp, then replay from there:
```bash
python replay_flight_to_live.py 3d7211ef --start-timestamp 1707580800
```

**How to find a good start timestamp:**
```sql
-- Get timestamp at 50% through the flight
SELECT 
    flight_id,
    MIN(timestamp) as first_ts,
    MAX(timestamp) as last_ts,
    MIN(timestamp) + (MAX(timestamp) - MIN(timestamp)) / 2 as mid_ts
FROM research.anomaly_tracks
WHERE flight_id = '3d7211ef'
GROUP BY flight_id;
```

### Custom Analysis Interval

Analyze every N points (default is 5):
```bash
python replay_flight_to_live.py 3d7211ef --interval 10
```

### Dry Run

See what would happen without inserting data:
```bash
python replay_flight_to_live.py 3d7211ef --start-timestamp 1707580800 --dry-run
```

## Command-Line Options

| Option | Description | Default |
|--------|-------------|---------|
| `flight_id` | Flight ID from research schema (required) | - |
| `--start-timestamp` | Unix timestamp to start real-time replay | None (replay from beginning) |
| `--interval` | Points interval for anomaly analysis | 5 |
| `--source-schema` | Source schema name | research |
| `--dest-schema` | Destination schema name | live |
| `--dry-run` | Show what would be done without inserting | False |

## Workflow Examples

### Example 1: Demo Anomaly Detection

You want to demo an anomaly that was detected at point 500 out of 800 total points.

```bash
# Find the timestamp at point 450 (just before anomaly)
SELECT timestamp 
FROM research.anomaly_tracks 
WHERE flight_id = '3d7211ef' 
ORDER BY timestamp 
LIMIT 1 OFFSET 449;

# Result: 1707580800

# Replay from point 450
python replay_flight_to_live.py 3d7211ef --start-timestamp 1707580800
```

**Result**: Points 1-449 are inserted instantly. Points 450+ replay in real-time with delays, showing the anomaly detection as it happens.

### Example 2: Test Long Flight

Flight duration is 3 hours. You don't want to wait 3 hours.

```bash
# Start from 2.5 hours in
SELECT timestamp 
FROM research.anomaly_tracks 
WHERE flight_id = '3d7211ef' 
ORDER BY timestamp 
LIMIT 1 OFFSET <calculated_point>;

# Replay from that point
python replay_flight_to_live.py 3d7211ef --start-timestamp <timestamp>
```

### Example 3: Reproduce Bug

You noticed a false positive in the live system and want to reproduce it.

```bash
# Get the exact flight from research schema
python replay_flight_to_live.py 3d7211ef

# Watch the logs to see when and why it triggers
```

## What Happens During Replay

### 1. Loading Phase
```
Loading flight 3d7211ef from research schema...
✓ Loaded 1234 track points from research.anomaly_tracks
✓ Loaded metadata: ELY123 | LLBG → EHAM
✓ Loaded existing anomaly report
```

### 2. Cleanup Phase
```
Cleaning up existing data for 3d7211ef in live schema...
  Deleted 245 rows from live.normal_tracks
  Deleted 1 rows from live.flight_metadata
  Deleted 1 rows from live.anomaly_reports
✓ Cleanup complete for 3d7211ef
```

### 3. Bulk Insert Phase (if using --start-timestamp)
```
PHASE 1: BULK INSERT
Bulk inserting 800 points to live.normal_tracks...
✓ Bulk insert complete
✓ 800 points inserted instantly
  Time range: 14:30:00 to 16:45:00
```

### 4. Real-time Replay Phase
```
PHASE 2: REAL-TIME REPLAY
Starting real-time replay of 434 points...
Press Ctrl+C to stop gracefully

[Point 850/1234] 16:45:12 | Lat 32.1234, Lon 34.5678, Alt 35000ft
✓ Normal (confidence: 45.2%)

[Point 900/1234] 16:47:23 | Lat 32.2345, Lon 34.6789, Alt 34500ft
################################################################################
🚨 FIRST ANOMALY DETECTED!
   Point: 900
   Time: 16:47:23
   Confidence: 78.5%
   Triggers: layer_1_rules, layer_4_deep_cnn
################################################################################

[Point 950/1234] 16:49:45 | Lat 32.3456, Lon 34.7890, Alt 33000ft
🚨 Anomaly continues (confidence: 82.1%)
```

### 5. Completion
```
REPLAY COMPLETE
Total Points Replayed: 1234
  Bulk Inserted: 800
  Real-time: 434

✓ Anomaly detected at point 900
```

## Finding Flights to Replay

### Get Recent Anomalies
```sql
SELECT 
    flight_id,
    callsign,
    origin_airport,
    destination_airport,
    COUNT(*) as points
FROM research.anomaly_tracks
GROUP BY flight_id, callsign, origin_airport, destination_airport
ORDER BY MAX(timestamp) DESC
LIMIT 10;
```

### Get Specific Rule Matches
```sql
SELECT 
    ar.flight_id,
    fm.callsign,
    ar.matched_rule_names,
    COUNT(at.timestamp) as points
FROM research.anomaly_reports ar
JOIN research.flight_metadata fm ON ar.flight_id = fm.flight_id
JOIN research.anomaly_tracks at ON ar.flight_id = at.flight_id
WHERE ar.matched_rule_names ILIKE '%off_course%'
GROUP BY ar.flight_id, fm.callsign, ar.matched_rule_names
LIMIT 10;
```

### Get Flights with Many Points (Long Flights)
```sql
SELECT 
    flight_id,
    callsign,
    total_points,
    flight_duration_sec / 60.0 as duration_minutes
FROM research.flight_metadata
WHERE total_points > 500
ORDER BY total_points DESC
LIMIT 10;
```

## Timestamp Adjustment Logic

The script preserves relative time differences but shifts absolute timestamps to "now":

```python
# Original flight
Point 1: 1707560000 (2024-02-10 10:00:00)
Point 2: 1707560008 (2024-02-10 10:00:08)  # 8 seconds later
Point 3: 1707560015 (2024-02-10 10:00:15)  # 7 seconds later

# Current time when replaying
Current: 1738843200 (2026-02-10 15:00:00)

# Time offset
offset = 1738843200 - 1707560000 = 31283200

# Adjusted timestamps (if bulk insert)
Point 1: 1738843200 (2026-02-10 15:00:00)
Point 2: 1738843208 (2026-02-10 15:00:08)  # Still 8 seconds later
Point 3: 1738843215 (2026-02-10 15:00:15)  # Still 7 seconds later

# Real-time replay
Point 4: Inserted at actual current time (e.g., 15:00:22)
  Wait 7 seconds...
Point 5: Inserted at actual current time (e.g., 15:00:29)
  Wait 6 seconds...
Point 6: Inserted at actual current time (e.g., 15:00:35)
```

## Troubleshooting

### Flight Not Found
```
No track points found for flight 3d7211ef in research schema
```

**Solution**: Check if the flight exists:
```sql
SELECT COUNT(*) FROM research.anomaly_tracks WHERE flight_id = '3d7211ef';
SELECT COUNT(*) FROM research.normal_tracks WHERE flight_id = '3d7211ef';
```

### Invalid Timestamp
```
Invalid start timestamp 1707580800. Must be between 1707560000 and 1707565000
```

**Solution**: The timestamp is outside the flight's time range. Query the flight's time range:
```sql
SELECT MIN(timestamp), MAX(timestamp) 
FROM research.anomaly_tracks 
WHERE flight_id = '3d7211ef';
```

### Database Connection Error
```
Failed to initialize PostgreSQL connection pool
```

**Solution**: Check your environment variables:
```bash
echo $PG_HOST
echo $PG_USER
echo $PG_DATABASE
```

Or set them:
```bash
export PG_HOST=your-host
export PG_PASSWORD=your-password
```

### Graceful Exit
Press `Ctrl+C` during replay to stop gracefully:
```
⚠️  Replay interrupted by user
Progress: 234/434 real-time points processed
```

The script will stop cleanly. You can restart it or query the live schema to see partially replayed data.

## Tips & Best Practices

1. **Use --dry-run first**: Always test with --dry-run to see what will happen

2. **Find interesting points**: Use SQL to find when anomalies were first detected:
   ```sql
   SELECT flight_id, MIN(timestamp) 
   FROM research.anomaly_tracks 
   WHERE flight_id = '3d7211ef' 
   GROUP BY flight_id;
   ```

3. **Clean up after demos**: The script cleans up automatically, but you can manually clean:
   ```sql
   DELETE FROM live.flight_metadata WHERE flight_id = '3d7211ef';
   DELETE FROM live.normal_tracks WHERE flight_id = '3d7211ef';
   DELETE FROM live.anomaly_reports WHERE flight_id = '3d7211ef';
   ```

4. **Monitor progress**: Watch the log output to see real-time progress and anomaly detections

5. **Speed it up**: Use larger --interval values (e.g., 10 or 20) to run pipeline less frequently

## Integration with Live Monitoring

After replay completes, the flight appears in the live schema exactly as if it was just detected:

```sql
-- View the replayed flight
SELECT * FROM live.flight_metadata WHERE flight_id = '3d7211ef';

-- View the track points
SELECT COUNT(*) FROM live.normal_tracks WHERE flight_id = '3d7211ef';

-- View the anomaly report
SELECT * FROM live.anomaly_reports WHERE flight_id = '3d7211ef';

-- View AI classification (if generated)
SELECT * FROM live.ai_classifications WHERE flight_id = '3d7211ef';
```

You can then view it in the web UI at the live monitoring dashboard!

## Performance Considerations

- **Bulk insert**: Very fast, can insert thousands of points in seconds
- **Real-time replay**: Bounded by actual flight delays (can't speed up)
- **Anomaly analysis**: Takes ~2-5 seconds per analysis, run every N points
- **Database**: Uses connection pooling for efficiency

## Example Session

```bash
$ python replay_flight_to_live.py 3d7211ef --start-timestamp 1707580800

================================================================================
FLIGHT REPLAY TO LIVE - REAL-TIME SIMULATION
================================================================================
Flight ID: 3d7211ef
Source Schema: research
Destination Schema: live
Start Timestamp: 1707580800
Analysis Interval: Every 5 points
Dry Run: False
================================================================================

Loading flight 3d7211ef from research schema...
✓ Loaded 1234 track points from research.anomaly_tracks
✓ Loaded metadata: ELY123 | LLBG → EHAM
✓ Loaded existing anomaly report

Flight Details:
  Total Points: 1234
  First Point: 2024-02-10 10:00:00
  Last Point: 2024-02-10 13:15:30
  Duration: 195.5 minutes
  Callsign: ELY123
  Route: LLBG → EHAM

Replay Strategy:
  Phase 1 (Bulk Insert): 800 points before timestamp 1707580800
  Phase 2 (Real-time): 434 points from timestamp onwards

Cleaning up existing data for 3d7211ef in live schema...
  Deleted 0 rows from live.ai_classifications
  Deleted 0 rows from live.anomaly_reports
  Deleted 0 rows from live.normal_tracks
  Deleted 0 rows from live.flight_metadata
✓ Cleanup complete for 3d7211ef

================================================================================
PHASE 1: BULK INSERT
================================================================================
Bulk inserting 800 points to live.normal_tracks...
✓ Bulk insert complete
✓ 800 points inserted instantly
  Time range: 14:30:00 to 16:45:00

================================================================================
PHASE 2: REAL-TIME REPLAY
================================================================================
Starting real-time replay of 434 points...
Press Ctrl+C to stop gracefully

✓ Anomaly pipeline initialized

[Point 800/1234] 16:45:05 | Lat 32.1234, Lon 34.5678, Alt 35000ft
✓ Normal (confidence: 42.3%)

[Point 805/1234] 16:45:45 | Lat 32.1456, Lon 34.5890, Alt 34800ft
✓ Normal (confidence: 45.1%)

[Point 900/1234] 16:47:23 | Lat 32.2345, Lon 34.6789, Alt 34500ft
################################################################################
🚨 FIRST ANOMALY DETECTED!
   Point: 900
   Time: 16:47:23
   Confidence: 78.5%
   Triggers: layer_1_rules, layer_4_deep_cnn
################################################################################

[Point 905/1234] 16:47:48 | Lat 32.2567, Lon 34.7012, Alt 34200ft
🚨 Anomaly continues (confidence: 82.1%)

...

================================================================================
REPLAY COMPLETE
================================================================================
Total Points Replayed: 1234
  Bulk Inserted: 800
  Real-time: 434

✓ Anomaly detected at point 900
================================================================================
```

## Next Steps

After replaying a flight:

1. **View in UI**: Open the live monitoring web interface
2. **Check AI Classification**: Run `batch_classify_flights.py` to get AI analysis
3. **Query Data**: Use SQL to analyze the replayed flight
4. **Clean Up**: Delete the flight from live schema when done

Happy replaying! 🚀
