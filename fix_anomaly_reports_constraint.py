#!/usr/bin/env python3
"""
Fix anomaly_reports table to ensure UNIQUE constraint exists on flight_id.
"""

import psycopg2
from psycopg2 import sql

PG_DSN = "postgresql://postgres:Warqi4-sywsow-zozfyc@tracer-db.cb80eku2emy0.eu-north-1.rds.amazonaws.com:5432/tracer"

def check_and_fix_constraint():
    """Check if UNIQUE constraint exists on flight_id, add if missing."""
    conn = psycopg2.connect(PG_DSN)
    try:
        with conn.cursor() as cursor:
            # Check table structure
            cursor.execute("""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_schema = 'live' 
                AND table_name = 'anomaly_reports'
                ORDER BY ordinal_position
            """)
            columns = cursor.fetchall()
            
            print("Current columns in live.anomaly_reports:")
            for col in columns:
                print(f"  - {col[0]} ({col[1]})")
            
            # Check if UNIQUE constraint exists on flight_id
            cursor.execute("""
                SELECT constraint_name, constraint_type
                FROM information_schema.table_constraints
                WHERE table_schema = 'live'
                AND table_name = 'anomaly_reports'
                AND constraint_type = 'UNIQUE'
            """)
            constraints = cursor.fetchall()
            
            print("\nCurrent UNIQUE constraints:")
            for constraint in constraints:
                print(f"  - {constraint[0]} ({constraint[1]})")
            
            # Check specifically for flight_id constraint
            cursor.execute("""
                SELECT 
                    tc.constraint_name,
                    kcu.column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                    ON tc.constraint_name = kcu.constraint_name
                    AND tc.table_schema = kcu.table_schema
                WHERE tc.table_schema = 'live'
                AND tc.table_name = 'anomaly_reports'
                AND tc.constraint_type = 'UNIQUE'
                AND kcu.column_name = 'flight_id'
            """)
            flight_id_constraint = cursor.fetchone()
            
            if flight_id_constraint:
                print(f"\n[OK] UNIQUE constraint on flight_id already exists: {flight_id_constraint[0]}")
            else:
                print("\n[MISSING] UNIQUE constraint on flight_id is missing")
                print("  Creating constraint...")
                
                try:
                    cursor.execute("""
                        ALTER TABLE live.anomaly_reports 
                        ADD CONSTRAINT anomaly_reports_flight_id_unique 
                        UNIQUE (flight_id)
                    """)
                    conn.commit()
                    print("  [OK] UNIQUE constraint created successfully!")
                except Exception as e:
                    conn.rollback()
                    print(f"  [ERROR] Failed to create constraint: {e}")
                    
                    # Try alternative approach - check if there are duplicate flight_ids
                    cursor.execute("""
                        SELECT flight_id, COUNT(*) as cnt 
                        FROM live.anomaly_reports 
                        GROUP BY flight_id 
                        HAVING COUNT(*) > 1
                    """)
                    duplicates = cursor.fetchall()
                    
                    if duplicates:
                        print(f"\n  Found {len(duplicates)} duplicate flight_ids:")
                        for dup in duplicates[:5]:  # Show first 5
                            print(f"    - {dup[0]}: {dup[1]} occurrences")
                        
                        print("\n  Cleaning up duplicates (keeping most recent)...")
                        cursor.execute("""
                            DELETE FROM live.anomaly_reports a
                            USING live.anomaly_reports b
                            WHERE a.id < b.id 
                            AND a.flight_id = b.flight_id
                        """)
                        deleted = cursor.rowcount
                        conn.commit()
                        print(f"  [OK] Deleted {deleted} duplicate rows")
                        
                        # Try again to add constraint
                        print("  Retrying constraint creation...")
                        cursor.execute("""
                            ALTER TABLE live.anomaly_reports 
                            ADD CONSTRAINT anomaly_reports_flight_id_unique 
                            UNIQUE (flight_id)
                        """)
                        conn.commit()
                        print("  [OK] UNIQUE constraint created successfully!")
            
    finally:
        conn.close()

if __name__ == "__main__":
    print("Checking and fixing anomaly_reports table...\n")
    check_and_fix_constraint()
    print("\nDone!")
