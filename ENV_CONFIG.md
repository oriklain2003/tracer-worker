# Environment Configuration

This document describes the required and optional environment variables for the Flight Anomaly Monitor.

## Required Environment Variables

### PostgreSQL Database

The monitor requires a PostgreSQL database for storing flight data, anomaly reports, and AI classifications.

```bash
PG_HOST=tracer-db.cb80eku2emy0.eu-north-1.rds.amazonaws.com
PG_PORT=5432
PG_DATABASE=tracer
PG_USER=postgres
PG_PASSWORD=your_database_password_here
```

### FlightRadar24 API

Required for fetching live flight data from FlightRadar24.

```bash
FR24_API_TOKEN=your_fr24_api_token_here
```

## Optional Environment Variables

### Google Gemini API (AI Classification)

**Optional** - Enables AI-powered anomaly classification with 3-6 word root cause summaries.

If not provided, the monitor will run normally but AI classification will be disabled.

```bash
GEMINI_API_KEY=your_gemini_api_key_here
```

**How to get a Gemini API key:**
1. Visit https://aistudio.google.com/app/apikey
2. Sign in with your Google account
3. Create a new API key
4. Copy the key and add it to your environment variables

**What happens when enabled:**
- Automatically classifies detected anomaly flights in the background (non-blocking)
- Generates concise 3-6 word root cause summaries using AI
- Stores results in `{schema}.ai_classifications` table
- Example outputs: "Weather Avoidance Maneuver", "Emergency Landing Procedure", "Military Training Exercise"

**Resource usage:**
- Runs in a background thread pool (max 2 concurrent classifications)
- Does not block the main monitoring loop
- API calls typically complete in 3-5 seconds

## Configuration Methods

### Method 1: .env File (Recommended)

Create a `.env` file in the monitor directory:

```bash
# Copy the example
cp ENV_CONFIG.md .env

# Edit with your actual values
nano .env
```

### Method 2: System Environment Variables

Set environment variables in your shell:

```bash
# Linux/Mac
export GEMINI_API_KEY="your_key_here"
export FR24_API_TOKEN="your_token_here"

# Windows PowerShell
$env:GEMINI_API_KEY="your_key_here"
$env:FR24_API_TOKEN="your_token_here"

# Windows CMD
set GEMINI_API_KEY=your_key_here
set FR24_API_TOKEN=your_token_here
```

### Method 3: Docker Environment

When running in Docker, pass environment variables via docker-compose.yml:

```yaml
services:
  monitor:
    environment:
      - GEMINI_API_KEY=${GEMINI_API_KEY}
      - FR24_API_TOKEN=${FR24_API_TOKEN}
      - PG_HOST=${PG_HOST}
      - PG_PASSWORD=${PG_PASSWORD}
```

## Verification

To verify your configuration:

```bash
# Check if GEMINI_API_KEY is set
python -c "import os; print('AI Classification:', 'Enabled' if os.getenv('GEMINI_API_KEY') else 'Disabled')"

# Run the monitor and check logs
python monitor.py
# Look for: "✨ AI Classifier initialized successfully"
# Or: "AI Classification disabled (GEMINI_API_KEY not set)"
```

## Database Setup

Before running the monitor, ensure the `ai_classifications` table exists:

```sql
-- The table is automatically created on first run
-- But you can manually create it if needed:

CREATE TABLE IF NOT EXISTS live.ai_classifications (
    id SERIAL PRIMARY KEY,
    flight_id TEXT NOT NULL,
    classification_text TEXT NOT NULL,
    confidence_score FLOAT,
    full_response TEXT,
    processing_time_sec FLOAT,
    created_at TIMESTAMP DEFAULT NOW(),
    error_message TEXT,
    gemini_model TEXT,
    CONSTRAINT fk_flight FOREIGN KEY (flight_id) 
        REFERENCES live.flight_metadata(flight_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_ai_classifications_flight_id 
    ON live.ai_classifications(flight_id);
CREATE INDEX IF NOT EXISTS idx_ai_classifications_created_at 
    ON live.ai_classifications(created_at DESC);
```

## Querying AI Classifications

View recent AI classifications:

```sql
-- Get latest 10 classifications
SELECT 
    flight_id, 
    classification_text, 
    processing_time_sec, 
    created_at 
FROM live.ai_classifications 
ORDER BY created_at DESC 
LIMIT 10;

-- Get classifications for a specific flight
SELECT * 
FROM live.ai_classifications 
WHERE flight_id = '3d7211ef';

-- Get failed classifications (for debugging)
SELECT 
    flight_id, 
    error_message, 
    created_at 
FROM live.ai_classifications 
WHERE error_message IS NOT NULL 
ORDER BY created_at DESC;
```

## Troubleshooting

### AI Classification not working

**Check logs for:**
- "AI Classification disabled (GEMINI_API_KEY not set)" → Set the API key
- "Failed to initialize AI Classifier" → Check API key validity
- "Gemini API call failed" → Check network connectivity and API quota

**Verify API key:**
```bash
# Test Gemini API key
python -c "from google import genai; client = genai.Client(api_key='YOUR_KEY'); print('API key valid')"
```

### Database connection issues

**Check logs for:**
- "Failed to initialize PostgreSQL connection pool"
- "PostgreSQL connection test failed"

**Verify database:**
```bash
# Test PostgreSQL connection
psql -h $PG_HOST -p $PG_PORT -U $PG_USER -d $PG_DATABASE -c "SELECT 1"
```

## Security Notes

- **Never commit .env files to version control**
- Store API keys securely (use secrets management in production)
- Rotate API keys periodically
- Use read-only database credentials where possible
- Enable API key restrictions in Google Cloud Console

## Cost Considerations

**Gemini API Pricing (as of 2024):**
- Free tier: 15 requests per minute
- Paid tier: ~$0.001 per classification
- Typical monitor: 10-50 classifications per hour
- Estimated monthly cost: $0.50 - $5.00

To limit costs, consider:
- Using the free tier for development
- Setting API quotas in Google Cloud Console
- Reducing max_workers in AIClassifier (default: 2)
