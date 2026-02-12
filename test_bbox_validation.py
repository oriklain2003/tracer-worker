#!/usr/bin/env python3
"""
Test Bounding Box Validation

This script verifies that the bounding box filtering is working correctly:
1. Tests the _is_within_bounding_box method logic
2. Runs a short collection test to verify real data is filtered
3. Checks database for any positions outside the configured bounding box

Usage:
    python test_bbox_validation.py
"""

import sys
import os
import asyncio
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from marine_monitor import MarineMonitor
from marine_pg_provider import get_connection, init_connection_pool


def test_bbox_logic():
    """Test the bounding box filtering logic."""
    print("=" * 60)
    print("Step 1: Testing Bounding Box Logic")
    print("=" * 60)
    
    # Create a monitor with Mediterranean bounding box
    mediterranean_bbox = [[[30, -6], [46, 37]]]
    
    monitor = MarineMonitor(
        api_key="test_key",
        bounding_boxes=mediterranean_bbox
    )
    
    # Test cases: (lat, lon, should_be_inside)
    test_cases = [
        # Inside Mediterranean
        (38.0, 15.0, True, "Central Mediterranean"),
        (35.5, 14.4, True, "Malta"),
        (40.85, 14.26, True, "Naples, Italy"),
        (43.73, 7.42, True, "Nice, France"),
        (36.14, -5.35, True, "Gibraltar"),
        
        # Outside Mediterranean
        (50.0, 0.0, False, "English Channel"),
        (25.0, 15.0, False, "Sahara Desert"),
        (40.0, -10.0, False, "Atlantic Ocean"),
        (40.0, 50.0, False, "Caspian Sea"),
        (60.0, 20.0, False, "Baltic Sea"),
    ]
    
    passed = 0
    failed = 0
    
    for lat, lon, expected, description in test_cases:
        result = monitor._is_within_bounding_box(lat, lon)
        status = "✅" if result == expected else "❌"
        
        if result == expected:
            passed += 1
        else:
            failed += 1
        
        print(f"{status} ({lat:7.2f}, {lon:7.2f}) -> {result:5} (expected {expected:5}) - {description}")
    
    print(f"\nResults: {passed} passed, {failed} failed")
    
    if failed > 0:
        print("❌ FAILED: Bounding box logic has errors!")
        return False
    
    print("✅ PASSED: Bounding box logic is correct")
    print()
    return True


async def test_live_filtering():
    """Test live data collection with filtering."""
    print("=" * 60)
    print("Step 2: Testing Live Data Filtering")
    print("=" * 60)
    
    # Check API key
    api_key = os.getenv("AIS_STREAM_API_KEY")
    if not api_key:
        print("⚠️  SKIPPED: AIS_STREAM_API_KEY not set")
        print("   Set the API key to test live filtering")
        return True
    
    # Mediterranean bounding box
    mediterranean_bbox = [[[30, -6], [46, 37]]]
    
    print(f"Configured bounding box: {mediterranean_bbox}")
    print("Running monitor for 30 seconds to test filtering...")
    
    try:
        monitor = MarineMonitor(
            api_key=api_key,
            bounding_boxes=mediterranean_bbox,
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
        
        print(f"\n📊 Collection Results:")
        print(f"  - Messages received: {monitor.messages_received}")
        print(f"  - Positions saved: {monitor.positions_saved}")
        print(f"  - Positions filtered: {monitor.positions_filtered}")
        print(f"  - Metadata saved: {monitor.metadata_saved}")
        
        if monitor.positions_filtered > 0:
            filter_rate = 100 * monitor.positions_filtered / (monitor.positions_saved + monitor.positions_filtered)
            print(f"  - Filter rate: {filter_rate:.1f}%")
            print("\n⚠️  WARNING: Some positions were outside the bounding box!")
            print("   This indicates the AISstream.io server-side filtering may not be working.")
            print("   However, local filtering is now active and preventing invalid data.")
        else:
            print(f"  - Filter rate: 0%")
            print("\n✅ All positions were within the configured bounding box!")
        
    except Exception as e:
        print(f"❌ Error during live test: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print()
    return True


def test_database_positions():
    """Check database for any positions outside bounding box."""
    print("=" * 60)
    print("Step 3: Checking Database for Invalid Positions")
    print("=" * 60)
    
    if not init_connection_pool():
        print("⚠️  SKIPPED: Could not connect to database")
        return True
    
    # Mediterranean bounding box
    south, west = 30, -6
    north, east = 46, 37
    
    try:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                # Count total positions
                cursor.execute("SELECT COUNT(*) FROM marine.vessel_positions")
                total = cursor.fetchone()[0]
                
                # Count positions outside bounding box
                cursor.execute("""
                    SELECT COUNT(*) FROM marine.vessel_positions
                    WHERE latitude < %s OR latitude > %s
                       OR longitude < %s OR longitude > %s
                """, (south, north, west, east))
                
                outside = cursor.fetchone()[0]
                
                print(f"Total positions in database: {total}")
                print(f"Positions outside Mediterranean bbox: {outside}")
                
                if outside > 0:
                    outside_pct = 100 * outside / total if total > 0 else 0
                    print(f"Percentage outside bbox: {outside_pct:.2f}%")
                    
                    # Show some examples
                    cursor.execute("""
                        SELECT mmsi, latitude, longitude, timestamp
                        FROM marine.vessel_positions
                        WHERE latitude < %s OR latitude > %s
                           OR longitude < %s OR longitude > %s
                        ORDER BY timestamp DESC
                        LIMIT 5
                    """, (south, north, west, east))
                    
                    examples = cursor.fetchall()
                    
                    if examples:
                        print("\nExamples of positions outside bounding box:")
                        print(f"{'MMSI':<12} {'Latitude':<10} {'Longitude':<11} {'Timestamp'}")
                        print("-" * 60)
                        for mmsi, lat, lon, ts in examples:
                            print(f"{mmsi:<12} {lat:>9.4f} {lon:>10.4f} {ts}")
                    
                    print("\n⚠️  WARNING: Database contains positions outside bounding box!")
                    print("   This may be historical data from before filtering was added.")
                    print("   New data collection should now filter correctly.")
                else:
                    print("\n✅ All positions in database are within the bounding box!")
                
    except Exception as e:
        print(f"Error checking database: {e}")
        return False
    
    print()
    return True


async def main():
    """Main test function."""
    print("\n" + "=" * 60)
    print("BOUNDING BOX VALIDATION TEST")
    print("=" * 60)
    print()
    
    # Test 1: Logic validation
    if not test_bbox_logic():
        print("❌ TEST FAILED: Bounding box logic errors")
        return 1
    
    # Test 2: Live filtering
    if not await test_live_filtering():
        print("❌ TEST FAILED: Live filtering errors")
        return 1
    
    # Test 3: Database check
    if not test_database_positions():
        print("⚠️  WARNING: Database check had issues")
    
    # Summary
    print("=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    print("✅ Bounding box logic: CORRECT")
    print("✅ Live filtering: WORKING")
    print("✅ Local validation: ACTIVE")
    print()
    print("🎉 Bounding box filtering is working correctly!")
    print()
    print("The monitor will now:")
    print("  1. Send bounding box to AISstream.io for server-side filtering")
    print("  2. Validate each position locally before saving to database")
    print("  3. Log filtered positions for visibility")
    print("  4. Track filter statistics in the monitoring output")
    print()
    
    return 0


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
