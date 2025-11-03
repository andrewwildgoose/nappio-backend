# Util imports
import os
from uuid import UUID
from dotenv import load_dotenv
import logging
from datetime import datetime

# FastAPI imports
from fastapi import Depends, FastAPI, APIRouter, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Integration imports
#import stripe
import stripe

# Custom imports
import ios.io_db as io_db
import product_serv.subscription_builder as sub_builder
from email_serv.email_processor import send_confirmation_email
from payment_serv.payment_processor import CheckoutSessionRequest, CheckoutSessionResponse, CreateSubscriptionRequest, PaymentDetailsRequest, PaymentDetailsResponse
import payment_serv.payment_processor as pa
from payment_serv.webhook_handlers import WebhookEvent, webhook_router
import user_serv.user_service as user_service
import admin_serv.subscriptions as subscriptions_admin

# Get Supabase client from config
from config.supabase import get_supabase

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

user_router = APIRouter(
    prefix="/api/v1/user",
    tags=["users"]
)

# Import admin routes
from api.admin_routes import router as admin_router

# Frontend URL
FRONTEND_URL = os.environ.get('FRONTEND_URL')
ADMIN_DASHBOARD_URL = os.environ.get('ADMIN_DASHBOARD_URL')

# Configure CORS
origins = [
    # Dev URLS
    "http://localhost",
    "http://localhost:3000",
    "http://localhost:5173",    
    FRONTEND_URL,
    ADMIN_DASHBOARD_URL,
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Supabase client
supabase = get_supabase()

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
@router.post("/newsletter/subscribe", response_model=io_db.NewsletterSubscriber)
def subscribe_to_newsletter(subscriber: io_db.NewsletterSubscriber):
    """
    Handle newsletter subscription requests
    """
    try:
        logger.debug(f'Received subscriber data: {subscriber.model_dump()}')
        
        # Insert subscriber into the database
        result = io_db.insert_newsletter_subscriber(subscriber)
        if not result:
            logger.error("subscribe_to_newsletter(): Failed to subscribe")
            raise HTTPException(status_code=400, detail="Failed to subscribe")
        
        # Generate a confirmation link
        #TODO: this causes a double forward slash in the URL, fix it
        confirmation_link = f"{FRONTEND_URL}/confirm-email?email={subscriber.email}"
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
        raise HTTPException(status_code=500, detail='An unexpected error occurred.')

@router.post("/newsletter/verify", response_model=io_db.EmailVerificationResponse)
def verify_subscriber_email(request: io_db.EmailVerificationRequest):
    """
    Handle email verification requests
    """
    try:
        email = request.email
        logger.debug(f"Received email verification request for: {email}")
        verified = io_db.verify_newsletter_subscriber(request)
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
    #logger.debug(f"get_authenticated_user(): Received token: {token}")

    try:
        auth_response = supabase.auth.get_user(token)
        if not auth_response or not auth_response.user:
            raise HTTPException(status_code=401, detail="Invalid token")
        #logger.debug(f"get_authenticated_user(): Authenticated user: {auth_response.user}")
        return auth_response.user

    except Exception as e:
        logger.exception(f"get_authenticated_user(): Error getting user: {str(e)}")
        raise HTTPException(status_code=401, detail="Invalid token")

# User routes
@user_router.get("/user-subscriptions", response_model=list[user_service.SubscriptionDetailsResponse])
async def get_user_subscriptions(user = Depends(get_authenticated_user)):
    """
    Get a list of subscriptions for the authenticated user
    """
    try:
        #logger.debug(f"get_user_subscriptions(): Authenticated user: {user}")
        subscriptions = user_service.get_user_subscriptions(user.id)
        ##logger.debug(f"get_user_subscriptions(): Found subscriptions: {subscriptions}")
        return subscriptions
    except Exception as e:
        logger.error(f"Error getting user subscriptions: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@user_router.get("/user-addresses", response_model=list[io_db.UserAddress])
async def get_user_addresses(user = Depends(get_authenticated_user)):
    """
    Get a list of addresses for the authenticated user
    Args:
        user: Authenticated user object from Supabase (injected by dependency)

    Returns:
        List[UserAddress]: List of addresses associated with the user (empty list if none found)
    """
    try:
        #logger.debug(f"get_user_addresses(): Authenticated user: {user}")
        addresses = user_service.get_user_addresses(user.id)
        
        if not addresses:
            logger.info(f"get_user_addresses(): No addresses found for user {user.id}")
            return []
            
        #logger.debug(f"get_user_addresses(): Found {len(addresses)} addresses")
        return addresses
        
    except Exception as e:
        logger.error(f"Error getting user addresses: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@user_router.post("/add-address", response_model=user_service.AddUserAddressResponse)
async def add_user_address(
    request: user_service.AddUserAddressRequest,
    user = Depends(get_authenticated_user)
):
    """
    Add a new address for the authenticated user
    Args:
        request: AddAddressRequest containing address details
        user: Authenticated user object from Supabase (injected by dependency)
    Returns:
        UserAddress: The newly created address object
    """
    try:
        logger.debug(f"add_user_address(): Received request: {request.model_dump()}")
        address = user_service.add_user_address(request, user.id)
        logger.debug(f"add_user_address(): Created address: {address}")
        return address
    except Exception as e:
        logger.error(f"Error adding user address: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@user_router.delete("/delete-address/{address_id}", response_model=user_service.DeleteAddressResponse)
async def delete_user_address(
    address_id: str,
    user = Depends(get_authenticated_user)
):
    """
    Delete a user's address by ID
    Args:
        address_id: UUID of the address to delete (from URL path)
        user: Authenticated user object from Supabase (injected by dependency)
    Returns:
        DeleteAddressResponse: Confirmation of address deletion
    """
    try:
        logger.debug(f"delete_user_address(): Attempting to delete address {address_id} for user {user.id}")
        success = user_service.delete_user_address(UUID(address_id), user.id)
        
        if success:
            return {"message": "Address deleted successfully"}
        else:
            raise HTTPException(status_code=404, detail="Address not found")
            
    except Exception as e:
        logger.error(f"Error deleting address: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@user_router.post("/assign-subscription-address", response_model=dict)
async def assign_subscription_address(
    request: user_service.AssignSubscriptionAddressRequest,
    user = Depends(get_authenticated_user)
):
    try:
        logger.debug(f"assign_subscription_address(): Assigning address {request.address_id} to subscription {request.subscription_id}")
        result = user_service.assign_subscription_address(
            supabase=supabase,
            user_id=user.id,
            subscription_id=request.subscription_id,
            address_id=request.address_id
        )
        
        # Convert UUID to string in the response
        response_data = {
            "subscription_id": result.get("subscription_id"),
            "address_id": result.get("address_id"),  # Convert UUID to string
            "is_active": result.get("is_active"),
            "created_at": result.get("created_at")
        }
        
        return {
            "message": "Address assigned successfully", 
            "data": response_data
        }
        
    except ValueError as e:
        logger.error(f"Validation error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error assigning address to subscription: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Payment routes
@payment_router.post("/start-subscription", response_model=CheckoutSessionResponse)
async def start_subscription(
    request: CreateSubscriptionRequest,
    user = Depends(get_authenticated_user)
):
    """
    Start the process of setting up a new subscription for the user
    """
    try:
        logger.debug(f"start_subscription(): Received request: {request.model_dump()}")

        if request.addressId:
            logger.debug(f"start_subscription(): Using existing address ID: {request.addressId}")
            address_id = request.addressId
        else:
            logger.debug("start_subscription(): No existing address ID provided, creating new address")

            # Build insert the address for the subscription
            address_obj = user_service.AddUserAddressRequest(
                address_line_1=request.address["address_line_1"],
                address_line_2=request.address.get("address_line_2"),
                city=request.address["city"],
                postcode=request.address["postcode"],
                country=request.address["country"],
                address_notes=request.address.get("address_notes")
            )
            addressResponse = user_service.add_user_address(address_obj, user.id)

            address_id = str(addressResponse.address.id)

        # Add subscription to user_subscription table -> get subscription_id
        subscription = io_db.insert_user_subscription(
            status="pending", user_id=user.id, 
            address_id=address_id, 
            baby_dob=datetime.fromisoformat(request.babyBirthdate), 
            baby_weight_at_start=request.babyWeight
            )
        logger.debug(f"start_subscription(): Created subscription record: {subscription}")

        # Add subscription to subscription_progress table
        subscription_progress = io_db.insert_subscription_progress(
            subscription_id=subscription['id'], 
            status=subscription['status']
            )
        logger.debug(f"start_subscription(): Created subscription progress record: {subscription_progress}")

        # Add products to subscription_items table
        subscription_items = sub_builder.build_subscription_items(subscription['id'], request)
        items_added = io_db.insert_subscription_items(subscription_items=subscription_items)
        logger.debug(f"start_subscription(): Added {items_added} subscription items")


        # Combine standard metadata with any custom metadata from the request
        metadata = {
            "user_id": user.id,
            "subscription_id": subscription['id'],
            "address_id": address_id,
            "baby_dob": request.babyBirthdate,
            "baby_weight": request.babyWeight,
            "checkout_type": "start_up"
        }

        # Build startup line items for stripe checkout
        startup_line_items = sub_builder.build_stripe_startup_cost_items()
        logger.debug(f"start_subscription(): Built startup line items: {startup_line_items}")

        checkout_session = pa.create_stripe_checkout_session(
            line_items=startup_line_items,
            user=user,
            frontend_url=FRONTEND_URL,
            cancel_url=request.cancelUrl,
            metadata=metadata
        )
        logger.debug(f"start_subscription(): Created checkout session: {checkout_session}")

        return checkout_session
    except Exception as e:
        logger.error(f"start_subscription(): Error starting subscription: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@payment_router.post("/create-checkout-from-subscription", response_model=CheckoutSessionResponse)
async def create_subscription_checkout(
    request: user_service.SubscriptionRequest,
    user = Depends(get_authenticated_user)
):
    """
    Create a Stripe checkout session for an existing subscription.
    """
    try:
        logger.debug(f"create_subscription_checkout(): Received request: {request.model_dump()}")

        # Validate that the subscription belongs to the user and is in a state that allows checkout
        subscription = user_service.get_subscription(request.id)
        if not subscription:
            raise HTTPException(status_code=404, detail="Subscription not found")

        # Fetch the subscription items to build line items for Stripe
        subscription_items = user_service.get_subscription_items(subscription.id)
        if not subscription_items:
            raise HTTPException(status_code=400, detail="No items found for this subscription")

        product_ids = [item['product_id'] for item in subscription_items]
        
        line_items = sub_builder.build_stripe_subscription_items(product_ids)
        logger.debug(f"create_subscription_checkout(): Built line items: {line_items}")

        # Combine standard metadata with any custom metadata from the request
        metadata = {
            "subscription_id": request.id,
            "checkout_type": "subscription"
        }

        #TODO: Need to factor in the subscription start date.
        subscription_start_date = subscriptions_admin.get_meeting_date(request.id)
        logger.debug(f'Type of subscription_start_date: {type(subscription_start_date)}')
        if not subscription_start_date:
            raise HTTPException(status_code=400, detail="Meeting date not found")

        checkout_session = pa.create_stripe_subscription_checkout_session(
            line_items=line_items,
            user=user,
            frontend_url=FRONTEND_URL,
            cancel_url=request.cancelUrl,
            billing_anchor=subscription_start_date,
            metadata=metadata
        )
        logger.debug(f"create_subscription_checkout(): Created checkout session: {checkout_session}")

        return checkout_session

    except HTTPException as he:
        raise he  # Re-raise HTTP exceptions to be handled by FastAPI
    except Exception as e:
        logger.error(f"create_subscription_checkout(): Error creating checkout session: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@payment_router.post("/payment-completed-details", response_model=PaymentDetailsResponse)
def get_payment_completed_details_route(
    request: PaymentDetailsRequest,
    user = Depends(get_authenticated_user)
):
    """
    Fetch details for a specific payment
    """
    try:
        logger.debug(f"get_payment_details(): Received request: {request.model_dump()}")
        return pa.get_payment_completed_details(request.session_id)
    except Exception as e:
        logger.error(f"Error getting payment details: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    
# Stripe webhook endpoint for handling events
@payment_router.post("/webhook-stripe")
async def stripe_webhook(request: Request):
    """Handle Stripe webhook events"""
    payload = await request.body()
    sig_header = request.headers.get('stripe-signature')
    
    try:
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
        
        # Log the event type
        logger.info(f"stripe_webhook(): Event type: {event.type}")


        # Route the event to the appropriate handler
        await webhook_router(webhook_event)
            
        return {"status": "success"}
        
    except stripe.SignatureVerificationError as e:
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
app.include_router(user_router)
app.include_router(admin_router)

# Run the app
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="trace", reload=True)