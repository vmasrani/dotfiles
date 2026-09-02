#!/usr/bin/env bash
# Host status widget for tmux — shows user@shorthost, plus SSH client IP when remote.
set -euo pipefail

out="$(whoami)@$(hostname -s)"

if [[ -n "${SSH_CLIENT:-}" ]]; then
    client_ip="${SSH_CLIENT%% *}"
    out="${out} | ${client_ip}"
fi

echo "$out"
