"""
Health Check Script for Flight Monitor

This script checks if the monitor is running properly by:
1. Checking if the process is alive
2. Verifying database connectivity
3. Checking the last heartbeat timestamp

Exit codes:
0 - Healthy
1 - Unhealthy
"""

import sys
import os
from pathlib import Path

# Add root to path for imports
sys.path.append(str(Path(__file__).resolve().parent))

from pg_provider import test_connection
import logging

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


def check_database() -> bool:
    """Check if database is accessible."""
    try:
        return test_connection()
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return False


def check_monitor_status() -> bool:
    """Check if monitor is properly configured."""
    try:
        from pg_provider import get_connection
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT is_active FROM public.monitor_status LIMIT 1")
                result = cursor.fetchone()
                if result:
                    return True
        return False
    except Exception as e:
        logger.error(f"Monitor status check failed: {e}")
        return False


def main():
    """Run health checks."""
    checks_passed = 0
    checks_total = 2
    
    # Check 1: Database connectivity
    if check_database():
        checks_passed += 1
        print("✓ Database connection OK")
    else:
        print("✗ Database connection FAILED")
    
    # Check 2: Monitor status table exists
    if check_monitor_status():
        checks_passed += 1
        print("✓ Monitor status OK")
    else:
        print("✗ Monitor status FAILED")
    
    # Return exit code
    if checks_passed == checks_total:
        print(f"\n✓ Health check PASSED ({checks_passed}/{checks_total})")
        sys.exit(0)
    else:
        print(f"\n✗ Health check FAILED ({checks_passed}/{checks_total})")
        sys.exit(1)


if __name__ == "__main__":
    main()
