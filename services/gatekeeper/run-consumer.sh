#!/bin/bash
# Helper script to run Gatekeeper Consumer locally

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}╔══════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  Gatekeeper Consumer - Local Development║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════╝${NC}"
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}Virtual environment not found. Creating...${NC}"
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
else
    source venv/bin/activate
fi

# Set environment variables
export PYTHONPATH="${PYTHONPATH}:$(cd ../.. && pwd)"
export MLFLOW_TRACKING_URI="http://localhost:5000"
export KAFKA_BOOTSTRAP_SERVERS="localhost:9092"
export REDIS_HOST="localhost"
export REDIS_PORT="6379"

echo -e "${GREEN}Environment configured:${NC}"
echo "  PYTHONPATH: $PYTHONPATH"
echo "  MLFLOW_TRACKING_URI: $MLFLOW_TRACKING_URI"
echo "  KAFKA_BOOTSTRAP_SERVERS: $KAFKA_BOOTSTRAP_SERVERS"
echo "  REDIS_HOST: $REDIS_HOST"
echo ""

# Check dependencies
echo -e "${YELLOW}Checking dependencies...${NC}"

# Check Redis
if ! docker compose exec -T redis redis-cli PING &> /dev/null; then
    echo -e "${YELLOW}⚠️  Redis not responding. Starting...${NC}"
    docker compose up -d redis
    sleep 2
fi
echo "✓ Redis: OK"

# Check MLflow
if ! curl -s http://localhost:5000/health &> /dev/null; then
    echo -e "${YELLOW}⚠️  MLflow not responding. Make sure it's running:${NC}"
    echo "   docker compose up -d mlflow"
    exit 1
else
    echo "✓ MLflow: OK"
fi

# Check Kafka
if ! docker compose ps kafka | grep -q "Up"; then
    echo -e "${YELLOW}⚠️  Kafka not running. Starting...${NC}"
    docker compose up -d kafka
    sleep 5
fi
echo "✓ Kafka: OK"

echo ""
echo -e "${GREEN}Starting Consumer...${NC}"
echo -e "${YELLOW}Press Ctrl+C to stop${NC}"
echo ""
echo "Consumer will:"
echo "  • Listen to: raw-clickstream"
echo "  • Route to: clean-events (normal) / suspicious-events (anomaly)"
echo "  • Ban suspicious users in Redis"
echo ""

# Run the consumer
python -m src.consumer
