#!/bin/zsh
# Last command capture for tmux status bar (per pane)

_tmux_capture_last_cmd() {
    [[ -z "$TMUX" ]] && return

    local pane_id
    pane_id=$(tmux display-message -p '#{pane_id}')
    [[ -z "$pane_id" ]] && return

    local safe_pane_id="${pane_id#%}"
    local cmd_dir="/tmp/tmux_last_cmd"
    [[ ! -d "$cmd_dir" ]] && mkdir -p "$cmd_dir"

    # $1 is the command about to be executed
    echo "$1" >| "${cmd_dir}/${safe_pane_id}"
}

autoload -Uz add-zsh-hook
add-zsh-hook preexec _tmux_capture_last_cmd
