#!/usr/bin/env bash
# Get agent count for center pill
panes=$(tmux list-panes -t agents -F "#{pane_current_command}" 2>/dev/null)
count=$(echo "$panes" | grep -cE "^[0-9]+\.[0-9]+|claude|node" 2>/dev/null || echo 0)
if (( count == 1 )); then
    echo "1 agent"
else
    echo "$count agents"
fi
