# MLOps Development Guide: The Shielded Recommender

## Introduction

This guide will walk you through the end-to-end development of "The Shielded Recommender" project. As a senior software engineer, you already have a strong foundation in building robust systems. This guide will bridge the gap between traditional software engineering and machine learning engineering by focusing on the MLOps lifecycle.

We will follow a standard, iterative process, moving from data to model to API, all within our containerized environment. For each phase, we'll discuss not just *what* to do, but *why* we're doing it that way, focusing on the trade-offs and design patterns that are crucial for production ML systems.

---

## Phase 1: Data - Replaying the Clickstream

Our first task is to create a realistic stream of data. We'll use a real-world e-commerce dataset and build a service to "replay" it into Kafka, while also giving us the power to inject anomalies.

**Goal**: Implement the `data_producer` service to read the **RetailRocket dataset**, inject synthetic bot traffic, and send the resulting events to the `raw-clickstream` Kafka topic.

### Your Tasks:

1.  **Download the Data**:
    *   Download the [RetailRocket dataset from Kaggle](https://www.kaggle.com/datasets/retailrocket/ecommerce-dataset).
    *   Place the `events.csv` file inside the `data/` directory.

2.  **Implement the Producer Logic**:
    *   Open `services/data_producer/src/producer.py`.
    *   This script will read `events.csv` row by row.
    *   For each row, it will create a `ClickEvent` object (using the schema from `schemas.events`).
    *   It will send the event to the `raw-clickstream` Kafka topic.
    *   **Bot Injection**: To test our system, we must create anomalies. A great way to do this is to have the producer, on occasion, pick a random `user_id` and generate an unrealistic burst of `view` events for that user in a very short time. This is the "bot attack" we want to shield our recommender from.

### MLOps Mentorship: Key Concepts & Trade-offs

*   **Why Replay a Real Dataset?** While purely random data is easy to generate, it often lacks the subtle patterns and characteristics of real user behavior. Replaying a real dataset gives our system a much more realistic foundation. Injecting synthetic anomalies into this real data gives us the best of both worlds: realistic traffic and controllable, known anomalies for testing.
*   **Kafka Topics as a Source of Truth**: We're using descriptive topic names. `raw-clickstream` is the unfiltered, untrusted source of all events. Later, we'll create `clean-events` and `suspicious-events`. This is a powerful pattern. Different services can consume from the topic that suits their needs, and the data lineage is clear.

---

## Phase 2: Model - Training the Anomaly Detector

With data flowing, we can now train our model. We need a model that can learn what "normal" user behavior looks like.

**Goal**: Train an Isolation Forest model on the clickstream data, focusing on "session velocity," and save the model to the MLflow Model Registry.

### Your Tasks:

1.  **Exploratory Data Analysis (EDA)**:
    *   Use the `notebooks/` directory.
    *   Read the `events.csv` file and analyze the patterns.
    *   Focus on features you can use to identify a "session." A good starting point for a feature is **session velocity**: the number of clicks a user performs in a given time window (e.g., clicks per minute). You should see a clear difference between your injected bots and normal users.

2.  **Create a Training Script**:
    *   Move your feature engineering and training logic to `services/trainer/src/train.py`.
    *   This script should:
        a. Connect to MLflow: `mlflow.set_tracking_uri("http://mlflow:5000")`.
        b. Start an MLflow run: `with mlflow.start_run():`.
        c. Load the `events.csv` data.
        d. Engineer the "session velocity" feature.
        e. Train a `sklearn.ensemble.IsolationForest` model on this feature.
        f. Log parameters and metrics to MLflow.
        g. Log the trained model using `mlflow.sklearn.log_model()`.

### MLOps Mentorship: Key Concepts & Trade-offs

*   **Feature Engineering is Key**: The raw data (`user_id`, `item_id`) isn't enough for an anomaly detector. The magic is in the features you create. "Session velocity" is a classic example of a behavioral feature. The model doesn't learn about users; it learns about *behavior*.
*   **The Power of a Model Registry**: By logging the model to MLflow, you're not just saving a file. You're creating an audit trail. You know exactly which version of your code, on which data, with which parameters, created that model artifact. This is non-negotiable for any serious ML system.

---

## Phase 3: API - Implementing the Gatekeeper

Now we'll build the service that uses our trained model to stand guard in front of our clean data stream.

**Goal**: Implement the `gatekeeper` service to consume events from `raw-clickstream`, use the model to predict anomalies, and forward events to either `clean-events` or `suspicious-events`.

### Your Tasks:

1.  **Load the Model**:
    *   In `services/gatekeeper/src/main.py`, use the MLflow client to load your trained Isolation Forest model from the registry.

2.  **Consume, Predict, and Forward**:
    *   Implement a Kafka consumer listening to the `raw-clickstream` topic.
    *   For each message:
        a. Calculate the "session velocity" feature. This will require keeping track of recent events for each user. **Redis is perfect for this.** You can store a timestamped list of recent events for each `user_id` with a short TTL.
        b. Use the model to predict if the event is an anomaly.
        c. **If Normal**: Produce the event to the `clean-events` Kafka topic.
        d. **If Anomaly**: Produce the event to the `suspicious-events` topic. Then, **ban the user**: add the `user_id` to a Redis set with an expiry of 10 minutes.

### MLOps Mentorship: Key Concepts & Trade-offs

*   **Redis for Real-time State**: Why Redis? Our anomaly detection model needs state (the user's recent clicks) to calculate features. Redis is an in-memory database, which means it is incredibly fast—perfect for a real-time service where latency is critical. Using it to temporarily ban users is also a powerful and efficient pattern.
*   **Data Segregation**: We don't just drop anomalies; we send them to a `suspicious-events` topic. This is a crucial design choice. It allows us to analyze bot behavior offline, perhaps to train a more sophisticated fraud detection model later, without polluting our main training pipeline.

---

## Phase 4: The Data Lake

The `clean-events` topic now contains a stream of data we trust. But Kafka isn't designed for long-term storage or for the kind of large-scale batch queries needed to train a heavy model like a recommender. For that, we need a data lake.

**Goal**: Persist the `clean-events` data into a data lake for future batch processing.

**The Tool**: We will use **MinIO**, which is a lightweight, S3-compatible object storage server that is perfect for local development. We can add a service to our system (e.g., a simple Python script orchestrated by Airflow) that consumes from `clean-events` and writes the data in batches (e.g., as Parquet files) to a MinIO "bucket."

**This is a critical step that bridges the gap between streaming and batch.**

---

## Phase 5 & Beyond

Once the above phases are complete, you have a best-practice MLOps loop for creating a trusted dataset. The next steps are:

*   **Orchestration with Airflow**:
    1.  Create a DAG to periodically run our `trainer` script to retrain the anomaly detection model.
    2.  Create a second DAG that runs a script to consume from `clean-events` and save the data to our MinIO data lake.
*   **Building the Recommender**: Implement the `trainer` service to read all the clean data from MinIO and train a powerful TensorFlow Recommenders model.
*   **Serving Recommendations**: Create a new FastAPI service that loads the trained recommender model. When a request comes in for a user, it first checks Redis to see if the user is banned. If not, it serves a recommendation.

This structured approach ensures you are building a robust and scalable system, not just a one-off model. Welcome to the world of MLOps!
