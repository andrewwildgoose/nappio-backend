import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
from dotenv import load_dotenv

import stripe
from gotrue import User

from config.supabase import get_supabase
from email_serv import email_processor
from models.payment_models import CheckoutSessionResponse, PaymentDetailsResponse
from payment_serv import voucher_service
from repositories.payment_repository import insert_checkout_session
from repositories.product_repository import get_product_by_stripe_price_id
from repositories.subscription_repository import (
    get_subscription_address,
    update_subscription_progress_admin,
    update_user_subscription,
)
from repositories.user_repository import get_user_by_subscription_id
from repositories.voucher_repository import get_voucher_by_subscription_id, update_voucher_status

logger = logging.getLogger('uvicorn.error')

load_dotenv()

supabase = get_supabase()


def get_or_create_customer(email: str) -> stripe.Customer:
    """
    Check if a customer exists in Stripe by email, and either:
    - Return the existing customer if found
    - Create a new customer if not found
    """
    customers = stripe.Customer.list(email=email, limit=1)

    if customers and len(customers.data) > 0:
        existing_customer = customers.data[0]
        logger.debug(f"get_or_create_customer(): Found existing customer: {existing_customer.id}")
        return existing_customer

    new_customer = stripe.Customer.create(email=email)
    logger.debug(f"get_or_create_customer(): Created new customer: {new_customer.id}")
    return new_customer


