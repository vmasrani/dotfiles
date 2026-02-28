#!/usr/bin/env bash
# SSH status widget for tmux — shows client IP + latency
# Outputs nothing when not in an SSH session (widget hides)

if [[ -z "$SSH_CLIENT" ]]; then
    echo ""
    exit 0
fi

# Extract client IP (first field of SSH_CLIENT)
client_ip="${SSH_CLIENT%% *}"

# Ping with 1s timeout, single packet
latency=$(ping -c 1 -W 1 "$client_ip" 2>/dev/null \
    | grep -oP 'time=\K[0-9.]+' \
    | head -1)

if [[ -n "$latency" ]]; then
    # Round to integer
    latency_int=$(printf "%.0f" "$latency")
    echo "${client_ip} ${latency_int}ms"
else
    echo "$client_ip"
fi
