# UUID Feature - Generate Unique Flight IDs

## What Changed

The replay script now **generates a new UUID4-based flight ID** for each replay by default. This allows you to replay the same flight multiple times without overwriting previous replays.

## New Behavior (Default)

### Before
```bash
python replay_flight_to_live.py 3cf959dd
# Deletes existing 3cf959dd from live schema
# Replays as 3cf959dd (overwrites old data)
```

### After
```bash
python replay_flight_to_live.py 3cf959dd
# Loads 3cf959dd from feedback schema
# Generates NEW UUID: 4bf51b7b
# Saves to live schema as 4bf51b7b (keeps old data)
```

## Benefits

✅ **Multiple Replays**: Replay the same flight multiple times  
✅ **No Data Loss**: Previous replays are preserved  
✅ **Clean Separation**: Each replay has unique ID in live schema  
✅ **Easier Testing**: Compare different replay runs side-by-side  

## Usage

### Default: Generate New UUID (Recommended)
```bash
# Generates new UUID automatically
python replay_flight_to_live.py 3cf959dd

# Output shows both IDs:
# Source Flight ID: 3cf959dd
# New Flight ID (live): 4bf51b7b
```

### Use Original ID (Old Behavior)
```bash
# Use --use-original-id to keep original ID
python replay_flight_to_live.py 3cf959dd --use-original-id

# This will:
# 1. Delete existing 3cf959dd from live schema
# 2. Replay as 3cf959dd
```

## Command-Line Options

| Option | Default | Description |
|--------|---------|-------------|
| (none) | Generate UUID | Creates new UUID4-based ID |
| `--use-original-id` | - | Uses original ID, deletes existing data |

## Examples

### Replay Multiple Times for Testing
```bash
# First replay
python replay_flight_to_live.py 3cf959dd --start-timestamp 1762354204
# Saved as: a1b2c3d4

# Second replay (different parameters)
python replay_flight_to_live.py 3cf959dd --start-timestamp 1762360000 --interval 10
# Saved as: e5f6g7h8

# Both replays now exist in live schema!
```

### Compare Replay Results
```sql
-- View all replays of the same source flight
SELECT 
    flight_id,
    callsign,
    first_seen_ts,
    is_anomaly
FROM live.flight_metadata
WHERE callsign = 'ISR727'
ORDER BY created_at DESC;

-- Compare track counts
SELECT 
    flight_id,
    COUNT(*) as points,
    MIN(timestamp) as first_ts,
    MAX(timestamp) as last_ts
FROM live.normal_tracks
WHERE flight_id IN ('a1b2c3d4', 'e5f6g7h8')
GROUP BY flight_id;
```

### Cleanup Old Replays
```sql
-- Delete specific replay
DELETE FROM live.flight_metadata WHERE flight_id = 'a1b2c3d4';
DELETE FROM live.normal_tracks WHERE flight_id = 'a1b2c3d4';
DELETE FROM live.anomaly_reports WHERE flight_id = 'a1b2c3d4';

-- Or delete all old replays (keep only recent)
DELETE FROM live.flight_metadata 
WHERE created_at < NOW() - INTERVAL '1 day';
```

## Technical Details

### UUID Generation
```python
import uuid

# Generate new UUID4
new_flight_id = str(uuid.uuid4())[:8]  # First 8 chars
# Example: '4bf51b7b'
```

### Why 8 Characters?
- Original flight IDs are 8 hex chars (e.g., `3cf959dd`)
- UUID4 is 32 chars, we use first 8 for consistency
- Still astronomically unlikely to collide
- Easier to read and reference

### Data Flow
```
Source (feedback):
  flight_id: 3cf959dd
  ↓ Load data
  ↓ Generate new UUID
  ↓ Update all points
Live (after replay):
  flight_id: 4bf51b7b  ← New UUID
  (All points and metadata updated)
```

## Migration Guide

### If You Were Using Original IDs

No changes needed! The old behavior is still available:

```bash
# Add --use-original-id flag
python replay_flight_to_live.py 3cf959dd --use-original-id
```

### If You Want New Behavior

Just remove any `--use-original-id` flags. The script now generates UUIDs by default.

## Verification

### Check New Flight IDs in Live Schema
```sql
-- List recent replays with their IDs
SELECT 
    flight_id,
    callsign,
    origin_airport,
    destination_airport,
    created_at
FROM live.flight_metadata
ORDER BY created_at DESC
LIMIT 10;
```

### Track Original Source Flight
If you want to track which source flight was used, you can:

1. Add a note in the replay log
2. Use metadata fields to store original ID
3. Create a tracking table

Example tracking table:
```sql
CREATE TABLE live.replay_tracking (
    replay_id TEXT PRIMARY KEY,
    source_flight_id TEXT NOT NULL,
    source_schema TEXT NOT NULL,
    replayed_at TIMESTAMP DEFAULT NOW()
);
```

## Summary

✅ **Default**: Generate new UUID4-based ID  
✅ **Benefit**: Multiple replays without data loss  
✅ **Fallback**: Use `--use-original-id` for old behavior  
✅ **Compatible**: Works with all existing features  

**Status**: ✅ IMPLEMENTED AND TESTED
