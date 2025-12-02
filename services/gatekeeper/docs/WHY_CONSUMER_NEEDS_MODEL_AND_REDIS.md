# Why the Consumer Needs Both Model and Redis

## TL;DR

The consumer needs:
- **Model**: To predict if events are anomalies
- **Redis**: To calculate features AND to ban users

This is the right design for this use case.

## The Consumer's Responsibilities

```python
# consumer.py calls these from main.py:
load_model_from_registry()  # ← Why?
initialize_redis()          # ← Why?
run_kafka_consumer()
```

### 1. Model - Required for Prediction

The consumer **must** predict anomalies in real-time:

```python
# In process_event() - main.py:207
prediction = model.predict(X)[0]  # ← Consumer needs model here

if prediction == -1:
    # Anomaly - route to suspicious-events
    producer.send(SUSPICIOUS_EVENTS_TOPIC, value=event)
    ban_user(user_id)
else:
    # Normal - route to clean-events
    producer.send(CLEAN_EVENTS_TOPIC, value=event)
```

**Without the model**, the consumer can't decide where to route events!

### 2. Redis - Required for Two Things

#### A. Feature Calculation (Session Velocity)

The model needs `time_since_last_event_sec` as input:

```python
# In calculate_time_since_last_event() - main.py:103
last_timestamp_str = redis_client.lindex(history_key, 0)  # ← Get last event

# Calculate feature
time_since_last = (current_timestamp_ms - last_timestamp_ms) / 1000.0

# Store for next event
redis_client.lpush(history_key, current_timestamp_ms)  # ← Save current event
```

This feature **can only be calculated at consume time**, not before:
- Each user's event history evolves
- Need to look up the last event for THIS specific user
- Need real-time state

#### B. User Banning

When anomaly detected, ban the user immediately:

```python
# In ban_user() - main.py:171
redis_client.zadd(banned_with_ttl_key, {user_id: expiry_time})
```

This prevents further events from the same user being processed.

## Data Flow

```
┌──────────────────┐
│ Kafka: raw-      │
│ clickstream      │
└────────┬─────────┘
         │ event
         ↓
┌─────────────────────────────────────┐
│     Consumer Process                │
│                                     │
│  ┌────────────────────────────┐    │
│  │ 1. Check if user banned    │ ←──┼── Redis
│  │    (zscore check)          │    │
│  └──────────┬─────────────────┘    │
│             │ not banned            │
│             ↓                       │
│  ┌────────────────────────────┐    │
│  │ 2. Get last event time     │ ←──┼── Redis
│  │    (lindex)                │    │
│  └──────────┬─────────────────┘    │
│             │ last_timestamp        │
│             ↓                       │
│  ┌────────────────────────────┐    │
│  │ 3. Calculate feature       │    │
│  │    time_since_last_event   │    │
│  └──────────┬─────────────────┘    │
│             │ feature value         │
│             ↓                       │
│  ┌────────────────────────────┐    │
│  │ 4. Store current event     │ ───┼→ Redis
│  │    (lpush)                 │    │
│  └──────────┬─────────────────┘    │
│             │                       │
│             ↓                       │
│  ┌────────────────────────────┐    │
│  │ 5. Predict anomaly         │ ←──┼── Model
│  │    model.predict(X)        │    │
│  └──────────┬─────────────────┘    │
│             │ prediction            │
│             ↓                       │
│       ┌─────┴─────┐                │
│       │ Anomaly?  │                │
│       └─────┬─────┘                │
│     Yes ←───┴───→ No               │
│      │               │              │
│      ↓               ↓              │
│  ┌───────────┐  ┌──────────┐      │
│  │Ban user   │  │Route to  │      │
│  │in Redis   │  │clean     │      │
│  │(zadd)     │  │events    │      │
│  └─────┬─────┘  └────┬─────┘      │
│        │             │              │
│        ↓             ↓              │
│  ┌────────────────────────────┐    │
│  │ Route to suspicious-events │    │
│  └────────────────────────────┘    │
│                                     │
└─────────────────────────────────────┘
         │
         ↓
┌────────────────────┐  ┌────────────────────┐
│ clean-events       │  │ suspicious-events  │
└────────────────────┘  └────────────────────┘
```

## Alternative Architectures (Why They Don't Work Well)

### Alternative 1: Separate Scorer Service

**Setup**:
```
Consumer → enriched-events topic → Scorer → clean/suspicious topics
```

**Problems**:
- ✅ Consumer still needs Redis (for features)
- ❌ Extra network hop (higher latency)
- ❌ Extra Kafka topic (more complexity)
- ❌ Consumer and Scorer both need to be scaled
- ❌ Harder to debug (event flows through 2 services)

**When to use**:
- If you need different models for different event types
- If scoring is very CPU-intensive and needs separate scaling
- If you want to score same events with multiple models

**Verdict**: Overkill for this use case ❌

### Alternative 2: Pre-Calculate Features in Producer

