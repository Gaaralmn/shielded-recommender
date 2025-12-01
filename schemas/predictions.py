from pydantic import BaseModel
from .events import ClickEvent

class PredictionRequest(ClickEvent):
    pass

class PredictionResponse(BaseModel):
    is_anomaly: bool
