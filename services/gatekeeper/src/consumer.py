"""
Standalone Kafka consumer for the Gatekeeper service.

This script runs the consumer independently from the FastAPI API server,
following the production best practice of separating concerns.

Architecture:
    gatekeeper-api:       FastAPI server for health checks and manual predictions
    gatekeeper-consumer:  This script - processes Kafka stream in real-time

Usage:
    # Standalone (with Python)
    python -m src.consumer

    # In Docker
    docker compose up gatekeeper-consumer

Environment Variables:
    MLFLOW_TRACKING_URI - MLflow server URL (default: http://mlflow:5000)
    MODEL_NAME - Model name in registry (default: isolation-forest-bot-detector)
    KAFKA_BOOTSTRAP_SERVERS - Kafka broker (default: kafka:9092)
    REDIS_HOST - Redis host (default: redis)
    REDIS_PORT - Redis port (default: 6379)
    USER_BAN_TTL_SECONDS - Ban duration (default: 600)
    USER_HISTORY_TTL_SECONDS - History TTL (default: 3600)

Benefits of Split Architecture:
    ✓ Independent scaling (scale consumer without affecting API)
    ✓ Fault isolation (API failure doesn't stop stream processing)
    ✓ Resource optimization (different CPU/memory for each service)
    ✓ Easier monitoring (separate logs and metrics)
    ✓ Zero-downtime deployments (update API without restarting consumer)
"""

import logging
import signal
import sys
from src.main import (
    load_model_from_registry,
    initialize_redis,
    run_kafka_consumer,
    should_run_consumer
)

# Setup logging for standalone consumer
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [CONSUMER] - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# Graceful shutdown handler
def signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    global should_run_consumer
    logger.info(f"Received signal {signum}, initiating graceful shutdown...")
    should_run_consumer = False
    sys.exit(0)

if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("Gatekeeper Kafka Consumer (Standalone)")
    logger.info("=" * 60)

    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)   # Ctrl+C
    signal.signal(signal.SIGTERM, signal_handler)  # docker stop

    try:
        # Initialize components
        logger.info("Step 1/3: Loading model from MLflow...")
        load_model_from_registry()

        logger.info("Step 2/3: Connecting to Redis...")
        initialize_redis()

        logger.info("Step 3/3: Starting Kafka consumer loop...")
        run_kafka_consumer()

    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received, shutting down...")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
    finally:
        logger.info("Consumer shutdown complete")
        logger.info("=" * 60)
