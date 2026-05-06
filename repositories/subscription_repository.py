import logging
from datetime import datetime
from typing import Optional
from uuid import UUID

from config.supabase import get_supabase
from models.admin_models import SubscriptionDashboardResponse

logger = logging.getLogger('uvicorn.error')

supabase = get_supabase()


def insert_user_subscription(
    status: str,
    user_id: str,
    customer_id: Optional[str] = None,
    stripe_subscription_id: Optional[str] = None,
    address_id: Optional[UUID] = None,
    baby_dob: Optional[datetime] = None,
    baby_weight_at_start: Optional[float] = None,
    subscribed_at: Optional[datetime] = None,
    last_payment_date: Optional[datetime] = None,
    next_payment_date: Optional[datetime] = None,
) -> dict:
    """Insert a new user subscription into the database."""
    try:
        subscription_data = {
            "status": status,
            "user_id": user_id
        }
        if customer_id:
            subscription_data["customer_id"] = customer_id
        if stripe_subscription_id:
            subscription_data["stripe_subscription_id"] = stripe_subscription_id
        if subscribed_at:
            subscription_data["subscribed_at"] = subscribed_at.isoformat()
        if last_payment_date:
            subscription_data["last_payment_date"] = last_payment_date.isoformat()
        if next_payment_date:
            subscription_data["next_payment_date"] = next_payment_date.isoformat()
        if address_id:
            subscription_data["address_id"] = str(address_id)
        if baby_dob:
            subscription_data["baby_dob"] = baby_dob.isoformat()
        if baby_weight_at_start is not None:
            subscription_data["baby_weight_at_start"] = baby_weight_at_start

        response = supabase.table('user_subscriptions').insert(subscription_data).execute()

        logger.debug(f"insert_user_subscription(): Inserted data: {response.data}")

        if not response.data:
            raise Exception("No data returned from subscription insert")

        return response.data[0]

    except Exception as e:
        logger.error(f"insert_user_subscription(): Failed to store subscription: {str(e)}")
        raise


def update_user_subscription(
    subscription_id: str,
    status: Optional[str] = None,
    user_id: Optional[str] = None,
    customer_id: Optional[str] = None,
    stripe_subscription_id: Optional[str] = None,
    address_id: Optional[UUID] = None,
    baby_dob: Optional[datetime] = None,
    baby_weight_at_start: Optional[float] = None,
    subscribed_at: Optional[datetime] = None,
    last_payment_date: Optional[datetime] = None,
    next_payment_date: Optional[datetime] = None,
    cancelled_at: Optional[datetime] = None
) -> dict | None:
    """Update an existing user subscription."""
    try:
        logger.debug(f"update_user_subscription(): Updating subscription {subscription_id}")

        data = {}
        if status is not None:
            data["status"] = status
        if user_id is not None:
            data["user_id"] = user_id
        if customer_id is not None:
            data["customer_id"] = customer_id
        if stripe_subscription_id is not None:
            data["stripe_subscription_id"] = stripe_subscription_id
        if subscribed_at is not None:
            data["subscribed_at"] = subscribed_at.isoformat()
        if last_payment_date is not None:
            data["last_payment_date"] = last_payment_date.isoformat()
        if next_payment_date is not None:
            data["next_payment_date"] = next_payment_date.isoformat()
        if cancelled_at is not None:
            data["cancelled_at"] = cancelled_at.isoformat()
        if address_id is not None:
            data["address_id"] = str(address_id)
        if baby_dob is not None:
            data["baby_dob"] = baby_dob.isoformat()
        if baby_weight_at_start is not None:
            data["baby_weight_at_start"] = baby_weight_at_start

        if not data:
            logger.warning("update_user_subscription(): No fields provided to update")
            return None

        response = supabase.table('user_subscriptions').update(data).eq("id", subscription_id).execute()

        if "status" in data:
            update_subscription_progress_admin(
                subscription_id,
                status=data["status"]
            )

        logger.debug(f"update_user_subscription(): Updated data: {response.data}")

        return response.data[0] if response.data else None

    except Exception as e:
        logger.error(f"update_user_subscription(): Failed to update subscription: {str(e)}")
        raise


def get_subscription_by_id(subscription_id: str) -> dict | None:
    """Retrieve a subscription by its ID."""
    try:
        logger.debug(f"get_subscription_by_id(): Retrieving subscription with ID {subscription_id}")

        response = supabase.table('user_subscriptions').select('*').eq('id', subscription_id).execute()
        if response.data:
            return response.data[0]
        return None
    except Exception as e:
        logger.error(f"get_subscription_by_id(): Error retrieving subscription with ID {subscription_id}: {str(e)}")
        raise Exception(f"Error retrieving subscription with ID {subscription_id}: {str(e)}")


