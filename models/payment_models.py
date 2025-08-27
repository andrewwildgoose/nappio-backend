from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class WebhookEvent(BaseModel):
    id: str
    type: str
    data: dict
    created: datetime

class SubscriptionWebhookData(BaseModel):
    user_id: str
    plan_id: str
    status: str
    subscribed_at: datetime
    cancelled_at: Optional[datetime] = None