def create_stripe_checkout_session(
        line_items: list[dict],
        user: User,
        frontend_url: str,
        cancel_url: str,
        metadata: Optional[dict] = None,
        coupon_id: Optional[str] = None
    ) -> CheckoutSessionResponse:
    """Creates a Stripe one-off payment checkout session."""
    try:
        logger.info(f"create_stripe_checkout_session(): Creating checkout session for user {user.id} with line items {line_items}")

        stripe_customer = get_or_create_customer(email=user.email)

        session_args = {
            "customer": stripe_customer.id,
            "line_items": line_items,
            "mode": "payment",
            "success_url": f"{frontend_url}/success?session_id={{CHECKOUT_SESSION_ID}}",
            "cancel_url": f"{frontend_url}{cancel_url}",
            "allow_promotion_codes": True,
            "metadata": metadata,
            "saved_payment_method_options": {
                "payment_method_save": "enabled"
            }
        }
        if coupon_id:
            session_args.pop("allow_promotion_codes", None)
            session_args["discounts"] = [{"coupon": coupon_id}]

        session = stripe.checkout.Session.create(**session_args)

        logger.info(f"create_stripe_checkout_session(): Checkout session created with ID {session.id}")

        insert_checkout_session(
            session_id=session.id,
            user_id=user.id,
            customer_id=session.customer,
            line_items=line_items,
            metadata=metadata
        )

        logger.info(f"create_stripe_checkout_session(): Checkout session stored in Supabase for user {user.id} with session ID {session.id}")

        return {
            "checkout_url": session.url,
            "session_id": session.id,
            "metadata": metadata
        }

    except stripe.error.StripeError as e:
        logger.error(f"create_stripe_checkout_session(): Stripe error: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"create_stripe_checkout_session(): Error: {str(e)}")
        raise


def create_stripe_subscription_checkout_session(
        line_items: list[dict],
        user: User,
        frontend_url: str,
        cancel_url: str,
        billing_anchor: datetime,
        metadata: Optional[dict] = None
    ) -> CheckoutSessionResponse:
    """Creates a Stripe subscription checkout session."""
    try:
        logger.info(f"create_stripe_subscription_checkout_session(): Creating subscription checkout session for user {user.id}")

        stripe_customer = get_or_create_customer(email=user.email)

        logger.debug("create_stripe_subscription_checkout_session(): Resolving billing cycle anchor timezone")

        if billing_anchor.tzinfo is None:
            billing_anchor = billing_anchor.replace(tzinfo=timezone.utc)
        else:
            billing_anchor = billing_anchor.astimezone(timezone.utc)

        current_time = datetime.now(timezone.utc)
        min_billing_cycle_anchor_time = current_time + timedelta(hours=48)

        logger.debug(
            "create_stripe_subscription_checkout_session(): Anchor decision inputs - "
            f"billing_anchor={billing_anchor.isoformat()}, "
            f"current_time={current_time.isoformat()}, "
            f"min_billing_cycle_anchor_time={min_billing_cycle_anchor_time.isoformat()}"
        )

        if billing_anchor >= min_billing_cycle_anchor_time:
            logger.debug(
                "create_stripe_subscription_checkout_session(): Using billing_cycle_anchor "
                f"because billing_anchor is at least 48h ahead. billing_anchor={billing_anchor.isoformat()}"
            )
            subscription_data = {
                'billing_cycle_anchor': int(billing_anchor.timestamp()),
                'metadata': metadata or {}
            }
        else:
            logger.debug(
                "create_stripe_subscription_checkout_session(): Using immediate-start subscription_data "
                f"because billing_anchor is less than 48h ahead. billing_anchor={billing_anchor.isoformat()}, "
                f"min_billing_cycle_anchor_time={min_billing_cycle_anchor_time.isoformat()}"
            )
            subscription_data = {
                'metadata': metadata or {}
            }

        logger.debug(
            "create_stripe_subscription_checkout_session(): Final subscription_data keys="
            f"{list(subscription_data.keys())}, values={subscription_data}"
        )

        session = stripe.checkout.Session.create(
            customer=stripe_customer.id,
            line_items=line_items,
            mode="subscription",
            subscription_data=subscription_data,
            success_url=f"{frontend_url}/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{frontend_url}{cancel_url}",
            allow_promotion_codes=True,
            metadata=metadata
        )

        logger.info(f"create_stripe_subscription_checkout_session(): Checkout session created with ID {session.id}")

        insert_checkout_session(
            session_id=session.id,
            user_id=user.id,
            customer_id=session.customer,
            line_items=line_items,
        )

        logger.info(f"create_stripe_subscription_checkout_session(): Checkout session stored in Supabase for user {user.id}")

        return CheckoutSessionResponse(
            checkout_url=session.url,
            session_id=session.id
        )

    except stripe.error.StripeError as e:
        logger.error(f"create_stripe_subscription_checkout_session(): Stripe error: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"create_stripe_subscription_checkout_session(): Error: {str(e)}")
        raise


def get_payment_completed_details(session_id: str) -> PaymentDetailsResponse:
    """Fetch payment details from a completed checkout session."""
    try:
        logger.info(f"get_payment_completed_details(): Fetching payment details for session ID {session_id}")

        session = stripe.checkout.Session.retrieve(session_id)

        logger.info(f"get_payment_completed_details(): Session details fetched for session ID {session_id}")

        return PaymentDetailsResponse(
            amount_total=session['amount_total'],
            customer_email=session.customer_details.email,
            checkout_type=session.metadata.get('checkout_type', 'unknown')
        )

    except Exception as e:
        logger.error(f"get_payment_completed_details(): Error: {str(e)}")
        raise


def paid_processing(checkout_type: str, subscription_id: str, event_data: dict, line_items: list) -> None:
    """Route payment processing based on checkout type."""
    try:
        logger.info(f"paid_processing(): Processing payment for checkout type: {checkout_type}")
        match checkout_type:
            case "start_up":
                startup_costs_paid_processing(subscription_id, event_data, line_items)
            case "subscription":
                subscription_paid_processing(subscription_id, event_data)
            case _:
                logger.warning(f"paid_processing(): Unknown checkout type: {checkout_type}")
                raise ValueError(f"Unknown checkout type: {checkout_type}")
    except Exception as e:
        logger.error(f"paid_processing(): Error processing payment for checkout type {checkout_type}: {str(e)}")
        raise


def startup_costs_paid_processing(subscription_id: str, event_data: dict, line_items: list) -> None:
    """Process startup costs payment: update subscription status and notify customer."""
    try:
        logger.info("startup_costs_paid_processing(): Processing startup costs payment")

        update_user_subscription(
            subscription_id=subscription_id,
            customer_id=event_data['object']['customer'],
        )

        update_subscription_progress_admin(
            subscription_id=subscription_id,
            status="setup_paid"
        )

        subscription_items_response = supabase.table('subscription_items')\
            .select('*')\
            .eq('subscription_id', subscription_id)\
            .execute()

        logger.debug(f"startup_costs_paid_processing(): Subscription items: {subscription_items_response.data}")

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
                    "cost": f'{product["currency"].upper()} {product["price"] / 100:.2f}',
                    "quantity": item['quantity'],
                    "type": product['type']
                })

        for item in line_items:
            product = get_product_by_stripe_price_id(item['price'])
            product_details.append({
                "subscription_id": subscription_id,
                "item_name": product['name'],
                "cost": f'{product["currency"].upper()} {product["price"] / 100:.2f}',
                "quantity": item['quantity'],
                "type": product['type']
            })

        logger.debug(f"startup_costs_paid_processing(): Products in subscription: {product_details}")

        user = get_user_by_subscription_id(subscription_id)
        customer_name = user.get("user_metadata", {}).get("first_name")
        customer_email = user.get("email")

        voucher = get_voucher_by_subscription_id(subscription_id)
        voucher_info = None
        if voucher:
            voucher_info = {
                "code": voucher["code"],
                "postcode": voucher["postcode"],
                "type": voucher["type"],
                "status": voucher["status"],
            }
            try:
                amount_total = event_data['object'].get('amount_total', 0)
                amount = f"{amount_total / 100:.2f}"
                voucher_service.redeem_voucher(
                    voucher_code=voucher["code"],
                    postcode=voucher["postcode"],
                    amount_gbp=amount,
                    supplier_reference=event_data['object']['id'],
                    surname=user.get("user_metadata", {}).get("surname"),
                )
                updated_voucher = update_voucher_status(voucher["code"], "redeemed")
                if updated_voucher:
                    voucher_info["status"] = updated_voucher["status"]
            except voucher_service.VoucherServiceError:
                updated_voucher = update_voucher_status(voucher["code"], "manual-review")
                if updated_voucher:
                    voucher_info["status"] = updated_voucher["status"]

        email_processor.send_new_subscription_email(customer_email, customer_name, product_details, voucher_info=voucher_info)

        team_email_subject = f"New Subscription: {customer_email}"
        subscription_address_res = get_subscription_address(subscription_id)
        email_processor.send_order_email_to_team(
            subject=team_email_subject,
            customer_email=customer_email,
            customer_name=customer_name,
            customer_address=subscription_address_res,
            items=product_details,
            voucher_info=voucher_info
        )

    except Exception as e:
        logger.error(f"startup_costs_paid_processing(): Error: {str(e)}")
        raise