**Setup**:
```
Producer (with Redis) → events with features → Consumer (model only)
```

**Problems**:
- ❌ Producer becomes stateful (harder to scale)
- ❌ Features calculated at produce time (too early)
- ❌ If consumer lags, features are stale
- ❌ Consumer still needs Redis (for banning users)
- ❌ Producer shouldn't know about ML features (separation of concerns)

**When to use**:
- If features don't depend on consume-time state
- If producer naturally has the data needed

**Verdict**: Wrong design for real-time features ❌

### Alternative 3: Stateless Consumer (No Redis)

**Setup**:
```
Consumer (model only) → can't calculate features or ban users
```

**Problems**:
- ❌ Can't calculate session velocity (need user history)
- ❌ Can't ban users (need persistent state)
- ❌ Would need to move these responsibilities elsewhere

**When to use**:
- If all features are in the event already
- If no state management needed

**Verdict**: Not possible for this use case ❌

## Why Current Design is Optimal ✅

### 1. Single Responsibility
The consumer has **one** responsibility: **process events in real-time**

This includes:
- Calculate real-time features (needs Redis)
- Predict anomalies (needs Model)
- Route events (needs both)
- Manage user bans (needs Redis)

All of these are part of the **same logical operation**.

### 2. Low Latency
```
Event → Consumer → Decision
  ↓       (one hop)
Routed in ~10ms
```

No extra services, no extra network hops.

### 3. Easy to Reason About
```python
# One place to understand the entire flow
def process_event(event):
    1. Check ban
    2. Calculate feature
    3. Predict
    4. Route + ban if needed
```

### 4. Easy to Scale
Scale consumer independently:
```bash
docker compose up -d --scale gatekeeper-consumer=3
```

All consumers share:
- Redis state (coordinated)
- Kafka partitions (distributed)
- Model (replicated in memory)

### 5. Proper Separation from API
```
API:      HTTP interface, testing, health checks
Consumer: Real-time stream processing
```

Clear separation of concerns at the **service boundary**, not within the consumer.

## What If We Need to Change?

### Scenario 1: Different Models for Different Events

**Then** split into:
```
consumer → enriched-events → scorer-A → clean/suspicious
                           → scorer-B → clean/suspicious
```

But keep consumer with Redis (for features).

### Scenario 2: Complex Feature Engineering

**Then** add a feature service:
```
consumer → feature-service (with Redis) → enriched-events → scorer
```

But this is premature optimization.

### Scenario 3: Consumer Becomes Too Heavy

**Then** profile first! Check:
- Is model inference the bottleneck? → Scale consumers
- Is Redis I/O the bottleneck? → Optimize Redis calls
- Is Kafka consuming slow? → Increase partitions

Usually, scaling consumers is enough.

## The Model Loading Decision

### Why Load Model in Consumer?

```python
# In consumer.py:73
load_model_from_registry()
```

**Pros**:
- ✅ Consumer has model in memory (fast inference)
- ✅ No network call per prediction
- ✅ Works even if MLflow goes down

**Cons**:
- ⚠️ Memory overhead (~100MB per consumer instance)
- ⚠️ Need to restart consumers to update model

### Alternative: Model Serving Endpoint

```python
# Call external model service
response = requests.post("http://model-server/predict", json={"features": X})
prediction = response.json()["prediction"]
```

**Pros**:
- ✅ Update model without restarting consumers
- ✅ Centralized model management
- ✅ Lower memory per consumer

**Cons**:
- ❌ Network latency per prediction (~5-10ms)
- ❌ Extra failure point
- ❌ Need another service (model-server)
- ❌ Higher total cost (need to run model-server)

**When to use model serving**:
- Large models (>1GB) that can't fit in consumer memory
- Frequent model updates (daily/hourly)
- GPU-based models (centralize expensive GPUs)
- Multiple services need same model

**For our case** (small sklearn model, ~100MB):
- ✅ Loading in consumer is better
- Inference is fast (~1ms)
- Model updates are infrequent (weekly/monthly)

## Conclusion

**The consumer needs both Model and Redis because**:

1. **Model** → Required to predict anomalies
2. **Redis** → Required to calculate features AND ban users

This is:
- ✅ The right design for real-time anomaly detection
- ✅ Simple and easy to understand
- ✅ Low latency
- ✅ Easy to scale
- ✅ Industry standard pattern

**Alternative architectures** would add complexity without benefits for this use case.

## Summary Table

| Component | Why Consumer Needs It | Alternative | Why Not? |
|-----------|----------------------|-------------|----------|
| **Model** | Predict anomalies | Model serving endpoint | Extra latency, complexity |
| **Redis (features)** | Calculate session velocity | Pre-calculate in producer | Wrong timing, stale features |
| **Redis (bans)** | Block suspicious users | Separate ban service | Extra complexity, latency |

The current design is **optimal** for this use case. Don't overthink it! 🎯
