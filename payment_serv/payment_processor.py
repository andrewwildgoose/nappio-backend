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

class CreateSubscriptionRequest(BaseModel):
    babyBirthdate: str  # Will receive as YYYY-MM-DD string
    babyWeight: float  # Changed from Decimal since we're receiving a float
    wantNappyWraps: bool
    address: dict  # Changed from UserAddress since we're receiving a plain dict
    cancelUrl: Optional[str] = '/'

class SubscriptionDetailsRequest(BaseModel):
    session_id: str

class SubscriptionSimpleResponse(BaseModel):
    plan_name: str
    customer_email: str

class SubscriptionDetailsResponse(BaseModel):
    plan_name: str
    customer_email: str
    subscription_id: str
    status: str
    start_date: datetime
    end_date: Optional[datetime] = None

# Calculate the next Tuesday for billing_cycle_anchor
def next_tuesday():
    today = datetime.now()
    days_until_tuesday = (1 - today.weekday()) % 7  # Tuesday is 1 in Python's weekday()
    if days_until_tuesday == 0:  # If today is Tuesday, get next Tuesday
        days_until_tuesday = 7
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
    request: CheckoutSessionRequest,
    user: User,
    frontend_url: str
) -> dict:
    """
    Creates a Stripe checkout session for subscription.
    """
    try:

        # Log the incoming price ID and strip any whitespace
        price_id = request.priceId.strip()
        logger.debug(f"Attempting to create checkout with price_id: '{price_id}'")
        
        # List all prices first to verify our API connection
        all_prices = stripe.Price.list(limit=5)
        logger.debug(f"Available prices: {[p.id for p in all_prices.data]}")

        # Try to retrieve the specific price
        try:
            price = stripe.Price.retrieve(price_id)
            logger.debug(f"Successfully retrieved price: {price.id}")
        except stripe.error.StripeError as e:
            logger.error(f"Failed to retrieve price '{price_id}': {str(e)}")
            raise

        logger.info(f"create_stripe_checkout_session(): Creating checkout session for user {user.id} with price ID {request.priceId}")
        # Create checkout session

        stripe_customer = stripe.Customer.create(
            email=user.email,
            metadata={"user_id": user.id}
        )
        
        session = stripe.checkout.Session.create(
            customer=stripe_customer.id,
            line_items=[{"price": request.priceId, "quantity": 1}],
            mode="subscription",
            success_url=f"{frontend_url}/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{frontend_url}{request.cancelUrl}",
            metadata={
                "user_id": user.id,
                "address_id": request.addressId,
            }
        )

        logger.info(f"create_stripe_checkout_session(): Checkout session created with ID {session.id}")
        
        # Store session info in Supabase
        insert_checkout_session(
            supabase=supabase,
            session_id=session.id,
            user_id=user.id,
            customer_id=session.customer,
            price_id=request.priceId
        )

        logger.info(f"create_stripe_checkout_session(): Checkout session stored in Supabase for user {user.id} with session ID {session.id}")
        
        # Return session URL and ID
        return {
            "checkout_url": session.url,
            "session_id": session.id
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
        address_id: str,
        frontend_url: str,
        cancel_url: str
    ) -> dict:

    try:
        logger.info(f"create_stripe_checkout_session_with_line_items(): Creating subscription checkout session for user {user.id} with line items {line_items}")

        stripe_customer = get_or_create_customer(email=user.email)

        # Create Stripe checkout session
        session = stripe.checkout.Session.create(
            customer=stripe_customer.id,
            line_items=line_items,
            mode="subscription",
            subscription_data={
                'billing_cycle_anchor': next_tuesday(),
            },
            success_url=f"{frontend_url}/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{frontend_url}{cancel_url}",
            metadata={
                "user_id": user.id,
                "address_id": address_id,
            }
        )

        logger.info(f"create_stripe_checkout_session_with_line_items(): Checkout session created with ID {session.id}")

        # Store session info in Supabase
        insert_checkout_session(
            supabase=supabase,
            session_id=session.id,
            user_id=user.id,
            customer_id=session.customer,
            line_items=line_items
        )

        logger.info(f"create_stripe_checkout_session_with_line_items(): Checkout session stored in Supabase for user {user.id} with session ID {session.id}\nSession URL: {session.url}")

        # Return session URL and ID
        return {
            "checkout_url": session.url,
            "session_id": session.id
        }

    except stripe.error.StripeError as e:
        logger.error(f"Stripe error creating checkout session: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Error creating checkout session: {str(e)}")
        raise

def get_subscription_details(session_id: str) -> SubscriptionSimpleResponse:
    """
    Fetch subscription details from a completed checkout session
    
    Args:
        session_id: Stripe checkout session ID
        
    Returns:
        SubscriptionSimpleResponse with plan and customer details
    """
    try:
        logger.info(f"get_subscription_details(): Fetching subscription details for session ID {session_id}")
        
        # Retrieve the session and subscription details
        session = stripe.checkout.Session.retrieve(session_id)
        subscription = stripe.Subscription.retrieve(session.subscription)

        # Access items directly
        subscription_items = subscription['items']

        logger.debug(f'Subscription items: {subscription_items}')

        if 'data' in subscription_items and subscription_items['data']:
            first_item = subscription_items['data'][0]
            if 'price' in first_item and 'id' in first_item['price']:
                price = stripe.Price.retrieve(first_item['price']['id'])
                product = stripe.Product.retrieve(price.product)
            else:
                logger.error("Price information not found in subscription item")
        else:
            logger.error("No subscription items found")

        
        logger.info(f"get_subscription_details(): Subscription details fetched for session ID {session_id}")
        
        return SubscriptionSimpleResponse(
            plan_name=product.name,
            customer_email=session.customer_details.email
        )
        
    except Exception as e:
        logger.error(f"Error fetching subscription details: {str(e)}")
        raise