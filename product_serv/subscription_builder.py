from datetime import datetime
from supabase import Client
from ios.io_db import get_stripe_price_ids
from payment_serv.payment_processor import CreateSubscriptionRequest
import logging

logger = logging.getLogger('uvicorn.error')




#TODO: Refactor this to use the database
NAPPY_RULES = [
    {"min_age": 0, "max_age": 3, "min_weight": 0, "max_weight": 6, "product_id": "45bf677e-02e4-4b4f-8e8b-84eb47d46b89"},
    {"min_age": 4, "max_age": 6, "min_weight": 6, "max_weight": 12, "product_id": "dfd5cc56-859d-4c40-9f25-2ae5dac2aca1"},
]

WRAP_RULES = [
    {"min_age": 0, "max_age": 3, "min_weight": 0, "max_weight": 6, "product_id": "e5c2656e-f6db-4a2e-a642-cbceceb56054"},
    {"min_age": 4, "max_age": 6, "min_weight": 6, "max_weight": 12, "product_id": "8e6bb3ed-eb3c-4812-8f65-9c2c93379fc4"},
]

def determine_age(birthdate: datetime) -> int:
    """Determine age in months from birthdate"""
    try:
        today = datetime.today()
        age_in_months = (today.year - birthdate.year) * 12 + today.month - birthdate.month
        return age_in_months
    except Exception as e:
        logger.error(f"determine_age(): Error determining age for birthdate {birthdate}: {str(e)}")
        raise

def build_subscription_items(supabase: Client, data: CreateSubscriptionRequest) -> list[dict]:
    """
    Build a CreateSubscriptionRequest from the incoming request data.
    """
    try:
        logger.info(f"build_subscription_items(): Building subscription items for baby birthdate {data.babyBirthdate}, weight {data.babyWeight}, wantNappyWraps {data.wantNappyWraps}")
        # Convert birthdate to datetime and get age
        baby_birthdate = datetime.strptime(data.babyBirthdate, "%Y-%m-%d")
        age_in_months = determine_age(baby_birthdate)

        product_ids = []

        # Add start up costs
        product_ids.append("10d144db-9ae0-47f0-b9e0-5d60267332a4")

        # Determine nappy subscription
        for rule in NAPPY_RULES:
            if (rule["min_age"] <= age_in_months <= rule["max_age"] and
                    rule["min_weight"] <= data.babyWeight <= rule["max_weight"]):
                product_ids.append(rule["product_id"])

        want_nappy_wraps = data.wantNappyWraps

        # Determine wrap subscription
        if want_nappy_wraps:
            for rule in WRAP_RULES:
                if (rule["min_age"] <= age_in_months <= rule["max_age"] and
                        rule["min_weight"] <= data.babyWeight <= rule["max_weight"]):
                    product_ids.append(rule["product_id"])

        # Match the product IDs with Stripe price IDs from the db
        stripe_price_ids = get_stripe_price_ids(supabase, product_ids)

        logger.info(f"build_subscription_items(): Matched product IDs {product_ids} to Stripe price IDs {stripe_price_ids}")

        # Build a stripe compatible set of line items
        stripe_line_items = [{"price": price_id, "quantity": 1} for price_id in stripe_price_ids]
        
        logger.debug(f"build_subscription_items(): Built Stripe line items: {stripe_line_items}")

        return stripe_line_items
    except Exception as e:
        logger.error(f"build_subscription_items(): Error building subscription items: {str(e)}")
        raise
