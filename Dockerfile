FROM python:3.9-slim

WORKDIR /app

# Install required packages
RUN pip install --no-cache-dir google-cloud-storage google-cloud-kms

# Copy application files
COPY . /app

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Entry point for the application
ENTRYPOINT ["python", "main.py"]