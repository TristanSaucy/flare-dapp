#!/bin/bash
# encrypt_key.sh - Encrypt Ethereum private key using values from .env

# Define print functions for better output
print_info() {
    echo -e "\033[0;34m[INFO]\033[0m $1"
}

print_success() {
    echo -e "\033[0;32m[SUCCESS]\033[0m $1"
}

print_error() {
    echo -e "\033[0;31m[ERROR]\033[0m $1"
}

# Load environment variables
if [ -f .env ]; then
    source .env
    print_info "Loaded environment variables from .env"
else
    print_error "No .env file found. Please create one with required variables."
    exit 1
fi

# Check required environment variables
if [ -z "$KEYRING_NAME" ] || [ -z "$KEY_NAME" ] || [ -z "$INPUT_BUCKET_NAME" ] || [ -z "$KEY_OBJECT_NAME" ]; then
    print_error "Missing required environment variables. Please check your .env file."
    print_info "Required variables: KEYRING_NAME, KEY_NAME, INPUT_BUCKET_NAME, KEY_OBJECT_NAME"
    exit 1
fi

# Ask user how they want to input the private key
echo "How would you like to input your Ethereum private key?"
echo "1) Type or paste it directly (visible input)"
echo "2) Provide a file containing the key"
echo -n "Enter your choice (1 or 2): "
read KEY_INPUT_CHOICE

PRIVATE_KEY=""

if [ "$KEY_INPUT_CHOICE" = "1" ]; then
    # Option 1: Direct input (visible)
    echo -n "Enter Ethereum private key (input will be visible): "
    read PRIVATE_KEY
    
    if [ -z "$PRIVATE_KEY" ]; then
        print_error "No private key entered. Exiting."
        exit 1
    fi
    
    # Create temporary file with private key
    print_info "Creating temporary file with private key..."
    echo -n "$PRIVATE_KEY" > private_key.txt
    
elif [ "$KEY_INPUT_CHOICE" = "2" ]; then
    # Option 2: File input
    echo -n "Enter the path to the file containing your private key: "
    read KEY_FILE_PATH
    
    if [ ! -f "$KEY_FILE_PATH" ]; then
        print_error "File not found: $KEY_FILE_PATH"
        exit 1
    fi
    
    # Copy the file content
    print_info "Reading private key from file..."
    cp "$KEY_FILE_PATH" private_key.txt
    
    # Read the key for validation
    PRIVATE_KEY=$(cat private_key.txt)
    if [ -z "$PRIVATE_KEY" ]; then
        print_error "The file appears to be empty. Exiting."
        rm private_key.txt
        exit 1
    fi
else
    print_error "Invalid choice. Please run the script again and select 1 or 2."
    exit 1
fi

# Encrypt the key
print_info "Encrypting the private key using KMS..."
if gcloud kms encrypt \
    --location=global \
    --keyring="$KEYRING_NAME" \
    --key="$KEY_NAME" \
    --plaintext-file=private_key.txt \
    --ciphertext-file=private_key.enc; then
    
    print_success "Private key encrypted successfully"
else
    print_error "Failed to encrypt private key"
    rm private_key.txt
    exit 1
fi

# Upload to GCS bucket
print_info "Uploading encrypted key to the input bucket..."
if gsutil cp private_key.enc "gs://$INPUT_BUCKET_NAME/$KEY_OBJECT_NAME"; then
    print_success "Private key uploaded successfully to gs://$INPUT_BUCKET_NAME/$KEY_OBJECT_NAME"
else
    print_error "Failed to upload encrypted key to bucket"
    rm private_key.txt private_key.enc
    exit 1
fi

# Clean up local files
print_info "Cleaning up local files..."
rm private_key.txt private_key.enc

print_success "Process completed successfully!"