import os
import time
import random
import logging
from datetime import datetime, timezone

import pandas as pd
from kafka import KafkaProducer
from kafka.errors import NoBrokersAvailable

# Assuming schemas are in a directory accessible to the service
from recommender_schemas.events import ClickEvent

# --- Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

KAFKA_BROKER = os.getenv("KAFKA_BROKER", "kafka:9092")
KAFKA_TOPIC = "raw-clickstream"
DATA_FILE_PATH = "/app/data/retailrocket/events.csv" # Path inside the container

# Bot injection settings
BOT_INJECTION_PROBABILITY = 0.02  # 2% chance to inject a bot after a real event
BOT_EVENT_COUNT = 150 # Number of events the bot will generate
BOT_TIME_WINDOW_SECONDS = 5 # How quickly the bot generates events

# --- Kafka Producer Setup ---
def create_kafka_producer():
    """Creates a Kafka producer with retry logic."""
    retries = 5
    while retries > 0:
        try:
            producer = KafkaProducer(
                bootstrap_servers=[KAFKA_BROKER],
                value_serializer=lambda v: v.encode('utf-8')
            )
            logging.info("Successfully connected to Kafka.")
            return producer
        except NoBrokersAvailable:
            logging.warning(f"Kafka broker not available. Retrying in 5 seconds... ({retries} retries left)")
            retries -= 1
            time.sleep(5)
    logging.error("Could not connect to Kafka after multiple retries. Exiting.")
    return None

# --- Bot Traffic Injection ---
def inject_bot_traffic(producer: KafkaProducer, user_id: str):
    """Injects a burst of synthetic 'view' events for a given user."""
    logging.warning(f"--- Injecting BOT traffic for user_id: {user_id} ---")
    
    # Pick a random item for the bot to view repeatedly
    random_item_id = str(random.randint(100000, 400000))
    
    for _ in range(BOT_EVENT_COUNT):
        event = ClickEvent(
            user_id=user_id,
            item_id=random_item_id,
            timestamp=datetime.now(timezone.utc)
        )
        
        # Send to Kafka
        producer.send(KAFKA_TOPIC, event.model_dump_json())
        
        # Simulate rapid-fire clicks
        time.sleep(BOT_TIME_WINDOW_SECONDS / BOT_EVENT_COUNT)
        
    logging.warning(f"--- Finished injecting {BOT_EVENT_COUNT} bot events. ---")


# --- Main Producer Logic ---
def main():
    """Main function to read data and produce events to Kafka."""
    producer = create_kafka_producer()
    if not producer:
        return

    # Check if the data file exists
    if not os.path.exists(DATA_FILE_PATH):
        logging.error(f"Data file not found at {DATA_FILE_PATH}. Please ensure it's mounted correctly.")
        return

    logging.info(f"Reading dataset from {DATA_FILE_PATH}...")
    df = pd.read_csv(DATA_FILE_PATH)

    logging.info("Starting to produce events to Kafka...")
    try:
        while True: # Loop indefinitely to continuously stream data
            for row in df.itertuples(index=False):
                # Create a Pydantic model for the real event
                event = ClickEvent(
                    user_id=str(row.visitorid),
                    item_id=str(row.itemid),
                    timestamp=datetime.now(timezone.utc)
                )
                
                # Send the real event
                producer.send(KAFKA_TOPIC, event.model_dump_json())
                logging.info(f"Sent event: user_id={event.user_id}, item_id={event.item_id}")

                # Simulate a real-time stream with a small delay
                time.sleep(random.uniform(0.1, 0.8))

                # Randomly decide whether to inject bot traffic
                if random.random() < BOT_INJECTION_PROBABILITY:
                    inject_bot_traffic(producer, user_id=str(event.user_id))
            
            logging.info("Completed one full pass of the dataset. Restarting...")

    except KeyboardInterrupt:
        logging.info("Producer stopped by user.")
    finally:
        if producer:
            producer.flush()
            producer.close()
            logging.info("Kafka producer closed.")


if __name__ == "__main__":
    main()