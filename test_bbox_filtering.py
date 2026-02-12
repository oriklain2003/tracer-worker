#!/usr/bin/env python3
"""
Quick test to verify bounding box filtering works
"""
import os
import sys
import asyncio
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from marine_monitor import MarineMonitor
from marine_pg_provider import init_connection_pool, get_connection
import psycopg2.extras

async def test_bbox_filtering():
    """Test that bounding box filtering works correctly."""
    api_key = os.getenv("AIS_STREAM_API_KEY", "806cb56388d212f6d346775d69190649dc456907")
    
    # Use a specific region - Mediterranean Sea
    mediterranean = [[[30, -6], [46, 37]]]
    
    print("="*60)
    print("Testing Bounding Box Filtering")
    print("="*60)
    print(f"\n🌍 Test Region: Mediterranean Sea")
    print(f"   Latitude: 30°N to 46°N")
    print(f"   Longitude: 6°W to 37°E")
    print(f"\n⏱️  Running for 30 seconds to collect data...")
    
    # Clear recent data first
    if init_connection_pool():
        try:
            with get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("DELETE FROM marine.vessel_positions WHERE timestamp > NOW() - INTERVAL '5 minutes'")
                    conn.commit()
                    print(f"✅ Cleared recent test data")
        except Exception as e:
            print(f"⚠️  Could not clear data: {e}")
    
    # Create monitor with Mediterranean bounding box
    monitor = MarineMonitor(
        api_key=api_key,
        bounding_boxes=mediterranean,
        batch_size=10
    )
    
    # Run for 30 seconds
    monitor_task = asyncio.create_task(monitor.run())
    
    try:
        await asyncio.wait_for(asyncio.shield(monitor_task), timeout=30.0)
    except asyncio.TimeoutError:
        monitor.should_stop = True
        try:
            await asyncio.wait_for(monitor_task, timeout=5.0)
        except asyncio.TimeoutError:
            monitor_task.cancel()
            try:
                await monitor_task
            except asyncio.CancelledError:
                pass
    
    print(f"\n✅ Collection complete")
    print(f"   Messages received: {monitor.messages_received}")
    print(f"   Positions saved: {monitor.positions_saved}")
    print(f"   Metadata saved: {monitor.metadata_saved}")
    
    # Verify all positions are within bounding box
    print(f"\n🔍 Verifying positions are within bounding box...")
    
    if init_connection_pool():
        try:
            with get_connection() as conn:
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                    # Get recent positions
                    cursor.execute("""
                        SELECT 
                            mmsi,
                            latitude,
                            longitude
                        FROM marine.vessel_positions
                        WHERE timestamp > NOW() - INTERVAL '2 minutes'
                    """)
                    
                    positions = cursor.fetchall()
                    total = len(positions)
                    
                    if total == 0:
                        print(f"⚠️  No positions collected (region may have low traffic)")
                        return
                    
                    # Check each position
                    south, west = mediterranean[0][0]
                    north, east = mediterranean[0][1]
                    
                    inside = 0
                    outside = 0
                    
                    for pos in positions:
                        lat, lon = pos['latitude'], pos['longitude']
                        if south <= lat <= north and west <= lon <= east:
                            inside += 1
                        else:
                            outside += 1
                            if outside <= 3:  # Show first 3 violations
                                print(f"   ⚠️  Position outside bbox: MMSI {pos['mmsi']} at ({lat:.3f}, {lon:.3f})")
                    
                    print(f"\n📊 Results:")
                    print(f"   • Total positions: {total}")
                    print(f"   • Inside bounding box: {inside} ({100*inside/total:.1f}%)")
                    print(f"   • Outside bounding box: {outside} ({100*outside/total:.1f}%)")
                    
                    if outside == 0:
                        print(f"\n🎉 SUCCESS! All positions are within the configured bounding box!")
                    else:
                        print(f"\n⚠️  WARNING: Some positions are outside the bounding box")
                        print(f"   This may indicate an issue with the filtering")
                    
        except Exception as e:
            print(f"❌ Error verifying data: {e}")

if __name__ == "__main__":
    asyncio.run(test_bbox_filtering())
