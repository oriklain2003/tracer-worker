import sys
from pathlib import Path
import json

sys.path.append(str(Path(__file__).resolve().parent.parent))

from flight_fetcher import get
from ml_deep.detector import DeepAnomalyDetector

def main():
    print("=== Deep Dense Anomaly Test ===")
    flight = get()
    print(f"Fetched Flight: {flight.flight_id}")
    
    model_dir = Path(__file__).parent / "output"
    detector = DeepAnomalyDetector(model_dir)
    
    result = detector.predict(flight)
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()

