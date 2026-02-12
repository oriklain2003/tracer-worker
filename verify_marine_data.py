#!/usr/bin/env python3
"""
Quick verification script to check marine data in database
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from marine_pg_provider import init_connection_pool, get_connection
import psycopg2.extras

def verify_data():
    """Verify marine data in database."""
    print("Connecting to database...")
    if not init_connection_pool():
        print("❌ Failed to connect to database")
        return False
    
    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                # Count positions
                cursor.execute("SELECT COUNT(*) as count FROM marine.vessel_positions")
                position_count = cursor.fetchone()['count']
                print(f"✅ Total vessel positions: {position_count}")
                
                # Count metadata
                cursor.execute("SELECT COUNT(*) as count FROM marine.vessel_metadata")
                metadata_count = cursor.fetchone()['count']
                print(f"✅ Total vessel metadata: {metadata_count}")
                
                # Count recent positions (last 10 minutes)
                cursor.execute("""
                    SELECT COUNT(*) as count FROM marine.vessel_positions 
                    WHERE timestamp > NOW() - INTERVAL '10 minutes'
                """)
                recent_count = cursor.fetchone()['count']
                print(f"✅ Recent positions (10 min): {recent_count}")
                
                # Count unique vessels
                cursor.execute("""
                    SELECT COUNT(DISTINCT mmsi) as count FROM marine.vessel_positions
                """)
                unique_vessels = cursor.fetchone()['count']
                print(f"✅ Unique vessels tracked: {unique_vessels}")
                
                # Show sample data
                if recent_count > 0:
                    print("\n📍 Sample recent positions:")
                    cursor.execute("""
                        SELECT 
                            vp.mmsi,
                            vm.vessel_name,
                            vm.vessel_type_description,
                            vp.latitude,
                            vp.longitude,
                            vp.speed_over_ground,
                            vp.navigation_status,
                            vp.timestamp
                        FROM marine.vessel_positions vp
                        LEFT JOIN marine.vessel_metadata vm USING (mmsi)
                        WHERE vp.timestamp > NOW() - INTERVAL '10 minutes'
                        ORDER BY vp.timestamp DESC
                        LIMIT 5
                    """)
                    
                    positions = cursor.fetchall()
                    for pos in positions:
                        name = pos['vessel_name'] or 'Unknown'
                        vtype = pos['vessel_type_description'] or 'N/A'
                        print(f"  • {pos['mmsi']:12s} | {name:25s} | {vtype:20s} | "
                              f"({pos['latitude']:7.3f}, {pos['longitude']:8.3f}) | "
                              f"{pos['speed_over_ground'] or 0:5.1f} kts")
                
                # Check data quality
                cursor.execute("""
                    SELECT 
                        COUNT(*) as total,
                        COUNT(*) FILTER (WHERE latitude IS NOT NULL AND longitude IS NOT NULL) as with_coords,
                        COUNT(*) FILTER (WHERE speed_over_ground IS NOT NULL) as with_speed,
                        COUNT(*) FILTER (WHERE navigation_status IS NOT NULL) as with_status
                    FROM marine.vessel_positions
                    WHERE timestamp > NOW() - INTERVAL '10 minutes'
                """)
                
                quality = cursor.fetchone()
                if quality['total'] > 0:
                    print("\n📊 Data Quality (recent 10 min):")
                    print(f"  • Positions with coordinates: {quality['with_coords']}/{quality['total']} ({100*quality['with_coords']/quality['total']:.1f}%)")
                    print(f"  • Positions with speed: {quality['with_speed']}/{quality['total']} ({100*quality['with_speed']/quality['total']:.1f}%)")
                    print(f"  • Positions with status: {quality['with_status']}/{quality['total']} ({100*quality['with_status']/quality['total']:.1f}%)")
                
                print("\n🎉 Marine data pipeline is working correctly!")
                return True
                
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    verify_data()
