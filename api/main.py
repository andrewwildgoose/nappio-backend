import os
import logging

import stripe
import uvicorn
from dotenv import load_dotenv
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.dependencies.auth import require_api_key
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

# Set ENVIRONMENT=development locally to enable /docs and localhost CORS origins
IS_DEV = os.environ.get('ENVIRONMENT', '').lower() == 'development'

# Initialize FastAPI app
app = FastAPI(
    title="Nappio API",
    description="Backend API for Nappio newsletter service",
    version="1.0.0",
    # API docs are only exposed in development so we don't advertise the API surface
    docs_url="/docs" if IS_DEV else None,
    redoc_url="/redoc" if IS_DEV else None,
    openapi_url="/openapi.json" if IS_DEV else None,
)

# Configure CORS
origins = [url.rstrip('/') for url in (FRONTEND_URL, ADMIN_DASHBOARD_URL) if url]
if IS_DEV:
    origins += [
        "http://localhost",
        "http://localhost:3000",
        "http://localhost:5173",
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
# Every router except webhooks needs an API key. The public website and the admin
# dashboard get separate keys, so the website's key can never reach admin routes.
frontend_key = [Depends(require_api_key("FRONTEND_API_KEY"))]
admin_key = [Depends(require_api_key("ADMIN_API_KEY"))]

app.include_router(newsletter.router, dependencies=frontend_key)
app.include_router(users.router, dependencies=frontend_key)
app.include_router(payments.router, dependencies=frontend_key)
app.include_router(service_config.router, dependencies=frontend_key)
app.include_router(admin.router, dependencies=admin_key)
# Stripe calls this directly; it is protected by the Stripe signature check instead
app.include_router(webhooks.router)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="trace", reload=True)
