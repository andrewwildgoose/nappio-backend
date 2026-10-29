import logging
from typing import Optional

from config.supabase import get_supabase

from models.user_models import Address, AddAddressRequest, UserAddress

logger = logging.getLogger('uvicorn.error')

supabase = get_supabase()


def insert_order(
    total_price: int,
    status: str = "pending",
    user_id: Optional[str] = None,
    address_id: Optional[str] = None,
) -> dict:
    """Insert a new order into the database. user_id is optional to support guest orders."""
    try:
        order_data: dict = {
            "total_price": total_price,
            "status": status,
        }
        if user_id is not None:
            order_data["user_id"] = user_id
        if address_id is not None:
            order_data["address_id"] = address_id

        response = supabase.table('orders').insert(order_data).execute()

        logger.debug(f"insert_order(): Inserted order: {response.data}")

        if not response.data:
            raise Exception("No data returned from order insert")

        return response.data[0]

    except Exception as e:
        logger.error(f"insert_order(): Failed to insert order: {str(e)}")
        raise


def insert_order_items(order_id: str, items: list[dict]) -> list[dict]:
    """
    Insert order line items into the database.

    Each item dict must contain: product_id, quantity, price_at_purchase.
    """
    try:
        rows = [
            {
                "order_id": order_id,
                "product_id": item["product_id"],
                "quantity": item["quantity"],
                "price_at_purchase": item["price_at_purchase"],
            }
            for item in items
        ]

        response = supabase.table('order_items').insert(rows).execute()

        logger.debug(f"insert_order_items(): Inserted order items: {response.data}")

        return response.data if response.data else []

    except Exception as e:
        logger.error(f"insert_order_items(): Failed to insert order items: {str(e)}")
        raise

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

def insert_guest_address(address_request: Address, email: str) -> AddAddressRequest:
    """
    Add a new address for a user to the database.
    """
    try:

        response = supabase.table('user_addresses').insert({
            "address_line_1": address_request.address_line_1,
            "address_line_2": address_request.address_line_2,
            "city": address_request.city,
            "postcode": address_request.postcode,
            "country": address_request.country,
            "address_notes": address_request.address_notes
        }).execute()

        logger.debug(f"insert_guest_address(): Inserted data: {response}")

        address_response = AddAddressRequest(
            success=True,
            message="Address added successfully.",
            address=response.data[0] if response.data else None
        )
        logger.debug(f"insert_guest_address(): Successfully added address {response.data[0]['id']} for user {email}")
        return address_response

    except Exception as e:
        logger.error(f"insert_guest_address(): Error adding address for user {email}: {str(e)}")
        raise

def get_order(order_id: str) -> Optional[dict]:
    """Retrieve an order by its primary key."""
    try:
        response = supabase.table('orders').select('*').eq('id', order_id).execute()
        logger.debug(f"get_order(): Retrieved order {order_id}: {response.data}")

        return response.data[0] if response.data else None

    except Exception as e:
        logger.error(f"get_order(): Failed to fetch order {order_id}: {str(e)}")
        raise


def get_order_items(order_id: str) -> list[dict]:
    """Retrieve all line items for a given order."""
    try:
        response = (
            supabase.table('order_items')
            .select('*, product:product_id(*)')
            .eq('order_id', order_id)
            .execute()
        )
        logger.debug(f"get_order_items(): Retrieved items for order {order_id}: {response.data}")

        return response.data if response.data else []

    except Exception as e:
        logger.error(f"get_order_items(): Failed to fetch items for order {order_id}: {str(e)}")
        raise


def update_order_status(order_id: str, status: str) -> Optional[dict]:
    """Update the status of an existing order."""
    try:
        response = (
            supabase.table('orders')
            .update({"status": status})
            .eq('id', order_id)
            .execute()
        )
        logger.debug(f"update_order_status(): Updated order {order_id} to status '{status}': {response.data}")

        return response.data[0] if response.data else None

    except Exception as e:
        logger.error(f"update_order_status(): Failed to update order {order_id}: {str(e)}")
        raise
