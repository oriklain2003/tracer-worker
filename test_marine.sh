#!/bin/bash
# Quick test script for marine data pipeline using uv

set -e

echo "=========================================="
echo "Marine Data Pipeline Test"
echo "=========================================="
echo

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    echo "❌ uv is not installed"
    echo "   Install with: curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

echo "✅ uv is installed"

# Check environment variables
if [ -z "$AIS_STREAM_API_KEY" ]; then
    echo "❌ AIS_STREAM_API_KEY not set"
    echo "   Please set: export AIS_STREAM_API_KEY='your_key'"
    exit 1
fi

if [ -z "$PG_PASSWORD" ]; then
    echo "❌ PG_PASSWORD not set"
    echo "   Please set: export PG_PASSWORD='your_password'"
    exit 1
fi

echo "✅ Environment variables configured"
echo

# Run the test
echo "Running test with uv..."
echo
cd "$(dirname "$0")"
uv run --with websockets --with psycopg2-binary test_marine_pipeline.py
