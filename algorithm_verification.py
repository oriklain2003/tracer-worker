"""
Algorithm Verification Script

Re-analyzes flights from the research schema using the current AnomalyPipeline
and produces a before/after report showing which flights changed their anomaly
status or matched rules.

Two modes:
- random: Fast analysis of a random subset of flights (default 100)
- full: Analysis of all flights within a time range (default 7 days)

Usage:
    python algorithm_verification.py --mode random --count 100
    python algorithm_verification.py --mode full --days 7
    python algorithm_verification.py --mode random --count 50 --output report.json
"""

from __future__ import annotations

import sys
import json
import time
import logging
import argparse
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict

# Add root to path for imports
sys.path.append(str(Path(__file__).resolve().parent))

from anomaly_pipeline import AnomalyPipeline
from core.models import FlightTrack, TrackPoint, FlightMetadata
from pg_provider import get_connection, init_connection_pool

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class FlightComparison:
    """Results of comparing old vs new analysis for a single flight."""
    flight_id: str
    callsign: Optional[str]
    old_is_anomaly: bool
    new_is_anomaly: bool
    old_rules: List[str]
    new_rules: List[str]
    status_changed: bool
    rules_changed: bool
    change_type: str  # "normal_to_anomaly", "anomaly_to_normal", "rules_only", "no_change"


@dataclass
class VerificationReport:
    """Complete verification report with summary statistics."""
    total_flights: int
    total_changed: int
    normal_to_anomaly: int
    anomaly_to_normal: int
    rules_only_changed: int
    no_change: int
    changed_flights: List[FlightComparison]
    duration_seconds: float
    mode: str
    timestamp: str


def load_flights(mode: str, count: int, days: int, schema: str = 'research') -> List[Dict]:
    """
    Load flights from the database to analyze.
    
    Args:
        mode: 'random' or 'full'
        count: Number of flights for random mode
        days: Number of days to look back for full mode
        schema: Database schema (default: 'research')
    
    Returns:
        List of flight records with metadata and old report data
    """
    logger.info(f"Loading flights (mode={mode}, count={count}, days={days})...")
    
    with get_connection() as conn:
        with conn.cursor() as cursor:
            if mode == 'random':
                # Random sample of flights
                query = f"""
                    SELECT 
                        fm.flight_id,
                        fm.callsign,
                        fm.is_anomaly as old_is_anomaly,
                        fm.origin_airport,
                        fm.destination_airport,
                        ar.matched_rule_names as old_rule_names,
                        ar.matched_rule_ids as old_rule_ids
                    FROM {schema}.flight_metadata fm
                    LEFT JOIN {schema}.anomaly_reports ar ON fm.flight_id = ar.flight_id
                    WHERE fm.total_points >= 50
                    ORDER BY RANDOM()
                    LIMIT %s
                """
                cursor.execute(query, (count,))
            else:
                # Full mode: all flights from last N days
                cutoff_ts = int((datetime.now() - timedelta(days=days)).timestamp())
                query = f"""
                    SELECT 
                        fm.flight_id,
                        fm.callsign,
                        fm.is_anomaly as old_is_anomaly,
                        fm.origin_airport,
                        fm.destination_airport,
                        ar.matched_rule_names as old_rule_names,
                        ar.matched_rule_ids as old_rule_ids
                    FROM {schema}.flight_metadata fm
                    LEFT JOIN {schema}.anomaly_reports ar ON fm.flight_id = ar.flight_id
                    WHERE fm.first_seen_ts >= %s
                      AND fm.total_points >= 50
                    ORDER BY fm.first_seen_ts DESC
                """
                cursor.execute(query, (cutoff_ts,))
            
            rows = cursor.fetchall()
            
            flights = []
            for row in rows:
                flights.append({
                    'flight_id': row[0],
                    'callsign': row[1],
                    'old_is_anomaly': row[2] if row[2] is not None else False,
                    'origin_airport': row[3],
                    'destination_airport': row[4],
                    'old_rule_names': row[5] if row[5] else "",
                    'old_rule_ids': row[6] if row[6] else ""
                })
            
            logger.info(f"Loaded {len(flights)} flights to analyze")
            return flights


