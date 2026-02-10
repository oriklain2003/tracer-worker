"""
Flight Simulation Script - Live Monitoring Replay

Simulates live monitoring by replaying flights from the feedback schema point-by-point
through the anomaly pipeline to determine exactly when and which detections trigger.

Inspired by analyze_deviation_timing.py but covers all 6 detection layers.
"""

from __future__ import annotations

import sys
import json
import logging
import argparse
from pathlib import Path
from datetime import datetime
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
class TriggerEvent:
    """Records when a detection layer triggers."""
    point_number: int
    timestamp: int
    timestamp_str: str
    layer_name: str
    detector_type: str
    is_anomaly: bool
    details: Dict
    matched_rules: List[str]
    confidence_score: float
    position: Dict  # lat, lon, alt


@dataclass
class SimulationResults:
    """Complete simulation results for report generation."""
    flight_id: str
    callsign: Optional[str]
    origin: Optional[str]
    destination: Optional[str]
    total_points: int
    analysis_interval: int
    timeline: List[TriggerEvent]
    first_anomaly_point: Optional[int]
    first_anomaly_timestamp: Optional[int]
    layers_triggered: List[str]
    total_anomaly_points: int


def load_flight_from_feedback(flight_id: str) -> Tuple[List[Dict], Dict]:
    """
    Load flight tracks and metadata from feedback schema.
    
    Args:
        flight_id: Flight ID to load
        
    Returns:
        (track_points, metadata_dict)
    """
    logger.info(f"Loading flight {flight_id} from feedback schema...")
    
    with get_connection() as conn:
        with conn.cursor() as cursor:
            # Load track points from flight_tracks
            cursor.execute("""
                SELECT flight_id, timestamp, lat, lon, alt, gspeed, vspeed, 
                       track, squawk, callsign, source
                FROM feedback.flight_tracks
                WHERE flight_id = %s
                ORDER BY timestamp ASC
            """, (flight_id,))
            
            rows = cursor.fetchall()
            
            if not rows:
                logger.error(f"No track points found for flight {flight_id} in feedback.flight_tracks")
                return [], {}
            
            points = []
            for row in rows:
                points.append({
                    'flight_id': row[0],
                    'timestamp': int(row[1]),
                    'lat': float(row[2]),
                    'lon': float(row[3]),
                    'alt': float(row[4]) if row[4] is not None else 0.0,
                    'gspeed': float(row[5]) if row[5] is not None else None,
                    'vspeed': float(row[6]) if row[6] is not None else None,
                    'track': float(row[7]) if row[7] is not None else None,
                    'squawk': str(row[8]) if row[8] is not None else None,
                    'callsign': row[9],
                    'source': row[10]
                })
            
            logger.info(f"Loaded {len(points)} track points")
            
            # Load metadata
            cursor.execute("""
                SELECT origin_airport, destination_airport, callsign
                FROM feedback.flight_metadata
                WHERE flight_id = %s
                LIMIT 1
            """, (flight_id,))
            
            meta_row = cursor.fetchone()
            
            if meta_row:
                metadata = {
                    'origin_airport': meta_row[0],
                    'destination_airport': meta_row[1],
                    'callsign': meta_row[2]
                }
                logger.info(f"Loaded metadata: {metadata}")
            else:
                logger.warning(f"No metadata found for flight {flight_id}")
                metadata = {
                    'origin_airport': None,
                    'destination_airport': None,
                    'callsign': None
                }
            
            return points, metadata


