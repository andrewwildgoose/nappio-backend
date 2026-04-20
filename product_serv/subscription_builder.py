from datetime import datetime
from repositories.product_repository import get_stripe_price_ids
from models.payment_models import CreateSubscriptionRequest
import logging

logger = logging.getLogger('uvicorn.error')




#TODO: Refactor this to use the database
NAPPY_RULES = [
    {"min_weight": 0, "max_weight": 6, "serviceLevel": "full-time", "product_id": "45bf677e-02e4-4b4f-8e8b-84eb47d46b89"},
    {"min_weight": 0, "max_weight": 6, "serviceLevel": "part-time", "product_id": "4b00c71a-e2f6-4a2e-9e06-0cfe009bbcd7"},
    {"min_weight": 6, "max_weight": 36, "serviceLevel": "full-time", "product_id": "dfd5cc56-859d-4c40-9f25-2ae5dac2aca1"},
        {"min_weight": 6, "max_weight": 36, "serviceLevel": "part-time", "product_id": "b8bc8da7-ffa6-4e5e-943f-75c2ab9c12aa"},
]

# Marked for removal - leaving in as may reintroduce later
# WRAP_RULES = [
#     {"min_weight": 0, "max_weight": 6, "product_id": "e5c2656e-f6db-4a2e-a642-cbceceb56054"},
#     {"min_weight": 6, "max_weight": 36, "product_id": "8e6bb3ed-eb3c-4812-8f65-9c2c93379fc4"},
# ]

def determine_age(birthdate: datetime) -> int:
    """Determine age in months from birthdate"""
    try:
        today = datetime.today()
        age_in_months = (today.year - birthdate.year) * 12 + today.month - birthdate.month
        return age_in_months
    except Exception as e:
        logger.error(f"determine_age(): Error determining age for birthdate {birthdate}: {str(e)}")
        raise

#TODO: refactor this to include a list of items to include
def build_stripe_startup_cost_items() -> list[dict]:
    """
    Build a list of the line items to be included in the startup costs from the incoming request data
    """
    try:
        logger.info("build_stripe_startup_cost_items(): Building startup cost items")

        # Startup costs product ID
        #TODO: refactor this to use database
        product_ids = ["10d144db-9ae0-47f0-b9e0-5d60267332a4"]

        # Match the product IDs with Stripe price IDs from the db
        stripe_price_ids = get_stripe_price_ids(product_ids)

        logger.info(f"build_startup_cost_items(): Matched product IDs {product_ids} to Stripe price IDs {stripe_price_ids}")

        # Build a stripe compatible set of line items
        stripe_line_items = [{"price": price_id, "quantity": 1} for price_id in stripe_price_ids]
        
        logger.debug(f"build_stripe_startup_cost_items(): Built Stripe line items: {stripe_line_items}")

        return stripe_line_items
    except Exception as e:
        logger.error(f"build_stripe_startup_cost_items(): Error building startup cost items: {str(e)}")
        raise

def build_subscription_items(subscription_id: str, data: CreateSubscriptionRequest) -> list[dict]:
    """
    Build a list of the products within the subscription from the incoming request data.
    """
    try:
        logger.info(f"build_subscription_items(): Building subscription items for baby birthdate: {data.babyBirthdate}, weight: {data.babyWeight}, service level: {data.serviceLevel}")
        # Convert birthdate to datetime and get age
        baby_birthdate = datetime.strptime(data.babyBirthdate, "%Y-%m-%d")
        age_in_months = determine_age(baby_birthdate)

        product_ids = []

        # Determine nappy subscription
        for rule in NAPPY_RULES:
            if rule["min_weight"] <= data.babyWeight <= rule["max_weight"] and rule["serviceLevel"] == data.serviceLevel:
                product_ids.append(rule["product_id"])

        # Marked for removal - leaving in as may reintroduce later
        # want_nappy_wraps = data.wantNappyWraps

        # # Determine wrap subscription
        # if want_nappy_wraps:
        #     for rule in WRAP_RULES:
        #         if rule["min_weight"] <= data.babyWeight <= rule["max_weight"]:
        #             product_ids.append(rule["product_id"])

        # Build a stripe compatible set of line items
        subscription_items = [{"subscription_id": subscription_id, "product_id": product_id, "quantity": 1} for product_id in product_ids]

        logger.debug(f"build_subscription_items(): Built subscription items: {subscription_items}")

        return subscription_items
    except Exception as e:
        logger.error(f"build_subscription_items(): Error building subscription items: {str(e)}")
        raise

def build_stripe_subscription_items(product_ids: list[str]) -> list[dict]:
    """
    Build a list of the line items within the subscription from the incoming request data.
    """
    try:
        logger.info(f"build_stripe_subscription_items(): Building subscription items for product IDs {product_ids}")

        # Match the product IDs with Stripe price IDs from the db
        stripe_price_ids = get_stripe_price_ids(product_ids)

        logger.info(f"build_stripe_subscription_items(): Matched product IDs {product_ids} to Stripe price IDs {stripe_price_ids}")

        # Build a stripe compatible set of line items
        stripe_line_items = [{"price": price_id, "quantity": 1} for price_id in stripe_price_ids]

        logger.debug(f"build_stripe_subscription_items(): Built Stripe line items: {stripe_line_items}")

        return stripe_line_items
    except Exception as e:
        logger.error(f"build_stripe_subscription_items(): Error building subscription items: {str(e)}")
        raise
