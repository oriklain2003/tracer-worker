# AI-Powered Anomaly Classification

## Overview

The Flight Anomaly Monitor now includes automatic AI-powered classification using Google Gemini. When an anomaly is detected, the system automatically generates a concise 3-6 word root cause summary and stores it in the database for later analysis.

## Features

✅ **Async Processing** - Runs in background threads, doesn't block the monitor  
✅ **Automatic Trigger** - Activates when anomalies are detected  
✅ **Concise Summaries** - Generates 3-6 word professional root cause descriptions  
✅ **Visual Context** - Includes flight path map images for better analysis  
✅ **Database Storage** - Stores results in `ai_classifications` table  
✅ **Error Handling** - Gracefully handles API failures without crashing  
✅ **Cost Effective** - Uses lightweight Gemini Flash model  

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

This will install:
- `google-genai` - Google Gemini API client
- `staticmap` - Map image generation
- `Pillow` - Image processing

### 2. Set Environment Variable

Get a Gemini API key from https://aistudio.google.com/app/apikey and set it:

```bash
# Linux/Mac
export GEMINI_API_KEY="your_api_key_here"

# Windows PowerShell
$env:GEMINI_API_KEY="your_api_key_here"

# Or create a .env file
echo "GEMINI_API_KEY=your_api_key_here" > .env
```

### 3. Run the Monitor

```bash
python monitor.py
```

Look for the initialization message:
```
✨ AI Classifier initialized successfully
```

### 4. Observe Classifications

When an anomaly is detected, you'll see:
```
🚨 ANOMALY DETECTED: 3d7211ef (ELY123)
🤖 Triggered AI classification for 3d7211ef
✅ Classification task completed: 3d7211ef -> 'Weather Avoidance Maneuver'
```

## Architecture

```
┌─────────────┐
│  monitor.py │ Detects anomaly
└──────┬──────┘
       │
       ├─────────────────────┐
       │                     │
       ▼                     ▼
┌─────────────┐      ┌──────────────┐
│   Save to   │      │ AI Classifier│ (async)
│  Database   │      │  Background  │
└─────────────┘      │    Thread    │
                     └──────┬───────┘
                            │
                            ▼
                     ┌──────────────┐
                     │ Google Gemini│
                     │      API     │
                     └──────┬───────┘
                            │
                            ▼
                     ┌──────────────┐
                     │ ai_classifications
                     │     table    │
                     └──────────────┘
```

## Database Schema

The `ai_classifications` table stores AI-generated summaries:

```sql
CREATE TABLE ai_classifications (
    id SERIAL PRIMARY KEY,
    flight_id TEXT NOT NULL,
    classification_text TEXT NOT NULL,      -- 3-6 word summary
    confidence_score FLOAT,                  -- Optional confidence
    full_response TEXT,                      -- Complete AI response
    processing_time_sec FLOAT,               -- Processing duration
    created_at TIMESTAMP DEFAULT NOW(),
    error_message TEXT,                      -- NULL if successful
    gemini_model TEXT,                       -- Model name used
    CONSTRAINT fk_flight FOREIGN KEY (flight_id) 
        REFERENCES flight_metadata(flight_id) ON DELETE CASCADE
);
```

## Querying Results

### View Recent Classifications

```sql
SELECT 
    flight_id,
    classification_text,
    processing_time_sec,
    created_at
FROM live.ai_classifications
ORDER BY created_at DESC
LIMIT 10;
```

### Join with Flight Metadata

```sql
SELECT 
    c.classification_text,
    m.callsign,
    m.origin_airport,
    m.destination_airport,
    c.created_at
FROM live.ai_classifications c
JOIN live.flight_metadata m ON c.flight_id = m.flight_id
ORDER BY c.created_at DESC;
```

### Failed Classifications (Debugging)

```sql
SELECT 
    flight_id,
    error_message,
    processing_time_sec,
    created_at
FROM live.ai_classifications
WHERE error_message IS NOT NULL
ORDER BY created_at DESC;
```

## Example Classifications

Real-world examples from the system:

| Flight ID | Classification | Context |
|-----------|---------------|---------|
| 3d7211ef | Weather Avoidance Route | Storm bypass via Lebanon |
| 3cf959dd | Technical Emergency Return | Multiple hold patterns before landing |
| 3ad2166a | Diplomatic Avoidance Maneuver | Israeli-Iranian tensions |
| 3adf2c74 | Missile Defense Holding | Iranian missile strike |
| 3bacace0 | Intelligence Gathering Mission | US drone patrol pattern |
| 3b5d3b75 | Covert Military Transit | US flight via Cyprus to Israel |

## Configuration Options

### Customize Thread Pool

Limit concurrent classifications to reduce API load:

```python
# In monitor.py __init__
self.ai_classifier = AIClassifier(
    gemini_api_key, 
    schema=self.schema,
    max_workers=1  # Default: 2
)
```

### Change AI Model

Modify the model in `ai_classify.py`:

```python
# In _call_gemini_api method
response = self.gemini_client.models.generate_content(
    model="gemini-2.5-pro",  # More powerful (slower/expensive)
    # model="gemini-3-flash-preview",  # Default (fast/cheap)
    config=config,
    contents=[content]
)
```

### Customize System Prompt

Edit the `SYSTEM_INSTRUCTION` in `ai_classify.py` to change classification style:

```python
SYSTEM_INSTRUCTION = """Your custom instruction here..."""
```

## Performance

### Typical Metrics

- **Processing Time**: 3-5 seconds per classification
- **API Latency**: 2-3 seconds
- **Map Generation**: 0.5-1 second
- **Database Save**: < 100ms

### Resource Usage

