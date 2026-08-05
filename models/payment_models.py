from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, model_validator


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

class CheckoutSessionRequest(BaseModel):
    priceId: str
    addressId: str
    cancelUrl: Optional[str] = '/'
    # userId: str

class CheckoutSessionResponse(BaseModel):
    checkout_url: str
    session_id: str
    metadata: Optional[dict] = None


class VoucherVerificationRequest(BaseModel):
    voucher_code: str
    postcode: str


class VoucherVerificationResult(BaseModel):
    eligible: bool
    message: str
    code: Optional[str] = None
    discount_code: Optional[str] = None
    voucher_type: Optional[str] = None
    failure_reason: Optional[
        Literal['not_found', 'already_used', 'postcode_mismatch', 'unavailable', 'service_error']
    ] = None


class AppliedVoucher(BaseModel):
    code: str
    postcode: str
    discount_code: str
    voucher_type: str = 'RNFL'

class CreateSubscriptionRequest(BaseModel):
    babyBirthdate: str  # Will receive as YYYY-MM-DD string
    babyWeight: float  # Changed from Decimal since we're receiving a float
    # Removed Nappy Wraps selection - leaving in as may reintroduce later
    #wantNappyWraps: bool
    serviceLevel: str  # e.g., 'full-time', 'part-time'
    address: Optional[dict] = None  # Address dict for new address
    addressId: Optional[str] = None  # ID for existing address
    cancelUrl: Optional[str] = '/'
    metadata: Optional[dict] = None  # Optional metadata to pass to the payment provider
    voucher: Optional[AppliedVoucher] = None

    @model_validator(mode='after')
    def check_address_or_address_id(self):
        """Ensure either address or addressId is provided, but not both."""
        if self.address is None and self.addressId is None:
            raise ValueError('Either address or addressId must be provided')
        if self.address is not None and self.addressId is not None:
            raise ValueError('Cannot provide both address and addressId')
        return self

class PaymentDetailsRequest(BaseModel):
    session_id: str

class PaymentDetailsResponse(BaseModel):
    amount_total: int
    customer_email: str
    checkout_type: str

class PauseSubscriptionRequest(BaseModel):
    subscription_id: str
    pause_until: Optional[str] = None  # If None, pause indefinitely

class PauseSubscriptionResponse(BaseModel):
    message: str
