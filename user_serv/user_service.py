import logging
import os
import stripe
from datetime import datetime
from typing import Optional, List

from supabase import Client
from uuid import UUID

import ios.io_db as io_db
import email_serv.email_processor as email_processor
from models.user_models import (
    ProductDetails,
    SubscriptionDetailsResponse,
    AddUserAddressRequest,
    AddUserAddressResponse,
    DeleteAddressResponse,
)

# Get Supabase client from config
from config.supabase import get_supabase

logger = logging.getLogger('uvicorn.error')

# Initialize Supabase client
supabase = get_supabase()

def get_subscription(subscription_id: str) -> Optional[SubscriptionDetailsResponse]:
    """
    Get a subscription by its ID from the database

    Args:
        subscription_id: The ID of the subscription to retrieve

    Returns:
        SubscriptionDetailsResponse if found, else None
    """
    try:
        response = io_db.get_subscription_by_id(subscription_id)
        if response is not None:
            logger.debug(f"get_subscription(): Retrieved subscription {subscription_id}: {response}")
            # Map the database response to SubscriptionDetailsResponse
            subscription = SubscriptionDetailsResponse(
                id=response['id'],
                user_id=response['user_id'],
                customer_id=response.get('customer_id'),
                status=response['status'],
                start_date=response['subscribed_at'],
                end_date=response.get('cancelled_at'),
                stripe_subscription_id=response['stripe_subscription_id'],
                next_payment_date=response.get('next_payment_date'),
                address_id=response.get('address_id'),
                items=[]  # Items can be fetched separately if needed
            )
            return subscription
        else:
            logger.debug(f"get_subscription(): No subscription found with ID {subscription_id}")
            return None
    except Exception as e:
        logger.error(f"get_subscription(): Error fetching subscription {subscription_id}: {str(e)}")
        raise

#TODO: There is a similar function in io_db.py, consider refactoring to avoid duplication
def get_user_subscriptions(user_id: str) -> List[SubscriptionDetailsResponse]:
    """
    Get a user's subscription details from the database and Stripe

    Args:
        supabase: Supabase client instance
        user_id: User ID to fetch subscriptions for

    Returns:
        List[SubscriptionDetailsResponse]: List of user's subscription details including plan info
    """
    try:
        # Get subscriptions from database
        response = supabase.table('user_subscriptions').select('*').eq('user_id', user_id).execute()
        logger.debug(f"get_user_subscriptions(): Retrieved subscriptions for user {user_id}")

        #logger.debug(f"get_user_subscriptions(): Response data: {response.data}")
        subscriptions = []
        for sub in response.data:
            try:
                

                # Get product details from the subscription_items and products tables
                product_response = supabase.table('subscription_items') \
                    .select(
                        "product(name, price, currency)"
                    ) \
                    .eq('subscription_id', sub['id']) \
                    .execute()
                
                logger.debug(f"Product details for subscription {sub['id']}: {product_response.data}")

                # Create list to hold product details
                product_items = []
                
                if product_response.data:
                    for item in product_response.data:
                        if item['product']:  # Check if product data exists
                            product = item['product']
                            product_items.append(ProductDetails(
                                name=product['name'],
                                price=float(product['price']) / 100,
                                currency=product['currency']
                            ))
                    
                subscription_details = SubscriptionDetailsResponse(
                    id=sub['id'],
                    status=sub['status'],
                    start_date=sub['subscribed_at'],
                    next_payment_date=sub['next_payment_date'],
                    end_date=sub['cancelled_at'],
                    stripe_subscription_id=sub['stripe_subscription_id'],
                    address_id=sub['address_id'] if 'address_id' in sub else None,
                    items=product_items
                )
                subscriptions.append(subscription_details)
                
            except stripe.error.StripeError as e:
                logger.error(f"Error fetching Stripe details for subscription {sub['subscription_id']}: {str(e)}")
                continue

        return subscriptions

    except Exception as e:
        logger.error(f"get_user_subscriptions(): Error fetching subscriptions for user {user_id}: {str(e)}")
        raise

#TODO: Refactor to use product object
def get_subscription_items(subscription_id: UUID) -> List[dict]:
    """
    Get all items for a subscription from the database

    Args:
        subscription_id: The ID of the subscription to retrieve items for
    Returns:
        List[SubscriptionItem]: List of subscription items (empty list if none found)
    """
    try:
        subscription_id_str = str(subscription_id)  # Ensure it's a string
        items = io_db.get_subscription_items(subscription_id_str)
        logger.debug(f"get_subscription_items(): Retrieved {len(items)} items for subscription {subscription_id}")
        return items
    except Exception as e:
        logger.error(f"get_subscription_items(): Error fetching items for subscription {subscription_id}: {str(e)}")
        raise

def get_user_addresses(user_id: str) -> List[io_db.UserAddress]:
    """
    Get all addresses for a user from the database
    
    Args:
        supabase: Supabase client instance
        user_id: User ID to fetch addresses for
        
    Returns:
        List[UserAddress]: List of user's addresses (empty list if none found)
    """
    try:
        response = supabase.table('user_addresses').select('*').eq('user_id', user_id).execute()
        
        if not response.data:
            logger.debug(f"get_user_addresses(): No addresses found for user {user_id}")
            return []
            
        return [io_db.UserAddress(**address) for address in response.data]
        
    except Exception as e:
        logger.error(f"get_user_addresses(): Error fetching addresses for user {user_id}: {str(e)}")
        raise

