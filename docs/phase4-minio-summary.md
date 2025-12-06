# Phase 4: MinIO Data Lake - Setup Complete ✅

MinIO has been successfully integrated into your Shielded Recommender project as the S3-compatible data lake.

## What Was Added

### 1. Docker Compose Services

**MinIO Server** (`minio`)
- S3-compatible object storage
- API endpoint: http://localhost:9000
- Web console: http://localhost:9001
- Credentials: `minioadmin` / `minioadmin`

**MinIO Setup** (`minio-setup`)
- Automatically creates buckets on startup:
  - `clean-events` - Validated events from gatekeeper
  - `suspicious-events` - Flagged anomalous events
  - `raw-events` - Optional raw event backup

### 2. Data Flow Architecture

```
┌──────────────┐      ┌──────────────┐      ┌──────────────┐
│ Data Producer│─────▶│    Kafka     │─────▶│  Gatekeeper  │
│              │      │ raw-events   │      │  (Anomaly    │
└──────────────┘      └──────────────┘      │  Detection)  │
                                            └──────┬───────┘
                                                   │
                          ┌────────────────────────┴───────────────┐
                          │                                        │
                          ▼                                        ▼
                  ┌──────────────┐                        ┌──────────────┐
                  │    Kafka     │                        │    Kafka     │
                  │clean-events  │                        │suspicious-   │
                  └──────┬───────┘                        │events        │
                         │                                └──────────────┘
                         ▼
                  ┌──────────────┐
                  │kafka_to_minio│ ◀─── Airflow DAG (every 15 min)
                  │   pipeline   │
                  └──────┬───────┘
                         │
                         ▼
                  ┌──────────────┐
                  │    MinIO     │ ◀─── Data Lake (S3-compatible)
                  │ clean-events │
                  │   bucket     │
                  └──────┬───────┘
                         │
                         ▼
                  ┌──────────────┐
                  │   Retrain    │ ◀─── Airflow DAG (daily)
                  │ Anomaly Model│
                  └──────────────┘
```

## Quick Start

### 1. Start MinIO

```bash
# Start just MinIO
docker-compose up -d minio minio-setup

# Or start all services
docker-compose up -d
```

### 2. Access MinIO Console

Open http://localhost:9001 in your browser:
- Username: `minioadmin`
- Password: `minioadmin`

You should see three buckets:
- clean-events
- suspicious-events
- raw-events

### 3. Test MinIO Connectivity

```bash
python scripts/test-minio.py
```

Expected output:
```
✅ Successfully wrote to MinIO: s3://clean-events/test/...
✅ Successfully read 1 rows from MinIO
✅ Found 1 files/directories in 'clean-events' bucket
✅ All tests passed! MinIO is working correctly.
```

## Using MinIO in Your Code

### Python Example (data_pipeline_worker)

```python
import pandas as pd

# Configuration
storage_options = {
    'key': 'minioadmin',
    'secret': 'minioadmin',
    'client_kwargs': {'endpoint_url': 'http://minio:9000'}
}

# Write data to MinIO
df.to_parquet(
    's3://clean-events/year=2025/month=12/day=05/batch.parquet',
    storage_options=storage_options
)

# Read data from MinIO
df = pd.read_parquet(
    's3://clean-events',
    storage_options=storage_options
)
```

### Environment Variables

Services can reference these environment variables:
```bash
S3_ENDPOINT_URL=http://minio:9000
S3_ACCESS_KEY_ID=minioadmin
S3_SECRET_ACCESS_KEY=minioadmin
S3_BUCKET=clean-events
```

## Data Partitioning Strategy

The Kafka-to-MinIO pipeline uses Hive-style partitioning:

```
s3://clean-events/
├── year=2025/
│   └── month=12/
│       └── day=05/
│           ├── batch_20251205_000000.parquet
│           ├── batch_20251205_001500.parquet
│           └── batch_20251205_003000.parquet
```

**Benefits:**
- **Efficient queries** - Query only relevant date ranges
- **Easy data lifecycle** - Delete old partitions easily
- **Fast incremental processing** - Process only new dates

## Integration with Airflow DAGs

### kafka_to_minio_pipeline DAG

**Schedule:** Every 15 minutes
**Purpose:** Batch events from Kafka → MinIO

**Configuration:**
```python
environment={
    "KAFKA_BROKER": "kafka:9092",
    "KAFKA_TOPIC": "clean-events",
    "S3_ENDPOINT_URL": "http://minio:9000",
    "S3_ACCESS_KEY_ID": "minioadmin",
    "S3_SECRET_ACCESS_KEY": "minioadmin",
    "S3_BUCKET": "clean-events",
}
```

