#!/usr/bin/env bash
# Per-session status-format override for agents session
#
# Agents session: replaces powerkit-render center with agents_status_bar.sh
# and patches session pill to orange with crab icon.
# Other sessions: unsets override → falls back to powerkit's global rendering.

session_name=$(tmux display-message -p '#S')
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

if [[ "$session_name" == "agents" ]]; then
    base_format=$(tmux show-option -gqv 'status-format[0]')

    # 1. Swap powerkit-render center → agents_status_bar.sh
    pk_cmd=$(printf '%s' "$base_format" | sed -n 's|.*#(\([^)]*powerkit-render center\)).*|\1|p')
    if [[ -n "$pk_cmd" ]]; then
        agents_format="${base_format//$pk_cmd/${SCRIPT_DIR}/agents_status_bar.sh}"
    else
        agents_format="$base_format"
    fi

    # 2. Make session pill solid orange — replace color ternaries with #fab387
    #    Mocha: #{?client_prefix,#fab387,#{?pane_in_mode,#74c7ec,#cba6f7}}
    #    Macchiato: #{?client_prefix,#f5a97f,#{?pane_in_mode,#7dc4e4,#c6a0f6}}
    agents_format=$(printf '%s' "$agents_format" | sed 's/#{?client_prefix,#[a-f0-9]*,#{?pane_in_mode,#[a-f0-9]*,#[a-f0-9]*}}/#fab387/g')

    # 3. Replace icon ternary with crab emoji
    #    After color ternaries are gone, the remaining #{?client_prefix,...}} is the icon
    agents_format=$(printf '%s' "$agents_format" | sed 's/#{?client_prefix,[^}]*}}/🦀/g')

    tmux set-option 'status-format[0]' "$agents_format"
    tmux set-option pane-border-status top
else
    # Unset session-level overrides → fall back to powerkit's global
    tmux set-option -u 'status-format[0]' 2>/dev/null
    tmux set-option pane-border-status off
fi
