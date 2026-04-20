import logging
from typing import List

from fastapi import APIRouter, HTTPException

from config.supabase import get_supabase, get_supabase_service_role
from models.admin_models import SubscriptionDashboardResponse, SubscriptionProgressUpdate
from repositories.subscription_repository import (
    get_all_subscription_progress,
    update_subscription_progress_admin,
)
from user_serv.user_service import meeting_confirmation_process

logger = logging.getLogger('uvicorn.error')

supabase = get_supabase()
auth_supabase = get_supabase_service_role()

router = APIRouter(
    prefix="/api/v1/admin",
    tags=["admin"]
)


@router.get("/health")
async def admin_health_check():
    """Basic health check endpoint for admin dashboard."""
    return {
        "status": "ok",
        "service": "Admin API"
    }


@router.post("/subscription-progress-update")
async def admin_update_subscription_progress(update: SubscriptionProgressUpdate):
    """Update subscription progress (status and/or meeting_date) for a subscription."""
    try:
        if not update.status and not update.meeting_date:
            raise HTTPException(status_code=400, detail="Both status and meeting_date must be provided")

        #TODO: build more robust status validation
        if update.status not in ['meeting_scheduled']:
            raise HTTPException(status_code=400, detail="Invalid status value, please ensure the status is set to 'Meeting Scheduled'")

        logger.info(f"admin_update_subscription_progress(): Updating subscription {update.subscription_id} with status {update.status} and meeting_date {update.meeting_date}")

        update_subscription_progress_admin(
            update.subscription_id,
            status=update.status,
            meeting_date=update.meeting_date
        )

        #TODO: Add address in to both emails for meeting confirmation
        meeting_confirmation_process(update.subscription_id, update.meeting_date)

        return {"message": "Subscription progress updated"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"admin_update_subscription_progress(): Error updating progress: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.get("/subscription-progress")
async def admin_subscription_progress() -> List[SubscriptionDashboardResponse]:
    """Get subscription progress for all users."""
    try:
        return get_all_subscription_progress(auth_supabase)
    except Exception as e:
        logger.error(f"admin_subscription_progress(): Error getting subscription progress: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal Server Error")
