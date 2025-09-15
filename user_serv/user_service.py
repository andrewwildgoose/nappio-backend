import logging
import os
import stripe
from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel
from supabase import Client
from uuid import UUID

import ios.io_db as io_db
import email_serv.email_processor as email_processor

logger = logging.getLogger('uvicorn.error')

class ProductDetails(BaseModel):
    name: str
    price: float
    currency: str

class SubscriptionDetailsResponse(BaseModel):
    id: Optional[UUID]
    status: str
    start_date: datetime
    end_date: Optional[datetime] = None
    subscription_id: str
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


#TODO: There is a similar function in io_db.py, consider refactoring to avoid duplication
def get_user_subscriptions(supabase: Client, user_id: str) -> List[SubscriptionDetailsResponse]:
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
                    subscription_id=sub['stripe_subscription_id'],
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

def get_user_addresses(supabase: Client, user_id: str) -> List[io_db.UserAddress]:
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

def add_user_address(supabase: Client, address_request: AddUserAddressRequest, user_id: str) -> AddUserAddressResponse:
    """
    Add a new address for a user to the database

    Args:
        supabase: Supabase client instance
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
            response = io_db.insert_user_address(supabase, new_address)
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

def delete_user_address(supabase: Client, address_id: UUID, user_id: UUID) -> DeleteAddressResponse:
    """
    Delete a user's address from the database

    Args:
        supabase: Supabase client instance
        address_id: UUID of the address to delete
        user_id: UUID of the user requesting the deletion

    Returns:
        DeleteAddressResponse: Response indicating the result of the deletion
    """
    try:
        response = supabase.table('user_addresses').delete().eq('id', str(address_id)).eq('user_id', str(user_id)).execute()
        if response.status_code == 204:
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

def meeting_confirmation_process(supabase: Client, subscription_id: str, meeting_date: datetime):
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
        user_info = io_db.get_user_by_subscription_id(supabase, subscription_id)
        if user_info:
            user_email = user_info.get("email")
            user_name = user_info.get("user_metadata", {}).get("name")

            logger.info(f"meeting_confirmation_process(): Retrieved user info for subscription {subscription_id}: email={user_email}, name={user_name}")
            if user_email and user_name:
                email_processor.send_meeting_confirm_and_sub_checkout_email(user_email, user_name, meeting_date, checkout_trigger_link)
        else:
            raise ValueError(f"meeting_confirmation_process(): No user found for subscription {subscription_id}")

        # email user confirming meeting date & with link to trigger checkout building
        pass
    except Exception as e:
        logger.error(f"meeting_confirmation_process(): Error in meeting confirmation process: {str(e)}")
        raise