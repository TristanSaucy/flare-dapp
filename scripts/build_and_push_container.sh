#!/bin/bash
# Build and Push Docker Container Script
# This script builds and pushes the Docker container for the Confidential Space application

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

# Load environment variables if .env exists
if [ -f .env ]; then
    print_info "Loading configuration from .env file"
    source .env
else
    print_error "No .env file found. Please run setup_confidential_space.sh first."
    exit 1
fi

# Check if required variables are set
if [ -z "$PROJECT_ID" ]; then
    print_error "PROJECT_ID not found in .env file. Please run setup_confidential_space.sh first."
    exit 1
fi

# Check if Docker is installed
print_section "Checking Prerequisites"
if ! command_exists docker; then
    print_error "Docker is not installed. Please install Docker first."
    exit 1
fi
print_success "Docker is installed"

# Check if Docker daemon is running
if ! docker info &> /dev/null; then
    print_error "Docker daemon is not running. Please start Docker and try again."
    exit 1
fi
print_success "Docker daemon is running"

# Check if Dockerfile exists
if [ ! -f Dockerfile ]; then
    print_error "Dockerfile not found in the current directory"
    exit 1
fi
print_success "Dockerfile found"

# Ask for container image name
print_section "Container Configuration"
read -p "Enter container image name (default: confidential-app): " IMAGE_NAME
IMAGE_NAME=${IMAGE_NAME:-confidential-app}

read -p "Enter container tag (default: latest): " IMAGE_TAG
IMAGE_TAG=${IMAGE_TAG:-latest}

# Configure Artifact Registry
print_info "Configuring Artifact Registry"
read -p "Enter Artifact Registry location (default: $REGION): " AR_LOCATION
AR_LOCATION=${AR_LOCATION:-$REGION}

read -p "Enter Artifact Registry repository name (default: confidential-apps): " AR_REPO
AR_REPO=${AR_REPO:-confidential-apps}

REGISTRY="$AR_LOCATION-docker.pkg.dev"
FULL_IMAGE_NAME="$REGISTRY/$PROJECT_ID/$AR_REPO/$IMAGE_NAME:$IMAGE_TAG"

# Create Artifact Registry repository if it doesn't exist
print_info "Ensuring Artifact Registry repository exists"
gcloud artifacts repositories describe $AR_REPO --location=$AR_LOCATION --project=$PROJECT_ID &> /dev/null || \
gcloud artifacts repositories create $AR_REPO \
    --repository-format=docker \
    --location=$AR_LOCATION \
    --description="Confidential Space Applications" \
    --project=$PROJECT_ID

# Configure Docker to use the registry
print_info "Configuring Docker authentication for $REGISTRY"
gcloud auth configure-docker $AR_LOCATION-docker.pkg.dev --quiet

# Build the Docker image
print_section "Building Docker Container"
print_info "Building Docker image: $FULL_IMAGE_NAME"
print_info "This may take a few minutes..."

if docker build -t $FULL_IMAGE_NAME .; then
    print_success "Docker image built successfully"
else
    print_error "Failed to build Docker image"
    exit 1
fi

# Push the Docker image
print_section "Pushing Docker Container"
print_info "Pushing Docker image to $REGISTRY"
print_info "This may take a few minutes..."

if docker push $FULL_IMAGE_NAME; then
    print_success "Docker image pushed successfully to $FULL_IMAGE_NAME"
else
    print_error "Failed to push Docker image"
    exit 1
fi

# Get the image digest - improved method
print_info "Retrieving image digest..."
IMAGE_DIGEST=""

# Try to get the digest from Artifact Registry
IMAGE_DIGEST=$(gcloud artifacts docker images describe $FULL_IMAGE_NAME --location=$AR_LOCATION --format='value(image_summary.digest)' 2>/dev/null || echo "")

# If gcloud method fails, try docker inspect
if [[ -z "$IMAGE_DIGEST" ]]; then
    print_info "Trying alternative method to get image digest..."
    REPO_DIGEST=$(docker inspect --format='{{index .RepoDigests 0}}' $FULL_IMAGE_NAME 2>/dev/null || echo "")
    if [[ ! -z "$REPO_DIGEST" ]]; then
        IMAGE_DIGEST=$(echo $REPO_DIGEST | cut -d'@' -f2)
    fi
fi

