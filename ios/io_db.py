"""
Compatibility shim: re-exports all repository functions and models.

Existing code that imports from `ios.io_db` continues to work unchanged.
New code should import directly from `repositories.*` and `models.*`.
"""

# Re-export models
from models.newsletter_models import (  # noqa: F401
    NewsletterSubscriber,
    EmailVerificationRequest,
    EmailVerificationResponse,
)
from models.user_models import UserAddress  # noqa: F401

# Re-export newsletter repository
from repositories.newsletter_repository import (  # noqa: F401
    insert_newsletter_subscriber,
    verify_newsletter_subscriber,
)

# Re-export subscription repository
from repositories.subscription_repository import (  # noqa: F401
    insert_user_subscription,
    update_user_subscription,
    get_subscription_by_id,
    get_user_subscriptions,
    insert_subscription_items,
    get_subscription_items,
    update_subscription_items,
    insert_subscription_progress,
    update_subscription_progress_admin,
    get_subscription_progress,
    get_all_subscription_progress,
    get_subscription_address,
)

# Re-export user repository
from repositories.user_repository import (  # noqa: F401
    insert_user_address,
    get_user_addresses,
    delete_user_address,
    get_user_by_subscription_id,
)

# Re-export payment repository
from repositories.payment_repository import (  # noqa: F401
    insert_checkout_session,
    update_checkout_session,
)

# Re-export product repository
from repositories.product_repository import (  # noqa: F401
    get_stripe_price_ids,
    get_products,
    get_products_by_stripe_product_ids,
    get_product_by_stripe_price_id,
)
