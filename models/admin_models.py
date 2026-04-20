from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class SubscriptionDashboardResponse(BaseModel):
    subscription_id: str
    user_id: str
    customer_name: str
    customer_email: str
    subscription_status: str
    progress_status: str
    meeting_date: Optional[datetime] = None
    subscribed_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    last_payment_date: Optional[datetime] = None
    next_payment_date: Optional[datetime] = None
    baby_dob: Optional[datetime] = None
    baby_weight_at_start: Optional[float] = None
    last_updated: Optional[datetime] = None

class SubscriptionProgressUpdate(BaseModel):
    subscription_id: str
    status: Optional[str] = None
    meeting_date: Optional[datetime] = None