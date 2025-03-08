#!/bin/bash

# Note: The Dockerfile has been updated to copy the entire project directory
# instead of just a single file. You'll need to update the ENTRYPOINT in the
# Dockerfile to point to your actual executable once it's available.

docker build -t \
    us-central1-docker.pkg.dev/onyx-sequencer-452900-i3/flare-dapp/flare-dapp:latest .

docker push \
    us-central1-docker.pkg.dev/onyx-sequencer-452900-i3/flare-dapp/flare-dapp:latest