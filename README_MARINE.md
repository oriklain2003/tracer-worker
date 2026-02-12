# Marine Data Pipeline - Quick Start

## 🚢 What is this?

A real-time marine vessel tracking system that collects AIS data from ships worldwide and stores it in PostgreSQL.

## ⚡ Quick Test (Using uv)

```bash
# 1. Set environment variables
export AIS_STREAM_API_KEY="806cb56388d212f6d346775d69190649dc456907"
export PG_PASSWORD="your_database_password"

# 2. Run test (60 seconds)
cd tracer-worker
./test_marine.sh
```

This will:
- ✅ Verify database schema exists
- ✅ Connect to AISstream.io
- ✅ Collect data for 60 seconds
- ✅ Display sample vessel positions
- ✅ Show data quality metrics

## 🚀 Run Continuously

```bash
# With uv (recommended - fast, auto-installs dependencies)
./run_marine_uv.sh

# Or with Python
pip install -r requirements.txt
python run_marine_monitor.py
```

## 📊 Check Data

```sql
-- Recent vessels (last 10 minutes)
SELECT COUNT(DISTINCT mmsi) FROM marine.vessel_positions 
WHERE timestamp > NOW() - INTERVAL '10 minutes';

-- Sample positions
SELECT vp.mmsi, vm.vessel_name, vp.latitude, vp.longitude, vp.timestamp
FROM marine.vessel_positions vp
LEFT JOIN marine.vessel_metadata vm USING (mmsi)
ORDER BY vp.timestamp DESC LIMIT 10;
```

## 🔧 Configuration

```bash
# Required
export AIS_STREAM_API_KEY="your_key"      # Get from https://aisstream.io
export PG_PASSWORD="your_password"        # Database password

# Optional
export AIS_BATCH_SIZE="100"               # Messages per batch (default: 100)
export AIS_BOUNDING_BOX='[[[-90,-180],[90,180]]]'  # Geographic filter (default: global)
export AIS_FILTER_MMSI="368207620,367719770"       # Filter specific vessels
```

## 📖 Documentation

- **Setup Guide**: `MARINE_SETUP.md` - Complete setup instructions
- **API Documentation**: `MARINE_DATA_API.md` - Query examples, endpoints
- **Integration Guide**: `../tracer-api/MARINE_INTEGRATION.md` - Backend integration
- **Architecture**: `../.cursor/specs/marine_architecture.md` - System design

## 🛠️ Tools Available

| Script | Purpose | Usage |
|--------|---------|-------|
| `test_marine.sh` | Quick test (60s) | `./test_marine.sh` |
| `run_marine_uv.sh` | Run with uv | `./run_marine_uv.sh` |
| `run_marine_monitor.py` | Run with Python | `python run_marine_monitor.py` |
| `test_marine_pipeline.py` | Full test script | `python test_marine_pipeline.py` |

## 🐛 Troubleshooting

**No data appearing?**
```bash
# Check worker is running
ps aux | grep marine_monitor

# Check logs
tail -f marine_monitor.log

# Verify API key works
curl -H "Authorization: Bearer $AIS_STREAM_API_KEY" https://stream.aisstream.io/v0/health
```

**Database connection issues?**
```bash
# Test connection
psql -h $PG_HOST -U postgres -d tracer -c "SELECT 1"

# Verify schema exists
psql -h $PG_HOST -U postgres -d tracer -c "\dn marine"
```

## 📈 Expected Performance

- **Global Coverage**: ~50,000 active vessels
- **Message Rate**: 250K-500K messages/minute
- **DB Insert Rate**: 2.5K-5K inserts/minute (after batching)
- **Storage**: ~50-100 GB per month

## ✨ Features

- ✅ Real-time vessel position tracking
- ✅ Vessel metadata (name, type, destination, etc.)
- ✅ Automatic reconnection with exponential backoff
- ✅ Batch processing for efficient database inserts
- ✅ Graceful shutdown (Ctrl+C flushes remaining data)
- ✅ Statistics logging every 60 seconds

## 🎯 Next Steps

1. ✅ **Test the pipeline** - Run `./test_marine.sh`
2. ⏳ **Implement API** - Add endpoints to tracer-api
3. ⏳ **Create UI** - Build vessel map in anomaly-prod

---

**Need Help?** Check the documentation files listed above or run the test script to verify everything is working.
