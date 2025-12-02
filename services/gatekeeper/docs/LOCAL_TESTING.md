# Running Gatekeeper Locally (Without Docker)

This guide shows you how to run the gatekeeper API and consumer directly on your local machine for testing and development.

## Prerequisites

### 1. Python Environment
```bash
# Create a virtual environment
cd services/gatekeeper
python3 -m venv venv

# Activate it
source venv/bin/activate  # On macOS/Linux
# or
venv\Scripts\activate  # On Windows
```

### 2. Install Dependencies
```bash
# Make sure you're in the virtual environment
pip install -r requirements.txt
```

### 3. Required Services Running

You still need these services running (via Docker or locally):
- **Kafka** (port 9092)
- **Redis** (port 6379)
- **MLflow** (port 5001)
- **PostgreSQL** (for MLflow backend)

**Quick start for dependencies**:
```bash
# From project root, start just the infrastructure
docker compose up -d kafka redis mlflow postgres
```

## Running the Services

### Option 1: Run API Only

```bash
# From project root
cd services/gatekeeper

# Activate virtual environment
source venv/bin/activate

# Set environment variables
export PYTHONPATH="${PYTHONPATH}:$(pwd)/../.."
export MLFLOW_TRACKING_URI="http://localhost:5001"
export KAFKA_BOOTSTRAP_SERVERS="localhost:9092"
export REDIS_HOST="localhost"
export REDIS_PORT="6379"
export START_CONSUMER="false"  # API only

# Run the API
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

**What you'll see**:
```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started reloader process [12345] using StatReload
INFO:     Started server process [12346]
INFO:     Waiting for application startup.
INFO:     Gatekeeper API starting up...
INFO:     Connecting to MLflow at http://localhost:5001
INFO:     Loading model from models:/isolation-forest-bot-detector/2
INFO:     Model loaded successfully: isolation-forest-bot-detector version 2
INFO:     Connected to Redis at localhost:6379
INFO:     Consumer disabled (split-process mode - run consumer separately)
INFO:     Gatekeeper API ready!
INFO:     Application startup complete.
```

**Test it**:
```bash
# In another terminal
curl http://localhost:8000/health
```

### Option 2: Run Consumer Only

```bash
# From project root
cd services/gatekeeper

# Activate virtual environment
source venv/bin/activate

# Set environment variables
export PYTHONPATH="${PYTHONPATH}:$(pwd)/../.."
export MLFLOW_TRACKING_URI="http://localhost:5001"
export KAFKA_BOOTSTRAP_SERVERS="localhost:9092"
export REDIS_HOST="localhost"
export REDIS_PORT="6379"

# Run the consumer
python -m src.consumer
```

**What you'll see**:
```
2025-12-02 10:30:00,123 - [CONSUMER] - INFO - ============================================================
2025-12-02 10:30:00,124 - [CONSUMER] - INFO - Gatekeeper Kafka Consumer (Standalone)
2025-12-02 10:30:00,125 - [CONSUMER] - INFO - ============================================================
2025-12-02 10:30:00,126 - [CONSUMER] - INFO - Step 1/3: Loading model from MLflow...
2025-12-02 10:30:01,234 - INFO - Loading model from models:/isolation-forest-bot-detector/2
2025-12-02 10:30:02,345 - INFO - Model loaded successfully: isolation-forest-bot-detector version 2
2025-12-02 10:30:02,346 - [CONSUMER] - INFO - Step 2/3: Connecting to Redis...
2025-12-02 10:30:02,456 - INFO - Connected to Redis at localhost:6379
2025-12-02 10:30:02,457 - [CONSUMER] - INFO - Step 3/3: Starting Kafka consumer loop...
2025-12-02 10:30:03,567 - INFO - Consumer listening to raw-clickstream
2025-12-02 10:30:03,568 - INFO - Will route to: clean-events (clean) and suspicious-events (suspicious)
```

### Option 3: Run Both (API + Consumer)

**Terminal 1 - API**:
```bash
cd services/gatekeeper
source venv/bin/activate

export PYTHONPATH="${PYTHONPATH}:$(pwd)/../.."
export MLFLOW_TRACKING_URI="http://localhost:5001"
export KAFKA_BOOTSTRAP_SERVERS="localhost:9092"
export REDIS_HOST="localhost"
export START_CONSUMER="false"

