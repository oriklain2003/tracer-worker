# Start Point Feature - Specify by Point Number

## New Feature: `--start-point`

You can now specify where to start the real-time replay using a **point number** instead of a timestamp!

## Why This Is Better

### Before (using timestamps)
```bash
# Had to figure out the timestamp first
python replay_flight_to_live.py 3cf959dd --start-timestamp 1762357161
# What timestamp is that? No idea!
```

### After (using point numbers)
```bash
# Much more intuitive!
python replay_flight_to_live.py 3cf959dd --start-point 1000
# Start from point #1000 - easy to understand!
```

## Usage

### Basic Example
```bash
# Replay from point 1000 onwards
python replay_flight_to_live.py 3cf959dd --start-point 1000

# Output shows:
# Start Point: Point #1000
# Converted point #1000 to timestamp 1762357161
# Timestamp: 2025-11-05 17:39:21
# Phase 1: Bulk insert points 0-999
# Phase 2: Real-time replay from point 1000 onwards
```

### Find Total Points First
```sql
-- Check how many points the flight has
SELECT COUNT(*) as total_points
FROM feedback.flight_tracks
WHERE flight_id = '3cf959dd';
-- Result: 1291 points
```

### Common Scenarios

**Start from 50% of flight:**
```bash
# If flight has 1291 points, start from 645 (50%)
python replay_flight_to_live.py 3cf959dd --start-point 645
```

**Start from last 100 points:**
```bash
# Flight has 1291 points, start from 1191 (last 100)
python replay_flight_to_live.py 3cf959dd --start-point 1191
```

**Start from 90% of flight:**
```bash
# Flight has 1291 points, start from 1161 (90%)
python replay_flight_to_live.py 3cf959dd --start-point 1161
```

## How It Works

### Automatic Conversion
1. You specify `--start-point 1000`
2. Script loads all points from feedback schema
3. Finds the timestamp of point #1000
4. Uses that timestamp internally
5. Shows you the conversion in logs

### Example Log Output
```
Start Point: Point #1000
Converted point #1000 to timestamp 1762357161
  Timestamp: 2025-11-05 17:39:21

Replay Strategy:
  Phase 1 (Bulk Insert): 1000 points (0 to 999)
  Phase 2 (Real-time): 291 points (from point #1000 onwards)
```

## Command-Line Options

| Option | Type | Description | Example |
|--------|------|-------------|---------|
| `--start-point` | int | Point number to start from (0-based) | `--start-point 1000` |
| `--start-timestamp` | int | Timestamp to start from (legacy) | `--start-timestamp 1762357161` |

**Note**: You can only use ONE of these options, not both!

## Examples

### Replay Last Hour of Flight
```bash
# If flight is 8 hours (480 minutes), and points are every 10 seconds
# That's about 2880 points total
# Last hour = last 360 points
# Start from: 2880 - 360 = 2520

python replay_flight_to_live.py 3cf959dd --start-point 2520
```

### Replay Middle Section
```bash
# Replay only points 500-700
# This would require two separate replays or modifying the script
# For now, start from 500:
python replay_flight_to_live.py 3cf959dd --start-point 500 --interval 1
```

### Skip Boring Takeoff/Landing
```bash
# Skip first 100 points (takeoff)
python replay_flight_to_live.py 3cf959dd --start-point 100

# Or skip last 50 points (landing) - not directly supported
# Use --start-point 0 and stop early with Ctrl+C
```

## Point Number vs Timestamp

### Use `--start-point` when:
- ✅ You know the flight has X points
- ✅ You want to start from a percentage (50%, 90%, etc.)
- ✅ You want to replay the last N points
- ✅ You're testing and want predictable behavior
- ✅ It's more intuitive

### Use `--start-timestamp` when:
- ✅ You have a specific time in mind
- ✅ You're syncing with external events
- ✅ You know exact times from logs

## Validation

### Valid Point Numbers
```bash
# Point numbers are 0-based
# If flight has 1291 points, valid range is 0-1290

python replay_flight_to_live.py 3cf959dd --start-point 0    # OK - first point
python replay_flight_to_live.py 3cf959dd --start-point 1290 # OK - last point
python replay_flight_to_live.py 3cf959dd --start-point 1291 # ERROR - out of range
python replay_flight_to_live.py 3cf959dd --start-point -1   # ERROR - negative
```

### Error Messages
```
Invalid start point 1500. Must be between 0 and 1290
```

## Mutually Exclusive

You **cannot** use both options at the same time:

```bash
# This will fail:
python replay_flight_to_live.py 3cf959dd --start-point 1000 --start-timestamp 1762357161

# Error: Cannot use both --start-timestamp and --start-point. Choose one.
```

## Quick Reference

```bash
# Full replay from beginning
python replay_flight_to_live.py 3cf959dd

# Start from specific point
python replay_flight_to_live.py 3cf959dd --start-point 1000

# Start from specific timestamp (old way)
python replay_flight_to_live.py 3cf959dd --start-timestamp 1762357161

# With other options
python replay_flight_to_live.py 3cf959dd --start-point 1000 --interval 10

# Test without inserting
python replay_flight_to_live.py 3cf959dd --start-point 1000 --dry-run
```

## Helper Script to Find Points

Create a helper to find good start points:

```python
# find_start_point.py
import sys
from pg_provider import get_connection, init_connection_pool

init_connection_pool()
flight_id = sys.argv[1] if len(sys.argv) > 1 else '3cf959dd'

with get_connection() as conn:
    with conn.cursor() as c:
        c.execute('''
            SELECT COUNT(*) FROM feedback.flight_tracks 
            WHERE flight_id = %s
        ''', (flight_id,))
        total = c.fetchone()[0]
        
        print(f"Flight {flight_id} has {total} points")
        print(f"\nSuggested start points:")
        print(f"  25%: {int(total * 0.25)}")
        print(f"  50%: {int(total * 0.50)}")
        print(f"  75%: {int(total * 0.75)}")
        print(f"  90%: {int(total * 0.90)}")
        print(f"  Last 100 points: {total - 100}")
```

Run it:
```bash
python find_start_point.py 3cf959dd
# Output:
# Flight 3cf959dd has 1291 points
# Suggested start points:
#   25%: 322
#   50%: 645
#   75%: 968
#   90%: 1161
#   Last 100 points: 1191
```

## Benefits

✅ **More Intuitive**: Point numbers easier than timestamps  
✅ **Percentage Based**: Easy to calculate (50% = point N/2)  
✅ **Predictable**: Same point number always means same location  
✅ **Backwards Compatible**: Old `--start-timestamp` still works  
✅ **Clear Logging**: Shows conversion and ranges  

## Status

✅ **Implemented and Tested**

- [x] Added `--start-point` option
- [x] Point to timestamp conversion
- [x] Validation for range
- [x] Mutually exclusive with timestamp
- [x] Clear logging output
- [x] Documentation complete

**Date**: 2026-02-10  
**Version**: 2.2 (with start-point feature)
