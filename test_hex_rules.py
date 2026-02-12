"""
Test suite for HEX-based rules and ICAO hex utilities.

Tests:
1. core/icao_hex.py - hex_to_country, airline_prefix_to_country, check_identity_origin_conflict
2. Rule 18 - Identity-Origin Conflict (IOC)
3. Rule 22 - Ghost Aircraft Detection (GAD) 
4. Rule 20 - Signal Discontinuity (ISD) - re-enabled
5. Integration: FlightMetadata with icao_hex flowing through rule engine

Usage:
    python test_hex_rules.py
"""
from __future__ import annotations

import sys
import time
import json
from pathlib import Path
from dataclasses import dataclass

# Ensure monitor root is on path
sys.path.insert(0, str(Path(__file__).resolve().parent))

# ============================================================================
# Test Utilities
# ============================================================================

_PASS = 0
_FAIL = 0
_ERRORS = []


def _check(label: str, condition: bool, detail: str = ""):
    global _PASS, _FAIL, _ERRORS
    if condition:
        _PASS += 1
        print(f"  [PASS] {label}")
    else:
        _FAIL += 1
        msg = f"  [FAIL] {label}" + (f" -- {detail}" if detail else "")
        print(msg)
        _ERRORS.append(msg)


def _header(title: str):
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}")


# ============================================================================
# Helpers: Create synthetic flight tracks for testing
# ============================================================================

from core.models import FlightTrack, FlightMetadata, TrackPoint, RuleContext


def make_track(flight_id: str, points_data: list) -> FlightTrack:
    """
    Create a FlightTrack from list of dicts.
    Each dict: {ts, lat, lon, alt, gspeed, vspeed, track, squawk, callsign}
    """
    points = []
    for pd in points_data:
        points.append(TrackPoint(
            flight_id=flight_id,
            timestamp=pd.get("ts", int(time.time())),
            lat=pd.get("lat", 32.0),
            lon=pd.get("lon", 34.8),
            alt=pd.get("alt", 35000),
            gspeed=pd.get("gspeed", 450),
            vspeed=pd.get("vspeed", 0),
            track=pd.get("track", 90),
            squawk=pd.get("squawk"),
            callsign=pd.get("callsign"),
            source=pd.get("source", "test"),
        ))
    return FlightTrack(flight_id=flight_id, points=points)


def make_straight_flight(
    flight_id: str = "TEST001",
    callsign: str = "ELY001",
    start_lat: float = 32.0, start_lon: float = 34.8,
    end_lat: float = 33.0, end_lon: float = 35.5,
    num_points: int = 100,
    alt: float = 35000,
    gspeed: float = 450,
    base_ts: int = None,
    interval_sec: int = 10,
) -> FlightTrack:
    """Create a simple straight-line flight with uniform parameters."""
    if base_ts is None:
        base_ts = int(time.time()) - (num_points * interval_sec)
    
    points = []
    for i in range(num_points):
        frac = i / max(1, num_points - 1)
        lat = start_lat + (end_lat - start_lat) * frac
        lon = start_lon + (end_lon - start_lon) * frac
        points.append({
            "ts": base_ts + i * interval_sec,
            "lat": lat,
            "lon": lon,
            "alt": alt,
            "gspeed": gspeed,
            "vspeed": 0,
            "track": 45.0,
            "callsign": callsign,
        })
    return make_track(flight_id, points)


# ============================================================================
# TEST 1: core/icao_hex.py
# ============================================================================

