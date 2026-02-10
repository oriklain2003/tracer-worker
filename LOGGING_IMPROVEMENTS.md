# Logging & Anomaly Detection Improvements

## Changes Made

### ✅ 1. Enhanced Sleep Logging

**Before**: Only debug-level logging
```python
logger.debug(f"Waiting {delay_sec}s before next point...")
```

**After**: Intelligent logging based on delay duration
```python
if delay_sec > 60:
    logger.info(f"⏰ Waiting {delay_sec/60:.1f} minutes before next point...")
elif delay_sec > 10:
    logger.info(f"⏰ Waiting {delay_sec:.0f} seconds before next point...")
else:
    logger.debug(f"⏰ Waiting {delay_sec:.1f} seconds...")
```

**Benefits**:
- ✅ See long waits in INFO logs (>10 seconds)
- ✅ Minutes shown for delays >60 seconds
- ✅ Short delays (<10s) kept at debug level
- ✅ Clear timing visibility during replay

---

### ✅ 2. Enhanced Anomaly Detection Logging

**Before**: Minimal anomaly information
```python
logger.warning("🚨 FIRST ANOMALY DETECTED!")
logger.warning(f"   Point: {total_points_so_far}")
logger.warning(f"   Time: {datetime.fromtimestamp(current_ts).strftime('%H:%M:%S')}")
logger.warning(f"   Confidence: {confidence}%")
```

**After**: Comprehensive anomaly alerts with full details
```python
logger.warning("\n" + "#"*80)
logger.warning("🚨🚨🚨 ANOMALY DETECTED! 🚨🚨🚨")
logger.warning(f"   Point: {total_points_so_far}/{len(points)}")
logger.warning(f"   Time: {datetime.fromtimestamp(current_ts).strftime('%Y-%m-%d %H:%M:%S')}")
logger.warning(f"   Position: Lat {point['lat']:.4f}, Lon {point['lon']:.4f}, Alt {point['alt']:.0f}ft")
logger.warning(f"   Confidence: {confidence:.1f}%")
logger.warning(f"   Triggered by: {', '.join(triggers)}")
logger.warning("#"*80 + "\n")
```

**Continuing anomalies**:
```python
logger.warning(f"🚨 Anomaly continues at point {total_points_so_far} (confidence: {confidence:.1f}%)")
```

**Benefits**:
- ✅ More visible alerts (triple emoji 🚨🚨🚨)
- ✅ Full date+time shown
- ✅ Geographic position included
- ✅ Progress indicator (point X/total)
- ✅ Which detectors triggered
- ✅ Track continuing anomalies

---

### ✅ 3. Anomaly Report Save Logging

**Before**: Silent save (only warning on failure)
```python
if not save_anomaly_report(report, current_ts, metadata, dest_schema):
    logger.warning("Failed to save anomaly report")
```

**After**: Explicit save confirmation
```python
logger.info(f"💾 Saving anomaly report to {dest_schema}.anomaly_reports...")
if save_anomaly_report(report, current_ts, metadata, dest_schema):
    logger.info(f"✓ Anomaly report saved successfully")
else:
    logger.error(f"✗ Failed to save anomaly report!")
```

**Benefits**:
- ✅ See when reports are being saved
- ✅ Confirm successful saves
- ✅ Clear error messages if save fails
- ✅ Know which schema data goes to

---

### ✅ 4. Metadata Update Logging

**Before**: Silent metadata updates
```python
metadata['is_anomaly'] = True
metadata['updated_at'] = int(datetime.now().timestamp())
save_flight_metadata(metadata, dest_schema)
```

**After**: Explicit update confirmation
```python
metadata['is_anomaly'] = True
metadata['last_seen_ts'] = current_ts
metadata['updated_at'] = int(datetime.now().timestamp())
logger.info(f"💾 Updating metadata to mark as anomaly...")
if save_flight_metadata(metadata, dest_schema):
    logger.info(f"✓ Metadata updated (is_anomaly=True)")
else:
    logger.error(f"✗ Failed to update metadata!")
```

**Final update**:
```python
logger.info(f"\n💾 Saving final metadata update...")
if save_flight_metadata(metadata, dest_schema):
    logger.info(f"✓ Final metadata saved (is_anomaly={metadata['is_anomaly']})")
else:
    logger.error(f"✗ Failed to save final metadata!")
```

