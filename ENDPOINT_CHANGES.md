# Endpoint Changes (Refactoring)

This document maps every changed API endpoint path from the old structure to the new structure.
No existing *functionality* has changed — only the URL paths and HTTP methods have been cleaned up.

## Changed Endpoints

| Old Path | New Path | Method | Notes |
|---|---|---|---|
| `GET /api/v1/user/user-subscriptions` | `GET /api/v1/user/subscriptions` | GET | Removed redundant `user-` prefix |
| `GET /api/v1/user/user-addresses` | `GET /api/v1/user/addresses` | GET | Removed redundant `user-` prefix |
| `POST /api/v1/user/add-address` | `POST /api/v1/user/addresses` | POST | RESTful resource naming |
| `DELETE /api/v1/user/delete-address/{address_id}` | `DELETE /api/v1/user/addresses/{address_id}` | DELETE | RESTful resource naming; address ID now a path param |
| `POST /api/v1/user/assign-subscription-address` | `POST /api/v1/user/subscription-address` | POST | Simplified name |
| `POST /api/v1/start-subscription` | `POST /api/v1/subscriptions` | POST | RESTful resource naming |
| `POST /api/v1/pause-subscription` | `POST /api/v1/subscriptions/pause` | POST | Grouped under subscriptions resource |
| `POST /api/v1/create-checkout-from-subscription` | `POST /api/v1/subscriptions/checkout` | POST | Grouped under subscriptions resource |
| `POST /api/v1/payment-completed-details` | `POST /api/v1/payments/details` | POST | Grouped under payments resource |
| `POST /api/v1/webhook-stripe` | `POST /api/v1/webhooks/stripe` | POST | Grouped under webhooks resource |

## Unchanged Endpoints

| Path | Method | Notes |
|---|---|---|
| `POST /api/v1/newsletter/subscribe` | POST | No change |
| `POST /api/v1/newsletter/verify` | POST | No change |
| `GET /api/v1/admin/health` | GET | No change |
| `POST /api/v1/admin/subscription-progress-update` | POST | No change |
| `GET /api/v1/admin/subscription-progress` | GET | No change |

## Removed Endpoints

| Old Path | Reason |
|---|---|
| `GET /api/test/jwt` | Test/debug endpoint removed as agreed |
