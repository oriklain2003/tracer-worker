import sys
from pathlib import Path
import json

# Add root to path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from flight_fetcher import get
from mlboost.detector import XGBoostDetector

def main():
    print("=== XGBoost Anomaly Test ===")
    flight = get()
    print(f"Fetched Flight: {flight.flight_id}")
    
    model_path = Path(__file__).parent / "output" / "xgb_model.joblib"
    detector = XGBoostDetector(model_path)
    
    result = detector.predict(flight)
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()

