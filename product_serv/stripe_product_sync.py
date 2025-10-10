from typing import Dict, Any
import logging
from models.payment_models import WebhookEvent
from supabase import Client

# Get Supabase client from config
from config.supabase import get_supabase

logger = logging.getLogger('uvicorn.error')

# Initialize Supabase client
supabase = get_supabase()

async def handle_product_created(event: WebhookEvent):
    """Sync new Stripe product to database"""
    try:
        # Extract product type from metadata
        stripe_product = event.data['object']

        logger.debug(f"Received product.created event: {stripe_product}")

        product_data = {
            'name': stripe_product['name'],
            'description': stripe_product.get('description', ''),
            'stripe_product_id': stripe_product['id'],
            'active': stripe_product['active'],
            'image_url': stripe_product.get('images', [None])[0] if stripe_product.get('images') else None
        }
        
        # Insert into Supabase
        response = supabase.table('product').insert(product_data).execute()
        logger.info(f"Created product: {response.data}")
        
    except Exception as e:
        logger.error(f"Error creating product: {e}")

async def handle_product_updated(event: WebhookEvent):
    """Sync updated Stripe product to database"""
    try:
        # Extract product data
        stripe_product = event.data['object']

        logger.debug(f"Received product.updated event: {stripe_product}")

        product_data = {
            'name': stripe_product['name'],
            'description': stripe_product.get('description', ''),
            'active': stripe_product['active'],
            'image_url': stripe_product.get('images', [None])[0] if stripe_product.get('images') else None
        }
        
        # Update in Supabase
        response = supabase.table('product').update(product_data).eq('stripe_product_id', stripe_product['id']).execute()
        logger.info(f"Updated product: {response.data}")
        
    except Exception as e:
        logger.error(f"Error updating product: {e}")

async def handle_product_deleted(event: WebhookEvent):
    """Handle product deletion in database"""
    try:
        stripe_product = event.data['object']

        logger.debug(f"Received product.deleted event: {stripe_product}")
        # Set product as inactive rather than deleting
        response = supabase.table('product').update({
            'active': False
        }).eq('stripe_product_id', stripe_product['id']).execute()
        logger.info(f"Marked product as inactive: {response.data}")
        
    except Exception as e:
        logger.error(f"Error handling product deletion: {e}")

async def handle_price_created(event: WebhookEvent):
    """Update product with price information"""
    try:
        stripe_price = event.data['object']

        logger.debug(f"Received price.created event: {stripe_price}")

        # Get product type
        product_type = 'subscription' if 'recurring' in stripe_price else 'oneoff'

        # Convert from cents to pence (if needed)
        price_in_pence = stripe_price['unit_amount']
        
        # Update the corresponding product
        response = supabase.table('product').update({
            'price': price_in_pence,
            'type': product_type,
            'stripe_price_id': stripe_price['id'],
            'currency': stripe_price['currency'].upper()
        }).eq('stripe_product_id', stripe_price['product']).execute()
        
        logger.info(f"Updated product with price: {response.data}")
        
    except Exception as e:
        logger.error(f"Error updating product price: {e}")

async def handle_price_updated(event: WebhookEvent):
    """Handle price updates in database"""
    try:
        stripe_price = event.data['object']

        logger.debug(f"Received price.updated event: {stripe_price}")
        # Convert from cents to pence (if needed)
        price_in_pence = stripe_price['unit_amount']
        
        # Update the corresponding product
        response = supabase.table('product').update({
            'price': price_in_pence,
            'stripe_price_id': stripe_price['id'],
            'currency': stripe_price['currency'].upper()
        }).eq('stripe_product_id', stripe_price['product']).execute()
        
        logger.info(f"Updated product price: {response.data}")
        
    except Exception as e:
        logger.error(f"Error updating product price: {e}")


