
import logging
from typing import Optional
from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
import pytz
from uuid import UUID
from supabase import Client
import json

# Get Supabase client from config
from config.supabase import get_supabase

from models.admin_models import SubscriptionDashboardResponse

logger = logging.getLogger('uvicorn.error')
logger.setLevel(logging.DEBUG)

# Initialize Supabase client
supabase = get_supabase()


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

def get_stripe_price_ids(product_ids: list[str]) -> list[str]:
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

def insert_newsletter_subscriber(subscriber: NewsletterSubscriber) -> dict:
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
    
def verify_newsletter_subscriber(verify_request: EmailVerificationRequest) -> bool:
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
        session_id: str, 
        user_id: str,
        customer_id: str,
        line_items: list[dict],
        status: str = "pending",
        metadata: Optional[dict] = None
) -> dict:
    """
    Insert a new checkout session into the database
    
    Args:
        supabase: Supabase client instance
        session_id: Stripe checkout session ID
        user_id: User ID from Supabase
        customer_id: Stripe customer ID
        line_items: List of line items for the checkout session
        status: Session status (default: "pending")
        metadata: Optional metadata for the checkout session

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
            "status": status,
            "metadata": metadata
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
) -> list | None:
    """Update an existing checkout session"""
    try:
        logger.debug(f"update_checkout_session(): Updating session with ID {session_id} to status {status}")

        # Prepare data to update
        response = supabase.table('checkout_sessions').update({
            "status": status,
            "metadata": metadata
        }).eq("session_id", session_id).execute()

        logger.debug(f"update_checkout_session(): Updated data: {response.data}")
        
        return response.data if response.data else None
        
    except Exception as e:
        logger.error(f"update_checkout_session(): Failed to update checkout session: {str(e)}")
        raise

def insert_user_subscription(
    status: str,
    user_id: str,
    customer_id: Optional[str] = None,
    stripe_subscription_id: Optional[str] = None,
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
        status: Subscription status ('pending', 'active', or 'cancelled')
        user_id: User ID from Supabase
        customer_id: Stripe customer ID (optional)
        stripe_subscription_id: Stripe subscription ID (optional)
        address_id: UUID of the delivery address (optional)
        baby_dob: Baby's date of birth (optional)
        baby_weight_at_start: Baby's weight when starting subscription (optional)
        subscribed_at: Subscription start timestamp (optional)
        last_payment_date: Last payment date (optional)
        next_payment_date: Next payment date (optional)
    Returns:
        dict: The inserted user subscription record

    Raises:
        Exception: If database insertion fails
    """
    try:
        # Initialize subscription data with required fields
        subscription_data = {
            "status": status,
            "user_id": user_id
        }
        if customer_id:
            subscription_data["customer_id"] = customer_id
        if stripe_subscription_id:
            subscription_data["stripe_subscription_id"] = stripe_subscription_id
        if subscribed_at:
            subscription_data["subscribed_at"] = subscribed_at.isoformat()
        if last_payment_date:
            subscription_data["last_payment_date"] = last_payment_date.isoformat()
        if next_payment_date:
            subscription_data["next_payment_date"] = next_payment_date.isoformat()
        if address_id:
            subscription_data["address_id"] = str(address_id)  # Convert UUID to string
        if baby_dob:
            subscription_data["baby_dob"] = baby_dob.isoformat()
        if baby_weight_at_start is not None:  # Check is not None because 0.0 is valid
            subscription_data["baby_weight_at_start"] = baby_weight_at_start
        
        response = supabase.table('user_subscriptions').insert(subscription_data).execute()
        
        logger.debug(f"insert_user_subscription(): Inserted data: {response.data}")

        if not response.data:
            raise Exception("No data returned from subscription insert")
            
        return response.data[0]
        
    except Exception as e:
        logger.error(f"insert_user_subscription(): Failed to store subscription: {str(e)}")
        raise

