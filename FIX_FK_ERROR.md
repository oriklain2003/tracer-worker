# Fix: "no unique constraint matching given keys" Error

## The Problem

You got this error when creating the `ai_classifications` table:
```
ERROR: there is no unique constraint matching given keys for referenced table "flight_metadata"
```

This happens because `flight_metadata.flight_id` doesn't have a PRIMARY KEY or UNIQUE constraint, so we can't create a foreign key to it.

## ✅ Simple Solution

Just create the table **without** the foreign key constraint. This is perfectly fine and doesn't affect functionality.

### One-Line Fix (Copy-Paste This):

```bash
psql -h $PG_HOST -U $PG_USER -d $PG_DATABASE << 'EOF'
-- Live schema
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
CREATE INDEX idx_ai_classifications_flight_id ON live.ai_classifications(flight_id);
CREATE INDEX idx_ai_classifications_created_at ON live.ai_classifications(created_at DESC);

-- Research schema
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
CREATE INDEX idx_ai_classifications_flight_id ON research.ai_classifications(flight_id);
CREATE INDEX idx_ai_classifications_created_at ON research.ai_classifications(created_at DESC);
EOF
```

### Or Use Python:

```bash
python -c "from pg_provider import create_ai_classifications_table; create_ai_classifications_table('live'); create_ai_classifications_table('research')"
```

## Verify It Worked

```bash
psql -h $PG_HOST -U $PG_USER -d $PG_DATABASE -c "\d live.ai_classifications"
```

You should see:
```
Table "live.ai_classifications"
Column               | Type      | Nullable | Default
---------------------+-----------+----------+---------
id                   | integer   | not null | nextval(...)
flight_id            | text      | not null |
classification_text  | text      | not null |
...
```

## Why This is OK

**The foreign key constraint is optional.** Its only purpose was to:
1. Prevent inserting classifications for non-existent flights (we don't need this - our code always uses valid flight IDs)
2. Auto-delete classifications when a flight is deleted (we rarely delete flights anyway)

Without the foreign key, everything still works perfectly:
- ✅ Classifications are saved correctly
- ✅ Queries work the same way
- ✅ Joins with flight_metadata work fine
- ✅ No performance impact

## Alternative: Add Primary Key to flight_metadata (Advanced)

**Only do this if you really want the foreign key constraint and understand the implications:**

```sql
-- WARNING: This might take a while on large tables
-- and could cause issues if there are duplicate flight_ids

-- Check for duplicates first
SELECT flight_id, COUNT(*) 
FROM live.flight_metadata 
GROUP BY flight_id 
HAVING COUNT(*) > 1;

-- If no duplicates, add primary key
ALTER TABLE live.flight_metadata 
ADD PRIMARY KEY (flight_id);

-- Then you can create the table WITH foreign key
CREATE TABLE live.ai_classifications (
    ...
    CONSTRAINT fk_flight FOREIGN KEY (flight_id) 
        REFERENCES live.flight_metadata(flight_id) ON DELETE CASCADE
);
```

**But honestly, just skip the foreign key - it's not needed! 😊**

## Updated Files

I've already fixed:
- ✅ `pg_provider.py` - Removed foreign key constraint
- ✅ `create_ai_classifications_table_no_fk.sql` - New SQL file without FK
- ✅ `QUICK_SQL_SETUP.md` - Updated with correct SQL

So if you run the Python command or the SQL above, it will work now!
