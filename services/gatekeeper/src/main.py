import os
import logging
import json
import time
import threading
from contextlib import asynccontextmanager
from datetime import datetime
import pandas as pd
import numpy as np
import redis
import mlflow
from mlflow.tracking import MlflowClient
from kafka import KafkaConsumer, KafkaProducer
from fastapi import FastAPI

# --- Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "http://mlflow:5000")
MODEL_NAME = os.getenv("MODEL_NAME", "isolation-forest-bot-detector")
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
USER_BAN_TTL_SECONDS = int(os.getenv("USER_BAN_TTL_SECONDS", "600"))  # 10 minutes
USER_HISTORY_TTL_SECONDS = int(os.getenv("USER_HISTORY_TTL_SECONDS", "3600"))  # 1 hour
BOT_VELOCITY_THRESHOLD_SEC = float(os.getenv("BOT_VELOCITY_THRESHOLD_SEC", "1.0"))  # Flag events < 1 second apart as bot-like

# Control whether to start consumer in this process (default: False for split architecture)
START_CONSUMER = os.getenv("START_CONSUMER", "false").lower() == "true"

# Kafka topics
RAW_CLICKSTREAM_TOPIC = "raw-clickstream"
CLEAN_EVENTS_TOPIC = "clean-events"
SUSPICIOUS_EVENTS_TOPIC = "suspicious-events"

