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

## 4. Project Structure

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

## 5. Getting Started

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
    *   **MLflow UI**: `http://localhost:5001`
    *   **Gatekeeper API docs**: `http://localhost:8000/docs`
    *   **Kafka UI**: `http://localhost:8081`

4.  **Stop all services**:
    ```bash
    make down
    ```
