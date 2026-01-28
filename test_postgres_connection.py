#!/usr/bin/env python3
"""
PostgreSQL Connection Test Script

Verifies that PostgreSQL is properly configured for the monitor.
Run this before starting monitor.py to catch configuration issues.
"""

import sys
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

def test_imports():
    """Test that required modules can be imported."""
    print("1. Testing imports...")
    try:
        import psycopg2
        print("   ✓ psycopg2 installed")
    except ImportError as e:
        print(f"   ✗ psycopg2 not found: {e}")
        print("   → Install with: pip install psycopg2-binary")
        return False
    
    try:
        from pg_provider import (
            init_connection_pool,
            test_connection,
            check_schema_exists
        )
        print("   ✓ pg_provider module loaded")
    except ImportError as e:
        print(f"   ✗ pg_provider import failed: {e}")
        return False
    
    try:
        from core.pg_db import PgFlightRepository, PgDbConfig
        print("   ✓ pg_db module loaded")
    except ImportError as e:
        print(f"   ✗ pg_db import failed: {e}")
        return False
    
    return True


def test_connection_pool():
    """Test PostgreSQL connection pool initialization."""
    print("\n2. Testing connection pool...")
    try:
        from pg_provider import init_connection_pool, test_connection
        
        if not init_connection_pool():
            print("   ✗ Failed to initialize connection pool")
            return False
        
        print("   ✓ Connection pool initialized")
        
        if not test_connection():
            print("   ✗ Connection test failed")
            return False
        
        print("   ✓ Connection test successful")
        return True
        
    except Exception as e:
        print(f"   ✗ Error: {e}")
        return False


def test_schema():
    """Test that the 'live' schema exists."""
    print("\n3. Testing schema existence...")
    try:
        from pg_provider import check_schema_exists
        
        if not check_schema_exists('live'):
            print("   ✗ Schema 'live' does not exist")
            print("   → Run the migration script first: python migrate_sqlite_to_postgres.py")
            return False
        
        print("   ✓ Schema 'live' exists")
        return True
        
    except Exception as e:
        print(f"   ✗ Error: {e}")
        return False


def test_tables():
    """Test that required tables exist in the live schema."""
    print("\n4. Testing table existence...")
    try:
        from pg_provider import get_connection
        
        required_tables = ['flight_metadata', 'normal_tracks', 'anomaly_reports']
        
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'live'
                    AND table_type = 'BASE TABLE'
                """)
                existing_tables = {row[0] for row in cursor.fetchall()}
        
        all_found = True
        for table in required_tables:
            if table in existing_tables:
                print(f"   ✓ Table 'live.{table}' exists")
            else:
                print(f"   ✗ Table 'live.{table}' missing")
                all_found = False
        
        return all_found
        
    except Exception as e:
        print(f"   ✗ Error: {e}")
        return False


def test_repository():
    """Test PostgreSQL FlightRepository."""
    print("\n5. Testing FlightRepository...")
    try:
        from core.pg_db import PgFlightRepository, PgDbConfig
        
        repo = PgFlightRepository(PgDbConfig(
            dsn="postgresql://postgres:Warqi4-sywsow-zozfyc@tracer-db.cb80eku2emy0.eu-north-1.rds.amazonaws.com:5432/tracer",
            schema="live",
            table="normal_tracks"
        ))
        print("   ✓ Repository initialized")
        
        # Try a simple query
        from pg_provider import get_connection
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) FROM live.normal_tracks")
                count = cursor.fetchone()[0]
                print(f"   ✓ Found {count:,} track points in database")
        
        return True
        
    except Exception as e:
        print(f"   ✗ Error: {e}")
        return False


def test_write_permissions():
    """Test that we can write to the database."""
    print("\n6. Testing write permissions...")
    try:
        from pg_provider import get_connection
        import time
        
        test_flight_id = f"TEST_{int(time.time())}"
        
        with get_connection() as conn:
            with conn.cursor() as cursor:
                # Try to insert a test record
                cursor.execute("""
                    INSERT INTO live.normal_tracks 
                    (flight_id, timestamp, lat, lon, alt, gspeed, vspeed, track, squawk, callsign, source)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT DO NOTHING
                """, (test_flight_id, int(time.time()), 32.0, 34.8, 1000, 250, 0, 90, None, "TEST", "test"))
                
                # Delete the test record
                cursor.execute("DELETE FROM live.normal_tracks WHERE flight_id = %s", (test_flight_id,))
                conn.commit()
        
        print("   ✓ Write permissions verified")
        return True
        
    except Exception as e:
        print(f"   ✗ Error: {e}")
        print("   → Check database user permissions")
        return False


def main():
    """Run all tests."""
    print("="*60)
    print("PostgreSQL Monitor Connection Test")
    print("="*60)
    
    tests = [
        test_imports,
        test_connection_pool,
        test_schema,
        test_tables,
        test_repository,
        test_write_permissions
    ]
    
    results = []
    for test in tests:
        try:
            results.append(test())
        except Exception as e:
            print(f"\n   ✗ Unexpected error: {e}")
            results.append(False)
    
    print("\n" + "="*60)
    print("Test Summary")
    print("="*60)
    
    passed = sum(results)
    total = len(results)
    
    print(f"Passed: {passed}/{total}")
    
    if all(results):
        print("\n✓ All tests passed! Monitor is ready to run.")
        print("\nStart the monitor with: python monitor.py")
        return 0
    else:
        print("\n✗ Some tests failed. Please fix the issues above before running the monitor.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