def test_icao_hex_module():
    _header("TEST 1: core/icao_hex.py - Hex Utilities")
    
    from core.icao_hex import (
        hex_to_country,
        airline_prefix_to_country,
        check_identity_origin_conflict,
        is_offshore_registration,
    )
    
    # --- hex_to_country ---
    print("\n  -- hex_to_country --")
    
    # Israel: 0x738000 - 0x73FFFF
    result = hex_to_country("738065")
    _check("Israel hex (738065)", result is not None and result[0] == "IL",
           f"got {result}")
    
    result = hex_to_country("73FFFF")
    _check("Israel hex upper bound (73FFFF)", result is not None and result[0] == "IL",
           f"got {result}")
    
    # Egypt: 0x010000 - 0x017FFF
    result = hex_to_country("010123")
    _check("Egypt hex (010123)", result is not None and result[0] == "EG",
           f"got {result}")
    
    # Lebanon: 0x748000 - 0x74FFFF
    result = hex_to_country("748001")
    _check("Lebanon hex (748001)", result is not None and result[0] == "LB",
           f"got {result}")
    
    # Iran: 0x730000 - 0x737FFF
    result = hex_to_country("730ABC")
    _check("Iran hex (730ABC)", result is not None and result[0] == "IR",
           f"got {result}")
    
    # Turkey: 0x4B8000 - 0x4BFFFF
    result = hex_to_country("4B8500")
    _check("Turkey hex (4B8500)", result is not None and result[0] == "TR",
           f"got {result}")
    
    # US: 0xA00000 - 0xAFFFFF
    result = hex_to_country("A12345")
    _check("US hex (A12345)", result is not None and result[0] == "US",
           f"got {result}")
    
    # Unknown / unassigned hex
    result = hex_to_country("000001")
    _check("Unassigned hex (000001) returns None", result is None,
           f"got {result}")
    
    # Invalid hex string
    result = hex_to_country("ZZZZZZ")
    _check("Invalid hex string returns None", result is None,
           f"got {result}")
    
    result = hex_to_country("")
    _check("Empty hex string returns None", result is None,
           f"got {result}")
    
    result = hex_to_country(None)
    _check("None hex returns None", result is None,
           f"got {result}")
    
    # Jordan: 0x740000 - 0x747FFF
    result = hex_to_country("740100")
    _check("Jordan hex (740100)", result is not None and result[0] == "JO",
           f"got {result}")
    
    # Syria: 0x778000 - 0x77FFFF
    result = hex_to_country("778100")
    _check("Syria hex (778100)", result is not None and result[0] == "SY",
           f"got {result}")
    
    # Saudi Arabia: 0x710000 - 0x717FFF
    result = hex_to_country("710500")
    _check("Saudi Arabia hex (710500)", result is not None and result[0] == "SA",
           f"got {result}")
    
    # UAE: 0x896000 - 0x896FFF
    result = hex_to_country("896100")
    _check("UAE hex (896100)", result is not None and result[0] == "AE",
           f"got {result}")
    
    # UK: 0x400000 - 0x43FFFF
    result = hex_to_country("406B21")
    _check("UK hex (406B21)", result is not None and result[0] == "GB",
           f"got {result}")
    
    # --- airline_prefix_to_country ---
    print("\n  -- airline_prefix_to_country --")
    
    result = airline_prefix_to_country("ELY001")
    _check("ELY prefix -> Israel", result is not None and result[0] == "IL",
           f"got {result}")
    
    result = airline_prefix_to_country("MEA402")
    _check("MEA prefix -> Lebanon", result is not None and result[0] == "LB",
           f"got {result}")
    
    result = airline_prefix_to_country("IRM456")
    _check("IRM prefix -> Iran", result is not None and result[0] == "IR",
           f"got {result}")
    
    result = airline_prefix_to_country("THY123")
    _check("THY prefix -> Turkey", result is not None and result[0] == "TR",
           f"got {result}")
    
    result = airline_prefix_to_country("MSR789")
    _check("MSR prefix -> Egypt", result is not None and result[0] == "EG",
           f"got {result}")
    
    result = airline_prefix_to_country("XY")
    _check("Too short callsign returns None", result is None,
           f"got {result}")
    
    result = airline_prefix_to_country("123ABC")
    _check("Numeric prefix returns None", result is None,
           f"got {result}")
    
    # --- check_identity_origin_conflict ---
    print("\n  -- check_identity_origin_conflict --")
    
    # Conflict: Egyptian hex + MEA (Lebanese) callsign
    result = check_identity_origin_conflict("010123", "MEA402")
    _check("Egypt hex + Lebanon callsign = CONFLICT", result is not None and result["conflict"] == True,
           f"got {result}")
    
    # No conflict: Israel hex + ELY callsign
    result = check_identity_origin_conflict("738065", "ELY001")
    _check("Israel hex + Israel callsign = NO conflict", result is None,
           f"got {result}")
    
    # Iran hex + Iran callsign (no conflict)
    result = check_identity_origin_conflict("730ABC", "IRA456")
    _check("Iran hex + Iran callsign = NO conflict", result is None,
           f"got {result}")
    
    # Iran hex + ELY callsign (conflict!)
    result = check_identity_origin_conflict("730ABC", "ELY001")
    _check("Iran hex + Israel callsign = CONFLICT", result is not None and result["conflict"] == True,
           f"got {result}")
    
    # --- is_offshore_registration ---
    print("\n  -- is_offshore_registration --")
    
    # Normal registration
    result = is_offshore_registration("738065")
    _check("Israel hex is NOT offshore", result == False,
           f"got {result}")


# ============================================================================
# TEST 2: Rule 18 - Identity-Origin Conflict (IOC)
# ============================================================================

