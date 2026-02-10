# AI Classifications - SQL Query Cheatsheet

Quick reference for common queries on the `ai_classifications` table.

## Basic Queries

### Get classification for one flight
```sql
SELECT classification_text, created_at
FROM live.ai_classifications
WHERE flight_id = '3d7211ef';
```

### Latest 10 classifications
```sql
SELECT flight_id, classification_text, created_at
FROM live.ai_classifications
ORDER BY created_at DESC
LIMIT 10;
```

### Count total classifications
```sql
SELECT COUNT(*) FROM live.ai_classifications;
```

## Join Queries

### With flight metadata
```sql
SELECT 
    c.classification_text,
    m.callsign,
    m.origin_airport,
    m.destination_airport
FROM live.ai_classifications c
JOIN live.flight_metadata m ON c.flight_id = m.flight_id
WHERE c.flight_id = '3d7211ef';
```

### With anomaly report
```sql
SELECT 
    c.classification_text AS ai_summary,
    ar.matched_rule_names AS triggered_rules,
    ar.confidence_score AS anomaly_confidence
FROM live.ai_classifications c
JOIN live.anomaly_reports ar ON c.flight_id = ar.flight_id
WHERE c.flight_id = '3d7211ef';
```

### Complete flight details with AI
```sql
SELECT 
    m.flight_id,
    m.callsign,
    m.origin_airport,
    m.destination_airport,
    ar.matched_rule_names,
    c.classification_text AS ai_analysis,
    c.created_at AS classified_at
FROM live.flight_metadata m
JOIN live.anomaly_reports ar ON m.flight_id = ar.flight_id
LEFT JOIN live.ai_classifications c ON m.flight_id = c.flight_id
WHERE m.is_anomaly = TRUE
ORDER BY c.created_at DESC
LIMIT 20;
```

## Analysis Queries

### Count by classification type
```sql
SELECT 
    classification_text,
    COUNT(*) as count
FROM live.ai_classifications
WHERE error_message IS NULL
GROUP BY classification_text
ORDER BY count DESC;
```

### Average processing time
```sql
SELECT 
    AVG(processing_time_sec) as avg_time,
    MIN(processing_time_sec) as min_time,
    MAX(processing_time_sec) as max_time
FROM live.ai_classifications
WHERE error_message IS NULL;
```

### Success rate
```sql
SELECT 
    COUNT(*) as total,
    COUNT(*) FILTER (WHERE error_message IS NULL) as success,
    COUNT(*) FILTER (WHERE error_message IS NOT NULL) as failed,
    ROUND(100.0 * COUNT(*) FILTER (WHERE error_message IS NULL) / COUNT(*), 2) as success_rate
FROM live.ai_classifications;
```

### Recent activity (last 24 hours)
```sql
SELECT 
    COUNT(*) as classifications_today,
    AVG(processing_time_sec) as avg_time_today
FROM live.ai_classifications
WHERE created_at > NOW() - INTERVAL '24 hours'
AND error_message IS NULL;
```

## Search Queries

### Find specific keyword in classifications
```sql
SELECT flight_id, classification_text
FROM live.ai_classifications
WHERE classification_text ILIKE '%weather%'
ORDER BY created_at DESC;
```

### Find emergency-related classifications
```sql
SELECT 
    c.flight_id,
    c.classification_text,
    m.callsign
FROM live.ai_classifications c
JOIN live.flight_metadata m ON c.flight_id = m.flight_id
WHERE c.classification_text ILIKE '%emergency%'
   OR c.classification_text ILIKE '%technical%'
ORDER BY c.created_at DESC;
```

## Error Queries

### Failed classifications
```sql
SELECT 
    flight_id,
    error_message,
    processing_time_sec,
    created_at
FROM live.ai_classifications
WHERE error_message IS NOT NULL
ORDER BY created_at DESC;
```

### Count errors by type
```sql
SELECT 
    error_message,
    COUNT(*) as count
FROM live.ai_classifications
WHERE error_message IS NOT NULL
GROUP BY error_message
ORDER BY count DESC;
```

## Schema Switching

Replace `live` with `research` to query historical data:

```sql
-- Research schema
SELECT * FROM research.ai_classifications WHERE flight_id = '3d7211ef';

-- Live schema
SELECT * FROM live.ai_classifications WHERE flight_id = '3d7211ef';
```

## Useful Views

### Create a view for easy querying
```sql
CREATE VIEW live.classified_flights AS
SELECT 
    m.flight_id,
    m.callsign,
    m.origin_airport,
    m.destination_airport,
    m.aircraft_type,
    ar.is_anomaly,
    ar.matched_rule_names,
    c.classification_text as ai_analysis,
    c.processing_time_sec,
    c.created_at as classified_at
FROM live.flight_metadata m
LEFT JOIN live.anomaly_reports ar ON m.flight_id = ar.flight_id
LEFT JOIN live.ai_classifications c ON m.flight_id = c.flight_id;

-- Then query simply:
SELECT * FROM live.classified_flights WHERE ai_analysis IS NOT NULL;
```

## Export Queries

### Export to CSV
```bash
psql -h $PG_HOST -U $PG_USER -d $PG_DATABASE -c "\COPY (
    SELECT 
        c.flight_id,
        c.classification_text,
        m.callsign,
        c.created_at
    FROM live.ai_classifications c
    JOIN live.flight_metadata m ON c.flight_id = m.flight_id
    ORDER BY c.created_at DESC
) TO 'classifications.csv' WITH CSV HEADER"
```

### Export to JSON
```bash
psql -h $PG_HOST -U $PG_USER -d $PG_DATABASE -t -c "
    SELECT json_agg(row_to_json(t))
    FROM (
        SELECT 
            c.flight_id,
            c.classification_text,
            m.callsign,
            c.created_at
        FROM live.ai_classifications c
        JOIN live.flight_metadata m ON c.flight_id = m.flight_id
        ORDER BY c.created_at DESC
        LIMIT 100
    ) t
" > classifications.json
```

## Quick Commands

```bash
# Count all classifications
psql -c "SELECT COUNT(*) FROM live.ai_classifications;"

# Latest classification
psql -c "SELECT flight_id, classification_text FROM live.ai_classifications ORDER BY created_at DESC LIMIT 1;"

# Success rate today
psql -c "SELECT ROUND(100.0 * COUNT(*) FILTER (WHERE error_message IS NULL) / COUNT(*), 2) FROM live.ai_classifications WHERE created_at > CURRENT_DATE;"
```

## Tips

- Use `LIMIT` to avoid overwhelming results
- Add `WHERE error_message IS NULL` to filter out failed classifications
- Use `ILIKE` for case-insensitive search
- Join with `LEFT JOIN` to include flights without classifications
- Always specify the schema (`live.` or `research.`)
