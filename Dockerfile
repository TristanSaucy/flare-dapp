FROM python:3.9-slim

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Install required packages
# Note: web3>=6.0.0 includes ExtraDataToPOAMiddleware
RUN pip install --no-cache-dir google-cloud-storage google-cloud-kms google-cloud-logging requests flask google-cloud-aiplatform google-generativeai "web3>=6.0.0" python-dotenv

# Copy application files
COPY . /app

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Expose the web server port
EXPOSE 8080

# Entry point for the application
ENTRYPOINT ["python", "main.py"]