def test_rule_18_ioc():
    _header("TEST 2: Rule 18 - Identity-Origin Conflict (IOC)")
    
    from rules.rule_logic import evaluate_rule
    from core.models import RuleContext
    
    # Use a mock repository (None is OK, rule 18 doesn't use it)
    repo = None
    
    # Test 1: Egypt hex + Lebanese callsign -> CONFLICT
    print("\n  -- Egypt hex + Lebanese callsign --")
    track = make_straight_flight(callsign="MEA402")
    metadata = FlightMetadata(
        icao_hex="010123",
        callsign="MEA402",
        origin="HECA",
        planned_destination="OLBA",
    )
    ctx = RuleContext(track=track, metadata=metadata, repository=repo)
    result = evaluate_rule(ctx, 18)
    _check("Rule 18 matches (Egypt hex + Lebanon callsign)", result.matched == True,
           f"matched={result.matched}, summary={result.summary}")
    
    if result.matched:
        _check("Details contain hex_country_iso=EG", 
               result.details.get("hex_country_iso") == "EG",
               f"got {result.details.get('hex_country_iso')}")
        _check("Details contain airline_country_iso=LB", 
               result.details.get("airline_country_iso") == "LB",
               f"got {result.details.get('airline_country_iso')}")
    
    # Test 2: Israel hex + Israel callsign -> NO conflict
    print("\n  -- Israel hex + Israel callsign --")
    track = make_straight_flight(callsign="ELY001")
    metadata = FlightMetadata(
        icao_hex="738065",
        callsign="ELY001",
        origin="LLBG",
        planned_destination="LCLK",
    )
    ctx = RuleContext(track=track, metadata=metadata, repository=repo)
    result = evaluate_rule(ctx, 18)
    _check("Rule 18 does NOT match (Israel hex + Israel callsign)", result.matched == False,
           f"matched={result.matched}, summary={result.summary}")
    
    # Test 3: No hex available -> rule skips gracefully
    print("\n  -- No hex available --")
    track = make_straight_flight(callsign="ELY001")
    metadata = FlightMetadata(
        callsign="ELY001",
    )
    ctx = RuleContext(track=track, metadata=metadata, repository=repo)
    result = evaluate_rule(ctx, 18)
    _check("Rule 18 skips when no hex", result.matched == False,
           f"matched={result.matched}, summary={result.summary}")
    
    # Test 4: Iran hex + Israeli callsign -> CONFLICT
    print("\n  -- Iran hex + Israeli callsign --")
    track = make_straight_flight(callsign="ELY789")
    metadata = FlightMetadata(
        icao_hex="730ABC",
        callsign="ELY789",
    )
    ctx = RuleContext(track=track, metadata=metadata, repository=repo)
    result = evaluate_rule(ctx, 18)
    _check("Rule 18 matches (Iran hex + Israel callsign)", result.matched == True,
           f"matched={result.matched}, summary={result.summary}")
    
    # Test 5: Turkey hex + Turkish callsign -> NO conflict
    print("\n  -- Turkey hex + Turkish callsign --")
    track = make_straight_flight(callsign="THY123")
    metadata = FlightMetadata(
        icao_hex="4B8500",
        callsign="THY123",
    )
    ctx = RuleContext(track=track, metadata=metadata, repository=repo)
    result = evaluate_rule(ctx, 18)
    _check("Rule 18 does NOT match (Turkey hex + Turkey callsign)", result.matched == False,
           f"matched={result.matched}, summary={result.summary}")


# ============================================================================
# TEST 3: Rule 22 - Ghost Aircraft Detection (GAD)
# ============================================================================

