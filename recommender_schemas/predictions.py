from pydantic import BaseModel
from recommender_schemas.events import ClickEvent

class PredictionRequest(ClickEvent):
    pass

class PredictionResponse(BaseModel):
    is_anomaly: bool
