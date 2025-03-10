# Confidential Space Application

## Quick Start

```bash
# Clone the repository
git clone <repository-url>
cd <repository-directory>

# Make the setup script executable
chmod +x scripts/setup_confidential_space.sh

# Run the setup script to configure everything
./scripts/setup_confidential_space.sh
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
- `env_setup.py`: Utility for loading environment variables
- `Dockerfile`: Container definition for the application
- `requirements.txt`: Python dependencies
- `scripts/`: Directory containing all the scripts for setup and deployment
  - `setup_confidential_space.sh`: Script to set up all prerequisites
  - `build_and_push_container.sh`: Script to build and push the Docker container
  - `deploy_confidential_space.sh`: Script to deploy the application to a Confidential Space VM
  - `update_attestation.sh`: Script to update the attestation verifier with a new image digest

## Prerequisites

- Google Cloud SDK (gcloud)
- Docker
- Python 3.9+
- A Google Cloud account with billing enabled

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
   ```

## License

This project is licensed under the terms of the LICENSE file included in the repository.