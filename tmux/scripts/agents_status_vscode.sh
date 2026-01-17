#!/usr/bin/env bash
# VS Code-inspired consolidated status line for agents session
# Output: ⚠ 2 waiting  —  4 agents  —  5h: 45%  —  7d: 72%  —  credits: 30%  —  resets 10pm pst

CACHE_FILE="/tmp/claude_usage_cache.json"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TZ="${TZ:-America/Vancouver}"

# Dracula colors (brighter for contrast)
muted="#bd93f9"
primary="#f8f8f2"
warning="#ffb86c"

# Usage color thresholds
usage_color() {
    local val="${1%\%}"
    [[ -z "$val" || "$val" == "null" ]] && val=0
    if (( val < 50 )); then
        echo "#4caf50"  # green
    elif (( val <= 80 )); then
        echo "#ff9800"  # amber
    else
        echo "#f44336"  # red
    fi
}

# Trigger cache refresh in background
"$SCRIPT_DIR/agents_cache_refresh.sh" &>/dev/null &

# --- Attention count ---
attention_count=0
panes=$(tmux list-panes -t agents -F "#{pane_id}" 2>/dev/null)
if [[ -n "$panes" ]]; then
    attention_count=$(echo "$panes" | xargs -P 4 -I {} sh -c '
        if tmux capture-pane -t {} -p 2>/dev/null | tail -5 | \
           grep -qE "^> $|^> .*\?$|waiting for.*input|What would you like|Enter.*:|Press enter"; then
            echo 1
        fi
    ' | wc -l | tr -d " ")
fi

# --- Agent count ---
agent_count=0
if [[ -n "$panes" ]]; then
    pane_cmds=$(tmux list-panes -t agents -F "#{pane_current_command}" 2>/dev/null)
    agent_count=$(echo "$pane_cmds" | grep -cE "^[0-9]+\.[0-9]+|claude|node" || echo 0)
fi

# --- Usage metrics from cache ---
five_hour="0"
seven_day="0"
credits="0"
reset_local=""

if [[ -f "$CACHE_FILE" ]]; then
    five_hour=$(jq -r '.five_hour // 0' "$CACHE_FILE" 2>/dev/null)
    seven_day=$(jq -r '.seven_day // 0' "$CACHE_FILE" 2>/dev/null)
    credits=$(jq -r '.credits // 0' "$CACHE_FILE" 2>/dev/null)

    # Reset time
    reset_utc=$(jq -r '.five_hour_resets // empty' "$CACHE_FILE" 2>/dev/null)
    if [[ -n "$reset_utc" ]]; then
        if command -v gdate &>/dev/null; then
            reset_local=$(TZ="$TZ" gdate -d "$reset_utc" "+%-I%p %Z" 2>/dev/null | tr '[:upper:]' '[:lower:]')
        else
            reset_local=$(TZ="$TZ" date -j -f "%Y-%m-%dT%H:%M:%S" "${reset_utc%%.*}" "+%-I%p %Z" 2>/dev/null | tr '[:upper:]' '[:lower:]')
        fi
    fi
fi

# Handle nulls
[[ "$five_hour" == "null" ]] && five_hour="0"
[[ "$seven_day" == "null" ]] && seven_day="0"
[[ "$credits" == "null" ]] && credits="0"

# --- Build status line ---
sep="#[fg=$muted] — #[fg=$primary]"
output=""

# Combined agent status: "X waiting, Y agents" or just "Y agents"
if (( attention_count > 0 )); then
    output+="#[fg=$warning]${attention_count} waiting#[fg=$primary], "
fi

if (( agent_count == 1 )); then
    output+="${agent_count} agent${sep}"
else
    output+="${agent_count} agents${sep}"
fi

# 5h usage
color_5h=$(usage_color "$five_hour")
output+="#[fg=$muted]5h: #[fg=$color_5h]${five_hour}%#[fg=$primary]${sep}"

# 7d usage
color_7d=$(usage_color "$seven_day")
output+="#[fg=$muted]7d: #[fg=$color_7d]${seven_day}%#[fg=$primary]${sep}"

# Credits
color_credits=$(usage_color "$credits")
output+="#[fg=$muted]credits: #[fg=$color_credits]${credits}%#[fg=$primary]"

# Reset time (only if available)
if [[ -n "$reset_local" ]]; then
    output+="${sep}#[fg=$muted]resets ${reset_local}#[fg=$primary]"
fi

echo "$output"
