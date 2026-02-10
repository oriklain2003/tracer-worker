# Flight Replay Script - Complete Feature Summary

## ✅ ALL FEATURES IMPLEMENTED

**Script**: `replay_flight_to_live.py`  
**Version**: 2.2  
**Status**: Production Ready  
**Date**: 2026-02-10  

---

## 🎯 Core Features

### 1. ✅ Data Loading with Fallback
- Load from feedback/research schema
- Try multiple tables: `anomaly_tracks` → `normal_tracks` → `flight_tracks`
- Load complete flight metadata
- Load existing anomaly reports

### 2. ✅ UUID Generation (NEW!)
- **Default**: Generate unique UUID4 for each replay
- Allows multiple replays of same flight
- No data loss or overwrites
- Optional: Use original ID with `--use-original-id`

### 3. ✅ Point Number Selection (NEW!)
- **`--start-point`**: Specify by point number (0-based)
- More intuitive than timestamps
- Example: `--start-point 1000` = start from point #1000
- Helper script: `find_start_point.py` shows suggested points

### 4. ✅ Timestamp Selection
- **`--start-timestamp`**: Specify by Unix timestamp
- Backwards compatible with old scripts
- Cannot use with `--start-point` (mutually exclusive)

### 5. ✅ Two-Phase Insertion
- **Phase 1 (Bulk)**: Instant insert of points before start
- **Phase 2 (Real-time)**: Replay remaining with actual delays
- Configurable split point

### 6. ✅ Real-Time Delay Simulation
- Preserves exact timing between points
- Sleeps between insertions
- Logs wait times (minutes/seconds)
- Accurate flight behavior replication

### 7. ✅ Timestamp Adjustment
- All timestamps shifted to "now"
- `first_seen_ts` matches first track point
- `last_seen_ts` matches last track point
- Scheduled times adjusted (if numeric)
- Relative timing preserved

### 8. ✅ Incremental Anomaly Detection
- Runs pipeline as points accumulate
- Configurable analysis interval
- Mimics live monitoring behavior
- Saves reports to live schema

### 9. ✅ Comprehensive Logging
- **Sleep timing**: ⏰ Minutes/seconds before next point
- **Anomaly alerts**: 🚨🚨🚨 with full details
- **Save operations**: 💾 with success/failure status
- **Progress tracking**: Point numbers and percentages
- **Geographic data**: Lat/lon/alt in logs

### 10. ✅ Database Management
- Optional cleanup (with `--use-original-id`)
- Deletes from: flight_metadata, normal_tracks, anomaly_reports, ai_classifications
- Bulk insert for performance
- Single-point insert for real-time
- Connection pooling

### 11. ✅ Error Handling
- Flight not found validation
- Point/timestamp range validation
- Database connection retries
- Pipeline error logging
- Graceful keyboard interrupt (Ctrl+C)

---

## 📋 Command-Line Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `flight_id` | Required | - | Source flight ID from feedback/research |
| `--start-point` | int | None | Point number to start real-time from (0-based) |
| `--start-timestamp` | int | None | Timestamp to start real-time from |
| `--interval` | int | 5 | Run pipeline every N points |
| `--source-schema` | string | feedback | Source schema name |
| `--dest-schema` | string | live | Destination schema name |
| `--dry-run` | flag | False | Test without inserting data |
| `--use-original-id` | flag | False | Use original ID (deletes existing) |

---

## 💡 Quick Usage Examples

### 1. Simple Replay (Full Flight)
```bash
python replay_flight_to_live.py 3cf959dd
# Generates new UUID, replays entire flight in real-time
```

### 2. Skip to 90% of Flight
```bash
# Find start points first
python find_start_point.py 3cf959dd
# Output: 90%: Point #1161

# Then replay from there
python replay_flight_to_live.py 3cf959dd --start-point 1161
```

### 3. Replay Last 100 Points
```bash
# Find last 100 points
python find_start_point.py 3cf959dd
# Output: Last 100 pts: Point #1191

# Replay
python replay_flight_to_live.py 3cf959dd --start-point 1191 --interval 1
```

