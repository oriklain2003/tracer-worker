# Marine Data API Documentation

## Overview

The marine vessel tracking system collects real-time AIS (Automatic Identification System) data from ships worldwide. This document describes the database schema, query patterns, and integration examples for consuming marine data in other services (API, UI, analytics).

---

## Table of Contents

1. [Database Schema](#database-schema)
2. [Data Models](#data-models)
3. [Common Queries](#common-queries)
4. [API Endpoint Suggestions](#api-endpoint-suggestions)
5. [TypeScript Interfaces](#typescript-interfaces)
6. [Integration Examples](#integration-examples)
7. [Performance Considerations](#performance-considerations)
8. [Real-time Updates](#real-time-updates)

---

## Database Schema

### Schema: `marine`

All marine vessel data is stored in the `marine` schema in PostgreSQL.

### Table: `marine.vessel_positions`

Real-time vessel position reports from AIS. **Partitioned by timestamp** (monthly) for efficient querying.

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| `id` | BIGSERIAL | Primary key | 12345 |
| `mmsi` | VARCHAR(9) | Maritime Mobile Service Identity (unique vessel ID) | "368207620" |
| `timestamp` | TIMESTAMP | Position report timestamp (UTC) | 2026-02-12 14:30:00 |
| `latitude` | DECIMAL(9,6) | Latitude in decimal degrees | 37.774929 |
| `longitude` | DECIMAL(9,6) | Longitude in decimal degrees | -122.419418 |
| `speed_over_ground` | DECIMAL(5,2) | Speed in knots | 12.3 |
| `course_over_ground` | DECIMAL(5,2) | Course in degrees (0-360) | 235.5 |
| `heading` | INTEGER | True heading in degrees (0-359) | 240 |
| `navigation_status` | VARCHAR(50) | Current navigation status | "Under way using engine" |
| `rate_of_turn` | DECIMAL(5,2) | Rate of turn in degrees per minute | -2.5 |
| `position_accuracy` | BOOLEAN | Position accuracy (true = high <10m) | true |
| `message_type` | INTEGER | AIS message type (1,2,3,18) | 1 |
| `received_at` | TIMESTAMP | When we received the message | 2026-02-12 14:30:01 |

**Indexes:**
- `(mmsi, timestamp DESC)` - Efficient vessel history queries
- `(received_at DESC)` - Recent data queries
- `(latitude, longitude)` - Spatial queries

**Partitions:**
- Monthly partitions (e.g., `vessel_positions_2026_02`)
- Automatically routes queries to correct partition based on timestamp

### Table: `marine.vessel_metadata`

Vessel static data and voyage information. Updated less frequently (typically every 6 minutes).

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| `mmsi` | VARCHAR(9) | PRIMARY KEY | "368207620" |
| `vessel_name` | VARCHAR(120) | Ship name | "EVER GIVEN" |
| `callsign` | VARCHAR(20) | Radio callsign | "HPEM" |
| `imo_number` | VARCHAR(10) | IMO number (international registry) | "9811000" |
| `vessel_type` | INTEGER | AIS ship type code (0-99) | 70 |
| `vessel_type_description` | VARCHAR(100) | Human-readable ship type | "Cargo" |
| `length` | INTEGER | Length in meters | 400 |
| `width` | INTEGER | Width (beam) in meters | 59 |
| `draught` | DECIMAL(4,2) | Draft in meters | 14.50 |
| `destination` | VARCHAR(120) | Reported destination | "SINGAPORE" |
| `eta` | TIMESTAMP | Estimated time of arrival | 2026-03-15 14:30:00 |
| `cargo_type` | INTEGER | Cargo type code | NULL |
| `dimension_to_bow` | INTEGER | Distance to bow from reference (meters) | 250 |
| `dimension_to_stern` | INTEGER | Distance to stern from reference (meters) | 150 |
| `dimension_to_port` | INTEGER | Distance to port from reference (meters) | 30 |
| `dimension_to_starboard` | INTEGER | Distance to starboard from reference (meters) | 29 |
| `position_fixing_device` | INTEGER | Position device type (1=GPS, 2=GLONASS) | 1 |
| `first_seen` | TIMESTAMP | When we first tracked this vessel | 2026-02-01 10:00:00 |
| `last_updated` | TIMESTAMP | Last metadata update | 2026-02-12 14:25:00 |
| `total_position_reports` | INTEGER | Total position reports received | 5420 |

**Indexes:**
- `(vessel_name)` - Search by name
- `(vessel_type)` - Filter by ship type
- `(last_updated DESC)` - Recently active vessels
- `(destination)` - Filter by destination

---

## Data Models

### Vessel Type Codes

Common AIS ship type codes:

| Code | Description |
|------|-------------|
| 0 | Not available |
| 30 | Fishing |
| 31-32 | Towing |
| 35 | Military operations |
| 36 | Sailing |
| 37 | Pleasure craft |
| 40 | High speed craft |
| 50 | Pilot vessel |
| 51 | Search and rescue |
| 52 | Tug |
| 53 | Port tender |
| 55 | Law enforcement |
| 58 | Medical transport |
| 60-69 | Passenger (with hazard categories) |
| 70-79 | Cargo (with hazard categories) |
| 80-89 | Tanker (with hazard categories) |
| 90 | Other |

### Navigation Status Codes

| Code | Status |
|------|--------|
| 0 | Under way using engine |
| 1 | At anchor |
| 2 | Not under command |
| 3 | Restricted manoeuvrability |
| 4 | Constrained by her draught |
| 5 | Moored |
| 6 | Aground |
| 7 | Engaged in fishing |
| 8 | Under way sailing |
| 15 | Not defined |

---

## Common Queries

### 1. Get Recent Vessel Positions (Last Hour)

```sql
SELECT 
    vp.mmsi,
    vm.vessel_name,
    vm.vessel_type_description,
    vp.latitude,
    vp.longitude,
    vp.speed_over_ground,
    vp.course_over_ground,
    vp.navigation_status,
    vp.timestamp
FROM marine.vessel_positions vp
LEFT JOIN marine.vessel_metadata vm USING (mmsi)
WHERE vp.timestamp > NOW() - INTERVAL '1 hour'
ORDER BY vp.timestamp DESC
LIMIT 100;
```

### 2. Get Vessel Track History

```sql
-- Get last 24 hours of positions for a specific vessel
SELECT 
    timestamp,
    latitude,
    longitude,
    speed_over_ground,
    course_over_ground,
    heading,
    navigation_status
FROM marine.vessel_positions
WHERE mmsi = '368207620'
  AND timestamp > NOW() - INTERVAL '24 hours'
ORDER BY timestamp ASC;
```

### 3. Get Active Vessels by Region (Bounding Box)

```sql
-- Get vessels currently in Mediterranean Sea
SELECT 
    vp.mmsi,
    vm.vessel_name,
    vm.vessel_type_description,
    vp.latitude,
    vp.longitude,
    vp.speed_over_ground,
    vp.timestamp
FROM marine.vessel_positions vp
LEFT JOIN marine.vessel_metadata vm USING (mmsi)
WHERE vp.timestamp > NOW() - INTERVAL '10 minutes'
  AND vp.latitude BETWEEN 30 AND 46
  AND vp.longitude BETWEEN -6 AND 37
ORDER BY vp.timestamp DESC;
```

### 4. Get Vessels by Type

```sql
-- Get all tankers currently active
SELECT 
    vm.mmsi,
    vm.vessel_name,
    vm.vessel_type_description,
    vm.length,
    vm.destination,
    vp.latitude,
    vp.longitude,
    vp.timestamp
FROM marine.vessel_metadata vm
INNER JOIN LATERAL (
    SELECT latitude, longitude, timestamp
    FROM marine.vessel_positions
    WHERE mmsi = vm.mmsi
      AND timestamp > NOW() - INTERVAL '10 minutes'
    ORDER BY timestamp DESC
    LIMIT 1
) vp ON true
WHERE vm.vessel_type BETWEEN 80 AND 89  -- Tankers
ORDER BY vm.vessel_name;
```

### 5. Get Vessel Details with Latest Position

```sql
-- Get complete vessel information including latest position
SELECT 
    vm.mmsi,
    vm.vessel_name,
    vm.callsign,
    vm.imo_number,
    vm.vessel_type_description,
    vm.length,
    vm.width,
    vm.destination,
    vm.eta,
    vp.latitude,
    vp.longitude,
    vp.speed_over_ground,
    vp.course_over_ground,
    vp.navigation_status,
    vp.timestamp as last_position_time,
    vm.total_position_reports
FROM marine.vessel_metadata vm
LEFT JOIN LATERAL (
    SELECT *
    FROM marine.vessel_positions
    WHERE mmsi = vm.mmsi
    ORDER BY timestamp DESC
    LIMIT 1
) vp ON true
WHERE vm.mmsi = '368207620';
```

### 6. Get Vessels Near a Point

```sql
-- Get vessels within ~50km of a point (simplified distance calculation)
-- For accurate distance, use PostGIS or geodesy functions
SELECT 
    vm.mmsi,
    vm.vessel_name,
    vp.latitude,
    vp.longitude,
    vp.speed_over_ground,
    vp.timestamp,
    -- Approximate distance in degrees (1 degree ≈ 111km)
    SQRT(
        POW(vp.latitude - 37.7749, 2) + 
        POW(vp.longitude - (-122.4194), 2)
    ) * 111 as distance_km
FROM marine.vessel_positions vp
LEFT JOIN marine.vessel_metadata vm USING (mmsi)
WHERE vp.timestamp > NOW() - INTERVAL '10 minutes'
  -- Bounding box filter (faster than distance calculation)
  AND vp.latitude BETWEEN 37.3 AND 38.3
  AND vp.longitude BETWEEN -122.9 AND -121.9
HAVING distance_km < 50
ORDER BY distance_km ASC;
```

### 7. Get Traffic Statistics

```sql
-- Get vessel count by type (last hour)
SELECT 
    vm.vessel_type_description,
    COUNT(DISTINCT vp.mmsi) as vessel_count,
    AVG(vp.speed_over_ground) as avg_speed_knots
FROM marine.vessel_positions vp
LEFT JOIN marine.vessel_metadata vm USING (mmsi)
WHERE vp.timestamp > NOW() - INTERVAL '1 hour'
GROUP BY vm.vessel_type_description
ORDER BY vessel_count DESC;
```

### 8. Get Vessels Heading to Port

```sql
-- Get vessels with destination containing port name
SELECT 
    vm.mmsi,
    vm.vessel_name,
    vm.vessel_type_description,
    vm.destination,
    vm.eta,
    vp.latitude,
    vp.longitude,
    vp.speed_over_ground
FROM marine.vessel_metadata vm
LEFT JOIN LATERAL (
    SELECT latitude, longitude, speed_over_ground
    FROM marine.vessel_positions
    WHERE mmsi = vm.mmsi
    ORDER BY timestamp DESC
    LIMIT 1
) vp ON true
WHERE vm.destination ILIKE '%SINGAPORE%'
  AND vm.eta > NOW()
ORDER BY vm.eta ASC;
```

### 9. Get Historical Position Count by Hour

```sql
-- Get position reports per hour for last 24 hours
SELECT 
    DATE_TRUNC('hour', timestamp) as hour,
    COUNT(*) as position_count,
    COUNT(DISTINCT mmsi) as unique_vessels
FROM marine.vessel_positions
WHERE timestamp > NOW() - INTERVAL '24 hours'
GROUP BY hour
ORDER BY hour DESC;
```

### 10. Get Latest Position for Multiple Vessels

```sql
-- Get latest position for a list of MMSIs
SELECT DISTINCT ON (mmsi)
    mmsi,
    latitude,
    longitude,
    speed_over_ground,
    course_over_ground,
    navigation_status,
    timestamp
FROM marine.vessel_positions
WHERE mmsi = ANY(ARRAY['368207620', '367719770', '211476060'])
  AND timestamp > NOW() - INTERVAL '1 hour'
ORDER BY mmsi, timestamp DESC;
```

---

## API Endpoint Suggestions

### Recommended REST API Endpoints

#### 1. `GET /api/marine/vessels`
Get list of active vessels with pagination

**Query Parameters:**
- `limit` (default: 50, max: 1000)
- `offset` (default: 0)
- `since` (ISO timestamp, default: last 10 minutes)
- `bbox` (bounding box: `south,west,north,east`)
- `type` (vessel type code or name)
- `search` (search vessel name)

**Response:**
```json
{
  "vessels": [
    {
      "mmsi": "368207620",
      "name": "EVER GIVEN",
      "type": "Cargo",
      "position": {
        "latitude": 37.7749,
        "longitude": -122.4194,
        "timestamp": "2026-02-12T14:30:00Z"
      },
      "speed": 12.3,
      "course": 235.5,
      "heading": 240,
      "status": "Under way using engine"
    }
  ],
  "total": 1523,
  "limit": 50,
  "offset": 0
}
```

#### 2. `GET /api/marine/vessels/:mmsi`
Get detailed vessel information

**Response:**
```json
{
  "mmsi": "368207620",
  "name": "EVER GIVEN",
  "callsign": "HPEM",
  "imo": "9811000",
  "type": {
    "code": 70,
    "description": "Cargo"
  },
  "dimensions": {
    "length": 400,
    "width": 59,
    "draught": 14.5
  },
  "voyage": {
    "destination": "SINGAPORE",
    "eta": "2026-03-15T14:30:00Z"
  },
  "position": {
    "latitude": 37.7749,
    "longitude": -122.4194,
    "speed": 12.3,
    "course": 235.5,
    "heading": 240,
    "status": "Under way using engine",
    "timestamp": "2026-02-12T14:30:00Z"
  },
  "statistics": {
    "firstSeen": "2026-02-01T10:00:00Z",
    "lastUpdated": "2026-02-12T14:25:00Z",
    "totalPositions": 5420
  }
}
```

#### 3. `GET /api/marine/vessels/:mmsi/track`
Get vessel track history

**Query Parameters:**
- `from` (ISO timestamp, default: 24 hours ago)
- `to` (ISO timestamp, default: now)
- `limit` (max points, default: 1000)

**Response:**
```json
{
  "mmsi": "368207620",
  "name": "EVER GIVEN",
  "track": [
    {
      "latitude": 37.7749,
      "longitude": -122.4194,
      "speed": 12.3,
      "course": 235.5,
      "heading": 240,
      "timestamp": "2026-02-12T14:30:00Z"
    }
  ],
  "points": 428
}
```

#### 4. `GET /api/marine/statistics`
Get marine traffic statistics

**Query Parameters:**
- `since` (ISO timestamp, default: last hour)
- `groupBy` (type, status, region)

**Response:**
```json
{
  "period": {
    "from": "2026-02-12T13:00:00Z",
    "to": "2026-02-12T14:00:00Z"
  },
  "totalVessels": 3542,
  "totalPositions": 156234,
  "byType": {
    "Cargo": 1234,
    "Tanker": 567,
    "Passenger": 234
  },
  "byStatus": {
    "Under way using engine": 2456,
    "At anchor": 678,
    "Moored": 234
  }
}
```

#### 5. `GET /api/marine/search`
Search vessels by name or MMSI

**Query Parameters:**
- `q` (search query)
- `limit` (default: 20)

**Response:**
```json
{
  "results": [
    {
      "mmsi": "368207620",
      "name": "EVER GIVEN",
      "type": "Cargo",
      "lastSeen": "2026-02-12T14:30:00Z"
    }
  ],
  "total": 1
}
```

#### 6. `GET /api/marine/heatmap`
Get position density for heatmap visualization

**Query Parameters:**
- `bbox` (required: `south,west,north,east`)
- `since` (ISO timestamp, default: last 24 hours)
- `resolution` (grid size, default: 0.1 degrees)

**Response:**
```json
{
  "grid": [
    {
      "lat": 37.7,
      "lon": -122.4,
      "count": 523,
      "avgSpeed": 11.2
    }
  ],
  "bounds": {
    "south": 30,
    "west": -130,
    "north": 50,
    "east": -100
  }
}
```

---

## TypeScript Interfaces

### For Frontend (React/TypeScript)

```typescript
// Core types
export interface VesselPosition {
  mmsi: string;
  timestamp: string; // ISO 8601
  latitude: number;
  longitude: number;
  speedOverGround: number | null; // knots
  courseOverGround: number | null; // degrees
  heading: number | null; // degrees
  navigationStatus: string | null;
  rateOfTurn: number | null; // degrees per minute
  positionAccuracy: boolean | null;
}

export interface VesselMetadata {
  mmsi: string;
  vesselName: string | null;
  callsign: string | null;
  imoNumber: string | null;
  vesselType: number | null;
  vesselTypeDescription: string | null;
  length: number | null; // meters
  width: number | null; // meters
  draught: number | null; // meters
  destination: string | null;
  eta: string | null; // ISO 8601
  cargoType: number | null;
  firstSeen: string; // ISO 8601
  lastUpdated: string; // ISO 8601
  totalPositionReports: number;
}

export interface Vessel {
  mmsi: string;
  name: string | null;
  type: {
    code: number | null;
    description: string | null;
  };
  position: {
    latitude: number;
    longitude: number;
    speed: number | null;
    course: number | null;
    heading: number | null;
    status: string | null;
    timestamp: string; // ISO 8601
  };
  dimensions?: {
    length: number | null;
    width: number | null;
    draught: number | null;
  };
  voyage?: {
    destination: string | null;
    eta: string | null;
  };
}

export interface VesselTrack {
  mmsi: string;
  name: string | null;
  track: VesselPosition[];
  points: number;
}

export interface VesselListResponse {
  vessels: Vessel[];
  total: number;
  limit: number;
  offset: number;
}

export interface MarineStatistics {
  period: {
    from: string; // ISO 8601
    to: string; // ISO 8601
  };
  totalVessels: number;
  totalPositions: number;
  byType: Record<string, number>;
  byStatus: Record<string, number>;
}

// Enums
export enum VesselTypeCode {
  NotAvailable = 0,
  Fishing = 30,
  Towing = 31,
  MilitaryOps = 35,
  Sailing = 36,
  PleasureCraft = 37,
  HighSpeedCraft = 40,
  Pilot = 50,
  SearchAndRescue = 51,
  Tug = 52,
  PortTender = 53,
  LawEnforcement = 55,
  MedicalTransport = 58,
  Passenger = 60,
  Cargo = 70,
  Tanker = 80,
  Other = 90,
}

export enum NavigationStatus {
  UnderWayEngine = 'Under way using engine',
  AtAnchor = 'At anchor',
  NotUnderCommand = 'Not under command',
  RestrictedManeuverability = 'Restricted manoeuvrability',
  ConstrainedByDraught = 'Constrained by her draught',
  Moored = 'Moored',
  Aground = 'Aground',
  Fishing = 'Engaged in fishing',
  UnderWaySailing = 'Under way sailing',
  NotDefined = 'Not defined',
}

// Filter types
export interface VesselFilters {
  bbox?: {
    south: number;
    west: number;
    north: number;
    east: number;
  };
  types?: number[];
  search?: string;
  since?: Date;
}
```

---

## Integration Examples

### 1. Python (FastAPI Backend)

```python
from fastapi import FastAPI, Query
from typing import List, Optional
from datetime import datetime, timedelta
import psycopg2
from psycopg2.extras import RealDictCursor

app = FastAPI()

def get_db_connection():
    """Get database connection."""
    return psycopg2.connect(
        host="tracer-db.cb80eku2emy0.eu-north-1.rds.amazonaws.com",
        port=5432,
        database="tracer",
        user="postgres",
        password="your_password"
    )

@app.get("/api/marine/vessels")
async def get_vessels(
    limit: int = Query(50, le=1000),
    offset: int = Query(0, ge=0),
    since_minutes: int = Query(10, ge=1, le=1440),
    vessel_type: Optional[str] = None
):
    """Get list of active vessels."""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            query = """
                SELECT DISTINCT ON (vp.mmsi)
                    vp.mmsi,
                    vm.vessel_name as name,
                    vm.vessel_type_description as type,
                    vp.latitude,
                    vp.longitude,
                    vp.speed_over_ground as speed,
                    vp.course_over_ground as course,
                    vp.heading,
                    vp.navigation_status as status,
                    vp.timestamp
                FROM marine.vessel_positions vp
                LEFT JOIN marine.vessel_metadata vm USING (mmsi)
                WHERE vp.timestamp > NOW() - INTERVAL '%s minutes'
            """
            
            params = [since_minutes]
            
            if vessel_type:
                query += " AND vm.vessel_type_description ILIKE %s"
                params.append(f"%{vessel_type}%")
            
            query += """
                ORDER BY vp.mmsi, vp.timestamp DESC
                LIMIT %s OFFSET %s
            """
            params.extend([limit, offset])
            
            cursor.execute(query, params)
            vessels = cursor.fetchall()
            
            # Get total count
            count_query = """
                SELECT COUNT(DISTINCT mmsi)
                FROM marine.vessel_positions
                WHERE timestamp > NOW() - INTERVAL '%s minutes'
            """
            cursor.execute(count_query, [since_minutes])
            total = cursor.fetchone()['count']
            
            return {
                "vessels": vessels,
                "total": total,
                "limit": limit,
                "offset": offset
            }
    finally:
        conn.close()

@app.get("/api/marine/vessels/{mmsi}")
async def get_vessel_details(mmsi: str):
    """Get detailed vessel information."""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            query = """
                SELECT 
                    vm.*,
                    vp.latitude,
                    vp.longitude,
                    vp.speed_over_ground,
                    vp.course_over_ground,
                    vp.heading,
                    vp.navigation_status,
                    vp.timestamp as last_position_time
                FROM marine.vessel_metadata vm
                LEFT JOIN LATERAL (
                    SELECT *
                    FROM marine.vessel_positions
                    WHERE mmsi = vm.mmsi
                    ORDER BY timestamp DESC
                    LIMIT 1
                ) vp ON true
                WHERE vm.mmsi = %s
            """
            cursor.execute(query, [mmsi])
            vessel = cursor.fetchone()
            
            if not vessel:
                return {"error": "Vessel not found"}, 404
            
            return vessel
    finally:
        conn.close()

@app.get("/api/marine/vessels/{mmsi}/track")
async def get_vessel_track(
    mmsi: str,
    hours: int = Query(24, ge=1, le=168)
):
    """Get vessel track history."""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            query = """
                SELECT 
                    latitude,
                    longitude,
                    speed_over_ground as speed,
                    course_over_ground as course,
                    heading,
                    timestamp
                FROM marine.vessel_positions
                WHERE mmsi = %s
                  AND timestamp > NOW() - INTERVAL '%s hours'
                ORDER BY timestamp ASC
            """
            cursor.execute(query, [mmsi, hours])
            track = cursor.fetchall()
            
            # Get vessel name
            cursor.execute(
                "SELECT vessel_name FROM marine.vessel_metadata WHERE mmsi = %s",
                [mmsi]
            )
            vessel = cursor.fetchone()
            
            return {
                "mmsi": mmsi,
                "name": vessel['vessel_name'] if vessel else None,
                "track": track,
                "points": len(track)
            }
    finally:
        conn.close()
```

### 2. React Frontend (Map Integration)

```typescript
import React, { useEffect, useState } from 'react';
import { MapContainer, TileLayer, Marker, Popup, Polyline } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';

interface VesselMapProps {
  bbox?: [number, number, number, number]; // [south, west, north, east]
}

export const VesselMap: React.FC<VesselMapProps> = ({ bbox }) => {
  const [vessels, setVessels] = useState<Vessel[]>([]);
  const [selectedVessel, setSelectedVessel] = useState<string | null>(null);
  const [track, setTrack] = useState<VesselPosition[]>([]);

  useEffect(() => {
    // Fetch vessels every 30 seconds
    const fetchVessels = async () => {
      const params = new URLSearchParams({
        limit: '1000',
        since_minutes: '10'
      });
      
      if (bbox) {
        params.append('bbox', bbox.join(','));
      }
      
      const response = await fetch(`/api/marine/vessels?${params}`);
      const data = await response.json();
      setVessels(data.vessels);
    };

    fetchVessels();
    const interval = setInterval(fetchVessels, 30000);
    
    return () => clearInterval(interval);
  }, [bbox]);

  const handleVesselClick = async (mmsi: string) => {
    setSelectedVessel(mmsi);
    
    // Fetch track history
    const response = await fetch(`/api/marine/vessels/${mmsi}/track?hours=24`);
    const data = await response.json();
    setTrack(data.track);
  };

  return (
    <MapContainer
      center={[37.7749, -122.4194]}
      zoom={8}
      style={{ height: '100vh', width: '100%' }}
    >
      <TileLayer
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        attribution='&copy; OpenStreetMap contributors'
      />
      
      {/* Render vessel markers */}
      {vessels.map((vessel) => (
        <Marker
          key={vessel.mmsi}
          position={[vessel.position.latitude, vessel.position.longitude]}
          eventHandlers={{
            click: () => handleVesselClick(vessel.mmsi)
          }}
        >
          <Popup>
            <div>
              <h3>{vessel.name || 'Unknown'}</h3>
              <p>MMSI: {vessel.mmsi}</p>
              <p>Type: {vessel.type.description}</p>
              <p>Speed: {vessel.position.speed?.toFixed(1) || 'N/A'} knots</p>
              <p>Course: {vessel.position.course?.toFixed(0) || 'N/A'}°</p>
              <p>Status: {vessel.position.status}</p>
            </div>
          </Popup>
        </Marker>
      ))}
      
      {/* Render selected vessel track */}
      {selectedVessel && track.length > 0 && (
        <Polyline
          positions={track.map(p => [p.latitude, p.longitude])}
          color="blue"
          weight={2}
        />
      )}
    </MapContainer>
  );
};
```

### 3. Node.js (Express Backend)

```javascript
const express = require('express');
const { Pool } = require('pg');

const app = express();

const pool = new Pool({
  host: 'tracer-db.cb80eku2emy0.eu-north-1.rds.amazonaws.com',
  port: 5432,
  database: 'tracer',
  user: 'postgres',
  password: 'your_password',
  max: 20
});

// Get active vessels
app.get('/api/marine/vessels', async (req, res) => {
  try {
    const { limit = 50, offset = 0, since_minutes = 10, type } = req.query;
    
    let query = `
      SELECT DISTINCT ON (vp.mmsi)
        vp.mmsi,
        vm.vessel_name as name,
        vm.vessel_type_description as type,
        vp.latitude,
        vp.longitude,
        vp.speed_over_ground as speed,
        vp.course_over_ground as course,
        vp.heading,
        vp.navigation_status as status,
        vp.timestamp
      FROM marine.vessel_positions vp
      LEFT JOIN marine.vessel_metadata vm USING (mmsi)
      WHERE vp.timestamp > NOW() - INTERVAL '${parseInt(since_minutes)} minutes'
    `;
    
    if (type) {
      query += ` AND vm.vessel_type_description ILIKE '%${type}%'`;
    }
    
    query += `
      ORDER BY vp.mmsi, vp.timestamp DESC
      LIMIT ${parseInt(limit)} OFFSET ${parseInt(offset)}
    `;
    
    const result = await pool.query(query);
    
    res.json({
      vessels: result.rows,
      total: result.rowCount,
      limit: parseInt(limit),
      offset: parseInt(offset)
    });
  } catch (error) {
    console.error('Error fetching vessels:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
});

// Get vessel track
app.get('/api/marine/vessels/:mmsi/track', async (req, res) => {
  try {
    const { mmsi } = req.params;
    const { hours = 24 } = req.query;
    
    const query = `
      SELECT 
        latitude,
        longitude,
        speed_over_ground as speed,
        course_over_ground as course,
        heading,
        timestamp
      FROM marine.vessel_positions
      WHERE mmsi = $1
        AND timestamp > NOW() - INTERVAL '${parseInt(hours)} hours'
      ORDER BY timestamp ASC
    `;
    
    const result = await pool.query(query, [mmsi]);
    
    res.json({
      mmsi,
      track: result.rows,
      points: result.rowCount
    });
  } catch (error) {
    console.error('Error fetching track:', error);
    res.status(500).json({ error: 'Internal server error' });
  }
});

app.listen(3000, () => {
  console.log('Marine API server running on port 3000');
});
```

---

## Performance Considerations

### 1. Query Optimization

**Use Indexes Effectively:**
```sql
-- Good: Uses index on (mmsi, timestamp)
SELECT * FROM marine.vessel_positions 
WHERE mmsi = '368207620' 
  AND timestamp > NOW() - INTERVAL '24 hours'
ORDER BY timestamp DESC;

-- Bad: Doesn't use index efficiently
SELECT * FROM marine.vessel_positions 
WHERE EXTRACT(HOUR FROM timestamp) = 14;
```

**Use LATERAL Joins for Latest Position:**
```sql
-- Efficient way to get latest position for each vessel
SELECT vm.*, vp.*
FROM marine.vessel_metadata vm
LEFT JOIN LATERAL (
  SELECT * FROM marine.vessel_positions
  WHERE mmsi = vm.mmsi
  ORDER BY timestamp DESC
  LIMIT 1
) vp ON true;
```

### 2. Partition Awareness

The `vessel_positions` table is partitioned by timestamp. Queries are most efficient when they include timestamp constraints:

```sql
-- Good: Partition pruning works
SELECT * FROM marine.vessel_positions
WHERE timestamp BETWEEN '2026-02-01' AND '2026-02-28'
  AND mmsi = '368207620';

-- Less efficient: Scans all partitions
SELECT * FROM marine.vessel_positions
WHERE mmsi = '368207620'
LIMIT 100;
```

### 3. Caching Strategies

- **Cache vessel metadata** (changes infrequently, ~6 minutes)
- **Cache vessel lists** for short periods (30-60 seconds)
- **Don't cache individual positions** (real-time data)

### 4. Rate Limiting

For public APIs, implement rate limiting:
- 100 requests/minute per IP for vessel lists
- 1000 requests/minute for track history
- Websocket connections for real-time updates

---

## Real-time Updates

### WebSocket Integration

For real-time vessel position updates, consider implementing a WebSocket endpoint:

```javascript
// Server-side (Node.js example)
const WebSocket = require('ws');
const wss = new WebSocket.Server({ port: 8080 });

wss.on('connection', (ws) => {
  // Subscribe to vessel updates
  ws.on('message', (message) => {
    const { action, mmsi } = JSON.parse(message);
    
    if (action === 'subscribe' && mmsi) {
      ws.mmsi = mmsi;
      ws.send(JSON.stringify({ status: 'subscribed', mmsi }));
    }
  });
});

// Broadcast position updates (triggered by database changes or polling)
function broadcastPositionUpdate(mmsi, position) {
  wss.clients.forEach((client) => {
    if (client.mmsi === mmsi && client.readyState === WebSocket.OPEN) {
      client.send(JSON.stringify({
        type: 'position_update',
        mmsi,
        position
      }));
    }
  });
}
```

```typescript
// Client-side (React)
const useVesselTracking = (mmsi: string) => {
  const [position, setPosition] = useState<VesselPosition | null>(null);
  
  useEffect(() => {
    const ws = new WebSocket('ws://localhost:8080');
    
    ws.onopen = () => {
      ws.send(JSON.stringify({ action: 'subscribe', mmsi }));
    };
    
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === 'position_update') {
        setPosition(data.position);
      }
    };
    
    return () => ws.close();
  }, [mmsi]);
  
  return position;
};
```

---

## Additional Resources

### Useful Links

- **AISstream.io Documentation**: https://aisstream.io/documentation
- **AIS Message Types**: https://gpsd.gitlab.io/gpsd/AIVDM.html
- **IMO Numbers**: https://www.imo.org/
- **Vessel Tracking Services**: https://www.marinetraffic.com

### Data Quality Notes

1. **Position Accuracy**: 
   - High accuracy (position_accuracy=true): <10m
   - Low accuracy (position_accuracy=false): >10m

2. **Update Frequency**:
   - Position reports: Every 2-10 seconds (depending on vessel speed)
   - Static data: Every 6 minutes
   - Our system batches every 100 messages

3. **Coverage**:
   - Global coverage via AISstream.io
   - Higher density near coastlines
   - Sparse coverage in open ocean

4. **Data Retention**:
   - Positions: Stored in monthly partitions
   - Recommend archiving data older than 3 months
   - Keep metadata indefinitely

### Support

For questions about marine data integration:
- See: `MARINE_SETUP.md` for initial setup
- Check: Database schema comments in `create_marine_schema.sql`
- Review: Example code in `marine_monitor.py`

---

**Last Updated**: February 12, 2026  
**Schema Version**: 1.0  
**Maintained by**: Tracer Development Team
