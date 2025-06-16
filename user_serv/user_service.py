import logging
import stripe
from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel
from supabase import Client
from uuid import UUID

import ios.io_db as io_db

logger = logging.getLogger('uvicorn.error')

class SubscriptionDetailsResponse(BaseModel):
    id: Optional[UUID]
    plan_name: str
    status: str
    monthly_cost: float
    start_date: datetime
    end_date: Optional[datetime] = None
    subscription_id: str
    next_payment_date: Optional[datetime] = None
    address_id: Optional[UUID] = None  # Optional field for address ID if applicable

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

        logger.debug(f"get_user_subscriptions(): Response data: {response.data}")
        subscriptions = []
        for sub in response.data:
            try:
                # Get price details from Stripe
                price = stripe.Price.retrieve(sub['price_id'])
                product = stripe.Product.retrieve(price.product)

                subscription_details = SubscriptionDetailsResponse(
                    id=sub['id'],
                    plan_name=product.name,
                    status=sub['status'],
                    monthly_cost=price.unit_amount / 100.0,  # Convert from cents to currency
                    start_date=sub['subscribed_at'],
                    next_payment_date=sub['next_payment_date'],
                    end_date=sub['cancelled_at'],
                    subscription_id=sub['subscription_id'],   # Assuming this field is available
                    address_id=sub['address_id'] if 'address_id' in sub else None
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

def add_user_address(supabase: Client, address_request: AddUserAddressRequest) -> io_db.UserAddress:
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
        response = supabase.table('user_addresses').insert(address_data).execute()

        if response.status_code == 201:
            new_address = io_db.UserAddress(**response.data[0])
            logger.debug(f"add_user_address(): Successfully added address {new_address.id} for user {address_request.user_id}")
            return new_address
        else:
            logger.error(f"add_user_address(): Failed to add address, status code: {response.status_code}")
            raise Exception("Failed to add address.")

    except Exception as e:
        logger.error(f"add_user_address(): Error adding address for user {address_request.user_id}: {str(e)}")
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

