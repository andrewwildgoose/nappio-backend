from datetime import datetime
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel

import ios.io_db as io_db


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
    user_id: Optional[str] = None  # Optional field for user ID if applicable
    customer_id: Optional[str] = None  # Optional field for customer ID if applicable
    status: str
    start_date: datetime
    end_date: Optional[datetime] = None
    stripe_subscription_id: Optional[str] = None
    next_payment_date: Optional[datetime] = None
    address_id: Optional[UUID] = None  # Optional field for address ID if applicable
    items: List[ProductDetails] = []  # List of products in the subscription

class UserAddressRequest(BaseModel):
    id: Optional[UUID] = None  # Optional UUID for existing address
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
    address: Optional[io_db.UserAddress] = None  # The newly created address object if successful

class DeleteAddressRequest(BaseModel):
    address_id: UUID  # UUID of the address to delete

class DeleteAddressResponse(BaseModel):
    success: bool
    message: str

class AssignSubscriptionAddressRequest(BaseModel):
    address_id: str
    subscription_id: str
