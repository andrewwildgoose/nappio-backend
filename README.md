# Nappio Backend Service

Welcome to the backend repository for the **Nappio** reusable nappy subscription service! This repository contains the FastAPI backend for handling customer subscriptions, product management, and payment processing through Stripe.

## Tech Stack

- **FastAPI**: Web framework for building the API.
- **Supabase**: Provides database and authentication.
- **Stripe**: Handles payments, including subscription billing.
- **PostgreSQL**: Database for storing customer and subscription data (provided by Supabase).
- **DigitalOcean App Platform**: Hosting the backend API on the cloud.

## Features

- User authentication using **Supabase**.
- Subscription management (start, pause, cancel) using **Stripe**.
- Customer management (profile creation, updates).
- Payment processing for one-off purchases and subscription-based products.
- Email notifications for various customer interactions (order confirmation, subscription reminders).

## Setup

Follow these steps to get the backend up and running locally:

### Prerequisites

- Python 3.9+ installed.
- Git installed.
- A GitHub account with SSH access set up (for cloning the repo).
- A **Supabase** account and **project** for authentication and database.
- A **Stripe** account for payment processing.

### 1. Clone the Repository

```bash
git clone git@github.com:your-username/backend-repo.git
cd backend-repo
```

### 2. Set Up Python Environment

We recommend using a virtual environment for this project:

```bash
python -m venv venv
source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
```

### 3. Install Dependencies

Install the necessary dependencies using pip:

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Create a .env file in the root of the project with the following keys (replace with your actual keys):

```bash
SUPABASE_URL=your_supabase_url
SUPABASE_API_KEY=your_supabase_api_key
STRIPE_SECRET_KEY=your_stripe_secret_key
SENDGRID_API_KEY=your_sendgrid_api_key
```

- SUPABASE_URL and SUPABASE_API_KEY are provided when you set up your Supabase project.
- STRIPE_SECRET_KEY is obtained from your Stripe account.
- SENDGRID_API_KEY is needed if you plan to send emails via SendGrid.

### 5. Run the FastAPI Backend Locally

You can run the application locally for development:

```bash
uvicorn main:app --reload
```

This will start the backend on http://localhost:8000.

### 6. Database Setup

The application uses Supabase as the database. To set up the database schema, follow these steps:

- Log in to your Supabase account and create a new project.
- Create a table for storing customer data and subscription info (e.g., users, subscriptions).
- Update your Supabase connection settings in .env to match your project details.

### 7. Test the API

You can test the endpoints using tools like Postman or curl. The FastAPI documentation can be accessed at:

```bash
http://localhost:8000/docs
```

### Endpoints

- POST /signup: Register a new user with Supabase authentication.
- GET /user: Get the currently logged-in user's details.
- POST /subscribe: Subscribe a user to a reusable nappy plan via Stripe.
- POST /unsubscribe: Unsubscribe a user from the subscription service.
- GET /subscriptions: Get the subscription details for a user.

### Deployment

The backend is deployed using DigitalOcean App Platform. Once your changes are ready, follow these steps to push them live:

- Commit your changes to the main branch.
- Push your changes to GitHub.
- DigitalOcean will automatically deploy the updated application.

### Troubleshooting

If you encounter any issues with the backend setup, consider the following:

- Environment Variables: Double-check that all keys and URLs are correctly placed in the .env file.
- Database Connection: Make sure your Supabase project is active and accessible.
- Stripe: Ensure that your Stripe account is set up with proper credentials for testing payments.

### Future Features

- Integration with a frontend (SvelteKit) for a full customer experience.
- Additional payment methods and subscription plans.
- Marketing and transactional email capabilities via SendGrid.