#!/usr/bin/env python3
"""
Check if vessel positions are within expected bounding boxes
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from marine_pg_provider import init_connection_pool, get_connection
import psycopg2.extras

def check_bounding_boxes():
    """Check the geographic distribution of vessels."""
    print("Checking vessel geographic distribution...")
    if not init_connection_pool():
        print("❌ Failed to connect to database")
        return False
    
    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                # Get geographic bounds
                cursor.execute("""
                    SELECT 
                        MIN(latitude) as min_lat,
                        MAX(latitude) as max_lat,
                        MIN(longitude) as min_lon,
                        MAX(longitude) as max_lon,
                        COUNT(*) as total
                    FROM marine.vessel_positions
                    WHERE timestamp > NOW() - INTERVAL '10 minutes'
                """)
                
                bounds = cursor.fetchone()
                
                print(f"\n📊 Current Data Coverage (last 10 min):")
                print(f"  • Total positions: {bounds['total']}")
                print(f"  • Latitude range: {bounds['min_lat']:.2f}° to {bounds['max_lat']:.2f}°")
                print(f"  • Longitude range: {bounds['min_lon']:.2f}° to {bounds['max_lon']:.2f}°")
                
                # Show regional distribution
                cursor.execute("""
                    SELECT 
                        CASE 
                            WHEN latitude >= 0 THEN 'Northern Hemisphere'
                            ELSE 'Southern Hemisphere'
                        END as hemisphere,
                        COUNT(*) as count
                    FROM marine.vessel_positions
                    WHERE timestamp > NOW() - INTERVAL '10 minutes'
                    GROUP BY hemisphere
                    ORDER BY count DESC
                """)
                
                print(f"\n🌍 Hemisphere Distribution:")
                for row in cursor.fetchall():
                    print(f"  • {row['hemisphere']}: {row['count']} positions")
                
                # Show sample positions from different regions
                cursor.execute("""
                    SELECT 
                        mmsi,
                        latitude,
                        longitude,
                        timestamp
                    FROM marine.vessel_positions
                    WHERE timestamp > NOW() - INTERVAL '10 minutes'
                    ORDER BY timestamp DESC
                    LIMIT 10
                """)
                
                print(f"\n📍 Sample Recent Positions:")
                for pos in cursor.fetchall():
                    print(f"  • MMSI {pos['mmsi']}: ({pos['latitude']:7.3f}, {pos['longitude']:8.3f})")
                
                # Current configuration warning
                if bounds['max_lat'] - bounds['min_lat'] > 90 or bounds['max_lon'] - bounds['min_lon'] > 180:
                    print(f"\n⚠️  WARNING: Data covers a very wide area (possibly global)")
                    print(f"   Consider setting a specific bounding box in the configuration")
                
                return True
                
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    check_bounding_boxes()
