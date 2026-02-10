# Quick SQL Setup for AI Classifications

⚠️ **IMPORTANT**: If you get error "no unique constraint matching given keys", use the version WITHOUT foreign key (see below).

## ✅ RECOMMENDED: Without Foreign Key Constraint

### Live Schema:
```sql
CREATE TABLE IF NOT EXISTS live.ai_classifications (
    id SERIAL PRIMARY KEY,
    flight_id TEXT NOT NULL,
    classification_text TEXT NOT NULL,
    confidence_score FLOAT,
    full_response TEXT,
    processing_time_sec FLOAT,
    created_at TIMESTAMP DEFAULT NOW(),
    error_message TEXT,
    gemini_model TEXT
);

CREATE INDEX idx_ai_classifications_flight_id 
    ON live.ai_classifications(flight_id);

CREATE INDEX idx_ai_classifications_created_at 
    ON live.ai_classifications(created_at DESC);
```

### Research Schema:
```sql
CREATE TABLE IF NOT EXISTS research.ai_classifications (
    id SERIAL PRIMARY KEY,
    flight_id TEXT NOT NULL,
    classification_text TEXT NOT NULL,
    confidence_score FLOAT,
    full_response TEXT,
    processing_time_sec FLOAT,
    created_at TIMESTAMP DEFAULT NOW(),
    error_message TEXT,
    gemini_model TEXT
);

CREATE INDEX idx_ai_classifications_flight_id 
    ON research.ai_classifications(flight_id);

CREATE INDEX idx_ai_classifications_created_at 
    ON research.ai_classifications(created_at DESC);
```

## Optional: With Foreign Key (if flight_metadata has PRIMARY KEY)

Only use this if your `flight_metadata` table has a PRIMARY KEY or UNIQUE constraint on `flight_id`:

```sql
-- Check if flight_metadata has a primary key first:
SELECT constraint_name, constraint_type
FROM information_schema.table_constraints
WHERE table_name = 'flight_metadata' AND constraint_type = 'PRIMARY KEY';

-- If yes, you can add the foreign key:
CREATE TABLE IF NOT EXISTS live.ai_classifications (
    id SERIAL PRIMARY KEY,
    flight_id TEXT NOT NULL,
    classification_text TEXT NOT NULL,
    confidence_score FLOAT,
    full_response TEXT,
    processing_time_sec FLOAT,
    created_at TIMESTAMP DEFAULT NOW(),
    error_message TEXT,
    gemini_model TEXT,
    CONSTRAINT fk_flight FOREIGN KEY (flight_id) 
        REFERENCES live.flight_metadata(flight_id) ON DELETE CASCADE
);
```

## Run from Command Line

```bash
# For live schema
psql -h $PG_HOST -U $PG_USER -d $PG_DATABASE -f create_ai_classifications_table.sql

# Or inline
psql -h $PG_HOST -U $PG_USER -d $PG_DATABASE << 'EOF'
CREATE TABLE IF NOT EXISTS live.ai_classifications (
    id SERIAL PRIMARY KEY,
    flight_id TEXT NOT NULL,
    classification_text TEXT NOT NULL,
    confidence_score FLOAT,
    full_response TEXT,
    processing_time_sec FLOAT,
    created_at TIMESTAMP DEFAULT NOW(),
    error_message TEXT,
    gemini_model TEXT,
    CONSTRAINT fk_flight FOREIGN KEY (flight_id) 
        REFERENCES live.flight_metadata(flight_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_ai_classifications_flight_id 
    ON live.ai_classifications(flight_id);

CREATE INDEX IF NOT EXISTS idx_ai_classifications_created_at 
    ON live.ai_classifications(created_at DESC);
EOF
```

## Verify Creation

```sql
-- Check table exists
SELECT table_name 
FROM information_schema.tables 
WHERE table_schema = 'live' 
AND table_name = 'ai_classifications';

-- Check columns
\d live.ai_classifications

-- Check indexes
\di live.idx_ai_classifications*

-- Count rows
SELECT COUNT(*) FROM live.ai_classifications;
```

## Test Insert

```sql
-- Insert test record (replace with real flight_id)
INSERT INTO live.ai_classifications (
    flight_id,
    classification_text,
    processing_time_sec,
    gemini_model
) VALUES (
    '3d7211ef',
    'Weather Avoidance Maneuver',
    4.23,
    'gemini-3-flash-preview'
);

-- Query it
SELECT * FROM live.ai_classifications WHERE flight_id = '3d7211ef';
```

## Drop Table (if needed)

```sql
-- Be careful! This deletes all data
DROP TABLE IF EXISTS live.ai_classifications CASCADE;
```

## Column Descriptions

| Column | Type | Description |
|--------|------|-------------|
| `id` | SERIAL | Auto-increment primary key |
| `flight_id` | TEXT | Links to flight_metadata table |
| `classification_text` | TEXT | The 3-6 word AI summary |
| `confidence_score` | FLOAT | Optional confidence (0-1) |
| `full_response` | TEXT | Complete AI response |
| `processing_time_sec` | FLOAT | Seconds to classify |
| `created_at` | TIMESTAMP | When classified |
| `error_message` | TEXT | NULL if success, error if failed |
| `gemini_model` | TEXT | AI model name used |

## Python Alternative

```python
# The table is automatically created when you run:
from pg_provider import create_ai_classifications_table

create_ai_classifications_table('live')    # For live schema
create_ai_classifications_table('research') # For research schema
```

## That's It!

The table is ready to store AI classifications. The monitor.py script will automatically create it on first run if you have `GEMINI_API_KEY` set.
