"""
Helper script to find good start points for replay.

Usage:
    python find_start_point.py 3cf959dd
    python find_start_point.py 3cf959dd --schema feedback
"""

import sys
import argparse
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent))

from pg_provider import get_connection, init_connection_pool
from datetime import datetime

def find_start_points(flight_id: str, schema: str = 'feedback'):
    """Find suggested start points for a flight."""
    init_connection_pool()
    
    with get_connection() as conn:
        with conn.cursor() as c:
            # Try different table names
            for table in ['flight_tracks', 'anomaly_tracks', 'normal_tracks']:
                try:
                    c.execute(f'''
                        SELECT 
                            timestamp,
                            lat,
                            lon,
                            alt
                        FROM {schema}.{table}
                        WHERE flight_id = %s
                        ORDER BY timestamp ASC
                    ''', (flight_id,))
                    
                    rows = c.fetchall()
                    
                    if rows:
                        print(f"Found {len(rows)} points in {schema}.{table}")
                        print("="*70)
                        
                        total = len(rows)
                        
                        # Calculate suggested start points
                        percentages = [25, 50, 75, 90, 95]
                        
                        print(f"\nSuggested start points for flight {flight_id}:")
                        print(f"Total points: {total}")
                        print()
                        
                        for pct in percentages:
                            point_num = int(total * pct / 100)
                            if point_num < total:
                                ts = rows[point_num][0]
                                lat = rows[point_num][1]
                                lon = rows[point_num][2]
                                alt = rows[point_num][3]
                                ts_str = datetime.fromtimestamp(ts).strftime('%H:%M:%S')
                                
                                print(f"  {pct:3}%: Point #{point_num:4} | {ts_str} | "
                                      f"Lat {lat:.4f}, Lon {lon:.4f}, Alt {alt:.0f}ft")
                        
                        # Last N points
                        for n in [100, 50, 20]:
                            if total > n:
                                point_num = total - n
                                ts = rows[point_num][0]
                                ts_str = datetime.fromtimestamp(ts).strftime('%H:%M:%S')
                                print(f"  Last {n:3} pts: Point #{point_num:4} | {ts_str}")
                        
                        print("\n" + "="*70)
                        print("\nExample commands:")
                        print(f"  python replay_flight_to_live.py {flight_id} --start-point 645  # 50%")
                        print(f"  python replay_flight_to_live.py {flight_id} --start-point 1161  # 90%")
                        print(f"  python replay_flight_to_live.py {flight_id} --start-point {total - 100}  # Last 100")
                        
                        return
                        
                except Exception as e:
                    continue
            
            print(f"Flight {flight_id} not found in {schema} schema")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Find good start points for flight replay'
    )
    parser.add_argument('flight_id', help='Flight ID to analyze')
    parser.add_argument('--schema', default='feedback', help='Schema name (default: feedback)')
    
    args = parser.parse_args()
    find_start_points(args.flight_id, args.schema)
