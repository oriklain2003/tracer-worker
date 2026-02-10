# Research Schema - Table Structures

**Database**: tracer (PostgreSQL on AWS RDS)  
**Schema**: research

---

## Tables Overview

| Table | Type | Partition Key | Row Count |
|-------|------|---------------|-----------|
| `flight_metadata` | Partitioned (monthly) | `first_seen_ts` | 50K-500K+ |
| `anomalies_tracks` | Partitioned (monthly) | `timestamp` | 1M-10M+ |
| `normal_tracks` | Partitioned (monthly) | `timestamp` | 10M-100M+ |
| `anomaly_reports` | Partitioned (monthly) | `timestamp` | 10K-100K+ |

---

## 1. research.flight_metadata

**Primary Key**: `(flight_id, first_seen_ts)`

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `flight_id` | text | NOT NULL | Unique identifier |
| `callsign` | text | NULL | Aircraft callsign |
| `flight_number` | text | NULL | Commercial flight number |
| `airline` | text | NULL | Airline name |
| `airline_code` | text | NULL | IATA/ICAO code |
| `aircraft_type` | text | NULL | Aircraft type (B738, A320) |
| `aircraft_model` | text | NULL | Full model name |
| `aircraft_registration` | text | NULL | Tail number |
| `origin_airport` | text | NULL | Departure ICAO |
| `origin_lat` | double precision | NULL | Origin latitude |
| `origin_lon` | double precision | NULL | Origin longitude |
| `destination_airport` | text | NULL | Arrival ICAO |
| `dest_lat` | double precision | NULL | Destination latitude |
| `dest_lon` | double precision | NULL | Destination longitude |
| `first_seen_ts` | bigint | NOT NULL | First detection (Unix epoch) **PARTITION KEY** |
| `last_seen_ts` | bigint | NULL | Last detection (Unix epoch) |
| `scheduled_departure` | text | NULL | ISO 8601 |
| `scheduled_arrival` | text | NULL | ISO 8601 |
| `flight_duration_sec` | bigint | NULL | Duration in seconds |
| `total_distance_nm` | double precision | NULL | Distance in nautical miles |
| `total_points` | bigint | NULL | Track point count |
| `min_altitude_ft` | double precision | NULL | Minimum altitude |
| `max_altitude_ft` | double precision | NULL | Maximum altitude |
| `avg_altitude_ft` | double precision | NULL | Average altitude |
| `cruise_altitude_ft` | double precision | NULL | Cruise altitude |
| `min_speed_kts` | double precision | NULL | Minimum ground speed |
| `max_speed_kts` | double precision | NULL | Maximum ground speed |
| `avg_speed_kts` | double precision | NULL | Average ground speed |
| `start_lat` | double precision | NULL | Starting latitude |
| `start_lon` | double precision | NULL | Starting longitude |
| `end_lat` | double precision | NULL | Ending latitude |
| `end_lon` | double precision | NULL | Ending longitude |
| `squawk_codes` | text | NULL | JSON array of squawk codes |
| `emergency_squawk_detected` | boolean | NULL | True if 7500/7600/7700 |
| `is_anomaly` | boolean | NULL | ML/rule classification |
| `is_military` | boolean | NULL | Military aircraft flag |
| `military_type` | text | NULL | tanker, ISR, fighter, transport |
| `flight_phase_summary` | text | NULL | JSON phase durations |
| `nearest_airport_start` | text | NULL | Closest airport at start |
| `nearest_airport_end` | text | NULL | Closest airport at end |
| `crossed_borders` | text | NULL | Comma-separated countries |
| `signal_loss_events` | bigint | NULL | Signal loss count |
| `data_quality_score` | double precision | NULL | Quality metric (0-1) |
| `created_at` | bigint | NULL | Record creation |
| `updated_at` | bigint | NULL | Last update |
| `category` | text | NULL | Flight category |

**Indexes**:
- `research_flight_metadata_pkey` - PRIMARY KEY (flight_id, first_seen_ts)
- `idx_flight_metadata_timestamps` - (first_seen_ts, last_seen_ts)
- `idx_flight_metadata_is_anomaly` - is_anomaly
- `idx_metadata_airline` - airline
- `idx_metadata_callsign` - callsign
- `idx_metadata_military` - is_military
- `idx_metadata_airports` - (origin_airport, destination_airport)
- `idx_metadata_emergency` - emergency_squawk_detected

---

## 2. research.anomalies_tracks

**Primary Key**: `(flight_id, timestamp)`

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `flight_id` | text | NOT NULL | Flight identifier |
| `timestamp` | bigint | NOT NULL | Position timestamp (Unix epoch) **PARTITION KEY** |
| `lat` | double precision | NULL | Latitude (-90 to 90) |
| `lon` | double precision | NULL | Longitude (-180 to 180) |
| `alt` | double precision | NULL | Altitude (feet MSL) |
| `gspeed` | double precision | NULL | Ground speed (knots) |
| `vspeed` | double precision | NULL | Vertical speed (ft/min) |
| `track` | double precision | NULL | Track angle (0-360°) |
| `squawk` | text | NULL | Transponder code |
| `callsign` | text | NULL | Aircraft callsign |
| `source` | text | NULL | Data source (fr24, adsb) |

