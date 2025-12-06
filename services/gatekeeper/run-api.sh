#!/bin/bash
# Helper script to run Gatekeeper API locally

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}╔══════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║   Gatekeeper API - Local Development    ║${NC}"
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
export START_CONSUMER="false"  # API only mode

echo -e "${GREEN}Environment configured:${NC}"
echo "  PYTHONPATH: $PYTHONPATH"
echo "  MLFLOW_TRACKING_URI: $MLFLOW_TRACKING_URI"
echo "  KAFKA_BOOTSTRAP_SERVERS: $KAFKA_BOOTSTRAP_SERVERS"
echo "  REDIS_HOST: $REDIS_HOST"
echo "  START_CONSUMER: $START_CONSUMER"
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
else
    echo "✓ MLflow: OK"
fi

# Check Kafka (optional for API-only)
if ! docker compose ps kafka | grep -q "Up"; then
    echo -e "${YELLOW}⚠️  Kafka not running (optional for API-only mode)${NC}"
else
    echo "✓ Kafka: OK"
fi

echo ""
echo -e "${GREEN}Starting API on http://localhost:8000${NC}"
echo -e "${YELLOW}Press Ctrl+C to stop${NC}"
echo ""
echo "Available endpoints:"
echo "  • http://localhost:8000/          - Service info"
echo "  • http://localhost:8000/health    - Health check"
echo "  • http://localhost:8000/predict   - Manual prediction"
echo "  • http://localhost:8000/docs      - API documentation"
echo ""

# Run the API with hot reload
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
