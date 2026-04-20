from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class NewsletterSubscriber(BaseModel):
    id: Optional[UUID] = None
    first_name: str
    email: EmailStr
    postcode: Optional[str] = Field(None, min_length=2, max_length=4)
    subscribed_at: Optional[datetime] = None
    email_verified: bool = False


class EmailVerificationRequest(BaseModel):
    email: str


class EmailVerificationResponse(BaseModel):
    message: str
