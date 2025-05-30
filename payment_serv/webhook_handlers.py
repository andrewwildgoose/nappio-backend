from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class WebhookEvent(BaseModel):
    id: str
    type: str
    data: dict
    created: datetime

class SubscriptionWebhookData(BaseModel):
    user_id: str
    plan_id: str
    status: str
    subscribed_at: datetime
    cancelled_at: Optional[datetime] = None

import logging
from datetime import datetime
import stripe
from supabase import Client
from ios.io_db import insert_user_subscription, update_user_subscription, update_checkout_session
from email_serv.email_processor import send_new_subscription_email

logger = logging.getLogger('uvicorn.error')

def webhook_router(event: WebhookEvent, supabase: Client) -> None:
    """Route webhook events to appropriate handlers"""
    try:
        logger.info("Webhook event received in webhook_router()")
        if event.type == "checkout.session.completed":
            handle_checkout_completed(event, supabase)
        elif event.type == "customer.subscription.created":
            handle_subscription_created(event, supabase)
        elif event.type == "customer.subscription.updated":
            handle_subscription_updated(event, supabase)
        elif event.type == "customer.subscription.deleted":
            handle_subscription_updated(event, supabase)
        else:
            logger.warning(f"Unhandled event type: {event.type}")
    except Exception as e:
        logger.error(f"Error processing webhook event: {str(e)}")
        raise

def handle_checkout_completed(event: WebhookEvent, supabase: Client) -> None:
    """Handle successful checkout completion"""
    try:
        logger.info(f"Handling checkout.session.completed for session ID: {event.data['object']['id']}")

        # Retrieve the session and subscription details
        session = stripe.checkout.Session.retrieve(event.data['object'].id)
        
        update_checkout_session(
            supabase=supabase,
            session_id=session.id,
            status=session.status
        )
        logger.info(f"Updated checkout session status to {session.status} for session ID: {session.id}")
        
    except Exception as e:
        logger.error(f"Error handling checkout.session.completed: {str(e)}")
        raise

def handle_subscription_created(webhook_event: WebhookEvent, supabase: Client) -> None:
    """Handle subscription creation"""
    try:
        logger.info(f"Handling customer.subscription.created for subscription ID: {webhook_event.data['object']['id']}")
        subscription = stripe.Subscription.retrieve(webhook_event.data['object']['id'])
        
        logger.debug(f'Plan ID: {subscription["items"]["data"][0]["price"]["metadata"]["plan_id"]}')
        logger.debug(f'Customer ID: {subscription.customer}') 
        logger.debug(f'Subscription ID: {subscription.id}')
        logger.debug(f'Subscription Status: {subscription.status}')
        logger.debug(f'Subscription Created At: {datetime.fromtimestamp(subscription.created)}')
        logger.debug(f'Subscription Metadata: {subscription.metadata}')
        logger.debug(f'Subscription Items: {subscription["items"]["data"]}')

        # Get the supabase user from the checkout session
        user_id_response = supabase.table('checkout_sessions').select('user_id').eq('customer_id', subscription.customer).execute()
        
        if not user_id_response.data:
            raise Exception("User ID not found in checkout session")
        user_id = user_id_response.data[0]['user_id']

        # Create subscription record
        insert_user_subscription(
            supabase=supabase,
            plan_id=subscription['items']['data'][0]['price']['metadata']['plan_id'],
            subscription_id=subscription.id,
            price_id=subscription['items']['data'][0]['price']['id'],
            customer_id=subscription.customer,
            status=subscription.status,
            subscribed_at=datetime.fromtimestamp(subscription.created),
            last_payment_date=datetime.fromtimestamp(subscription['items']['data'][0]['current_period_start']),
            next_payment_date=datetime.fromtimestamp(subscription['items']['data'][0]['current_period_end']),
        )
        
        logger.info(f"Created subscription for user {subscription.customer}")

        # Send confirmation email
        # Retrieve user details from Supabase
        user = supabase.auth.admin.get_user_by_id(user_id)

        if not user:
            logger.error(f"User not found for ID: {user_id}")
            return
        user_email = user.user.email
        first_name = user.user.user_metadata['first_name']

        logger.debug(f"User data: {user}")
        logger.info(f"User email: {user_email}")
        logger.info(f"User first name: {first_name}")

        # Get the product name from the subscription 
        price_id = subscription['items']['data'][0]['price']['id'] 
        price = stripe.Price.retrieve(price_id) 
        logger.debug(f"Price details: {price}")
        product = stripe.Product.retrieve(price['product']) 
        product_name = product['name']

        # Get the price
        unit_amount = price['unit_amount'] # Convert to dollars if the amount is in cents 
        unit_price = unit_amount / 100.0 # Get the currency 
        currency = price['currency']

        subscription_details = {
            "plan_name": product_name,
            "price": f'{currency.upper()} {unit_price:.2f}',
        }

        send_new_subscription_email(user_email, first_name, subscription_details)
        logger.info(f"Sent subscription confirmation email to {user_email}")
        
    except Exception as e:
        logger.error(f"Error handling customer.subscription.created: {str(e)}")
        raise

def handle_subscription_updated(event: WebhookEvent, supabase: Client) -> None:
    """Handle subscription updates"""
    try:
        logger.info(f"Handling customer.subscription.updated for subscription ID: {event.data['object']['id']}")
        subscription = event.data['object']
        subscription_item = subscription['items']['data'][0]
        
        update_user_subscription(
            supabase=supabase,
            subscription_id=subscription.id,
            status=subscription.status,
            last_payment_date=datetime.fromtimestamp(subscription_item.current_period_start),
            next_payment_date=datetime.fromtimestamp(subscription_item.current_period_end),
            cancelled_at=datetime.fromtimestamp(subscription.canceled_at) if subscription.canceled_at else None
        )
        
        logger.info(f"Updated subscription for user {subscription.metadata['user_id']}")
        
    except Exception as e:
        logger.error(f"Error handling customer.subscription.updated: {str(e)}")
        raise