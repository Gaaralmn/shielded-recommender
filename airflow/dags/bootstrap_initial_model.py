from __future__ import annotations

import pendulum

from airflow.models.dag import DAG
from airflow.providers.docker.operators.docker import DockerOperator

with DAG(
    dag_id="bootstrap_initial_model",
    start_date=pendulum.datetime(2025, 1, 1, tz="UTC"),
    schedule=None,  # Manual trigger only - not scheduled!
    catchup=False,
    tags=["bootstrap", "one-time", "anomaly-detection"],
    doc_md="""
    ### Bootstrap Initial Anomaly Detection Model

    **ONE-TIME USE ONLY**: This DAG trains the first anomaly detection model using
    the historical RetailRocket dataset (events.csv).

    #### When to Run:
    - **Once** when first setting up the system
    - Before starting the gatekeeper service (it needs a model to load)
    - When you want to reset the model to baseline

    #### What It Does:
    1. Loads `/app/data/retailrocket/events.csv` (1 year of historical data)
    2. Performs feature engineering (time_since_last_event_sec)
    3. Trains an Isolation Forest model on normal behavior
    4. Registers the model to MLflow as version 1

    #### After This Runs:
    - Use the `retrain_anomaly_model` DAG for all subsequent retraining
    - That DAG runs daily and uses live data from the MinIO data lake

    #### How to Run:
    - Airflow UI → DAGs → bootstrap_initial_model → Trigger DAG
    - Or via CLI: `airflow dags trigger bootstrap_initial_model`
    """,
) as dag:
    DockerOperator(
        task_id="bootstrap_train_from_csv",
        image="shielded-recommender-trainer",
        command="python src/train.py",
        network_mode="shielded-recommender_default",
        mounts=[
            # Mount the local data directory to access the RetailRocket CSV
            {
                "source": "/Users/qingwang/Development/shielded-recommender/data",
                "target": "/app/data",
                "type": "bind",
            }
        ],
        mount_tmp_dir=False,  # Disable temp mount (not needed, causes issues on macOS)
        environment={
            "MLFLOW_TRACKING_URI": "http://mlflow:5000",
            "DATA_PATH": "/app/data/retailrocket/events.csv",  # Local CSV file
            "TRAINING_TYPE": "bootstrap",  # Tag for MLflow
            "PYTHONPATH": "/app",
        },
        auto_remove=True,
        docker_url="unix://var/run/docker.sock",
    )
