# MinIO Data Lake Setup

MinIO is an S3-compatible object storage system that serves as the data lake for storing clean event data.

## Quick Start

### 1. Start MinIO

```bash
docker-compose up -d minio minio-setup
```

The `minio-setup` container automatically creates three buckets:
- `clean-events` - Validated events from the gatekeeper
- `suspicious-events` - Flagged anomalous events
- `raw-events` - Optional backup of all raw events

### 2. Access MinIO

**Web Console:**
- URL: http://localhost:9001
- Username: `minioadmin`
- Password: `minioadmin`

**S3 API Endpoint:**
- URL: http://localhost:9000
- Access Key: `minioadmin`
- Secret Key: `minioadmin`

### 3. Verify Buckets

```bash
# Using MinIO CLI
docker exec shielded-recommender-minio-1 mc ls local

# Or via API
curl http://localhost:9000
```

## Using MinIO in Your Services

### Python with s3fs (Recommended)

```python
import pandas as pd

# Read from MinIO
df = pd.read_parquet(
    's3://clean-events',
    storage_options={
        'key': 'minioadmin',
        'secret': 'minioadmin',
        'endpoint_url': 'http://minio:9000'
    }
)

# Write to MinIO
df.to_parquet(
    's3://clean-events/year=2025/month=12/data.parquet',
    storage_options={
        'key': 'minioadmin',
        'secret': 'minioadmin',
        'endpoint_url': 'http://minio:9000'
    }
)
```

### Python with boto3

```python
import boto3

s3 = boto3.client(
    's3',
    endpoint_url='http://minio:9000',
    aws_access_key_id='minioadmin',
    aws_secret_access_key='minioadmin'
)

# List buckets
response = s3.list_buckets()
print([bucket['Name'] for bucket in response['Buckets']])

# Upload file
s3.upload_file('data.parquet', 'clean-events', 'year=2025/month=12/data.parquet')

# Download file
s3.download_file('clean-events', 'year=2025/month=12/data.parquet', 'local_data.parquet')
```

## Data Organization

The Kafka-to-MinIO pipeline organizes data with partitioning:

```
s3://clean-events/
├── year=2025/
│   ├── month=01/
│   │   ├── day=01/
│   │   │   ├── batch_20250101_000000.parquet
│   │   │   └── batch_20250101_001500.parquet
│   │   └── day=02/
│   │       └── batch_20250102_000000.parquet
│   └── month=02/
│       └── day=01/
│           └── batch_20250201_000000.parquet
```

This partitioning enables:
- Efficient time-based queries
- Easy data lifecycle management
- Fast incremental processing

## Bucket Details

### clean-events
**Purpose:** Stores events that passed anomaly detection
**Writer:** `kafka_to_minio_pipeline` Airflow DAG
**Reader:** `retrain_anomaly_model` Airflow DAG
**Format:** Parquet files with Hive-style partitioning

### suspicious-events
**Purpose:** Stores events flagged as anomalous
**Writer:** Gatekeeper consumer (optional)
**Reader:** Analysis tools, fraud detection
**Format:** Parquet files

### raw-events
**Purpose:** Optional backup of all events before filtering
**Writer:** Data producer (optional)
**Reader:** Debugging, replay scenarios
**Format:** Parquet files

## Monitoring Storage

### Check Bucket Size

```bash
# Via MinIO Console
# Navigate to http://localhost:9001 → Buckets → clean-events

# Via CLI
docker exec shielded-recommender-minio-1 mc du local/clean-events
```

### List Recent Files

```bash
docker exec shielded-recommender-minio-1 mc ls --recursive local/clean-events
```

## Troubleshooting

### Buckets Not Created

```bash
# Check setup logs
docker-compose logs minio-setup

# Manually create buckets
docker exec shielded-recommender-minio-1 mc mb local/clean-events
```

### Connection Refused

Ensure MinIO is running:
```bash
docker-compose ps minio

# Restart if needed
docker-compose restart minio
```

### Access Denied

Verify credentials in your code match the environment variables:
```bash
echo $MINIO_ROOT_USER      # Should be: minioadmin
echo $MINIO_ROOT_PASSWORD  # Should be: minioadmin
```

## Production Considerations

When moving to production (GCP):

1. **Replace MinIO with Cloud Storage:**
   ```python
   # Development (MinIO)
   endpoint_url='http://minio:9000'

   # Production (GCS)
   endpoint_url='https://storage.googleapis.com'
   # Or use native GCS client
   ```

2. **Update bucket names:**
   ```python
   # Development
   bucket = 'clean-events'

   # Production
   bucket = 'shielded-recommender-clean-events-prod'
   ```

3. **Use IAM instead of access keys:**
   - Workload Identity in GKE
   - Service account keys in VMs

## Backup and Recovery

### Export Data from MinIO

```bash
# Download all data from a bucket
docker exec shielded-recommender-minio-1 mc cp --recursive \
  local/clean-events ./backup/clean-events/
```

### Import Data to MinIO

```bash
# Upload data to bucket
docker exec -v $(pwd)/backup:/backup shielded-recommender-minio-1 \
  mc cp --recursive /backup/clean-events/ local/clean-events/
```

## Integration with Kafka-to-MinIO Pipeline

The Airflow DAG `kafka_to_minio_pipeline` automatically:
1. Consumes events from Kafka `clean-events` topic
2. Batches them (default: 5000 events or 60 seconds)
3. Writes as Parquet to MinIO with date partitioning
4. Runs every 15 minutes

See [kafka_to_minio_pipeline.py](../airflow/dags/kafka_to_minio_pipeline.py) for details.
