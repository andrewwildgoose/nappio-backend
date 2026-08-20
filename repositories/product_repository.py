import logging
from typing import Optional

from config.supabase import get_supabase

logger = logging.getLogger('uvicorn.error')

supabase = get_supabase()


def get_stripe_price_ids(product_ids: list[str]) -> list[str]:
    """Retrieve Stripe price IDs from the database that match the given product IDs."""
    try:
        stripe_price_ids_dict = supabase.table('product').select('stripe_price_id').in_("id", product_ids).execute()
        stripe_price_ids = [item['stripe_price_id'] for item in stripe_price_ids_dict.data if item.get('stripe_price_id')]
        logger.debug(f"get_stripe_price_ids(): Retrieved price IDs: {stripe_price_ids}")
        return stripe_price_ids
    except Exception as e:
        logger.error(f"get_stripe_price_ids(): Error retrieving price IDs: {str(e)}")
        raise Exception(f"Error retrieving price IDs: {str(e)}")


def get_products(product_ids: list[str]) -> Optional[list[dict]]:
    """Retrieve product details by product ID."""
    try:
        response = supabase.table('product').select('*').in_('id', product_ids).execute()
        logger.debug(f"get_products(): Retrieved products for IDs {product_ids}: {response.data}")

        return response.data if response.data else None
    except Exception as e:
        logger.error(f"get_products(): Error fetching products with IDs {product_ids}: {str(e)}")
        raise


def get_products_by_stripe_product_ids(stripe_product_ids: list[str]) -> Optional[list[dict]]:
    """Retrieve product details by Stripe product ID."""
    try:
        response = supabase.table('product').select('*').in_('stripe_product_id', stripe_product_ids).execute()
        logger.debug(f"get_products_by_stripe_product_ids(): Retrieved products for Stripe IDs {stripe_product_ids}: {response.data}")

        return response.data if response.data else None
    except Exception as e:
        logger.error(f"get_products_by_stripe_product_ids(): Error fetching products with Stripe IDs {stripe_product_ids}: {str(e)}")
        raise


def get_active_shop_products(product_type: str = "oneoff") -> list[dict]:
    """Retrieve all active products of the given type for the shop."""
    try:
        response = (
            supabase.table('product')
            .select('*')
            .eq('active', True)
            .eq('type', product_type)
            .execute()
        )
        logger.debug(f"get_active_shop_products(): Retrieved {len(response.data)} products of type '{product_type}'")
        return response.data if response.data else []
    except Exception as e:
        logger.error(f"get_active_shop_products(): Error fetching shop products: {str(e)}")
        raise


def get_product_by_stripe_price_id(stripe_price_id: str) -> dict:
    """Retrieve product details by Stripe price ID."""
    try:
        response = supabase.table('product').select('*').eq('stripe_price_id', stripe_price_id).execute()
        logger.debug(f"get_product_by_stripe_price_id(): Retrieved product for Stripe Price ID {stripe_price_id}: {response.data}")

        return response.data[0]
    except Exception as e:
        logger.error(f"get_product_by_stripe_price_id(): Error fetching product with Stripe Price ID {stripe_price_id}: {str(e)}")
        raise
