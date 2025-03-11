#!/bin/bash
# Confidential Space Deployment Script
# This script helps deploy your application to a Confidential Space VM

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

# Function to print warning messages
print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
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
if [ -z "$PROJECT_ID" ] || [ -z "$REGION" ] || [ -z "$SERVICE_ACCOUNT_EMAIL" ] || [ -z "$POOL_NAME" ]; then
    print_error "Missing required environment variables. Please run scripts/setup_confidential_space.sh first."
    exit 1
fi

print_section "Confidential Space Deployment"
print_info "Project ID: $PROJECT_ID"
print_info "Region: $REGION"
print_info "Service Account: $SERVICE_ACCOUNT_EMAIL"

# Ask for VM name
read -p "Enter VM name (default: confidential-workload-vm): " VM_NAME
VM_NAME=${VM_NAME:-confidential-workload-vm}

# Ask for machine type
read -p "Enter machine type (default: n2d-standard-2): " MACHINE_TYPE
MACHINE_TYPE=${MACHINE_TYPE:-n2d-standard-2}

# Function to validate container image name
validate_container_image() {
    local image_name=$1
    if [[ ! "$image_name" =~ ^[a-z0-9.-]+/[a-z0-9.-]+/[a-z0-9.-]+:[a-z0-9.-]+$ && ! "$image_name" =~ ^gcr.io/[a-z0-9.-]+/[a-z0-9.-]+:[a-z0-9.-]+$ ]]; then
        print_error "Invalid container image name format. It should be in the format: gcr.io/PROJECT_ID/IMAGE_NAME:TAG or REGION-docker.pkg.dev/PROJECT_ID/REPO/IMAGE:TAG"
        return 1
    fi
    return 0
}

# Check if container image is already set in .env
if [ -z "$CONTAINER_IMAGE" ]; then
    # Ask for container image with validation
    while true; do
        read -p "Enter container image (default: gcr.io/$PROJECT_ID/confidential-app:latest): " CONTAINER_IMAGE
        CONTAINER_IMAGE=${CONTAINER_IMAGE:-gcr.io/$PROJECT_ID/confidential-app:latest}
        
        if validate_container_image "$CONTAINER_IMAGE"; then
            break
        fi
    done
    
    # Save to .env for future use
    if grep -q "CONTAINER_IMAGE=" .env; then
        sed -i "s|CONTAINER_IMAGE=.*|CONTAINER_IMAGE=\"$CONTAINER_IMAGE\"|" .env
    else
        echo "" >> .env
        echo "# Container image" >> .env
        echo "CONTAINER_IMAGE=\"$CONTAINER_IMAGE\"" >> .env
    fi
else
    print_info "Using container image from .env: $CONTAINER_IMAGE"
fi

# Check if image digest is available
if [ -z "$IMAGE_DIGEST" ]; then
    print_warning "No image digest found in .env file."
    print_info "The attestation verifier may not work correctly without an image digest."
    print_info "Consider building and pushing your container with scripts/build_and_push_container.sh first."
    
    read -p "Do you want to continue without an image digest? (y/n, default: n): " CONTINUE_WITHOUT_DIGEST
    CONTINUE_WITHOUT_DIGEST=${CONTINUE_WITHOUT_DIGEST:-n}
    
    if [[ "$CONTINUE_WITHOUT_DIGEST" != "y" ]]; then
        print_info "Exiting. Please run scripts/build_and_push_container.sh first to build and push your container."
        exit 0
    fi
else
    print_info "Using image digest from .env: $IMAGE_DIGEST"
fi

# Set up Workload Identity Binding
print_section "Setting up Workload Identity Binding"
print_info "Creating workload identity binding"

# Get the workload identity pool ID
WORKLOAD_IDENTITY_POOL_ID=$(gcloud iam workload-identity-pools describe "$POOL_NAME" --location=global --format="value(name)")

# Create the binding
print_info "Adding IAM policy binding for workload identity..."
gcloud iam service-accounts add-iam-policy-binding "$SERVICE_ACCOUNT_EMAIL" \
    --role="roles/iam.workloadIdentityUser" \
    --member="principalSet://iam.googleapis.com/${WORKLOAD_IDENTITY_POOL_ID}/attribute.tee_identity/CONFIDENTIAL_SPACE" || true

