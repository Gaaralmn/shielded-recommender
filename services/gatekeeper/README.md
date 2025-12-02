# Gatekeeper Service

Real-time anomaly detection service that filters bot traffic from the clickstream using ML-based detection.

## 📚 Table of Contents

### Quick Start & Guides
- **[Quick Start Guide](docs/QUICKSTART.md)** - Get started in 5 minutes
- **[Local Testing](docs/LOCAL_TESTING.md)** - Complete guide for running locally
- **[Local Quick Start](docs/LOCAL_QUICK_START.md)** - Quick reference for local development

### Architecture & Design
- **[Split Architecture](docs/SPLIT_ARCHITECTURE.md)** - API and Consumer separation explained
- **[Why Consumer Needs Model and Redis](docs/WHY_CONSUMER_NEEDS_MODEL_AND_REDIS.md)** - Architectural decisions
- **[Yield Explained](docs/YIELD_EXPLAINED.md)** - Understanding Python generators and context managers

### Bot Detection & ML
- **[ML Model Approach](docs/ML_MODEL_APPROACH.md)** - How the ML-based bot detection works
- **[Bot Detection Explained](docs/BOT_DETECTION_EXPLAINED.md)** - Original hybrid detection approach
- **[Timestamp Formats](docs/TIMESTAMP_FORMATS.md)** - Supported timestamp formats and conversion

### Deployment
- **[Deployment Guide](docs/DEPLOYMENT.md)** - Production deployment strategies
- **[Dockerfile Comparison](docs/DOCKERFILE_COMPARISON.md)** - Choosing the right Dockerfile strategy

---

## Overview

The Gatekeeper service uses **machine learning** (Isolation Forest) combined with threshold-based rules to detect and block bot traffic in real-time.

### Key Features

- ✅ **ML-Based Detection**: Isolation Forest trained on normal user behavior
- ✅ **Hybrid Approach**: Combines threshold rules (< 1s) + ML model (1-15s)
- ✅ **Real-time Processing**: Kafka stream processing with <10ms latency
- ✅ **Automatic Banning**: Redis-based user banning with TTL
- ✅ **Split Architecture**: Separate API and consumer for independent scaling

## Architecture

```
┌─────────────────┐
│  raw-clickstream│
│     (Kafka)     │
└────────┬────────┘
         │
         ▼
┌─────────────────────────┐
│   Gatekeeper Service    │
│                         │
│  ┌──────────────────┐  │
│  │  FastAPI API     │  │  ← Health checks, manual predictions
│  └──────────────────┘  │
│                         │
│  ┌──────────────────┐  │
│  │ Kafka Consumer   │  │  ← Real-time stream processing
│  └──────────────────┘  │
│           │             │
│    ┌──────┴──────┐     │
│    ▼             ▼      │
│  ┌────┐      ┌─────┐   │
│  │MLflow│    │Redis│   │  ← ML Model + User State
│  └────┘      └─────┘   │
└─────────┬───────┬───────┘
          │       │
     ┌────┴──┐ ┌──┴─────────┐
     ▼       │ ▼            │
┌────────┐  │ ┌──────────┐ │
│ clean  │  │ │suspicious│ │
│ events │  │ │  events  │ │
└────────┘  │ └──────────┘ │
            │              │
            └──────────────┘
          Ban user in Redis
```

## Bot Detection Strategy

### Hybrid Detection Approach

1. **Threshold Rule (< 1s)**: Fast detection for obvious bots
2. **ML Model (1-15s)**: Isolation Forest detects sophisticated bots
3. **Normal (30s+)**: Passed through as legitimate traffic

```
Time Gap    | Detection Method | Result
------------------------------------------------
< 1s        | Threshold rule   | ⚡ Bot (threshold)
1-15s       | ML Model (IF)    | 🤖 Bot (ML detected!)
30-3600s    | None             | ✓ Normal
```

See **[ML Model Approach](docs/ML_MODEL_APPROACH.md)** for detailed explanation.

## Quick Start

### Using Docker (Recommended)

```bash
# Start all services
docker compose up -d

# Check health
curl http://localhost:8000/health

# View logs
docker compose logs -f gatekeeper-api gatekeeper-consumer
```

### Local Development

```bash
# Terminal 1: Start API
cd services/gatekeeper
./run-api.sh

# Terminal 2: Start Consumer
cd services/gatekeeper
./run-consumer.sh
```

See **[Local Quick Start](docs/LOCAL_QUICK_START.md)** for details.

## Testing Bot Detection

### Run the test script

```bash
cd services/gatekeeper
python test_anomaly.py
```

### Expected Output

```
Event 2 (+50ms):
  Detection method: threshold
  ⚠️  ANOMALY DETECTED!

Event 5 (+1500ms):
  Detection method: model  # ← ML Model detected this!
  ⚠️  ANOMALY DETECTED!
```

### Manual Testing

```bash
# Send rapid-fire events (will be flagged)
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"visitorid":"bot-test","timestamp":1672531200000}'

curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"visitorid":"bot-test","timestamp":1672531200050}'
# ↑ 50ms gap → Detected as bot
```

