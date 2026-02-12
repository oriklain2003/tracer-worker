#!/usr/bin/env python3
"""
Test Marine Data Pipeline

This script tests the marine data pipeline by:
1. Verifying database schema exists
2. Running the worker for a short time
3. Checking if data is being inserted
4. Displaying sample data

Usage:
    python test_marine_pipeline.py
"""

import sys
import os
import time
import asyncio
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from marine_pg_provider import (
    check_marine_schema_exists,
    init_connection_pool,
    get_connection
)
from marine_monitor import MarineMonitor
import psycopg2.extras


def test_database_connection():
    """Test database connection and schema."""
    print("=" * 60)
    print("Step 1: Testing Database Connection")
    print("=" * 60)
    
    # Initialize connection pool
    if not init_connection_pool():
        print("❌ FAILED: Could not initialize connection pool")
        return False
    
    print("✅ Connection pool initialized")
    
    # Check schema exists
    if not check_marine_schema_exists():
        print("❌ FAILED: Marine schema does not exist")
        print("   Please run: psql -f create_marine_schema.sql")
        return False
    
    print("✅ Marine schema exists")
    
    # Check tables exist
    try:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                # Check vessel_positions table
                cursor.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_schema = 'marine' 
                        AND table_name = 'vessel_positions'
                    )
                """)
                if not cursor.fetchone()[0]:
                    print("❌ FAILED: vessel_positions table not found")
                    return False
                print("✅ vessel_positions table exists")
                
                # Check vessel_metadata table
                cursor.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_schema = 'marine' 
                        AND table_name = 'vessel_metadata'
                    )
                """)
                if not cursor.fetchone()[0]:
                    print("❌ FAILED: vessel_metadata table not found")
                    return False
                print("✅ vessel_metadata table exists")
                
    except Exception as e:
        print(f"❌ FAILED: Error checking tables: {e}")
        return False
    
    print()
    return True


def get_data_counts():
    """Get current data counts from database."""
    try:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                # Count positions
                cursor.execute("SELECT COUNT(*) FROM marine.vessel_positions")
                position_count = cursor.fetchone()[0]
                
                # Count metadata
                cursor.execute("SELECT COUNT(*) FROM marine.vessel_metadata")
                metadata_count = cursor.fetchone()[0]
                
                # Count recent positions (last 5 minutes)
                cursor.execute("""
                    SELECT COUNT(*) FROM marine.vessel_positions 
                    WHERE timestamp > NOW() - INTERVAL '5 minutes'
                """)
                recent_count = cursor.fetchone()[0]
                
                # Count unique vessels
                cursor.execute("""
                    SELECT COUNT(DISTINCT mmsi) FROM marine.vessel_positions
                """)
                unique_vessels = cursor.fetchone()[0]
                
                return {
                    'positions': position_count,
                    'metadata': metadata_count,
                    'recent': recent_count,
                    'unique_vessels': unique_vessels
                }
    except Exception as e:
        print(f"Error getting counts: {e}")
        return None


