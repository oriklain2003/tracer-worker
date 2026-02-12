-- Marine Schema Creation Script
-- Creates schema and tables for storing real-time vessel tracking data from AISstream.io

-- Create marine schema
CREATE SCHEMA IF NOT EXISTS marine;

-- ============================================================================
-- Table: marine.vessel_positions
-- Stores real-time vessel position reports (AIS message types 1,2,3,18)
-- Partitioned by timestamp for efficient querying and data management
-- ============================================================================

CREATE TABLE IF NOT EXISTS marine.vessel_positions (
    id BIGSERIAL,
    mmsi VARCHAR(9) NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    latitude DECIMAL(9,6) NOT NULL,
    longitude DECIMAL(9,6) NOT NULL,
    speed_over_ground DECIMAL(5,2),  -- knots
    course_over_ground DECIMAL(5,2),  -- degrees
    heading INTEGER,  -- degrees (0-359)
    navigation_status VARCHAR(50),
    rate_of_turn DECIMAL(5,2),  -- degrees per minute
    position_accuracy BOOLEAN,  -- true = high accuracy (<10m), false = low accuracy (>10m)
    message_type INTEGER,  -- AIS message type (1,2,3,18, etc.)
    received_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (id, timestamp)
) PARTITION BY RANGE (timestamp);

-- Create partitions for vessel_positions (monthly partitions for better performance)
-- Create partitions for the current year
CREATE TABLE IF NOT EXISTS marine.vessel_positions_2026_02 PARTITION OF marine.vessel_positions
    FOR VALUES FROM ('2026-02-01') TO ('2026-03-01');

CREATE TABLE IF NOT EXISTS marine.vessel_positions_2026_03 PARTITION OF marine.vessel_positions
    FOR VALUES FROM ('2026-03-01') TO ('2026-04-01');

CREATE TABLE IF NOT EXISTS marine.vessel_positions_2026_04 PARTITION OF marine.vessel_positions
    FOR VALUES FROM ('2026-04-01') TO ('2026-05-01');

CREATE TABLE IF NOT EXISTS marine.vessel_positions_2026_05 PARTITION OF marine.vessel_positions
    FOR VALUES FROM ('2026-05-01') TO ('2026-06-01');

CREATE TABLE IF NOT EXISTS marine.vessel_positions_2026_06 PARTITION OF marine.vessel_positions
    FOR VALUES FROM ('2026-06-01') TO ('2026-07-01');

CREATE TABLE IF NOT EXISTS marine.vessel_positions_2026_07 PARTITION OF marine.vessel_positions
    FOR VALUES FROM ('2026-07-01') TO ('2026-08-01');

CREATE TABLE IF NOT EXISTS marine.vessel_positions_2026_08 PARTITION OF marine.vessel_positions
    FOR VALUES FROM ('2026-08-01') TO ('2026-09-01');

CREATE TABLE IF NOT EXISTS marine.vessel_positions_2026_09 PARTITION OF marine.vessel_positions
    FOR VALUES FROM ('2026-09-01') TO ('2026-10-01');

CREATE TABLE IF NOT EXISTS marine.vessel_positions_2026_10 PARTITION OF marine.vessel_positions
    FOR VALUES FROM ('2026-10-01') TO ('2026-11-01');

CREATE TABLE IF NOT EXISTS marine.vessel_positions_2026_11 PARTITION OF marine.vessel_positions
    FOR VALUES FROM ('2026-11-01') TO ('2026-12-01');

CREATE TABLE IF NOT EXISTS marine.vessel_positions_2026_12 PARTITION OF marine.vessel_positions
    FOR VALUES FROM ('2026-12-01') TO ('2027-01-01');

-- Indexes for vessel_positions
CREATE INDEX IF NOT EXISTS idx_vessel_positions_mmsi_timestamp 
    ON marine.vessel_positions(mmsi, timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_vessel_positions_received_at 
    ON marine.vessel_positions(received_at DESC);

CREATE INDEX IF NOT EXISTS idx_vessel_positions_location 
    ON marine.vessel_positions(latitude, longitude);

-- ============================================================================
-- Table: marine.vessel_metadata
-- Stores vessel static data and voyage information (AIS message type 5, 24)
-- This is updated less frequently (every 6 minutes typically)
-- ============================================================================

CREATE TABLE IF NOT EXISTS marine.vessel_metadata (
    mmsi VARCHAR(9) PRIMARY KEY,
    vessel_name VARCHAR(120),
    callsign VARCHAR(20),
    imo_number VARCHAR(10),  -- International Maritime Organization number
    vessel_type INTEGER,  -- AIS ship type code (0-99)
    vessel_type_description VARCHAR(100),  -- Human-readable ship type
    length INTEGER,  -- meters
    width INTEGER,  -- meters (beam)
    draught DECIMAL(4,2),  -- meters (draft)
    destination VARCHAR(120),  -- Reported destination
    eta TIMESTAMP,  -- Estimated time of arrival
    cargo_type INTEGER,  -- Cargo type code
    dimension_to_bow INTEGER,  -- meters
    dimension_to_stern INTEGER,  -- meters
    dimension_to_port INTEGER,  -- meters
    dimension_to_starboard INTEGER,  -- meters
    position_fixing_device INTEGER,  -- Type of EPFS (1=GPS, 2=GLONASS, etc.)
    first_seen TIMESTAMP DEFAULT NOW(),
    last_updated TIMESTAMP DEFAULT NOW(),
    total_position_reports INTEGER DEFAULT 0
);

-- Indexes for vessel_metadata
CREATE INDEX IF NOT EXISTS idx_vessel_metadata_vessel_name 
    ON marine.vessel_metadata(vessel_name);

CREATE INDEX IF NOT EXISTS idx_vessel_metadata_vessel_type 
    ON marine.vessel_metadata(vessel_type);

CREATE INDEX IF NOT EXISTS idx_vessel_metadata_last_updated 
    ON marine.vessel_metadata(last_updated DESC);

CREATE INDEX IF NOT EXISTS idx_vessel_metadata_destination 
    ON marine.vessel_metadata(destination);

-- ============================================================================
-- Grants (adjust user as needed)
-- ============================================================================

GRANT USAGE ON SCHEMA marine TO postgres;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA marine TO postgres;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA marine TO postgres;

-- ============================================================================
-- Helpful queries for monitoring
-- ============================================================================

-- View recent vessel positions
-- SELECT mmsi, vessel_name, latitude, longitude, speed_over_ground, timestamp
-- FROM marine.vessel_positions vp
-- LEFT JOIN marine.vessel_metadata vm USING (mmsi)
-- WHERE timestamp > NOW() - INTERVAL '1 hour'
-- ORDER BY timestamp DESC
-- LIMIT 100;

-- Count vessels tracked in last hour
-- SELECT COUNT(DISTINCT mmsi) as active_vessels
-- FROM marine.vessel_positions
-- WHERE timestamp > NOW() - INTERVAL '1 hour';

-- Top vessel types being tracked
-- SELECT vessel_type_description, COUNT(*) as count
-- FROM marine.vessel_metadata
-- GROUP BY vessel_type_description
-- ORDER BY count DESC
-- LIMIT 10;

COMMENT ON SCHEMA marine IS 'Marine vessel tracking data from AISstream.io';
COMMENT ON TABLE marine.vessel_positions IS 'Real-time vessel position reports from AIS';
COMMENT ON TABLE marine.vessel_metadata IS 'Vessel static data and voyage information';
