# Confidential Space Application

## Prerequisites

- Google Cloud SDK (gcloud)
- Docker
- Python 3.9+
- A Google Cloud account with billing enabled

  
## Quick Start

```bash
# Clone the repository
git clone <repository-url>
cd <repository-directory>

# Make the setup script executable
chmod +x scripts/setup_confidential_space.sh

# Run the setup script to configure everything
./scripts/setup_confidential_space.sh

# Encrypt a key for use with the application
./scripts/encrypt_key.sh

```

The setup script will guide you through the entire process:
1. Create a Google Cloud project
2. Set up all required resources (KMS, storage, service accounts)
3. Build and push your container to Artifact Registry
4. Deploy your application to a Confidential Space VM

## What is Confidential Space?

Confidential Space is a Google Cloud solution that enables secure multi-party computation. It provides:

- Hardware-based isolation using AMD SEV (Secure Encrypted Virtualization)
- Memory encryption to protect data in use
- Cryptographic attestation to verify the integrity of the workload
- Secure access to cloud resources based on the workload's identity

## Project Structure

- `main.py`: The main Python application that runs in the Confidential Space
- `Dockerfile`: Container definition for the application
- `requirements.txt`: Python dependencies
- `scripts/`: Directory containing all the scripts for setup and deployment
  - `setup_confidential_space.sh`: Script to set up all prerequisites
  - `build_and_push_container.sh`: Script to build and push the Docker container
  - `deploy_confidential_space.sh`: Script to deploy the application to a Confidential Space VM
  - `update_attestation.sh`: Script to update the attestation verifier with a new image digest
  - `monitor_cs_vm.sh`: Interactive script to monitor a Confidential Space VM
  - `rebuild_and_redeploy.sh`: Script to quickly rebuild and redeploy after making changes

## Detailed Setup Instructions

If you prefer to run each step manually instead of using the guided setup:

1. Set up the prerequisites:
   ```
   ./scripts/setup_confidential_space.sh
   ```
   
   This script will:
   - Create a new GCP project (or use an existing one)
   - Enable required APIs
   - Create a service account with necessary permissions
   - Set up Cloud KMS for encryption/decryption
   - Create storage buckets
   - Configure workload identity for Confidential Space
   - Create a sample encrypted key
   - Generate a `.env` file with your configuration

2. Build and push the Docker container:
   ```
   ./scripts/build_and_push_container.sh
   ```

3. Deploy the application to a Confidential Space VM:
   ```
   ./scripts/deploy_confidential_space.sh
   ```

4. Update the attestation verifier (if needed):
   ```
   ./scripts/update_attestation.sh
   ```

5. Monitor your Confidential Space VM:
   ```
   ./scripts/monitor_cs_vm.sh
   ```
   This interactive script provides various options to monitor your VM and view logs.

## How It Works

1. The application runs in a Confidential Space VM with hardware-based isolation
2. It authenticates to Google Cloud using workload identity federation
3. It downloads an encrypted key from a GCP Storage bucket
4. It decrypts the key using Google Cloud KMS
5. It uses the decrypted key for its operations

## Security Considerations

- The key is only decrypted inside the Confidential Space
- The application's memory is encrypted by the hardware
- Access to cloud resources is based on the workload's identity and attestation
- Even Google administrators cannot access the decrypted data

## Customization

You can customize the application by modifying:

- `main.py`: Implement your specific application logic
- `Dockerfile`: Add additional dependencies or configuration
- Environment variables: Modify the `.env` file to change configuration

## Troubleshooting

If you encounter issues:

1. Check the VM logs:
   ```
   gcloud compute instances get-serial-port-output <vm-name> --zone=<zone>
   ```

2. Check the container status:
   ```
   gcloud compute instances describe <vm-name> --zone=<zone> --format='get(status)'
   ```

3. Check the container logs:
   ```
   gcloud logging read "resource.type=gce_instance AND resource.labels.instance_id=$(gcloud compute instances describe <vm-name> --zone=<zone> --format='value(id)')"
   ```

## ChatBot Overview

### Introduction

Our AI-powered chatbot provides a seamless interface for interacting with SparkDEX, a decentralized exchange on the Flare network. The chatbot combines natural language processing with blockchain functionality to make DeFi more accessible to users of all experience levels.

### Key Capabilities

#### Token Swapping
- Execute token swaps directly through conversation
- Get real-time price quotes before confirming transactions
- Set custom slippage tolerance to protect your trades
- View transaction status and confirmation details

#### Liquidity Management
- Add liquidity to pools with simple commands
- Create new liquidity pools when needed
- View your active liquidity positions
- Monitor pool performance and statistics

#### Market Information
- Get current token prices and exchange rates
- View detailed pool information including fees, liquidity, and price ranges
- Access historical trading data and volume statistics
- Monitor market trends across different token pairs

#### Wallet Integration
- Connect securely to your blockchain wallet
- Check token balances across multiple assets
- View transaction history
- Receive notifications about important account activities

#### Educational Resources
- Learn about DeFi concepts through interactive explanations
- Access guides on using SparkDEX features
- Receive personalized recommendations based on your experience level
- Get answers to frequently asked questions about blockchain and trading

### Technical Features

- **Secure Authentication**: Connect your wallet without exposing private keys
- **Real-time Data**: Access up-to-date blockchain information
- **Transaction Simulation**: Preview transaction outcomes before execution
- **Gas Optimization**: Recommendations for optimal gas settings
- **Multi-chain Support**: Interact with multiple blockchain networks
- **Contextual Memory**: The bot remembers your preferences and previous interactions

### Getting Started

To start using the chatbot, simply type a greeting or ask a question about SparkDEX. Here are some example commands to try:

- "What's the current price of FLR?"
- "I want to swap 10 USDC for FLR"
- "Show me the WFLR/USDC pool details"
- "Add liquidity to the FLR/USDC pool"
- "What are my current liquidity positions?"
- "Explain how concentrated liquidity works"

The chatbot will guide you through any complex processes and confirm important actions before execution.

### Feedback and Support

We're constantly improving our chatbot based on user feedback. If you encounter any issues or have suggestions for new features, please let us know through the feedback button or by opening an issue in this repository.

## License

This project is licensed under the terms of the LICENSE file included in the repository.
