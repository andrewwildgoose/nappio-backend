from fastapi import FastAPI, Depends, HTTPException
import os
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
#import stripe
from supabase import create_client, Client
import uvicorn

# Initialize FastAPI app
app = FastAPI()

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
SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY')
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Stripe configuration
#stripe.api_key = "your_stripe_secret_key"

# Pydantic models
class User(BaseModel):
    email: str
    password: str

class Subscription(BaseModel):
    user_id: str
    plan_id: str

# Routes
@app.post("/register")
async def register(user: User):
    # Register user with Supabase
    response = supabase.auth.sign_up(email=user.email, password=user.password)
    if response.get("error"):
        raise HTTPException(status_code=400, detail=response["error"]["message"])
    return {"message": "User registered successfully"}

@app.post("/login")
async def login(user: User):
    # Authenticate user with Supabase
    response = supabase.auth.sign_in(email=user.email, password=user.password)
    if response.get("error"):
        raise HTTPException(status_code=400, detail=response["error"]["message"])
    return {"message": "User logged in successfully", "token": response["data"]["access_token"]}

# @app.post("/create-subscription")
# async def create_subscription(subscription: Subscription):
#     # Create Stripe subscription
#     try:
#         customer = stripe.Customer.create(email=subscription.user_id)
#         stripe.Subscription.create(
#             customer=customer.id,
#             items=[{"plan": subscription.plan_id}],
#         )
#     except stripe.error.StripeError as e:
#         raise HTTPException(status_code=400, detail=str(e))
#     return {"message": "Subscription created successfully"}

# Run the app
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)