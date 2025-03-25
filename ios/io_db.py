import logging
from typing import Optional
from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from uuid import UUID

logger = logging.getLogger('uvicorn.error')
logger.setLevel(logging.DEBUG)

class NewsletterSubscriber(BaseModel):
    id: Optional[UUID] = None
    first_name: str
    email: EmailStr
    postcode: Optional[str] = Field(None, min_length=3, max_length=4)
    subscribed_at: Optional[datetime] = None

def insert_newsletter_subscriber(supabase, subscriber: NewsletterSubscriber) -> dict:
    """
    Insert a new newsletter subscriber into the database
    """
    try:
        response = supabase.table('newsletter_subscribers').insert({
            "first_name": subscriber.first_name,
            "email": subscriber.email,
            "postcode": subscriber.postcode
        }).execute()
        
        return response.data[0] if response.data else None
    except Exception as e:
        logger.error(f"insert_newsletter_subscriber(): Error inserting newsletter subscriber: {str(e)}")   
        raise Exception(f"Error inserting newsletter subscriber: {str(e)}")