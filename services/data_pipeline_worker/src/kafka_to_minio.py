import os
import json
import logging
from datetime import datetime
import pandas as pd
from kafka import KafkaConsumer

# --- Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Kafka settings from environment variables
KAFKA_BROKER = os.getenv("KAFKA_BROKER", "kafka:9092")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "clean-events")
CONSUMER_GROUP_ID = "kafka-to-minio-consumer"
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "1000"))
CONSUMER_TIMEOUT_MS = int(os.getenv("CONSUMER_TIMEOUT_MS", "30000"))  # 30 seconds

# MinIO/S3 settings from environment variables
S3_ENDPOINT_URL = os.getenv("S3_ENDPOINT_URL")
S3_ACCESS_KEY_ID = os.getenv("S3_ACCESS_KEY_ID")
S3_SECRET_ACCESS_KEY = os.getenv("S3_SECRET_ACCESS_KEY")
S3_BUCKET = os.getenv("S3_BUCKET")


def main():
    """
    Consumes messages from a Kafka topic in batches and writes them
    as a Parquet file to an S3-compatible object store (MinIO).
    """
    logging.info(f"Starting Kafka to MinIO pipeline for topic '{KAFKA_TOPIC}'.")

    if not all([S3_ENDPOINT_URL, S3_ACCESS_KEY_ID, S3_SECRET_ACCESS_KEY, S3_BUCKET]):
        logging.error("S3 environment variables are not fully configured. Exiting.")
        exit(1)

    try:
        consumer = KafkaConsumer(
            KAFKA_TOPIC,
            bootstrap_servers=KAFKA_BROKER,
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            auto_offset_reset='earliest',
            group_id=CONSUMER_GROUP_ID,
            consumer_timeout_ms=CONSUMER_TIMEOUT_MS,
            enable_auto_commit=True
        )
        logging.info("Successfully connected to Kafka.")
    except Exception as e:
        logging.error(f"Could not connect to Kafka: {e}")
        return

    messages = []
    try:
        for message in consumer:
            messages.append(message.value)
            if len(messages) >= BATCH_SIZE:
                logging.info(f"Reached batch size of {len(messages)}. Writing to MinIO.")
                break

        if not messages:
            logging.info("No new messages found in Kafka topic. Exiting.")
            return

        # Convert messages to a pandas DataFrame
        df = pd.DataFrame(messages)

        # Generate a unique filename based on the current timestamp
        now = datetime.utcnow()
        date_partition = now.strftime('year=%Y/month=%m/day=%d')
        timestamp_str = now.strftime('%Y-%m-%d-%H-%M-%S')
        file_name = f"events-{timestamp_str}.parquet"
        s3_path = f"s3://{S3_BUCKET}/{date_partition}/{file_name}"

        logging.info(f"Writing {len(df)} records to {s3_path}")

        # Configure storage options for pandas to connect to MinIO
        storage_options = {
            "key": S3_ACCESS_KEY_ID,
            "secret": S3_SECRET_ACCESS_KEY,
            "client_kwargs": {"endpoint_url": S3_ENDPOINT_URL}
        }

        # Write DataFrame to Parquet file in MinIO
        df.to_parquet(s3_path, index=False, storage_options=storage_options)

        logging.info("Successfully wrote batch to MinIO.")

    except Exception as e:
        logging.error(f"An error occurred during the pipeline: {e}")
    finally:
        consumer.close()
        logging.info("Kafka consumer closed.")


if __name__ == "__main__":
    main()