def load_flight_tracks(flight_id: str, was_anomaly: bool, schema: str = 'research') -> List[TrackPoint]:
    """
    Load track points for a flight from the appropriate table.
    
    Args:
        flight_id: Flight ID to load
        was_anomaly: Whether the flight was classified as anomaly (determines table)
        schema: Database schema (default: 'research')
    
    Returns:
        List of TrackPoint objects
    """
    # Determine which table to query based on old classification
    table = 'anomalies_tracks' if was_anomaly else 'normal_tracks'
    
    with get_connection() as conn:
        with conn.cursor() as cursor:
            query = f"""
                SELECT flight_id, timestamp, lat, lon, alt, gspeed, vspeed,
                       track, squawk, callsign, source
                FROM {schema}.{table}
                WHERE flight_id = %s
                ORDER BY timestamp ASC
            """
            cursor.execute(query, (flight_id,))
            rows = cursor.fetchall()
            
            if not rows:
                logger.warning(f"No track points found for {flight_id} in {schema}.{table}")
                return []
            
            points = []
            for row in rows:
                points.append(TrackPoint(
                    flight_id=row[0],
                    timestamp=int(row[1]),
                    lat=float(row[2]),
                    lon=float(row[3]),
                    alt=float(row[4]) if row[4] is not None else 0.0,
                    gspeed=float(row[5]) if row[5] is not None else None,
                    vspeed=float(row[6]) if row[6] is not None else None,
                    track=float(row[7]) if row[7] is not None else None,
                    squawk=str(row[8]) if row[8] is not None else None,
                    callsign=row[9],
                    source=row[10]
                ))
            
            return points


def reanalyze(pipeline: AnomalyPipeline, flight_id: str, points: List[TrackPoint], 
              origin: Optional[str], destination: Optional[str]) -> Dict:
    """
    Re-analyze a flight using the current pipeline.
    
    Args:
        pipeline: AnomalyPipeline instance
        flight_id: Flight ID
        points: List of TrackPoint objects
        origin: Origin airport code
        destination: Destination airport code
    
    Returns:
        Analysis report dictionary
    """
    if not points:
        return {
            "summary": {
                "is_anomaly": False,
                "triggers": [],
                "flight_id": flight_id,
                "status": "ERROR_NO_POINTS"
            }
        }
    
    # Build FlightTrack object
    flight = FlightTrack(flight_id=flight_id, points=points)
    
    # Build FlightMetadata object
    metadata = FlightMetadata(
        origin=origin,
        planned_destination=destination,
        planned_route=None
    )
    
    # Run analysis
    try:
        report = pipeline.analyze(flight, metadata=metadata)
        return report
    except Exception as e:
        logger.error(f"Error analyzing {flight_id}: {e}")
        return {
            "summary": {
                "is_anomaly": False,
                "triggers": [],
                "flight_id": flight_id,
                "status": f"ERROR: {str(e)}"
            }
        }


def compare(flight_record: Dict, new_report: Dict) -> FlightComparison:
    """
    Compare old and new analysis results.
    
    Args:
        flight_record: Original flight record from database
        new_report: New analysis report from pipeline
    
    Returns:
        FlightComparison object with detailed comparison
    """
    flight_id = flight_record['flight_id']
    callsign = flight_record['callsign']
    old_is_anomaly = flight_record['old_is_anomaly']
    
    # Parse old rules
    old_rule_names = flight_record.get('old_rule_names', '') or ''
    old_rules = [r.strip() for r in old_rule_names.split(',') if r.strip()]
    
    # Parse new results
    new_is_anomaly = new_report.get('summary', {}).get('is_anomaly', False)
    
    # Extract new rules from layer_1_rules triggers
    new_rules = []
    rules_layer = new_report.get('layer_1_rules', {})
    if rules_layer.get('status') == 'ANOMALY':
        new_rules = rules_layer.get('triggers', [])
    
    # Determine what changed
    status_changed = old_is_anomaly != new_is_anomaly
    rules_changed = set(old_rules) != set(new_rules)
    
    # Categorize change type
    if status_changed:
        if old_is_anomaly and not new_is_anomaly:
            change_type = "anomaly_to_normal"
        else:
            change_type = "normal_to_anomaly"
    elif rules_changed:
        change_type = "rules_only"
    else:
        change_type = "no_change"
    
    return FlightComparison(
        flight_id=flight_id,
        callsign=callsign,
        old_is_anomaly=old_is_anomaly,
        new_is_anomaly=new_is_anomaly,
        old_rules=old_rules,
        new_rules=new_rules,
        status_changed=status_changed,
        rules_changed=rules_changed,
        change_type=change_type
    )


