import logging
from datetime import datetime

import ios.io_db as io_db

logger = logging.getLogger('uvicorn.error')
logger.setLevel(logging.DEBUG)

def get_meeting_date(subscription_id: str) -> datetime | None:
    """
    Retrieve the meeting date for a given subscription ID from the database.
    
    Args:
        subscription_id: The ID of the subscription to look up.

    Returns:
        datetime: The meeting date as a datetime object, or None if not found.
    """
    try:
        subscription_progress = io_db.get_subscription_progress(subscription_id)
        logger.debug(f"Retrieved subscription progress for subscription {subscription_id}: {subscription_progress}")

        meeting_date = subscription_progress.get('meeting_date')

        if meeting_date:
            logger.debug(f"Raw meeting_date string: {meeting_date}")
            parsed_datetime = datetime.fromisoformat(meeting_date.replace('Z', '+00:00'))
            logger.debug(f"Parsed datetime: {parsed_datetime}")
            logger.debug(f"Year: {parsed_datetime.year}, Month: {parsed_datetime.month}, Day: {parsed_datetime.day}")
            return parsed_datetime
        else:
            return None
    except Exception as e:
        logger.error(f"Error retrieving meeting date for subscription {subscription_id}: {str(e)}")
        raise