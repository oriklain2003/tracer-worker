#!/usr/bin/env python3
"""
Verify that vessel positions are within the configured bounding box(es)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from marine_pg_provider import init_connection_pool, get_connection
import psycopg2.extras

def check_positions_in_bbox(bbox_list):
    """
    Check if all positions are within the specified bounding boxes.
    
    Args:
        bbox_list: List of bounding boxes [[[south, west], [north, east]], ...]
    """
    print("Verifying bounding box filtering...")
    if not init_connection_pool():
        print("❌ Failed to connect to database")
        return False
    
    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                # Get all recent positions
                cursor.execute("""
                    SELECT 
                        mmsi,
                        latitude,
                        longitude,
                        timestamp
                    FROM marine.vessel_positions
                    WHERE timestamp > NOW() - INTERVAL '10 minutes'
                    ORDER BY timestamp DESC
                """)
                
                positions = cursor.fetchall()
                total = len(positions)
                
                if total == 0:
                    print("⚠️  No recent positions found")
                    return True
                
                # Check each position against all bounding boxes
                inside_count = 0
                outside_count = 0
                outside_positions = []
                
                for pos in positions:
                    lat, lon = pos['latitude'], pos['longitude']
                    is_inside = False
                    
                    # Check if position is in any of the bounding boxes
                    for bbox in bbox_list:
                        south, west = bbox[0]
                        north, east = bbox[1]
                        
                        if south <= lat <= north and west <= lon <= east:
                            is_inside = True
                            break
                    
                    if is_inside:
                        inside_count += 1
                    else:
                        outside_count += 1
                        if len(outside_positions) < 5:  # Keep first 5 examples
                            outside_positions.append(pos)
                
                # Print results
                print(f"\n📊 Bounding Box Verification Results:")
                print(f"  • Total positions checked: {total}")
                print(f"  • Positions inside bounding box(es): {inside_count} ({100*inside_count/total:.1f}%)")
                print(f"  • Positions outside bounding box(es): {outside_count} ({100*outside_count/total:.1f}%)")
                
                if outside_count > 0:
                    print(f"\n⚠️  WARNING: Found {outside_count} positions outside configured bounding boxes!")
                    print(f"\n📍 Sample positions outside bounding box:")
                    for pos in outside_positions:
                        print(f"  • MMSI {pos['mmsi']}: ({pos['latitude']:7.3f}, {pos['longitude']:8.3f})")
                    
                    print(f"\n🔧 Configured Bounding Boxes:")
                    for i, bbox in enumerate(bbox_list, 1):
                        south, west = bbox[0]
                        north, east = bbox[1]
                        print(f"  Box {i}: Lat {south}° to {north}°, Lon {west}° to {east}°")
                    
                    return False
                else:
                    print(f"\n✅ All positions are within configured bounding boxes!")
                    print(f"\n🔧 Configured Bounding Boxes:")
                    for i, bbox in enumerate(bbox_list, 1):
                        south, west = bbox[0]
                        north, east = bbox[1]
                        print(f"  Box {i}: Lat {south}° to {north}°, Lon {west}° to {east}°")
                    
                    return True
                
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    import os
    import json
    
    # Default to Mediterranean if not specified
    default_bbox = [[[30, -6], [46, 37]]]
    
    bbox_str = os.getenv("AIS_BOUNDING_BOX")
    if bbox_str:
        try:
            bbox_list = json.loads(bbox_str)
        except json.JSONDecodeError:
            print("⚠️  Invalid AIS_BOUNDING_BOX format, using default Mediterranean")
            bbox_list = default_bbox
    else:
        print("Using default Mediterranean bounding box")
        bbox_list = default_bbox
    
    check_positions_in_bbox(bbox_list)
