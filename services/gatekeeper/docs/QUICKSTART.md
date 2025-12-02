# Gatekeeper Quick Start Guide

Get the split-architecture gatekeeper up and running in 5 minutes.

## Prerequisites

- Docker and Docker Compose installed
- MLflow service running with trained model
- Kafka and Redis running

## Quick Start

### 1. Start Both Services

```bash
# From project root
docker compose up -d gatekeeper-api gatekeeper-consumer
```

### 2. Verify API is Running

```bash
curl http://localhost:8000/health
```

**Expected output**:
```json
{
  "status": "healthy",
  "model_loaded": true,
  "redis_connected": true,
  "consumer_running": false
}
```

### 3. Verify Consumer is Running

```bash
docker compose logs gatekeeper-consumer --tail 20
```

**Expected output**:
```
gatekeeper-consumer | ============================================================
gatekeeper-consumer | Gatekeeper Kafka Consumer (Standalone)
gatekeeper-consumer | ============================================================
gatekeeper-consumer | Step 1/3: Loading model from MLflow...
gatekeeper-consumer | Model loaded successfully: isolation-forest-bot-detector version 2
gatekeeper-consumer | Step 2/3: Connecting to Redis...
gatekeeper-consumer | Connected to Redis at redis:6379
gatekeeper-consumer | Step 3/3: Starting Kafka consumer loop...
gatekeeper-consumer | Consumer listening to raw-clickstream
```

### 4. Test with Data

```bash
# Start data producer
docker compose up -d data_producer

# Watch events being processed
docker compose logs -f gatekeeper-consumer
```

**You should see**:
```
Clean event from user 12345 (velocity: 5.23s)
Clean event from user 67890 (velocity: 2.15s)
Anomaly detected for user 99999 (velocity: 0.05s)
User 99999 has been banned for 600 seconds
```

## Common Commands

### View Status
```bash
# Check all services
docker compose ps

# Should show:
# gatekeeper-api        Up      0.0.0.0:8000->8000/tcp
# gatekeeper-consumer   Up
```

### View Logs
```bash
# API logs
docker compose logs -f gatekeeper-api

# Consumer logs
docker compose logs -f gatekeeper-consumer

# Both
docker compose logs -f gatekeeper-api gatekeeper-consumer
```

### Restart Services
```bash
# Restart both
docker compose restart gatekeeper-api gatekeeper-consumer

# Restart just consumer
docker compose restart gatekeeper-consumer

# Restart just API
docker compose restart gatekeeper-api
```

### Stop Services
```bash
# Stop both
docker compose stop gatekeeper-api gatekeeper-consumer

# Stop just consumer (keep API for health checks)
docker compose stop gatekeeper-consumer
```

### Rebuild After Code Changes
```bash
# Rebuild and restart
docker compose build gatekeeper-api gatekeeper-consumer
docker compose up -d gatekeeper-api gatekeeper-consumer
```

## Testing

### Test Manual Prediction
```bash
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{
    "visitorid": "test123",
    "timestamp": 1672531200000
  }'
```

**Expected output**:
```json
{
  "is_anomaly": false,
  "time_since_last_event_sec": 3600.0,
  "prediction": 1
}
```

### Check Clean Events Topic
```bash
docker exec -it shielded-recommender-kafka-1 \
  kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic clean-events \
  --from-beginning \
  --max-messages 5
```

### Check Suspicious Events Topic
```bash
docker exec -it shielded-recommender-kafka-1 \
  kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic suspicious-events \
  --from-beginning
```

### Check Banned Users in Redis
```bash
docker compose exec redis redis-cli ZRANGE banned_users_with_ttl 0 -1 WITHSCORES
```

## Troubleshooting

### Problem: API returns 500 error
**Solution**: Check logs
```bash
docker compose logs gatekeeper-api --tail 50
```
Look for model loading errors or Redis connection issues.

### Problem: Consumer not processing events
**Solution**: Verify dependencies
```bash
# Check Kafka is running
docker compose ps kafka

# Check data producer is running
docker compose ps data_producer

# Check consumer logs for errors
docker compose logs gatekeeper-consumer --tail 50
```

### Problem: "Model not found" error
**Solution**: Train and register the model first
```bash
# Run training script
PYTHONPATH=. MLFLOW_TRACKING_URI="http://localhost:5001" \
  python services/trainer/src/train.py

# Verify model exists
curl http://localhost:5001/api/2.0/mlflow/registered-models/get?name=isolation-forest-bot-detector
```

### Problem: Consumer keeps restarting
**Solution**: Check resource limits
```bash
# View container stats
docker stats shielded-recommender-gatekeeper-consumer-1

# If memory is maxed out, increase limit in docker-compose.yml:
gatekeeper-consumer:
  deploy:
    resources:
      limits:
        memory: 2G
```

## Next Steps

- **Scale the consumer**: See [SPLIT_ARCHITECTURE.md](SPLIT_ARCHITECTURE.md#scaling-strategies)
- **Monitor performance**: Set up Prometheus metrics
- **Production deployment**: See [DEPLOYMENT.md](DEPLOYMENT.md)
- **Understand the code**: See [README.md](README.md)

## Architecture Diagram

```
User Request → gatekeeper-api → /health, /predict
                                 ↓
                              ML Model
                                 ↓
                               Redis

Kafka Stream → gatekeeper-consumer → Process Event
                                       ↓
                                    ML Model
                                       ↓
                                    Redis
                                       ↓
                              clean-events / suspicious-events
```

## Quick Reference

| Task | Command |
|------|---------|
| Start services | `docker compose up -d gatekeeper-api gatekeeper-consumer` |
| Check health | `curl http://localhost:8000/health` |
| View consumer logs | `docker compose logs -f gatekeeper-consumer` |
| Test prediction | `curl -X POST http://localhost:8000/predict -H "Content-Type: application/json" -d '{"visitorid":"123","timestamp":1672531200000}'` |
| Restart | `docker compose restart gatekeeper-api gatekeeper-consumer` |
| Stop | `docker compose stop gatekeeper-api gatekeeper-consumer` |
| Scale consumer | `docker compose up -d --scale gatekeeper-consumer=3` |

## Support

For detailed documentation:
- [README.md](README.md) - Full service documentation
- [SPLIT_ARCHITECTURE.md](SPLIT_ARCHITECTURE.md) - Architecture details
- [DEPLOYMENT.md](DEPLOYMENT.md) - Production deployment
- [../../Guide.md](../../Guide.md) - Project guide (Phase 3)