print_success "Workload identity binding created"

# Create a TEE VM
print_section "Creating Confidential Space VM"
print_info "Creating Confidential Space VM: $VM_NAME"

# Check if VM already exists
if gcloud compute instances describe "$VM_NAME" --zone="$REGION-a" &> /dev/null; then
    print_info "VM '$VM_NAME' already exists in zone '$REGION-a'"
    read -p "Do you want to delete and recreate it? (y/n): " RECREATE_VM
    if [[ "$RECREATE_VM" == "y" ]]; then
        print_info "Deleting existing VM..."
        gcloud compute instances delete "$VM_NAME" --zone="$REGION-a" --quiet
    else
        print_info "Skipping VM creation. Using existing VM."
        VM_CREATED=false
    fi
fi

# Create the VM if needed
if [[ "$VM_CREATED" != "false" ]]; then
    print_info "Creating VM with Confidential Computing enabled in DEBUG mode..."
    
    # Prepare metadata for the VM
    print_info "Preparing environment variables as metadata..."
    
    # Start with required TEE metadata
    METADATA="^~^tee-image-reference=$CONTAINER_IMAGE"
    METADATA="${METADATA}~tee-container-log-redirect=true"
    
    # Always add PROJECT_ID and REGION for Vertex AI
    METADATA="${METADATA}~PROJECT_ID=$PROJECT_ID"
    print_info "Added PROJECT_ID to metadata"
    
    METADATA="${METADATA}~REGION=$REGION"
    print_info "Added REGION to metadata"
    
    # Add environment variables from .env
    if [ ! -z "$INPUT_BUCKET_NAME" ]; then
        METADATA="${METADATA}~INPUT_BUCKET_NAME=$INPUT_BUCKET_NAME"
        print_info "Added INPUT_BUCKET_NAME to metadata"
    fi
    
    if [ ! -z "$RESULTS_BUCKET_NAME" ]; then
        METADATA="${METADATA}~RESULTS_BUCKET_NAME=$RESULTS_BUCKET_NAME"
        print_info "Added RESULTS_BUCKET_NAME to metadata"
    fi
    
    if [ ! -z "$KEY_OBJECT_NAME" ]; then
        METADATA="${METADATA}~KEY_OBJECT_NAME=$KEY_OBJECT_NAME"
        print_info "Added KEY_OBJECT_NAME to metadata"
    fi
    
    if [ ! -z "$KMS_KEY_NAME" ]; then
        METADATA="${METADATA}~KMS_KEY_NAME=$KMS_KEY_NAME"
        print_info "Added KMS_KEY_NAME to metadata"
    fi
    
    if [ ! -z "$POOL_NAME" ]; then
        METADATA="${METADATA}~POOL_NAME=$POOL_NAME"
        print_info "Added POOL_NAME to metadata"
    fi
    
    
    # Create the VM with error handling
    if ! gcloud compute instances create "$VM_NAME" \
        --project="$PROJECT_ID" \
        --zone="$REGION-a" \
        --machine-type="$MACHINE_TYPE" \
        --confidential-compute-type=SEV \
        --shielded-secure-boot \
        --scopes=cloud-platform \
        --maintenance-policy=MIGRATE \
        --min-cpu-platform="AMD Milan" \
        --image-project=confidential-space-images \
        --image-family=confidential-space-debug \
        --service-account="$SERVICE_ACCOUNT_EMAIL" \
        --metadata="$METADATA"; then
        
        print_error "Failed to create Confidential Space VM. Please check the error message above."
        exit 1
    fi
    
    print_success "Confidential Space VM created successfully with DEBUG mode enabled"
    print_info "Environment variables have been passed as metadata to the VM"
    
    # Create a firewall rule to allow access to the web server
    print_section "Setting up Firewall Rule"
    FIREWALL_RULE_NAME="allow-web-$VM_NAME"
    
    # Check if the firewall rule already exists
    if gcloud compute firewall-rules describe "$FIREWALL_RULE_NAME" --project="$PROJECT_ID" &> /dev/null; then
        print_info "Firewall rule '$FIREWALL_RULE_NAME' already exists"
    else
        print_info "Creating firewall rule to allow web access on port 8080..."
        if gcloud compute firewall-rules create "$FIREWALL_RULE_NAME" \
            --project="$PROJECT_ID" \
            --direction=INGRESS \
            --priority=1000 \
            --network=default \
            --action=ALLOW \
            --rules=tcp:8080 \
            --source-ranges=0.0.0.0/0 \
            --target-tags="$VM_NAME"; then
            print_success "Firewall rule created successfully"
        else
            print_warning "Failed to create firewall rule. You may need to manually allow access to port 8080."
        fi
    fi
    
    # Add network tag to the VM for the firewall rule
    print_info "Adding network tag to VM..."
    gcloud compute instances add-tags "$VM_NAME" \
        --project="$PROJECT_ID" \
        --zone="$REGION-a" \
        --tags="$VM_NAME"
    
    # Get the external IP of the VM
    EXTERNAL_IP=$(gcloud compute instances describe "$VM_NAME" \
        --project="$PROJECT_ID" \
        --zone="$REGION-a" \
        --format="value(networkInterfaces[0].accessConfigs[0].natIP)")
    
    if [ ! -z "$EXTERNAL_IP" ]; then
        print_success "VM external IP: $EXTERNAL_IP"
        print_info "Web interface will be available at: http://$EXTERNAL_IP:8080"
    else
        print_warning "Could not determine VM external IP"
    fi