uvicorn src.main:app --reload --port 8000
```

**Terminal 2 - Consumer**:
```bash
cd services/gatekeeper
source venv/bin/activate

export PYTHONPATH="${PYTHONPATH}:$(pwd)/../.."
export MLFLOW_TRACKING_URI="http://localhost:5001"
export KAFKA_BOOTSTRAP_SERVERS="localhost:9092"
export REDIS_HOST="localhost"

python -m src.consumer
```

## Helper Scripts

Create these helper scripts for easier local testing:

### `run-api.sh`
```bash
#!/bin/bash
# services/gatekeeper/run-api.sh

# Activate virtual environment
source venv/bin/activate

# Set environment
export PYTHONPATH="${PYTHONPATH}:$(pwd)/../.."
export MLFLOW_TRACKING_URI="http://localhost:5001"
export KAFKA_BOOTSTRAP_SERVERS="localhost:9092"
export REDIS_HOST="localhost"
export REDIS_PORT="6379"
export START_CONSUMER="false"

echo "Starting Gatekeeper API on http://localhost:8000"
echo "Press Ctrl+C to stop"
echo ""

uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

### `run-consumer.sh`
```bash
#!/bin/bash
# services/gatekeeper/run-consumer.sh

# Activate virtual environment
source venv/bin/activate

# Set environment
export PYTHONPATH="${PYTHONPATH}:$(pwd)/../.."
export MLFLOW_TRACKING_URI="http://localhost:5001"
export KAFKA_BOOTSTRAP_SERVERS="localhost:9092"
export REDIS_HOST="localhost"
export REDIS_PORT="6379"

echo "Starting Gatekeeper Consumer"
echo "Press Ctrl+C to stop"
echo ""

python -m src.consumer
```

**Make them executable**:
```bash
chmod +x run-api.sh run-consumer.sh
```

**Usage**:
```bash
# Run API
./run-api.sh

# Run Consumer (in another terminal)
./run-consumer.sh
```

## Testing

### 1. Test API Health
```bash
curl http://localhost:8000/health

# Expected:
# {
#   "status": "healthy",
#   "model_loaded": true,
#   "redis_connected": true,
#   "consumer_running": false
# }
```

### 2. Test Manual Prediction
```bash
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{
    "visitorid": "test-user-123",
    "timestamp": 1672531200000
  }'

# Expected:
# {
#   "is_anomaly": false,
#   "time_since_last_event_sec": 3600.0,
#   "prediction": 1
# }
```

### 3. Test Consumer Processing

**Start data producer** (in Docker or locally):
```bash
docker compose up -d data_producer
```

**Watch consumer logs**:
The consumer terminal should show events being processed:
```
Clean event from user 12345 (velocity: 5.23s)
Clean event from user 67890 (velocity: 2.15s)
Anomaly detected for user 99999 (velocity: 0.05s)
User 99999 has been banned for 600 seconds
```

### 4. Monitor Kafka Topics

**Check clean events**:
```bash
docker exec -it shielded-recommender-kafka-1 \
  kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic clean-events \
  --from-beginning \
  --max-messages 5
```

**Check suspicious events**:
```bash
docker exec -it shielded-recommender-kafka-1 \
  kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic suspicious-events \
  --from-beginning
```

### 5. Check Redis State

**Check banned users**:
```bash
docker compose exec redis redis-cli ZRANGE banned_users_with_ttl 0 -1 WITHSCORES
```

**Check user history**:
```bash
docker compose exec redis redis-cli LRANGE user_history:12345 0 -1
```

## Development Workflow

### 1. Start Dependencies
```bash
# From project root
docker compose up -d kafka redis mlflow postgres
```

### 2. Start Services
```bash
# Terminal 1 - API with hot reload
cd services/gatekeeper
./run-api.sh

# Terminal 2 - Consumer (restart manually after changes)
cd services/gatekeeper
./run-consumer.sh
```

### 3. Make Code Changes
- API changes auto-reload (thanks to `--reload`)
- Consumer changes require manual restart (Ctrl+C, then run again)

### 4. Test Changes
```bash
# Test API
curl http://localhost:8000/health

# Test prediction
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"visitorid":"test","timestamp":1672531200000}'
```

## Troubleshooting

