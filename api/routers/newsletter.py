import logging

from fastapi import APIRouter, HTTPException

from models.newsletter_models import EmailVerificationRequest, EmailVerificationResponse, NewsletterSubscriber
from newsletter_serv.newsletter_service import subscribe, verify_email

logger = logging.getLogger('uvicorn.error')

router = APIRouter(
    prefix="/api/v1/newsletter",
    tags=["newsletter"]
)


@router.post("/subscribe", response_model=NewsletterSubscriber)
def subscribe_to_newsletter(subscriber: NewsletterSubscriber):
    """Handle newsletter subscription requests."""
    try:
        return subscribe(subscriber)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"subscribe_to_newsletter(): Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail='An unexpected error occurred.')


@router.post("/verify", response_model=EmailVerificationResponse)
def verify_subscriber_email(request: EmailVerificationRequest):
    """Handle email verification requests."""
    try:
        verified = verify_email(request)
        if verified:
            return {"message": f"Email {request.email} verified successfully."}
        else:
            raise HTTPException(status_code=404, detail="Subscriber not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"verify_subscriber_email(): Error verifying email {request.email}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
