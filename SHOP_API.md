# Shop API – Frontend Integration Guide

Base URL: `https://<your-api-host>/api/v1/shop`

---

## Authentication

| Endpoint | Auth required? |
|---|---|
| `GET /products` | ❌ Public |
| `POST /checkout` | ✅ ****** (Supabase access token) |
| `POST /checkout/guest` | ❌ Public |

Pass the token in the `Authorization` header:

```
Authorization: ******
```

---

## 1. List Shop Products

Returns all active one-off products available in the shop, sourced from the product catalogue (synced with Stripe).

### Request

```
GET /api/v1/shop/products
```

No request body or query parameters.

### Response `200 OK`

```json
{
  "products": [
    {
      "id": "uuid",
      "name": "Reusable Nappy Starter Pack",
      "description": "Everything you need to get started with reusable nappies.",
      "active": true,
      "price": 2999,
      "currency": "GBP",
      "type": "oneoff",
      "stripe_product_id": "prod_xxxx",
      "stripe_price_id": "price_xxxx",
      "image_url": "https://...",
      "stock": null,
      "created_at": "2025-01-01T00:00:00",
      "updated_at": "2025-01-01T00:00:00"
    }
  ]
}
```

| Field | Type | Notes |
|---|---|---|
| `id` | `string (uuid)` | Internal product ID – use this in checkout requests |
| `name` | `string` | Display name |
| `description` | `string \| null` | Optional product description |
| `active` | `boolean` | Always `true` in this response |
| `price` | `integer` | Price in **pence** (divide by 100 for £ display) |
| `currency` | `string` | Always `"GBP"` |
| `type` | `string` | Always `"oneoff"` for shop products |
| `image_url` | `string \| null` | Product image URL |
| `stock` | `integer \| null` | Available stock; `null` means unlimited |

---

## 2. Create Checkout – Authenticated User

Creates a Stripe-hosted checkout session for a logged-in user.

### Request

```
POST /api/v1/shop/checkout
Authorization: ******
Content-Type: application/json
```

**Body:**

```json
{
  "items": [
    { "product_id": "uuid", "quantity": 1 },
    { "product_id": "uuid", "quantity": 2 }
  ],
  "address_id": "uuid-of-existing-address",
  "cancel_url": "/shop"
}
```

**OR** provide a new address instead of `address_id`:

```json
{
  "items": [
    { "product_id": "uuid", "quantity": 1 }
  ],
  "address": {
    "address_line_1": "123 High Street",
    "address_line_2": "Flat 4",
    "city": "London",
    "postcode": "SW1A 1AA",
    "country": "United Kingdom",
    "address_notes": "Leave with neighbour if out"
  },
  "cancel_url": "/shop"
}
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `items` | `CartItem[]` | ✅ | At least one item |
| `items[].product_id` | `string (uuid)` | ✅ | Must match a product `id` from `/products` |
| `items[].quantity` | `integer` | ✅ | Minimum 1 |
| `address_id` | `string (uuid)` | ✅ (or `address`) | ID of a previously saved address |
| `address` | `object` | ✅ (or `address_id`) | New delivery address – see fields below |
| `address.address_line_1` | `string` | ✅ | |
| `address.address_line_2` | `string` | ❌ | |
| `address.city` | `string` | ✅ | |
| `address.postcode` | `string` | ✅ | |
| `address.country` | `string` | ✅ | |
| `address.address_notes` | `string` | ❌ | |
| `cancel_url` | `string` | ❌ | Path to redirect to on cancel (default: `/`) |

> **Note:** Exactly one of `address_id` or `address` must be provided; providing both or neither returns a `422`.

### Response `200 OK`

```json
{
  "checkout_url": "https://checkout.stripe.com/pay/cs_test_xxxx",
  "session_id": "cs_test_xxxx",
  "metadata": {
    "user_id": "uuid",
    "order_id": "uuid",
    "address_id": "uuid",
    "checkout_type": "one_off_purchase"
  }
}
```

| Field | Type | Notes |
|---|---|---|
| `checkout_url` | `string` | **Redirect the user to this URL** to complete payment |
| `session_id` | `string` | Stripe checkout session ID – use to retrieve payment details after success |
| `metadata` | `object` | Internal metadata echoed back for reference |

### After Successful Payment

Redirect the user from Stripe to:
```
<FRONTEND_URL>/success?session_id=<session_id>
```

Fetch payment details using the existing endpoint:
```
POST /api/v1/payments/details
{ "session_id": "<session_id>" }
```

---

## 3. Create Checkout – Guest User

Creates a Stripe-hosted checkout session for an unauthenticated (guest) user. No account is required. The customer enters payment details on the Stripe-hosted page.

### Request

```
POST /api/v1/shop/checkout/guest
Content-Type: application/json
```

**Body:**

```json
{
  "guest_email": "jane@example.com",
  "items": [
    { "product_id": "uuid", "quantity": 1 }
  ],
  "address": {
    "address_line_1": "123 High Street",
    "city": "London",
    "postcode": "SW1A 1AA",
    "country": "United Kingdom"
  },
  "cancel_url": "/shop"
}
```

**OR** pass a previously created `address_id`:

```json
{
  "guest_email": "jane@example.com",
  "items": [{ "product_id": "uuid", "quantity": 1 }],
  "address_id": "uuid",
  "cancel_url": "/shop"
}
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `guest_email` | `string` | ✅ | Customer's email – shown on the Stripe checkout page and used for confirmation email |
| `items` | `CartItem[]` | ✅ | |
| `items[].product_id` | `string (uuid)` | ✅ | |
| `items[].quantity` | `integer` | ✅ | |
| `address_id` | `string (uuid)` | ✅ (or `address`) | |
| `address` | `object` | ✅ (or `address_id`) | See field descriptions above |
| `cancel_url` | `string` | ❌ | Default: `/` |

