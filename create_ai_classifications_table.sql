-- ============================================================================
-- AI Classifications Table
-- ============================================================================
-- Stores AI-generated 3-6 word root cause summaries for anomaly flights
-- 
-- Usage:
--   For live monitoring:    Run for 'live' schema
--   For research/historical: Run for 'research' schema
--
-- Replace {schema} with your target schema name (e.g., 'live' or 'research')
-- ============================================================================

-- Create the ai_classifications table
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
    
    -- Foreign key to flight_metadata
    CONSTRAINT fk_flight FOREIGN KEY (flight_id) 
        REFERENCES live.flight_metadata(flight_id) ON DELETE CASCADE
);

-- Create indexes for fast queries
CREATE INDEX IF NOT EXISTS idx_ai_classifications_flight_id 
    ON live.ai_classifications(flight_id);

CREATE INDEX IF NOT EXISTS idx_ai_classifications_created_at 
    ON live.ai_classifications(created_at DESC);

-- Optional: Create index on classification text for searching
CREATE INDEX IF NOT EXISTS idx_ai_classifications_text 
    ON live.ai_classifications(classification_text);

-- Add comments for documentation
COMMENT ON TABLE live.ai_classifications IS 'AI-generated root cause summaries for anomaly flights';
COMMENT ON COLUMN live.ai_classifications.flight_id IS 'Foreign key to flight_metadata';
COMMENT ON COLUMN live.ai_classifications.classification_text IS 'Concise 3-6 word root cause summary';
COMMENT ON COLUMN live.ai_classifications.confidence_score IS 'Optional confidence score from AI model';
COMMENT ON COLUMN live.ai_classifications.full_response IS 'Complete AI response text';
COMMENT ON COLUMN live.ai_classifications.processing_time_sec IS 'Time taken to generate classification';
COMMENT ON COLUMN live.ai_classifications.error_message IS 'NULL if successful, error text if failed';
COMMENT ON COLUMN live.ai_classifications.gemini_model IS 'AI model used (e.g., gemini-3-flash-preview)';

-- ============================================================================
-- For Research Schema
-- ============================================================================
-- Uncomment and run these commands to create in 'research' schema

/*
CREATE TABLE IF NOT EXISTS research.ai_classifications (
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
        REFERENCES research.flight_metadata(flight_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_ai_classifications_flight_id 
    ON research.ai_classifications(flight_id);

CREATE INDEX IF NOT EXISTS idx_ai_classifications_created_at 
    ON research.ai_classifications(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_ai_classifications_text 
    ON research.ai_classifications(classification_text);

COMMENT ON TABLE research.ai_classifications IS 'AI-generated root cause summaries for anomaly flights';
*/

-- ============================================================================
-- Verification Queries
-- ============================================================================

-- Check if table was created
SELECT table_schema, table_name 
FROM information_schema.tables 
WHERE table_name = 'ai_classifications';

-- Check indexes
SELECT 
    schemaname,
    tablename,
    indexname,
    indexdef
FROM pg_indexes
WHERE tablename = 'ai_classifications';

-- Check foreign key constraint
SELECT
    tc.table_schema,
    tc.constraint_name,
    tc.table_name,
    kcu.column_name,
    ccu.table_name AS foreign_table_name,
    ccu.column_name AS foreign_column_name
FROM information_schema.table_constraints AS tc
JOIN information_schema.key_column_usage AS kcu
    ON tc.constraint_name = kcu.constraint_name
JOIN information_schema.constraint_column_usage AS ccu
    ON ccu.constraint_name = tc.constraint_name
WHERE tc.constraint_type = 'FOREIGN KEY'
AND tc.table_name = 'ai_classifications';

-- ============================================================================
-- Test Insert (Optional)
-- ============================================================================

-- Test insert (will fail if flight_id doesn't exist in flight_metadata)
/*
INSERT INTO live.ai_classifications (
    flight_id,
    classification_text,
    processing_time_sec,
    gemini_model
) VALUES (
    'test_flight_id',
    'Weather Avoidance Maneuver',
    4.23,
    'gemini-3-flash-preview'
);

-- Query the test record
SELECT * FROM live.ai_classifications WHERE flight_id = 'test_flight_id';

-- Clean up test record
DELETE FROM live.ai_classifications WHERE flight_id = 'test_flight_id';
*/

-- ============================================================================
-- Useful Queries After Creation
-- ============================================================================

-- Count classifications
-- SELECT COUNT(*) FROM live.ai_classifications;

-- View recent classifications
-- SELECT flight_id, classification_text, created_at 
-- FROM live.ai_classifications 
-- ORDER BY created_at DESC 
-- LIMIT 10;

-- Check for errors
-- SELECT flight_id, error_message, created_at 
-- FROM live.ai_classifications 
-- WHERE error_message IS NOT NULL;
