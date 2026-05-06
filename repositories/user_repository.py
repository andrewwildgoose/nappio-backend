import logging
from typing import Optional
from uuid import UUID

from config.supabase import get_supabase
from models.user_models import UserAddress

logger = logging.getLogger('uvicorn.error')

supabase = get_supabase()


def insert_user_address(new_address: UserAddress) -> Optional[UserAddress]:
    """Insert a new user address into the database."""
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


def get_user_addresses(user_id: UUID) -> list[UserAddress]:
    """Retrieve all addresses for a given user ID."""
    try:
        response = supabase.table('user_addresses').select('*').eq('user_id', user_id).execute()
        logger.debug(f"get_user_addresses(): Retrieved addresses for user {user_id}: {response.data}")

        return [UserAddress(**addr) for addr in response.data] if response.data else []
    except Exception as e:
        logger.error(f"get_user_addresses(): Error fetching addresses for user {user_id}: {str(e)}")
        raise


def delete_user_address(address_id: UUID) -> bool:
    """Delete a user address by its ID."""
    try:
        response = supabase.table('user_addresses').delete().eq('id', address_id).execute()
        logger.debug(f"delete_user_address(): Deleted address with ID {address_id}: {response.data}")

        return response.data is not None and len(response.data) > 0
    except Exception as e:
        logger.error(f"delete_user_address(): Error deleting address with ID {address_id}: {str(e)}")
        raise


def get_user_by_subscription_id(subscription_id: str) -> Optional[dict]:
    """Retrieve user information based on a subscription ID."""
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
