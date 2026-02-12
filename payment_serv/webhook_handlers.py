import logging
import stripe
from datetime import datetime
from models.payment_models import WebhookEvent
from product_serv import stripe_product_sync as sps
import ios.io_db as io_db
from payment_serv import payment_processor as pp

# Get Supabase client from config
from config.supabase import get_supabase

logger = logging.getLogger('uvicorn.error')

# Initialize Supabase client
supabase = get_supabase()

async def webhook_router(event: WebhookEvent) -> None:
    """Route webhook events to appropriate handlers"""
    try:
        #logger.info(f"Webhook event received in webhook_router(): {event.data}")
        match event.type:
            case 'product.created':
                await sps.handle_product_created(event)
            case 'product.updated':
                await sps.handle_product_updated(event)
            case 'product.deleted':
                await sps.handle_product_deleted(event)
            case 'price.created':
                await sps.handle_price_created(event)
            case 'price.updated':
                await sps.handle_price_updated(event)
            case "checkout.session.completed":
                await handle_checkout_completed(event)
            case "customer.subscription.created":
                await handle_subscription_created(event)
            case "customer.subscription.updated":
                await handle_subscription_updated(event)
            case "customer.subscription.deleted":
                await handle_subscription_updated(event)
            case _:
                logger.warning(f"Unhandled event type: {event.type}")
    except Exception as e:
        logger.error(f"Error processing webhook event: {str(e)}")
        raise

async def handle_checkout_completed(event: WebhookEvent) -> None:
    """Handle successful checkout completion"""
    try:
        logger.info(f"Handling checkout.session.completed for session ID: {event.data['object']['id']}")
        logger.debug(f"Session metadata: {event.data['object']['metadata']}")
        logger.debug(f"Session data: {event.data['object']}")
        
        # Get stripe checkout session ID
        session_id = event.data['object']['id']

        # Update checkout session status in Supabase & get supabase checkout session record
        supabase_checkout_response = io_db.update_checkout_session(
            session_id=event.data['object']['id'],
            status=event.data['object']['status'],
            metadata=event.data['object']['metadata'],
        )

        logger.info(f"Updated checkout session status to {event.data['object']['status']} for session ID: {event.data['object']['id']}")

        # get supabase subscription record
        subscription_id = event.data['object']['metadata']['subscription_id']
        logger.debug(f"Checkout session linked to subscription ID: {subscription_id}")
        
        # Get the checkout type to determine next steps
        checkout_type = event.data['object']['metadata']['checkout_type']

        line_items = [line_item for line_item in supabase_checkout_response['line_items']]

        pp.paid_processing(
            checkout_type, 
            subscription_id, 
            event.data,
            line_items
            )

        logger.info(f"Updated checkout session status to {event.data['object']['status']} for session ID: {event.data['object']['id']}")

    except Exception as e:
        logger.error(f"Error handling checkout.session.completed: {str(e)}")
        raise

async def handle_subscription_created(event: WebhookEvent) -> None:
    """Handle subscription creation"""
    try:
        logger.info(f"Handling customer.subscription.created for subscription ID: {event.data['object']['id']}")
        stripe_subscription = stripe.Subscription.retrieve(event.data['object']['id'])

        # get supabase subscription record
        subscription_id = stripe_subscription.metadata['subscription_id']
        stripe_subscription_id = stripe_subscription.id
        

        # Update STATUS & STRIPE_SUBSCRIPTION_ID in user_subscriptions table in supabase
        subscription = io_db.update_user_subscription(
            subscription_id=subscription_id,
            status="active",
            stripe_subscription_id=stripe_subscription_id
            )

        # Update subscription progress status to Active OR remove from subscription progress tracking???
        io_db.update_subscription_progress_admin(
            subscription_id=subscription_id, 
            status="active",
            )     

        logger.debug(f"Local subscription ID: {subscription_id} - linked to Stripe subscription ID: {stripe_subscription_id}\nUpdated status to active in user_subscription & subscription_progress tables.")
    except Exception as e:
        logger.error(f"Error handling customer.subscription.created: {str(e)}")
        raise

async def handle_subscription_updated(event: WebhookEvent) -> None:
    """Handle subscription updates"""
    try:
        logger.info(f"Handling customer.subscription.updated for subscription ID: {event.data['object']['id']}")
        logger.debug(f"Subscription data: {event.data['object']}")
        subscription = event.data['object']
        subscription_items = subscription['items']['data']
        subscription_item = subscription_items[0]

        # Update STATUS, LAST_PAYMENT_DATE, NEXT_PAYMENT_DATE, CANCELLED_AT in user_subscriptions table in supabase
        io_db.update_user_subscription(
            subscription_id=subscription.metadata['subscription_id'],
            status=subscription.status,
            last_payment_date=datetime.fromtimestamp(subscription_item.current_period_start),
            next_payment_date=datetime.fromtimestamp(subscription_item.current_period_end),
            cancelled_at=datetime.fromtimestamp(subscription.canceled_at) if subscription.canceled_at else None
        )

        # Check if subscription items have changed

        # get current subscription items for comparison
        current_items = io_db.get_subscription_items(subscription.metadata['subscription_id']) 

        logger.debug(f"Current subscription items for subscription ID {subscription.metadata['subscription_id']}: {current_items}")

        # Build new subscription items list
        new_products = io_db.get_products_by_stripe_product_ids(
            [item.price.product for item in subscription_items])
        
        # Add internal product IDs and get quantities from Stripe subscription items
        new_item_details = []
        for item in subscription_items:
            for product in new_products:
                if item.price.product == product['stripe_product_id']:
                    new_item_details.append({
                        'product_id': product['id'],
                        'quantity': item.quantity
                    })
                    break
        
        # Check if there are any differences between current and new items
        update_products = False

        for current_item in current_items:
            matched = False
            for new_item in new_item_details:
                if current_item['product_id'] == new_item['product_id'] and current_item['quantity'] == new_item['quantity']:
                    matched = True
                    break
            if not matched:
                update_products = True
                break

        if update_products:
            io_db.update_subscription_items(
                subscription_id=subscription.metadata['subscription_id'],
                new_items=new_item_details
            )
            logger.info(f"Updated subscription items for subscription {subscription.metadata['subscription_id']}")

        logger.info(f"Updated subscription {subscription.metadata['subscription_id']}")
        
    except Exception as e:
        logger.error(f"Error handling customer.subscription.updated: {str(e)}")
        raise