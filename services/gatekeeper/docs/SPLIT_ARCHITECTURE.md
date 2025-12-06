# Split Architecture: API + Consumer

The gatekeeper service is now split into two independent processes for production scalability.

## Architecture Overview

```
┌────────────────────────────────────────────────────────────┐
│                    Docker Compose                          │
├────────────────────────────────────────────────────────────┤
│                                                            │
│  ┌─────────────────────┐      ┌─────────────────────────┐ │
│  │  gatekeeper-api     │      │  gatekeeper-consumer    │ │
│  │  (Port 8000)        │      │  (No ports)             │ │
│  ├─────────────────────┤      ├─────────────────────────┤ │
│  │ FastAPI App         │      │ Kafka Consumer Loop     │ │
│  │                     │      │                         │ │
│  │ ✓ Health checks     │      │ ✓ Stream processing     │ │
│  │ ✓ Manual predictions│      │ ✓ Anomaly detection     │ │
│  │ ✓ Metrics           │      │ ✓ User banning          │ │
│  │ ✓ No Kafka consumer │      │ ✓ Event routing         │ │
│  └──────┬──────────────┘      └─────────┬───────────────┘ │
│         │                               │                  │
│         └───────────┬───────────────────┘                  │
│                     │                                      │
│         ┌───────────┴────────────┐                        │
│         │  Shared Dependencies   │                        │
│         ├────────────────────────┤                        │
│         │ • MLflow (model)       │                        │
│         │ • Redis (state)        │                        │
│         │ • Kafka (topics)       │                        │
│         └────────────────────────┘                        │
└────────────────────────────────────────────────────────────┘
```

## Services

### 1. gatekeeper-api
**Purpose**: HTTP API for health checks and testing

**Responsibilities**:
- Serve health check endpoint (`GET /health`)
- Provide manual prediction endpoint (`POST /predict`)
- Load and hold ML model in memory
- Connect to Redis for state queries

**Does NOT**:
- ❌ Consume from Kafka
- ❌ Process streaming events
- ❌ Run background threads

**Docker Configuration**:
```yaml
gatekeeper-api:
  ports:
    - '8000:8000'
  environment:
    - START_CONSUMER=false  # Disable consumer
  command: ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 2. gatekeeper-consumer
**Purpose**: Real-time stream processing

**Responsibilities**:
- Consume events from `raw-clickstream` topic
- Calculate session velocity features
- Run anomaly detection on each event
- Route events to `clean-events` or `suspicious-events`
- Ban suspicious users in Redis

**Does NOT**:
- ❌ Expose HTTP endpoints
- ❌ Handle API requests
- ❌ Serve metrics directly

**Docker Configuration**:
```yaml
gatekeeper-consumer:
  # No ports exposed
  environment:
    - MLFLOW_TRACKING_URI=http://mlflow:5000
  command: ["python", "-m", "src.consumer"]
  restart: unless-stopped  # Auto-restart on crash
```

## Benefits

| Aspect | Monolithic (Old) | Split Architecture (New) |
|--------|------------------|--------------------------|
| **Scaling** | Scale everything together | Scale API and consumer independently |
| **Resource Allocation** | Same CPU/memory for both | Optimize resources per service |
| **Fault Isolation** | One crash stops both | Failures are isolated |
| **Deployment** | Full restart required | Update API without restarting consumer |
| **Monitoring** | Mixed logs | Clear separation of concerns |
| **Development** | Test both together | Test API and consumer independently |

## Deployment Commands

### Start Both Services
```bash
docker compose up -d gatekeeper-api gatekeeper-consumer
```

### Start API Only (for testing)
```bash
docker compose up -d gatekeeper-api
```

### Start Consumer Only (for stream processing)
```bash
docker compose up -d gatekeeper-consumer
```

### Scale Consumer (Multiple Instances)
```bash
docker compose up -d --scale gatekeeper-consumer=3
```
This starts 3 consumer instances that share the Kafka partition load.

### View Logs Separately
```bash
# API logs
docker compose logs -f gatekeeper-api

# Consumer logs
docker compose logs -f gatekeeper-consumer

# Both
docker compose logs -f gatekeeper-api gatekeeper-consumer
```

## Monitoring

### API Health Check
```bash
curl http://localhost:8000/health
```

**Response**:
```json
{
  "status": "healthy",
  "model_loaded": true,
  "redis_connected": true,
  "consumer_running": false  # ← Always false in split mode
}
```

### Consumer Health
Check logs for activity:
```bash
docker compose logs gatekeeper-consumer --tail 20

# Should see:
# "Consumer listening to raw-clickstream"
# "Clean event from user 12345 (velocity: 5.23s)"
# "Anomaly detected for user 67890 (velocity: 0.05s)"
```

### Check Consumer is Running
```bash
docker compose ps gatekeeper-consumer

# Should show: State: Up
```

## Scaling Strategies

### Vertical Scaling
Allocate more resources to each service:

```yaml
gatekeeper-consumer:
  deploy:
    resources:
      limits:
        cpus: '2.0'
        memory: 2G
      reservations:
        cpus: '1.0'
        memory: 1G
```

### Horizontal Scaling
Run multiple consumer instances:

```bash
# Method 1: Docker Compose scale
docker compose up -d --scale gatekeeper-consumer=3

# Method 2: Kubernetes ReplicaSet
apiVersion: apps/v1
kind: Deployment
metadata:
  name: gatekeeper-consumer
spec:
  replicas: 3  # ← Multiple consumers
