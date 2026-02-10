# Algorithm Verification Implementation

## Context

**Date Implemented**: February 8, 2026  
**Related Spec**: [test_design.md](test_design.md)

## The Problem

The anomaly detection pipeline had been adjusted over time to reduce false alarms and improve accuracy. However, when making changes to rules, ML models, or detection thresholds, there was no systematic way to verify that:

1. Changes didn't cause **new false alarms** (normal flights becoming anomalies)
2. Changes didn't cause **missed detections** (anomalies becoming normal)
3. Rule modifications worked as intended across the entire dataset

Making pipeline adjustments was risky because you couldn't see the full impact across all historical flights.

## The Solution

Created `algorithm_verification.py` - a script that:
- Loads flights from the `research` schema (historical data)
- Re-analyzes them with the **current** pipeline code/rules
- Compares results to the **original** analysis stored in the database
- Reports exactly what changed

## Why This Approach

### Two Analysis Modes

1. **Random Mode** (fast): Analyze 100-200 random flights in ~2-5 minutes
   - Quick sanity check before committing changes
   - Good for iterative development
   
2. **Full Mode** (thorough): Analyze all flights from last N days
   - Comprehensive verification before production deployment
   - Ensures no regression across entire dataset

### Database Schema Choice

Uses **`research` schema only** (not `feedback` or `live`):
- `research.flight_metadata` - Contains all historical flights with original `is_anomaly` classification
- `research.anomaly_reports` - Contains original matched rules
- `research.anomalies_tracks` / `research.normal_tracks` - Contains track points (separated by classification)

Why not other schemas?
- `feedback`: Too small (only user-tagged flights, ~1K records)
- `live`: Only active flights, not suitable for historical verification

### What Gets Compared

**Before** (from database):
- `is_anomaly` flag
- `matched_rule_names` (which rules triggered)

**After** (from re-analysis):
- `report["summary"]["is_anomaly"]`
- `report["layer_1_rules"]["triggers"]`

**Change Detection**:
- Status flip: normal ↔ anomaly (CRITICAL)
- Rule changes: same status but different rules matched (IMPORTANT)
- No change: everything matches (GOOD)

## How It Works

### Architecture Flow

```
1. Query research.flight_metadata + research.anomaly_reports
   └─> Get flight_id, old is_anomaly, old matched_rule_names

2. For each flight:
   ├─> Load tracks from anomalies_tracks OR normal_tracks
   │   (based on old classification)
   │
   ├─> Build FlightTrack + FlightMetadata objects
   │
   ├─> Call pipeline.analyze(flight, metadata)
   │   └─> Runs all 6 detection layers with CURRENT code
   │
   ├─> Extract new is_anomaly + new matched rules
   │
   └─> Compare old vs new
       ├─> Status changed? → Flag as CRITICAL
       ├─> Rules changed? → Flag as IMPORTANT
       └─> No change? → Mark as VERIFIED

3. Generate report with statistics and changed flights
```

### Key Design Decisions

1. **Reuses Existing Pipeline**: Calls the same `AnomalyPipeline.analyze()` used by `monitor.py`
   - No code duplication
   - Tests exactly what runs in production

2. **Efficient Loading**: Queries flights in batches, knows which tracks table to use

3. **Clean Output**: Console-friendly report shows only what matters:
   ```
   Flight_ID          Old Status    New Status    Change Type
   ABC123_1234567890  NORMAL        ANOMALY       normal_to_anomaly
     Old Rules: None
     New Rules: Off Course, Low Altitude
   ```

4. **JSON Export**: Optional `--output` flag saves detailed results for further analysis

## Usage Examples

### Quick Check During Development
```bash
# Test changes on 50 random flights (fast)
python algorithm_verification.py --mode random --count 50
```

### Before Committing Changes
```bash
# Comprehensive check on 200 random flights
python algorithm_verification.py --mode random --count 200 --output before_commit.json
```

### Pre-Production Verification
```bash
# Analyze all flights from last 30 days (thorough)
python algorithm_verification.py --mode full --days 30 --output prod_verification.json
```

### After Modifying a Rule
```bash
# Quick verification that rule changes work as expected
python algorithm_verification.py --mode random --count 100
```

## When to Use This

### ✅ Use Before:
- Modifying rule logic in `rules/rule_logic.py`
- Changing rule parameters in `rules/anomaly_rule.json`
- Adjusting ML model thresholds
- Updating confidence score weights in `anomaly_pipeline.py`
- Deploying to production

### ✅ Use After:
- Training new ML models
- Updating path learning database
- Changing bounding box filters
- Modifying flight phase detection logic

### ❌ Don't Need For:
- UI changes (doesn't affect detection)
- API endpoint changes
- Database migrations
- Documentation updates

## Expected Results

### Good Signs ✓
- `No Change: 95-100%` - Algorithm is stable
- `Rules Changed Only: 0-5%` - Minor refinements
- Changes are intentional and improve accuracy

### Warning Signs ⚠️
- `Normal → Anomaly: >10%` - Too many new false alarms
- `Anomaly → Normal: >10%` - Missing real anomalies
- Random changes with no clear pattern

### Action Required 🚨
- Status changes >20% - Likely a bug or major regression
- All flights changed - Pipeline initialization error
- Script crashes - Database connection or data corruption

## Technical Notes

### Performance
- Random mode (100 flights): ~2-5 minutes
- Full mode (7 days, ~5000 flights): ~40-60 minutes
- Bottleneck: Pipeline analysis (6 ML layers per flight)

### Requirements
- PostgreSQL connection (uses `pg_provider`)
- All ML models loaded (Deep CNN, Transformer, XGBoost, etc.)
- Sufficient memory for model inference (~2GB)

### Limitations
- Only compares rule-based detection (Layer 1) in detail
- ML layer changes are visible via `is_anomaly` flip but not granular
- Requires flights to have minimum 50 points

## Future Enhancements

Potential improvements for future AI agents:

1. **Parallel Processing**: Use multiprocessing to analyze flights concurrently
2. **Layer-by-Layer Comparison**: Compare each ML layer separately (CNN, XGBoost, etc.)
3. **Confidence Score Tracking**: Report confidence score changes, not just binary anomaly flag
4. **Rule-Specific Reports**: Filter verification by specific rule IDs
5. **Performance Profiling**: Track which layers take longest
6. **Automated Thresholds**: Suggest if changes are acceptable based on historical patterns

## Related Files

- **Implementation**: `algorithm_verification.py`
- **Original Spec**: `.cursor/specs/test_design.md`
- **Pipeline**: `anomaly_pipeline.py`
- **Rules**: `rules/rule_logic.py`, `rules/anomaly_rule.json`
- **Monitor**: `monitor.py` (uses same pipeline)
- **Database Docs**: `docs/db.md`

## Summary

This tool enables **safe, data-driven development** of the anomaly detection pipeline. Before this existed, rule changes were risky guesses. Now you can:

1. Make a change
2. Run verification
3. See exactly what impact it has
4. Iterate with confidence

The script is the **safety net** that allows aggressive tuning without fear of breaking production.