def print_report(report: VerificationReport):
    """
    Print a formatted verification report to console.
    
    Args:
        report: VerificationReport object with results
    """
    print("\n" + "="*80)
    print("ALGORITHM VERIFICATION REPORT")
    print("="*80)
    print(f"Timestamp: {report.timestamp}")
    print(f"Mode: {report.mode}")
    print(f"Duration: {report.duration_seconds:.2f} seconds")
    print(f"Total Flights Analyzed: {report.total_flights}")
    print(f"Total Changed: {report.total_changed}")
    print("-"*80)
    
    # Summary statistics
    print("\nCHANGE BREAKDOWN:")
    print(f"  Normal → Anomaly:     {report.normal_to_anomaly:>5}")
    print(f"  Anomaly → Normal:     {report.anomaly_to_normal:>5}")
    print(f"  Rules Changed Only:   {report.rules_only_changed:>5}")
    print(f"  No Change:            {report.no_change:>5}")
    
    if report.changed_flights:
        print("\n" + "-"*80)
        print("CHANGED FLIGHTS:")
        print("-"*80)
        
        # Print header
        print(f"{'Flight ID':<25} {'Callsign':<12} {'Old Status':<12} {'New Status':<12} {'Change Type':<20}")
        print("-"*80)
        
        # Print each changed flight
        for comp in report.changed_flights:
            old_status = "ANOMALY" if comp.old_is_anomaly else "NORMAL"
            new_status = "ANOMALY" if comp.new_is_anomaly else "NORMAL"
            callsign = comp.callsign or "N/A"
            
            print(f"{comp.flight_id:<25} {callsign:<12} {old_status:<12} {new_status:<12} {comp.change_type:<20}")
            
            # Show rule changes if applicable
            if comp.old_rules or comp.new_rules:
                old_rules_str = ", ".join(comp.old_rules) if comp.old_rules else "None"
                new_rules_str = ", ".join(comp.new_rules) if comp.new_rules else "None"
                print(f"  Old Rules: {old_rules_str}")
                print(f"  New Rules: {new_rules_str}")
                print()
    else:
        print("\n✓ No changes detected - all flights have consistent results!")
    
    print("="*80 + "\n")


def save_report_json(report: VerificationReport, output_path: str):
    """
    Save verification report to JSON file.
    
    Args:
        report: VerificationReport object
        output_path: Path to output JSON file
    """
    # Convert to dict for JSON serialization
    report_dict = asdict(report)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(report_dict, f, indent=2)
    
    logger.info(f"Report saved to {output_path}")


def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(
        description='Algorithm Verification Script - Re-analyze flights to detect changes'
    )
    parser.add_argument(
        '--mode',
        choices=['random', 'full'],
        default='random',
        help='Analysis mode: random (subset) or full (all flights in range)'
    )
    parser.add_argument(
        '--count',
        type=int,
        default=100,
        help='Number of flights for random mode (default: 100)'
    )
    parser.add_argument(
        '--days',
        type=int,
        default=7,
        help='Number of days to look back for full mode (default: 7)'
    )
    parser.add_argument(
        '--output',
        type=str,
        help='Optional output file path for JSON report'
    )
    parser.add_argument(
        '--schema',
        type=str,
        default='research',
        help='Database schema to use (default: research)'
    )
    
    args = parser.parse_args()
    
    start_time = time.time()
    
    # Initialize database connection pool
    logger.info("Initializing database connection...")
    if not init_connection_pool():
        logger.error("Failed to initialize database connection pool")
        sys.exit(1)
    
    # Initialize anomaly pipeline
    logger.info("Initializing anomaly pipeline...")
    pipeline = AnomalyPipeline(use_postgres=True)
    
    # Load flights to analyze
    flights = load_flights(args.mode, args.count, args.days, args.schema)
    
    if not flights:
        logger.error("No flights found to analyze")
        sys.exit(1)
    
    # Process each flight
    comparisons = []
    changed_count = 0
    normal_to_anomaly = 0
    anomaly_to_normal = 0
    rules_only = 0
    no_change = 0
    
    logger.info(f"Starting analysis of {len(flights)} flights...")
    
    for i, flight_record in enumerate(flights, 1):
        flight_id = flight_record['flight_id']
        
        if i % 10 == 0:
            logger.info(f"Progress: {i}/{len(flights)} flights analyzed...")
        
        # Load tracks
        points = load_flight_tracks(
            flight_id,
            flight_record['old_is_anomaly'],
            args.schema
        )
        
        if not points:
            logger.warning(f"Skipping {flight_id} - no track points found")
            continue
        
        # Re-analyze
        new_report = reanalyze(
            pipeline,
            flight_id,
            points,
            flight_record['origin_airport'],
            flight_record['destination_airport']
        )
        
        # Compare results
        comparison = compare(flight_record, new_report)
        comparisons.append(comparison)
        
        # Update statistics
        if comparison.change_type == "normal_to_anomaly":
            changed_count += 1
            normal_to_anomaly += 1
        elif comparison.change_type == "anomaly_to_normal":
            changed_count += 1
            anomaly_to_normal += 1
        elif comparison.change_type == "rules_only":
            changed_count += 1
            rules_only += 1
        else:
            no_change += 1
    
    duration = time.time() - start_time
    
    # Build report
    changed_flights = [c for c in comparisons if c.change_type != "no_change"]
    
    report = VerificationReport(
        total_flights=len(comparisons),
        total_changed=changed_count,
        normal_to_anomaly=normal_to_anomaly,
        anomaly_to_normal=anomaly_to_normal,
        rules_only_changed=rules_only,
        no_change=no_change,
        changed_flights=changed_flights,
        duration_seconds=duration,
        mode=args.mode,
        timestamp=datetime.now().isoformat()
    )
    
    # Print report
    print_report(report)
    
    # Save to file if requested
    if args.output:
        save_report_json(report, args.output)
    
    logger.info("Verification complete!")


if __name__ == "__main__":
    main()
