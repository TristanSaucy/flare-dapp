#!/bin/bash
# Confidential Space Setup Script
# This script helps set up all prerequisites for running a confidential space application

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

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check prerequisites
print_section "Checking Prerequisites"

# Check if gcloud is installed
if ! command_exists gcloud; then
    print_error "gcloud CLI is not installed. Please install it from: https://cloud.google.com/sdk/docs/install"
    exit 1
fi
print_success "gcloud CLI is installed"

# Check if user is logged in to gcloud
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" >/dev/null 2>&1; then
    print_info "You need to log in to Google Cloud"
    gcloud auth login
fi
print_success "Logged in to Google Cloud as $(gcloud auth list --filter=status:ACTIVE --format="value(account)")"

# Collect information from user
print_section "Project Configuration"

# Function to create a project with retry logic
create_project() {
    local project_id=$1
    print_info "Creating project: $project_id"
    
    if gcloud projects create "$project_id" --name="Confidential Space Project" 2>/dev/null; then
        print_success "Project created successfully"
        return 0
    else
        print_error "Project ID '$project_id' is already in use or invalid"
        return 1
    fi
}

# Ask for project ID with retry logic
while true; do
    read -p "Enter a unique project ID (e.g., my-confidential-project-123): " PROJECT_ID
    
    if [[ -z "$PROJECT_ID" ]]; then
        print_error "Project ID cannot be empty"
        continue
    fi
    
    # Try to create the project
    if create_project "$PROJECT_ID"; then
        break
    else
        read -p "Do you want to use an existing project with this ID? (y/n): " USE_EXISTING
        if [[ "$USE_EXISTING" == "y" ]]; then
            print_info "Using existing project: $PROJECT_ID"
            break
        fi
        
        print_info "Please enter a different project ID"
    fi
done

# Set the current project
gcloud config set project "$PROJECT_ID"
print_success "Set current project to $PROJECT_ID"

# Check and enable billing once before any resource creation
print_section "Checking Billing Status"
if ! gcloud beta billing projects describe "$PROJECT_ID" >/dev/null 2>&1; then
    print_info "Billing is not enabled for this project"
    print_info "You need to enable billing to continue"
    print_info "Opening billing page in browser..."
    gcloud alpha billing projects link "$PROJECT_ID" --billing-account=$(gcloud alpha billing accounts list --format="value(name)" | head -1) || true
    
    # Check again if billing is enabled
    if ! gcloud beta billing projects describe "$PROJECT_ID" >/dev/null 2>&1; then
        print_info "Please visit https://console.cloud.google.com/billing/linkedaccount?project=$PROJECT_ID to enable billing"
        read -p "Press Enter once you've enabled billing..."
    fi
fi
print_success "Billing is enabled for project $PROJECT_ID"

# Enable required APIs
print_section "Enabling Required APIs"
print_info "Enabling required APIs (this may take a few minutes)..."
gcloud services enable cloudkms.googleapis.com \
    storage.googleapis.com \
    artifactregistry.googleapis.com \
    iamcredentials.googleapis.com \
    confidentialcomputing.googleapis.com
print_success "APIs enabled successfully"

# Ask for region
read -p "Enter region (default: us-central1): " REGION
REGION=${REGION:-us-central1}

# Ask for service account name
read -p "Enter service account name (default: cs-service-account): " SERVICE_ACCOUNT_NAME
SERVICE_ACCOUNT_NAME=${SERVICE_ACCOUNT_NAME:-cs-service-account}

# Ask for KMS keyring name
read -p "Enter KMS keyring name (default: cs-keyring): " KEYRING_NAME
KEYRING_NAME=${KEYRING_NAME:-cs-keyring}

# Ask for KMS key name
read -p "Enter KMS key name (default: cs-key): " KEY_NAME
KEY_NAME=${KEY_NAME:-cs-key}

