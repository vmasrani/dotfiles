# Smart Pane Title - zsh hook integration
# Uses Claude Sonnet to generate contextual pane titles based on recent activity
#
# Usage: Add to .zshrc:
#   source ~/dotfiles/tools/smart-pane-title-hook.zsh
#
# Configuration (set before sourcing):
#   SMART_PANE_TITLE_ENABLED=1        # Enable/disable
#   SMART_PANE_TITLE_DEBOUNCE=15      # Seconds between updates
#   SMART_PANE_TITLE_MODEL="sonnet"   # Claude model to use

SMART_PANE_TITLE_ENABLED="${SMART_PANE_TITLE_ENABLED:-1}"
SMART_PANE_TITLE_DEBOUNCE="${SMART_PANE_TITLE_DEBOUNCE:-15}"
SMART_PANE_TITLE_MODEL="${SMART_PANE_TITLE_MODEL:-sonnet}"
SMART_PANE_TITLE_LAST_UPDATE=0
SMART_PANE_TITLE_LAST_HASH=""

_smart_pane_title_set() {
    local title="$1"
    [[ -z "$title" ]] && return
    [[ -z "${TMUX:-}" ]] && return

    # Set tmux pane title directly
    tmux select-pane -T "$title" 2>/dev/null || true
}

_smart_pane_title_generate_async() {
    local pane_id="${TMUX_PANE:-}"
    [[ -z "$pane_id" ]] && return

    # Run in background to not block prompt
    (
        local context="Directory: $(basename "$PWD")"

        # Add git branch if available
        if git rev-parse --git-dir &>/dev/null 2>&1; then
            local branch
            branch=$(git branch --show-current 2>/dev/null)
            [[ -n "$branch" ]] && context+="\nGit branch: $branch"
        fi

        # Add last 5 commands from history
        local cmds
        cmds=$(fc -l -n -5 2>/dev/null | sed 's/^[[:space:]]*//' | head -5)
        [[ -n "$cmds" ]] && context+="\nRecent commands:\n$cmds"

        # Add current process if not zsh
        local current_cmd
        current_cmd=$(tmux display-message -p -t "$pane_id" '#{pane_current_command}' 2>/dev/null)
        [[ -n "$current_cmd" && "$current_cmd" != "zsh" ]] && context+="\nRunning: $current_cmd"

        local prompt="Based on this terminal pane context, generate a SHORT (2-5 words max) descriptive title. Be specific about what work is being done. Output ONLY the title, nothing else.

Context:
$context"

        local title
        title=$(echo "$prompt" | claude -p --model "$SMART_PANE_TITLE_MODEL" 2>/dev/null | head -1 | tr -d '\n' | cut -c1-40)

        if [[ -n "$title" ]]; then
            # Write to pane-specific temp file
            echo "$title" > "/tmp/smart-pane-title-${pane_id//\%/}"
        fi
    ) &>/dev/null &
    disown
}

_smart_pane_title_check_result() {
    [[ -z "${TMUX_PANE:-}" ]] && return

    local result_file="/tmp/smart-pane-title-${TMUX_PANE//\%/}"
    if [[ -f "$result_file" ]]; then
        local title
        title=$(cat "$result_file")
        rm -f "$result_file"
        [[ -n "$title" ]] && _smart_pane_title_set "$title"
    fi
}

_smart_pane_title_precmd() {
    [[ "$SMART_PANE_TITLE_ENABLED" != "1" ]] && return
    [[ -z "${TMUX:-}" ]] && return

    # Only run in 'agents' session
    local session_name
    session_name=$(tmux display-message -p '#S' 2>/dev/null)
    [[ "$session_name" != "agents" ]] && return

    # Check for async result from previous command
    _smart_pane_title_check_result

    local now
    now=$(date +%s)

    # Debounce - only generate every N seconds
    local elapsed=$((now - SMART_PANE_TITLE_LAST_UPDATE))
    [[ $elapsed -lt $SMART_PANE_TITLE_DEBOUNCE ]] && return

    # Check if context changed (hash of pwd + last command)
    local current_hash
    current_hash="$(pwd):$(fc -l -n -1 2>/dev/null)"

    [[ "$current_hash" == "$SMART_PANE_TITLE_LAST_HASH" ]] && return

    SMART_PANE_TITLE_LAST_HASH="$current_hash"
    SMART_PANE_TITLE_LAST_UPDATE=$now

    # Generate new title asynchronously
    _smart_pane_title_generate_async
}

# Register the hook
autoload -Uz add-zsh-hook
add-zsh-hook precmd _smart_pane_title_precmd

# Commands to control it
pane-title-enable() { SMART_PANE_TITLE_ENABLED=1; echo "Smart pane title enabled"; }
pane-title-disable() { SMART_PANE_TITLE_ENABLED=0; echo "Smart pane title disabled"; }
pane-title-now() {
    SMART_PANE_TITLE_LAST_UPDATE=0
    SMART_PANE_TITLE_LAST_HASH=""
    _smart_pane_title_precmd
    echo "Pane title update triggered (async)"
}
pane-title-set() {
    [[ -z "$1" ]] && { echo "Usage: pane-title-set 'My Title'"; return 1; }
    tmux select-pane -T "$1"
    echo "Pane title set to: $1"
}
