import logging
import os
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException

import admin_serv.subscriptions as subscriptions_admin
import payment_serv.payment_processor as pa
import payment_serv.voucher_service as voucher_service
import product_serv.subscription_builder as sub_builder
import user_serv.user_service as user_service
from api.dependencies.auth import get_authenticated_user
from models.payment_models import (
    CheckoutSessionResponse,
    CreateSubscriptionRequest,
    PauseSubscriptionRequest,
    PauseSubscriptionResponse,
    PaymentDetailsRequest,
    PaymentDetailsResponse,
    VoucherVerificationRequest,
    VoucherVerificationResult,
)
from models.user_models import (
    AddUserAddressRequest,
    SubscriptionRequest,
)
from repositories.subscription_repository import (
    insert_subscription_items,
    insert_subscription_progress,
    insert_user_subscription,
)
from repositories.user_repository import get_user_addresses
from repositories.voucher_repository import insert_voucher

logger = logging.getLogger('uvicorn.error')

FRONTEND_URL = os.environ.get('FRONTEND_URL')

router = APIRouter(
    prefix="/api/v1",
    tags=["payments"]
)


@router.post('/vouchers/verify', response_model=VoucherVerificationResult)
async def verify_voucher(
    request: VoucherVerificationRequest,
    user=Depends(get_authenticated_user)
):
    """Verify an RNFL voucher before checkout."""
    try:
        logger.debug(f"verify_voucher(): Verifying voucher for user {user.id}")
        return voucher_service.verify_voucher(request.voucher_code, request.postcode)
    except voucher_service.VoucherVerificationFailed as e:
        return e.result
    except voucher_service.VoucherServiceError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error(f"verify_voucher(): Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/subscriptions", response_model=CheckoutSessionResponse)
async def start_subscription(
    request: CreateSubscriptionRequest,
    user=Depends(get_authenticated_user)
):
    """Start the process of setting up a new subscription for the user."""
    try:
        logger.debug(f"start_subscription(): Received request: {request.model_dump()}")

        if request.addressId:
            address_id = request.addressId
            user_addresses = get_user_addresses(user.id)
            address_lookup = {str(address.id): address for address in user_addresses}
            selected_address = address_lookup.get(str(address_id))
            if not selected_address:
                raise HTTPException(status_code=404, detail="Address not found")
            postcode = selected_address.postcode
        else:
            address_obj = AddUserAddressRequest(
                address_line_1=request.address["address_line_1"],
                address_line_2=request.address.get("address_line_2"),
                city=request.address["city"],
                postcode=request.address["postcode"],
                country=request.address["country"],
                address_notes=request.address.get("address_notes")
            )
            address_response = user_service.add_user_address(address_obj, user.id)
            address_id = str(address_response.address.id)
            postcode = address_response.address.postcode

        subscription = insert_user_subscription(
            status="pending",
            user_id=user.id,
            address_id=address_id,
            baby_dob=datetime.fromisoformat(request.babyBirthdate),
            baby_weight_at_start=request.babyWeight
        )
        logger.debug(f"start_subscription(): Created subscription record: {subscription}")

        subscription_progress = insert_subscription_progress(
            subscription_id=subscription['id'],
            status=subscription['status']
        )
        logger.debug(f"start_subscription(): Created subscription progress record: {subscription_progress}")

        subscription_items = sub_builder.build_subscription_items(subscription['id'], request)
        insert_subscription_items(subscription_items=subscription_items)
        logger.debug("start_subscription(): Added subscription items")

        metadata = {
            "user_id": user.id,
            "subscription_id": subscription['id'],
            "address_id": address_id,
            "baby_dob": request.babyBirthdate,
            "baby_weight": request.babyWeight,
            "checkout_type": "start_up"
        }

        coupon_id = None
        if request.voucher:
            if request.voucher.postcode.strip().lower() != postcode.strip().lower():
                raise HTTPException(status_code=400, detail="Voucher postcode must match the subscription address postcode")
            insert_voucher(
                subscription_id=subscription['id'],
                code=request.voucher.code,
                postcode=request.voucher.postcode,
                status="verified",
                voucher_type=request.voucher.voucher_type,
            )
            coupon_id = request.voucher.discount_code
            metadata.update({
                "voucher_code": request.voucher.code,
                "voucher_postcode": request.voucher.postcode,
                "voucher_type": request.voucher.voucher_type,
                "voucher_discount_code": request.voucher.discount_code,
            })

        startup_line_items = sub_builder.build_stripe_startup_cost_items()

        checkout_session = pa.create_stripe_checkout_session(
            line_items=startup_line_items,
            user=user,
            frontend_url=FRONTEND_URL,
            cancel_url=request.cancelUrl,
            metadata=metadata,
            coupon_id=coupon_id,
        )

        return checkout_session

    except Exception as e:
        logger.error(f"start_subscription(): Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/subscriptions/pause", response_model=PauseSubscriptionResponse)
async def pause_subscription(
    request: PauseSubscriptionRequest,
    user=Depends(get_authenticated_user)
):
    """Pause an active subscription."""
    try:
        logger.debug(f"pause_subscription(): Received request: {request.model_dump()}")

        subscription = user_service.get_subscription(request.subscription_id)
        if not subscription:
            raise HTTPException(status_code=404, detail="Subscription not found")
        if subscription.user_id != user.id:
            raise HTTPException(status_code=403, detail="Not authorized to pause this subscription")

        pause_until_datetime = None
        if request.pause_until:
            pause_until_datetime = datetime.fromisoformat(request.pause_until)

        pa.pause_subscription(
            subscription_id=request.subscription_id,
            stripe_subscription_id=subscription.stripe_subscription_id,
            pause_until=pause_until_datetime
        )

        return PauseSubscriptionResponse(message="Subscription paused successfully")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"pause_subscription(): Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/subscriptions/checkout", response_model=CheckoutSessionResponse)
async def create_subscription_checkout(
    request: SubscriptionRequest,
    user=Depends(get_authenticated_user)
):
    """Create a Stripe checkout session for an existing subscription."""
    try:
        logger.debug(f"create_subscription_checkout(): Received request: {request.model_dump()}")

        subscription = user_service.get_subscription(request.id)
        if not subscription:
            raise HTTPException(status_code=404, detail="Subscription not found")

        subscription_items = user_service.get_subscription_items(subscription.id)
        if not subscription_items:
            raise HTTPException(status_code=400, detail="No items found for this subscription")

        product_ids = [item['product_id'] for item in subscription_items]
        line_items = sub_builder.build_stripe_subscription_items(product_ids)

        metadata = {
            "subscription_id": request.id,
            "checkout_type": "subscription"
        }

        subscription_start_date = subscriptions_admin.get_meeting_date(request.id)
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

        return checkout_session

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"create_subscription_checkout(): Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/payments/details", response_model=PaymentDetailsResponse)
def get_payment_completed_details_route(
    request: PaymentDetailsRequest,
    user=Depends(get_authenticated_user)
):
    """Fetch details for a specific payment."""
    try:
        logger.debug(f"get_payment_completed_details_route(): Received request: {request.model_dump()}")
        return pa.get_payment_completed_details(request.session_id)
    except Exception as e:
        logger.error(f"get_payment_completed_details_route(): Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
