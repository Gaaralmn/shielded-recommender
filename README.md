# The Shielded Recommender

## 1. Introduction

"The Shielded Recommender" is a portfolio-grade MLOps project that demonstrates a complete, end-to-end machine learning system in a real-world scenario. The primary goal of this project is to build a recommender system that is protected from pollution by bot traffic. It achieves this by implementing a real-time anomaly detection service that acts as a "gatekeeper," filtering out suspicious interactions before they can be used for training the recommendation model.

This project is built with a focus on production-readiness, scalability, and maintainability, leveraging a modern microservices architecture and industry-standard MLOps tooling.

### Key Features:

*   **Real-time Anomaly Detection**: A FastAPI service uses an Isolation Forest model to identify and block bot traffic in real-time.
*   **Decoupled Architecture**: Services communicate asynchronously via Kafka message queues, ensuring scalability and resilience.
*   **Automated Model Training**: Airflow is used to orchestrate the periodic retraining of the anomaly detection model.
*   **Experiment Tracking & Model Registry**: MLflow is integrated for tracking model experiments and managing the lifecycle of trained models.
*   **Clean Data for Recommendations**: The recommender model (a TFRS model) is trained exclusively on data that has been vetted by the gatekeeper service, ensuring higher quality recommendations.

### Technology Stack:

*   **Data Ingestion**: Kafka
*   **Data Lake**: MinIO (S3-compatible)
*   **Anomaly Detection Service**: FastAPI, Redis, Scikit-learn (Isolation Forest)
*   **Recommender Training**: TensorFlow Recommenders
*   **Orchestration**: Apache Airflow
*   **Model Registry & Tracking**: MLflow
*   **Infrastructure**: Docker Compose

## 2. The Dataset

This project uses the **RetailRocket E-Commerce Dataset**, which is publicly available on Kaggle.

