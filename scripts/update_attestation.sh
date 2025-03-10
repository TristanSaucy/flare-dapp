#!/bin/bash
# Update Attestation Verifier Script
# This script updates the attestation verifier with the image digest

set -e  # Exit on any error

# Text formatting
BOLD='\033[1m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Function to print section headers
print_section() {
    echo -e "\n${BOLD}${BLUE}=== $1 ===${NC}\n"
}

# Function to print success messages
print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

# Function to print info messages
print_info() {
    echo -e "${YELLOW}ℹ $1${NC}"
}

# Function to print error messages
print_error() {
    echo -e "${RED}✗ $1${NC}"
}

# Load environment variables
if [ -f .env ]; then
    print_info "Loading configuration from .env file"
    source .env
else
    print_error "No .env file found. Please run scripts/setup_confidential_space.sh first."
    exit 1
fi

# Check if required variables are set
if [ -z "$PROJECT_ID" ] || [ -z "$POOL_NAME" ] || [ -z "$SERVICE_ACCOUNT_EMAIL" ]; then
    print_error "Missing required environment variables. Please run scripts/setup_confidential_space.sh first."
    exit 1
fi

print_section "Attestation Verifier Update"
print_info "Project ID: $PROJECT_ID"
print_info "Workload Identity Pool: $POOL_NAME"
print_info "Service Account: $SERVICE_ACCOUNT_EMAIL"

# Check if we have an image digest
if [ -z "$IMAGE_DIGEST" ]; then
    print_error "No image digest found in .env file."
    print_info "Please build and push your container first using build_and_push_container.sh"
    print_info "Or manually add IMAGE_DIGEST to your .env file."
    
    read -p "Do you want to enter an image digest manually? (y/n): " ENTER_DIGEST
    if [[ "$ENTER_DIGEST" == "y" ]]; then
        read -p "Enter image digest (without 'sha256:' prefix): " IMAGE_DIGEST
        
        # Update .env file with the image digest
        if grep -q "IMAGE_DIGEST=" .env; then
            sed -i "s|IMAGE_DIGEST=.*|IMAGE_DIGEST=\"$IMAGE_DIGEST\"|" .env
        else
            echo "IMAGE_DIGEST=\"$IMAGE_DIGEST\"" >> .env
        fi
    else
        exit 1
    fi
fi

print_info "Using image digest: $IMAGE_DIGEST"

# Check if the attestation verifier exists
print_info "Checking if attestation verifier exists"
if ! gcloud iam workload-identity-pools providers describe attestation-verifier \
    --location=global \
    --workload-identity-pool="$POOL_NAME" &>/dev/null; then
    
    print_error "Attestation verifier not found. Please run scripts/setup_confidential_space.sh first."
    exit 1
fi

# Create the attestation condition
ATTESTATION_CONDITION="assertion.submods.container.image_digest == '$IMAGE_DIGEST' \
&& '$SERVICE_ACCOUNT_EMAIL' in assertion.google_service_accounts \
&& assertion.swname == 'CONFIDENTIAL_SPACE' \
&& 'STABLE' in assertion.submods.confidential_space.support_attributes"

# Update the attestation verifier
print_info "Updating attestation verifier with image digest"
gcloud iam workload-identity-pools providers update-oidc attestation-verifier \
    --location=global \
    --workload-identity-pool="$POOL_NAME" \
    --attribute-condition="$ATTESTATION_CONDITION"

print_success "Attestation verifier updated successfully"

# Summary
print_section "Update Complete"
echo -e "${GREEN}Attestation verifier has been updated with the image digest!${NC}"
echo ""
echo -e "${BOLD}Project ID:${NC} $PROJECT_ID"
echo -e "${BOLD}Workload Identity Pool:${NC} $POOL_NAME"
echo -e "${BOLD}Service Account:${NC} $SERVICE_ACCOUNT_EMAIL"
echo -e "${BOLD}Image Digest:${NC} $IMAGE_DIGEST"
echo ""
echo -e "${YELLOW}Note:${NC} The attestation verifier will now only allow workloads with this exact image digest."
echo -e "If you rebuild your container, you will need to run this script again with the new digest."
echo "" 