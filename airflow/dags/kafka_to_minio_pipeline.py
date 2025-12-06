from __future__ import annotations

import pendulum

from airflow.models.dag import DAG
from airflow.providers.docker.operators.docker import DockerOperator

with DAG(
    dag_id="kafka_to_minio_pipeline",
    start_date=pendulum.datetime(2025, 1, 1, tz="UTC"),
    schedule="*/15 * * * *",  # Run every 15 minutes
    catchup=False,
    tags=["data-engineering", "kafka", "minio"],
    doc_md="""
    ### Kafka to MinIO Data Pipeline

    This DAG consumes event data from the 'clean-events' Kafka topic in batches
    and writes it to the 'clean-events' MinIO bucket in Parquet format.
    """,
) as dag:
    DockerOperator(
        task_id="run_kafka_to_minio_script",
        image="shielded-recommender-data_pipeline_worker",  # Use the new, dedicated image
        command="python src/kafka_to_minio.py",
        network_mode="shielded-recommender_default",  # Connect to the project's network
        environment={
            "KAFKA_BROKER": "kafka:9092",
            "KAFKA_TOPIC": "clean-events",
            "BATCH_SIZE": "5000",
            "CONSUMER_TIMEOUT_MS": "60000",  # Wait up to 60 seconds for messages
            "S3_ENDPOINT_URL": "http://minio:9000",
            "S3_ACCESS_KEY_ID": "{{ var.value.get('MINIO_ROOT_USER', 'minioadmin') }}",
            "S3_SECRET_ACCESS_KEY": "{{ var.value.get('MINIO_ROOT_PASSWORD', 'minioadmin') }}",
            "S3_BUCKET": "clean-events",
            "PYTHONPATH": "/app",
        },
        auto_remove=True,
        docker_url="unix://var/run/docker.sock",
    )