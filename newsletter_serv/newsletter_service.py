import logging
import os

from email_serv.email_processor import send_confirmation_email, send_newsletter_signup_to_team
from models.newsletter_models import EmailVerificationRequest, NewsletterSubscriber
from repositories.newsletter_repository import (
    insert_newsletter_subscriber,
    verify_newsletter_subscriber,
)

logger = logging.getLogger('uvicorn.error')

FRONTEND_URL = os.environ.get('FRONTEND_URL')


def subscribe(subscriber: NewsletterSubscriber) -> dict:
    """
    Process a newsletter subscription:
    - Insert subscriber into the database
    - Send confirmation email to the subscriber
    - Notify the team of the new signup

    Returns the newly created subscriber record.
    Raises ValueError on duplicate email, or Exception on unexpected errors.
    """
    try:
        logger.debug(f"subscribe(): Received subscriber data: {subscriber.model_dump()}")

        result = insert_newsletter_subscriber(subscriber)
        if not result:
            raise Exception("Failed to insert subscriber into the database")

        confirmation_link = f"{FRONTEND_URL}/confirm-email?email={subscriber.email}"
        logger.debug(f"subscribe(): Generated confirmation link: {confirmation_link}")

        email_response = send_confirmation_email(
            to_email=subscriber.email,
            first_name=subscriber.first_name,
            confirmation_link=confirmation_link
        )

        if email_response.get("status") != 200:
            logger.warning(f"subscribe(): Failed to send confirmation email to {subscriber.email}")

        team_response = send_newsletter_signup_to_team(
            subscriber_email=subscriber.email,
            subscriber_name=subscriber.first_name,
            subscriber_postcode=subscriber.postcode if hasattr(subscriber, 'postcode') else None
        )

        if team_response.get("status") != 200:
            logger.warning("subscribe(): Failed to send signup notification to team")

        return result

    except Exception as e:
        if "duplicate key" in str(e).lower():
            raise ValueError("Email already subscribed")
        logger.exception(f"subscribe(): Unexpected error: {str(e)}")
        raise


def verify_email(request: EmailVerificationRequest) -> bool:
    """
    Verify a subscriber's email address.

    Returns True if verified successfully, False if subscriber not found.
    """
    try:
        email = request.email
        logger.debug(f"verify_email(): Received email verification request for: {email}")
        return verify_newsletter_subscriber(request)
    except Exception as e:
        logger.exception(f"verify_email(): Error verifying email {request.email}: {str(e)}")
        raise
