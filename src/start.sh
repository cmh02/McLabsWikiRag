#!/bin/sh

# Start tailscaled in the background with userspace networking.
# We also setup SOCKS5 and HTTP proxies on port 1055.
echo "Starting tailscaled..."
tailscaled \
  --tun=userspace-networking \
  --statedir=/var/lib/tailscale \
  --socks5-server=localhost:1055 \
  --outbound-http-proxy-listen=localhost:1055 &

# Wait for tailscaled socket to be ready
sleep 2

# Authenticate with Tailscale if an auth key is provided
if [ -n "$TAILSCALE_AUTHKEY" ]; then
    echo "Authenticating Tailscale with TAILSCALE_AUTHKEY..."
    tailscale up --authkey="$TAILSCALE_AUTHKEY" --hostname="${TAILSCALE_HOSTNAME:-mclabs-wiki-gpt}"
elif [ -n "$TS_AUTHKEY" ]; then
    echo "Authenticating Tailscale with TS_AUTHKEY..."
    tailscale up --authkey="$TS_AUTHKEY" --hostname="${TAILSCALE_HOSTNAME:-mclabs-wiki-gpt}"
else
    echo "Warning: TAILSCALE_AUTHKEY / TS_AUTHKEY is not set. Skipping tailscale authentication."
fi

# Set proxy environment variables so the app can route traffic through Tailscale
export HTTP_PROXY="http://localhost:1055"
export HTTPS_PROXY="http://localhost:1055"
export ALL_PROXY="socks5://localhost:1055"

# Run the backend API start command
echo "Starting backend application!"
exec uvicorn src.api:app --host :: --port "${PORT:-5000}"
