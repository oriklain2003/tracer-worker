# PostgreSQL Schema Documentation - Feedback & Research

**Database**: tracer (PostgreSQL on AWS RDS)  
**Host**: tracer-db.cb80eku2emy0.eu-north-1.rds.amazonaws.com  
**Last Updated**: February 2026

---

## Table of Contents

1. [Overview](#overview)
2. [Feedback Schema](#1-feedback-schema)
   - [feedback.flight_metadata](#11-feedbackflight_metadata)
   - [feedback.flight_tracks](#12-feedbackflight_tracks)
   - [feedback.anomaly_reports](#13-feedbackanomaly_reports)
   - [feedback.user_feedback](#14-feedbackuser_feedback)
3. [Research Schema](#2-research-schema)
   - [research.flight_metadata](#21-researchflight_metadata)
   - [research.anomalies_tracks](#22-researchanomalies_tracks)
   - [research.normal_tracks](#23-researchnormal_tracks)
   - [research.anomaly_reports](#24-researchanomaly_reports)
4. [Schema Comparison](#schema-comparison)
5. [Partition Management](#partition-management)
6. [Data Flow Architecture](#data-flow-architecture)
7. [Connection Management](#connection-management)
8. [Query Examples](#query-examples)
9. [Performance Considerations](#performance-considerations)
10. [Related Files](#related-files)

---

## Overview

This document provides comprehensive documentation for the **feedback** and **research** PostgreSQL schemas used in the FiveAir anomaly detection system. Both schemas store flight tracking data but serve different purposes:

- **Research Schema**: Historical flight data collected for analysis and ML training. Contains all flights detected by the monitoring system.
- **Feedback Schema**: User-tagged and reviewed flights for quality control and training validation. Contains only flights that have been manually reviewed.

### Database Connection

Connection management is handled through a singleton connection pool pattern:
- **Module**: [`service/pg_provider.py`](pg_provider.py)
- **Pool Size**: 2-10 connections (configurable)
- **Connection Timeout**: 10 seconds
- **Query Timeout**: 30 seconds
- **Thread-safe**: Yes
- **Auto-cleanup**: Yes (on application exit)

---

## 1. FEEDBACK SCHEMA

The feedback schema stores user-tagged flights with complete metadata, tracks, and analysis results. This data is used for model training validation and quality assurance.

### 1.1 feedback.flight_metadata

**Purpose**: Complete flight information for user-tagged flights

**Storage Type**: Partitioned table (monthly partitions by `first_seen_ts`)

**Row Count**: ~1,000-5,000 (subset of research data)

#### Columns

| Column Name | Data Type | Nullable | Description |
|------------|-----------|----------|-------------|
| `flight_id` | text | NOT NULL | Unique flight identifier (format: CALLSIGN_TIMESTAMP) |
| `callsign` | text | NULL | Aircraft callsign |
| `flight_number` | text | NULL | Commercial flight number |
| `airline` | text | NULL | Airline name |
| `airline_code` | text | NULL | IATA/ICAO airline code |
| `aircraft_type` | text | NULL | Aircraft type code (e.g., B738, A320) |
| `aircraft_model` | text | NULL | Full aircraft model name |
| `aircraft_registration` | text | NULL | Aircraft registration number (tail number) |
| `origin_airport` | text | NULL | Departure airport ICAO code |
| `origin_lat` | double precision | NULL | Origin airport latitude |
| `origin_lon` | double precision | NULL | Origin airport longitude |
| `destination_airport` | text | NULL | Arrival airport ICAO code |
| `dest_lat` | double precision | NULL | Destination airport latitude |
| `dest_lon` | double precision | NULL | Destination airport longitude |
| `first_seen_ts` | bigint | NOT NULL | First detection timestamp (Unix epoch) **PARTITION KEY** |
| `last_seen_ts` | bigint | NULL | Last detection timestamp |
| `scheduled_departure` | text | NULL | Scheduled departure time (ISO 8601) |
| `scheduled_arrival` | text | NULL | Scheduled arrival time (ISO 8601) |
| `flight_duration_sec` | bigint | NULL | Total flight duration in seconds |
| `total_distance_nm` | double precision | NULL | Total distance traveled in nautical miles |
| `total_points` | bigint | NULL | Number of track points collected |
| `min_altitude_ft` | double precision | NULL | Minimum altitude in feet |
| `max_altitude_ft` | double precision | NULL | Maximum altitude in feet |
| `avg_altitude_ft` | double precision | NULL | Average altitude in feet |
| `cruise_altitude_ft` | double precision | NULL | Cruise altitude in feet |
| `min_speed_kts` | double precision | NULL | Minimum ground speed in knots |
| `max_speed_kts` | double precision | NULL | Maximum ground speed in knots |
| `avg_speed_kts` | double precision | NULL | Average ground speed in knots |
| `start_lat` | double precision | NULL | Starting position latitude |
| `start_lon` | double precision | NULL | Starting position longitude |
| `end_lat` | double precision | NULL | Ending position latitude |
| `end_lon` | double precision | NULL | Ending position longitude |
| `squawk_codes` | text | NULL | JSON array of squawk codes used during flight |
| `emergency_squawk_detected` | boolean | NULL | True if 7500/7600/7700 detected |
| `is_anomaly` | boolean | NULL | User-labeled anomaly flag |
| `is_military` | boolean | NULL | True if identified as military aircraft |
| `military_type` | text | NULL | Type: tanker, ISR, fighter, transport, etc. |
| `flight_phase_summary` | text | NULL | JSON object with phase durations (taxi, climb, cruise, descent, holding) |
| `nearest_airport_start` | text | NULL | Closest airport at flight start |
| `nearest_airport_end` | text | NULL | Closest airport at flight end |
| `crossed_borders` | text | NULL | Comma-separated list of countries crossed |
| `signal_loss_events` | bigint | NULL | Count of signal loss occurrences |
| `data_quality_score` | double precision | NULL | Overall data quality metric (0-1 scale) |
| `created_at` | bigint | NULL | Record creation timestamp |
| `updated_at` | bigint | NULL | Last update timestamp |
| `category` | text | NULL | Flight category classification |

#### Primary Key

```sql
PRIMARY KEY (flight_id, first_seen_ts)
```

**Note**: Composite key required for partitioning. The partition key (`first_seen_ts`) must be included in the primary key.

#### Indexes

| Index Name | Columns | Type | Purpose |
|-----------|---------|------|---------|
| `feedback_flight_metadata_pkey` | `(flight_id, first_seen_ts)` | PRIMARY KEY | Unique constraint and fast lookups |
| `idx_flight_metadata_timestamps` | `(first_seen_ts, last_seen_ts)` | B-tree | Time range queries |
| `idx_flight_metadata_is_anomaly` | `is_anomaly` | B-tree | Filter anomalous flights |
| `idx_metadata_airline` | `airline` | B-tree | Airline-specific queries |
| `idx_metadata_callsign` | `callsign` | B-tree | Callsign lookups |
| `idx_metadata_military` | `is_military` | B-tree | Military flight queries |
| `idx_metadata_airports` | `(origin_airport, destination_airport)` | B-tree | Route-based queries |
| `idx_metadata_emergency` | `emergency_squawk_detected` | B-tree | Emergency event queries |

#### Foreign Key Relationships

**Referenced By**:
- `feedback.flight_tracks(flight_id)` - Track points for this flight
- `feedback.anomaly_reports(flight_id)` - Analysis results for this flight
- `feedback.user_feedback(flight_id)` - User tagging information

#### Partitions

Partitions are created monthly. Example structure:
- `feedback.flight_metadata_2025_01` - January 2025
- `feedback.flight_metadata_2025_02` - February 2025
- `feedback.flight_metadata_2026_01` - January 2026
- etc.

#### Usage Notes

- Use time-based queries with `first_seen_ts` to leverage partition pruning
- The `flight_id` format is typically `{CALLSIGN}_{TIMESTAMP}`
- JSON fields (`squawk_codes`, `flight_phase_summary`) can be queried with PostgreSQL JSONB operators
- Emergency squawk codes: 7500 (hijack), 7600 (radio failure), 7700 (general emergency)

---

### 1.2 feedback.flight_tracks

**Purpose**: Unified track point storage for all tagged flights (both anomalous and normal)

**Storage Type**: Regular table (not partitioned)

**Row Count**: ~100,000-500,000 points

#### Columns

| Column Name | Data Type | Nullable | Description |
|------------|-----------|----------|-------------|
| `flight_id` | text | NOT NULL | Flight identifier (references flight_metadata) |
| `timestamp` | bigint | NOT NULL | Unix epoch timestamp of this position |
| `lat` | double precision | NULL | Latitude in decimal degrees (-90 to 90) |
| `lon` | double precision | NULL | Longitude in decimal degrees (-180 to 180) |
| `alt` | double precision | NULL | Altitude in feet (MSL - Mean Sea Level) |
| `gspeed` | double precision | NULL | Ground speed in knots |
| `vspeed` | double precision | NULL | Vertical speed in feet/minute (positive = climb) |
| `track` | double precision | NULL | Track angle in degrees (0-360, 0=North) |
| `squawk` | text | NULL | Transponder squawk code at this point |
| `callsign` | text | NULL | Aircraft callsign at this point |
| `source` | text | NULL | Data source identifier (e.g., "fr24", "adsb") |

#### Primary Key

```sql
PRIMARY KEY (flight_id, timestamp)
```

#### Indexes

| Index Name | Columns | Type | Purpose |
|-----------|---------|------|---------|
| `feedback_flight_tracks_pkey` | `(flight_id, timestamp)` | PRIMARY KEY | Unique constraint |
| `idx_tracks_ts` | `timestamp` | B-tree | Time-based queries |
| `idx_tracks_fid_ts` | `(flight_id, timestamp)` | B-tree | Flight-specific queries |
| `idx_tracks_callsign` | `callsign` | B-tree | Callsign-based searches |

#### Foreign Key Relationships

**References**:
- `feedback.flight_metadata(flight_id)` - Parent flight record

#### Query Examples

```sql
-- Get all track points for a specific flight
SELECT timestamp, lat, lon, alt, gspeed, vspeed, track
FROM feedback.flight_tracks
WHERE flight_id = 'ABC123_1234567890'
ORDER BY timestamp;

-- Get recent positions for all flights
SELECT DISTINCT ON (flight_id) 
    flight_id, timestamp, lat, lon, alt, callsign
FROM feedback.flight_tracks
WHERE timestamp > extract(epoch from NOW() - INTERVAL '1 hour')
ORDER BY flight_id, timestamp DESC;
```

---

### 1.3 feedback.anomaly_reports

**Purpose**: Stores ML model and rule engine analysis results for tagged flights

**Storage Type**: Partitioned table (monthly partitions by `timestamp`)

**Row Count**: ~1,000-5,000 (one per tagged flight)

#### Columns

| Column Name | Data Type | Nullable | Description |
|------------|-----------|----------|-------------|
| `id` | bigint | NOT NULL | Unique report ID (auto-increment) |
| `flight_id` | text | NOT NULL | Flight identifier |
| `timestamp` | bigint | NOT NULL | Report generation timestamp **PARTITION KEY** |
| `is_anomaly` | boolean | NULL | Overall anomaly classification (true/false) |
| `severity_cnn` | double precision | NULL | CNN model severity score (0.0-1.0) |
| `severity_dense` | double precision | NULL | Dense network severity score (0.0-1.0) |
| `full_report` | jsonb | NULL | Complete analysis report with all layers |
| `callsign` | text | NULL | Flight callsign (denormalized) |
| `airline` | text | NULL | Airline name (denormalized) |
| `origin_airport` | text | NULL | Origin airport (denormalized) |
| `destination_airport` | text | NULL | Destination airport (denormalized) |
| `aircraft_type` | text | NULL | Aircraft type (denormalized) |
| `flight_duration_sec` | bigint | NULL | Flight duration (denormalized) |
| `max_altitude_ft` | double precision | NULL | Maximum altitude (denormalized) |
| `avg_speed_kts` | double precision | NULL | Average speed (denormalized) |
| `nearest_airport` | text | NULL | Nearest airport during anomaly |
| `geographic_region` | text | NULL | Geographic region of flight |
| `is_military` | boolean | NULL | Military flag (denormalized) |
| `matched_rule_ids` | text | NULL | Comma-separated rule IDs triggered |
| `matched_rule_names` | text | NULL | Comma-separated rule names |
| `matched_rule_categories` | text | NULL | Comma-separated rule categories |

#### Primary Key

```sql
PRIMARY KEY (flight_id, timestamp)
```

#### Indexes

| Index Name | Columns | Type | Purpose |
|-----------|---------|------|---------|
| `feedback_anomaly_reports_pkey` | `(flight_id, timestamp)` | PRIMARY KEY | Unique constraint |
| `idx_anomaly_reports_timestamp` | `timestamp` | B-tree | Time-based queries |
| `idx_anomaly_reports_fid` | `flight_id` | B-tree | Flight lookups |
| `idx_anomaly_reports_callsign` | `callsign` | B-tree | Callsign searches |
| `idx_anomaly_reports_airline` | `airline` | B-tree | Airline-specific queries |
| `idx_anomaly_reports_military` | `is_military` | B-tree | Military flight queries |
| `idx_anomaly_reports_airport` | `nearest_airport` | B-tree | Airport-based queries |
| `idx_anomaly_reports_region` | `geographic_region` | B-tree | Regional analysis |
| `idx_anomaly_reports_severity` | `(severity_cnn, severity_dense)` | B-tree | Severity-based queries |
| `idx_anomaly_reports_rules` | `matched_rule_ids` | B-tree | Rule-based searches |

#### Foreign Key Relationships

**References**:
- `feedback.flight_metadata(flight_id)` - Parent flight record

#### Full Report Structure (JSONB)

The `full_report` column contains a comprehensive JSON structure:

```json
{
  "summary": {
    "is_anomaly": true,
    "severity_cnn": 0.85,
    "severity_dense": 0.72,
    "confidence_score": 0.88
  },
  "layer_1_rules": {
    "is_anomaly": true,
    "report": {
      "matched_rules": [
        {
          "id": 8,
          "name": "Off Course",
          "category": "Navigation",
          "severity": 0.9,
          "details": "..."
        }
      ],
      "evaluations": [...]
    }
  },
  "layer_2_xgboost": {
    "is_anomaly": false,
    "score": 0.23,
    "features": {...}
  },
  "layer_3_deep_dense": {
    "is_anomaly": true,
    "severity": 0.72,
    "reconstruction_error": 0.15
  },
  "layer_4_deep_cnn": {
    "is_anomaly": true,
    "severity": 0.85,
    "pattern_deviations": [...]
  },
  "layer_5_transformer": {
    "is_anomaly": true,
    "attention_weights": [...]
  },
  "layer_6_hybrid": {
    "is_anomaly": true,
    "combined_score": 0.87
  }
}
```

#### Query Examples

```sql
-- Find high-severity anomalies
SELECT flight_id, callsign, severity_cnn, matched_rule_names
FROM feedback.anomaly_reports
WHERE is_anomaly = true 
  AND severity_cnn > 0.8
ORDER BY severity_cnn DESC;

-- Query specific rules using JSONB
SELECT flight_id, callsign,
       full_report->'layer_1_rules'->'report'->'matched_rules' as rules
FROM feedback.anomaly_reports
WHERE full_report @> '{"layer_1_rules": {"is_anomaly": true}}';
```

---

### 1.4 feedback.user_feedback

**Purpose**: Stores user tagging decisions, comments, and classifications

**Storage Type**: Regular table (not partitioned)

**Row Count**: ~1,000-5,000 (one per tagged flight)

#### Columns

| Column Name | Data Type | Nullable | Default | Description |
|------------|-----------|----------|---------|-------------|
| `id` | bigint | NOT NULL | AUTO | Unique feedback ID (auto-increment) |
| `flight_id` | text | NOT NULL | - | Flight being tagged (unique constraint) |
| `first_seen_ts` | bigint | NULL | - | Flight start time (denormalized) |
| `last_seen_ts` | bigint | NULL | - | Flight end time (denormalized) |
| `tagged_at` | bigint | NOT NULL | - | When user tagged this flight (Unix epoch) |
| `rule_id` | bigint | NULL | - | First matched rule ID (legacy, single rule) |
| `rule_name` | text | NULL | - | First matched rule name (legacy) |
| `rule_ids` | text | NULL | - | JSON array of all matched rule IDs |
| `rule_names` | text | NULL | - | JSON array of all matched rule names |
| `comments` | text | NULL | - | User comments about the flight |
| `other_details` | text | NULL | - | Additional details for "Other" classification |
| `user_label` | bigint | NULL | 1 | User's classification: 0=normal, 1=anomaly |

#### Primary Key

```sql
PRIMARY KEY (id)
```

#### Unique Constraints

```sql
UNIQUE (flight_id)
```

**Note**: Each flight can only be tagged once

#### Indexes

| Index Name | Columns | Type | Purpose |
|-----------|---------|------|---------|
| `feedback_user_feedback_pkey` | `id` | PRIMARY KEY | Unique identifier |
| `feedback_user_feedback_flight_id_key` | `flight_id` | UNIQUE | Prevent duplicate tags |
| `idx_user_feedback_flight` | `flight_id` | B-tree | Flight lookups |
| `idx_user_feedback_tagged_at` | `tagged_at` | B-tree | Time-based queries |
| `idx_user_feedback_rule` | `rule_id` | B-tree | Rule-based queries |

#### Foreign Key Relationships

**References**:
- `feedback.flight_metadata(flight_id)` - Parent flight record

#### Usage Notes

- `user_label`: 0 = user marked as normal, 1 = user marked as anomaly
- `rule_ids` and `rule_names` are JSON arrays stored as text: `["1", "8", "11"]`
- Legacy fields (`rule_id`, `rule_name`) maintained for backward compatibility
- Use for training data validation and quality assurance

#### Query Examples

```sql
-- Get all user-confirmed anomalies
SELECT uf.flight_id, uf.tagged_at, uf.comments, uf.rule_names,
       fm.callsign, fm.airline
FROM feedback.user_feedback uf
JOIN feedback.flight_metadata fm ON uf.flight_id = fm.flight_id
WHERE uf.user_label = 1
ORDER BY uf.tagged_at DESC;

-- Get tagging statistics
SELECT 
    user_label,
    COUNT(*) as count,
    COUNT(*) * 100.0 / SUM(COUNT(*)) OVER () as percentage
FROM feedback.user_feedback
GROUP BY user_label;
```

---

## 2. RESEARCH SCHEMA

The research schema stores all historical flight data collected by the monitoring system. This is the primary data source for analysis, ML training, and research purposes.

### 2.1 research.flight_metadata

**Purpose**: Complete flight information for all detected flights (research/historical data)

**Storage Type**: Partitioned table (monthly partitions by `first_seen_ts`)

**Row Count**: ~50,000-500,000+ (all flights, not just tagged)

#### Structure

**Identical to `feedback.flight_metadata`** - See [section 1.1](#11-feedbackflight_metadata) for complete column definitions.

#### Key Differences from Feedback Schema

- **Data Volume**: Contains ALL flights detected, not just user-tagged flights
- **Purpose**: Research, analysis, and ML training data source
- **Write Pattern**: Continuous streaming writes from monitor.py
- **User Labels**: `is_anomaly` reflects ML/rule engine classification, not user labels

#### Partitions

Monthly partitions created automatically or via SQL scripts:
- `research.flight_metadata_2025` - All of 2025
- `research.flight_metadata_2026` - All of 2026
- `research.flight_metadata_YYYY_MM` - Monthly partitions as needed

**Creation Scripts**:
- `service/create_2025_2026_partitions.sql`
- `service/create_all_2026_partitions.sql`

#### Query Examples

```sql
-- Get recent anomalies
SELECT flight_id, callsign, airline, origin_airport, destination_airport,
       max_altitude_ft, avg_speed_kts, is_military
FROM research.flight_metadata
WHERE is_anomaly = true
  AND first_seen_ts > extract(epoch from NOW() - INTERVAL '24 hours')
ORDER BY first_seen_ts DESC;

-- Route analysis
SELECT origin_airport, destination_airport,
       COUNT(*) as flight_count,
       AVG(flight_duration_sec/60.0) as avg_duration_min,
       AVG(avg_speed_kts) as avg_speed
FROM research.flight_metadata
WHERE origin_airport IS NOT NULL 
  AND destination_airport IS NOT NULL
  AND first_seen_ts > extract(epoch from NOW() - INTERVAL '7 days')
GROUP BY origin_airport, destination_airport
HAVING COUNT(*) >= 5
ORDER BY flight_count DESC;
```

---

### 2.2 research.anomalies_tracks

**Purpose**: Track points for flights classified as anomalies by the ML/rule engine

**Storage Type**: Partitioned table (monthly partitions by `timestamp`)

**Row Count**: ~1M-10M+ points (depends on anomaly rate)

#### Columns

Identical to `feedback.flight_tracks` - See [section 1.2](#12-feedbackflight_tracks) for column definitions.

#### Primary Key

```sql
PRIMARY KEY (flight_id, timestamp)
```

**Note**: Composite key includes partition key for efficient partitioning.

#### Indexes

| Index Name | Columns | Type | Purpose |
|-----------|---------|------|---------|
| `research_anomalies_tracks_pkey` | `(flight_id, timestamp)` | PRIMARY KEY | Unique constraint |
| `idx_anomalies_tracks_timestamp` | `timestamp` | B-tree | Time range queries |
| `idx_anomalies_tracks_timestamp_brin` | `timestamp` | BRIN | Partition pruning |
| `idx_anomalies_tracks_flight_id` | `flight_id` | B-tree | Flight-specific queries |

**BRIN Index**: Block Range INdex - very efficient for partitioned time-series data. Uses minimal storage and provides fast partition pruning.

#### Partitions

Monthly partitions:
- `research.anomalies_tracks_2025`
- `research.anomalies_tracks_2026`
- `research.anomalies_tracks_YYYY_MM` - Created as needed

#### Performance Notes

- Use time-based `WHERE` clauses to leverage partition pruning
- BRIN indexes are automatically maintained on partitions
- Query specific partitions when date range is known for best performance

#### Query Examples

```sql
-- Get full track for anomalous flight
SELECT timestamp, lat, lon, alt, gspeed, vspeed, track, squawk
FROM research.anomalies_tracks
WHERE flight_id = 'ABC123_1234567890'
ORDER BY timestamp;

-- Analyze altitude patterns for anomalies
SELECT 
    FLOOR(alt/1000)*1000 as altitude_band,
    COUNT(*) as point_count,
    AVG(gspeed) as avg_speed
FROM research.anomalies_tracks
WHERE timestamp > extract(epoch from NOW() - INTERVAL '24 hours')
  AND alt > 0
GROUP BY altitude_band
ORDER BY altitude_band;
```

---

### 2.3 research.normal_tracks

**Purpose**: Track points for flights classified as normal by the ML/rule engine

**Storage Type**: Partitioned table (monthly partitions by `timestamp`)

**Row Count**: ~10M-100M+ points (majority of flights are normal)

#### Structure

**Identical to `research.anomalies_tracks`** - See [section 2.2](#22-researchanomalies_tracks) for complete details.

#### Key Differences from Anomalies Tracks

- **Data Volume**: Much larger (most flights are normal)
- **Purpose**: Baseline data for ML training and statistical analysis
- **Query Patterns**: Often aggregated for statistical analysis rather than individual flight tracking

#### Partitions

Monthly partitions:
- `research.normal_tracks_2025`
- `research.normal_tracks_2026`
- `research.normal_tracks_YYYY_MM` - Created as needed

#### Performance Considerations

Due to high data volume:
- **Always use time range filters** to leverage partition pruning
- **Avoid full table scans** - they can be extremely slow
- **Use aggregations wisely** - consider materialized views for common queries
- **BRIN indexes** provide efficient partition pruning with minimal storage overhead

#### Query Examples

```sql
-- Analyze normal flight patterns by hour
SELECT 
    date_trunc('hour', to_timestamp(timestamp)) as hour,
    COUNT(DISTINCT flight_id) as unique_flights,
    COUNT(*) as total_points,
    AVG(alt) as avg_altitude,
    AVG(gspeed) as avg_speed
FROM research.normal_tracks
WHERE timestamp > extract(epoch from NOW() - INTERVAL '24 hours')
GROUP BY hour
ORDER BY hour;

-- Sample normal tracks for ML training
SELECT flight_id, timestamp, lat, lon, alt, gspeed, vspeed, track
FROM research.normal_tracks
WHERE timestamp BETWEEN 1735689600 AND 1735776000  -- Specific day
  AND flight_id IN (
    SELECT flight_id FROM research.flight_metadata 
    WHERE is_military = false 
    LIMIT 100
  )
ORDER BY flight_id, timestamp;
```

---

### 2.4 research.anomaly_reports

**Purpose**: ML model and rule engine analysis results for all analyzed flights

**Storage Type**: Partitioned table (monthly partitions by `timestamp`)

**Row Count**: ~10,000-100,000+ (depends on analysis rate)

#### Structure

**Identical to `feedback.anomaly_reports`** - See [section 1.3](#13-feedbackanomaly_reports) for complete column and JSONB structure details.

#### Key Differences from Feedback Schema

- **Data Volume**: Contains reports for ALL analyzed flights, not just tagged flights
- **Purpose**: Primary source for anomaly analysis and ML model outputs
- **Write Pattern**: Continuous writes from analysis pipeline

#### Partitions

Monthly partitions:
- `research.anomaly_reports_2025`
- `research.anomaly_reports_2026`
- `research.anomaly_reports_YYYY_MM` - Created as needed

#### Query Examples

```sql
-- Get recent high-severity anomalies
SELECT ar.flight_id, ar.callsign, ar.airline,
       ar.origin_airport, ar.destination_airport,
       ar.severity_cnn, ar.matched_rule_names,
       fm.max_altitude_ft, fm.avg_speed_kts
FROM research.anomaly_reports ar
JOIN research.flight_metadata fm ON ar.flight_id = fm.flight_id
WHERE ar.is_anomaly = true
  AND ar.severity_cnn > 0.7
  AND ar.timestamp > extract(epoch from NOW() - INTERVAL '7 days')
ORDER BY ar.severity_cnn DESC
LIMIT 50;

-- Analyze rule match frequency
SELECT 
    UNNEST(string_to_array(matched_rule_names, ',')) as rule_name,
    COUNT(*) as match_count
FROM research.anomaly_reports
WHERE is_anomaly = true
  AND matched_rule_names IS NOT NULL
  AND timestamp > extract(epoch from NOW() - INTERVAL '30 days')
GROUP BY rule_name
ORDER BY match_count DESC;
```

---

## Schema Comparison

| Feature | Feedback Schema | Research Schema |
|---------|----------------|-----------------|
| **Primary Purpose** | User-tagged flights for validation | Historical analysis and ML training |
| **Data Source** | Manual user tagging via UI | Automated monitoring system |
| **Data Volume** | Small (~1K-5K flights) | Large (~50K-500K+ flights) |
| **Track Storage** | Unified `flight_tracks` table | Separated `anomalies_tracks` / `normal_tracks` |
| **User Tags** | Has `user_feedback` table | No user feedback table |
| **Partitioning** | flight_metadata, anomaly_reports | All large tables partitioned |
| **Write Pattern** | Batch imports after tagging | Continuous streaming writes |
| **Update Frequency** | Occasional (manual tagging) | Real-time (monitoring) |
| **Query Pattern** | User history, training validation | Analysis, statistics, ML training |
| **Retention** | Permanent | Permanent with periodic archival |

### When to Use Each Schema

**Use Feedback Schema When**:
- Querying user-tagged flights
- Validating ML model predictions
- Analyzing user feedback and comments
- Building training datasets with ground truth labels
- Quality assurance and model evaluation

**Use Research Schema When**:
- Analyzing all flight data (not just tagged)
- Computing statistics and trends
- Training ML models on large datasets
- Historical analysis and research
- Real-time monitoring queries

---

## Partition Management

### Partition Strategy

Both schemas use **monthly range partitioning** on timestamp columns to:
- Improve query performance through partition pruning
- Enable efficient data archival and deletion
- Reduce index size and maintenance overhead
- Support parallel query execution

### Partition Key Selection

| Table | Partition Column | Reason |
|-------|-----------------|---------|
| `flight_metadata` | `first_seen_ts` | Flight start time (immutable) |
| `anomalies_tracks` | `timestamp` | Track point time (most common query filter) |
| `normal_tracks` | `timestamp` | Track point time (most common query filter) |
| `anomaly_reports` | `timestamp` | Report generation time (query by date) |

### Partition Ranges

Partitions use Unix epoch timestamps with monthly boundaries:

```sql
-- Example: January 2026 partition
CREATE TABLE research.normal_tracks_2026_01 
PARTITION OF research.normal_tracks
FOR VALUES FROM (1735689600) TO (1738368000);
-- From: 2026-01-01 00:00:00 UTC
-- To:   2026-02-01 00:00:00 UTC (exclusive)
```

### Creating New Partitions

#### Automatic Creation (Recommended)

New partitions are created automatically when data is inserted if using PostgreSQL 11+.

#### Manual Creation Scripts

For pre-creating partitions:

```sql
-- Create full year partitions
\i service/create_2025_2026_partitions.sql

-- Create specific month
CREATE TABLE IF NOT EXISTS research.normal_tracks_2026_03
PARTITION OF research.normal_tracks
FOR VALUES FROM (1740787200) TO (1743465600);
```

**Helper Scripts**:
- [`create_2025_2026_partitions.sql`](create_2025_2026_partitions.sql) - Create all 2025-2026 partitions
- [`create_all_2026_partitions.sql`](create_all_2026_partitions.sql) - Create all 2026 partitions
- [`create_gap_partition.sql`](create_gap_partition.sql) - Fill gaps in partition ranges

### Partition Maintenance

#### View Existing Partitions

```sql
-- List all partitions for a table
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
FROM pg_tables
WHERE schemaname = 'research'
  AND tablename LIKE 'normal_tracks_%'
ORDER BY tablename;
```

#### Partition Statistics

```sql
-- Get row counts per partition
SELECT 
    schemaname,
    tablename,
    n_live_tup as estimated_rows,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
FROM pg_stat_user_tables
WHERE schemaname = 'research'
  AND tablename LIKE 'normal_tracks_%'
ORDER BY tablename;
```

#### Drop Old Partitions

To archive or delete old data:

```sql
-- Detach partition (keeps data, removes from parent)
ALTER TABLE research.normal_tracks 
DETACH PARTITION research.normal_tracks_2024;

-- Drop partition (deletes data)
DROP TABLE IF EXISTS research.normal_tracks_2024;
```

### Partition Pruning

PostgreSQL automatically prunes (skips) partitions based on query filters:

```sql
-- Good: Will only scan January 2026 partition
SELECT * FROM research.normal_tracks
WHERE timestamp BETWEEN 1735689600 AND 1738368000;

-- Bad: Will scan ALL partitions (no timestamp filter)
SELECT * FROM research.normal_tracks
WHERE flight_id = 'ABC123_1234567890';
```

**Best Practices**:
- Always include timestamp in WHERE clause when possible
- Use time range filters to leverage partition pruning
- Check query plans with `EXPLAIN` to verify pruning works

---

## Data Flow Architecture

```mermaid
graph TD
    subgraph External[External Data Sources]
        FR24[FR24 API<br/>Live Flight Data]
    end
    
    subgraph Monitoring[Real-time Monitoring]
        Monitor[monitor.py<br/>Flight Tracker]
        Pipeline[anomaly_pipeline.py<br/>ML Analysis]
    end
    
    subgraph Database[PostgreSQL Database]
        Live[live schema<br/>Active Flights]
        Research[research schema<br/>Historical Data]
        Feedback[feedback schema<br/>User Tagged]
    end
    
    subgraph Analysis[Analysis & Training]
        ResearchReplay[research_replay.py<br/>Historical Analysis]
        ML[ML Models<br/>Training & Inference]
    end
    
    subgraph UserInterface[User Interface]
        Web[Web UI<br/>Tagging Interface]
        API[API Server<br/>FastAPI]
    end
    
    FR24 -->|Real-time Data| Monitor
    Monitor -->|Stream| Pipeline
    Pipeline -->|Write| Live
    Monitor -->|Archive| Research
    
    Research -->|Load Data| ResearchReplay
    ResearchReplay -->|Re-analyze| Research
    
    Research -->|Training Data| ML
    Feedback -->|Validation Data| ML
    ML -->|Improve Models| Pipeline
    
    Web -->|User Actions| API
    API -->|Copy Flight Data| Feedback
    Research -->|Display Data| API
    Feedback -->|Display Tags| API
    API -->|JSON Response| Web
    
    style Feedback fill:#90EE90,stroke:#2d5016,stroke-width:2px
    style Research fill:#87CEEB,stroke:#104e8b,stroke-width:2px
    style Live fill:#FFB6C1,stroke:#8b1a1a,stroke-width:2px
    style ML fill:#FFD700,stroke:#8b7500,stroke-width:2px
```

### Data Flow Summary

1. **Real-time Collection** (monitor.py → live schema):
   - FR24 API provides live flight positions
   - monitor.py tracks active flights
   - Writes to `live` schema for real-time queries

2. **Historical Archive** (monitor.py → research schema):
   - Completed flights moved to `research` schema
   - All track points stored (separated by anomaly classification)
   - Enables long-term analysis

3. **Batch Analysis** (research_replay.py → research schema):
   - Re-analyzes historical flights with updated models
   - Updates anomaly classifications
   - Fills gaps in analysis

4. **User Tagging** (Web UI → feedback schema):
   - Users review and tag flights via web interface
   - Complete flight data copied to `feedback` schema
   - User comments and classifications stored

5. **ML Training** (feedback + research → ML models):
   - Training data from both schemas
   - Feedback provides ground truth labels
   - Research provides bulk training data

---

## Connection Management

### Connection Pool Configuration

Located in: [`service/pg_provider.py`](pg_provider.py)

```python
class PostgreSQLConnectionPool:
    # Connection string (AWS RDS)
    PG_DSN = "postgresql://postgres:***@tracer-db.cb80eku2emy0.eu-north-1.rds.amazonaws.com:5432/tracer"
    
    # Pool configuration
    MIN_CONNECTIONS = 2   # Minimum pool size
    MAX_CONNECTIONS = 10  # Maximum pool size
    
    # Timeouts
    connect_timeout = 10      # Connection timeout (seconds)
    statement_timeout = 30000 # Query timeout (milliseconds)
```

### Pool Sizing Guidelines

| Traffic Level | MIN | MAX | Use Case |
|--------------|-----|-----|----------|
| Low | 2 | 5 | Development, testing |
| Medium | 5 | 15 | Production API (current) |
| High | 10 | 30 | High-traffic production |

### Using Connections

```python
from service.pg_provider import get_connection

# Recommended: Context manager (automatic cleanup)
with get_connection() as conn:
    with conn.cursor() as cursor:
        cursor.execute("SELECT * FROM feedback.flight_metadata LIMIT 10")
        rows = cursor.fetchall()

# Connection automatically returned to pool
```

### Key Functions

#### Query Functions

```python
# Get user-tagged flights
get_tagged_feedback_history(start_ts, end_ts, limit=100, include_normal=False)

# Get research anomalies
get_research_anomalies(start_ts, end_ts, limit=1000)

# Get flight tracks
get_flight_track(flight_id, schema='feedback')

# Get flight metadata
get_flight_metadata(flight_id, schema='feedback')

# Get unified track (feedback only)
get_unified_track(flight_id)
```

#### Write Functions

```python
# Save flight data
save_flight_metadata(metadata, schema='live')
save_flight_tracks(flight_track, is_anomaly, schema='live')
save_anomaly_report(report, last_ts, metadata, schema='live')
```

#### Utility Functions

```python
# Test connection
test_connection()  # Returns True/False

# Get pool status
get_pool_status()  # Returns dict with status info

# Close pool (for cleanup/testing)
close_pool()
```

### Connection Health

The pool includes automatic health checks:
- Connection validation before use
- Automatic reconnection on failure
- Transaction rollback on errors
- Graceful cleanup on exit

### Monitoring Connection Pool

```python
from service.pg_provider import get_pool_status

status = get_pool_status()
print(status)
# Output: {
#   "status": "active",
#   "initialized": True,
#   "dsn": "tracer-db.cb80eku2emy0.eu-north-1.rds.amazonaws.com:5432/tracer"
# }
```

---

## Query Examples

### Basic Queries

#### Get Recent Anomalies

```sql
-- Feedback schema (user-tagged)
SELECT f.flight_id, f.callsign, f.airline,
       uf.tagged_at, uf.comments,
       ar.severity_cnn, ar.matched_rule_names
FROM feedback.user_feedback uf
JOIN feedback.flight_metadata f ON uf.flight_id = f.flight_id
LEFT JOIN feedback.anomaly_reports ar ON f.flight_id = ar.flight_id
WHERE uf.user_label = 1
ORDER BY uf.tagged_at DESC
LIMIT 100;

-- Research schema (ML-detected)
SELECT fm.flight_id, fm.callsign, fm.airline,
       fm.origin_airport, fm.destination_airport,
       ar.severity_cnn, ar.matched_rule_names
FROM research.flight_metadata fm
JOIN research.anomaly_reports ar ON fm.flight_id = ar.flight_id
WHERE ar.is_anomaly = true
  AND ar.severity_cnn > 0.7
  AND ar.timestamp > extract(epoch from NOW() - INTERVAL '7 days')
ORDER BY ar.severity_cnn DESC
LIMIT 50;
```

#### Get Flight Track

```sql
-- From feedback schema
SELECT timestamp, lat, lon, alt, gspeed, vspeed, track
FROM feedback.flight_tracks
WHERE flight_id = 'ABC123_1234567890'
ORDER BY timestamp;

-- From research schema (anomaly)
SELECT timestamp, lat, lon, alt, gspeed, vspeed, track
FROM research.anomalies_tracks
WHERE flight_id = 'ABC123_1234567890'
ORDER BY timestamp;

-- From research schema (normal)
SELECT timestamp, lat, lon, alt, gspeed, vspeed, track
FROM research.normal_tracks
WHERE flight_id = 'ABC123_1234567890'
ORDER BY timestamp;
```

### Advanced Queries

#### Route Analysis

```sql
-- Busiest routes in last 30 days
SELECT 
    origin_airport,
    destination_airport,
    origin_airport || ' → ' || destination_airport as route,
    COUNT(*) as flight_count,
    COUNT(DISTINCT airline) as airline_count,
    AVG(flight_duration_sec / 60.0) as avg_duration_min,
    AVG(total_distance_nm) as avg_distance_nm,
    AVG(avg_speed_kts) as avg_speed_kts
FROM research.flight_metadata
WHERE origin_airport IS NOT NULL
  AND destination_airport IS NOT NULL
  AND first_seen_ts > extract(epoch from NOW() - INTERVAL '30 days')
GROUP BY origin_airport, destination_airport
HAVING COUNT(*) >= 10
ORDER BY flight_count DESC
LIMIT 50;
```

#### Military Activity Analysis

```sql
-- Military flights by type
SELECT 
    military_type,
    COUNT(*) as flight_count,
    AVG(flight_duration_sec / 3600.0) as avg_duration_hours,
    AVG(total_distance_nm) as avg_distance_nm,
    COUNT(DISTINCT callsign) as unique_callsigns
FROM research.flight_metadata
WHERE is_military = true
  AND first_seen_ts > extract(epoch from NOW() - INTERVAL '7 days')
GROUP BY military_type
ORDER BY flight_count DESC;
```

#### Emergency Events

```sql
-- Emergency squawk codes detected
SELECT 
    flight_id,
    callsign,
    airline,
    origin_airport,
    destination_airport,
    squawk_codes,
    to_timestamp(first_seen_ts) as event_time,
    flight_duration_sec / 60.0 as duration_minutes
FROM research.flight_metadata
WHERE emergency_squawk_detected = true
ORDER BY first_seen_ts DESC
LIMIT 100;
```

#### JSONB Queries

```sql
-- Query specific rules in full_report
SELECT 
    flight_id,
    callsign,
    full_report->'layer_1_rules'->'report'->'matched_rules' as matched_rules,
    full_report->'summary'->>'severity_cnn' as severity
FROM feedback.anomaly_reports
WHERE full_report @> '{"layer_1_rules": {"is_anomaly": true}}'
  AND (full_report->'layer_1_rules'->'report'->'matched_rules')::text LIKE '%Off Course%'
LIMIT 50;

-- Extract matched rules as rows
SELECT 
    flight_id,
    callsign,
    jsonb_array_elements(
        full_report->'layer_1_rules'->'report'->'matched_rules'
    )->>'name' as rule_name,
    jsonb_array_elements(
        full_report->'layer_1_rules'->'report'->'matched_rules'
    )->>'severity' as rule_severity
FROM research.anomaly_reports
WHERE is_anomaly = true
  AND timestamp > extract(epoch from NOW() - INTERVAL '24 hours')
LIMIT 100;
```

### Aggregation Queries

#### Daily Statistics

```sql
-- Daily flight statistics
SELECT 
    DATE(to_timestamp(first_seen_ts)) as date,
    COUNT(*) as total_flights,
    COUNT(*) FILTER (WHERE is_anomaly = true) as anomaly_count,
    COUNT(*) FILTER (WHERE is_military = true) as military_count,
    COUNT(*) FILTER (WHERE emergency_squawk_detected = true) as emergency_count,
    AVG(flight_duration_sec / 60.0) as avg_duration_min,
    AVG(avg_speed_kts) as avg_speed
FROM research.flight_metadata
WHERE first_seen_ts > extract(epoch from NOW() - INTERVAL '30 days')
GROUP BY date
ORDER BY date DESC;
```

#### Hourly Traffic Patterns

```sql
-- Hourly traffic analysis
SELECT 
    EXTRACT(HOUR FROM to_timestamp(timestamp)) as hour,
    COUNT(DISTINCT flight_id) as unique_flights,
    COUNT(*) as total_points,
    AVG(alt) as avg_altitude,
    AVG(gspeed) as avg_speed
FROM research.normal_tracks
WHERE timestamp > extract(epoch from NOW() - INTERVAL '7 days')
GROUP BY hour
ORDER BY hour;
```

### Performance Optimization Examples

#### Using Partition Pruning

```sql
-- Good: Partition pruning works
EXPLAIN ANALYZE
SELECT * FROM research.normal_tracks
WHERE timestamp BETWEEN 1735689600 AND 1738368000  -- January 2026
  AND flight_id = 'ABC123_1234567890';
-- Result: Scans only 1 partition

-- Bad: No partition pruning
EXPLAIN ANALYZE
SELECT * FROM research.normal_tracks
WHERE flight_id = 'ABC123_1234567890';
-- Result: Scans ALL partitions
```

#### Using Indexes Effectively

```sql
-- Good: Uses index on callsign
SELECT * FROM research.flight_metadata
WHERE callsign = 'ABC123'
  AND first_seen_ts > extract(epoch from NOW() - INTERVAL '24 hours');

-- Good: Uses composite index
SELECT * FROM research.flight_metadata
WHERE origin_airport = 'KJFK'
  AND destination_airport = 'KLAX'
  AND first_seen_ts > extract(epoch from NOW() - INTERVAL '7 days');
```

---

## Performance Considerations

### Indexing Strategy

#### Index Types Used

1. **B-tree Indexes** (default)
   - Fast equality and range queries
   - Used on: flight_id, callsign, airline, airports
   - Best for: Point lookups, sorted scans

2. **BRIN Indexes** (Block Range Index)
   - Minimal storage overhead
   - Used on: timestamp columns in partitioned tables
   - Best for: Time-series range queries with partitions

3. **Partial Indexes**
   - Index only rows matching condition
   - Example: `WHERE is_anomaly = true`
   - Best for: Filtering on boolean flags with low selectivity

#### Index Maintenance

```sql
-- Reindex a specific table
REINDEX TABLE research.flight_metadata;

-- Reindex entire schema
REINDEX SCHEMA feedback;

-- Check index usage
SELECT 
    schemaname,
    tablename,
    indexname,
    idx_scan as index_scans,
    idx_tup_read as tuples_read,
    idx_tup_fetch as tuples_fetched
FROM pg_stat_user_indexes
WHERE schemaname IN ('research', 'feedback')
  AND idx_scan > 0
ORDER BY idx_scan DESC;

-- Find unused indexes
SELECT 
    schemaname,
    tablename,
    indexname,
    pg_size_pretty(pg_relation_size(indexrelid)) as index_size
FROM pg_stat_user_indexes
WHERE schemaname IN ('research', 'feedback')
  AND idx_scan = 0
  AND indexname NOT LIKE '%_pkey'
ORDER BY pg_relation_size(indexrelid) DESC;
```

### Query Optimization Tips

#### 1. Always Use Time Filters

```sql
-- Good: Leverages partition pruning
SELECT * FROM research.normal_tracks
WHERE timestamp > extract(epoch from NOW() - INTERVAL '24 hours')
  AND flight_id = 'ABC123_1234567890';

-- Bad: Scans all partitions
SELECT * FROM research.normal_tracks
WHERE flight_id = 'ABC123_1234567890';
```

#### 2. Use Specific Columns

```sql
-- Good: Only needed columns
SELECT flight_id, callsign, airline, severity_cnn
FROM research.anomaly_reports
WHERE is_anomaly = true;

-- Bad: Fetches all columns including large JSONB
SELECT * FROM research.anomaly_reports
WHERE is_anomaly = true;
```

#### 3. Limit Result Sets

```sql
-- Good: Limit early
SELECT * FROM research.flight_metadata
WHERE is_anomaly = true
ORDER BY first_seen_ts DESC
LIMIT 100;

-- Bad: Sorts all rows then limits
SELECT * FROM research.flight_metadata
WHERE is_anomaly = true
ORDER BY airline, callsign
LIMIT 100;
```

#### 4. Use Explain Analyze

```sql
-- Check query plan before running expensive queries
EXPLAIN ANALYZE
SELECT fm.*, ar.severity_cnn
FROM research.flight_metadata fm
JOIN research.anomaly_reports ar ON fm.flight_id = ar.flight_id
WHERE fm.is_anomaly = true
  AND ar.timestamp > extract(epoch from NOW() - INTERVAL '7 days');
```

### Maintenance Operations

#### Regular Maintenance Schedule

```sql
-- Daily: Analyze statistics
ANALYZE research.flight_metadata;
ANALYZE research.anomaly_reports;
ANALYZE feedback.flight_metadata;

-- Weekly: Vacuum to reclaim space
VACUUM ANALYZE research.flight_metadata;
VACUUM ANALYZE research.anomaly_reports;
VACUUM ANALYZE research.normal_tracks;

-- Monthly: Reindex if needed
REINDEX TABLE research.flight_metadata;
```

#### Monitoring Table Bloat

```sql
-- Check table and index sizes
SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as total_size,
    pg_size_pretty(pg_relation_size(schemaname||'.'||tablename)) as table_size,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename) - 
                   pg_relation_size(schemaname||'.'||tablename)) as index_size
FROM pg_stat_user_tables
WHERE schemaname IN ('research', 'feedback')
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

### Performance Benchmarks

Typical query performance on production system:

| Query Type | Row Count | Time | Notes |
|-----------|-----------|------|-------|
| Single flight track | 500-2000 pts | 50-200ms | With time filter + index |
| Recent anomalies | 100 rows | 100-300ms | Last 24 hours |
| Daily statistics | 30 days | 500ms-2s | Aggregation over partitions |
| Route analysis | 1000 routes | 1-3s | Complex aggregation |
| Full table scan | 1M+ rows | 10s-60s+ | Avoid without filters |

---

## Related Files

### Core Application Files

#### Database Management
- **[`service/pg_provider.py`](pg_provider.py)** - PostgreSQL connection pool and query functions
- **[`service/feedback_db.py`](feedback_db.py)** - Feedback schema creation and management
- **[`migrate_sqlite_to_postgres.py`](migrate_sqlite_to_postgres.py)** - SQLite to PostgreSQL migration script

#### Monitoring & Analysis
- **[`realtime/monitor.py`](realtime/monitor.py)** - Real-time flight monitoring (writes to live/research)
- **[`realtime/research_replay.py`](realtime/research_replay.py)** - Historical flight analysis
- **[`anomaly_pipeline.py`](anomaly_pipeline.py)** - ML model pipeline for anomaly detection

#### API & Routes
- **[`service/api.py`](service/api.py)** - Main FastAPI application
- **[`service/routes/feedback.py`](service/routes/feedback.py)** - Feedback/tagging endpoints
- **[`service/routes/flights.py`](service/routes/flights.py)** - Flight data endpoints
- **[`service/routes/analytics.py`](service/routes/analytics.py)** - Statistics and analytics

### SQL Scripts

#### Schema Creation & Maintenance
- **[`create_2025_2026_partitions.sql`](create_2025_2026_partitions.sql)** - Create partitions for 2025-2026
- **[`create_all_2026_partitions.sql`](create_all_2026_partitions.sql)** - Create all 2026 partitions
- **[`create_gap_partition.sql`](create_gap_partition.sql)** - Fill partition gaps
- **[`add_live_schema_constraints.sql`](add_live_schema_constraints.sql)** - Add constraints to live schema
- **[`create_monitor_status_table.sql`](create_monitor_status_table.sql)** - Monitor control table

#### Query References
- **[`postgres_queries.sql`](postgres_queries.sql)** - Common query examples
- **[`realtime/dashboard_queries.sql`](realtime/dashboard_queries.sql)** - Analytics and dashboard queries
- **[`check_schemas.sql`](check_schemas.sql)** - Schema verification queries
- **[`check_partitions.sql`](check_partitions.sql)** - Partition inspection queries

### Documentation

#### Integration Guides
- **[`POSTGRES_INTEGRATION.md`](POSTGRES_INTEGRATION.md)** - PostgreSQL integration overview
- **[`MIGRATION_GUIDE.md`](MIGRATION_GUIDE.md)** - SQLite to PostgreSQL migration guide
- **[`POSTGRES_CONNECTION_POOL.md`](POSTGRES_CONNECTION_POOL.md)** - Connection pool documentation
- **[`UNIFIED_TRACK_POSTGRES.md`](UNIFIED_TRACK_POSTGRES.md)** - Unified track query guide

#### Operational Guides
- **[`LIVE_MONITORING_POSTGRES.md`](LIVE_MONITORING_POSTGRES.md)** - Live monitoring setup
- **[`RESEARCH_REPLAY_POSTGRES_FIXES.md`](RESEARCH_REPLAY_POSTGRES_FIXES.md)** - Research replay troubleshooting
- **[`MONITOR_CONTROL_DB.md`](MONITOR_CONTROL_DB.md)** - Monitor control via database
- **[`QUICK_START.md`](QUICK_START.md)** - Quick start guide

#### Technical Documentation
- **[`OPTIMIZE_SAVE_TRACKS.md`](OPTIMIZE_SAVE_TRACKS.md)** - Track insertion optimization
- **[`PARTITION_KEY_FIX.md`](PARTITION_KEY_FIX.md)** - Partition key constraint fixes
- **[`PERFORMANCE_TIMING_LOGS.md`](PERFORMANCE_TIMING_LOGS.md)** - Performance monitoring
- **[`ARCHITECTURE_DIAGRAM.md`](ARCHITECTURE_DIAGRAM.md)** - System architecture

### Configuration Files
- **`requirements.txt`** - Python dependencies (includes psycopg2-binary)
- **`requirements_migration.txt`** - Migration script dependencies

---

## Summary

### Feedback Schema Summary

**Purpose**: User-tagged flights for quality control and training validation

**Tables**: 4 tables
- `flight_metadata` - 45 columns, partitioned by first_seen_ts
- `flight_tracks` - 11 columns, unified storage
- `anomaly_reports` - 19 columns, partitioned by timestamp
- `user_feedback` - 11 columns, tagging metadata

**Key Features**:
- ✅ Complete flight metadata (45+ fields)
- ✅ Unified track storage (no separation by classification)
- ✅ User tagging with comments
- ✅ JSONB analysis reports
- ✅ Monthly partitioning for metadata and reports

**Use Cases**:
- Model validation and evaluation
- Ground truth dataset creation
- Quality assurance
- User feedback analysis

---

### Research Schema Summary

**Purpose**: Historical flight data for analysis and ML training

**Tables**: 4 tables
- `flight_metadata` - 45 columns, partitioned by first_seen_ts
- `anomalies_tracks` - 11 columns, partitioned by timestamp
- `normal_tracks` - 11 columns, partitioned by timestamp
- `anomaly_reports` - 19 columns, partitioned by timestamp

**Key Features**:
- ✅ Complete historical coverage (all flights)
- ✅ Separated track storage (anomalies vs normal)
- ✅ BRIN indexes for efficient time-series queries
- ✅ Monthly partitioning on all large tables
- ✅ Continuous real-time updates

**Use Cases**:
- ML model training (large datasets)
- Statistical analysis and trends
- Historical research
- Real-time monitoring queries

---

### Overall System Capabilities

Both schemas provide comprehensive flight tracking with:

- **Rich Metadata**: 45+ fields per flight including position, speed, altitude, airports, airline, aircraft type
- **Detailed Tracks**: 11 fields per position including lat/lon, altitude, speed, heading, squawk
- **ML/Rule Analysis**: JSONB reports with 6-layer anomaly detection results
- **Time-Series Partitioning**: Monthly partitions for optimal query performance
- **Optimized Indexes**: B-tree for lookups, BRIN for time-series, partial for boolean filters
- **Connection Pooling**: 2-10 connection pool with automatic health checks
- **Data Integrity**: Primary keys, unique constraints, foreign key relationships
- **Scalability**: Handles millions of track points efficiently

The schemas support diverse workflows:
- Real-time monitoring and alerting
- Historical analysis and research
- User feedback and quality control
- ML model training and evaluation
- Statistical reporting and dashboards
- Compliance and safety monitoring

---

**Document Version**: 1.0  
**Last Updated**: February 8, 2026  
**Maintained By**: FiveAir Development Team