## Configuration

Environment variables (with defaults):

```bash
# MLflow
MLFLOW_TRACKING_URI=http://mlflow:5000
MODEL_NAME=isolation-forest-bot-detector

# Kafka
KAFKA_BOOTSTRAP_SERVERS=kafka:9092

# Redis
REDIS_HOST=redis
REDIS_PORT=6379

# Bot Detection
BOT_VELOCITY_THRESHOLD_SEC=1.0    # Threshold for rapid-fire detection

# Timeouts
USER_BAN_TTL_SECONDS=600          # 10 minutes
USER_HISTORY_TTL_SECONDS=3600     # 1 hour
```

## API Endpoints

### GET /
Service status and information

### GET /health
Health check with component status
```json
{
  "status": "healthy",
  "model_loaded": true,
  "redis_connected": true,
  "consumer_running": false
}
```

### POST /predict
Manual prediction for testing
```bash
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{
    "visitorid": "12345",
    "timestamp": 1672531200000
  }'
```

Response:
```json
{
  "is_anomaly": false,
  "time_since_last_event_sec": 3600.0,
  "detection_method": "none",
  "velocity_threshold": 1.0
}
```

## Monitoring

### Key Metrics to Monitor
- Consumer lag (Kafka)
- Event processing rate
- Anomaly detection rate (threshold vs ML)
- Redis memory usage
- Model inference latency

### Health Check

```bash
# Check all components
curl http://localhost:8000/health

# Check banned users in Redis
docker compose exec redis redis-cli ZRANGE banned_users_with_ttl 0 -1 WITHSCORES
```

### Logs to Watch

```bash
# Successful detection
"🤖 Bot detected for user 67890: rapid-fire (velocity: 0.0500s < 1.0s)"
"🤖 Bot detected for user 12345: model anomaly (velocity: 1.50s)"

# Normal traffic
"✓ Clean event from user 99999 (velocity: 5.23s)"
```

## Troubleshooting

### Model Not Detecting Bots

**Symptom**: All events classified as normal

**Solution**:
1. Check model version: Latest is **v7** with contamination=0.15
2. Retrain if needed: `docker compose run --rm trainer`
3. Verify threshold: `BOT_VELOCITY_THRESHOLD_SEC=1.0`

See **[ML Model Approach](docs/ML_MODEL_APPROACH.md)** for training details.

### Consumer Not Starting

**Symptom**: `consumer_running: false` in health check

**Solution**:
```bash
# Check logs
docker compose logs gatekeeper-consumer --tail 100

# Ensure dependencies are running
docker compose up -d kafka redis mlflow

# Restart consumer
docker compose restart gatekeeper-consumer
```

### High Memory Usage

**Causes**:
1. Too many user histories in Redis → Reduce TTL
2. Kafka messages piling up → Increase `max_poll_records`

**Solution**:
```bash
# Check Redis memory
docker compose exec redis redis-cli INFO memory

# Check container stats
docker stats shielded-recommender-gatekeeper-consumer-1
```

## Development

### Project Structure

```
services/gatekeeper/
├── src/
│   ├── __init__.py
│   ├── main.py              # FastAPI app + detection logic
│   └── consumer.py          # Standalone consumer script
├── docs/                    # Documentation
│   ├── QUICKSTART.md
│   ├── ML_MODEL_APPROACH.md
│   ├── DEPLOYMENT.md
│   └── ...
├── tests/
│   └── __init__.py
├── requirements.txt         # Python dependencies
├── Dockerfile              # Container definition
├── run-api.sh              # Local API startup script
├── run-consumer.sh         # Local consumer startup script
├── test_anomaly.py         # Bot detection test script
└── README.md               # This file
```

### Running Tests

```bash
# Test anomaly detection
python test_anomaly.py

# Integration test with full pipeline
docker compose up -d
docker compose logs -f gatekeeper-consumer
```

### Local Development

See **[Local Testing](docs/LOCAL_TESTING.md)** for complete setup instructions.

## Production Deployment

For production deployment:
- See **[Deployment Guide](docs/DEPLOYMENT.md)** for scaling strategies
- See **[Split Architecture](docs/SPLIT_ARCHITECTURE.md)** for API/Consumer separation
- See **[Dockerfile Comparison](docs/DOCKERFILE_COMPARISON.md)** for container optimization

## Related Documentation

- [MLflow Version Guide](../../MLFLOW_VERSION_GUIDE.md)
- [Project Guide](../../Guide.md) - Phase 3: API - Implementing the Gatekeeper
- [Trainer Service](../trainer/) - Model training and MLflow setup

## Contributing

When adding new documentation:
1. Create the `.md` file in the `docs/` folder
2. Add an entry to the Table of Contents above
3. Use descriptive titles and clear sections
4. Include code examples where relevant

---

**Last Updated**: December 2025
**Model Version**: 7 (Isolation Forest with contamination=0.15)
