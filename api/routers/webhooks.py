import logging
import os
from datetime import datetime

import stripe
from fastapi import APIRouter, HTTPException, Request

from models.payment_models import WebhookEvent
from payment_serv.webhook_handlers import webhook_router

logger = logging.getLogger('uvicorn.error')

router = APIRouter(
    prefix="/api/v1/webhooks",
    tags=["webhooks"]
)


@router.post("/stripe")
async def stripe_webhook(request: Request):
    """Handle Stripe webhook events."""
    payload = await request.body()
    sig_header = request.headers.get('stripe-signature')

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, os.environ.get('STRIPE_WEBHOOK_SECRET')
        )

        webhook_event = WebhookEvent(
            id=event.id,
            type=event.type,
            data=event.data,
            created=datetime.fromtimestamp(event.created)
        )

        logger.info(f"stripe_webhook(): Event type: {event.type}")

        await webhook_router(webhook_event)

        return {"status": "success"}

    except stripe.SignatureVerificationError as e:
        logger.error(f"Invalid webhook signature: {str(e)}")
        raise HTTPException(status_code=400, detail="Invalid signature")
    except Exception as e:
        logger.error(f"Webhook error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
