# MLflow Version Compatibility Guide

## Current Version Strategy

All components use **MLflow 2.17.0** for consistency:

- **MLflow Server** (Docker): `ghcr.io/mlflow/mlflow:v2.17.0`
- **Trainer Service**: `mlflow==2.17.0`
- **Gatekeeper Service**: `mlflow==2.17.0`

## Why Version Consistency Matters

### 1. Training → Tracking Server
- The Python library in `services/trainer` communicates with the MLflow server
- **Required**: Same major version (2.x)
- **Recommended**: Same minor version (2.17.x)
- **OK**: Different patch versions (2.17.0 vs 2.17.1)

### 2. Model Serving → Model Registry
- The gatekeeper loads models that were saved by the trainer
- Both use the same MLflow version to ensure serialization compatibility
- The underlying model library (scikit-learn) version is more critical than MLflow

## Upgrading MLflow

When upgrading MLflow, follow this order:

1. **Test in development first**
2. **Upgrade the server** (update `MLFLOW_IMAGE_TAG` in docker-compose.yml)
3. **Run database migrations** (`mlflow db upgrade`)
4. **Update client libraries** (trainer and gatekeeper requirements.txt)
5. **Rebuild and test all services**

### Example Upgrade Process

```bash
# 1. Update .env or docker-compose.yml
MLFLOW_IMAGE_TAG=v2.18.0

# 2. Update requirements.txt files
echo "mlflow==2.18.0" >> services/trainer/requirements.txt
echo "mlflow==2.18.0" >> services/gatekeeper/requirements.txt

# 3. Restart services
docker compose down
docker compose up -d mlflow-db-upgrade  # Runs migrations
docker compose up -d mlflow
docker compose build trainer gatekeeper
docker compose up -d
```

## Compatibility Matrix

| Trainer MLflow | Server MLflow | Gatekeeper MLflow | Status |
|---------------|---------------|-------------------|---------|
| 2.17.0        | 2.17.0       | 2.17.0           | ✅ Ideal |
| 2.17.0        | 2.17.1       | 2.17.0           | ✅ Safe  |
| 2.17.0        | 2.16.0       | 2.17.0           | ⚠️ Works, not recommended |
| 2.17.0        | 2.18.0       | 2.17.0           | ⚠️ Works, update clients |
| 2.17.0        | 1.30.0       | 2.17.0           | ❌ Breaking changes |

## Version Pinning Strategy

### Production
Always pin exact versions:
```txt
mlflow==2.17.0
scikit-learn==1.3.0
```

### Development
You can use compatible version ranges:
```txt
mlflow>=2.17.0,<2.18.0
```

## Model Compatibility

Models saved with MLflow include dependency information:

```yaml
# conda.yaml (auto-generated)
dependencies:
  - python=3.9
  - pip:
    - mlflow==2.17.0
    - scikit-learn==1.3.0
```

**When loading models**:
- MLflow can automatically restore the exact environment
- Or use `mlflow.pyfunc.load_model()` which handles version mismatches better
- Current approach with `mlflow.sklearn.load_model()` requires compatible sklearn versions

## Troubleshooting

### Issue: "Model was saved with MLflow X but loading with Y"
**Solution**: Match the MLflow versions or use `mlflow.pyfunc.load_model()`

### Issue: "Cannot connect to MLflow server"
**Solution**: Check client/server versions are compatible (same major.minor)

### Issue: "Model prediction fails after loading"
**Solution**: Check scikit-learn version compatibility, not just MLflow

## References

- [MLflow Versioning Policy](https://mlflow.org/docs/latest/versioning.html)
- [MLflow Model Registry](https://mlflow.org/docs/latest/model-registry.html)
- [MLflow Python API Docs](https://mlflow.org/docs/latest/python_api/index.html)
