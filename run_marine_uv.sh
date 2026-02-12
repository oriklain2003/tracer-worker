#!/bin/bash
# Run marine monitor using uv for fast startup

set -e

echo "=========================================="
echo "Marine Vessel Monitoring Worker (uv)"
echo "=========================================="
echo

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    echo "❌ uv is not installed"
    echo "   Install with: curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

# Check environment variables
if [ -z "$AIS_STREAM_API_KEY" ]; then
    echo "❌ AIS_STREAM_API_KEY not set"
    echo "   Please export: AIS_STREAM_API_KEY='your_key'"
    exit 1
fi

if [ -z "$PG_PASSWORD" ]; then
    echo "⚠️  PG_PASSWORD not set, using default from pg_provider.py"
fi

echo "Configuration:"
echo "  API Key: ${AIS_STREAM_API_KEY:0:20}..."
echo "  Database: ${PG_DATABASE:-tracer}@${PG_HOST:-tracer-db.cb80eku2emy0.eu-north-1.rds.amazonaws.com}"
echo "  Batch Size: ${AIS_BATCH_SIZE:-100}"
echo
echo "Press Ctrl+C to stop gracefully"
echo "=========================================="
echo

# Run with uv
cd "$(dirname "$0")"
exec uv run --with websockets --with psycopg2-binary marine_monitor.py