def extract_layer_results(report: Dict, point_num: int, timestamp: int, position: Dict) -> List[TriggerEvent]:
    """
    Extract trigger events from all layers in the pipeline report.
    
    Args:
        report: Full pipeline report
        point_num: Current point number
        timestamp: Current timestamp
        position: Current position (lat, lon, alt)
        
    Returns:
        List of TriggerEvent objects
    """
    events = []
    summary = report.get("summary", {})
    confidence_score = summary.get("confidence_score", 0.0)
    timestamp_str = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
    
    # Layer 1: Rules Engine
    rules_layer = report.get("layer_1_rules", {})
    if rules_layer.get("status") == "ANOMALY":
        matched_rules = []
        rule_report = rules_layer.get("report", {})
        for rule in rule_report.get("matched_rules", []):
            matched_rules.append(f"{rule.get('id')}: {rule.get('name')}")
        
        events.append(TriggerEvent(
            point_number=point_num,
            timestamp=timestamp,
            timestamp_str=timestamp_str,
            layer_name="layer_1_rules",
            detector_type="Rules Engine",
            is_anomaly=True,
            details=rules_layer,
            matched_rules=matched_rules,
            confidence_score=confidence_score,
            position=position
        ))
    
    # Layer 2: XGBoost
    xgb_layer = report.get("layer_2_xgboost", {})
    if xgb_layer.get("is_anomaly"):
        events.append(TriggerEvent(
            point_number=point_num,
            timestamp=timestamp,
            timestamp_str=timestamp_str,
            layer_name="layer_2_xgboost",
            detector_type="XGBoost",
            is_anomaly=True,
            details=xgb_layer,
            matched_rules=[],
            confidence_score=confidence_score,
            position=position
        ))
    
    # Layer 3: Deep Dense
    dense_layer = report.get("layer_3_deep_dense", {})
    if dense_layer.get("is_anomaly"):
        events.append(TriggerEvent(
            point_number=point_num,
            timestamp=timestamp,
            timestamp_str=timestamp_str,
            layer_name="layer_3_deep_dense",
            detector_type="Deep Dense",
            is_anomaly=True,
            details=dense_layer,
            matched_rules=[],
            confidence_score=confidence_score,
            position=position
        ))
    
    # Layer 4: Deep CNN
    cnn_layer = report.get("layer_4_deep_cnn", {})
    if cnn_layer.get("is_anomaly"):
        events.append(TriggerEvent(
            point_number=point_num,
            timestamp=timestamp,
            timestamp_str=timestamp_str,
            layer_name="layer_4_deep_cnn",
            detector_type="Deep CNN",
            is_anomaly=True,
            details=cnn_layer,
            matched_rules=[],
            confidence_score=confidence_score,
            position=position
        ))
    
    # Layer 5: Transformer
    trans_layer = report.get("layer_5_transformer", {})
    if trans_layer.get("is_anomaly"):
        events.append(TriggerEvent(
            point_number=point_num,
            timestamp=timestamp,
            timestamp_str=timestamp_str,
            layer_name="layer_5_transformer",
            detector_type="Transformer",
            is_anomaly=True,
            details=trans_layer,
            matched_rules=[],
            confidence_score=confidence_score,
            position=position
        ))
    
    # Layer 6: Hybrid
    hybrid_layer = report.get("layer_6_hybrid", {})
    if hybrid_layer.get("is_anomaly"):
        events.append(TriggerEvent(
            point_number=point_num,
            timestamp=timestamp,
            timestamp_str=timestamp_str,
            layer_name="layer_6_hybrid",
            detector_type="Hybrid CNN-Transformer",
            is_anomaly=True,
            details=hybrid_layer,
            matched_rules=[],
            confidence_score=confidence_score,
            position=position
        ))
    
    return events