def get_user_subscriptions(user_id: str):
    """Retrieve all subscriptions for a given user ID."""
    try:
        logger.debug(f"get_user_subscriptions(): Retrieving subscriptions for user ID {user_id}")

        response = supabase.table('user_subscriptions').select('*').eq('user_id', user_id).execute()

        if response.data:
            logger.info(f"get_user_subscriptions(): Found {len(response.data)} subscriptions for user ID {user_id}")
        else:
            logger.warning(f"get_user_subscriptions(): No subscriptions found for user ID {user_id}")

        return response.data if response.data else []
    except Exception as e:
        logger.error(f"get_user_subscriptions(): Error retrieving subscriptions for user ID {user_id}: {str(e)}")
        raise Exception(f"Error retrieving subscriptions for user ID {user_id}: {str(e)}")


def insert_subscription_items(subscription_items: list[dict]):
    """Insert subscription items into the database."""
    try:
        for item in subscription_items:
            subscription_item = {
                "subscription_id": item["subscription_id"],
                "product_id": item["product_id"],
                "quantity": item["quantity"]
            }
            logger.debug(f"insert_subscription_items(): Inserting subscription item: {subscription_item}")
            response = supabase.table('subscription_items').insert(subscription_item).execute()
            logger.debug(f"insert_subscription_items(): Inserted data: {response.data}")

        return response

    except Exception as e:
        logger.error(f"insert_subscription_items(): Failed to store subscription items: {str(e)}")
        raise


def get_subscription_items(subscription_id: str) -> list[dict]:
    """Retrieve subscription items for a given subscription ID."""
    try:
        response = supabase.table('subscription_items')\
            .select("*")\
            .eq("subscription_id", subscription_id)\
            .execute()

        logger.debug(f"get_subscription_items(): Retrieved data: {response.data}")
        return response.data
    except Exception as e:
        logger.error(f"get_subscription_items(): Failed to retrieve subscription items: {str(e)}")
        raise


def update_subscription_items(subscription_id: str, new_items: list[dict]) -> None:
    """Update subscription items by replacing existing items with new ones."""
    try:
        delete_response = supabase.table('subscription_items')\
            .delete()\
            .eq("subscription_id", subscription_id)\
            .execute()

        logger.debug(f"update_subscription_items(): Deleted existing items for subscription ID {subscription_id}: {delete_response.data}")

        for item in new_items:
            subscription_item = {
                "subscription_id": subscription_id,
                "product_id": item["product_id"],
                "quantity": item["quantity"]
            }
            logger.debug(f"update_subscription_items(): Inserting new subscription item: {subscription_item}")
            insert_response = supabase.table('subscription_items').insert(subscription_item).execute()
            logger.debug(f"update_subscription_items(): Inserted data: {insert_response.data}")

    except Exception as e:
        logger.error(f"update_subscription_items(): Failed to update subscription items: {str(e)}")
        raise


def insert_subscription_progress(subscription_id: str, status: str) -> dict:
    """Insert a new subscription progress record into the database."""
    try:
        response = supabase.table('subscription_progress').insert({
            "subscription_id": subscription_id,
            "status": status
        }).execute()

        logger.debug(f"insert_subscription_progress(): Inserted data: {response}")

        return response.data[0] if response.data else None

    except Exception as e:
        logger.error(f"insert_subscription_progress(): Failed to insert subscription progress: {str(e)}")
        raise


def update_subscription_progress_admin(
    subscription_id: str,
    status: Optional[str] = None,
    meeting_date: Optional[datetime] = None,
) -> None:
    """Update the progress record for a given subscription_id."""
    try:
        update_data = {}
        if status is not None:
            update_data["status"] = status
        if meeting_date is not None:
            if isinstance(meeting_date, datetime):
                update_data["meeting_date"] = meeting_date.isoformat()
            else:
                update_data["meeting_date"] = meeting_date
        if not update_data:
            return

        response = supabase.table('subscription_progress').update(update_data).eq('subscription_id', subscription_id).execute()
        if hasattr(response, "error") and response.error:
            logger.error(f"update_subscription_progress_admin(): Supabase error: {response.error}")
            raise RuntimeError(f"Supabase error: {response.error}")
        logger.info(f"update_subscription_progress_admin(): Updated progress for subscription_id {subscription_id}")
    except Exception as e:
        logger.error(f"update_subscription_progress_admin(): Error updating progress: {str(e)}")
        raise


