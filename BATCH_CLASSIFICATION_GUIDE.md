# Batch Flight Classification Guide

## Overview

The `batch_classify_flights.py` script allows you to classify multiple historical flights from the database in parallel. This is useful for:
- Classifying anomalies detected before AI system was deployed
- Re-classifying flights with updated AI models
- Bulk processing of research data

## Quick Start

### 1. Classify Specific Flights

```bash
python batch_classify_flights.py --flight-ids 3d7211ef 3cf959dd 3ad2166a
```

### 2. Classify from File

Create a text file with flight IDs (one per line):

```bash
# Create flight_ids.txt
cat > flight_ids.txt << EOF
3d7211ef
3cf959dd
3ad2166a
3adf2c74
3ade9062
EOF

# Run classification
python batch_classify_flights.py --file flight_ids.txt
```

### 3. Auto-Classify All Unclassified Anomalies

```bash
# Classify up to 100 unclassified anomalies
python batch_classify_flights.py --all-anomalies --limit 100

# Classify all (no limit)
python batch_classify_flights.py --all-anomalies --limit 999999
```

## Command Line Options

### Input Sources (choose one)

- `--flight-ids ID1 ID2 ID3` - List of flight IDs
- `--file path/to/file.txt` - File with flight IDs (one per line)
- `--all-anomalies` - Automatically fetch unclassified anomalies

### Options

- `--schema SCHEMA` - Database schema (default: `research`)
  - Use `research` for historical data
  - Use `live` for live monitoring data

- `--limit N` - Max flights with `--all-anomalies` (default: 100)

- `--max-workers N` - Parallel workers (default: 2)
  - More workers = faster, but higher API load
  - Recommended: 2-4 workers

- `--no-skip-existing` - Re-classify already classified flights
  - By default, already classified flights are skipped

- `--api-key KEY` - Gemini API key
  - If not provided, reads from `GEMINI_API_KEY` env var

## Examples

### Example 1: Classify Top 50 Recent Anomalies

```bash
python batch_classify_flights.py --all-anomalies --limit 50
```

**Output:**
```
2026-02-09 15:30:00 - INFO - Found 50 unclassified anomalies in research schema
2026-02-09 15:30:00 - INFO - Starting batch classification of 50 flights...
2026-02-09 15:30:05 - INFO - ✓ Flight 3d7211ef classified: 'Weather Avoidance Maneuver'
2026-02-09 15:30:08 - INFO - ✓ Flight 3cf959dd classified: 'Technical Emergency Return'
...
================================================================================
BATCH CLASSIFICATION COMPLETE
================================================================================
Total flights: 50
Successfully classified: 48
Skipped (already classified): 0
Failed: 2
Duration: 245.3 seconds
Average time per flight: 4.9 seconds
================================================================================
```

### Example 2: Classify Specific Flights from Different Schema

```bash
python batch_classify_flights.py \
    --flight-ids 3d7211ef 3cf959dd \
    --schema live \
    --max-workers 1
```

### Example 3: Re-classify with Updated Model

```bash
# Force re-classification even if already classified
python batch_classify_flights.py \
    --file high_priority_flights.txt \
    --no-skip-existing
```

### Example 4: Query and Classify in Pipeline

```bash
# Get flight IDs from database query
psql -h $PG_HOST -U $PG_USER -d $PG_DATABASE -t -c \
  "SELECT flight_id FROM research.anomaly_reports 
   WHERE is_anomaly = TRUE 
   AND matched_rule_ids LIKE '%4%' 
   LIMIT 20" > proximity_flights.txt

# Classify them
python batch_classify_flights.py --file proximity_flights.txt
```

## Performance

### Timing

- **Per flight**: 3-5 seconds (Gemini API latency)
- **100 flights with 2 workers**: ~15-20 minutes
- **Parallel speedup**: 2x with 2 workers, 3x with 3 workers

### Resource Usage

- **Memory**: ~100MB per worker
- **Network**: ~100KB per flight (with map image)
- **CPU**: Minimal (I/O bound)

### Cost

**Gemini API Pricing:**
- Free tier: 1500 requests/day
- Paid tier: ~$0.001 per classification
- 100 flights = ~$0.10 (or free)

## Database Queries

