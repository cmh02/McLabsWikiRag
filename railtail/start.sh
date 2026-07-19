#!/bin/sh

# Ensure logs flush instantly
export PYTHONUNBUFFERED=1

pids=""

# Start tailscaled in userspace mode and expose a SOCKS5 server on port 1055
echo "Starting tailscaled..."
tailscaled \
  --tun=userspace-networking \
  --statedir=/var/lib/tailscale \
  --socks5-server=localhost:1055 \
  --outbound-http-proxy-listen=localhost:1055 &

tailscale_pid=$!
pids="$pids $tailscale_pid"

# Wait for tailscaled socket to be ready
sleep 2

# Authenticate with Tailscale
if [ -n "$TAILSCALE_AUTHKEY" ]; then
    echo "Authenticating Tailscale with TAILSCALE_AUTHKEY..."
    tailscale up --authkey="$TAILSCALE_AUTHKEY" --hostname="${TAILSCALE_HOSTNAME:-railtail-proxy}"
elif [ -n "$TS_AUTHKEY" ]; then
    echo "Authenticating Tailscale with TS_AUTHKEY..."
    tailscale up --authkey="$TS_AUTHKEY" --hostname="${TAILSCALE_HOSTNAME:-railtail-proxy}"
else
    echo "Warning: TAILSCALE_AUTHKEY / TS_AUTHKEY is not set. Skipping tailscale authentication."
fi

# Set up port forwarders
if [ -z "$PROXY_MAPPINGS" ]; then
    echo "Error: PROXY_MAPPINGS environment variable is not defined!"
    exit 1
fi

echo "Parsing PROXY_MAPPINGS: $PROXY_MAPPINGS"
OLD_IFS="$IFS"
IFS=','
for mapping in $PROXY_MAPPINGS; do
    # Trim leading/trailing whitespace
    mapping=$(echo "$mapping" | tr -d '[:space:]')
    [ -z "$mapping" ] && continue

    local_port=$(echo "$mapping" | cut -d':' -f1)
    target_host=$(echo "$mapping" | cut -d':' -f2)
    target_port=$(echo "$mapping" | cut -d':' -f3)

    echo "Forwarding internal port $local_port -> $target_host:$target_port (via SOCKS5)..."
    # Listen on IPv4 (0.0.0.0)
    socat TCP-LISTEN:$local_port,fork,reuseaddr SOCKS5:127.0.0.1:$target_host:$target_port,socksport=1055 &
    pids="$pids $!"
    
    # Listen on IPv6 (::) only to prevent port collision with IPv4 listener
    socat TCP6-LISTEN:$local_port,fork,reuseaddr,ipv6only=1 SOCKS5:127.0.0.1:$target_host:$target_port,socksport=1055 &
    pids="$pids $!"
done
IFS="$OLD_IFS"

# Monitor background jobs
echo "All processes started (PIDs: $pids). Monitoring..."
while true; do
    for pid in $pids; do
        if ! kill -0 "$pid" 2>/dev/null; then
            echo "Process $pid has exited. Terminating container."
            exit 1
        fi
    done
    sleep 2
done
