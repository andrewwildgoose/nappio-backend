import logging
import os

from fastapi import APIRouter, Depends, HTTPException

import payment_serv.payment_processor as pa
import product_serv.shop_builder as shop_builder
import user_serv.user_service as user_service
from api.dependencies.auth import get_authenticated_user
from models.payment_models import (
    CheckoutSessionResponse,
    CreateOrderCheckoutRequest,
    GuestCreateOrderCheckoutRequest,
)
from models.user_models import AddUserAddressRequest
from repositories.order_repository import insert_order, insert_order_items

logger = logging.getLogger('uvicorn.error')

FRONTEND_URL = os.environ.get('FRONTEND_URL')

router = APIRouter(
    prefix="/api/v1/shop",
    tags=["shop"]
)


@router.get("/products")
async def list_shop_products():
    """
    Return all active one-off products available in the shop.

    This endpoint is **public** – no authentication is required.

    Powered by the local product catalogue, which is kept in sync with Stripe
    via webhooks (product.created / product.updated / price.created, etc.).
    """
    try:
        from repositories.product_repository import get_active_shop_products
        products = get_active_shop_products()
        return {"products": products}
    except Exception as e:
        logger.error(f"list_shop_products(): Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/checkout", response_model=CheckoutSessionResponse)
async def create_shop_checkout(
    request: CreateOrderCheckoutRequest,
    user=Depends(get_authenticated_user)
):
    """
    Create a Stripe checkout session for an authenticated user purchasing shop items.

    - Resolves or creates a delivery address.
    - Records a pending order in `public.orders` / `public.order_items`.
    - Returns a Stripe-hosted checkout URL.

    **Authentication:** ****** required (`Authorization: ******
    """
    try:
        logger.debug(f"create_shop_checkout(): Received request for user {user.id}: {request.model_dump()}")

        if request.address_id:
            address_id = request.address_id
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

        total_price = shop_builder.calculate_order_total(request.items)

        order = insert_order(
            total_price=total_price,
            status="pending",
            user_id=str(user.id),
            address_id=address_id,
        )
        order_id = order['id']
        logger.debug(f"create_shop_checkout(): Created order {order_id}")

        db_items = shop_builder.build_order_items_for_db(order_id, request.items)
        insert_order_items(order_id, db_items)
        logger.debug(f"create_shop_checkout(): Inserted {len(db_items)} order items")

        stripe_line_items = shop_builder.build_stripe_shop_line_items(request.items)

        metadata = {
            "user_id": str(user.id),
            "order_id": order_id,
            "address_id": address_id,
            "checkout_type": "one_off_purchase",
        }

        checkout_session = pa.create_stripe_checkout_session(
            line_items=stripe_line_items,
            user=user,
            frontend_url=FRONTEND_URL,
            cancel_url=request.cancel_url,
            metadata=metadata,
        )

        return checkout_session

    except Exception as e:
        logger.error(f"create_shop_checkout(): Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/checkout/guest", response_model=CheckoutSessionResponse)
async def create_guest_shop_checkout(request: GuestCreateOrderCheckoutRequest):
    """
    Create a Stripe checkout session for a **guest** (unauthenticated) user.

    - No account is required.
    - Resolves or accepts an address for delivery.
    - Records a pending order in `public.orders` with `user_id = NULL`.
    - Returns a Stripe-hosted checkout URL where the guest enters payment details.

    **Authentication:** None required.
    """
    try:
        logger.debug(f"create_guest_shop_checkout(): Received guest checkout request for {request.guest_email}")

        address_id = None
        if request.address_id:
            address_id = request.address_id
        elif request.address:
            from config.supabase import get_supabase
            _supabase = get_supabase()
            addr_response = _supabase.table('user_addresses').insert({
                "address_line_1": request.address["address_line_1"],
                "address_line_2": request.address.get("address_line_2"),
                "city": request.address["city"],
                "postcode": request.address["postcode"],
                "country": request.address["country"],
                "address_notes": request.address.get("address_notes"),
            }).execute()
            if addr_response.data:
                address_id = str(addr_response.data[0]['id'])

        total_price = shop_builder.calculate_order_total(request.items)

        order = insert_order(
            total_price=total_price,
            status="pending",
            user_id=None,
            address_id=address_id,
        )
        order_id = order['id']
        logger.debug(f"create_guest_shop_checkout(): Created guest order {order_id}")

        db_items = shop_builder.build_order_items_for_db(order_id, request.items)
        insert_order_items(order_id, db_items)
        logger.debug(f"create_guest_shop_checkout(): Inserted {len(db_items)} order items")

        stripe_line_items = shop_builder.build_stripe_shop_line_items(request.items)

        metadata = {
            "order_id": order_id,
            "checkout_type": "one_off_purchase",
        }

        checkout_session = pa.create_stripe_checkout_session(
            line_items=stripe_line_items,
            guest_email=request.guest_email,
            frontend_url=FRONTEND_URL,
            cancel_url=request.cancel_url,
            metadata=metadata,
        )

        return checkout_session

    except Exception as e:
        logger.error(f"create_guest_shop_checkout(): Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
