#!/bin/bash
# encrypt_key.sh - Encrypt Ethereum private key using values from .env

# Load environment variables
source .env

# Prompt user for private key
echo -n "Enter Ethereum private key: "
read -s PRIVATE_KEY
echo ""  # Add a newline after input

# Encrypt and upload in one command
echo -n "$PRIVATE_KEY" | gcloud kms encrypt \
  --project="$PROJECT_ID" \
  --location="global" \
  --keyring="$KEYRING_NAME" \
  --key="$KEY_NAME" \
  --plaintext-file=- \
  --ciphertext-file=- | gsutil cp - "gs://$INPUT_BUCKET_NAME/$KEY_OBJECT_NAME"

echo "Private key encrypted and uploaded to gs://$INPUT_BUCKET_NAME/$KEY_OBJECT_NAME"