if [[ -z "$IMAGE_DIGEST" ]]; then
    print_error "Could not retrieve image digest. The attestator may not work correctly."
    read -p "Enter image digest manually (if known): " IMAGE_DIGEST
fi

if [[ ! -z "$IMAGE_DIGEST" ]]; then
    print_success "Image digest retrieved: $IMAGE_DIGEST"
else
    print_info "No image digest available"
fi

# Update .env file with the image name and digest
print_section "Updating Configuration"
print_info "Updating .env file with container image information"

# Check if CONTAINER_IMAGE already exists in .env
if grep -q "CONTAINER_IMAGE=" .env; then
    # Replace existing CONTAINER_IMAGE line
    sed -i "s|CONTAINER_IMAGE=.*|CONTAINER_IMAGE=\"$FULL_IMAGE_NAME\"|" .env
else
    # Add CONTAINER_IMAGE to .env
    echo "" >> .env
    echo "# Container image" >> .env
    echo "CONTAINER_IMAGE=\"$FULL_IMAGE_NAME\"" >> .env
fi

# Add or update IMAGE_DIGEST in .env
if [[ ! -z "$IMAGE_DIGEST" ]]; then
    if grep -q "IMAGE_DIGEST=" .env; then
        # Replace existing IMAGE_DIGEST line
        sed -i "s|IMAGE_DIGEST=.*|IMAGE_DIGEST=\"$IMAGE_DIGEST\"|" .env
    else
        # Add IMAGE_DIGEST to .env
        echo "IMAGE_DIGEST=\"$IMAGE_DIGEST\"" >> .env
    fi
fi

print_success "Configuration updated"

# Update the attestation verifier
ATTESTATION_UPDATED=false
if [[ ! -z "$IMAGE_DIGEST" ]]; then
    print_section "Attestation Verification"
    print_info "The image digest has been saved to the .env file."
    print_info "Updating the attestation verifier with this digest..."
    
    # Check if update_attestation.sh exists and is executable
    if [ ! -f "scripts/update_attestation.sh" ]; then
        print_error "Attestation update script not found: scripts/update_attestation.sh"
        print_warning "The attestation verifier was not updated. This will prevent your application from running correctly."
        print_info "Please create the scripts/update_attestation.sh script or run the setup script again."
    else
        # Make the script executable if it's not already
        if [ ! -x "scripts/update_attestation.sh" ]; then
            print_info "Making attestation update script executable"
            chmod +x scripts/update_attestation.sh
        fi
        
        print_info "Updating attestation verifier..."
        ./scripts/update_attestation.sh
        ATTESTATION_UPDATED=true
    fi
else
    print_warning "No image digest was obtained. The attestation verifier cannot be updated."
    print_warning "This will prevent your application from running correctly in Confidential Space."
    print_info "Please try rebuilding the container to obtain a valid image digest."
fi

# Summary
print_section "Container Build Complete"
echo -e "${GREEN}Docker container has been built and pushed successfully!${NC}"
echo ""
echo -e "${BOLD}Container Image:${NC} $FULL_IMAGE_NAME"
if [[ ! -z "$IMAGE_DIGEST" ]]; then
    echo -e "${BOLD}Image Digest:${NC} $IMAGE_DIGEST"
fi
echo -e "${BOLD}Project ID:${NC} $PROJECT_ID"
echo ""

# Ask if user wants to deploy
echo -e "Would you like to deploy this container to a Confidential Space VM now?"
read -p "Deploy to Confidential Space? (y/n, default: y): " DEPLOY_NOW
DEPLOY_NOW=${DEPLOY_NOW:-y}

if [[ "$DEPLOY_NOW" == "y" ]]; then
    # Check if deploy script exists and is executable
    if [ ! -f "scripts/deploy_confidential_space.sh" ]; then
        print_error "Deployment script not found: scripts/deploy_confidential_space.sh"
        exit 1
    fi
    
    # Make the deployment script executable if it's not already
    if [ ! -x "scripts/deploy_confidential_space.sh" ]; then
        print_info "Making deployment script executable"
        chmod +x scripts/deploy_confidential_space.sh
    fi
    
    print_info "Starting deployment process..."
    ./scripts/deploy_confidential_space.sh
else
    echo ""
    echo -e "${YELLOW}Next steps:${NC}"
    echo -e "When you're ready to deploy, run: ${BOLD}./scripts/deploy_confidential_space.sh${NC}"
    echo ""
fi 