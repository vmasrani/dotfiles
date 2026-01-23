#!/usr/bin/env bash
# Per-session status bar customization
# Switches between dracula-inspired agents status and normal dracula status

session_name=$(tmux display-message -p '#S')

if [[ "$session_name" == "agents" ]]; then
    dir="$HOME/dotfiles/tmux/scripts"

    # Catppuccin Macchiato color palette
    bg="#494d64"           # surface1
    dark_gray="#24273a"    # base
    white="#cad3f5"        # text
    light_purple="#c6a0f6" # mauve
    dark_purple="#8087a2"  # overlay1
    orange="#f5a97f"       # peach
    yellow="#eed49f"       # yellow
    green="#a6da95"        # green

    # Powerline separator (U+E0B0)
    left_sep=""

    # Status bar background and general style
    tmux set-option status-style "bg=$bg,fg=$white"
    tmux set-option status-justify centre

    # Left side: Claude emoji with powerline segment + prefix highlight (matches Dracula format)
    # #{?client_prefix,...,...} changes color when prefix is pressed
    tmux set-option status-left "#[bg=${bg},fg=${orange}]#[bg=${orange},fg=${dark_gray}]#{?client_prefix,#[bg=${yellow}],} 🦀 #[fg=${orange},bg=${bg}]#{?client_prefix,#[fg=${yellow}],}${left_sep}"
    tmux set-option status-left-length 20
    tmux set-option status-right-length 200

    # Centered status line from consolidated script
    tmux set-option status-right "#($dir/agents_status_vscode.sh)"

    # Window list styling (orange to match crab)
    tmux set-option window-status-format "#[fg=$dark_purple] #I:#W "
    tmux set-option window-status-current-format "#[fg=$orange,bold] #I:#W "
    tmux set-option window-status-separator ""
else
    # Non-agents session: Let the main .tmux.conf handle the status bar
    # No action needed - catppuccin plugin sets it up automatically
    :
fi
