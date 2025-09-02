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

def get_stripe_price_ids(supabase: Client, product_ids: list[str]) -> list[str]:
    """
    Retrieve Stripe price IDs from the database that match the given product IDs.
    """
    try:
        stripe_price_ids_dict = supabase.table('product').select('stripe_price_id').in_("id", product_ids).execute()
        stripe_price_ids = [item['stripe_price_id'] for item in stripe_price_ids_dict.data if item.get('stripe_price_id')]
        logger.debug(f"get_stripe_price_ids(): Retrieved price IDs: {stripe_price_ids}")
        return stripe_price_ids
    except Exception as e:
        logger.error(f"get_stripe_price_ids(): Error retrieving price IDs: {str(e)}")
        raise Exception(f"Error retrieving price IDs: {str(e)}")

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
        line_items: list[dict],
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
            "line_items": line_items,
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
    status: str,
    metadata: Optional[dict] = None
) -> dict:
    """Update an existing checkout session"""
    try:
        logger.debug(f"update_checkout_session(): Updating session with ID {session_id} to status {status}")

        # Prepare data to update
        response = supabase.table('checkout_sessions').update({
            "status": status,
            "metadata": metadata
        }).eq("session_id", session_id).execute()

        logger.debug(f"update_checkout_session(): Updated data: {response.data}")
        
        return response.data[0] if response.data else None
        
    except Exception as e:
        logger.error(f"update_checkout_session(): Failed to update checkout session: {str(e)}")
        raise

def insert_user_subscription(
    supabase: Client,
    customer_id: str,
    stripe_subscription_id: str,
    status: str,
    address_id: Optional[UUID] = None,
    baby_dob: Optional[datetime] = None,
    baby_weight_at_start: Optional[float] = None,
    subscribed_at: Optional[datetime] = None,
    last_payment_date: Optional[datetime] = None,
    next_payment_date: Optional[datetime] = None,
) -> dict:
    """
    Insert a new user subscription into the database
    
    Args:
        supabase: Supabase client instance
        customer_id: Stripe customer ID
        stripe_subscription_id: Stripe subscription ID
        status: Subscription status ('pending', 'active', or 'cancelled')
        address_id: UUID of the delivery address (optional)
        baby_dob: Baby's date of birth (optional)
        baby_weight_at_start: Baby's weight when starting subscription (optional)
        subscribed_at: Subscription start timestamp (optional, defaults to now)
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
        
        # Prepare data to insert
        subscription_data = {
            "user_id": user_id,
            "customer_id": customer_id,
            "stripe_subscription_id": stripe_subscription_id,
            "status": status,
            "subscribed_at": subscribed_at.isoformat() if subscribed_at else None,
            "last_payment_date": last_payment_date.isoformat() if last_payment_date else None,
            "next_payment_date": next_payment_date.isoformat() if next_payment_date else None,
            "cancelled_at": None
        }

        # Add optional fields if they are provided
        if address_id:
            subscription_data["address_id"] = str(address_id)  # Convert UUID to string
        if baby_dob:
            subscription_data["baby_dob"] = baby_dob.isoformat()
        if baby_weight_at_start is not None:  # Check is not None because 0.0 is valid
            subscription_data["baby_weight_at_start"] = baby_weight_at_start
        
        response = supabase.table('user_subscriptions').insert(subscription_data).execute()
        
        logger.debug(f"insert_user_subscription(): Inserted data: {response.data}")

        return response.data[0] if response.data else None
        
    except Exception as e:
        logger.error(f"insert_user_subscription(): Failed to store subscription: {str(e)}")
        raise

def insert_subscription_items(
        supabase: Client,
        subscription_items: list[dict]):
    """
    Insert subscription items into the database

    Args:
        supabase: Supabase client instance
        subscription_items: List of subscription item dictionaries to insert
    Returns:
        bool: True if insertion was successful, False otherwise
    Raises:
        Exception: If database insertion fails
    """
    try:
        for item in subscription_items:
            subscription_item = {
                "subscription_id": item["subscription_id"],
                "product_id": item["product_id"],
                "quantity": item["quantity"]
            }
            logger.debug(f"insert_subscription_items(): Inserting subscription item: {subscription_item}")
            response = supabase.table('subscription_items').insert(subscription_item).execute()
            logger.debug(f"insert_subscription_items(): Inserted data: {response.data}")

        return True

    except Exception as e:
        logger.error(f"insert_subscription_items(): Failed to store subscription items: {str(e)}")
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
        ).eq("stripe_subscription_id", subscription_id).execute()

        logger.debug(f"update_user_subscription(): Updated data: {response.data}")
        
        return response.data[0] if response.data else None
        
    except Exception as e:
        logger.error(f"update_user_subscription(): Failed to update subscription: {str(e)}")
        raise

def get_user_subscriptions(supabase, user_id):
    """
    Retrieve all subscriptions for a given user ID
    """
    try:
        logger.debug(f"get_user_subscriptions(): Retrieving subscriptions for user ID {user_id}")
        
        response = supabase.table('user_subscriptions').select('*').eq('user_id', user_id).execute()
        
        if response.data:
            logger.info(f"get_user_subscriptions(): Found {len(response.data)} subscriptions for user ID {user_id}")
        else:
            logger.warning(f"get_user_subscriptions(): No subscriptions found for user ID {user_id}")
        
        return response.data if response.data else []
    except Exception as e:
        logger.error(f"get_user_subscriptions(): Error retrieving subscriptions for user ID {user_id}: {str(e)}")
        raise Exception(f"Error retrieving subscriptions for user ID {user_id}: {str(e)}")

def insert_user_address(
        supabase: Client,
        new_address: UserAddress
) -> Optional[UserAddress]:

    """
    Insert a new user address into the database
    """
    try:
        response = supabase.table('user_addresses').insert({
            "user_id": new_address.user_id,
            "address_line_1": new_address.address_line_1,
            "address_line_2": new_address.address_line_2,
            "city": new_address.city,
            "postcode": new_address.postcode,
            "country": new_address.country,
            "address_notes": new_address.address_notes
        }).execute()

        logger.debug(f"insert_user_address(): Inserted data: {response}")

        return response.data[0] if response.data else None

    except Exception as e:
        logger.error(f"insert_user_address(): Failed to insert address: {str(e)}")
        raise

def get_user_addresses(supabase: Client, user_id: UUID) -> Optional[UserAddress]:
    """
    Retrieve all addresses for a given user ID
    """
    try:
        response = supabase.table('user_addresses').select('*').eq('user_id', user_id).execute()
        logger.debug(f"get_user_addresses(): Retrieved addresses for user {user_id}: {response.data}")

        return [UserAddress(**addr) for addr in response.data] if response.data else []
    except Exception as e:
        logger.error(f"get_user_addresses(): Error fetching addresses for user {user_id}: {str(e)}")
        raise

def delete_user_address(supabase: Client, address_id: UUID) -> bool:
    """
    Delete a user address by its ID
    """
    try:
        response = supabase.table('user_addresses').delete().eq('id', address_id).execute()
        logger.debug(f"delete_user_address(): Deleted address with ID {address_id}: {response.data}")

        return response.data is not None and len(response.data) > 0
    except Exception as e:
        logger.error(f"delete_user_address(): Error deleting address with ID {address_id}: {str(e)}")
        raise