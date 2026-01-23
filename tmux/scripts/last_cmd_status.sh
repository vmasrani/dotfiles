#!/usr/bin/env bash
# Get last executed command for tmux status bar (per pane)

MAX_LENGTH=40

get_last_cmd() {
    local pane_id="${1#%}"
    local cmd_file="/tmp/tmux_last_cmd/${pane_id}"

    if [[ -f "$cmd_file" && -r "$cmd_file" ]]; then
        local cmd
        cmd=$(head -1 "$cmd_file" 2>/dev/null)
        [[ -z "$cmd" ]] && return

        if [[ ${#cmd} -gt $MAX_LENGTH ]]; then
            echo "❯ ${cmd:0:$((MAX_LENGTH - 1))}…"
        else
            echo "❯ $cmd"
        fi
    fi
}

pane_id="${1:-$(tmux display-message -p '#{pane_id}')}"
get_last_cmd "$pane_id"
