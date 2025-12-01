from pydantic import BaseModel
from datetime import datetime

class ClickEvent(BaseModel):
    user_id: str
    item_id: str
    timestamp: datetime