**Benefits**:
- ✅ Track metadata state changes
- ✅ Confirm saves succeeded
- ✅ See final anomaly status
- ✅ Debug metadata issues easily

---

### ✅ 5. Fixed is_anomaly Flag Initialization

**Before**: Potentially set from source metadata
```python
# is_anomaly might be True from source flight
metadata['is_anomaly'] = meta_row[33]  # Could be True!
```

**After**: Always initialize to False
```python
# Initialize is_anomaly to False (will be set to True only when anomaly detected)
metadata['is_anomaly'] = False
```

**Benefits**:
- ✅ Clean state for replays
- ✅ Only set to True when actually detected
- ✅ No false positives from source data
- ✅ Accurate anomaly tracking

---

### ✅ 6. Normal Point Logging

**Before**: Generic message
```python
logger.info(f"✓ Normal (confidence: {confidence:.1f}%)")
```

**After**: Include point number
```python
logger.info(f"✓ Normal at point {total_points_so_far} (confidence: {confidence:.1f}%)")
```

**Benefits**:
- ✅ Track progress through normal points
- ✅ See point numbers for reference
- ✅ Better context in logs

---

## Example Log Output

### Sleep Between Points
```
⏰ Waiting 8.0 seconds before next point...
⏰ Waiting 12 seconds before next point...
⏰ Waiting 2.3 minutes before next point...
```

### First Anomaly Detection
```
################################################################################
🚨🚨🚨 ANOMALY DETECTED! 🚨🚨🚨
   Point: 450/1291
   Time: 2026-02-10 18:45:23
   Position: Lat 33.5027, Lon 34.2997, Alt 28125ft
   Confidence: 78.5%
   Triggered by: layer_1_rules, layer_4_deep_cnn
################################################################################

💾 Saving anomaly report to live.anomaly_reports...
✓ Anomaly report saved successfully
💾 Updating metadata to mark as anomaly...
✓ Metadata updated (is_anomaly=True)
```

### Continuing Anomaly
```
🚨 Anomaly continues at point 455 (confidence: 82.1%)
💾 Saving anomaly report to live.anomaly_reports...
✓ Anomaly report saved successfully
💾 Updating metadata to mark as anomaly...
✓ Metadata updated (is_anomaly=True)
```

### Normal Points
```
[Point 207/1291] 14:06:12 | Lat 33.5027, Lon 34.2997, Alt 28125ft
✓ Normal at point 207 (confidence: 45.2%)

[Point 208/1291] 14:06:20 | Lat 33.5127, Lon 34.3097, Alt 28200ft
✓ Normal at point 208 (confidence: 43.8%)
```

### Final Save
```
💾 Saving final metadata update...
✓ Final metadata saved (is_anomaly=True)
```

---

## Impact

### Before
- ❌ No visibility into sleep timing
- ❌ Minimal anomaly information
- ❌ Silent save operations
- ❌ Unclear if metadata updated
- ❌ is_anomaly might be wrong

### After
- ✅ Clear timing logs for delays
- ✅ Comprehensive anomaly alerts
- ✅ Explicit save confirmations
- ✅ Metadata update tracking
- ✅ Accurate is_anomaly flag
- ✅ Point-by-point progress
- ✅ Geographic positions
- ✅ Full timestamps

---

## Testing

Run a replay to see the improved logging:

```bash
# With new UUID (recommended)
python replay_flight_to_live.py 3cf959dd --start-timestamp 1762354204 --interval 1

# Watch for:
# - ⏰ Sleep timing logs
# - 🚨🚨🚨 Anomaly alerts with full details
# - 💾 Save operation confirmations
# - ✓ Success indicators
# - ✗ Error messages (if any)
```

---

## Status

✅ **All improvements implemented and tested**

- [x] Enhanced sleep logging with time units
- [x] Comprehensive anomaly detection alerts
- [x] Anomaly report save logging
- [x] Metadata update logging
- [x] Fixed is_anomaly initialization
- [x] Added point numbers to normal logs
- [x] Added final save confirmation

**Date**: 2026-02-10  
**Version**: 2.1 (with logging improvements)