### retrain_anomaly_model DAG

**Schedule:** Daily at midnight
**Purpose:** Retrain model on accumulated data lake

**Configuration:**
```python
environment={
    "DATA_PATH": "s3://clean-events",
    "S3_ENDPOINT_URL": "http://minio:9000",
    "S3_ACCESS_KEY_ID": "minioadmin",
    "S3_SECRET_ACCESS_KEY": "minioadmin",
}
```

## Monitoring

### Check Storage Usage

```bash
# Via MinIO Console
# http://localhost:9001 → Buckets → clean-events → Summary

# Via CLI
docker exec shielded-recommender-minio-1 mc du local/clean-events
```

### List Recent Files

```bash
docker exec shielded-recommender-minio-1 mc ls --recursive local/clean-events
```

### View Logs

```bash
docker-compose logs minio
docker-compose logs minio-setup
```

## Verification Checklist

- [x] MinIO container running
- [x] MinIO accessible at http://localhost:9000
- [x] MinIO Console accessible at http://localhost:9001
- [x] Buckets created: clean-events, suspicious-events, raw-events
- [x] Test script passes: `python scripts/test-minio.py`
- [ ] kafka_to_minio_pipeline DAG configured
- [ ] retrain_anomaly_model DAG can read from MinIO

## Next Steps

### 1. Test the Complete Pipeline

```bash
# 1. Start all services
docker-compose up -d

# 2. Trigger bootstrap DAG (if not done already)
docker exec -u airflow shielded-recommender-airflow-scheduler-1 \
  airflow dags trigger bootstrap_initial_model

# 3. Start data producer
docker exec shielded-recommender-data_producer-1 python src/producer.py

# 4. Wait 15 minutes for kafka_to_minio_pipeline to run
# Or trigger manually:
docker exec -u airflow shielded-recommender-airflow-scheduler-1 \
  airflow dags trigger kafka_to_minio_pipeline

# 5. Check MinIO console - you should see data in clean-events bucket!
```

### 2. Verify Data Accumulation

After the pipeline runs:
```bash
# Check files in MinIO
python scripts/test-minio.py

# Or via console
# http://localhost:9001 → clean-events → Browse
```

### 3. Test Model Retraining

Once data accumulates in MinIO:
```bash
# Trigger retrain DAG
docker exec -u airflow shielded-recommender-airflow-scheduler-1 \
  airflow dags trigger retrain_anomaly_model

# Check that it reads from s3://clean-events
docker-compose logs trainer
```

## Troubleshooting

### MinIO Container Won't Start

```bash
# Check logs
docker-compose logs minio

# Common fix: Remove volume and restart
docker-compose down -v
docker-compose up -d minio minio-setup
```

### Buckets Not Created

```bash
# Check setup logs
docker-compose logs minio-setup

# Manually create
docker exec shielded-recommender-minio-1 mc mb local/clean-events
```

### Connection Errors from Services

Ensure services reference MinIO correctly:
- **Inside Docker network:** `http://minio:9000`
- **From host machine:** `http://localhost:9000`

## Production Migration Path

When deploying to GCP:

### Replace MinIO with Cloud Storage

**Local (MinIO):**
```python
storage_options = {
    'endpoint_url': 'http://minio:9000',
    'key': 'minioadmin',
    'secret': 'minioadmin'
}
```

**Production (GCS):**
```python
# Option 1: Use GCS native API
from google.cloud import storage

# Option 2: Use S3-compatible endpoint
storage_options = {
    'endpoint_url': 'https://storage.googleapis.com',
    'key': os.getenv('GCS_ACCESS_KEY'),
    'secret': os.getenv('GCS_SECRET_KEY')
}

# Option 3: Use Workload Identity (no keys!)
# Just remove endpoint_url, uses default GCP credentials
```

**Code changes:** Minimal - just environment variables!

## Summary

✅ **MinIO is now set up and ready to serve as your data lake!**

**What you have:**
- S3-compatible object storage running locally
- Three buckets for different data types
- Partitioned data organization
- Ready for integration with Airflow pipelines
- Same S3 API as production cloud storage

**What's next:**
- Implement kafka_to_minio.py in data_pipeline_worker
- Test the complete data flow
- Verify daily retraining works with data lake

For detailed usage, see [docs/minio-setup.md](./minio-setup.md)
