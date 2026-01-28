import torch
import numpy as np
from ml_transformer.detector import TransformerAnomalyDetector
from core.models import FlightTrack, TrackPoint

def test():
    print("Initializing Detector...")
    detector = TransformerAnomalyDetector()
    
    # Create a dummy normal flight
    print("Testing Normal Flight...")
    points = []
    for i in range(60):
        points.append(TrackPoint(
            flight_id="normal_test",
            timestamp=1000+i*10,
            lat=32.0 + i*0.01,
            lon=34.0 + i*0.01,
            alt=10000 + i*10,
            gspeed=250,
            track=45,
            source="test"
        ))
    flight = FlightTrack("normal_test", points)
    score, is_anom = detector.predict(flight)
    print(f"Score: {score:.6f}, Is Anomaly: {is_anom}")
    
    # Create a dummy anomalous flight (zig-zag)
    print("\nTesting Anomalous Flight...")
    points = []
    for i in range(60):
        lat_offset = 0.1 if i % 2 == 0 else -0.1
        points.append(TrackPoint(
            flight_id="anom_test",
            timestamp=1000+i*10,
            lat=32.0 + i*0.01 + lat_offset,
            lon=34.0 + i*0.01,
            alt=10000,
            gspeed=250,
            track=45 + (90 if i%2==0 else -90),
            source="test"
        ))
    flight_anom = FlightTrack("anom_test", points)
    score, is_anom = detector.predict(flight_anom)
    print(f"Score: {score:.6f}, Is Anomaly: {is_anom}")

if __name__ == "__main__":
    test()

