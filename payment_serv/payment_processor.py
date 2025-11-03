import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import stripe
from supabase import Client
from gotrue import User
from pydantic import BaseModel, model_validator

from email_serv import email_processor
from ios import io_db

# Get Supabase client from config
from config.supabase import get_supabase

logger = logging.getLogger('uvicorn.error')

# Initialize Supabase client
supabase = get_supabase()

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
    address: Optional[dict] = None  # Address dict for new address
    addressId: Optional[str] = None  # ID for existing address
    cancelUrl: Optional[str] = '/'
    metadata: Optional[dict] = None  # Optional metadata to pass to the payment provider

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
        inserted_session = io_db.insert_checkout_session(
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
        line_items: list[dict],
        user: User,
        frontend_url: str,
        cancel_url: str,
        billing_anchor: datetime,
        metadata: Optional[dict] = None
    ) -> CheckoutSessionResponse:

    try:
        logger.info(f"create_stripe_checkout_session_with_line_items(): Creating subscription checkout session for user {user.id} with line items {line_items}")

        stripe_customer = get_or_create_customer(email=user.email)

        logger.debug(f"Billing cycle anchor datetime: {billing_anchor}")
        logger.debug(f"Billing cycle anchor timezone: {billing_anchor.tzinfo}")
        logger.debug(f"Billing cycle anchor timestamp (float): {billing_anchor.timestamp()}")
        logger.debug(f"Billing cycle anchor timestamp (int): {int(billing_anchor.timestamp())}") 
        # Ensure billing_anchor is in UTC
        if billing_anchor.tzinfo is None:
            # If timezone-naive, assume it's UTC
            billing_anchor = billing_anchor.replace(tzinfo=timezone.utc)
        else:
            # Convert to UTC if it has a different timezone
            billing_anchor = billing_anchor.astimezone(timezone.utc)
        
        subscription_start_timestamp: int = int(billing_anchor.timestamp())
        logger.debug(f"UTC Billing cycle anchor timestamp: {subscription_start_timestamp}")
        
        # Check if billing_anchor is more than 2 days away
        current_time = datetime.now(timezone.utc)
        five_days_from_now = current_time + timedelta(days=5)
        
        if billing_anchor > five_days_from_now:
            subscription_data = {
                'trial_end': subscription_start_timestamp,
                'metadata': metadata or {}
            }
        else:
            subscription_data = {
                'billing_cycle_anchor': subscription_start_timestamp,
                'proration_behavior': 'none',
                'metadata': metadata or {}
            }

        # Create Stripe checkout session
        session = stripe.checkout.Session.create(
            customer=stripe_customer.id,
            line_items=line_items,
            mode="subscription",
            subscription_data=subscription_data,
            success_url=f"{frontend_url}/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{frontend_url}{cancel_url}",
            metadata=metadata
        )

        logger.info(f"create_stripe_checkout_session_with_line_items(): Checkout session created with ID {session.id}")

        # Store session info in Supabase
        io_db.insert_checkout_session(
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

def paid_processing(checkout_type: str, subscription_id: str, event_data: dict) -> None:
    """
    Placeholder function for processing after a payment is made.
    This could include updating user status, sending confirmation emails, etc.
    """
    try:
        logger.info(f"Processing payment for checkout type: {checkout_type}")
        match checkout_type:
            case "start_up":
                startup_costs_paid_processing(subscription_id, event_data)
            case "subscription":
                subscription_paid_processing(subscription_id, event_data)
            case _:
                logger.warning(f"Unknown checkout type: {checkout_type}")
                raise ValueError(f"Unknown checkout type: {checkout_type}")           
    except Exception as e:
        logger.error(f"paid_processing(): Error processing payment for checkout type {checkout_type}: {str(e)}")
        raise

def startup_costs_paid_processing(subscription_id: str, event_data: dict):
    """
    Placeholder function for processing after startup costs are paid.
    This could include updating user status, sending confirmation emails, etc.
    """
    try:
        logger.info("Processing startup costs payment")
        # Update STATUS & CUSTOMER_ID in user_subscriptions table in supabase
        subscription = io_db.update_user_subscription(
            subscription_id=subscription_id,
            customer_id=event_data['object']['customer'],
            )

        # Update subscription progress status to setup paid
        io_db.update_subscription_progress_admin(
            subscription_id=subscription_id, 
            status="setup_paid"
            )
        
        # Send confirmation email to user
        subscription_items_response = supabase.table('subscription_items')\
            .select('*')\
            .eq('subscription_id', subscription_id)\
            .execute()
        
        logger.debug(f"Subscription items: {subscription_items_response.data}")
        
        # Get product details for each subscription item
        product_details = []
        for item in subscription_items_response.data:
            product_response = supabase.table('product')\
                .select('*')\
                .eq('id', item['product_id'])\
                .execute()
                
            if product_response.data:
                product = product_response.data[0]
                product_details.append({
                    "subscription_id": subscription_id,
                    "item_name": product['name'],
                    "cost": f'{product['currency'].upper()} {product['price'] / 100:.2f}',
                    "quantity": item['quantity'],
                    "type": product['type']
                })
        
        logger.debug(f"Products in subscription: {product_details}")

        # get user email and first name
        customer_email = event_data['object']['customer_details']['email']
        customer_name = event_data['object']['customer_details']['name']
        
        
        #TODO: Need to make these conditional on the right kind of checkout session
        # ONLY FOR STARTUP COSTS
        # send confirmation email to customer
        email_processor.send_new_subscription_email(customer_email, customer_name, product_details)
        
        # Send confirmation to team
        team_email_subject = f"New Subscription: {customer_email}"
        
        # ONLY FOR STARTUP COSTS

        # Get customer address
        subscription_address_res = io_db.get_subscription_address(subscription_id)
        # send confirmation email to team
        email_processor.send_order_email_to_team(
            subject=team_email_subject,
            customer_email=customer_email,
            customer_name=customer_name,
            customer_address=subscription_address_res,
            items=product_details
        )
        # Send notification email to team

    except Exception as e:
        logger.error(f"startup_costs_paid_processing(): Error processing startup costs payment: {str(e)}")
        raise

def subscription_paid_processing(subscription_id: str, event_data: dict):
    """
    Placeholder function for processing after a subscription payment is made.
    This could include updating subscription status, sending confirmation emails, etc.
    """

    try:   
        # get user email and first name
        customer_email = event_data['object']['customer_details']['email']
        customer_name = event_data['object']['customer_details']['name']

        # Get subscription items
        subscription_items_response = supabase.table('subscription_items')\
            .select('*')\
            .eq('subscription_id', subscription_id)\
            .execute()
        
        logger.debug(f"Subscription items: {subscription_items_response.data}")
        
        # Get product details for each subscription item
        product_details = []
        for item in subscription_items_response.data:
            product_response = supabase.table('product')\
                .select('*')\
                .eq('id', item['product_id'])\
                .execute()
                
            if product_response.data:
                product = product_response.data[0]
                product_details.append({
                    "subscription_id": subscription_id,
                    "item_name": product['name'],
                    "cost": f'{product['currency'].upper()} {product['price'] / 100:.2f}',
                    "quantity": item['quantity'],
                    "type": product['type']
                })
        
        logger.debug(f"Products in subscription: {product_details}")
        # Send confirmation email to user
        email_processor.send_subscription_payment_active_email(
            to_email=customer_email,
            first_name=customer_name,
            subscription_items=product_details
        )

        # Send notification email to team
        logger.info("Sending notification email to team")
        email_processor.send_subscription_payment_active_to_team(
            customer_email=customer_email,
            customer_name=customer_name,
            items=product_details
        )
    except Exception as e:
        logger.error(f"Error sending notification email to team: {str(e)}")
        raise