def insert_subscription_items(subscription_items: list[dict]):
    """
    Insert subscription items into the database

    Args:
        subscription_items: List of subscription item dictionaries to insert
    Returns:
        response: the inserted subscription items records
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

        return response

    except Exception as e:
        logger.error(f"insert_subscription_items(): Failed to store subscription items: {str(e)}")
        raise

def get_subscription_items(subscription_id: str) -> list[dict]:
    """
    Retrieve subscription items for a given subscription ID

    Args:
        subscription_id: The ID of the subscription

    Returns:
        list[dict]: A list of subscription item dictionaries
    """
    try:
        response = supabase.table('subscription_items')\
            .select("*")\
            .eq("subscription_id", subscription_id)\
            .execute()
        
        logger.debug(f"get_subscription_items(): Retrieved data: {response.data}")
        return response.data
    except Exception as e:
        logger.error(f"get_subscription_items(): Failed to retrieve subscription items: {str(e)}")
        raise

def update_user_subscription(
    subscription_id: str,
    status: Optional[str] = None,
    user_id: Optional[str] = None,
    customer_id: Optional[str] = None,
    stripe_subscription_id: Optional[str] = None,
    address_id: Optional[UUID] = None,
    baby_dob: Optional[datetime] = None,
    baby_weight_at_start: Optional[float] = None,
    subscribed_at: Optional[datetime] = None,
    last_payment_date: Optional[datetime] = None,
    next_payment_date: Optional[datetime] = None,
    cancelled_at: Optional[datetime] = None
) -> dict | None:
    """Update an existing user subscription
    
    Args:
        supabase: Supabase client instance
        subscription_id: ID of the subscription to update
        status: Subscription status ('pending', 'active', or 'cancelled') (optional)
        user_id: User ID from Supabase (optional)
        customer_id: Stripe customer ID (optional)
        stripe_subscription_id: Stripe subscription ID (optional)
        address_id: UUID of the delivery address (optional)
        baby_dob: Baby's date of birth (optional)
        baby_weight_at_start: Baby's weight when starting subscription (optional)
        subscribed_at: Subscription start timestamp (optional)
        last_payment_date: Last payment date (optional)
        next_payment_date: Next payment date (optional)
        cancelled_at: Cancellation timestamp (optional)
    Returns:
        dict: The updated subscription data
        
    Raises:
        Exception: If database update fails
    """
    try:
        logger.debug(f"update_user_subscription(): Updating subscription {subscription_id}")

        # Initialize empty update data
        data = {}

        # Add all optional fields if they are provided
        if status is not None:
            data["status"] = status
        if user_id is not None:
            data["user_id"] = user_id
        if customer_id is not None:
            data["customer_id"] = customer_id
        if stripe_subscription_id is not None:
            data["stripe_subscription_id"] = stripe_subscription_id
        if subscribed_at is not None:
            data["subscribed_at"] = subscribed_at.isoformat()
        if last_payment_date is not None:
            data["last_payment_date"] = last_payment_date.isoformat()
        if next_payment_date is not None:
            data["next_payment_date"] = next_payment_date.isoformat()
        if cancelled_at is not None:
            data["cancelled_at"] = cancelled_at.isoformat()
        if address_id is not None:
            data["address_id"] = str(address_id)  # Convert UUID to string
        if baby_dob is not None:
            data["baby_dob"] = baby_dob.isoformat()
        if baby_weight_at_start is not None:  # 0.0 is valid
            data["baby_weight_at_start"] = baby_weight_at_start

        if not data:
            logger.warning("update_user_subscription(): No fields provided to update")
            return None
        
        # Update the subscription in the database
        response = supabase.table('user_subscriptions').update(
            data
        ).eq("id", subscription_id).execute()

        # if the status has changed, update the subscription progress as well
        if "status" in data:
            update_subscription_progress_admin(
                subscription_id,
                status=data["status"]
            )

        logger.debug(f"update_user_subscription(): Updated data: {response.data}")
        
        return response.data[0] if response.data else None
        
    except Exception as e:
        logger.error(f"update_user_subscription(): Failed to update subscription: {str(e)}")
        raise

# TODO: Implement get_subscription to return a SubscriptionDetailsResponse for a given subscription ID
def get_subscription_by_id(subscription_id: str) -> dict | None:
    """
    Retrieve a subscription by its ID
    """
    try:
        logger.debug(f"get_subscription_by_id(): Retrieving subscription with ID {subscription_id}")
        
        response = supabase.table('user_subscriptions').select('*').eq('id', subscription_id).execute()
        if response.data:
            return response.data[0]
        return None
    except Exception as e:
        logger.error(f"get_subscription_by_id(): Error retrieving subscription with ID {subscription_id}: {str(e)}")
        raise Exception(f"Error retrieving subscription with ID {subscription_id}: {str(e)}")

def get_user_subscriptions(supabase: Client, user_id: str):
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

def insert_subscription_progress(subscription_id: str, status: str) -> dict:
    """
    Insert a new subscription progress record into the database

    Args:
        subscription_id (str): The ID of the subscription.
        status (str): The current status of the subscription.

    Returns:
        dict: The inserted subscription progress record or None if the insertion failed.

    Raises:
        Exception: If the insertion fails.
    """
    try:
        response = supabase.table('subscription_progress').insert({
            "subscription_id": subscription_id,
            "status": status
        }).execute()

        logger.debug(f"insert_subscription_progress(): Inserted data: {response}")

        return response.data[0] if response.data else None

    except Exception as e:
        logger.error(f"insert_subscription_progress(): Failed to insert subscription progress: {str(e)}")
        raise

def update_subscription_progress_admin(
    subscription_id: str,
    status: Optional[str] = None,
    meeting_date: Optional[datetime] = None,
) -> None:
    """
    Update the progress record for a given subscription_id.
    """
    try:
        update_data = {}
        if status is not None:
            update_data["status"] = status
        if meeting_date is not None:
            # Convert datetime to ISO string if needed
            if isinstance(meeting_date, datetime):
                update_data["meeting_date"] = meeting_date.isoformat()
            else:
                update_data["meeting_date"] = meeting_date
        if not update_data:
            return  # Nothing to update
        # Find the progress record by subscription_id
        response = supabase.table('subscription_progress').update(update_data).eq('subscription_id', subscription_id).execute()
        if hasattr(response, "error") and response.error:
            logger.error(f"update_subscription_progress_admin(): Supabase error: {response.error}")
            raise RuntimeError(f"Supabase error: {response.error}")
        logger.info(f"update_subscription_progress_admin(): Updated progress for subscription_id {subscription_id}")
    except Exception as e:
        logger.error(f"update_subscription_progress_admin(): Error updating progress: {str(e)}")
        raise

def insert_user_address(
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

def get_subscription_progress(subscription_id: str) -> dict | None:
    """
    Retrieve the subscription progress record for a given subscription ID

    Args:
        subscription_id (str): The ID of the subscription.
    Returns:
        dict | None: The subscription progress record or None if not found.
    """
    try:
        response = supabase.table('subscription_progress').select('*').eq('subscription_id', subscription_id).execute()
        logger.debug(f"get_subscription_progress(): Retrieved progress for subscription {subscription_id}: {response.data}")

        return response.data[0] if response.data else None
    except Exception as e:
        logger.error(f"get_subscription_progress(): Error fetching progress for subscription {subscription_id}: {str(e)}")
        raise

def get_all_subscription_progress(supabase: Client, auth_supabase: Client) -> list[SubscriptionDashboardResponse]:
    """
    Retrieve all subscription progress records joined with user subscription data and user information.
    Returns a list of SubscriptionDashboardResponse.
    """
    try:
        # 1. Get subscription_progress joined with user_subscriptions
        progress_response = supabase.table('subscription_progress').select(
            """
            subscription_id,
            status,
            meeting_date,
            last_updated,
            user_subscriptions!inner (
                id,
                user_id,
                status,
                subscribed_at,
                cancelled_at,
                last_payment_date,
                next_payment_date,
                baby_dob,
                baby_weight_at_start
            )
            """
        ).execute()

        if hasattr(progress_response, "error") and progress_response.error:
            logger.error("Supabase error fetching subscription_progress: %s", progress_response.error)
            raise RuntimeError(f"Supabase error: {progress_response.error}")

        logger.debug(f"get_subscription_progress(): Retrieved subscription progress data: {progress_response.data}")

        # 2. Collect all unique user_ids
        user_ids = set()
        for record in progress_response.data:
            subscription = record.get("user_subscriptions")
            if subscription and subscription.get("user_id"):
                user_ids.add(subscription["user_id"])

        if not user_ids:
            logger.debug("No user IDs found in subscriptions")
            return []

        # 3. Get user info for all user_ids
        users_response = auth_supabase.auth.admin.list_users()
        users = users_response.users if hasattr(users_response, "users") else users_response
        logger.debug(f"get_subscription_progress(): Retrieved user data: {users}")

        # 4. Build a user_id -> user object map
        user_map = {}
        for user in users:
            # Supabase Python client returns User objects, not dicts
            user_id = getattr(user, "id", None)
            if user_id:
                user_map[user_id] = user

        # 5. Build the final response
        result = []
        for record in progress_response.data:
            subscription = record.get("user_subscriptions", {})
            user_id = subscription.get("user_id")
            user = user_map.get(user_id)

            # Default values
            customer_name = "Unknown"
            customer_email = None

            if user:
                # Supabase User object: user_metadata is a dict
                meta = getattr(user, "user_metadata", {}) or {}
                first = meta.get("first_name", "") or meta.get("firstName", "")
                last = meta.get("surname", "") or meta.get("lastName", "")
                customer_name = f"{first} {last}".strip() or "Unknown"
                customer_email = getattr(user, "email", None) or meta.get("email")

            result.append(SubscriptionDashboardResponse(
                subscription_id=record.get("subscription_id"),
                user_id=user_id,
                customer_name=customer_name,
                customer_email=customer_email,
                subscription_status=subscription.get("status"),
                progress_status=record.get("status"),
                meeting_date=record.get("meeting_date"),
                subscribed_at=subscription.get("subscribed_at"),
                cancelled_at=subscription.get("cancelled_at"),
                last_payment_date=subscription.get("last_payment_date"),
                next_payment_date=subscription.get("next_payment_date"),
                baby_dob=subscription.get("baby_dob"),
                baby_weight_at_start=subscription.get("baby_weight_at_start"),
                last_updated=record.get("last_updated"),
            ))

        logger.debug("get_subscription_progress(): Returning %d dashboard records", len(result))
        return result

    except Exception as e:
        logger.error(f"get_subscription_progress(): Error fetching subscription progress records: {str(e)}")
        raise

def get_user_by_subscription_id(supabase: Client, subscription_id: str) -> Optional[dict]:
    """
    Retrieve user information based on a subscription ID
    """
    try:
        response = supabase.table('user_subscriptions').select('user_id').eq('id', subscription_id).execute()
        logger.debug(f"get_user_by_subscription_id(): Retrieved user for subscription {subscription_id}: {response.data}")

        if response.data and len(response.data) > 0:
            user_id = response.data[0].get('user_id')
            user_response = supabase.auth.admin.get_user_by_id(user_id)
            if hasattr(user_response, "user"):
                user = user_response.user
                return {
                    "id": getattr(user, "id", None),
                    "email": getattr(user, "email", None),
                    "user_metadata": getattr(user, "user_metadata", {})
                }
            else:
                logger.warning(f"get_user_by_subscription_id(): No user found with ID {user_id}")
                return None
        else:
            logger.warning(f"get_user_by_subscription_id(): No subscription found with ID {subscription_id}")
            return None
    except Exception as e:
        logger.error(f"get_user_by_subscription_id(): Error fetching user for subscription {subscription_id}: {str(e)}")
        raise

def get_subscription_address(subscription_id: str) -> Optional[dict]:
    """
    Retrieve the address associated with a subscription ID
    """
    try:
        response = supabase.table('user_subscriptions').select('address_id').eq('id', subscription_id).execute()
        logger.debug(f"get_subscription_address(): Retrieved address for subscription {subscription_id}: {response.data}")

        if response.data and len(response.data) > 0:
            address_id = response.data[0].get('address_id')
            address_response = supabase.table('user_addresses').select('*').eq('id', address_id).execute()
            if address_response.data and len(address_response.data) > 0:
                return address_response.data[0]
            else:
                logger.warning(f"get_subscription_address(): No address found with ID {address_id}")
                return None
        else:
            logger.warning(f"get_subscription_address(): No subscription found with ID {subscription_id}")
            return None
    except Exception as e:
        logger.error(f"get_subscription_address(): Error fetching address for subscription {subscription_id}: {str(e)}")
        raise