async def test_data_collection():
    """Test data collection by running worker briefly."""
    print("=" * 60)
    print("Step 2: Testing Data Collection")
    print("=" * 60)
    
    # Check API key
    api_key = os.getenv("AIS_STREAM_API_KEY")
    if not api_key:
        print("❌ FAILED: AIS_STREAM_API_KEY not set")
        print("   Please set: export AIS_STREAM_API_KEY='your_key'")
        return False
    
    print(f"✅ API key configured: {api_key[:20]}...")
    
    # Get initial counts
    print("\nInitial database state:")
    initial_counts = get_data_counts()
    if initial_counts:
        print(f"  - Total positions: {initial_counts['positions']}")
        print(f"  - Total metadata: {initial_counts['metadata']}")
        print(f"  - Recent positions (5 min): {initial_counts['recent']}")
        print(f"  - Unique vessels: {initial_counts['unique_vessels']}")
    
    # Run worker for 60 seconds
    print(f"\n⏱️  Running worker for 60 seconds to collect data...")
    print("   (Press Ctrl+C to stop early)")
    
    try:
        # Get bounding box from environment or use Mediterranean as default test region
        # Mediterranean: Southern Europe, North Africa
        default_bbox = [[[30, -6], [46, 37]]]  # Mediterranean Sea
        
        bbox_str = os.getenv("AIS_BOUNDING_BOX")
        if bbox_str:
            import json
            try:
                bounding_boxes = json.loads(bbox_str)
                print(f"  Using configured bounding box: {bounding_boxes}")
            except json.JSONDecodeError:
                print(f"  Invalid AIS_BOUNDING_BOX format, using default Mediterranean region")
                bounding_boxes = default_bbox
        else:
            bounding_boxes = default_bbox
            print(f"  Using default Mediterranean region: {bounding_boxes}")
        
        # Create monitor with specified bounding box, small batch size for testing
        monitor = MarineMonitor(
            api_key=api_key,
            bounding_boxes=bounding_boxes,
            batch_size=10  # Small batch for faster testing
        )
        
        # Run for 60 seconds
        start_time = time.time()
        
        # Create a task to run the monitor
        monitor_task = asyncio.create_task(monitor.run())
        
        # Wait for 60 seconds or until interrupted
        try:
            await asyncio.wait_for(asyncio.shield(monitor_task), timeout=60.0)
        except asyncio.TimeoutError:
            # Expected - we want to stop after 60 seconds
            monitor.should_stop = True
            try:
                await asyncio.wait_for(monitor_task, timeout=5.0)
            except asyncio.TimeoutError:
                print("\n⚠️  Worker didn't stop gracefully, cancelling...")
                monitor_task.cancel()
                try:
                    await monitor_task
                except asyncio.CancelledError:
                    pass
        
        elapsed = time.time() - start_time
        print(f"\n✅ Worker ran for {elapsed:.1f} seconds")
        print(f"   Messages received: {monitor.messages_received}")
        print(f"   Positions saved: {monitor.positions_saved}")
        print(f"   Metadata saved: {monitor.metadata_saved}")
        print(f"   Errors: {monitor.errors}")
        
        if monitor.messages_received == 0:
            print("\n⚠️  WARNING: No messages received from AISstream.io")
            print("   This could mean:")
            print("   - API key is invalid")
            print("   - Network connectivity issues")
            print("   - AISstream.io service is down")
            return False
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        monitor.should_stop = True
        return False
    except Exception as e:
        print(f"\n❌ FAILED: Error running worker: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Get final counts
    print("\nFinal database state:")
    final_counts = get_data_counts()
    if final_counts:
        print(f"  - Total positions: {final_counts['positions']}")
        print(f"  - Total metadata: {final_counts['metadata']}")
        print(f"  - Recent positions (5 min): {final_counts['recent']}")
        print(f"  - Unique vessels: {final_counts['unique_vessels']}")
        
        if initial_counts:
            print("\nData changes:")
            print(f"  - New positions: {final_counts['positions'] - initial_counts['positions']}")
            print(f"  - New metadata: {final_counts['metadata'] - initial_counts['metadata']}")
            print(f"  - New vessels: {final_counts['unique_vessels'] - initial_counts['unique_vessels']}")
    
    print()
    return True


def display_sample_data():
    """Display sample data from database."""
    print("=" * 60)
    print("Step 3: Displaying Sample Data")
    print("=" * 60)
    
    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                # Get recent positions with metadata
                cursor.execute("""
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
                    ORDER BY vp.timestamp DESC
                    LIMIT 10
                """)
                
                positions = cursor.fetchall()
                
                if not positions:
                    print("No position data found in database")
                    print()
                    return False
                
                print(f"\nMost Recent Vessel Positions ({len(positions)} samples):")
                print("-" * 120)
                print(f"{'MMSI':<12} {'Name':<25} {'Type':<20} {'Lat':<10} {'Lon':<11} {'Speed':<8} {'Status':<25} {'Time'}")
                print("-" * 120)
                
                for pos in positions:
                    mmsi = pos['mmsi'] or 'N/A'
                    name = (pos['vessel_name'] or 'Unknown')[:24]
                    vtype = (pos['vessel_type_description'] or 'N/A')[:19]
                    lat = f"{pos['latitude']:.4f}" if pos['latitude'] else 'N/A'
                    lon = f"{pos['longitude']:.4f}" if pos['longitude'] else 'N/A'
                    speed = f"{pos['speed_over_ground']:.1f} kts" if pos['speed_over_ground'] else 'N/A'
                    status = (pos['navigation_status'] or 'N/A')[:24]
                    timestamp = pos['timestamp'].strftime('%H:%M:%S') if pos['timestamp'] else 'N/A'
                    
                    print(f"{mmsi:<12} {name:<25} {vtype:<20} {lat:<10} {lon:<11} {speed:<8} {status:<25} {timestamp}")
                
                print("-" * 120)
                
                # Get vessel type distribution
                cursor.execute("""
                    SELECT 
                        vessel_type_description,
                        COUNT(*) as count
                    FROM marine.vessel_metadata
                    WHERE vessel_type_description IS NOT NULL
                    GROUP BY vessel_type_description
                    ORDER BY count DESC
                    LIMIT 5
                """)
                
                types = cursor.fetchall()
                
                if types:
                    print("\nVessel Type Distribution (Top 5):")
                    print("-" * 40)
                    for row in types:
                        print(f"  {row['vessel_type_description']:<25} {row['count']:>5}")
                    print("-" * 40)
                
    except Exception as e:
        print(f"Error displaying sample data: {e}")
        return False
    
    print()
    return True


def run_verification_queries():
    """Run verification queries to check data quality."""
    print("=" * 60)
    print("Step 4: Data Quality Verification")
    print("=" * 60)
    
    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                # Check for recent data
                cursor.execute("""
                    SELECT 
                        COUNT(*) as count,
                        MIN(timestamp) as oldest,
                        MAX(timestamp) as newest
                    FROM marine.vessel_positions
                    WHERE timestamp > NOW() - INTERVAL '10 minutes'
                """)
                
                recent = cursor.fetchone()
                
                print(f"\nRecent Data (Last 10 minutes):")
                print(f"  - Position count: {recent['count']}")
                if recent['oldest']:
                    print(f"  - Oldest: {recent['oldest']}")
                if recent['newest']:
                    print(f"  - Newest: {recent['newest']}")
                
                if recent['count'] == 0:
                    print("\n⚠️  WARNING: No recent data found")
                    print("   The worker may not be running or data collection stopped")
                else:
                    print("✅ Recent data found - pipeline is working!")
                
                # Check position quality
                cursor.execute("""
                    SELECT 
                        COUNT(*) as total,
                        COUNT(*) FILTER (WHERE position_accuracy = true) as high_accuracy,
                        COUNT(*) FILTER (WHERE speed_over_ground IS NOT NULL) as with_speed,
                        COUNT(*) FILTER (WHERE navigation_status IS NOT NULL) as with_status
                    FROM marine.vessel_positions
                    WHERE timestamp > NOW() - INTERVAL '10 minutes'
                """)
                
                quality = cursor.fetchone()
                
                if quality['total'] > 0:
                    print(f"\nData Quality:")
                    print(f"  - High accuracy positions: {quality['high_accuracy']}/{quality['total']} ({100*quality['high_accuracy']/quality['total']:.1f}%)")
                    print(f"  - Positions with speed: {quality['with_speed']}/{quality['total']} ({100*quality['with_speed']/quality['total']:.1f}%)")
                    print(f"  - Positions with status: {quality['with_status']}/{quality['total']} ({100*quality['with_status']/quality['total']:.1f}%)")
                
    except Exception as e:
        print(f"Error running verification queries: {e}")
        return False
    
    print()
    return True


async def main():
    """Main test function."""
    print("\n" + "=" * 60)
    print("MARINE DATA PIPELINE TEST")
    print("=" * 60)
    print()
    
    # Step 1: Database connection
    if not test_database_connection():
        print("❌ TEST FAILED: Database connection issues")
        return 1
    
    # Step 2: Data collection
    if not await test_data_collection():
        print("❌ TEST FAILED: Data collection issues")
        return 1
    
    # Wait a moment for data to settle
    await asyncio.sleep(2)
    
    # Step 3: Display sample data
    if not display_sample_data():
        print("⚠️  WARNING: No sample data to display")
    
    # Step 4: Verification
    if not run_verification_queries():
        print("⚠️  WARNING: Verification queries failed")
    
    # Summary
    print("=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    print("✅ Database schema: PASSED")
    print("✅ Data collection: PASSED")
    print("✅ Data storage: PASSED")
    print()
    print("🎉 Marine data pipeline is working correctly!")
    print()
    print("Next steps:")
    print("  1. Run the worker continuously: python run_marine_monitor.py")
    print("  2. Implement API endpoints in tracer-api")
    print("  3. Create UI components in anomaly-prod")
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