### 4. Fast Analysis (Skip Most Points)
```bash
# Analyze every 20 points instead of every point
python replay_flight_to_live.py 3cf959dd --start-point 1000 --interval 20
```

### 5. Use Original ID (Overwrite Mode)
```bash
# Delete existing and use same ID
python replay_flight_to_live.py 3cf959dd --use-original-id --start-point 1000
```

### 6. Test Without Inserting
```bash
# Dry run to see what would happen
python replay_flight_to_live.py 3cf959dd --start-point 1000 --dry-run
```

---

## 🔄 Typical Workflow

### Step 1: Find Good Flight
```sql
-- Find recent anomaly flights
SELECT flight_id, callsign, total_points
FROM feedback.flight_metadata
WHERE is_anomaly = TRUE
ORDER BY last_seen_ts DESC
LIMIT 10;
```

### Step 2: Check Point Count
```bash
python find_start_point.py 3cf959dd
# Shows: Total points: 1291
# Suggested start points at 25%, 50%, 75%, 90%, 95%
```

### Step 3: Replay from Interesting Point
```bash
python replay_flight_to_live.py 3cf959dd --start-point 1161 --interval 5
```

### Step 4: Monitor in Real-Time
Watch the logs for:
- ⏰ Sleep timing between points
- 🚨🚨🚨 Anomaly detection alerts
- 💾 Save operation confirmations
- ✓ Success indicators

### Step 5: Check Results
```sql
-- View replayed flight (with new UUID)
SELECT flight_id, callsign, is_anomaly, first_seen_ts, last_seen_ts
FROM live.flight_metadata
ORDER BY created_at DESC
LIMIT 1;

-- Check anomaly report
SELECT matched_rule_names, severity_cnn, severity_dense
FROM live.anomaly_reports
WHERE flight_id = '<new_uuid>';
```

---

## 📊 Example Log Output

### Startup
```
================================================================================
FLIGHT REPLAY TO LIVE - REAL-TIME SIMULATION
================================================================================
Source Flight ID: 3cf959dd
New Flight ID (live): 9fe172fd
Source Schema: feedback
Destination Schema: live
Start Point: Point #1161
Analysis Interval: Every 5 points
Dry Run: False
================================================================================

Loading flight 3cf959dd from feedback schema...
✓ Loaded 1291 track points from feedback.flight_tracks
✓ Loaded metadata: ISR727 | LLBG → LHBP
✓ Loaded existing anomaly report

Converted point #1161 to timestamp 1762361889
  Timestamp: 2025-11-05 17:58:09

Replay Strategy:
  Phase 1 (Bulk Insert): 1161 points (0 to 1160)
  Phase 2 (Real-time): 130 points (from point #1161 onwards)
```

### Bulk Insert
```
================================================================================
PHASE 1: BULK INSERT
================================================================================
Bulk inserting 1161 points to live.normal_tracks...
✓ Bulk insert complete
✓ 1161 points inserted instantly
  Time range: 08:35:12 to 11:25:45
```

### Real-Time Replay
```
================================================================================
PHASE 2: REAL-TIME REPLAY
================================================================================
Starting real-time replay of 130 points...
Press Ctrl+C to stop gracefully

✓ Anomaly pipeline initialized

⏰ Waiting 8 seconds before next point...

[Point 1162/1291] 11:25:53 | Lat 31.9428, Lon 35.1565, Alt 4075ft
✓ Normal at point 1162 (confidence: 42.3%)

⏰ Waiting 12 seconds before next point...

[Point 1167/1291] 11:26:15 | Lat 31.9512, Lon 35.1423, Alt 3950ft
✓ Normal at point 1167 (confidence: 43.8%)

⏰ Waiting 1.5 minutes before next point...

[Point 1172/1291] 11:27:45 | Lat 31.9623, Lon 35.1234, Alt 3825ft
################################################################################
🚨🚨🚨 ANOMALY DETECTED! 🚨🚨🚨
   Point: 1172/1291
   Time: 2026-02-10 11:27:45
   Position: Lat 31.9623, Lon 35.1234, Alt 3825ft
   Confidence: 78.5%
   Triggered by: layer_1_rules, layer_4_deep_cnn
################################################################################

💾 Saving anomaly report to live.anomaly_reports...
✓ Anomaly report saved successfully
💾 Updating metadata to mark as anomaly...
✓ Metadata updated (is_anomaly=True)

⏰ Waiting 10 seconds before next point...

[Point 1177/1291] 11:27:55 | Lat 31.9734, Lon 35.1098, Alt 3700ft
🚨 Anomaly continues at point 1177 (confidence: 82.1%)
💾 Saving anomaly report to live.anomaly_reports...
✓ Anomaly report saved successfully
💾 Updating metadata to mark as anomaly...
✓ Metadata updated (is_anomaly=True)
```

