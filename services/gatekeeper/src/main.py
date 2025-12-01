from fastapi import FastAPI

app = FastAPI(
    title="Gatekeeper Service",
    description="Detects bot traffic to prevent it from polluting recommendation data.",
    version="0.1.0",
)

@app.get("/")
def read_root():
    return {"message": "Gatekeeper service is running."}

@app.post("/predict")
def predict(data: dict):
    # Placeholder for anomaly detection logic
    return {"is_anomaly": False}
