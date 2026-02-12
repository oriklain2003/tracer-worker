-- Check Mediterranean bounding box (30°N to 46°N, 6°W to 37°E)
-- Verify all recent positions are within the configured region

SELECT 
    COUNT(*) as total_positions,
    COUNT(*) FILTER (
        WHERE latitude BETWEEN 30 AND 46 
        AND longitude BETWEEN -6 AND 37
    ) as inside_mediterranean,
    COUNT(*) FILTER (
        WHERE latitude NOT BETWEEN 30 AND 46 
        OR longitude NOT BETWEEN -6 AND 37
    ) as outside_mediterranean,
    MIN(latitude) as min_lat,
    MAX(latitude) as max_lat,
    MIN(longitude) as min_lon,
    MAX(longitude) as max_lon
FROM marine.vessel_positions
WHERE timestamp > NOW() - INTERVAL '10 minutes';

-- Show sample positions to verify locations
SELECT 
    mmsi,
    latitude,
    longitude,
    timestamp,
    CASE 
        WHEN latitude BETWEEN 30 AND 46 AND longitude BETWEEN -6 AND 37 THEN '✓ Inside'
        ELSE '✗ Outside'
    END as in_bbox
FROM marine.vessel_positions
WHERE timestamp > NOW() - INTERVAL '10 minutes'
ORDER BY timestamp DESC
LIMIT 10;
