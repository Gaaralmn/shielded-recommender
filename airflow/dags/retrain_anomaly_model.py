from __future__ import annotations

import pendulum

from airflow.models.dag import DAG
from airflow.providers.docker.operators.docker import DockerOperator

with DAG(
    dag_id="retrain_anomaly_model",
    start_date=pendulum.datetime(2025, 1, 1, tz="UTC"),
    schedule="0 0 * * *",  # Run daily at midnight
    catchup=False,
    tags=["anomaly-detection", "training", "production"],
    doc_md="""
    ### Retrain Anomaly Detection Model (Production)

    **Scheduled Daily Retraining**: This DAG retrains the anomaly detection model
    using live production data from the MinIO data lake.

    #### When It Runs:
    - Automatically every day at midnight UTC
    - Can also be triggered manually for immediate retraining

    #### What It Does:
    1. Loads all clean events from `s3://clean-events` bucket (MinIO)
    2. Performs feature engineering on production data
    3. Trains a new Isolation Forest model
    4. Registers new model version to MLflow
    5. Gatekeeper will hot-reload the new model on next health check

    #### Prerequisites:
    - Bootstrap DAG must have run at least once
    - `kafka_to_minio_pipeline` should be running to populate data lake
    - MinIO bucket 'clean-events' should contain parquet files

    #### Data Source:
    - Uses S3/MinIO data lake (not local CSV)
    - Reads from all partitions: year=*/month=*/day=*/*.parquet
    """,
) as dag:
    DockerOperator(
        task_id="retrain_from_datalake",
        image="shielded-recommender-trainer",
        command="python src/train.py",
        network_mode="shielded-recommender_default",
        mount_tmp_dir=False,  # Disable temp mount (not needed, causes issues on macOS)
        environment={
            "MLFLOW_TRACKING_URI": "http://mlflow:5000",
            "DATA_PATH": "s3://clean-events",  # MinIO data lake
            "S3_ENDPOINT_URL": "http://minio:9000",
            "S3_ACCESS_KEY_ID": "minioadmin",
            "S3_SECRET_ACCESS_KEY": "minioadmin",
            "TRAINING_TYPE": "retrain",  # Tag for MLflow
            "PYTHONPATH": "/app",
        },
        auto_remove=True,
        docker_url="unix://var/run/docker.sock",
    )
