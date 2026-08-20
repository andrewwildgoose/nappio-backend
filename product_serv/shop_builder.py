import logging

from config.supabase import get_supabase
from models.payment_models import CartItem
from repositories.product_repository import get_products

logger = logging.getLogger('uvicorn.error')

supabase = get_supabase()


def build_stripe_shop_line_items(items: list[CartItem]) -> list[dict]:
    """
    Convert a list of CartItem objects into Stripe-compatible line items.

    Looks up the Stripe price ID for each product and pairs it with the requested quantity.
    """
    try:
        product_ids = [item.product_id for item in items]
        quantity_map = {item.product_id: item.quantity for item in items}

        rows = (
            supabase.table('product')
            .select('id, stripe_price_id')
            .in_('id', product_ids)
            .execute()
        )

        stripe_line_items = []
        for row in rows.data:
            price_id = row.get('stripe_price_id')
            if price_id:
                qty = quantity_map.get(row['id'], 1)
                stripe_line_items.append({"price": price_id, "quantity": qty})

        logger.debug(f"build_stripe_shop_line_items(): Built line items: {stripe_line_items}")
        return stripe_line_items

    except Exception as e:
        logger.error(f"build_stripe_shop_line_items(): Error: {str(e)}")
        raise


def calculate_order_total(items: list[CartItem]) -> int:
    """
    Calculate the total order price in pence.

    Fetches each product's price from the database and multiplies by quantity.
    """
    try:
        product_ids = [item.product_id for item in items]
        quantity_map = {item.product_id: item.quantity for item in items}

        products = get_products(product_ids) or []

        total = 0
        for product in products:
            qty = quantity_map.get(product['id'], 0)
            total += product['price'] * qty

        logger.debug(f"calculate_order_total(): Total = {total} pence for {len(items)} cart items")
        return total

    except Exception as e:
        logger.error(f"calculate_order_total(): Error: {str(e)}")
        raise


def build_order_items_for_db(order_id: str, items: list[CartItem]) -> list[dict]:
    """
    Build the list of dicts required by insert_order_items, capturing price_at_purchase.
    """
    try:
        product_ids = [item.product_id for item in items]
        quantity_map = {item.product_id: item.quantity for item in items}

        products = get_products(product_ids) or []
        price_map = {p['id']: p['price'] for p in products}

        order_items = []
        for item in items:
            order_items.append({
                "order_id": order_id,
                "product_id": item.product_id,
                "quantity": item.quantity,
                "price_at_purchase": price_map.get(item.product_id, 0),
            })

        logger.debug(f"build_order_items_for_db(): Built {len(order_items)} order items for order {order_id}")
        return order_items

    except Exception as e:
        logger.error(f"build_order_items_for_db(): Error: {str(e)}")
        raise