# Function to create a bucket with retry logic
create_bucket() {
    local bucket_name=$1
    local region=$2
    
    print_info "Creating bucket: $bucket_name"
    
    if gsutil mb -l "$region" "gs://$bucket_name" 2>/dev/null; then
        print_success "Bucket created successfully"
        return 0
    else
        print_error "Bucket name '$bucket_name' is already taken or invalid"
        return 1
    fi
}

# Ask for input bucket name with retry logic
print_section "Creating Storage Buckets"
while true; do
    read -p "Enter input bucket name (default: ${PROJECT_ID}-input): " INPUT_BUCKET_NAME
    INPUT_BUCKET_NAME=${INPUT_BUCKET_NAME:-${PROJECT_ID}-input}
    
    # Try to create the input bucket
    if create_bucket "$INPUT_BUCKET_NAME" "$REGION"; then
        break
    else
        print_info "Please enter a different input bucket name"
    fi
done

# Ask for results bucket name with retry logic
while true; do
    read -p "Enter results bucket name (default: ${PROJECT_ID}-results): " RESULTS_BUCKET_NAME
    RESULTS_BUCKET_NAME=${RESULTS_BUCKET_NAME:-${PROJECT_ID}-results}
    
    # Try to create the results bucket
    if create_bucket "$RESULTS_BUCKET_NAME" "$REGION"; then
        break
    else
        print_info "Please enter a different results bucket name"
    fi
done

# Ask for encrypted key object name
read -p "Enter encrypted key object name (default: encrypted-key.enc): " KEY_OBJECT_NAME
KEY_OBJECT_NAME=${KEY_OBJECT_NAME:-encrypted-key.enc}

# Create service account
print_section "Creating Service Account"
print_info "Creating service account: $SERVICE_ACCOUNT_NAME"
gcloud iam service-accounts create "$SERVICE_ACCOUNT_NAME" \
    --display-name="Confidential Space Service Account" || true
SERVICE_ACCOUNT_EMAIL="${SERVICE_ACCOUNT_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
print_success "Service account created: $SERVICE_ACCOUNT_EMAIL"

# Create KMS keyring and key
print_section "Setting up Cloud KMS"
print_info "Creating KMS keyring: $KEYRING_NAME"
gcloud kms keyrings create "$KEYRING_NAME" --location=global || true

print_info "Creating KMS key: $KEY_NAME"
gcloud kms keys create "$KEY_NAME" \
    --location=global \
    --keyring="$KEYRING_NAME" \
    --purpose=encryption || true

# Grant encryption permissions to the current user
CURRENT_USER=$(gcloud auth list --filter=status:ACTIVE --format="value(account)")
print_info "Granting encryption permissions to $CURRENT_USER"
gcloud kms keys add-iam-policy-binding \
    "projects/$PROJECT_ID/locations/global/keyRings/$KEYRING_NAME/cryptoKeys/$KEY_NAME" \
    --member="user:$CURRENT_USER" \
    --role="roles/cloudkms.cryptoKeyEncrypter"

# Grant decryption permissions to the service account
print_info "Granting decryption permissions to $SERVICE_ACCOUNT_EMAIL"
gcloud kms keys add-iam-policy-binding \
    "projects/$PROJECT_ID/locations/global/keyRings/$KEYRING_NAME/cryptoKeys/$KEY_NAME" \
    --member="serviceAccount:$SERVICE_ACCOUNT_EMAIL" \
    --role="roles/cloudkms.cryptoKeyDecrypter"

print_success "KMS setup completed"

# Grant access to service account
print_info "Granting access to service account"
gsutil iam ch "serviceAccount:$SERVICE_ACCOUNT_EMAIL:objectViewer" "gs://$INPUT_BUCKET_NAME"
gsutil iam ch "serviceAccount:$SERVICE_ACCOUNT_EMAIL:objectCreator" "gs://$RESULTS_BUCKET_NAME"

print_success "Storage buckets created and permissions set"

