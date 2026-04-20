import logging
from typing import Optional

from config.supabase import get_supabase

logger = logging.getLogger('uvicorn.error')

supabase = get_supabase()


def insert_checkout_session(
    session_id: str,
    user_id: str,
    customer_id: str,
    line_items: list[dict],
    status: str = "pending",
    metadata: Optional[dict] = None
) -> dict:
    """Insert a new checkout session into the database."""
    try:
        logger.debug(f"insert_checkout_session(): Inserting session with ID {session_id} for user {user_id}")

        response = supabase.table('checkout_sessions').insert({
            "session_id": session_id,
            "user_id": user_id,
            "customer_id": customer_id,
            "line_items": line_items,
            "status": status,
            "metadata": metadata
        }).execute()

        logger.debug(f"insert_checkout_session(): Inserted data: {response.data}")

        return response.data[0] if response.data else None

    except Exception as e:
        logger.error(f"insert_checkout_session(): Failed to store checkout session: {str(e)}")
        raise


def update_checkout_session(
    session_id: str,
    status: str,
    metadata: Optional[dict] = None
) -> dict:
    """Update an existing checkout session."""
    try:
        logger.debug(f"update_checkout_session(): Updating session with ID {session_id} to status {status}")

        response = supabase.table('checkout_sessions').update({
            "status": status,
            "metadata": metadata
        }).eq("session_id", session_id).execute()

        logger.debug(f"update_checkout_session(): Updated data: {response.data}")

        return response.data[0]

    except Exception as e:
        logger.error(f"update_checkout_session(): Failed to update checkout session: {str(e)}")
        raise