def add_user_address(address_request: AddUserAddressRequest, user_id: str) -> AddUserAddressResponse:
    """
    Add a new address for a user to the database

    Args:
        address_request: UserAddressRequest containing address details

    Returns:
        UserAddress: The newly created address object
    """
    try:
        # Prepare data for insertion
        address_data = address_request.model_dump(exclude_unset=True)
        address_data['user_id'] = str(user_id)  # Ensure user_id is set


        try:
            new_address = io_db.UserAddress(**address_data)
            response = io_db.insert_user_address(new_address)
            logger.debug(f"add_user_address(): Inserted address data: {response}")
            address_response = AddUserAddressResponse(
                success=True,
                message="Address added successfully.",
                address=response if response else None
            )
            logger.debug(f"add_user_address(): Successfully added address {new_address.id} for user {user_id}")
            return address_response
        except Exception as e:
            logger.error(f"add_user_address(): Failed to add address: {str(e)}")
            raise Exception("Failed to add address.")

    except Exception as e:
        logger.error(f"add_user_address(): Error adding address for user {user_id}: {str(e)}")
        raise

#TODO: Refactor to use io_db function
def delete_user_address(address_id: UUID, user_id: UUID) -> DeleteAddressResponse:
    """
    Delete a user's address from the database

    Args:
        address_id: UUID of the address to delete
        user_id: UUID of the user requesting the deletion

    Returns:
        DeleteAddressResponse: Response indicating the result of the deletion
    """
    try:
        response = supabase.table('user_addresses').delete().eq('id', str(address_id)).eq('user_id', str(user_id)).execute()
        if response.status_code == 200:
            logger.debug(f"delete_user_address(): Successfully deleted address {address_id}")
            return DeleteAddressResponse(success=True, message="Address deleted successfully.")
        else:
            logger.error(f"delete_user_address(): Failed to delete address {address_id}, status code: {response.status_code}")
            return DeleteAddressResponse(success=False, message="Failed to delete address.")

    except Exception as e:
        logger.error(f"delete_user_address(): Error deleting address {address_id}: {str(e)}")
        raise

def assign_subscription_address(
    supabase: Client,
    user_id: str,
    subscription_id: str,
    address_id: str
) -> dict:
    """
    Assign an address to a subscription using a single database call
    """
    try:
        logger.debug(f"Updating subscription {subscription_id} with address {address_id}")
        
        # Update subscription with address_id only if user owns both the subscription and address
        response = supabase.table('user_subscriptions').update({
            'address_id': address_id
        }).match({
            'id': subscription_id,
            'user_id': user_id,
        }).execute()

        logger.debug(f"assign_subscription_address(): Response from Supabase: {response.data}")
        if not response.data:
            logger.error("Failed to update subscription - verify subscription and address ownership")
            raise ValueError("Subscription or address not found or doesn't belong to user")

        logger.info(f"Successfully assigned address {address_id} to subscription {subscription_id}")
        return response.data[0]

    except Exception as e:
        logger.error(f"Error assigning address to subscription: {str(e)}")
        raise

def meeting_confirmation_process(subscription_id: str, meeting_date: datetime):
    """
    Placeholder for meeting confirmation email process
    """
    try:
        logger.info(f"meeting_confirmation_process(): Processing meeting confirmation for subscription {subscription_id} with meeting date {meeting_date}")
        # build link to front end to trigger checkout session creation
        # Frontend URL
        FRONTEND_URL = os.environ.get('FRONTEND_URL')

        checkout_trigger_link = f"{FRONTEND_URL}/checkout?subscription_id={subscription_id}"

        # get user email & name from user id if needed
        user_info = io_db.get_user_by_subscription_id(subscription_id)

        meeting_date_str = meeting_date.strftime("%A, %B %d, %Y at %I:%M %p")

        subscription_address_res = io_db.get_subscription_address(subscription_id)

        logger.debug(f"meeting_confirmation_process(): Retrieved subscription address: {subscription_address_res}")

        if user_info:
            logger.debug(f"meeting_confirmation_process(): Retrieved user info: {user_info}")
            user_email = user_info.get("email")
            user_name = user_info.get("user_metadata", {}).get("first_name")

            logger.info(f"meeting_confirmation_process(): Retrieved user info for subscription {subscription_id}: email={user_email}, name={user_name}")
            if user_email and user_name:
                email_processor.send_meeting_confirm_and_sub_checkout_email(
                    user_email, 
                    user_name, 
                    meeting_date_str, 
                    checkout_trigger_link,
                    subscription_address_res
                )
                email_processor.send_meeting_confirm_to_team(meeting_date_str, user_name, user_email, subscription_address_res)
                io_db.update_subscription_progress_admin(
                    subscription_id=subscription_id,
                    status="checkout_sent"
                )
            else:
                raise ValueError(f"meeting_confirmation_process(): Incomplete user info for subscription {subscription_id}: email={user_email}, name={user_name}")
        else:
            raise ValueError(f"meeting_confirmation_process(): No user found for subscription {subscription_id}")

        # email user confirming meeting date & with link to trigger checkout building
        pass
    except Exception as e:
        logger.error(f"meeting_confirmation_process(): Error in meeting confirmation process: {str(e)}")
        raise