# Create workload identity pool for confidential space
print_section "Setting up Workload Identity for Confidential Space"
print_info "Creating workload identity pool"
POOL_NAME="cs-pool"
gcloud iam workload-identity-pools create "$POOL_NAME" \
    --location=global || true

print_info "Creating provider for the pool"
gcloud iam workload-identity-pools providers create-oidc attestation-verifier \
    --location=global \
    --workload-identity-pool="$POOL_NAME" \
    --issuer-uri="https://confidentialcomputing.googleapis.com/" \
    --allowed-audiences="https://sts.googleapis.com" \
    --attribute-mapping="google.subject=assertion.sub" || true

print_success "Workload identity setup completed"

# Create a sample key file for demonstration
print_section "Creating Sample Key File"
print_info "Creating a sample key file for demonstration"
echo "This is a sample secret key" > sample_key.txt

print_info "Encrypting the sample key file using KMS"
gcloud kms encrypt \
    --location=global \
    --keyring="$KEYRING_NAME" \
    --key="$KEY_NAME" \
    --plaintext-file=sample_key.txt \
    --ciphertext-file=encrypted_key.enc

print_info "Uploading encrypted key to the input bucket"
gsutil cp encrypted_key.enc "gs://$INPUT_BUCKET_NAME/$KEY_OBJECT_NAME"

print_info "Cleaning up local files"
rm sample_key.txt encrypted_key.enc

print_success "Sample key file created, encrypted, and uploaded"

# Create .env file
print_section "Creating Environment File"
print_info "Creating .env file with configuration"

cat > .env << EOF
# Project configuration
PROJECT_ID="$PROJECT_ID"
REGION="$REGION"

# Service account
SERVICE_ACCOUNT_NAME="$SERVICE_ACCOUNT_NAME"
SERVICE_ACCOUNT_EMAIL="$SERVICE_ACCOUNT_EMAIL"

# KMS configuration
KEYRING_NAME="$KEYRING_NAME"
KEY_NAME="$KEY_NAME"
KMS_KEY_NAME="projects/$PROJECT_ID/locations/global/keyRings/$KEYRING_NAME/cryptoKeys/$KEY_NAME"

# Storage configuration
INPUT_BUCKET_NAME="$INPUT_BUCKET_NAME"
RESULTS_BUCKET_NAME="$RESULTS_BUCKET_NAME"
KEY_OBJECT_NAME="$KEY_OBJECT_NAME"

# Workload identity
POOL_NAME="$POOL_NAME"
EOF

print_success ".env file created with your configuration"

# Summary
print_section "Setup Complete"
echo -e "${GREEN}Confidential Space prerequisites have been set up successfully!${NC}"
echo ""
echo -e "${BOLD}Project ID:${NC} $PROJECT_ID"
echo -e "${BOLD}Service Account:${NC} $SERVICE_ACCOUNT_EMAIL"
echo -e "${BOLD}KMS Key:${NC} projects/$PROJECT_ID/locations/global/keyRings/$KEYRING_NAME/cryptoKeys/$KEY_NAME"
echo -e "${BOLD}Input Bucket:${NC} gs://$INPUT_BUCKET_NAME"
echo -e "${BOLD}Results Bucket:${NC} gs://$RESULTS_BUCKET_NAME"
echo -e "${BOLD}Encrypted Key:${NC} gs://$INPUT_BUCKET_NAME/$KEY_OBJECT_NAME"
echo ""
echo -e "Your configuration has been saved to the ${BOLD}.env${NC} file."
echo -e "You can now build and deploy your confidential space application."
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo -e "1. Build your Docker container: ${BOLD}docker build -t gcr.io/$PROJECT_ID/confidential-app:latest .${NC}"
echo -e "2. Push to Artifact Registry: ${BOLD}docker push gcr.io/$PROJECT_ID/confidential-app:latest${NC}"
echo -e "3. Deploy to Confidential Space: See documentation for deployment instructions"
echo "" 