### Response `200 OK`

```json
{
  "checkout_url": "https://checkout.stripe.com/pay/cs_test_xxxx",
  "session_id": "cs_test_xxxx",
  "metadata": {
    "order_id": "uuid",
    "checkout_type": "one_off_purchase"
  }
}
```

---

## 4. Get Payment Details (existing endpoint)

Retrieve details of a completed payment using the Stripe session ID returned from a checkout.

### Request

```
POST /api/v1/payments/details
Authorization: ******
Content-Type: application/json
```

```json
{
  "session_id": "cs_test_xxxx"
}
```

### Response `200 OK`

```json
{
  "amount_total": 2999,
  "customer_email": "jane@example.com",
  "checkout_type": "one_off_purchase"
}
```

| Field | Type | Notes |
|---|---|---|
| `amount_total` | `integer` | Total charged in pence |
| `customer_email` | `string` | Customer email from Stripe |
| `checkout_type` | `string` | `"one_off_purchase"` for shop orders |

---

## Error Responses

All endpoints follow the same error shape:

```json
{
  "detail": "Human-readable error message"
}
```

| Status | Meaning |
|---|---|
| `401` | Missing or invalid auth token (authenticated endpoints only) |
| `422` | Validation error – check request body (e.g. both `address` and `address_id` provided) |
| `500` | Internal server error |

---

## Full Checkout Flow (Frontend)

### Authenticated User

```
1.  GET  /api/v1/shop/products
        → Display product list with prices

2.  User adds items to cart and selects/enters delivery address

3.  POST /api/v1/shop/checkout
        → Receive { checkout_url, session_id }

4.  Redirect browser to checkout_url (Stripe hosted page)

5.  Stripe redirects to <FRONTEND_URL>/success?session_id=<id>

6.  POST /api/v1/payments/details  { session_id }
        → Display confirmation with amount_total & customer_email
```

### Guest User

```
1.  GET  /api/v1/shop/products
        → Display product list

2.  User adds items, enters email & delivery address (no login required)

3.  POST /api/v1/shop/checkout/guest
        → Receive { checkout_url, session_id }

4.  Redirect browser to checkout_url

5.  Stripe redirects to <FRONTEND_URL>/success?session_id=<id>

6.  Show confirmation page (no further API call required;
    confirmation email is automatically sent to guest_email)
```

---

## Notes for Frontend

- **Prices are in pence.** Divide by `100` for pound display: `£${(price / 100).toFixed(2)}`
- **`product_id`** (UUID) is the field to use in checkout requests, not `stripe_price_id`.
- After a successful checkout, the backend automatically:
  - Updates the order status to `"paid"` in the database
  - Sends an order confirmation email to the customer
  - Notifies the Nappio team
- Stripe handles all PCI-compliant card data; the frontend never touches card numbers.
