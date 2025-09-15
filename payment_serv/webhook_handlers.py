import logging
import stripe
from datetime import datetime
from models.payment_models import WebhookEvent
from supabase import Client
from product_serv import stripe_product_sync as sps
from ios.io_db import insert_user_subscription, update_user_subscription, update_checkout_session, insert_subscription_items
from user_serv.user_service import assign_subscription_address
from email_serv.email_processor import send_new_subscription_email, send_order_email_to_team

logger = logging.getLogger('uvicorn.error')

async def webhook_router(event: WebhookEvent, supabase: Client) -> None:
    """Route webhook events to appropriate handlers"""
    try:
        logger.info(f"Webhook event received in webhook_router(): {event.data}")
        if event.type == 'product.created':
            await sps.handle_product_created(event, supabase)
        elif event.type == 'product.updated':
            await sps.handle_product_updated(event, supabase)
        elif event.type == 'product.deleted':
            await sps.handle_product_deleted(event, supabase)
        elif event.type == 'price.created':
            await sps.handle_price_created(event, supabase)
        elif event.type == 'price.updated':
            await sps.handle_price_updated(event, supabase)
        elif event.type == "checkout.session.completed":
            await handle_checkout_completed(event, supabase)
        elif event.type == "customer.subscription.created":
            await handle_subscription_created(event, supabase)
        elif event.type == "customer.subscription.updated":
            await handle_subscription_updated(event, supabase)
        elif event.type == "customer.subscription.deleted":
            await handle_subscription_updated(event, supabase)
        else:
            logger.warning(f"Unhandled event type: {event.type}")
    except Exception as e:
        logger.error(f"Error processing webhook event: {str(e)}")
        raise

async def handle_checkout_completed(event: WebhookEvent, supabase: Client) -> None:
    """Handle successful checkout completion"""
    try:
        logger.info(f"Handling checkout.session.completed for session ID: {event.data['object']['id']}")
        logger.debug(f"Session metadata: {event.data['object']['metadata']}")
        
        # Get stripe checkout session ID
        session_id = event.data['object']['id']

        # Update checkout session status in Supabase & get supabase checkout session record
        supabase_checkout_response = update_checkout_session(
            supabase=supabase,
            session_id=event.data['object']['id'],
            status=event.data['object']['status'],
            metadata=event.data['object']['metadata'],
        )

        logger.info(f"Updated checkout session status to {event.data['object']['status']} for session ID: {event.data['object']['id']}")

        # get supabase subscription record
        subscription_id = supabase_checkout_response[0]['metadata']['subscription_id']
        logger.debug(f"Checkout session linked to subscription ID: {subscription_id}")

        # Get subscription items
        subscription_items_response = supabase.table('subscription_items')\
            .select('*')\
            .eq('subscription_id', subscription_id)\
            .execute()
        
        logger.debug(f"Subscription items: {subscription_items_response.data}")
        
        # Get product details for each subscription item
        product_details = []
        for item in subscription_items_response.data:
            product_response = supabase.table('product')\
                .select('*')\
                .eq('id', item['product_id'])\
                .execute()
                
            if product_response.data:
                product = product_response.data[0]
                product_details.append({
                    "subscription_id": subscription_id,
                    "item_name": product['name'],
                    "cost": f'{product['currency'].upper()} {product['price']:.2f}',
                    "quantity": item['quantity'],
                    "type": product['type']
                })
        
        logger.debug(f"Products in subscription: {product_details}")

        # get user email and first name
        customer_email = event.data['object']['customer_details']['email']
        customer_name = event.data['object']['customer_details']['name']
        
        
        # send confirmation email to customer

                # Send confirmation to customer
        send_new_subscription_email(customer_email, customer_name, product_details)
        
        # Send confirmation to team
        team_email_subject = f"New Subscription: {customer_email}"
        
        # send confirmation email to team
        send_order_email_to_team(
            subject=team_email_subject,
            customer_email=customer_email,
            customer_name=customer_name,
            items=product_details
        )
        

        logger.info(f"Updated checkout session status to {event.data['object']['status']} for session ID: {event.data['object']['id']}")

    except Exception as e:
        logger.error(f"Error handling checkout.session.completed: {str(e)}")
        raise