```

**How it works**:
- All consumers join the same Kafka consumer group (`gatekeeper-service`)
- Kafka automatically distributes partitions among consumers
- Each consumer processes different events (no duplication)

**Optimal scaling**:
- Max consumers = number of Kafka topic partitions
- For `raw-clickstream` with 6 partitions → max 6 consumers
- More than 6 consumers = some will be idle

## Testing the Split Architecture

### 1. Start All Services
```bash
docker compose up -d
```

### 2. Verify API is Running
```bash
curl http://localhost:8000/health

# Should return: {"status": "healthy", ...}
```

### 3. Verify Consumer is Running
```bash
docker compose logs gatekeeper-consumer | grep "Consumer listening"

# Should see: "Consumer listening to raw-clickstream"
```

### 4. Send Test Events
```bash
# Start data producer
docker compose up -d data_producer

# Check consumer is processing
docker compose logs -f gatekeeper-consumer

# Should see events being processed
```

### 5. Test Manual Prediction (API)
```bash
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"visitorid": "test123", "timestamp": 1672531200000}'

# Should return: {"is_anomaly": false, ...}
```

### 6. Monitor Topics
```bash
# Check clean events are being produced
docker exec -it shielded-recommender-kafka-1 \
  kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic clean-events \
  --from-beginning \
  --max-messages 10

# Check suspicious events
docker exec -it shielded-recommender-kafka-1 \
  kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic suspicious-events \
  --from-beginning
```

## Troubleshooting

### Consumer Not Starting
**Symptom**: `docker compose ps` shows consumer as "Exited"

**Check logs**:
```bash
docker compose logs gatekeeper-consumer --tail 50
```

**Common issues**:
1. Model not found in MLflow → Check MLflow is running and model is registered
2. Kafka connection failed → Check Kafka is healthy: `docker compose ps kafka`
3. Redis connection failed → Check Redis: `docker compose ps redis`

### Consumer Crashing
**Symptom**: Container keeps restarting

**Check for**:
- Memory issues: Increase `--memory` limit
- Model loading errors: Verify model compatibility
- Kafka consumer timeout: Adjust `consumer_timeout_ms`

### Events Not Being Processed
**Symptom**: No logs showing event processing

**Verify**:
1. Data producer is running: `docker compose ps data_producer`
2. Events exist in topic: Use kafka-ui at http://localhost:8081
3. Consumer group lag: Check consumer group `gatekeeper-service` in kafka-ui

### API Can't Reach MLflow/Redis
**Symptom**: Health check shows `model_loaded: false`

**Fix**:
```bash
# Check MLflow
curl http://localhost:5000/health

# Check Redis
docker compose exec redis redis-cli PING

# Restart API
docker compose restart gatekeeper-api
```

## Migration from Monolithic

If you were using the old single-container setup:

### Old (Single Container)
```yaml
gatekeeper:
  environment:
    - START_CONSUMER=true  # Both API and consumer
```

### New (Split Architecture)
```yaml
gatekeeper-api:
  environment:
    - START_CONSUMER=false  # API only

gatekeeper-consumer:
  command: ["python", "-m", "src.consumer"]  # Consumer only
```

### Migration Steps
1. Stop old gatekeeper: `docker compose stop gatekeeper`
2. Start new services: `docker compose up -d gatekeeper-api gatekeeper-consumer`
3. Verify both are running: `docker compose ps`
4. Check logs for errors: `docker compose logs`
5. Remove old service from docker-compose.yml (if satisfied)

## Performance Tuning

### Consumer Throughput
Increase batch size in `main.py`:
```python
consumer = KafkaConsumer(
    max_poll_records=500,  # Process 500 events per batch
    fetch_min_bytes=1024,  # Wait for 1KB of data
)
```

### API Response Time
Use connection pooling for Redis:
```python
redis_pool = redis.ConnectionPool(
    host=REDIS_HOST,
    port=REDIS_PORT,
    max_connections=50
)
redis_client = redis.Redis(connection_pool=redis_pool)
```

### Resource Optimization
```yaml
gatekeeper-api:
  deploy:
    resources:
      limits:
        cpus: '0.5'     # API is lightweight
        memory: 512M

gatekeeper-consumer:
  deploy:
    resources:
      limits:
        cpus: '2.0'     # Consumer needs more CPU
        memory: 2G      # Model + processing
```

## Best Practices

1. **Always run both services in production**
   - API for monitoring and health checks
   - Consumer for actual work

2. **Monitor consumer lag**
   - Use kafka-ui or Prometheus to track lag
   - Alert if lag grows beyond threshold

3. **Set up proper logging**
   - Structured logs (JSON format)
   - Ship to centralized logging (ELK, Loki, etc.)

4. **Use health checks**
   - API has `/health` endpoint
   - Consumer: monitor process is alive + no errors in logs

5. **Graceful shutdowns**
   - Always use `docker compose stop` (not `kill`)
   - Consumer finishes processing current event before exiting

6. **Resource limits**
   - Set memory limits to prevent OOM
   - Set CPU limits for fair resource sharing

7. **Auto-restart**
   - Consumer has `restart: unless-stopped`
   - Ensures resilience against transient failures

## Further Reading

- [Main README](README.md) - Service overview
- [DEPLOYMENT.md](DEPLOYMENT.md) - Detailed deployment guide
- [YIELD_EXPLAINED.md](YIELD_EXPLAINED.md) - Understanding FastAPI lifespan
- [../MLFLOW_VERSION_GUIDE.md](../../MLFLOW_VERSION_GUIDE.md) - MLflow compatibility
