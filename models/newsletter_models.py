import re
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator

# UK postcode outward code (first half), e.g. SW2, M1, EC1A, B33
UK_OUTWARD_CODE_RE = re.compile(r"^[A-Z]{1,2}[0-9][A-Z0-9]?$")

# Patterns commonly seen in spam submissions
SPAM_NAME_RE = re.compile(r"https?://|www\.|<|>", re.IGNORECASE)


class NewsletterSubscriber(BaseModel):
    id: Optional[UUID] = None
    first_name: str = Field(..., min_length=1, max_length=50)
    email: EmailStr
    postcode: Optional[str] = Field(None, min_length=2, max_length=4)
    subscribed_at: Optional[datetime] = None
    email_verified: bool = False

    @field_validator("first_name", mode="before")
    @classmethod
    def validate_first_name(cls, value):
        if isinstance(value, str):
            value = value.strip()
            if SPAM_NAME_RE.search(value):
                raise ValueError("Please enter a valid first name")
        return value

    @field_validator("postcode", mode="before")
    @classmethod
    def validate_postcode(cls, value):
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError("Please enter a valid UK postcode area, e.g. SW2")
        value = value.strip().upper()
        if not value:
            return None
        if not UK_OUTWARD_CODE_RE.match(value):
            raise ValueError("Please enter a valid UK postcode area, e.g. SW2")
        return value


class EmailVerificationRequest(BaseModel):
    email: str


class EmailVerificationResponse(BaseModel):
    message: str