*   **Why this dataset?** It contains a year's worth of real-world e-commerce events (`view`, `addtocart`, `transaction`), making it ideal for building a recommender system.
*   **The Anomaly Detection Hook**: The dataset is raw clickstream data. We will use this to our advantage by writing a data producer that can "inject" synthetic bot traffic into the stream (e.g., a single user_id performing hundreds of `view` events in a few seconds). This allows us to rigorously test and validate our anomaly detector. You can download the dataset from [here](https://www.kaggle.com/datasets/retailrocket/ecommerce-dataset). The relevant file is `events.csv`. Please place it in the `data/` directory.

## 3. Engineering Decisions & Trade-offs

This section documents key architectural choices and the reasoning behind them. Showcasing this thought process is critical for senior-level engineering roles.

> #### Trade-off: Latency vs. Accuracy in Anomaly Detection
>
> *   **Decision**: I chose a simple **Isolation Forest** for the real-time anomaly detector instead of a heavier Deep Learning model like an LSTM or Autoencoder.
> *   **Reasoning**: While a more complex model might offer a marginal (e.g., 1-2%) accuracy improvement, its inference latency would be significantly higher (e.g., >100ms). The gatekeeper service sits in the critical, real-time path of data ingestion. Therefore, maintaining low latency (<50ms) was prioritized to ensure the system could handle high throughput without becoming a bottleneck. More complex fraud analysis can be performed offline on the `suspicious-events` data.

> #### Trade-off: Real-time vs. Batch Predictions
>
> *   **Decision**: The anomaly detection is performed in real-time on a per-event basis, while the recommender model is trained in a batch process (nightly).
> *   **Reasoning**: Anomaly detection must happen in real-time to prevent corrupt data from ever entering the system. Recommendation models, however, are less sensitive to single-event changes and are computationally expensive to train. A nightly batch training job on the complete set of `clean-events` is a standard and cost-effective industry pattern.

> #### Trade-off: Bootstrap vs. Continuous Retraining
>
> *   **Decision**: The system uses a two-phase training strategy: (1) Bootstrap training with historical data, (2) Continuous retraining with live production data.
> *   **Reasoning**: This mirrors real production ML systems. The bootstrap phase solves the "cold start" problem by training an initial model on historical data (RetailRocket CSV). Once the system is operational, the `kafka_to_minio_pipeline` accumulates clean events in the data lake, enabling daily retraining on fresh production data. This approach demonstrates understanding of the complete ML lifecycle: initial deployment, data accumulation, and model iteration.
> *   **Implementation**: Two separate Airflow DAGs handle this:
>     *   `bootstrap_initial_model`: Manual trigger, uses local CSV, runs once
>     *   `retrain_anomaly_model`: Scheduled daily, uses MinIO S3 data lake, continuous operation

## 4. Model Training Lifecycle

This project demonstrates production-grade MLOps practices with a complete model lifecycle:

### **Phase 1: Bootstrap (Cold Start)**
When first deploying the system, there is no trained model and no production data yet. The bootstrap process:

1. **Trigger** the `bootstrap_initial_model` DAG in Airflow (manual, one-time)
2. **Loads** historical RetailRocket dataset (`data/events.csv` - 1 year of e-commerce events)
3. **Trains** initial Isolation Forest model on normal user behavior patterns
4. **Registers** model as version 1 in MLflow model registry
5. **Enables** gatekeeper service to load and serve predictions

**Key Point**: This uses static historical data to get the system operational quickly.

### **Phase 2: Data Accumulation**
Once the gatekeeper is running with the bootstrap model:

1. **Producer** sends events to Kafka (`raw-events` topic)
2. **Gatekeeper** filters traffic in real-time, routes to `clean-events` or `suspicious-events` topics
3. **Kafka-to-MinIO pipeline** runs every 15 minutes, batching clean events into Parquet files
4. **Data lake grows** with partitioned production data: `s3://clean-events/year=2025/month=12/day=03/*.parquet`

**Key Point**: Clean, vetted data accumulates for future model improvements.

### **Phase 3: Continuous Retraining**
The `retrain_anomaly_model` DAG runs automatically:

1. **Scheduled** to run daily at midnight UTC
2. **Reads** all accumulated data from MinIO data lake (`s3://clean-events`)
3. **Trains** new model version on growing dataset (reflects latest user behavior patterns)
4. **Registers** new version to MLflow (version 2, 3, 4...)
5. **Gatekeeper** hot-reloads latest model (on next health check or restart)

**Key Point**: Model continuously improves as more production data is collected, adapting to evolving patterns.

### **Why This Matters**
This two-phase approach demonstrates:
- Understanding of ML "cold start" problem
- Production data pipelines (Kafka → MinIO)
- Automated retraining workflows (Airflow orchestration)
- Model versioning and registry (MLflow)
- Separation of bootstrap vs. production training logic

## 5. Project Structure

The project is organized into a modular, service-oriented architecture.

```
.
├── .github/                 # CI/CD workflows (placeholder)
├── .gitignore               # Files and directories to be ignored by Git
├── airflow/                 # Airflow configuration, DAGs, and plugins
├── data/                    # Local development data (e.g., events.csv)
├── infra/                   # Infrastructure as Code (e.g., Terraform, placeholder)
├── mlflow/                  # MLflow tracking data and artifacts
├── notebooks/               # Jupyter notebooks for EDA and prototyping
├── schemas/                 # Shared data contracts (Pydantic models)
├── services/                # Source code for the microservices
├── docker-compose.yml       # Local orchestration of all services
└── Makefile                 # Development shortcuts (up, down, test, etc.)
```

## 6. Getting Started

1.  **Build the Docker images**:
    ```bash
    make build
    ```

2.  **Start all services**:
    ```bash
    make up
    ```

3.  **Access the services**:
    *   **Airflow UI**: `http://localhost:8080` (user: `admin`, pass: `admin`)
    *   **MLflow UI**: `http://localhost:5000`
    *   **Gatekeeper API docs**: `http://localhost:8000/docs`
    *   **Kafka UI**: `http://localhost:8081`
    *   **MinIO Console**: `http://localhost:9001` (user: `minioadmin`, pass: `minioadmin`)
    *   **MinIO S3 API**: `http://localhost:9000`

4.  **Bootstrap the initial model** (one-time setup):

    Before the gatekeeper can filter traffic, you need to train an initial anomaly detection model:

    a. Go to Airflow UI: `http://localhost:8080`

    b. Find the `bootstrap_initial_model` DAG and trigger it manually

    c. This trains the first model using the historical RetailRocket dataset

    d. Check MLflow UI (`http://localhost:5000`) to verify the model was registered

    **Note**: This only needs to be run once. After this, the `retrain_anomaly_model` DAG will run automatically every night to retrain on live production data from the MinIO data lake.

5.  **Stop all services**:
    ```bash
    make down
    ```

## 7. Production Deployment Considerations

This project uses **Docker Compose** for local development, which is ideal for rapid iteration and demonstration. However, several architectural changes would be necessary for production deployment:

### **Orchestration: Docker Compose → Kubernetes**

**Current (Local Development):**
- Airflow uses `DockerOperator` to spawn training tasks
- Airflow containers run as root to access `/var/run/docker.sock`
- Simple, works great for single-machine development

**Production Approach:**
- Deploy Airflow on **Kubernetes** using the official [Airflow Helm Chart](https://airflow.apache.org/docs/helm-chart/stable/index.html)
- Replace `DockerOperator` with **`KubernetesPodOperator`**
- No Docker socket mounting required
- Proper RBAC and ServiceAccounts for security

**Example production DAG change:**
```python
# Current (DockerOperator for local dev)
from airflow.providers.docker.operators.docker import DockerOperator

# Production (KubernetesPodOperator)
from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator

KubernetesPodOperator(
    task_id="bootstrap_train",
    image="your-registry.io/shielded-recommender-trainer:v1.0.0",
    cmds=["python", "src/train.py"],
    namespace="ml-training",
    env_vars={
        "MLFLOW_TRACKING_URI": "http://mlflow.ml-system.svc.cluster.local:5000",
        "DATA_PATH": "/app/retailrocket/data/events.csv",
        "TRAINING_TYPE": "bootstrap",
    },
    service_account_name="airflow-worker",
    resources={
        "request_memory": "2Gi",
        "limit_memory": "4Gi",
        "request_cpu": "1",
        "limit_cpu": "2",
    },
)
```

### **Why This Matters**

**Security:**
- Running Airflow as root (current approach) is acceptable for local development but **not** for production
- Kubernetes RBAC provides fine-grained access control
- No direct Docker socket access eliminates a major security risk

**Scalability:**
- Kubernetes auto-scales worker pods based on load
- Multiple training jobs can run in parallel across cluster nodes
- Resource limits prevent runaway jobs

**Reliability:**
- Failed pods automatically restart
- Node failures don't take down the entire system
- Built-in health checks and monitoring

### **Other Production Changes**

| Component | Local Development | Production |
|-----------|------------------|------------|
| **Data Lake** | MinIO (self-hosted) | AWS S3 / GCS / Azure Blob |
| **Message Queue** | Kafka (single broker) | Kafka (multi-broker cluster) or AWS MSK |
| **Database** | PostgreSQL (single instance) | Managed PostgreSQL (RDS, Cloud SQL) with replicas |
| **MLflow** | Local tracking server | MLflow on K8s with S3 artifact store |
| **Secrets** | Hardcoded in docker-compose.yml | Kubernetes Secrets / AWS Secrets Manager / Vault |
| **Monitoring** | Manual log inspection | Prometheus + Grafana + ELK Stack |

### **Migration Path**

To transition this project to production:

1. **Containerize & Push Images**
   ```bash
   docker build -t your-registry.io/trainer:v1.0.0 -f services/trainer/Dockerfile .
   docker push your-registry.io/trainer:v1.0.0
   ```

2. **Deploy Infrastructure on Kubernetes**
   ```bash
   helm install airflow apache-airflow/airflow -f production-values.yaml
   kubectl apply -f k8s/mlflow-deployment.yaml
   kubectl apply -f k8s/kafka-cluster.yaml
   ```

3. **Update DAGs to use KubernetesPodOperator**
   - Replace all `DockerOperator` instances
   - Add resource limits and requests
   - Configure service accounts

4. **Set up Monitoring & Alerting**
   - Deploy Prometheus for metrics collection
   - Configure Grafana dashboards
   - Set up PagerDuty/Slack alerts for failures

This architecture demonstrates understanding of the development-to-production lifecycle while keeping local development simple and accessible.
