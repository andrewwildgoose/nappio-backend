import logging
from datetime import datetime, timedelta
from typing import Optional

import stripe
from supabase import Client
from gotrue import User
from pydantic import BaseModel

from ios.io_db import insert_checkout_session, UserAddress

logger = logging.getLogger('uvicorn.error')

class CheckoutSessionRequest(BaseModel):
    priceId: str
    addressId: str
    cancelUrl: Optional[str] = '/'
    # userId: str

class CheckoutSessionResponse(BaseModel):
    checkout_url: str
    session_id: str
    metadata: Optional[dict] = None

class CreateSubscriptionRequest(BaseModel):
    babyBirthdate: str  # Will receive as YYYY-MM-DD string
    babyWeight: float  # Changed from Decimal since we're receiving a float
    wantNappyWraps: bool
    address: dict  # Changed from UserAddress since we're receiving a plain dict
    cancelUrl: Optional[str] = '/'
    metadata: Optional[dict] = None  # Optional metadata to pass to the payment provider

class PaymentDetailsRequest(BaseModel):
    session_id: str

class PaymentDetailsResponse(BaseModel):
    amount_total: int
    customer_email: str

# Calculate the next Tuesday for billing_cycle_anchor
def next_tuesday():
    today = datetime.now()
    days_until_tuesday = (1 - today.weekday()) % 7  # Tuesday is 1 in Python's weekday()
    
    # If it's Tuesday (days_until = 0) or days until Tuesday is 1 or 2
    # add a week to get the following Tuesday
    if days_until_tuesday < 3:  # This covers 0 (Tuesday), 1 (Monday), 2 (Sunday)
        days_until_tuesday += 7
        
    next_tues = today + timedelta(days=days_until_tuesday)
    return int(next_tues.timestamp())

def get_or_create_customer(email: str) -> stripe.Customer:
    """
    Check if a customer exists in Stripe by email, and either:
    - Return the existing customer if found
    - Create a new customer if not found

    Args:
        email: Customer's email address

    Returns:
        Stripe Customer object
    """
    # Search for customers with matching email
    customers = stripe.Customer.list(email=email, limit=1)

    # If customer exists, return the first match
    if customers and len(customers.data) > 0:
        existing_customer = customers.data[0]
        print(f"Found existing customer: {existing_customer.id}")

        return existing_customer

    # No customer found, create a new one
    new_customer = stripe.Customer.create(
        email=email
    )
    print(f"Created new customer: {new_customer.id}")
    return new_customer

def create_stripe_checkout_session(
        supabase: Client, 
        line_items: list[dict],
        user: User,
        frontend_url: str,
        cancel_url: str,
        metadata: Optional[dict] = None
    ) -> CheckoutSessionResponse:
    """
    Creates a Stripe one-off payment checkout session.

    Args:
        supabase: Supabase client instance
        line_items: List of line items to include in the checkout session
        user: Authenticated user object
        frontend_url: URL of the frontend application
        cancel_url: URL to redirect to if the user cancels the checkout
        metadata: Optional metadata to include in the checkout session

    Returns:
        CheckoutSessionResponse containing the checkout URL, session ID and metadata
    """
    try:
        logger.info(f"create_stripe_checkout_session(): Creating checkout session for user {user.id} with line items {line_items}")

        stripe_customer = get_or_create_customer(email=user.email)


        # Create Stripe checkout session
        session = stripe.checkout.Session.create(
            customer=stripe_customer.id,
            line_items=line_items,
            mode="payment",
            success_url=f"{frontend_url}/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{frontend_url}{cancel_url}",
            metadata=metadata,
            saved_payment_method_options={
                "payment_method_save": "enabled"
            }
        )

        logger.info(f"create_stripe_checkout_session_with_line_items(): Checkout session created with ID {session.id}")

        # Store session in supabase
        inserted_session = insert_checkout_session(
            supabase=supabase,
            session_id=session.id,
            user_id=user.id,
            customer_id=session.customer,
            line_items=line_items,
            metadata=metadata
        )

        logger.info(f"create_stripe_checkout_session(): Checkout session stored in Supabase for user {user.id} with session ID {session.id}")
        
        # Return session URL and ID
        return {
            "checkout_url": session.url,
            "session_id": session.id,
            "metadata": metadata
        }
        
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error creating checkout session: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Error creating checkout session: {str(e)}")
        raise

def create_stripe_subscription_checkout_session(
        supabase: Client, 
        line_items: list[dict],
        user: User,
        frontend_url: str,
        cancel_url: str,
        metadata: Optional[dict] = None
    ) -> CheckoutSessionResponse:

    try:
        logger.info(f"create_stripe_checkout_session_with_line_items(): Creating subscription checkout session for user {user.id} with line items {line_items}")

        stripe_customer = get_or_create_customer(email=user.email)

        # Create Stripe checkout session
        session = stripe.checkout.Session.create(
            customer=stripe_customer.id,
            line_items=line_items,
            mode="subscription",
            subscription_data={
                'billing_anchor': next_tuesday(),
                'metadata': metadata or {}
            },
            success_url=f"{frontend_url}/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{frontend_url}{cancel_url}",
            metadata=metadata
        )

        logger.info(f"create_stripe_checkout_session_with_line_items(): Checkout session created with ID {session.id}")

        # Store session info in Supabase
        insert_checkout_session(
            supabase=supabase,
            session_id=session.id,
            user_id=user.id,
            customer_id=session.customer,
            line_items=line_items,
        )

        logger.info(f"create_stripe_checkout_session_with_line_items(): Checkout session stored in Supabase for user {user.id} with session ID {session.id}\nSession URL: {session.url}")

        # Return session URL and ID
        return CheckoutSessionResponse(
            checkout_url=session.url,
            session_id=session.id
        )

    except stripe.error.StripeError as e:
        logger.error(f"Stripe error creating checkout session: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Error creating checkout session: {str(e)}")
        raise

def get_payment_completed_details(session_id: str) -> PaymentDetailsResponse:
    """
    Fetch payment details from a completed checkout session

    Args:
        session_id: Stripe checkout session ID
        
    Returns:
        PaymentDetailsResponse with items and customer details
    """
    try:
        logger.info(f"get_payment_details(): Fetching payment details for session ID {session_id}")

        # Retrieve the session and subscription details
        session = stripe.checkout.Session.retrieve(session_id)
        amount_total = session['amount_total']

        # access      
        logger.info(f"get_subscription_details(): Subscription details fetched for session ID {session_id}")
        
        return PaymentDetailsResponse(
            amount_total=amount_total,
            customer_email=session.customer_details.email
        )
        
    except Exception as e:
        logger.error(f"Error fetching subscription details: {str(e)}")
        raise