def get_subscription_progress(subscription_id: str) -> dict | None:
    """Retrieve the subscription progress record for a given subscription ID."""
    try:
        response = supabase.table('subscription_progress').select('*').eq('subscription_id', subscription_id).execute()
        logger.debug(f"get_subscription_progress(): Retrieved progress for subscription {subscription_id}: {response.data}")

        return response.data[0] if response.data else None
    except Exception as e:
        logger.error(f"get_subscription_progress(): Error fetching progress for subscription {subscription_id}: {str(e)}")
        raise


def get_all_subscription_progress(auth_supabase) -> list[SubscriptionDashboardResponse]:
    """Retrieve all subscription progress records joined with user subscription data and user information."""
    try:
        progress_response = supabase.table('subscription_progress').select(
            """
            subscription_id,
            status,
            meeting_date,
            last_updated,
            user_subscriptions!inner (
                id,
                user_id,
                status,
                subscribed_at,
                cancelled_at,
                last_payment_date,
                next_payment_date,
                baby_dob,
                baby_weight_at_start
            )
            """
        ).execute()

        if hasattr(progress_response, "error") and progress_response.error:
            logger.error("Supabase error fetching subscription_progress: %s", progress_response.error)
            raise RuntimeError(f"Supabase error: {progress_response.error}")

        user_ids = set()
        for record in progress_response.data:
            subscription = record.get("user_subscriptions")
            if subscription and subscription.get("user_id"):
                user_ids.add(subscription["user_id"])

        if not user_ids:
            logger.debug("No user IDs found in subscriptions")
            return []

        users_response = auth_supabase.auth.admin.list_users()
        users = users_response.users if hasattr(users_response, "users") else users_response

        user_map = {}
        for user in users:
            user_id = getattr(user, "id", None)
            if user_id:
                user_map[user_id] = user

        result = []
        for record in progress_response.data:
            subscription = record.get("user_subscriptions", {})
            user_id = subscription.get("user_id")
            user = user_map.get(user_id)

            customer_name = "Unknown"
            customer_email = None

            if user:
                meta = getattr(user, "user_metadata", {}) or {}
                first = meta.get("first_name", "") or meta.get("firstName", "")
                last = meta.get("surname", "") or meta.get("lastName", "")
                customer_name = f"{first} {last}".strip() or "Unknown"
                customer_email = getattr(user, "email", None) or meta.get("email")

            result.append(SubscriptionDashboardResponse(
                subscription_id=record.get("subscription_id"),
                user_id=user_id,
                customer_name=customer_name,
                customer_email=customer_email,
                subscription_status=subscription.get("status"),
                progress_status=record.get("status"),
                meeting_date=record.get("meeting_date"),
                subscribed_at=subscription.get("subscribed_at"),
                cancelled_at=subscription.get("cancelled_at"),
                last_payment_date=subscription.get("last_payment_date"),
                next_payment_date=subscription.get("next_payment_date"),
                baby_dob=subscription.get("baby_dob"),
                baby_weight_at_start=subscription.get("baby_weight_at_start"),
                last_updated=record.get("last_updated"),
            ))

        logger.debug(f"get_all_subscription_progress(): Returning {len(result)} dashboard records")
        return result

    except Exception as e:
        logger.error(f"get_all_subscription_progress(): Error fetching subscription progress records: {str(e)}")
        raise


def get_subscription_address(subscription_id: str) -> Optional[dict]:
    """Retrieve the address associated with a subscription ID."""
    try:
        response = supabase.table('user_subscriptions').select('address_id').eq('id', subscription_id).execute()
        logger.debug(f"get_subscription_address(): Retrieved address for subscription {subscription_id}: {response.data}")

        if response.data and len(response.data) > 0:
            address_id = response.data[0].get('address_id')
            address_response = supabase.table('user_addresses').select('*').eq('id', address_id).execute()
            if address_response.data and len(address_response.data) > 0:
                return address_response.data[0]
            else:
                logger.warning(f"get_subscription_address(): No address found with ID {address_id}")
                return None
        else:
            logger.warning(f"get_subscription_address(): No subscription found with ID {subscription_id}")
            return None
    except Exception as e:
        logger.error(f"get_subscription_address(): Error fetching address for subscription {subscription_id}: {str(e)}")
        raise
