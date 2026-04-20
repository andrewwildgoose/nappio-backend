import logging
from datetime import datetime

import pytz

from config.supabase import get_supabase
from models.newsletter_models import EmailVerificationRequest, NewsletterSubscriber

logger = logging.getLogger('uvicorn.error')

supabase = get_supabase()


def insert_newsletter_subscriber(subscriber: NewsletterSubscriber) -> dict:
    """Insert a new newsletter subscriber into the database."""
    try:
        data_to_insert = {
            "first_name": subscriber.first_name,
            "email": subscriber.email,
            "postcode": subscriber.postcode,
            "subscribed_at": datetime.now(pytz.UTC).isoformat(),
            "email_verified": subscriber.email_verified,
        }
        logger.debug(f"insert_newsletter_subscriber(): Data to insert: {data_to_insert}")

        response = supabase.table('newsletter_subscribers').insert(data_to_insert).execute()

        if response.data:
            logger.info(f"insert_newsletter_subscriber(): Inserted data: {response.data[0]}")
        else:
            logger.warning("insert_newsletter_subscriber(): No data returned from insert operation.")

        return response.data[0] if response.data else None
    except Exception as e:
        logger.error(f"insert_newsletter_subscriber(): Error inserting newsletter subscriber: {str(e)}")
        raise Exception(f"Error inserting newsletter subscriber: {str(e)}")


def verify_newsletter_subscriber(verify_request: EmailVerificationRequest) -> bool:
    """Verify a subscriber's email address."""
    try:
        email = verify_request.email
        response = supabase.table('newsletter_subscribers').update({
            "email_verified": True
        }).eq("email", email).execute()

        if response.data:
            logger.info(f"verify_newsletter_subscriber(): Email {email} verified successfully.")
            return True
        else:
            logger.warning(f"verify_newsletter_subscriber(): No subscriber found with email {email}.")
            return False
    except Exception as e:
        logger.error(f"verify_newsletter_subscriber(): Error verifying email {verify_request.email}: {str(e)}")
        raise Exception(f"Error verifying email {verify_request.email}: {str(e)}")
