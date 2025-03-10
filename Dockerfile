FROM python:3.9-slim

WORKDIR /app

# Install required packages
RUN pip install --no-cache-dir google-cloud-storage google-cloud-kms google-cloud-logging requests flask google-cloud-aiplatform google-generativeai

# Copy application files
COPY . /app

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Expose the web server port
EXPOSE 8080

# Entry point for the application
ENTRYPOINT ["python", "main.py"]