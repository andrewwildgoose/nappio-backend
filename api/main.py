import os
import logging

import stripe
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import newsletter, users, payments, webhooks, admin, service_config

# Load environment variables from .env file
load_dotenv()

# Set up logging
logger = logging.getLogger('uvicorn.error')
logger.setLevel(logging.DEBUG)

# Stripe configuration
stripe.api_key = os.environ.get('STRIPE_SECRET_KEY')

# Frontend / admin URLs
FRONTEND_URL = os.environ.get('FRONTEND_URL')
ADMIN_DASHBOARD_URL = os.environ.get('ADMIN_DASHBOARD_URL')

# Initialize FastAPI app
app = FastAPI(
    title="Nappio API",
    description="Backend API for Nappio newsletter service",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Configure CORS
origins = [
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

# Health check
@app.get("/")
async def root():
    """Root endpoint – used for health checks."""
    return {
        "status": "ok",
        "service": "Nappio API",
        "version": "1.0.0"
    }

# Register routers
app.include_router(newsletter.router)
app.include_router(users.router)
app.include_router(payments.router)
app.include_router(webhooks.router)
app.include_router(admin.router)
app.include_router(service_config.router)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="trace", reload=True)