- **Memory**: ~50MB per worker thread
- **CPU**: Minimal (mostly I/O wait)
- **Network**: ~100KB per classification (with image)

### Cost Estimates

**Gemini API Pricing:**
- Free tier: 15 requests/minute, 1500 requests/day
- Typical monitor: 10-50 classifications/hour
- Monthly cost (free tier): $0
- Monthly cost (paid): $0.50 - $5.00

## Troubleshooting

### AI Classification Not Enabled

**Symptom**: Log shows "AI Classification disabled (GEMINI_API_KEY not set)"

**Solution**:
```bash
# Check if key is set
echo $GEMINI_API_KEY

# Set it if missing
export GEMINI_API_KEY="your_key_here"

# Restart monitor
python monitor.py
```

### API Key Invalid

**Symptom**: "Failed to initialize AI Classifier" or "401 Unauthorized"

**Solution**:
1. Verify key is correct: https://aistudio.google.com/app/apikey
2. Check for leading/trailing spaces: `echo "$GEMINI_API_KEY" | cat -A`
3. Regenerate key if necessary

### Classification Failures

**Symptom**: Errors in log like "Gemini API call failed"

**Common causes**:
- API rate limits exceeded → Reduce max_workers or add delays
- Network connectivity issues → Check firewall/proxy settings
- Quota exhausted → Check Google Cloud Console quotas
- Image too large → Reduce map size in `generate_flight_map()`

**Debug query**:
```sql
SELECT flight_id, error_message, created_at
FROM live.ai_classifications
WHERE error_message IS NOT NULL
ORDER BY created_at DESC
LIMIT 20;
```

### Map Generation Fails

**Symptom**: "Failed to generate flight map" warnings

**Solution**:
```bash
# Check staticmap installation
pip show staticmap

# Reinstall if needed
pip install --force-reinstall staticmap Pillow

# Test map generation
python -c "from ai_helpers import generate_flight_map; print('OK' if generate_flight_map else 'FAIL')"
```

### Database Table Not Created

**Symptom**: "relation ai_classifications does not exist"

**Solution**:
```sql
-- Manually create the table
\i create_ai_classifications_table.sql

-- Or use Python
python -c "from pg_provider import create_ai_classifications_table; create_ai_classifications_table('live')"
```

## Disabling AI Classification

If you want to disable AI classification without removing the code:

### Method 1: Don't Set API Key
Simply don't set `GEMINI_API_KEY` - the monitor will run normally without AI classification.

### Method 2: Comment Out Initialization
In `monitor.py`, comment out the classifier initialization:

```python
# self.ai_classifier = AIClassifier(gemini_api_key, schema=self.schema)
self.ai_classifier = None
```

### Method 3: Skip Anomalies
Modify the trigger condition:

```python
# Only classify specific types
if is_anomaly and self.ai_classifier and metadata_dict.get('is_military'):
    self.ai_classifier.classify_async(...)
```

## Advanced Usage

### Batch Classification

Classify historical flights:

```python
from ai_classify import AIClassifier
from pg_provider import get_connection

# Initialize classifier
classifier = AIClassifier(api_key="your_key", schema="research")

# Fetch unclassified anomalies
with get_connection() as conn:
    cursor = conn.cursor()
    cursor.execute("""
        SELECT flight_id 
        FROM research.anomaly_reports ar
        LEFT JOIN research.ai_classifications ac ON ar.flight_id = ac.flight_id
        WHERE ar.is_anomaly = TRUE 
        AND ac.flight_id IS NULL
        LIMIT 100
    """)
    
    for (flight_id,) in cursor.fetchall():
        # Fetch flight data and trigger classification
        # ... (implementation left to user)
        pass

# Wait for completion
classifier.shutdown(wait=True)
```

### Custom Classification Prompts

Override the system instruction per-flight:

```python
# In ai_classify.py, modify _call_gemini_api to accept custom prompt
config = self.types.GenerateContentConfig(
    system_instruction=custom_prompt or self.SYSTEM_INSTRUCTION,
    tools=[...]
)
```

## Integration with UI

The classification results can be displayed in your UI:

```javascript
// Fetch classification for a flight
fetch(`/api/flights/${flightId}/ai-classification`)
  .then(r => r.json())
  .then(data => {
    console.log("AI Classification:", data.classification_text);
  });
```

## Contributing

To improve the AI classification system:

1. **Enhance Prompts**: Edit `SYSTEM_INSTRUCTION` in `ai_classify.py`
2. **Add Context**: Modify `build_anomaly_context()` in `ai_helpers.py`
3. **Improve Maps**: Enhance `generate_flight_map()` in `ai_helpers.py`
4. **Add Models**: Support other AI models (OpenAI, Claude, etc.)

## FAQ

**Q: Can I use a different AI model?**  
A: Yes, modify `ai_classify.py` to use OpenAI, Claude, or any other LLM API.

**Q: How do I bulk classify historical flights?**  
A: See "Advanced Usage - Batch Classification" section above.

**Q: Can I customize the output format?**  
A: Yes, modify the `SYSTEM_INSTRUCTION` to request different formats (JSON, longer descriptions, etc.)

**Q: What happens if Gemini is down?**  
A: Classifications fail gracefully, errors are logged and stored in database. Monitor continues running normally.

**Q: Can I use this with other schemas (research, etc.)?**  
A: Yes, pass `schema="research"` when initializing AIClassifier.

## Support

For issues, questions, or feature requests:
- Check logs: `tail -f live_monitor.log`
- Review database errors: Query `ai_classifications` WHERE `error_message IS NOT NULL`
- See full documentation: `ENV_CONFIG.md`

## License

Same as the parent project.
