import logging
from datetime import datetime

import stripe

from models.payment_models import WebhookEvent
from payment_serv import payment_processor as pp
from product_serv import stripe_product_sync as sps
from repositories.payment_repository import update_checkout_session
from repositories.product_repository import get_products_by_stripe_product_ids
from repositories.subscription_repository import (
    get_subscription_items,
    update_subscription_items,
    update_subscription_progress_admin,
    update_user_subscription,
)

logger = logging.getLogger('uvicorn.error')


async def webhook_router(event: WebhookEvent) -> None:
    """Route webhook events to appropriate handlers."""
    try:
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
            case "payment_intent.payment_failed":
                logger.warning(f"webhook_router(): Payment failed: {event.data}")
            case _:
                logger.warning(f"webhook_router(): Unhandled event type: {event.type}")
    except Exception as e:
        logger.error(f"webhook_router(): Error processing webhook event: {str(e)}")
        raise


async def handle_checkout_completed(event: WebhookEvent) -> None:
    """Handle successful checkout completion."""
    try:
        logger.info(f"handle_checkout_completed(): Handling checkout.session.completed for session ID: {event.data['object']['id']}")
        logger.debug(f"handle_checkout_completed(): Session metadata: {event.data['object']['metadata']}")

        supabase_checkout_response = update_checkout_session(
            session_id=event.data['object']['id'],
            status=event.data['object']['status'],
            metadata=event.data['object']['metadata'],
        )

        logger.info(f"handle_checkout_completed(): Updated checkout session status to {event.data['object']['status']}")

        metadata = event.data['object'].get('metadata') or {}
        checkout_type = metadata.get('checkout_type')
        subscription_id = metadata.get('subscription_id')
        order_id = metadata.get('order_id')
        line_items = [line_item for line_item in supabase_checkout_response['line_items']]

        pp.paid_processing(
            checkout_type=checkout_type,
            event_data=event.data,
            line_items=line_items,
            subscription_id=subscription_id,
            order_id=order_id,
        )

    except Exception as e:
        logger.error(f"handle_checkout_completed(): Error: {str(e)}")
        raise


async def handle_subscription_created(event: WebhookEvent) -> None:
    """Handle subscription creation."""
    try:
        logger.info(f"handle_subscription_created(): Handling customer.subscription.created for subscription ID: {event.data['object']['id']}")
        stripe_subscription = stripe.Subscription.retrieve(event.data['object']['id'])

        subscription_id = stripe_subscription.metadata['subscription_id']
        stripe_subscription_id = stripe_subscription.id

        update_user_subscription(
            subscription_id=subscription_id,
            status="active",
            stripe_subscription_id=stripe_subscription_id
        )

        update_subscription_progress_admin(
            subscription_id=subscription_id,
            status="active",
        )

        logger.debug(f"handle_subscription_created(): Local subscription ID: {subscription_id} - linked to Stripe subscription ID: {stripe_subscription_id}. Updated status to active.")
    except Exception as e:
        logger.error(f"handle_subscription_created(): Error: {str(e)}")
        raise


async def handle_subscription_updated(event: WebhookEvent) -> None:
    """Handle subscription updates."""
    try:
        logger.info(f"handle_subscription_updated(): Handling customer.subscription.updated for subscription ID: {event.data['object']['id']}")
        subscription = event.data['object']
        subscription_items = subscription['items']['data']
        subscription_item = subscription_items[0]

        update_user_subscription(
            subscription_id=subscription.metadata['subscription_id'],
            status=subscription.status,
            last_payment_date=datetime.fromtimestamp(subscription_item.current_period_start),
            next_payment_date=datetime.fromtimestamp(subscription_item.current_period_end),
            cancelled_at=datetime.fromtimestamp(subscription.canceled_at) if subscription.canceled_at else None
        )

        current_items = get_subscription_items(subscription.metadata['subscription_id'])

        new_products = get_products_by_stripe_product_ids(
            [item.price.product for item in subscription_items])

        new_item_details = []
        for item in subscription_items:
            for product in new_products:
                if item.price.product == product['stripe_product_id']:
                    new_item_details.append({
                        'product_id': product['id'],
                        'quantity': item.quantity
                    })
                    break

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
            update_subscription_items(
                subscription_id=subscription.metadata['subscription_id'],
                new_items=new_item_details
            )
            logger.info(f"handle_subscription_updated(): Updated subscription items for subscription {subscription.metadata['subscription_id']}")

        logger.info(f"handle_subscription_updated(): Updated subscription {subscription.metadata['subscription_id']}")

    except Exception as e:
        logger.error(f"handle_subscription_updated(): Error: {str(e)}")
        raise