### Find Unclassified Anomalies

```sql
-- Count unclassified anomalies
SELECT COUNT(*)
FROM research.anomaly_reports ar
LEFT JOIN research.ai_classifications ac ON ar.flight_id = ac.flight_id
WHERE ar.is_anomaly = TRUE
AND ac.flight_id IS NULL;

-- Get flight IDs
SELECT ar.flight_id
FROM research.anomaly_reports ar
LEFT JOIN research.ai_classifications ac ON ar.flight_id = ac.flight_id
WHERE ar.is_anomaly = TRUE
AND ac.flight_id IS NULL
ORDER BY ar.timestamp DESC
LIMIT 100;
```

### Export to File

```bash
# Export unclassified flight IDs
psql -h $PG_HOST -U $PG_USER -d $PG_DATABASE -t -c \
  "SELECT ar.flight_id 
   FROM research.anomaly_reports ar
   LEFT JOIN research.ai_classifications ac ON ar.flight_id = ac.flight_id
   WHERE ar.is_anomaly = TRUE AND ac.flight_id IS NULL
   LIMIT 100" > unclassified.txt

# Clean up whitespace
sed 's/^ *//g' unclassified.txt > flight_ids.txt

# Classify
python batch_classify_flights.py --file flight_ids.txt
```

### View Results

```sql
-- Latest classifications
SELECT 
    c.flight_id,
    c.classification_text,
    m.callsign,
    m.origin_airport,
    m.destination_airport,
    c.processing_time_sec,
    c.created_at
FROM research.ai_classifications c
JOIN research.flight_metadata m ON c.flight_id = m.flight_id
ORDER BY c.created_at DESC
LIMIT 20;

-- Failed classifications
SELECT 
    flight_id,
    error_message,
    processing_time_sec,
    created_at
FROM research.ai_classifications
WHERE error_message IS NOT NULL
ORDER BY created_at DESC;
```

## Troubleshooting

### API Key Not Set

**Error:**
```
ValueError: GEMINI_API_KEY not set
```

**Solution:**
```bash
export GEMINI_API_KEY="your_api_key_here"
# Or pass directly
python batch_classify_flights.py --api-key "your_key" --flight-ids ...
```

### Rate Limit Exceeded

**Error:**
```
Gemini API call failed: 429 Too Many Requests
```

**Solution:**
```bash
# Reduce workers to slow down requests
python batch_classify_flights.py --all-anomalies --max-workers 1 --limit 50

# Or wait and retry
sleep 60
python batch_classify_flights.py --all-anomalies --limit 100
```

### Flight Not Found

**Warning:**
```
Flight 3d7211ef not found in research.flight_metadata
```

**Reasons:**
- Flight ID doesn't exist
- Wrong schema specified
- Database connection issues

**Solution:**
```bash
# Check if flight exists
psql -h $PG_HOST -U $PG_USER -d $PG_DATABASE -c \
  "SELECT flight_id, callsign FROM research.flight_metadata WHERE flight_id = '3d7211ef'"

# Try different schema
python batch_classify_flights.py --flight-ids 3d7211ef --schema live
```

### Map Generation Fails

**Warning:**
```
Failed to generate flight map
```

**Impact:** Classification continues without map image

**Solution:**
```bash
# Check staticmap installation
pip show staticmap

# Reinstall if needed
pip install --force-reinstall staticmap Pillow
```

## Advanced Usage

### Filter by Rule ID

Classify only flights matching specific rules:

```sql
-- Export proximity alert flights (rule_id = 4)
psql -t -c \
  "SELECT ar.flight_id 
   FROM research.anomaly_reports ar
   LEFT JOIN research.ai_classifications ac ON ar.flight_id = ac.flight_id
   WHERE ar.is_anomaly = TRUE 
   AND ar.matched_rule_ids LIKE '%4%'
   AND ac.flight_id IS NULL
   LIMIT 50" > proximity_flights.txt

python batch_classify_flights.py --file proximity_flights.txt
```

### Filter by Date Range

```sql
-- Export flights from specific date range
psql -t -c \
  "SELECT ar.flight_id 
   FROM research.anomaly_reports ar
   LEFT JOIN research.ai_classifications ac ON ar.flight_id = ac.flight_id
   WHERE ar.is_anomaly = TRUE 
   AND ar.timestamp BETWEEN 1704067200 AND 1706745600
   AND ac.flight_id IS NULL" > date_range_flights.txt

python batch_classify_flights.py --file date_range_flights.txt
```

