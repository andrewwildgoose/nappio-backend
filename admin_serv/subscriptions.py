import logging
from datetime import datetime

from repositories.subscription_repository import get_subscription_progress

logger = logging.getLogger('uvicorn.error')
logger.setLevel(logging.DEBUG)


def get_meeting_date(subscription_id: str) -> datetime | None:
    """
    Retrieve the meeting date for a given subscription ID from the database.
    """
    try:
        subscription_progress = get_subscription_progress(subscription_id)
        logger.debug(f"get_meeting_date(): Retrieved subscription progress for subscription {subscription_id}: {subscription_progress}")

        meeting_date = subscription_progress.get('meeting_date')

        if meeting_date:
            logger.debug(f"get_meeting_date(): Raw meeting_date string: {meeting_date}")
            parsed_datetime = datetime.fromisoformat(meeting_date.replace('Z', '+00:00'))
            logger.debug(f"get_meeting_date(): Parsed datetime: {parsed_datetime}")
            return parsed_datetime
        else:
            return None
    except Exception as e:
        logger.error(f"get_meeting_date(): Error retrieving meeting date for subscription {subscription_id}: {str(e)}")
        raise