def test_rule_22_gad():
    _header("TEST 3: Rule 22 - Ghost Aircraft Detection (GAD)")
    
    from rules.rule_logic import evaluate_rule
    from core.models import RuleContext
    
    repo = None
    
    # Test 1: Valid hex (Israel) -> no ghost
    print("\n  -- Valid hex (Israel) --")
    track = make_straight_flight(callsign="ELY001")
    metadata = FlightMetadata(icao_hex="738065")
    ctx = RuleContext(track=track, metadata=metadata, repository=repo)
    result = evaluate_rule(ctx, 22)
    _check("Rule 22 does NOT match valid hex", result.matched == False,
           f"matched={result.matched}, summary={result.summary}")
    
    # Test 2: Unassigned hex -> ghost alert
    print("\n  -- Unassigned hex (000001) --")
    track = make_straight_flight(callsign="UNKN01")
    metadata = FlightMetadata(icao_hex="000001")
    ctx = RuleContext(track=track, metadata=metadata, repository=repo)
    result = evaluate_rule(ctx, 22)
    _check("Rule 22 matches unassigned hex", result.matched == True,
           f"matched={result.matched}, summary={result.summary}")
    
    # Test 3: Another unassigned range
    print("\n  -- Hex in gap between allocations --")
    track = make_straight_flight(callsign="TEST01")
    metadata = FlightMetadata(icao_hex="001000")
    ctx = RuleContext(track=track, metadata=metadata, repository=repo)
    result = evaluate_rule(ctx, 22)
    _check("Rule 22 matches hex in gap", result.matched == True,
           f"matched={result.matched}, summary={result.summary}")
    
    # Test 4: No hex available -> skips
    print("\n  -- No hex available --")
    track = make_straight_flight(callsign="ELY001")
    metadata = FlightMetadata()
    ctx = RuleContext(track=track, metadata=metadata, repository=repo)
    result = evaluate_rule(ctx, 22)
    _check("Rule 22 skips when no hex", result.matched == False,
           f"matched={result.matched}, summary={result.summary}")
    
    # Test 5: Invalid hex format
    print("\n  -- Invalid hex format --")
    track = make_straight_flight(callsign="TEST01")
    metadata = FlightMetadata(icao_hex="ZZZZZZ")
    ctx = RuleContext(track=track, metadata=metadata, repository=repo)
    result = evaluate_rule(ctx, 22)
    _check("Rule 22 matches invalid hex format", result.matched == True,
           f"matched={result.matched}, summary={result.summary}")


# ============================================================================
# TEST 4: Rule 20 - Signal Discontinuity (ISD) - re-enabled
# ============================================================================

def test_rule_20_isd():
    _header("TEST 4: Rule 20 - Signal Discontinuity (ISD)")
    
    from rules.rule_logic import evaluate_rule
    from core.models import RuleContext
    
    repo = None
    base_ts = int(time.time()) - 3600
    
    # Test 1: Flight with large gap at altitude -> should detect
    print("\n  -- Flight with suspicious signal gap --")
    points = []
    # First 20 points: stable cruise, far from airports
    for i in range(20):
        points.append({
            "ts": base_ts + i * 10,
            "lat": 31.5 + i * 0.01,
            "lon": 35.3 + i * 0.01,
            "alt": 35000,
            "gspeed": 450,
            "vspeed": 0,
            "track": 45.0,
            "callsign": "TST001",
        })
    
    # Gap of 5 minutes (300 seconds)
    gap_ts = base_ts + 200 + 300  # Last point was at base_ts+190
    
    # Points after gap
    for i in range(20):
        points.append({
            "ts": gap_ts + i * 10,
            "lat": 31.7 + i * 0.01,
            "lon": 35.5 + i * 0.01,
            "alt": 34500,
            "gspeed": 445,
            "vspeed": 0,
            "track": 45.0,
            "callsign": "TST001",
        })
    
    track = make_track("GAPTEST", points)
    metadata = FlightMetadata()
    ctx = RuleContext(track=track, metadata=metadata, repository=repo)
    result = evaluate_rule(ctx, 20)
    _check("Rule 20 detects signal gap at altitude", result.matched == True,
           f"matched={result.matched}, summary={result.summary}")
    
    # Test 2: Normal continuous flight -> no gap detected
    print("\n  -- Normal continuous flight --")
    track = make_straight_flight(
        flight_id="NORMAL001",
        callsign="ELY001",
        start_lat=31.5, start_lon=35.3,
        end_lat=32.0, end_lon=35.8,
        alt=35000, gspeed=450,
    )
    metadata = FlightMetadata()
    ctx = RuleContext(track=track, metadata=metadata, repository=repo)
    result = evaluate_rule(ctx, 20)
    _check("Rule 20 does NOT trigger on normal flight", result.matched == False,
           f"matched={result.matched}, summary={result.summary}")


# ============================================================================
# TEST 5: FlightMetadata with icao_hex integration
# ============================================================================

def test_metadata_integration():
    _header("TEST 5: FlightMetadata icao_hex integration")
    
    # Test that FlightMetadata properly stores hex
    metadata = FlightMetadata(
        origin="LLBG",
        planned_destination="LCLK",
        icao_hex="738065",
        aircraft_type="B738",
        callsign="ELY001",
        aircraft_registration="4X-EKA",
    )
    
    _check("FlightMetadata stores icao_hex", metadata.icao_hex == "738065",
           f"got {metadata.icao_hex}")
    _check("FlightMetadata stores callsign", metadata.callsign == "ELY001",
           f"got {metadata.callsign}")
    _check("FlightMetadata stores aircraft_registration", metadata.aircraft_registration == "4X-EKA",
           f"got {metadata.aircraft_registration}")
    
    # Test rule evaluation with full metadata
    from rules.rule_logic import evaluate_rule
    from core.models import RuleContext
    
    track = make_straight_flight(callsign="ELY001")
    ctx = RuleContext(track=track, metadata=metadata, repository=None)
    
    # Rule 18 should NOT trigger (matching countries)
    result = evaluate_rule(ctx, 18)
    _check("Rule 18 with full metadata (no conflict)", result.matched == False,
           f"matched={result.matched}")
    
    # Rule 22 should NOT trigger (valid hex)
    result = evaluate_rule(ctx, 22)
    _check("Rule 22 with valid hex (no ghost)", result.matched == False,
           f"matched={result.matched}")


