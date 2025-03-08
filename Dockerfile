FROM alpine:latest
WORKDIR /app
COPY . /app
# Update this to point to your actual entry point or executable
# ENTRYPOINT ["/app/your-actual-executable"]
# For now, just use a simple command to keep the container running
CMD ["tail", "-f", "/dev/null"]