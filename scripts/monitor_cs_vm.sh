#!/bin/bash
# Monitor Confidential Space VM
# This script helps monitor a Confidential Space VM and its logs

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

# Load environment variables if .env exists
if [ -f .env ]; then
    print_info "Loading configuration from .env file"
    source .env
else
    print_error "No .env file found. Please run scripts/setup_confidential_space.sh first."
    exit 1
fi

# Check if required variables are set
if [ -z "$PROJECT_ID" ] || [ -z "$REGION" ]; then
    print_error "Missing required environment variables. Please run scripts/setup_confidential_space.sh first."
    exit 1
fi

# Ask for VM name if not provided
if [ -z "$1" ]; then
    read -p "Enter VM name (default: confidential-workload-vm): " VM_NAME
    VM_NAME=${VM_NAME:-confidential-workload-vm}
else
    VM_NAME=$1
fi

# Set zone
ZONE="${REGION}-a"

print_section "Monitoring Confidential Space VM: $VM_NAME"
print_info "Project: $PROJECT_ID"
print_info "Zone: $ZONE"

# Check if VM exists
if ! gcloud compute instances describe "$VM_NAME" --zone="$ZONE" --project="$PROJECT_ID" &> /dev/null; then
    print_error "VM '$VM_NAME' does not exist in zone '$ZONE'"
    exit 1
fi

# Get VM status
VM_STATUS=$(gcloud compute instances describe "$VM_NAME" --zone="$ZONE" --project="$PROJECT_ID" --format="value(status)")
print_info "VM Status: $VM_STATUS"

# Get VM ID for logging
VM_ID=$(gcloud compute instances describe "$VM_NAME" --zone="$ZONE" --project="$PROJECT_ID" --format="value(id)")
print_info "VM ID: $VM_ID"

# Menu for monitoring options
while true; do
    print_section "Monitoring Options"
    echo "1. View VM status"
    echo "2. View serial port output (last 50 lines)"
    echo "3. View application logs (last 20 lines)"
    echo "4. View error logs only"
    echo "5. View TEE guest agent logs"
    echo "6. Stream logs in real-time (Ctrl+C to stop)"
    echo "7. Exit"
    echo ""
    
    read -p "Select an option (1-7): " OPTION
    
    case $OPTION in
        1)
            print_section "VM Status"
            gcloud compute instances describe "$VM_NAME" --zone="$ZONE" --project="$PROJECT_ID" --format="table(name,status,machineType.basename(),creationTimestamp)"
            ;;
        2)
            print_section "Serial Port Output (last 50 lines)"
            gcloud compute instances get-serial-port-output "$VM_NAME" --zone="$ZONE" --project="$PROJECT_ID" | tail -n 50
            ;;
        3)
            print_section "Application Logs (last 20 lines)"
            gcloud logging read "resource.type=gce_instance AND resource.labels.instance_id=$VM_ID" --project="$PROJECT_ID" --limit=20
            ;;
        4)
            print_section "Error Logs Only"
            gcloud logging read "resource.type=gce_instance AND severity>=ERROR AND resource.labels.instance_id=$VM_ID" --project="$PROJECT_ID" --limit=10
            ;;
        5)
            print_section "TEE Guest Agent Logs"
            gcloud logging read "resource.type=gce_instance AND logName:projects/$PROJECT_ID/logs/tee-guest-agent AND resource.labels.instance_id=$VM_ID" --project="$PROJECT_ID" --limit=20
            ;;
        6)
            print_section "Streaming Logs (Ctrl+C to stop)"
            print_info "Streaming logs in real-time..."
            gcloud logging read "resource.type=gce_instance AND resource.labels.instance_id=$VM_ID" --project="$PROJECT_ID" --limit=10 --format='default' --freshness=1d --follow
            ;;
        7)
            print_info "Exiting..."
            exit 0
            ;;
        *)
            print_error "Invalid option. Please select 1-7."
            ;;
    esac
    
    echo ""
    read -p "Press Enter to continue..."
done 