# ============================================================================
# TEST 6: Rule Engine full evaluation with new rules
# ============================================================================

def test_rule_engine_integration():
    _header("TEST 6: Rule Engine integration with new rules")
    
    from rules.rule_engine import AnomalyRuleEngine
    
    rules_path = Path(__file__).parent / "anomaly_rule.json"
    if not rules_path.exists():
        print(f"  [SKIP] anomaly_rule.json not found at {rules_path}")
        return
    
    # Load rule definitions and check new rules are present
    with open(rules_path, "r", encoding="utf-8") as f:
        rules = json.load(f)
    
    rule_ids = [r["id"] for r in rules]
    _check("Rule 18 (IOC) in anomaly_rule.json", 18 in rule_ids,
           f"rule_ids={rule_ids}")
    _check("Rule 22 (GAD) in anomaly_rule.json", 22 in rule_ids,
           f"rule_ids={rule_ids}")
    
    # Test full evaluation with engine
    engine = AnomalyRuleEngine(repository=None, rules_path=rules_path)
    
    # Create a flight with Egyptian hex + Lebanese callsign (should trigger IOC)
    track = make_straight_flight(
        flight_id="IOC_TEST",
        callsign="MEA402",
        start_lat=30.5, start_lon=31.5,
        end_lat=33.8, end_lon=35.5,
        alt=35000, gspeed=450,
    )
    metadata = FlightMetadata(
        icao_hex="010123",
        callsign="MEA402",
        origin="HECA",
        planned_destination="OLBA",
        aircraft_type="A320",
        category="passenger",
    )
    
    report = engine.evaluate_track(track, metadata=metadata)
    
    matched_ids = [r["id"] for r in report.get("matched_rules", [])]
    _check("Engine found matched rules", len(report.get("evaluations", [])) > 0,
           f"total evaluations: {report.get('total_rules', 0)}")
    _check("Rule 18 triggered in engine evaluation", 18 in matched_ids,
           f"matched_ids={matched_ids}")
    
    # Check total rules includes 18 and 22
    eval_ids = [e["id"] for e in report.get("evaluations", [])]
    _check("Rule 18 evaluated by engine", 18 in eval_ids,
           f"eval_ids={eval_ids}")
    _check("Rule 22 evaluated by engine", 22 in eval_ids,
           f"eval_ids={eval_ids}")


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("  HEX RULES TEST SUITE")
    print("=" * 70)
    
    try:
        test_icao_hex_module()
    except Exception as e:
        print(f"\n  [ERROR] test_icao_hex_module crashed: {e}")
        import traceback; traceback.print_exc()
    
    try:
        test_rule_18_ioc()
    except Exception as e:
        print(f"\n  [ERROR] test_rule_18_ioc crashed: {e}")
        import traceback; traceback.print_exc()
    
    try:
        test_rule_22_gad()
    except Exception as e:
        print(f"\n  [ERROR] test_rule_22_gad crashed: {e}")
        import traceback; traceback.print_exc()
    
    try:
        test_rule_20_isd()
    except Exception as e:
        print(f"\n  [ERROR] test_rule_20_isd crashed: {e}")
        import traceback; traceback.print_exc()
    
    try:
        test_metadata_integration()
    except Exception as e:
        print(f"\n  [ERROR] test_metadata_integration crashed: {e}")
        import traceback; traceback.print_exc()
    
    try:
        test_rule_engine_integration()
    except Exception as e:
        print(f"\n  [ERROR] test_rule_engine_integration crashed: {e}")
        import traceback; traceback.print_exc()
    
    # Summary
    print(f"\n{'='*70}")
    print(f"  RESULTS: {_PASS} passed, {_FAIL} failed")
    print(f"{'='*70}")
    
    if _ERRORS:
        print("\n  FAILURES:")
        for err in _ERRORS:
            print(f"    {err}")
    
    print()
    sys.exit(0 if _FAIL == 0 else 1)
