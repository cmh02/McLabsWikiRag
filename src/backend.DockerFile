# Use a lightweight python image
FROM python:3.11-slim

# Install system dependencies needed for Tailscale and general operations
RUN apt-get update && apt-get upgrade -y && \
    apt-get install -y --no-install-recommends curl ca-certificates iptables ip6tables && \
    rm -rf /var/lib/apt/lists/*

# Copy Tailscale binaries from the official Tailscale image
COPY --from=tailscale/tailscale:stable /usr/local/bin/tailscaled /usr/local/bin/tailscaled
COPY --from=tailscale/tailscale:stable /usr/local/bin/tailscale /usr/local/bin/tailscale

# Create necessary directories for Tailscale state and runtime
RUN mkdir -p /var/run/tailscale /var/cache/tailscale /var/lib/tailscale

# Set the working directory
WORKDIR /app

# Copy the requirements file and install python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application files
COPY . .

# Make the start script executable
RUN chmod +x /app/src/start.sh

# Set entrypoint to the startup script
CMD ["/app/src/start.sh"]
