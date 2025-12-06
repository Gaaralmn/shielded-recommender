"""
Bootstrap Initial Model DAG (Environment-Aware Version)

This DAG demonstrates the operator factory pattern for environment-agnostic training tasks.
It automatically uses:
- DockerOperator in development (AIRFLOW_ENV=dev)
- KubernetesPodOperator in production (AIRFLOW_ENV=prod)

To switch environments:
    export AIRFLOW_ENV=prod  # Use Kubernetes
    export AIRFLOW_ENV=dev   # Use Docker (default)
"""
from __future__ import annotations

import pendulum

from airflow.models.dag import DAG
from lib.operator_factory import create_training_operator, get_mlflow_uri

with DAG(
    dag_id="bootstrap_initial_model_v2",
    start_date=pendulum.datetime(2025, 1, 1, tz="UTC"),
    schedule=None,  # Manual trigger only
    catchup=False,
    tags=["bootstrap", "one-time", "anomaly-detection", "environment-agnostic"],
    doc_md="""
    ### Bootstrap Initial Model (Environment-Agnostic)

    This is an example of environment-aware DAG design using the operator factory pattern.

    #### Environment Detection:
    - **Development** (`AIRFLOW_ENV=dev`): Uses DockerOperator with local Docker socket
    - **Production** (`AIRFLOW_ENV=prod`): Uses KubernetesPodOperator with proper RBAC

    #### What It Does:
    1. Detects current environment via AIRFLOW_ENV variable
    2. Creates appropriate operator (Docker vs Kubernetes)
    3. Trains initial Isolation Forest model
    4. Registers model to MLflow

    #### How to Use:
    - Development: `export AIRFLOW_ENV=dev` (or leave unset)
    - Production: `export AIRFLOW_ENV=prod`
    """,
) as dag:
    # Create training task - automatically adapts to environment
    bootstrap_train = create_training_operator(
        task_id="bootstrap_train_from_csv",
        image="shielded-recommender-trainer",
        command="python src/train.py",
        env_vars={
            "MLFLOW_TRACKING_URI": get_mlflow_uri(),  # Auto-adjusts for environment
            "DATA_PATH": "/app/retailrocket/data/retailrocket/events.csv",
            "TRAINING_TYPE": "bootstrap",
            "PYTHONPATH": "/app",
        },
        # Production-specific settings (ignored in dev)
        namespace="ml-training",
        service_account="airflow-worker",
        cpu_request="1",
        cpu_limit="2",
        memory_request="2Gi",
        memory_limit="4Gi",
        # Development-specific settings (ignored in prod)
        dev_mounts=[
            {
                "source": "/Users/qingwang/Development/shielded-recommender/data",
                "target": "/app/retailrocket/data",
                "type": "bind",
            }
        ],
        dev_network="shielded-recommender_default",
    )
