# Util imports
import os
from dotenv import load_dotenv
import logging
from datetime import datetime

# FastAPI imports
from fastapi import Depends, FastAPI, APIRouter, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Integration imports
#import stripe
from supabase import create_client, Client
import stripe

# Custom imports
from ios.io_db import NewsletterSubscriber, EmailVerificationRequest, EmailVerificationResponse, insert_newsletter_subscriber, verify_newsletter_subscriber
from email_serv.email_processor import send_confirmation_email
from payment_serv.payment_processor import CheckoutSessionRequest, CheckoutSessionResponse, SubscriptionDetailsRequest, SubscriptionDetailsResponse, create_stripe_checkout_session, get_subscription_details
from payment_serv.webhook_handlers import WebhookEvent, webhook_router

# Set up logging
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

payment_router = APIRouter(
    prefix="/api/v1",
    tags=["payments"]
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
stripe.api_key = os.environ.get('STRIPE_SECRET_KEY')

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

# Authentication and JWT token handling
async def get_authenticated_user(request: Request):
    """
    Extracts and validates a JWT token from the Authorization header and returns the user data.
    
    Args:
        request (Request): The FastAPI request object containing the Authorization header.
    
    Returns:
        UserResponse: The authenticated user object from Supabase
    
    Raises:
        HTTPException: 
            - 401 if no authorization header is present
            - 401 if the token is invalid or expired
            - 401 if Supabase authentication fails
    """
    authorization = request.headers.get("Authorization")
    if not authorization:
        raise HTTPException(status_code=401, detail="No auth token")
    
    token = authorization.replace('Bearer ', '')
    logger.debug(f"get_authenticated_user(): Received token: {token}")

    try:
        auth_response = supabase.auth.get_user(token)
        if not auth_response or not auth_response.user:
            raise HTTPException(status_code=401, detail="Invalid token")
        logger.debug(f"get_authenticated_user(): Authenticated user: {auth_response.user}")
        return auth_response.user

    except Exception as e:
        logger.exception(f"get_authenticated_user(): Error getting user: {str(e)}")
        raise HTTPException(status_code=401, detail="Invalid token")

# Stripe checkout session creation
@payment_router.post("/create-checkout", response_model=CheckoutSessionResponse)
async def create_checkout_session(
    request: CheckoutSessionRequest,
    user = Depends(get_authenticated_user)
):
    """
    Create a Stripe checkout session for subscription purchase

    Args:
        request: Checkout session request containing price ID
        user: Authenticated user object from Supabase (injected by dependency)

    Returns:
        CheckoutSessionResponse: Contains checkout URL for redirect
    
    Raises:
        HTTPException: 
            - 400 if Stripe encounters an error
            - 500 if server encounters an error
    """
    try:
        logger.debug(f"create_checkout_session(): Received request: {request.model_dump()}")
        # Create checkout session using authenticated user
        result = create_stripe_checkout_session(
            supabase=supabase,
            request=request,
            user=user,
            frontend_url=FRONTEND_URL
        )

        logger.debug(f"create_checkout_session(): Created session: {result}")
        
        return result
        
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating checkout session: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    
# Get a user's subscription details
@payment_router.post("/subscription-details", response_model=SubscriptionDetailsResponse)
async def get_session_details(
    request: SubscriptionDetailsRequest,
    user = Depends(get_authenticated_user)
):
    """
    Fetch details for a successful subscription
    """
    try:
        logger.debug(f"get_session_details(): Received request: {request.model_dump()}")
        # Validate session ID
        return get_subscription_details(request.session_id)
    except Exception as e:
        logger.error(f"Error getting subscription details: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    
# Stripe webhook endpoint for handling events
@payment_router.post("/webhook-stripe")
async def stripe_webhook(request: Request):
    """Handle Stripe webhook events"""
    payload = await request.body()
    sig_header = request.headers.get('stripe-signature')
    
    try:
        # logger.debug(f"stripe_webhook(): Received payload: {payload.decode()}")
        # logger.debug(f"stripe_webhook(): Received signature header: {sig_header}")
        # Verify webhook signature
        event = stripe.Webhook.construct_event(
            payload, sig_header, os.environ.get('STRIPE_WEBHOOK_SECRET')
        )
        
        # Convert to our webhook event model
        webhook_event = WebhookEvent(
            id=event.id,
            type=event.type,
            data=event.data,
            created=datetime.fromtimestamp(event.created)
        )
        
        # # Log the event type
        # logger.info(f"stripe_webhook(): Event type: {event.type}")
        # # Log the event data
        # logger.debug(f"stripe_webhook(): Event data: {event.data}")

        # Route the event to the appropriate handler
        webhook_router(webhook_event, supabase)
            
        return {"status": "success"}
        
    except stripe.error.SignatureVerificationError as e:
        logger.error(f"Invalid webhook signature: {str(e)}")
        raise HTTPException(status_code=400, detail="Invalid signature")
    except Exception as e:
        logger.error(f"Webhook error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

#TEST METHODS

# Create APIRouter instance for test routes
test_router = APIRouter(
    prefix="/api/test",
    tags=["test"]
)

@test_router.post("/jwt")
async def test_jwt_endpoint(request: Request):
    """
    Test endpoint for JWT verification
    Logs the JWT from the Authorization header
    """
    try:
        # Get the Authorization header
        auth_header = request.headers.get('Authorization')
        if not auth_header:
            logger.warning("test_jwt_endpoint(): No Authorization header found")
            raise HTTPException(status_code=401, detail="No Authorization header")

        # Extract the JWT token
        if not auth_header.startswith('Bearer '):
            logger.warning("test_jwt_endpoint(): Invalid Authorization header format")
            raise HTTPException(status_code=401, detail="Invalid Authorization header format")

        jwt_token = auth_header.replace('Bearer ', '')
        
        # Log the JWT token (be careful with this in production!)
        logger.info(f"test_jwt_endpoint(): Received JWT token: {jwt_token}")

        return {
            "message": "JWT received and logged",
            "token_length": len(jwt_token)
        }

    except Exception as e:
        logger.exception(f"test_jwt_endpoint(): Error processing JWT: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Add the test router to the app
app.include_router(test_router)

# Include router in app
app.include_router(router)
app.include_router(payment_router)

# Run the app
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)