async def handle_subscription_created(webhook_event: WebhookEvent, supabase: Client) -> None:
    """Handle subscription creation"""
    try:
        logger.info(f"Handling customer.subscription.created for subscription ID: {webhook_event.data['object']['id']}")
        subscription = stripe.Subscription.retrieve(webhook_event.data['object']['id'])
        
        # logger.debug(f'Customer ID: {subscription.customer}') 
        # logger.debug(f'Subscription ID: {subscription.id}')
        # logger.debug(f'Subscription Created At: {datetime.fromtimestamp(subscription.created)}')
        # logger.debug(f'Subscription Metadata: {subscription.metadata}')
        # logger.debug(f'Subscription Items: {subscription["items"]["data"]}')

        # # Prepare and format metadata
        # user_id=subscription.metadata['user_id'] if subscription.metadata and 'user_id' in subscription.metadata else None
        # address_id=subscription.metadata['address_id'] if subscription.metadata and 'address_id' in subscription.metadata else None
        # baby_dob=datetime.strptime(subscription.metadata['baby_dob'], '%Y-%m-%d') if subscription.metadata and 'baby_dob' in subscription.metadata else None
        # baby_weight=float(subscription.metadata['baby_weight']) if subscription.metadata and 'baby_weight' in subscription.metadata else None

        # logger.debug(f"SUBCRIPTION CREATED - User ID: {user_id}")
        # logger.debug(f"SUBCRIPTION CREATED - Address ID: {address_id}")
        # logger.debug(f"Parsed baby_dob: {baby_dob}")
        # logger.debug(f"Parsed baby_weight: {baby_weight}")

        # # Create subscription record
        # subscription_response = insert_user_subscription(
        #     supabase=supabase,
        #     customer_id=subscription.customer,
        #     stripe_subscription_id=subscription.id,
        #     status=subscription.status,
        #     address_id=address_id,
        #     subscribed_at=datetime.fromtimestamp(subscription.created),
        #     last_payment_date=datetime.fromtimestamp(subscription['items']['data'][0]['current_period_start']),
        #     next_payment_date=datetime.fromtimestamp(subscription['items']['data'][0]['current_period_end']),
        #     baby_dob=baby_dob,
        #     baby_weight_at_start=baby_weight,
        # )

        # # Get the subscription items for inserting into db & formatting confirmation email
        # subscription_items = []
        # for item in subscription['items']['data']:
        #     stripe_price_id = item['price']['id']
        #     price = stripe.Price.retrieve(stripe_price_id)
        #     logger.debug(f"Price details: {price}")

        #     # Get the supabase product ID
        #     product_id_response = supabase.table('product').select('id').eq('stripe_price_id', stripe_price_id).execute()
        #     logger.debug(f"Product ID details from Supabase: {product_id_response.data[0]['id']}")

        #     product_id = product_id_response.data[0]['id']

        #     # Quantity
        #     quantity = item['quantity']

        #     # Get product name
        #     product = stripe.Product.retrieve(price['product'])
        #     product_name = product['name']

        #     # Format the cost
        #     unit_amount = price['unit_amount'] # Convert to dollars if the amount is in cents 
        #     unit_price = unit_amount / 100.0 # Get the currency 
        #     currency = price['currency']

        #     item_details = {
        #         "subscription_id": subscription_response['id'],
        #         "item_name": product_name,
        #         "cost": f'{currency.upper()} {unit_price:.2f}',
        #         "product_id": product_id,
        #         "quantity": quantity
        #     }

        #     subscription_items.append(item_details)

        # insert_subscription_items(supabase, subscription_items)

        # logger.info(f"Created subscription for user {subscription.customer}")

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

        # Send confirmation to customer
        send_new_subscription_email(user_email, first_name, subscription_items)

        # Send confirmation to team
        team_email_subject = f"New Subscription: {user_email}"

        send_order_email_to_team(
            subject=team_email_subject,
            customer_email=user_email,
            customer_name=first_name,
            items=subscription_items
        )
        logger.info(f"Sent subscription confirmation email to {user_email}")
        
    except Exception as e:
        logger.error(f"Error handling customer.subscription.created: {str(e)}")
        raise

async def handle_subscription_updated(event: WebhookEvent, supabase: Client) -> None:
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