**Indexes**:
- `research_anomalies_tracks_pkey` - PRIMARY KEY (flight_id, timestamp)
- `idx_anomalies_tracks_timestamp` - timestamp (B-tree)
- `idx_anomalies_tracks_timestamp_brin` - timestamp (BRIN)
- `idx_anomalies_tracks_flight_id` - flight_id

---

## 3. research.normal_tracks

**Primary Key**: `(flight_id, timestamp)`

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `flight_id` | text | NOT NULL | Flight identifier |
| `timestamp` | bigint | NOT NULL | Position timestamp (Unix epoch) **PARTITION KEY** |
| `lat` | double precision | NULL | Latitude (-90 to 90) |
| `lon` | double precision | NULL | Longitude (-180 to 180) |
| `alt` | double precision | NULL | Altitude (feet MSL) |
| `gspeed` | double precision | NULL | Ground speed (knots) |
| `vspeed` | double precision | NULL | Vertical speed (ft/min) |
| `track` | double precision | NULL | Track angle (0-360°) |
| `squawk` | text | NULL | Transponder code |
| `callsign` | text | NULL | Aircraft callsign |
| `source` | text | NULL | Data source (fr24, adsb) |

**Indexes**:
- `research_normal_tracks_pkey` - PRIMARY KEY (flight_id, timestamp)
- `idx_normal_tracks_timestamp` - timestamp (B-tree)
- `idx_normal_tracks_timestamp_brin` - timestamp (BRIN)
- `idx_normal_tracks_flight_id` - flight_id

---

## 4. research.anomaly_reports

**Primary Key**: `(flight_id, timestamp)`

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `id` | bigint | NOT NULL | Auto-increment ID |
| `flight_id` | text | NOT NULL | Flight identifier |
| `timestamp` | bigint | NOT NULL | Report timestamp (Unix epoch) **PARTITION KEY** |
| `is_anomaly` | boolean | NULL | Overall classification |
| `severity_cnn` | double precision | NULL | CNN severity (0.0-1.0) |
| `severity_dense` | double precision | NULL | Dense network severity (0.0-1.0) |
| `full_report` | jsonb | NULL | Complete 6-layer analysis |
| `callsign` | text | NULL | Denormalized |
| `airline` | text | NULL | Denormalized |
| `origin_airport` | text | NULL | Denormalized |
| `destination_airport` | text | NULL | Denormalized |
| `aircraft_type` | text | NULL | Denormalized |
| `flight_duration_sec` | bigint | NULL | Denormalized |
| `max_altitude_ft` | double precision | NULL | Denormalized |
| `avg_speed_kts` | double precision | NULL | Denormalized |
| `nearest_airport` | text | NULL | Nearest during anomaly |
| `geographic_region` | text | NULL | Geographic region |
| `is_military` | boolean | NULL | Denormalized |
| `matched_rule_ids` | text | NULL | Comma-separated rule IDs |
| `matched_rule_names` | text | NULL | Comma-separated names |
| `matched_rule_categories` | text | NULL | Comma-separated categories |

**Indexes**:
- `research_anomaly_reports_pkey` - PRIMARY KEY (flight_id, timestamp)
- `idx_anomaly_reports_timestamp` - timestamp
- `idx_anomaly_reports_fid` - flight_id
- `idx_anomaly_reports_callsign` - callsign
- `idx_anomaly_reports_airline` - airline
- `idx_anomaly_reports_military` - is_military
- `idx_anomaly_reports_airport` - nearest_airport
- `idx_anomaly_reports_region` - geographic_region
- `idx_anomaly_reports_severity` - (severity_cnn, severity_dense)
- `idx_anomaly_reports_rules` - matched_rule_ids

**full_report JSONB Structure**:
```json
{
  "summary": {"is_anomaly": bool, "severity_cnn": float, "severity_dense": float, "confidence_score": float},
  "layer_1_rules": {"is_anomaly": bool, "report": {...}},
  "layer_2_xgboost": {"is_anomaly": bool, "score": float, "features": {...}},
  "layer_3_deep_dense": {"is_anomaly": bool, "severity": float, "reconstruction_error": float},
  "layer_4_deep_cnn": {"is_anomaly": bool, "severity": float, "pattern_deviations": [...]},
  "layer_5_transformer": {"is_anomaly": bool, "attention_weights": [...]},
  "layer_6_hybrid": {"is_anomaly": bool, "combined_score": float}
}
```

---

## Partitions

**Naming Convention**: `research.{table_name}_YYYY_MM` or `research.{table_name}_YYYY`

**Examples**:
- `research.flight_metadata_2025`
- `research.flight_metadata_2026`
- `research.anomalies_tracks_2026_01`
- `research.normal_tracks_2026_01`
- `research.anomaly_reports_2026_01`

---

## Foreign Key Relationships

```
research.flight_metadata (flight_id)
  ↓
  ├── research.anomalies_tracks (flight_id)
  ├── research.normal_tracks (flight_id)
  └── research.anomaly_reports (flight_id)
```
