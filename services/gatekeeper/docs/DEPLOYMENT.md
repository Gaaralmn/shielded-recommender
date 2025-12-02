# Gatekeeper Service Deployment Guide

## How the Consumer Runs in Production

### The Problem
When you run a FastAPI app with uvicorn (`uvicorn src.main:app`), the `if __name__ == "__main__"` block **never executes** because uvicorn imports the module instead of running it as a script.

### Current Implementation: Background Thread Approach

**How it works:**
1. When FastAPI starts up, the `@app.on_event("startup")` handler runs
2. This creates a background thread that runs `run_kafka_consumer()`
3. The consumer runs continuously while the FastAPI server handles HTTP requests
4. On shutdown, the consumer gracefully stops

**Code flow:**
```python
FastAPI starts
  ↓
@app.on_event("startup") triggered
  ↓
Load model from MLflow
Initialize Redis
  ↓
Start consumer thread (daemon=True)
  ↓
FastAPI ready to serve requests
```

**Advantages:**
- ✅ Simple deployment (single container)
- ✅ Easy to monitor (one service)
- ✅ Good for moderate load

**Disadvantages:**
- ⚠️ Consumer shares resources with API
- ⚠️ If one crashes, both restart
- ⚠️ Can't scale consumer independently

### Alternative: Separate Services (Production Best Practice)

For high-scale production, you should split into two services:

#### 1. Update docker-compose.yml

```yaml
services:
  # API service for health checks and manual predictions
  gatekeeper-api:
    build:
      context: .
      dockerfile: ./services/gatekeeper/Dockerfile
    ports:
      - '${GATEKEEPER_HOST_PORT:-8000}:8000'
    depends_on:
      - kafka
      - redis
      - mlflow
    volumes:
      - ./services/gatekeeper/src:/app/src
      - ./recommender_schemas:/app/recommender_schemas
    environment:
      - PYTHONPATH=/app
      - MLFLOW_TRACKING_URI=http://mlflow:5000
    command: ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]

  # Consumer service for stream processing
  gatekeeper-consumer:
    build:
      context: .
      dockerfile: ./services/gatekeeper/Dockerfile
    depends_on:
      - kafka
      - redis
      - mlflow
    volumes:
      - ./services/gatekeeper/src:/app/src
      - ./recommender_schemas:/app/recommender_schemas
    environment:
      - PYTHONPATH=/app
      - MLFLOW_TRACKING_URI=http://mlflow:5000
    # Run as standalone consumer script
    command: ["python", "-m", "src.consumer"]
```

#### 2. Create src/consumer.py

```python
# services/gatekeeper/src/consumer.py
"""
Standalone Kafka consumer script.
Run this separately from the FastAPI app in production.
"""
from src.main import (
    load_model_from_registry,
    initialize_redis,
    run_kafka_consumer
)

if __name__ == "__main__":
    load_model_from_registry()
    initialize_redis()
    run_kafka_consumer()
```

#### 3. Benefits of Separate Services

- ✅ **Independent scaling**: Scale consumer separately from API
- ✅ **Fault isolation**: API failure doesn't stop consumer
- ✅ **Resource allocation**: Different CPU/memory for each
- ✅ **Easier monitoring**: Separate logs and metrics
- ✅ **Zero-downtime deployments**: Update API without restarting consumer

## Current Deployment (Single Container)

The current implementation runs both API and consumer in one container:

```bash
# Start the gatekeeper service
docker compose up -d gatekeeper

# Check health (includes consumer status)
curl http://localhost:8000/health

# Expected response:
{
  "status": "healthy",
  "model_loaded": true,
  "redis_connected": true,
  "consumer_running": true
}
```

## Testing Locally

### Test with Docker
```bash
# Rebuild and start
docker compose build gatekeeper
docker compose up -d gatekeeper

# View logs
docker compose logs -f gatekeeper

# Should see:
# "Gatekeeper service starting up..."
# "Model loaded successfully: isolation-forest-bot-detector version X"
# "Connected to Redis at redis:6379"
# "Starting Kafka consumer..."
# "Consumer listening to raw-clickstream"
# "Gatekeeper service ready!"
```

### Test Manually (without Docker)
```bash
# Run as FastAPI app (consumer starts automatically)
MLFLOW_TRACKING_URI=http://localhost:5001 \
KAFKA_BOOTSTRAP_SERVERS=localhost:9092 \
REDIS_HOST=localhost \
uvicorn src.main:app --reload

# Or run as standalone consumer script
MLFLOW_TRACKING_URI=http://localhost:5001 \
KAFKA_BOOTSTRAP_SERVERS=localhost:9092 \
REDIS_HOST=localhost \
python services/gatekeeper/src/main.py
```

## Monitoring

### Check if consumer is running
```bash
curl http://localhost:8000/health | jq .consumer_running
```

### View consumer logs
```bash
docker compose logs gatekeeper | grep "Consumer"
```

### Test event processing
```bash
# Send a test event to Kafka (requires data_producer to be running)
docker compose up -d data_producer

# Check clean-events and suspicious-events topics
docker exec -it shielded-recommender-kafka-1 kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic clean-events \
  --from-beginning
```

## Graceful Shutdown

The consumer handles shutdown gracefully:

1. FastAPI receives shutdown signal
2. Sets `should_run_consumer = False`
3. Consumer finishes processing current event
4. Closes Kafka connections
5. Thread joins (max 10 seconds)
6. Service exits

```bash
# Graceful shutdown
docker compose stop gatekeeper

# Check logs for clean shutdown
docker compose logs gatekeeper | tail -20
# Should see: "Shutting down consumer..."
#             "Consumer shut down complete"
```

## Troubleshooting

### Consumer not starting
- Check Kafka is running: `docker compose ps kafka`
- Check logs: `docker compose logs gatekeeper`
- Verify network: Consumer retries 10 times with 5-second delays

### Consumer crashes
- Check if model loaded: `curl http://localhost:8000/health`
- Check Redis connection: `docker compose ps redis`
- Review error logs: `docker compose logs gatekeeper --tail 100`

### Events not being processed
- Verify data_producer is running: `docker compose ps data_producer`
- Check topic has messages: Use kafka-ui at http://localhost:8081
- Verify consumer group: Look for `gatekeeper-service` group in kafka-ui

## Production Recommendations

For production deployment:

1. **Use separate services** (gatekeeper-api + gatekeeper-consumer)
2. **Add health checks** to docker-compose and orchestrator
3. **Monitor consumer lag** using Kafka metrics
4. **Set up alerts** for consumer failures
5. **Use proper resource limits** in docker-compose
6. **Implement circuit breakers** for MLflow/Redis failures
7. **Add structured logging** for better observability
8. **Use Kubernetes** for true horizontal scaling

## Scaling Strategy

### Vertical Scaling (Current Setup)
- Increase container resources
- Tune Kafka consumer `max_poll_records`
- Adjust batch sizes

### Horizontal Scaling (Separate Services)
- Run multiple consumer instances
- Kafka partitions = max parallelism
- Load balance API instances

### Example: 3 Consumer Instances
```yaml
gatekeeper-consumer:
  deploy:
    replicas: 3  # Kubernetes/Docker Swarm
```

All consumers join the same `gatekeeper-service` consumer group, and Kafka automatically distributes partitions among them.
