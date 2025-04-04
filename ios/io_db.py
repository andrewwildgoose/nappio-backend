import logging
from typing import Optional
from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
import pytz
from uuid import UUID

logger = logging.getLogger('uvicorn.error')
logger.setLevel(logging.DEBUG)

class NewsletterSubscriber(BaseModel):
    id: Optional[UUID] = None
    first_name: str
    email: EmailStr
    postcode: Optional[str] = Field(None, min_length=2, max_length=4)
    subscribed_at: Optional[datetime] = None
    email_verified: bool = False

class EmailVerificationRequest(BaseModel):
    email: str

class EmailVerificationResponse(BaseModel):
    message: str

def insert_newsletter_subscriber(supabase, subscriber: NewsletterSubscriber) -> dict:
    """
    Insert a new newsletter subscriber into the database
    """
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
    
def verify_newsletter_subscriber(supabase, verify_request: EmailVerificationRequest) -> bool:
    """
    Verify a subscriber's email address
    """
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
        logger.error(f"verify_newsletter_subscriber(): Error verifying email {email}: {str(e)}")
        raise Exception(f"Error verifying email {email}: {str(e)}")