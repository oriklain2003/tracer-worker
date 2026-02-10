-- ============================================================================
-- AI Classifications Table (Without Foreign Key Constraint)
-- ============================================================================
-- This version creates the table WITHOUT the foreign key constraint
-- Use this if flight_metadata.flight_id doesn't have a PRIMARY KEY
-- ============================================================================

-- For LIVE schema
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
    -- No foreign key constraint
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_ai_classifications_flight_id 
    ON live.ai_classifications(flight_id);

CREATE INDEX IF NOT EXISTS idx_ai_classifications_created_at 
    ON live.ai_classifications(created_at DESC);

-- For RESEARCH schema
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
    -- No foreign key constraint
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_ai_classifications_flight_id 
    ON research.ai_classifications(flight_id);

CREATE INDEX IF NOT EXISTS idx_ai_classifications_created_at 
    ON research.ai_classifications(created_at DESC);

-- ============================================================================
-- Verification
-- ============================================================================

-- Check tables were created
SELECT table_schema, table_name 
FROM information_schema.tables 
WHERE table_name = 'ai_classifications';

-- Check indexes
SELECT schemaname, tablename, indexname
FROM pg_indexes
WHERE tablename = 'ai_classifications';
