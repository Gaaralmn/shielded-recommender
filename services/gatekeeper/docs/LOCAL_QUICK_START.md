# Local Testing - Quick Start

Run gatekeeper API and consumer locally (without Docker) in 3 steps.

## 1. Start Dependencies (Docker)

```bash
# From project root
docker compose up -d kafka redis mlflow postgres
```

## 2. Start API

```bash
cd services/gatekeeper
./run-api.sh
```

**➜ Open browser**: http://localhost:8000/docs

## 3. Start Consumer (New Terminal)

```bash
cd services/gatekeeper
./run-consumer.sh
```

## Test It

```bash
# Health check
curl http://localhost:8000/health

# Manual prediction
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"visitorid":"test","timestamp":1672531200000}'
```

## What Each Script Does

### `run-api.sh`
- ✅ Creates/activates virtual environment
- ✅ Installs dependencies
- ✅ Checks Redis and MLflow
- ✅ Starts API with hot reload on port 8000

### `run-consumer.sh`
- ✅ Creates/activates virtual environment
- ✅ Installs dependencies
- ✅ Checks Kafka, Redis, and MLflow
- ✅ Starts consumer to process events

## First Time Setup

```bash
cd services/gatekeeper

# Option 1: Use the scripts (recommended)
./run-api.sh  # Will create venv and install dependencies

# Option 2: Manual setup
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Stopping Services

- **Press Ctrl+C** in each terminal
- Services stop gracefully

## Troubleshooting

### "Permission denied"
```bash
chmod +x run-api.sh run-consumer.sh
```

### "Module not found"
The scripts set `PYTHONPATH` automatically. If running manually:
```bash
export PYTHONPATH="${PYTHONPATH}:$(cd ../.. && pwd)"
```

### "Model not found"
Train the model first:
```bash
cd ../..  # Project root
PYTHONPATH=. MLFLOW_TRACKING_URI="http://localhost:5000" \
  python services/trainer/src/train.py
```

### "Kafka connection failed"
```bash
docker compose up -d kafka
sleep 5  # Wait for Kafka to start
```

## Development Workflow

```bash
# Terminal 1: Dependencies
docker compose up -d kafka redis mlflow postgres

# Terminal 2: API (auto-reloads on changes)
cd services/gatekeeper
./run-api.sh

# Terminal 3: Consumer (restart after changes)
cd services/gatekeeper
./run-consumer.sh

# Terminal 4: Testing
curl http://localhost:8000/health
```

## IDE Configuration

### VS Code
Press F5 to debug with the configurations in [LOCAL_TESTING.md](LOCAL_TESTING.md)

### PyCharm
1. Open services/gatekeeper/src/main.py
2. Right-click → Run 'main'
3. Edit run configuration to set environment variables

## Quick Commands

| Task | Command |
|------|---------|
| Start API | `./run-api.sh` |
| Start Consumer | `./run-consumer.sh` |
| Health check | `curl http://localhost:8000/health` |
| Test predict | `curl -X POST http://localhost:8000/predict -H "Content-Type: application/json" -d '{"visitorid":"test","timestamp":1672531200000}'` |
| View API docs | Open http://localhost:8000/docs |
| Check banned users | `docker compose exec redis redis-cli ZRANGE banned_users_with_ttl 0 -1` |

## Full Documentation

See [LOCAL_TESTING.md](LOCAL_TESTING.md) for complete guide including:
- Manual setup without scripts
- Detailed troubleshooting
- VS Code debugging configuration
- Environment variables reference