# --- Global state ---
model = None
redis_client = None
consumer_thread = None
should_run_consumer = True


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for startup and shutdown events.
    This replaces the deprecated @app.on_event decorators.
    """
    global consumer_thread, should_run_consumer

    # Startup
    logging.info("Gatekeeper API starting up...")

    # Load model and initialize Redis
    load_model_from_registry()
    initialize_redis()

    # Optionally start Kafka consumer in a background thread
    # In production split architecture, this is disabled and consumer runs separately
    if START_CONSUMER:
        logging.info("Starting consumer in background thread (single-process mode)...")
        should_run_consumer = True
        consumer_thread = threading.Thread(target=run_kafka_consumer, daemon=True)
        consumer_thread.start()
    else:
        logging.info("Consumer disabled (split-process mode - run consumer separately)")

    logging.info("Gatekeeper API ready!")

    yield  # Application runs here

    # Shutdown
    logging.info("Gatekeeper API shutting down...")

    if START_CONSUMER and consumer_thread:
        should_run_consumer = False
        if consumer_thread.is_alive():
            logging.info("Waiting for consumer thread to finish...")
            consumer_thread.join(timeout=10)

    logging.info("Gatekeeper API shut down complete")


app = FastAPI(
    title="Gatekeeper Service",
    description="Detects bot traffic to prevent it from polluting recommendation data.",
    version="0.1.0",
    lifespan=lifespan
)


def load_model_from_registry():
    """Load the latest version of the model from MLflow registry."""
    global model
    try:
        logging.info(f"Connecting to MLflow at {MLFLOW_TRACKING_URI}")
        mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)

        client = MlflowClient()

        # Get the latest version of the model
        model_versions = client.search_model_versions(f"name='{MODEL_NAME}'")
        if not model_versions:
            raise ValueError(f"No model versions found for model '{MODEL_NAME}'")

        # Get the latest version (assuming higher version numbers are newer)
        latest_version = max(model_versions, key=lambda x: int(x.version))
        model_uri = f"models:/{MODEL_NAME}/{latest_version.version}"

        logging.info(f"Loading model from {model_uri}")
        model = mlflow.sklearn.load_model(model_uri)
        logging.info(f"Model loaded successfully: {MODEL_NAME} version {latest_version.version}")

    except Exception as e:
        logging.error(f"Failed to load model: {e}")
        raise


def initialize_redis():
    """Initialize Redis client."""
    global redis_client
    try:
        redis_client = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            decode_responses=True
        )
        redis_client.ping()
        logging.info(f"Connected to Redis at {REDIS_HOST}:{REDIS_PORT}")
    except Exception as e:
        logging.error(f"Failed to connect to Redis: {e}")
        raise


def get_user_history_key(user_id: str) -> str:
    """Generate Redis key for user event history."""
    return f"user_history:{user_id}"


def get_banned_users_key() -> str:
    """Generate Redis key for banned users set."""
    return "banned_users"


def calculate_time_since_last_event(user_id: str, current_timestamp_ms: int) -> float:
    """
    Calculate the time since the last event for a user.
    Returns time in seconds, or 3600 if this is the first event.
    """
    history_key = get_user_history_key(user_id)

    # Get the last timestamp from Redis
    last_timestamp_str = redis_client.lindex(history_key, 0)

    if last_timestamp_str is None:
        # First event for this user
        time_since_last = 3600.0
    else:
        last_timestamp_ms = int(last_timestamp_str)
        time_since_last = (current_timestamp_ms - last_timestamp_ms) / 1000.0

    # Store the current timestamp at the front of the list
    redis_client.lpush(history_key, current_timestamp_ms)
    redis_client.ltrim(history_key, 0, 99)  # Keep only last 100 events
    redis_client.expire(history_key, USER_HISTORY_TTL_SECONDS)

    return time_since_last


def is_user_banned(user_id: str) -> bool:
    """Check if a user is currently banned."""
    return redis_client.sismember(get_banned_users_key(), user_id)


def ban_user(user_id: str):
    """Ban a user by adding them to the banned users set with expiry."""
    banned_key = get_banned_users_key()
    redis_client.sadd(banned_key, user_id)
    # Note: Redis doesn't support TTL on individual set members,
    # so we'll use a sorted set with scores as expiry timestamps
    banned_with_ttl_key = f"banned_users_with_ttl"
    expiry_time = time.time() + USER_BAN_TTL_SECONDS
    redis_client.zadd(banned_with_ttl_key, {user_id: expiry_time})
    logging.info(f"User {user_id} has been banned for {USER_BAN_TTL_SECONDS} seconds")


def cleanup_expired_bans():
    """Remove expired bans from the sorted set."""
    banned_with_ttl_key = "banned_users_with_ttl"
    current_time = time.time()
    # Remove users whose ban has expired
    redis_client.zremrangebyscore(banned_with_ttl_key, 0, current_time)


def parse_timestamp(timestamp_value) -> int:
    """
    Convert timestamp to milliseconds.
    Handles both integer timestamps and ISO datetime strings.

    Args:
        timestamp_value: Either int/float (milliseconds) or string (ISO datetime)

    Returns:
        int: Timestamp in milliseconds
    """
    if isinstance(timestamp_value, (int, float)):
        return int(timestamp_value)

    if isinstance(timestamp_value, str):
        # Parse ISO format datetime string (e.g., "2025-12-02T19:23:01.860023")
        try:
            dt = datetime.fromisoformat(timestamp_value.replace('Z', '+00:00'))
            return int(dt.timestamp() * 1000)
        except ValueError:
            # Try parsing as integer string
            return int(timestamp_value)

    raise ValueError(f"Unsupported timestamp type: {type(timestamp_value)}")


def process_event(event: dict, producer: KafkaProducer):
    """
    Process a single event: calculate features, predict anomaly, and route to appropriate topic.
    """
    try:
        user_id = str(event.get('user_id'))

        # Parse timestamp - handles both milliseconds and ISO datetime strings
        timestamp_value = event.get('timestamp')
        timestamp_ms = parse_timestamp(timestamp_value)

        # Check if user is already banned
        cleanup_expired_bans()
        banned_with_ttl_key = "banned_users_with_ttl"
        if redis_client.zscore(banned_with_ttl_key, user_id) is not None:
            # User is banned, send to suspicious events
            producer.send(SUSPICIOUS_EVENTS_TOPIC, value=event)
            logging.debug(f"Rejected event from banned user {user_id}")
            return

        # Calculate session velocity feature
        time_since_last_event_sec = calculate_time_since_last_event(user_id, timestamp_ms)

        # Bot detection logic:
        # 1. Threshold-based: Events < 1 second apart are bot-like (primary rule)
        # 2. Model-based: Use Isolation Forest as secondary check (currently detects very long gaps)
        is_bot = False
        detection_reason = ""

        # Check velocity threshold (primary bot detection)
        if time_since_last_event_sec < BOT_VELOCITY_THRESHOLD_SEC:
            is_bot = True
            detection_reason = f"rapid-fire (velocity: {time_since_last_event_sec:.4f}s < {BOT_VELOCITY_THRESHOLD_SEC}s)"
        else:
            # Use model as secondary check
            # Model uses both original and log-transformed features
            log_time = np.log1p(time_since_last_event_sec)
            X = pd.DataFrame([[time_since_last_event_sec, log_time]],
                           columns=['time_since_last_event_sec', 'log_time_since_last'])
            prediction = model.predict(X)[0]

            if prediction == -1:
                is_bot = True
                detection_reason = f"model anomaly (velocity: {time_since_last_event_sec:.2f}s)"

        if is_bot:
            # Anomaly detected
            producer.send(SUSPICIOUS_EVENTS_TOPIC, value=event)
            ban_user(user_id)
            logging.info(f"🤖 Bot detected for user {user_id}: {detection_reason}")
        else:
            # Normal event
            producer.send(CLEAN_EVENTS_TOPIC, value=event)
            logging.debug(f"✓ Clean event from user {user_id} (velocity: {time_since_last_event_sec:.2f}s)")

    except Exception as e:
        logging.error(f"Error processing event: {e}")
        # On error, send to suspicious events to be safe
        producer.send(SUSPICIOUS_EVENTS_TOPIC, value=event)


def run_kafka_consumer():
    """
    Main consumer loop: consume from raw-clickstream, predict, and route events.
    This runs in a separate thread when started by FastAPI.
    """
    global should_run_consumer

    logging.info("Starting Kafka consumer...")

    # Retry connection to Kafka (it might not be ready immediately)
    max_retries = 10
    retry_delay = 5

    for attempt in range(max_retries):
        try:
            consumer = KafkaConsumer(
                RAW_CLICKSTREAM_TOPIC,
                bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
                value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                auto_offset_reset='latest',
                enable_auto_commit=True,
                group_id='gatekeeper-service',
                consumer_timeout_ms=1000  # Timeout to allow checking should_run_consumer
            )

            producer = KafkaProducer(
                bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
                value_serializer=lambda v: json.dumps(v).encode('utf-8')
            )

            logging.info(f"Consumer listening to {RAW_CLICKSTREAM_TOPIC}")
            logging.info(f"Will route to: {CLEAN_EVENTS_TOPIC} (clean) and {SUSPICIOUS_EVENTS_TOPIC} (suspicious)")
            break

        except Exception as e:
            if attempt < max_retries - 1:
                logging.warning(f"Failed to connect to Kafka (attempt {attempt + 1}/{max_retries}): {e}")
                time.sleep(retry_delay)
            else:
                logging.error(f"Could not connect to Kafka after {max_retries} attempts: {e}")
                return

    try:
        while should_run_consumer:
            try:
                # Use consumer iterator with timeout to allow graceful shutdown
                for message in consumer:
                    if not should_run_consumer:
                        break
                    event = message.value
                    process_event(event, producer)
            except StopIteration:
                # Consumer timeout - continue loop to check should_run_consumer
                continue

    except Exception as e:
        logging.error(f"Consumer error: {e}")
    finally:
        logging.info("Shutting down consumer...")
        consumer.close()
        producer.close()
        logging.info("Consumer shut down complete")


@app.get("/")
def read_root():
    return {
        "message": "Gatekeeper service is running.",
        "model": MODEL_NAME if model else "Not loaded",
        "redis": "Connected" if redis_client else "Not connected"
    }


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "model_loaded": model is not None,
        "redis_connected": redis_client is not None,
        "consumer_running": consumer_thread is not None and consumer_thread.is_alive()
    }


@app.post("/predict")
def predict(data: dict):
    """
    Manual prediction endpoint for testing.
    Accepts timestamp as either:
    - Integer milliseconds: {"visitorid": "123", "timestamp": 1672531200000}
    - ISO datetime string: {"visitorid": "123", "timestamp": "2025-12-02T19:23:01.860023"}
    """
    if model is None:
        return {"error": "Model not loaded"}

    try:
        user_id = str(data.get('user_id'))

        # Parse timestamp - handles both formats
        timestamp_value = data.get('timestamp')
        timestamp_ms = parse_timestamp(timestamp_value)

        time_since_last_event_sec = calculate_time_since_last_event(user_id, timestamp_ms)

        # Apply same bot detection logic as consumer
        is_bot = False
        detection_method = "none"

        if time_since_last_event_sec < BOT_VELOCITY_THRESHOLD_SEC:
            is_bot = True
            detection_method = "threshold"
        else:
            # Model uses both original and log-transformed features
            log_time = np.log1p(time_since_last_event_sec)
            X = pd.DataFrame([[time_since_last_event_sec, log_time]],
                           columns=['time_since_last_event_sec', 'log_time_since_last'])
            prediction = model.predict(X)[0]
            if prediction == -1:
                is_bot = True
                detection_method = "model"

        return {
            "is_anomaly": bool(is_bot),
            "time_since_last_event_sec": float(time_since_last_event_sec),
            "detection_method": detection_method,
            "velocity_threshold": float(BOT_VELOCITY_THRESHOLD_SEC)
        }
    except Exception as e:
        return {"error": str(e)}


if __name__ == "__main__":
    # When running as a standalone script, start the Kafka consumer
    # Note: In production, you'd run this separately from the FastAPI app
    load_model_from_registry()
    initialize_redis()
    run_kafka_consumer()
