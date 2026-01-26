#!/usr/bin/env bash
# Per-session status bar customization for agents session

session_name=$(tmux display-message -p '#S')

if [[ "$session_name" == "agents" ]]; then
    dir="$HOME/dotfiles/tmux/scripts"

    base="#24273a"
    crust="#181926"
    peach="#f5a97f"
    yellow="#eed49f"
    left_cap=""
    right_cap=""

    # Enable pane borders with titles for agents session
    tmux set-option pane-border-status top

    tmux set-option status-style "bg=$base,fg=#cad3f5"
    tmux set-option status-justify centre
    tmux set-option status-left-length 30
    tmux set-option status-right-length 200

    # Left: Crab pill (peach, yellow on prefix)
    tmux set-option status-left "\
#[fg=$peach,bg=$base]#{?client_prefix,#[fg=$yellow],}$left_cap\
#[fg=$crust,bg=$peach]#{?client_prefix,#[bg=$yellow],} 🦀 \
#[fg=$peach,bg=$base]#{?client_prefix,#[fg=$yellow],}$right_cap"

    # Right: Usage metrics only
    tmux set-option status-right "#($dir/agents_status_vscode.sh)"

    # Window list: non-current windows muted
    tmux set-option window-status-format "#[fg=#5b6078] #W "
    
    # Current window: Orange pill with icon, window name + agent count (bold)
    tmux set-option window-status-current-format "\
#[fg=$peach,bg=$base]$left_cap\
#[fg=$crust,bg=$peach,bold] #W · 󰚩 #($dir/agents_count.sh) \
#[fg=$peach,bg=$base]$right_cap"
    
    tmux set-option window-status-separator ""
else
    # Disable pane borders for non-agents sessions
    tmux set-option pane-border-status off
fi
