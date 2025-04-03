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
COPY api/main.py api/
COPY ios/io_db.py ios/
COPY email_serv/email_processor.py email_serv/

# Set environment variables
ENV PYTHONPATH=/app
ENV PORT=8080

# Expose the port
EXPOSE 8080

# Run the application
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8080", "--proxy-headers"]