def subscription_paid_processing(subscription_id: str, event_data: dict):
    """Process a subscription payment: update records and notify customer."""
    try:
        user = get_user_by_subscription_id(subscription_id)
        customer_name = user.get("user_metadata", {}).get("first_name")
        customer_email = user.get("email")

        subscription_items_response = supabase.table('subscription_items')\
            .select('*')\
            .eq('subscription_id', subscription_id)\
            .execute()

        logger.debug(f"subscription_paid_processing(): Subscription items: {subscription_items_response.data}")

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
                    "cost": f'{product["currency"].upper()} {product["price"] / 100:.2f}',
                    "quantity": item['quantity'],
                    "type": product['type']
                })

        logger.debug(f"subscription_paid_processing(): Products in subscription: {product_details}")

        email_processor.send_subscription_payment_active_email(
            to_email=customer_email,
            first_name=customer_name,
            subscription_items=product_details
        )

        logger.info("subscription_paid_processing(): Sending notification email to team")
        email_processor.send_subscription_payment_active_to_team(
            customer_email=customer_email,
            customer_name=customer_name,
            items=product_details
        )

    except Exception as e:
        logger.error(f"subscription_paid_processing(): Error: {str(e)}")
        raise


def pause_subscription(subscription_id: str, stripe_subscription_id: str, pause_until: Optional[datetime] = None) -> None:
    """Pause a Stripe subscription."""
    try:
        logger.info(f"pause_subscription(): Pausing subscription {subscription_id}")
        stripe.Subscription.modify(
            stripe_subscription_id,
            pause_collection={
                'behavior': 'void',
                'resumes_at': int(pause_until.timestamp()) if pause_until else None
            }
        )
        logger.info(f"pause_subscription(): Subscription {subscription_id} paused successfully")
    except Exception as e:
        logger.error(f"pause_subscription(): Error pausing subscription {subscription_id}: {str(e)}")
        raise
