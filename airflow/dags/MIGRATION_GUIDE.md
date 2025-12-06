# Airflow Environment Migration Guide

This guide explains how to manage DAGs across development and production environments.

## Quick Start

### Development (Current Setup)
```bash
# Use Docker Compose
export AIRFLOW_ENV=dev  # or leave unset (dev is default)
docker-compose up -d
```

### Production (Kubernetes)
```bash
# Deploy to Kubernetes
export AIRFLOW_ENV=prod
helm install airflow apache-airflow/airflow -f production-values.yaml
```

---

## Architecture Patterns

### Current Approach: Environment-Specific DAG Files

**Files:**
- `bootstrap_initial_model.py` - DockerOperator only (current implementation)
- `retrain_anomaly_model.py` - DockerOperator only (current implementation)

**Pros:**
- Simple, explicit
- No abstraction complexity
- Easy to understand

**Cons:**
- Manual migration required when deploying to production
- Can't test production code locally
- Risk of dev/prod drift

---

### Recommended Approach: Operator Factory Pattern

**Files:**
- `lib/operator_factory.py` - Abstraction layer
- `bootstrap_initial_model_v2.py` - Environment-agnostic DAG (example)

**Pros:**
- Single DAG works in both environments
- Controlled via `AIRFLOW_ENV` environment variable
- Can test prod configuration locally
- Centralized environment logic

**Cons:**
- Slight abstraction overhead
- Need to understand factory pattern

---

## Migration Steps

### Option 1: Keep Current Approach (No Migration)

If you deploy to production later, you'll manually update DAGs:

1. Create `airflow/dags/prod/` directory
2. Copy DAG files
3. Replace all `DockerOperator` with `KubernetesPodOperator`
4. Deploy only `prod/` folder to production Airflow

**When to choose:** You never plan to test production DAGs locally.

---

### Option 2: Adopt Operator Factory (Recommended for Portfolio)

Demonstrates production-ready design patterns:

1. **Create factory** (already done):
   - `lib/operator_factory.py`
   - `lib/__init__.py`

2. **Refactor existing DAGs** (optional):
   ```python
   # Before (DockerOperator only)
   from airflow.providers.docker.operators.docker import DockerOperator

   DockerOperator(
       task_id="train",
       image="trainer:latest",
       command="python train.py",
       network_mode="shielded-recommender_default",
       environment={"KEY": "value"},
       docker_url="unix://var/run/docker.sock",
   )

   # After (Environment-agnostic)
   from lib.operator_factory import create_training_operator

   create_training_operator(
       task_id="train",
       image="trainer:latest",
       command="python train.py",
       env_vars={"KEY": "value"},
   )
   ```

3. **Set environment variable**:
   ```bash
   # docker-compose.yml
   airflow-webserver:
     environment:
       - AIRFLOW_ENV=dev  # Explicitly set

   # production-values.yaml (Kubernetes)
   env:
     - name: AIRFLOW_ENV
       value: "prod"
   ```

**When to choose:** You want to demonstrate production-ready patterns in your portfolio.

---

## Testing Both Environments Locally

You can test both operator types without deploying to Kubernetes:

```bash
# Test development mode
export AIRFLOW_ENV=dev
docker-compose restart airflow-scheduler airflow-webserver

# Trigger DAG - uses DockerOperator
docker exec -u airflow shielded-recommender-airflow-scheduler-1 \
  airflow dags trigger bootstrap_initial_model_v2
```

For production mode (requires local Kubernetes):
```bash
# Start minikube or kind
kind create cluster

# Deploy Airflow to local K8s
helm install airflow apache-airflow/airflow

# Test production mode
export AIRFLOW_ENV=prod
# Trigger DAG - uses KubernetesPodOperator
```

---

## Environment Variable Reference

| Variable | Values | Default | Purpose |
|----------|--------|---------|---------|
| `AIRFLOW_ENV` | `dev`, `prod` | `dev` | Controls operator type |

### Example Configurations

**Development (docker-compose.yml):**
```yaml
airflow-scheduler:
  environment:
    - AIRFLOW_ENV=dev
```

**Production (Kubernetes values.yaml):**
```yaml
env:
  - name: AIRFLOW_ENV
    value: "prod"
```

---

## Comparison: Before vs After

### Before (Current)
```
bootstrap_initial_model.py
└── DockerOperator (hardcoded)
    ├── network_mode: shielded-recommender_default
    ├── docker_url: unix://var/run/docker.sock
    └── Works only in Docker Compose
```

### After (Operator Factory)
```
bootstrap_initial_model_v2.py
└── create_training_operator() (dynamic)
    ├── AIRFLOW_ENV=dev → DockerOperator
    └── AIRFLOW_ENV=prod → KubernetesPodOperator
```

---

## Production Deployment Checklist

When deploying to Kubernetes:

- [ ] Set `AIRFLOW_ENV=prod` in Helm values
- [ ] Update image references to container registry (e.g., `gcr.io/myproject/trainer:v1.0.0`)
- [ ] Configure Kubernetes ServiceAccount with proper RBAC
- [ ] Update MLflow URI to Kubernetes service DNS
- [ ] Configure S3/GCS for data lake (replace MinIO)
- [ ] Set up secrets management (Kubernetes Secrets / Vault)
- [ ] Configure resource limits per environment needs
- [ ] Test DAGs in staging environment first

---

## Troubleshooting

### DAG not appearing in UI after refactoring
**Cause:** Python import error in factory module
**Fix:** Check Airflow scheduler logs for import errors

### Task fails with "No module named 'lib'"
**Cause:** `lib/` directory not in PYTHONPATH
**Fix:** Ensure `lib/` is under `dags/` folder (Airflow auto-adds `dags/` to path)

### Different behavior in dev vs prod
**Cause:** Environment variable not set correctly
**Fix:** Verify `AIRFLOW_ENV` with:
```bash
docker exec airflow-scheduler-1 printenv AIRFLOW_ENV
```

---

## Recommended Next Steps

For your portfolio project:

1. **Keep current DAGs** (`bootstrap_initial_model.py`, `retrain_anomaly_model.py`)
   - They work, they're simple, they demonstrate the actual implementation

2. **Add factory example** (`bootstrap_initial_model_v2.py`)
   - Shows you understand production patterns
   - Demonstrates abstraction and environment handling
   - Tag it clearly as "production-ready pattern example"

3. **Document in README**
   - Link to this migration guide
   - Explain why you chose operator factory pattern
   - Show you've thought about the full lifecycle

This way, reviewers see:
- ✅ Working implementation (current DAGs)
- ✅ Production awareness (factory pattern)
- ✅ Migration strategy (this guide)
- ✅ Thoughtful engineering decisions
