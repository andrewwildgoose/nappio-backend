# Util imports
import os
from dotenv import load_dotenv
import logging

# FastAPI imports
from fastapi import FastAPI, APIRouter, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Intergration imports
#import stripe
from supabase import create_client, Client

# Custom imports
from ios.io_db import NewsletterSubscriber, insert_newsletter_subscriber


logger = logging.getLogger('uvicorn.error')
logger.setLevel(logging.DEBUG)

# Load environment variables from .env file
load_dotenv()

# Initialize FastAPI app
app = FastAPI()

# Create APIRouter instance
router = APIRouter(
    prefix="/api/v1",
    tags=["newsletter"]
)

# Configure CORS
origins = [
    # Dev URLS
    # TODO: inject frontend URL from environment variable
    "http://localhost",
    "http://localhost:3000",
    "http://localhost:5173",
    # Add your frontend URL here
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Supabase configuration
SUPABASE_URL: str = os.environ.get('SUPABASE_URL')
SUPABASE_KEY: str = os.environ.get('SUPABASE_KEY')
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Stripe configuration
#stripe.api_key = os.environ.get('STRIPE_SECRET_KEY')

# Newsletter routes
@router.post("/newsletter/subscribe", response_model=NewsletterSubscriber)
def subscribe_to_newsletter(subscriber: NewsletterSubscriber):
    """
    Handle newsletter subscription requests
    """
    try:
        logger.debug(f'Received subscriber data: {subscriber.model_dump()}')
        result = insert_newsletter_subscriber(supabase, subscriber)
        if not result:
            logger.error("subscribe_to_newsletter(): Failed to subscribe")
            raise HTTPException(status_code=400, detail="Failed to subscribe")
        return result
    except Exception as e:
        if "duplicate key" in str(e).lower():
            logger.error("subscribe_to_newsletter(): Email already subscribed")
            raise HTTPException(status_code=400, detail="Email already subscribed")
        logger.error(f"subscribe_to_newsletter(): Error subscribing to newsletter: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Include router in app
app.include_router(router)

# Run the app
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)