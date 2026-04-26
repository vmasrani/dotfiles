#!/usr/bin/env bash
# SSH status widget for tmux — shows client IP + latency
# Outputs nothing when not in an SSH session (widget hides)

if [[ -z "$SSH_CLIENT" ]]; then
    echo ""
    exit 0
fi

# Extract client IP (first field of SSH_CLIENT)
client_ip="${SSH_CLIENT%% *}"

# Cache latency result for 60s to avoid blocking the status bar on every refresh.
# Many client IPs (home NATs) drop ICMP, so the ping always times out at 1s —
# that 1s stall would hit every tmux status-interval (default 15s) otherwise.
cache="/tmp/tmux-ssh-status-$USER"
if [[ -f "$cache" && $(( $(date +%s) - $(stat -c %Y "$cache") )) -lt 60 ]]; then
    cat "$cache"
    exit 0
fi

latency=$(timeout 0.3 ping -c 1 -W 1 "$client_ip" 2>/dev/null \
    | grep -oP 'time=\K[0-9.]+' \
    | head -1)

if [[ -n "$latency" ]]; then
    latency_int=$(printf "%.0f" "$latency")
    out="${client_ip} ${latency_int}ms"
else
    out="$client_ip"
fi

echo "$out" | tee "$cache"
