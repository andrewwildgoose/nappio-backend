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
    plan_name: str
    status: str
    monthly_cost: float
    start_date: datetime
    end_date: Optional[datetime] = None
    subscription_id: str
    next_payment_date: Optional[datetime] = None
    #TODO: Add address

class UserAddressRequest(BaseModel):
    address_line_1: str
    address_line_2: Optional[str] = None
    city: str
    postcode: str
    country: str
    address_notes: Optional[str] = None

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
                    plan_name=product.name,
                    status=sub['status'],
                    monthly_cost=price.unit_amount / 100.0,  # Convert from cents to currency
                    start_date=sub['subscribed_at'],
                    next_payment_date=sub['next_payment_date'],
                    end_date=sub['cancelled_at'],
                    subscription_id=sub['subscription_id']   # Assuming this field is available
                )
                subscriptions.append(subscription_details)
                
            except stripe.error.StripeError as e:
                logger.error(f"Error fetching Stripe details for subscription {sub['subscription_id']}: {str(e)}")
                continue

        return subscriptions

    except Exception as e:
        logger.error(f"get_user_subscriptions(): Error fetching subscriptions for user {user_id}: {str(e)}")
        raise

def update_user_address(
    supabase: Client,
    user_id: str,
    address: UserAddressRequest
) -> dict:
    """
    Update or insert a user's address in the database.

    Args:
        supabase: Supabase client instance
        user_id: User ID to update address for
        address: UserAddress object containing address details

    Returns:
        dict: Updated or inserted address data
    """
    try:
        logger.debug(f"update_user_address(): Processing address for user {user_id}")
        
        # Check if address exists
        existing_address = _get_existing_address(supabase, user_id, address)
        
        if existing_address:
            logger.info(f"update_user_address(): Updating existing address for user {user_id}")
            response = supabase.table('user_addresses').update(address.model_dump()).eq('id', existing_address['id']).execute()
        else:
            logger.info(f"update_user_address(): Creating new address for user {user_id}")
            response = supabase.table('user_addresses').insert({
                'user_id': user_id,
                **address.model_dump()
            }).execute()

        logger.info(f"update_user_address(): Successfully processed address for user {user_id}")
        return response.data[0]

    except Exception as e:
        logger.error(f"update_user_address(): Error processing address for user {user_id}: {str(e)}")
        raise

def _get_existing_address(supabase: Client, user_id: str, address: io_db.UserAddress) -> Optional[dict]:
    """
    Check if an address already exists for the user with matching details.
    
    Returns:
        Optional[dict]: Existing address record if found, None otherwise
    """
    try:
        response = supabase.table('user_addresses').select('*').match({
            'user_id': user_id,
            'address_line_1': address.address_line_1,
            'postcode': address.postcode
        }).execute()
        
        return response.data[0] if response.data else None
        
    except Exception as e:
        logger.error(f"Error checking existing address: {str(e)}")
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