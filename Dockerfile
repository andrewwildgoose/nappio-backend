FROM python:3.13-slim

# Set working directory
WORKDIR /app

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Create project structure
RUN mkdir -p api ios email_serv

# Copy files maintaining project structure
COPY admin_serv/subscriptions.py admin_serv/
COPY api/main.py api/
COPY api/admin_routes.py api/
COPY config/supabase.py config/
COPY email_serv/email_processor.py email_serv/
COPY email_serv/email_utils.py email_serv/
COPY ios/io_db.py ios/
COPY models/admin_models.py models/
COPY models/payment_models.py models/
COPY models/user_models.py models/
COPY payment_serv/webhook_handlers.py payment_serv/
COPY payment_serv/payment_processor.py payment_serv/
COPY product_serv/stripe_product_sync.py product_serv/
COPY product_serv/subscription_builder.py product_serv/
COPY user_serv/user_service.py user_serv/

# Set environment variables
ENV PYTHONPATH=/app
ENV PORT=8080

# Expose the port
EXPOSE 8080

# Run the application
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8080", "--proxy-headers"]