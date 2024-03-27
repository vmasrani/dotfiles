#!/bin/bash

# Usage: show-tmux-popup.sh popup_name

popup_name=$1
if [ -z "$popup_name" ]; then
    echo "Please provide a popup name."
    exit 1
fi

session="_popup_${popup_name}_$(tmux display -p '#S')"

if ! tmux has-session -t "$session" 2>/dev/null; then
    parent_session="$(tmux display -p '#{session_id}')"
    session_id="$(tmux new-session -dP -s "$session" -F '#{session_id}' -e TMUX_PARENT_SESSION="$parent_session")"
    tmux set-option -s -t "$session_id" key-table popup
    tmux set-option -s -t "$session_id" status off
    tmux set-option -s -t "$session_id" prefix None
else
    session_id="$session"
fi

exec tmux attach-session -t "$session_id" >/dev/null


# #!/bin/bash

# session="_popup_$(tmux display -p '#S')"

# if ! tmux has -t "$session" 2>/dev/null; then
# 	parent_session="$(tmux display -p '#{session_id}')"
# 	session_id="$(tmux new-session -dP -s "$session" -F '#{session_id}' -e TMUX_PARENT_SESSION="$parent_session")"
# 	tmux set-option -s -t "$session_id" key-table popup
# 	tmux set-option -s -t "$session_id" status off
# 	tmux set-option -s -t "$session_id" prefix None
# 	session="$session_id"
# fi

# exec tmux attach -t "$session" >/dev/null
