from fastapi import APIRouter, Depends, HTTPException
from typing import List
import logging

# Get Supabase client from config
from config.supabase import get_supabase, get_supabase_service_role
from supabase import Client

from ios import io_db
from models.admin_models import SubscriptionDashboardResponse, SubscriptionProgressUpdate
from email_serv.email_processor import send_order_email_to_team
from user_serv.user_service import meeting_confirmation_process

# Set up logging
logger = logging.getLogger('uvicorn.error')

# Initialize Supabase client
supabase = get_supabase()
logger.info(f"Supabase client initialized in admin_routes.py: {supabase}")
auth_supabase = get_supabase_service_role()
logger.info(f"Supabase service role client initialized in admin_routes.py: {auth_supabase}")

# Create admin router
router = APIRouter(
    prefix="/api/v1/admin",
    tags=["admin"]
)

# Example admin route
@router.get("/health")
async def admin_health_check():
    """
    Basic health check endpoint for admin dashboard
    """
    return {
        "status": "ok",
        "service": "Admin API"
    }

@router.post("/subscription-progress-update")
async def admin_update_subscription_progress(update: SubscriptionProgressUpdate):
    """
    Update subscription progress (status and/or meeting_date) for a subscription
    """
    try:
        logger.info(f"admin_update_subscription_progress(): Updating subscription {update.subscription_id} with status {update.status} and meeting_date {update.meeting_date}")
        # Call a function in io_db to perform the update
        io_db.update_subscription_progress_admin(
            supabase,
            update.subscription_id,
            status=update.status,
            meeting_date=update.meeting_date
        )

        #TODO:Add address in to both emails for meeting confirmation
        # send email to customer confirming meeting date & with link to trigger checkout building
        meeting_confirmation_process(supabase, update.subscription_id, update.meeting_date)

        # email team to confirm meeting date


        return {"message": "Subscription progress updated"}
    except Exception as e:
        logger.error(f"admin_update_subscription_progress(): Error updating progress: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

@router.get("/subscription-progress")
async def admin_subscription_progress() -> List[SubscriptionDashboardResponse]:
    """
    Get subscription progress for all users
    """
    try:
        subscription_dashboard_data = io_db.get_subscription_progress(supabase, auth_supabase)
        return subscription_dashboard_data
    except Exception as e:
        logger.error(f"admin_subscription_progress(): Error getting subscription progress: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal Server Error")