### Completion
```
💾 Saving final metadata update...
✓ Final metadata saved (is_anomaly=True)

================================================================================
REPLAY COMPLETE
================================================================================
Total Points Replayed: 1291
  Bulk Inserted: 1161
  Real-time: 130

✓ Anomaly detected at point 1172
================================================================================
```

---

## 📚 Helper Scripts

### 1. `find_start_point.py`
Find suggested start points for any flight:
```bash
python find_start_point.py 3cf959dd
python find_start_point.py <flight_id> --schema feedback
```

### 2. `replay_flight_to_live.py`
Main replay script with all features:
```bash
python replay_flight_to_live.py <flight_id> [options]
```

---

## 🎯 Use Cases

### Demo Anomaly Detection
```bash
# Show how anomalies appear in real-time
python find_start_point.py 3cf959dd  # Find good start point
python replay_flight_to_live.py 3cf959dd --start-point 1100 --interval 1
```

### Test Pipeline Quickly
```bash
# Skip to interesting part, analyze less frequently
python replay_flight_to_live.py 3cf959dd --start-point 1000 --interval 20
```

### Train Operators
```bash
# Full real-time experience
python replay_flight_to_live.py 3cf959dd --start-point 500 --interval 1
```

### Compare Multiple Runs
```bash
# Each generates new UUID - all preserved!
python replay_flight_to_live.py 3cf959dd --start-point 1000
python replay_flight_to_live.py 3cf959dd --start-point 1100
python replay_flight_to_live.py 3cf959dd --start-point 1200
```

---

## 🐛 Troubleshooting

### Invalid Point Number
```
Invalid start point 1500. Must be between 0 and 1290
```
**Fix**: Use `find_start_point.py` to see valid range

### Cannot Use Both Options
```
Cannot use both --start-timestamp and --start-point. Choose one.
```
**Fix**: Use only one: `--start-point` OR `--start-timestamp`

### Flight Not Found
```
No track points found for flight 3cf959dd in feedback schema
```
**Fix**: Check flight exists in source schema

---

## 📖 Documentation Files

1. **`REPLAY_QUICK_START.md`** - Quick reference (this file)
2. **`REPLAY_FLIGHT_GUIDE.md`** - Comprehensive guide
3. **`START_POINT_FEATURE.md`** - Point number feature docs
4. **`UUID_FEATURE_SUMMARY.md`** - UUID generation docs
5. **`LOGGING_IMPROVEMENTS.md`** - Logging enhancements
6. **`TIMESTAMP_FIX_SUMMARY.md`** - Metadata timestamp fixes
7. **`COMPLETE_FEATURE_SUMMARY.md`** - Full feature list

---

## ⚡ Quick Commands

```bash
# Most common usage
python find_start_point.py 3cf959dd
python replay_flight_to_live.py 3cf959dd --start-point 1161

# Test first
python replay_flight_to_live.py 3cf959dd --start-point 1161 --dry-run

# Then run for real
python replay_flight_to_live.py 3cf959dd --start-point 1161 --interval 5
```

---

## 🚀 Ready to Use!

All features are implemented and tested. The script is production-ready for:
- ✅ Live demos
- ✅ Pipeline testing
- ✅ Operator training
- ✅ Bug reproduction
- ✅ Multiple concurrent replays

**Happy replaying!** 🎉
