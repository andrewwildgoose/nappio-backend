import logging
from typing import Optional
from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
import pytz
from uuid import UUID
from supabase import Client

logger = logging.getLogger('uvicorn.error')
logger.setLevel(logging.DEBUG)

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

def insert_newsletter_subscriber(supabase, subscriber: NewsletterSubscriber) -> dict:
    """
    Insert a new newsletter subscriber into the database
    """
    try:
        data_to_insert = {
            "first_name": subscriber.first_name,
            "email": subscriber.email,
            "postcode": subscriber.postcode,
            "subscribed_at": datetime.now(pytz.UTC).isoformat(),
            "email_verified": subscriber.email_verified,
        }
        logger.debug(f"insert_newsletter_subscriber(): Data to insert: {data_to_insert}")
        
        response = supabase.table('newsletter_subscribers').insert(data_to_insert).execute()
        
        if response.data:
            logger.info(f"insert_newsletter_subscriber(): Inserted data: {response.data[0]}")
        else:
            logger.warning("insert_newsletter_subscriber(): No data returned from insert operation.")
        
        return response.data[0] if response.data else None
    except Exception as e:
        logger.error(f"insert_newsletter_subscriber(): Error inserting newsletter subscriber: {str(e)}")   
        raise Exception(f"Error inserting newsletter subscriber: {str(e)}")
    
def verify_newsletter_subscriber(supabase, verify_request: EmailVerificationRequest) -> bool:
    """
    Verify a subscriber's email address
    """
    try:
        email = verify_request.email
        response = supabase.table('newsletter_subscribers').update({
            "email_verified": True
        }).eq("email", email).execute()
        
        if response.data:
            logger.info(f"verify_newsletter_subscriber(): Email {email} verified successfully.")
            return True
        else:
            logger.warning(f"verify_newsletter_subscriber(): No subscriber found with email {email}.")
            return False
    except Exception as e:
        logger.error(f"verify_newsletter_subscriber(): Error verifying email {email}: {str(e)}")
        raise Exception(f"Error verifying email {email}: {str(e)}")
    

def insert_checkout_session(
        supabase: Client, 
        session_id: str, 
        user_id: str,
        customer_id: str,
        price_id: str, 
        status: str = "pending"
) -> dict:
    """
    Insert a new checkout session into the database
    
    Args:
        supabase: Supabase client instance
        session_id: Stripe checkout session ID
        user_id: User ID from Supabase
        price_id: Stripe price ID
        status: Session status (default: "pending")
        
    Returns:
        dict: The inserted checkout session data
        
    Raises:
        Exception: If database insertion fails
    """
    try:
        logger.debug(f"insert_checkout_session(): Inserting session with ID {session_id} for user {user_id}")

        # Prepare data to insert
        response = supabase.table('checkout_sessions').insert({
            "session_id": session_id,
            "user_id": user_id,
            "customer_id": customer_id,
            "price_id": price_id,
            "status": status
        }).execute()
        
        logger.debug(f"insert_checkout_session(): Inserted data: {response.data}")

        return response.data[0] if response.data else None
        
    except Exception as e:
        logger.error(f"insert_checkout_session(): Failed to store checkout session: {str(e)}")
        raise

def update_checkout_session(
    supabase: Client,
    session_id: str,
    status: str
) -> dict:
    """Update an existing checkout session"""
    try:
        logger.debug(f"update_checkout_session(): Updating session with ID {session_id} to status {status}")

        # Prepare data to update
        response = supabase.table('checkout_sessions').update({
            "status": status
        }).eq("session_id", session_id).execute()

        logger.debug(f"update_checkout_session(): Updated data: {response.data}")
        
        return response.data[0] if response.data else None
        
    except Exception as e:
        logger.error(f"update_checkout_session(): Failed to update checkout session: {str(e)}")
        raise

def insert_user_subscription(
    supabase: Client,
    plan_id: str,
    price_id: str,
    customer_id: str,
    subscription_id: str,
    status: str,
    subscribed_at: datetime,
    last_payment_date: Optional[datetime] = None,
    next_payment_date: Optional[datetime] = None,
) -> dict:
    """
    Insert a new user subscription into the database
    
    Args:
        supabase: Supabase client instance
        user_id: User ID from Supabase auth
        plan_id: Subscription plan ID
        status: Subscription status
        subscribed_at: Subscription start timestamp
        last_payment_date: Last payment date (optional)
        next_payment_date: Next payment date (optional)        
    Returns:
        dict: The inserted subscription data
        
    Raises:
        Exception: If database insertion fails
    """
    try:
        

        # Get the supabase user from the checkout session
        user_id_response = supabase.table('checkout_sessions').select('user_id').eq('customer_id', customer_id).execute()
        
        if not user_id_response.data:
            raise Exception("User ID not found in checkout session")
        user_id = user_id_response.data[0]['user_id']

        logger.debug(f"insert_user_subscription(): Retrieved user ID {user_id} from checkout session for customer {customer_id}")
        
        logger.debug(f"insert_user_subscription(): Inserting subscription for user {user_id} with plan {plan_id}")
        
        # Prepare data to insert
        response = supabase.table('user_subscriptions').insert({
            "user_id": user_id,
            "plan_id": plan_id,
            "price_id": price_id,
            "customer_id": customer_id,
            "subscription_id": subscription_id,
            "status": status,
            "subscribed_at": subscribed_at.isoformat(),
            #TODO: DATES NOT POPULATING
            "last_payment_date": last_payment_date.isoformat() if last_payment_date else None,
            #TODO: DATES NOT POPULATING
            "next_payment_date": next_payment_date.isoformat() if next_payment_date else None,
            "cancelled_at": None
        }).execute()
        
        logger.debug(f"insert_user_subscription(): Inserted data: {response.data}")

        return response.data[0] if response.data else None
        
    except Exception as e:
        logger.error(f"insert_user_subscription(): Failed to store subscription: {str(e)}")
        raise

def update_user_subscription(
    supabase: Client,
    subscription_id: str,
    status: str,
    last_payment_date: Optional[datetime] = None,
    next_payment_date: Optional[datetime] = None,
    cancelled_at: Optional[datetime] = None
) -> dict:
    """Update an existing user subscription"""
    try:
        logger.debug(f"update_user_subscription(): Updating subscription for to status {status}")

        # Prepare data to update
        data = {"status": status}

        # Only include optional fields if they are provided
        if cancelled_at:
            data["cancelled_at"] = cancelled_at.isoformat()
        if last_payment_date:
            data["last_payment_date"] = last_payment_date.isoformat()
        if next_payment_date:
            data["next_payment_date"] = next_payment_date.isoformat()
        
        # Update the subscription in the database
        response = supabase.table('user_subscriptions').update(
            data
        ).eq("subscription_id", subscription_id).execute()

        logger.debug(f"update_user_subscription(): Updated data: {response.data}")
        
        return response.data[0] if response.data else None
        
    except Exception as e:
        logger.error(f"update_user_subscription(): Failed to update subscription: {str(e)}")
        raise