### Problem: "Module not found" error

**Solution**: Set PYTHONPATH correctly
```bash
# From services/gatekeeper directory
export PYTHONPATH="${PYTHONPATH}:$(pwd)/../.."

# Verify
echo $PYTHONPATH
# Should include path to project root
```

### Problem: "Cannot connect to Kafka"

**Solution**: Check Kafka is accessible
```bash
# Test Kafka connection
docker compose ps kafka

# Should show: State: Up

# If not running
docker compose up -d kafka
```

### Problem: "Model not found"

**Solution**: Train and register the model first
```bash
# Run training script
cd ../../  # Back to project root
PYTHONPATH=. MLFLOW_TRACKING_URI="http://localhost:5001" \
  python services/trainer/src/train.py

# Verify model exists
curl http://localhost:5001/api/2.0/mlflow/registered-models/get?name=isolation-forest-bot-detector
```

### Problem: "Redis connection failed"

**Solution**: Check Redis is running
```bash
# Test Redis
docker compose exec redis redis-cli PING
# Should return: PONG

# If not running
docker compose up -d redis
```

### Problem: Consumer can't deserialize events

**Solution**: Check event format in Kafka
```bash
# View raw events
docker exec -it shielded-recommender-kafka-1 \
  kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic raw-clickstream \
  --from-beginning \
  --max-messages 1

# Should be valid JSON
```

## Environment Variables Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `PYTHONPATH` | - | Must include project root |
| `MLFLOW_TRACKING_URI` | `http://mlflow:5000` | MLflow server URL |
| `MODEL_NAME` | `isolation-forest-bot-detector` | Model name in registry |
| `KAFKA_BOOTSTRAP_SERVERS` | `kafka:9092` | Kafka broker address |
| `REDIS_HOST` | `redis` | Redis hostname |
| `REDIS_PORT` | `6379` | Redis port |
| `START_CONSUMER` | `false` | Start consumer in API process |
| `USER_BAN_TTL_SECONDS` | `600` | Ban duration (10 min) |
| `USER_HISTORY_TTL_SECONDS` | `3600` | History TTL (1 hour) |

## VS Code Configuration

### `.vscode/launch.json`
```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Gatekeeper API",
      "type": "python",
      "request": "launch",
      "module": "uvicorn",
      "args": [
        "src.main:app",
        "--reload",
        "--host", "0.0.0.0",
        "--port", "8000"
      ],
      "cwd": "${workspaceFolder}/services/gatekeeper",
      "env": {
        "PYTHONPATH": "${workspaceFolder}",
        "MLFLOW_TRACKING_URI": "http://localhost:5001",
        "KAFKA_BOOTSTRAP_SERVERS": "localhost:9092",
        "REDIS_HOST": "localhost",
        "START_CONSUMER": "false"
      }
    },
    {
      "name": "Gatekeeper Consumer",
      "type": "python",
      "request": "launch",
      "module": "src.consumer",
      "cwd": "${workspaceFolder}/services/gatekeeper",
      "env": {
        "PYTHONPATH": "${workspaceFolder}",
        "MLFLOW_TRACKING_URI": "http://localhost:5001",
        "KAFKA_BOOTSTRAP_SERVERS": "localhost:9092",
        "REDIS_HOST": "localhost"
      }
    }
  ]
}
```

Now you can debug in VS Code with F5!

## Tips

1. **Use separate terminals** for API and consumer - easier to see logs
2. **Enable hot reload** for API (`--reload`) - changes apply instantly
3. **Keep Docker running** for dependencies - easier than local Kafka/Redis
4. **Use tmux/screen** for managing multiple terminals
5. **Check logs frequently** - errors are easier to debug locally

## Comparison: Local vs Docker

| Aspect | Local | Docker |
|--------|-------|--------|
| **Startup time** | Instant | ~10 seconds |
| **Hot reload** | ✅ Yes (API) | ❌ Need rebuild |
| **Debugging** | ✅ Easy (breakpoints) | ⚠️ Remote debugging |
| **Dependencies** | Manual setup | Automatic |
| **Consistency** | ⚠️ Local variations | ✅ Identical everywhere |
| **Testing** | ✅ Fast iteration | ⚠️ Slower |

**Best approach**: Use local for development, Docker for final testing before deployment.
