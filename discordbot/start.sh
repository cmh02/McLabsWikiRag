#!/bin/sh

# Ensure Python flushes logs instantly so you can see them in Railway
export PYTHONUNBUFFERED=1

# Start tailscaled in the background with userspace networking.
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
    tailscale up --authkey="$TAILSCALE_AUTHKEY" --hostname="${TAILSCALE_HOSTNAME_DISCORD:-railway-discord}"
elif [ -n "$TS_AUTHKEY" ]; then
    echo "Authenticating Tailscale with TS_AUTHKEY..."
    tailscale up --authkey="$TS_AUTHKEY" --hostname="${TAILSCALE_HOSTNAME_DISCORD:-railway-discord}"
else
    echo "Warning: TAILSCALE_AUTHKEY / TS_AUTHKEY is not set. Skipping tailscale authentication."
fi

# -------------------------------------------------------------------------
# CRITICAL FIX: We removed global HTTP_PROXY/HTTPS_PROXY/ALL_PROXY exports.
# This prevents your Discord bot traffic from getting hijacked by Tailscale.
# -------------------------------------------------------------------------

# Run the discord bot start command with explicitly enabled log capture
echo "Starting discord bot application!"
exec uvicorn discordbot.bot:app --host :: --port ${RAILWAY_DISCORD_PORT:-${PORT:-3000}} --log-level info --workers 1
