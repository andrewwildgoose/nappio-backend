import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

import user_serv.user_service as user_service
from api.dependencies.auth import get_authenticated_user
from config.supabase import get_supabase
from models.user_models import (
    AddUserAddressRequest,
    AddUserAddressResponse,
    AssignSubscriptionAddressRequest,
    DeleteAddressResponse,
    SubscriptionDetailsResponse,
    UserAddress,
)

logger = logging.getLogger('uvicorn.error')

supabase = get_supabase()

router = APIRouter(
    prefix="/api/v1/user",
    tags=["users"]
)


@router.get("/subscriptions", response_model=list[SubscriptionDetailsResponse])
async def get_user_subscriptions(user=Depends(get_authenticated_user)):
    """Get a list of subscriptions for the authenticated user."""
    try:
        return user_service.get_user_subscriptions(user.id)
    except Exception as e:
        logger.error(f"get_user_subscriptions(): Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/addresses", response_model=list[UserAddress])
async def get_user_addresses(user=Depends(get_authenticated_user)):
    """Get a list of addresses for the authenticated user."""
    try:
        addresses = user_service.get_user_addresses(user.id)
        return addresses if addresses else []
    except Exception as e:
        logger.error(f"get_user_addresses(): Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/addresses", response_model=AddUserAddressResponse)
async def add_user_address(
    request: AddUserAddressRequest,
    user=Depends(get_authenticated_user)
):
    """Add a new address for the authenticated user."""
    try:
        logger.debug(f"add_user_address(): Received request: {request.model_dump()}")
        return user_service.add_user_address(request, user.id)
    except Exception as e:
        logger.error(f"add_user_address(): Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/addresses/{address_id}", response_model=DeleteAddressResponse)
async def delete_user_address(
    address_id: str,
    user=Depends(get_authenticated_user)
):
    """Delete a user's address by ID."""
    try:
        logger.debug(f"delete_user_address(): Attempting to delete address {address_id} for user {user.id}")
        success = user_service.delete_user_address(UUID(address_id), user.id)
        if success:
            return DeleteAddressResponse(success=True, message="Address deleted successfully")
        else:
            raise HTTPException(status_code=404, detail="Address not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"delete_user_address(): Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/subscription-address", response_model=dict)
async def assign_subscription_address(
    request: AssignSubscriptionAddressRequest,
    user=Depends(get_authenticated_user)
):
    """Assign a delivery address to an existing subscription."""
    try:
        logger.debug(f"assign_subscription_address(): Assigning address {request.address_id} to subscription {request.subscription_id}")
        result = user_service.assign_subscription_address(
            supabase=supabase,
            user_id=user.id,
            subscription_id=request.subscription_id,
            address_id=request.address_id
        )

        response_data = {
            "subscription_id": result.get("subscription_id"),
            "address_id": result.get("address_id"),
            "is_active": result.get("is_active"),
            "created_at": result.get("created_at")
        }

        return {
            "message": "Address assigned successfully",
            "data": response_data
        }

    except ValueError as e:
        logger.error(f"assign_subscription_address(): Validation error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"assign_subscription_address(): Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
