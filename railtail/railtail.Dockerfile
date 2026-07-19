FROM alpine:latest

# Install runtime dependencies (socat, ca-certificates, iptables)
RUN apk add --no-cache \
    ca-certificates \
    iptables \
    ip6tables \
    socat

# Copy Tailscale binaries from the official Tailscale image
COPY --from=tailscale/tailscale:stable /usr/local/bin/tailscaled /usr/local/bin/tailscaled
COPY --from=tailscale/tailscale:stable /usr/local/bin/tailscale /usr/local/bin/tailscale

# Create directory for Tailscale state
RUN mkdir -p /var/run/tailscale /var/lib/tailscale

# Copy startup script
COPY --chmod=755 railtail/start.sh /start.sh


CMD ["/start.sh"]
