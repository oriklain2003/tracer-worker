# Flight Replay - Quick Start Guide

## 🚀 Quick Commands

### Replay Entire Flight
```bash
python replay_flight_to_live.py 3cf959dd
```

### Skip to Interesting Part
```bash
# Find good start points (helper script)
python find_start_point.py 3cf959dd

# Then use the suggested point number
python replay_flight_to_live.py 3cf959dd --start-point 1161  # 90%
python replay_flight_to_live.py 3cf959dd --start-point 645   # 50%
python replay_flight_to_live.py 3cf959dd --start-point 1191  # Last 100 points
```

### Test Without Inserting
```bash
python replay_flight_to_live.py 3cf959dd --start-timestamp 1707580800 --dry-run
```

## 📋 Available Flights

From `flight_ids.txt`:
- 3cf85582
- 3cf85e1c
- 3cf86646
- 3cf86754
- 3cf86e35
- 3cf881de
- 3cf88db2
- 3cf8c85f
- 3cf8fc3a
- 3cf959dd ⭐ (recommended for testing)
- 3cf9aa25
- 3cfa09f8
- 3cfa0ee7
- 3cfa4953
- 3cfb0c9f
- 3cfb153c

## 🔍 Find Good Flights

### Get Flight Info & Start Points
```bash
# Quick way - use helper script
python find_start_point.py 3cf959dd

# Shows suggested start points:
#   25%: Point #322
#   50%: Point #645
#   75%: Point #968
#   90%: Point #1161
#   Last 100 points: Point #1191
```

### SQL Method
```sql
SELECT 
    flight_id,
    callsign,
    origin_airport,
    destination_airport,
    total_points,
    flight_duration_sec / 60 as duration_minutes,
    is_anomaly
FROM feedback.flight_metadata
WHERE flight_id = '3cf959dd';
```

### Find Anomalies
```sql
SELECT 
    ar.flight_id,
    fm.callsign,
    ar.matched_rule_names,
    fm.total_points
FROM research.anomaly_reports ar
JOIN research.flight_metadata fm ON ar.flight_id = fm.flight_id
ORDER BY ar.timestamp DESC
LIMIT 10;
```

### Get Timestamp at N% Through Flight
```sql
-- Replace 0.5 with your desired percentage (0.0 to 1.0)
SELECT 
    flight_id,
    MIN(timestamp) as start_ts,
    MIN(timestamp) + (MAX(timestamp) - MIN(timestamp)) * 0.5 as mid_ts,
    MAX(timestamp) as end_ts
FROM research.anomaly_tracks
WHERE flight_id = '3cf959dd'
GROUP BY flight_id;
```

## ⚙️ Options

| Option | Example | Description |
|--------|---------|-------------|
| Basic | `python replay_flight_to_live.py 3cf959dd` | Replay from start |
| Skip to point | `--start-point 1000` | Bulk insert until point number |
| Skip to time | `--start-timestamp 1707580800` | Bulk insert until timestamp |
| Analysis interval | `--interval 10` | Run pipeline every N points |
| Dry run | `--dry-run` | Test without inserting |
| Use original ID | `--use-original-id` | Don't generate new UUID |
| Different schema | `--source-schema feedback` | Change source schema |

## 📊 After Replay

### Check in Database
```sql
-- View flight metadata
SELECT * FROM live.flight_metadata WHERE flight_id = '3cf959dd';

-- Count track points
SELECT COUNT(*) FROM live.normal_tracks WHERE flight_id = '3cf959dd';

-- View anomaly report
SELECT is_anomaly, matched_rule_names 
FROM live.anomaly_reports 
WHERE flight_id = '3cf959dd';
```

### Clean Up When Done
```sql
DELETE FROM live.flight_metadata WHERE flight_id = '3cf959dd';
DELETE FROM live.normal_tracks WHERE flight_id = '3cf959dd';
DELETE FROM live.anomaly_reports WHERE flight_id = '3cf959dd';
DELETE FROM live.ai_classifications WHERE flight_id = '3cf959dd';
```

## 🐛 Troubleshooting

### PyTorch DLL Error
```bash
pip uninstall torch
pip install torch --index-url https://download.pytorch.org/whl/cpu
```

### Flight Not Found
Check if flight exists:
```sql
SELECT COUNT(*) FROM research.anomaly_tracks WHERE flight_id = '3cf959dd';
SELECT COUNT(*) FROM research.normal_tracks WHERE flight_id = '3cf959dd';
```

### Database Connection Error
Check environment variables:
```bash
echo $PG_HOST
echo $PG_USER
echo $PG_PASSWORD
```

## 📖 Full Documentation

- **User Guide**: `REPLAY_FLIGHT_GUIDE.md` (comprehensive examples)
- **Technical Details**: `REPLAY_IMPLEMENTATION_SUMMARY.md` (architecture)
- **Script**: `replay_flight_to_live.py` (implementation)

## 💡 Common Workflows

### Demo for Stakeholders
```bash
# 1. Find a good anomaly flight
# 2. Get timestamp at 80% (skip boring part)
# 3. Replay from there
python replay_flight_to_live.py <flight_id> --start-timestamp <timestamp>
# 4. Watch live UI for anomaly alerts
```

### Test Pipeline Changes
```bash
# 1. Modify anomaly detection rules
# 2. Replay known anomaly flight
python replay_flight_to_live.py <known_anomaly_id>
# 3. Verify it still detects correctly
```

### Train Operators
```bash
# Replay multiple flights in sequence
for id in 3cf959dd 3cfa4953 3cfb0c9f; do
    python replay_flight_to_live.py $id --start-timestamp <ts>
    sleep 5  # Pause between flights
done
```

## ⏱️ Timing Tips

- **Short flights** (<30 min): Replay entire flight
- **Medium flights** (30-90 min): Start at 50-70%
- **Long flights** (>90 min): Start at 80-90%

Use this formula:
```
start_timestamp = first_ts + (last_ts - first_ts) * percentage
```

Where percentage is:
- 0.5 = 50% through flight
- 0.7 = 70% through flight
- 0.8 = 80% through flight

## 🎯 Ready to Go!

```bash
# Test it now!
python replay_flight_to_live.py 3cf959dd --dry-run
```

Happy replaying! 🚀✈️