### Parallel Processing with Multiple Scripts

For very large batches, split into multiple files and run in parallel:

```bash
# Split into 4 files
split -n 4 all_flights.txt batch_

# Run 4 instances in parallel (different terminals)
python batch_classify_flights.py --file batch_aa --max-workers 1 &
python batch_classify_flights.py --file batch_ab --max-workers 1 &
python batch_classify_flights.py --file batch_ac --max-workers 1 &
python batch_classify_flights.py --file batch_ad --max-workers 1 &

# Wait for all to complete
wait
```

## Monitoring Progress

### Watch Logs

```bash
# Follow batch classification log
tail -f batch_classify.log

# Filter for successes
tail -f batch_classify.log | grep "✓ Flight"

# Filter for errors
tail -f batch_classify.log | grep "✗"
```

### Check Database Progress

```sql
-- Count classified flights in real-time
SELECT COUNT(*) 
FROM research.ai_classifications
WHERE created_at > NOW() - INTERVAL '1 hour';

-- Watch progress (refresh every 5 seconds)
WATCH "psql -c 'SELECT COUNT(*) FROM research.ai_classifications WHERE created_at > NOW() - INTERVAL \"1 hour\"'"
```

### Calculate ETA

```bash
# After first few flights complete
# Check average time per flight from logs
# Calculate: remaining_flights * avg_time_per_flight
```

## Best Practices

### 1. Start Small
```bash
# Test with 5-10 flights first
python batch_classify_flights.py --all-anomalies --limit 10
```

### 2. Use Appropriate Workers
```bash
# For free tier API: 1-2 workers
python batch_classify_flights.py --all-anomalies --max-workers 2 --limit 100

# For paid tier: 3-4 workers
python batch_classify_flights.py --all-anomalies --max-workers 4 --limit 500
```

### 3. Monitor Costs
```bash
# Check Google Cloud Console for API usage
# Set budget alerts at Google Cloud Console
```

### 4. Handle Interruptions
```bash
# Script saves results as it goes
# If interrupted, re-run with --all-anomalies
# It will skip already classified flights automatically
```

### 5. Review Results
```sql
-- Check classification quality
SELECT 
    classification_text,
    COUNT(*) as count
FROM research.ai_classifications
GROUP BY classification_text
ORDER BY count DESC
LIMIT 20;

-- Review specific classifications
SELECT 
    c.flight_id,
    c.classification_text,
    m.callsign,
    ar.matched_rule_names
FROM research.ai_classifications c
JOIN research.flight_metadata m ON c.flight_id = m.flight_id
JOIN research.anomaly_reports ar ON c.flight_id = ar.flight_id
ORDER BY c.created_at DESC
LIMIT 50;
```

## Automation

### Cron Job for Daily Classification

```bash
# Add to crontab (run daily at 2 AM)
0 2 * * * cd /path/to/monitor && /usr/bin/python batch_classify_flights.py --all-anomalies --limit 100 >> /var/log/batch_classify.log 2>&1
```

### Systemd Service

Create `/etc/systemd/system/batch-classify.service`:

```ini
[Unit]
Description=Batch Flight Classification
After=network.target postgresql.service

[Service]
Type=oneshot
User=monitor
WorkingDirectory=/path/to/monitor
Environment="GEMINI_API_KEY=your_key_here"
ExecStart=/usr/bin/python batch_classify_flights.py --all-anomalies --limit 100

[Install]
WantedBy=multi-user.target
```

Run manually:
```bash
sudo systemctl start batch-classify
```

## Summary

The batch classification script provides a robust way to classify historical flights:

✅ **Parallel Processing** - Multiple workers for speed  
✅ **Resume Support** - Skips already classified flights  
✅ **Error Handling** - Continues despite individual failures  
✅ **Progress Logging** - Real-time status updates  
✅ **Flexible Input** - Command line, file, or auto-fetch  
✅ **Cost Effective** - Works within free tier limits  

For questions or issues, check `batch_classify.log` or review the main documentation.
