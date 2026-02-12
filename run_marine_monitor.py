#!/usr/bin/env python3
"""
Run Marine Monitor

Simple entry point script to run the marine vessel monitoring worker.
Loads environment variables and starts the monitor with proper signal handling.

Usage:
    python run_marine_monitor.py

Environment Variables:
    AIS_STREAM_API_KEY: AISstream.io API key (required)
    AIS_BOUNDING_BOX: JSON array of bounding boxes (optional, default: global)
    AIS_FILTER_MMSI: Comma-separated MMSI codes to filter (optional)
    AIS_BATCH_SIZE: Number of positions to batch before DB insert (default: 100)
    PG_HOST: PostgreSQL host (default: tracer-db.cb80eku2emy0.eu-north-1.rds.amazonaws.com)
    PG_PORT: PostgreSQL port (default: 5432)
    PG_DATABASE: PostgreSQL database (default: tracer)
    PG_USER: PostgreSQL user (default: postgres)
    PG_PASSWORD: PostgreSQL password (required)

Example:
    export AIS_STREAM_API_KEY="806cb56388d212f6d346775d69190649dc456907"
    export PG_PASSWORD="your_password"
    python run_marine_monitor.py
"""

import sys
import os
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent))

from marine_monitor import main

if __name__ == "__main__":
    print("=" * 60)
    print("Marine Vessel Monitoring Worker")
    print("=" * 60)
    print()
    print("Configuration:")
    print(f"  API Key: {'Set' if os.getenv('AIS_STREAM_API_KEY') else 'NOT SET'}")
    print(f"  Bounding Box: {os.getenv('AIS_BOUNDING_BOX', 'Global coverage')}")
    print(f"  MMSI Filter: {os.getenv('AIS_FILTER_MMSI', 'None')}")
    print(f"  Batch Size: {os.getenv('AIS_BATCH_SIZE', '100')}")
    print(f"  Database: {os.getenv('PG_DATABASE', 'tracer')}@{os.getenv('PG_HOST', 'tracer-db.cb80eku2emy0.eu-north-1.rds.amazonaws.com')}")
    print()
    print("Press Ctrl+C to stop gracefully")
    print("=" * 60)
    print()
    
    # Run the monitor
    main()