def generate_markdown_report(results: SimulationResults, output_path: str):
    """
    Generate a detailed markdown report of the simulation.
    
    Args:
        results: SimulationResults object
        output_path: Path to save the markdown file
    """
    logger.info(f"Generating markdown report: {output_path}")
    
    with open(output_path, 'w', encoding='utf-8') as f:
        # Header
        f.write(f"# Flight Simulation Report: {results.flight_id}\n\n")
        
        # Flight Information
        f.write("## Flight Information\n\n")
        f.write(f"- **Flight ID**: {results.flight_id}\n")
        f.write(f"- **Callsign**: {results.callsign or 'N/A'}\n")
        f.write(f"- **Route**: {results.origin or 'Unknown'} → {results.destination or 'Unknown'}\n")
        f.write(f"- **Total Points**: {results.total_points}\n")
        f.write(f"- **Analysis Interval**: Every {results.analysis_interval} points\n")
        f.write(f"- **Simulation Date**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        # Summary
        f.write("## Summary\n\n")
        if results.first_anomaly_point:
            f.write(f"- **First Anomaly Detected**: Point {results.first_anomaly_point} at {datetime.fromtimestamp(results.first_anomaly_timestamp).strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"- **Layers Triggered**: {', '.join(results.layers_triggered) if results.layers_triggered else 'None'}\n")
            f.write(f"- **Total Anomaly Points**: {results.total_anomaly_points}\n")
        else:
            f.write("- **No anomalies detected** during this simulation\n")
        
        f.write("\n---\n\n")
        
        # Timeline
        f.write("## Detection Timeline\n\n")
        
        if not results.timeline:
            f.write("*No detection events recorded*\n\n")
        else:
            current_point = None
            
            for event in results.timeline:
                # New point section
                if event.point_number != current_point:
                    current_point = event.point_number
                    f.write(f"\n### Point {event.point_number} - {event.timestamp_str}\n\n")
                    f.write(f"**Position**: Lat {event.position['lat']:.6f}, Lon {event.position['lon']:.6f}, Alt {event.position['alt']:.0f}ft\n\n")
                    f.write(f"**Overall Confidence**: {event.confidence_score:.1f}%\n\n")
                    f.write("#### Detections:\n\n")
                
                # Detection details
                f.write(f"- **{event.detector_type}**: TRIGGERED\n")
                
                if event.matched_rules:
                    f.write(f"  - Matched Rules:\n")
                    for rule in event.matched_rules:
                        f.write(f"    - {rule}\n")
                
                # Add key details
                if "severity" in event.details:
                    f.write(f"  - Severity: {event.details['severity']:.3f}\n")
                if "score" in event.details:
                    f.write(f"  - Score: {event.details['score']:.3f}\n")
                
                f.write("\n")
        
        f.write("\n---\n\n")
        f.write("*Report generated by simulate_flight_live.py*\n")
    
    logger.info(f"Report saved to {output_path}")


def simulate_live_monitoring(flight_id: str, interval_points: int = 5, output_file: str = "simulation_report.md"):
    """
    Simulate live monitoring by analyzing flight incrementally.
    
    Args:
        flight_id: Flight ID from research schema
        interval_points: Analyze every N points (default: 5)
        output_file: Output markdown file path
    """
    logger.info("="*80)
    logger.info("Starting Flight Simulation")
    logger.info("="*80)
    
    # Initialize database connection
    if not init_connection_pool():
        logger.error("Failed to initialize PostgreSQL connection pool")
        return
    
    # Load flight data
    all_points, metadata_dict = load_flight_from_feedback(flight_id)
    
    if not all_points:
        logger.error("No points loaded, aborting simulation")
        return
    
    # Initialize anomaly pipeline with PostgreSQL enabled
    logger.info("Initializing anomaly pipeline...")
    pipeline = AnomalyPipeline(use_postgres=True)
    
    # Create metadata object
    metadata = None
    if metadata_dict.get('origin_airport') or metadata_dict.get('destination_airport'):
        metadata = FlightMetadata(
            origin=metadata_dict.get('origin_airport'),
            planned_destination=metadata_dict.get('destination_airport'),
            planned_route=None
        )
    
    logger.info("="*80)
    logger.info(f"Starting point-by-point analysis for flight {flight_id}")
    logger.info(f"Total points: {len(all_points)}")
    logger.info(f"Analysis interval: Every {interval_points} points")
    logger.info("="*80)
    
    # Simulation state
    accumulated_points = []
    timeline = []
    first_anomaly_point = None
    first_anomaly_timestamp = None
    layers_triggered = set()
    total_anomaly_points = 0
    was_anomaly = False
    
    # Analyze point-by-point
    for i, point_data in enumerate(all_points, 1):
        # Add point to accumulated list
        track_point = TrackPoint(
            flight_id=point_data['flight_id'],
            timestamp=point_data['timestamp'],
            lat=point_data['lat'],
            lon=point_data['lon'],
            alt=point_data['alt'],
            gspeed=point_data['gspeed'],
            vspeed=point_data['vspeed'],
            track=point_data['track'],
            squawk=point_data['squawk'],
            callsign=point_data['callsign'],
            source=point_data['source']
        )
        accumulated_points.append(track_point)
        
        # Analyze at intervals (after minimum threshold)
        if len(accumulated_points) >= 20 and i % interval_points == 0:
            # Create flight track
            flight_track = FlightTrack(flight_id=flight_id, points=accumulated_points.copy())
            
            # Log progress
            timestamp_str = datetime.fromtimestamp(point_data['timestamp']).strftime('%Y-%m-%d %H:%M:%S')
            logger.info(f"\nAnalysis #{i//interval_points} - Point {i}/{len(all_points)}")
            logger.info(f"Timestamp: {timestamp_str}")
            logger.info(f"Position: Lat {point_data['lat']:.6f}, Lon {point_data['lon']:.6f}, Alt {point_data['alt']:.0f}ft")
            
            # Run pipeline analysis
            try:
                print(len(flight_track.points))
                report = pipeline.analyze(flight_track, metadata=metadata)
                
                is_anomaly = report["summary"]["is_anomaly"]
                confidence = report["summary"].get("confidence_score", 0)
                triggers = report["summary"].get("triggers", [])
                
                # Only extract trigger events when overall is_anomaly is True
                if is_anomaly:
                    position = {
                        'lat': point_data['lat'],
                        'lon': point_data['lon'],
                        'alt': point_data['alt']
                    }
                    events = extract_layer_results(report, i, point_data['timestamp'], position)
                else:
                    events = []
                
                if is_anomaly:
                    # Record trigger events
                    if events:
                        timeline.extend(events)
                        
                        for event in events:
                            layers_triggered.add(event.detector_type)
                            logger.warning(f"🚨 {event.detector_type} TRIGGERED")
                            if event.matched_rules:
                                for rule in event.matched_rules:
                                    logger.warning(f"   - {rule}")
                    
                    # Track first anomaly
                    if first_anomaly_point is None:
                        first_anomaly_point = i
                        first_anomaly_timestamp = point_data['timestamp']
                        logger.warning(f"\n{'#'*80}")
                        logger.warning(f"⚠️  FIRST ANOMALY DETECTED")
                        logger.warning(f"   Point: {i}")
                        logger.warning(f"   Timestamp: {timestamp_str}")
                        logger.warning(f"   Confidence: {confidence}%")
                        logger.warning(f"   Triggers: {', '.join(triggers)}")
                        logger.warning(f"{'#'*80}\n")
                    
                    total_anomaly_points += 1
                    was_anomaly = True
                else:
                    if was_anomaly:
                        logger.info(f"✓ Normal (confidence: {confidence}%)")
                    else:
                        logger.info(f"✓ Normal")
                
            except Exception as e:
                logger.error(f"Error during analysis: {e}", exc_info=True)
    
    # Generate results
    results = SimulationResults(
        flight_id=flight_id,
        callsign=metadata_dict.get('callsign'),
        origin=metadata_dict.get('origin_airport'),
        destination=metadata_dict.get('destination_airport'),
        total_points=len(all_points),
        analysis_interval=interval_points,
        timeline=timeline,
        first_anomaly_point=first_anomaly_point,
        first_anomaly_timestamp=first_anomaly_timestamp,
        layers_triggered=sorted(list(layers_triggered)),
        total_anomaly_points=total_anomaly_points
    )
    
    # Generate report
    generate_markdown_report(results, output_file)
    
    # Final summary
    logger.info("\n" + "="*80)
    logger.info("SIMULATION COMPLETE")
    logger.info("="*80)
    
    if first_anomaly_point:
        logger.info(f"✓ Anomaly detected at point {first_anomaly_point}")
        logger.info(f"  Timestamp: {datetime.fromtimestamp(first_anomaly_timestamp).strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"  Layers triggered: {', '.join(results.layers_triggered)}")
        logger.info(f"  Total anomaly points: {total_anomaly_points}")
    else:
        logger.info("✗ No anomalies detected during simulation")
    
    logger.info(f"Report saved to: {output_file}")
    logger.info("="*80)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Simulate live flight monitoring by replaying flights point-by-point"
    )
    parser.add_argument(
        "flight_id",
        help="Flight ID from feedback schema to simulate"
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=5,
        help="Analysis interval in points (default: 5)"
    )
    parser.add_argument(
        "--output",
        default="simulation_report.md",
        help="Output markdown file path (default: simulation_report.md)"
    )
    
    args = parser.parse_args()
    
    simulate_live_monitoring(args.flight_id, args.interval, args.output)
