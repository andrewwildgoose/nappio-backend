from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel


class UserAddress(BaseModel):
    id: Optional[UUID] = None
    user_id: str
    address_line_1: str
    address_line_2: Optional[str] = None
    city: str
    postcode: str
    country: str
    address_notes: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ProductDetails(BaseModel):
    name: str
    price: float
    currency: str


class SubscriptionRequest(BaseModel):
    id: str
    cancelUrl: Optional[str] = '/'


#TODO: Update this to match the db schema
class SubscriptionDetailsResponse(BaseModel):
    id: UUID
    user_id: Optional[str] = None
    customer_id: Optional[str] = None
    status: str
    start_date: datetime
    end_date: Optional[datetime] = None
    stripe_subscription_id: Optional[str] = None
    next_payment_date: Optional[datetime] = None
    address_id: Optional[UUID] = None
    items: List[ProductDetails] = []


class UserAddressRequest(BaseModel):
    id: Optional[UUID] = None
    user_id: str
    address_line_1: str
    address_line_2: Optional[str] = None
    city: str
    postcode: str
    country: str
    address_notes: Optional[str] = None


class AddUserAddressRequest(BaseModel):
    address_line_1: str
    address_line_2: Optional[str] = None
    city: str
    postcode: str
    country: str
    address_notes: Optional[str] = None


class AddUserAddressResponse(BaseModel):
    success: bool
    message: str
    address: Optional[UserAddress] = None


class DeleteAddressRequest(BaseModel):
    address_id: UUID


class DeleteAddressResponse(BaseModel):
    success: bool
    message: str


class AssignSubscriptionAddressRequest(BaseModel):
    address_id: str
    subscription_id: str
