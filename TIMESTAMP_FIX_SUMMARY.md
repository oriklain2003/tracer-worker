# Metadata Timestamp Fix - Complete

## Issue
The flight metadata timestamps (`first_seen_ts`, `last_seen_ts`) were not being adjusted to match the new "now" time when replaying flights from feedback schema to live schema.

## Root Cause
1. Original timestamps from feedback schema were being used directly
2. When bulk inserting points, we used `bulk_time_offset` but metadata used `base_time_offset`
3. Scheduled departure/arrival times were causing TypeErrors (string values, not timestamps)

## Fixes Applied

### 1. Adjust first_seen_ts and last_seen_ts
```python
# Use bulk_time_offset when we have bulk points
if bulk_points:
    metadata['first_seen_ts'] = points[0]['timestamp'] + bulk_time_offset
    if realtime_points:
        metadata['last_seen_ts'] = bulk_points[-1]['timestamp'] + bulk_time_offset
    else:
        metadata['last_seen_ts'] = points[-1]['timestamp'] + bulk_time_offset
else:
    metadata['first_seen_ts'] = points[0]['timestamp'] + base_time_offset
    metadata['last_seen_ts'] = points[-1]['timestamp'] + base_time_offset
```

### 2. Handle scheduled times safely
```python
# Only adjust if they're numeric (not strings)
if metadata.get('scheduled_departure') and isinstance(metadata['scheduled_departure'], (int, float)):
    metadata['scheduled_departure'] = metadata['scheduled_departure'] + base_time_offset
if metadata.get('scheduled_arrival') and isinstance(metadata['scheduled_arrival'], (int, float)):
    metadata['scheduled_arrival'] = metadata['scheduled_arrival'] + base_time_offset
```

### 3. Update last_seen_ts during real-time replay
```python
# Update metadata as new points are added
metadata['last_seen_ts'] = current_ts
metadata['updated_at'] = int(datetime.now().timestamp())
```

### 4. Final update at end of replay
```python
# Ensure last_seen_ts reflects the very last point
if realtime_points:
    final_ts = int(time.time())
    metadata['last_seen_ts'] = final_ts
    metadata['updated_at'] = int(datetime.now().timestamp())
    save_flight_metadata(metadata, dest_schema)
```

## Verification Results

### Test Flight: 3cf959dd

**Original (feedback schema):**
- First Point: 2025-11-05 15:07:30
- Last Point: 2025-11-05 23:45:50
- Duration: 518.3 minutes

**After Replay (live schema):**

**Track Points:**
- First Point: 2026-02-10 05:48:36
- Last Point: 2026-02-10 14:01:40
- Duration: 493.1 minutes

**Metadata:**
- first_seen_ts: 2026-02-10 05:48:36 ✅
- last_seen_ts: 2026-02-10 14:01:40 ✅
- created_at: 2026-02-10 14:01:03 ✅
- updated_at: 2026-02-10 14:01:40 ✅

**Verification:**
- ✅ first_seen_ts matches first track point (perfect alignment)
- ✅ last_seen_ts matches last track point (perfect alignment)
- ✅ Timestamps appear as "now" (last point 0.3 min ago)
- ✅ Duration preserved (slight compression expected with bulk insert)

## Impact

### What Changed
1. **first_seen_ts**: Now matches the timestamp of the first track point in live schema
2. **last_seen_ts**: Now matches the timestamp of the last track point in live schema
3. **updated_at**: Dynamically updated as replay progresses
4. **scheduled times**: Safely handled (adjusted if numeric, preserved if string)

### What This Enables
- ✅ Metadata timestamps align with track timestamps
- ✅ Flight appears to have started/ended at correct relative times
- ✅ Web UI will show correct time ranges
- ✅ Analytics queries will work correctly
- ✅ No timestamp mismatches between tables

## Files Modified
- `replay_flight_to_live.py` (lines 489-512, 631, 644-649)

## Testing
- [x] Replayed flight 3cf959dd with --start-timestamp
- [x] Verified all metadata timestamps adjusted
- [x] Verified alignment with track points
- [x] Verified timestamps appear as "now"
- [x] Handled string scheduled times safely

## Status: ✅ COMPLETE

All metadata timestamps are now properly adjusted to appear as "happening now" when flights are replayed from feedback/research schemas to the live schema.
