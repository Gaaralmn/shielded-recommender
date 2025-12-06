import os
import logging
import pandas as pd
import mlflow
from sklearn.ensemble import IsolationForest

# --- Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "http://mlflow:5000")
DATA_PATH = os.getenv("DATA_PATH", "s3://clean-events") # Default to S3 for production, can be overridden for bootstrap
REGISTERED_MODEL_NAME = "isolation-forest-bot-detector"
TRAINING_TYPE = os.getenv("TRAINING_TYPE", "retrain")  # "bootstrap" or "retrain"

# MinIO/S3 settings for reading from the data lake
S3_ENDPOINT_URL = os.getenv("S3_ENDPOINT_URL")
S3_ACCESS_KEY_ID = os.getenv("S3_ACCESS_KEY_ID")
S3_SECRET_ACCESS_KEY = os.getenv("S3_SECRET_ACCESS_KEY")


def feature_engineering(df: pd.DataFrame) -> pd.DataFrame:
    """
    Engineers the 'time_since_last_event_sec' feature from the raw data.
    This feature is crucial for identifying session velocity.
    """
    logging.info("Starting feature engineering...")

    # Standardize column names to match the schema contract
    df = df.rename(columns={'visitorid': 'user_id', 'itemid': 'item_id'})

    # Convert timestamp to datetime - handle both numeric (ms) and ISO string formats
    if pd.api.types.is_numeric_dtype(df['timestamp']):
        # Bootstrap data: numeric timestamp in milliseconds
        df['timestamp_dt'] = pd.to_datetime(df['timestamp'], unit='ms')
    else:
        # Production data from Kafka: ISO-formatted string
        df['timestamp_dt'] = pd.to_datetime(df['timestamp'])

    # Sort by user and timestamp to correctly calculate time differences
    df_sorted = df.sort_values(by=['user_id', 'timestamp_dt']).reset_index(drop=True)

    # Calculate time delta between consecutive events for each user
    df_sorted['time_since_last_event_sec'] = df_sorted.groupby('user_id')['timestamp_dt'].diff().dt.total_seconds()

    # The first event for each user will have a NaN delta. We fill it with a large number
    # to signify it's the start of a session and not a rapid-fire event.
    # 3600 seconds = 1 hour.
    df_sorted['time_since_last_event_sec'] = df_sorted['time_since_last_event_sec'].fillna(3600)

    logging.info("Feature engineering complete.")
    return df_sorted


if __name__ == "__main__":
    logging.info("Starting anomaly detection model training script.")

    # --- 1. Connect to MLflow ---
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)

    # Set the experiment - this will create it if it doesn't exist
    experiment_name = "anomaly-detection"
    mlflow.set_experiment(experiment_name)

    logging.info(f"Connected to MLflow at {MLFLOW_TRACKING_URI}")
    logging.info(f"Using experiment: {experiment_name}")

    # --- 2. Load Data ---
    logging.info(f"Attempting to load data from: {DATA_PATH}")
    try:
        if DATA_PATH.startswith("s3://"):
            # Data is in S3/MinIO, load all parquet files from the bucket
            if not all([S3_ENDPOINT_URL, S3_ACCESS_KEY_ID, S3_SECRET_ACCESS_KEY]):
                raise ValueError("S3 environment variables are not fully configured for S3 path.")

            storage_options = {
                "key": S3_ACCESS_KEY_ID,
                "secret": S3_SECRET_ACCESS_KEY,
                "client_kwargs": {"endpoint_url": S3_ENDPOINT_URL}
            }
            raw_df = pd.read_parquet(DATA_PATH, storage_options=storage_options)
            logging.info(f"Successfully loaded {len(raw_df)} events from data lake: {DATA_PATH}")
        else:
            # Fallback to loading a local CSV file
            raw_df = pd.read_csv(DATA_PATH)
            logging.info(f"Successfully loaded {len(raw_df)} events from local CSV: {DATA_PATH}")

    except FileNotFoundError:
        logging.error(f"Data file not found at {DATA_PATH}. Exiting.")
        exit(1)

    # --- 3. Feature Engineering ---
    featured_df = feature_engineering(raw_df)

    # --- 4. Create Training Set - Filter to NORMAL behavior only ---
    # Key insight: Train Isolation Forest on what NORMAL looks like
    # Bots have very short time gaps (< 1s), so we exclude those from training
    # This way the model learns "normal human behavior" and flags deviations

    logging.info("Filtering training data to normal user behavior...")

    # Remove very short gaps (likely bots) and very long gaps (inactive users)
    # Focus on typical human browsing: 2 seconds to 1 hour between events
    normal_behavior = featured_df[
        (featured_df['time_since_last_event_sec'] >= 2.0) &  # At least 2 seconds (human speed)
        (featured_df['time_since_last_event_sec'] <= 3600.0)  # At most 1 hour (active session)
    ]

    logging.info(f"Original dataset: {len(featured_df)} events")
    logging.info(f"Normal behavior subset: {len(normal_behavior)} events ({len(normal_behavior)/len(featured_df)*100:.1f}%)")

    # Add log-transformed feature to help Isolation Forest detect outliers
    # Log transform spreads out the distribution and makes extreme values more isolated
    import numpy as np
    normal_behavior['log_time_since_last'] = np.log1p(normal_behavior['time_since_last_event_sec'])

    X_train = normal_behavior[['time_since_last_event_sec', 'log_time_since_last']]

    # --- 5. Model Training ---
    # Start an MLflow run to log the training process
    with mlflow.start_run() as run:
        logging.info(f"Started MLflow run: {run.info.run_id}")
        mlflow.set_tag("ml.purpose", "anomaly-detection")
        mlflow.set_tag("training.strategy", "normal-behavior-only")
        mlflow.set_tag("training.type", TRAINING_TYPE)  # "bootstrap" or "retrain"
        mlflow.set_tag("data.source", DATA_PATH)

        # Define and train the Isolation Forest model
        # Since we're training ONLY on normal behavior, contamination should be low
        # (we expect very few anomalies in the filtered dataset)
        params = {
            "n_estimators": 100,
            "max_samples": "auto",
            "contamination": 0.15,  # 15% - higher threshold to catch out-of-range values
            "random_state": 42
        }
        model = IsolationForest(**params)
        model.fit(X_train)
        logging.info("Model training complete.")

        # Log parameters, metrics, and the model to MLflow
        mlflow.log_params(params)
        mlflow.log_metric("training_set_rows", len(X_train))
        mlflow.log_metric("original_dataset_rows", len(featured_df))
        mlflow.log_metric("normal_behavior_pct", len(normal_behavior)/len(featured_df)*100)
        mlflow.log_metric("min_time_gap_sec", float(X_train['time_since_last_event_sec'].min()))
        mlflow.log_metric("max_time_gap_sec", float(X_train['time_since_last_event_sec'].max()))
        mlflow.log_metric("median_time_gap_sec", float(X_train['time_since_last_event_sec'].median()))
        mlflow.sklearn.log_model(
            sk_model=model,
            artifact_path="model",
            registered_model_name=REGISTERED_MODEL_NAME
        )
        logging.info(f"Model logged and registered as '{REGISTERED_MODEL_NAME}'.")

    logging.info("Training script finished successfully.")
