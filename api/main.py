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
from ios.io_db import NewsletterSubscriber, EmailVerificationRequest, EmailVerificationResponse, insert_newsletter_subscriber, verify_newsletter_subscriber
from email_serv.email_processor import send_confirmation_email


logger = logging.getLogger('uvicorn.error')
logger.setLevel(logging.DEBUG)

# Load environment variables from .env file
load_dotenv()

# Initialize FastAPI app
app = FastAPI(
    title="Nappio API",
    description="Backend API for Nappio newsletter service",
    version="1.0.0",
    docs_url="/docs",    # Swagger UI at /docs
    redoc_url="/redoc"   # ReDoc at /redoc
)

# Create APIRouter instance
router = APIRouter(
    prefix="/api/v1",
    tags=["newsletter"]

)
# Frontend URL
FRONTEND_URL = os.environ.get('FRONTEND_URL')

# Configure CORS
origins = [
    # Dev URLS
    "http://localhost",
    "http://localhost:3000",
    "http://localhost:5173",    
    # inject frontend URL from environment variable
    FRONTEND_URL,
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

# Root route for health chec
@app.get("/")
async def root():
    """
    Root endpoint - can be used for health checks
    """
    return {
        "status": "ok",
        "service": "Nappio API",
        "version": "1.0.0"
    }

# Newsletter routes
@router.post("/newsletter/subscribe", response_model=NewsletterSubscriber)
def subscribe_to_newsletter(subscriber: NewsletterSubscriber):
    """
    Handle newsletter subscription requests
    """
    try:
        logger.debug(f'Received subscriber data: {subscriber.model_dump()}')
        
        # Insert subscriber into the database
        result = insert_newsletter_subscriber(supabase, subscriber)
        if not result:
            logger.error("subscribe_to_newsletter(): Failed to subscribe")
            raise HTTPException(status_code=400, detail="Failed to subscribe")
        
        # Generate a confirmation link
        #TODO: this causes a double forward slash in the URL, fix it
        confirmation_link = f"{FRONTEND_URL}confirm-email?email={subscriber.email}"
        logger.debug(f"Generated confirmation link: {confirmation_link}")
        
        # Send confirmation email
        email_response = send_confirmation_email(
            to_email=subscriber.email,
            first_name=subscriber.first_name,
            confirmation_link=confirmation_link
        )
        
        if email_response.get("status") != 200:
            logger.warning(f"subscribe_to_newsletter(): Failed to send confirmation email to {subscriber.email}")
        
        return result
    except Exception as e:
        if "duplicate key" in str(e).lower():
            logger.error("subscribe_to_newsletter(): Email already subscribed")
            raise HTTPException(status_code=400, detail="Email already subscribed")
        logger.exception(f"subscribe_to_newsletter(): Error subscribing to newsletter: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/newsletter/verify", response_model=EmailVerificationResponse)
def verify_subscriber_email(request: EmailVerificationRequest):
    """
    Handle email verification requests
    """
    try:
        email = request.email
        logger.debug(f"Received email verification request for: {email}")
        verified = verify_newsletter_subscriber(supabase, request)
        if verified:
            return {"message": f"Email {email} verified successfully."}
        else:
            raise HTTPException(status_code=404, detail="Subscriber not found")
    except Exception as e:
        logger.exception(f"verify_subscriber_email(): Error verifying email {email}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Include router in app
app.include_router(router)

# Run the app
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)