fi

# Wait for VM to initialize
print_section "Waiting for VM Initialization"
print_info "Waiting for the VM to initialize (this may take a minute)..."
sleep 30  # Give the VM some time to start up

# Check VM status
VM_STATUS=$(gcloud compute instances describe "$VM_NAME" --zone="$REGION-a" --format="value(status)" 2>/dev/null || echo "UNKNOWN")
if [[ "$VM_STATUS" == "RUNNING" ]]; then
    print_success "VM is running"
else
    print_info "VM status: $VM_STATUS"
    print_info "The VM might still be initializing. You can check its status later."
fi

# Summary
print_section "Deployment Complete"
echo -e "${GREEN}Your application has been deployed to a Confidential Space VM!${NC}"
echo ""
echo -e "${BOLD}VM Name:${NC} $VM_NAME"
echo -e "${BOLD}Region:${NC} $REGION-a"
echo -e "${BOLD}Container Image:${NC} $CONTAINER_IMAGE"
if [ ! -z "$IMAGE_DIGEST" ]; then
    echo -e "${BOLD}Image Digest:${NC} $IMAGE_DIGEST"
fi
echo -e "${BOLD}Service Account:${NC} $SERVICE_ACCOUNT_EMAIL"

# Display web interface URL if available
if [ ! -z "$EXTERNAL_IP" ]; then
    echo -e "${BOLD}Web Interface:${NC} http://$EXTERNAL_IP:8080"
fi

echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo -e "1. Check VM status: ${BOLD}gcloud compute instances describe $VM_NAME --zone=$REGION-a${NC}"
echo -e "2. View logs: ${BOLD}gcloud compute instances get-serial-port-output $VM_NAME --zone=$REGION-a${NC}"
echo -e "3. SSH into the VM (for debugging): ${BOLD}gcloud compute ssh $VM_NAME --zone=$REGION-a${NC}"
if [ ! -z "$EXTERNAL_IP" ]; then
    echo -e "4. Access the web interface: ${BOLD}http://$EXTERNAL_IP:8080${NC}"
fi
echo ""
echo -e "${YELLOW}Note:${NC} The application is running in a Confidential Space environment."
echo -e "The container is isolated and protected by hardware-based confidential computing."
echo ""
echo -e "${YELLOW}Troubleshooting:${NC}"
echo -e "If your application isn't working as expected, check the logs using:"
echo -e "${BOLD}gcloud logging read \"resource.type=gce_instance AND resource.labels.instance_id=\$(gcloud compute instances describe $VM_NAME --zone=$REGION-a --format='value(id)')\" --limit=50${NC}"
echo "" 