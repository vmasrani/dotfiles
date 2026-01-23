#!/usr/bin/env bash
# Usage metrics for agents session (RHS only)

CACHE_FILE="/tmp/claude_usage_cache.json"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Catppuccin Macchiato colors
base="#24273a" crust="#181926" green="#a6da95" red="#ed8796" overlay="#6e738d"
left_cap="" right_cap=""

# Interpolate between two hex colors (ratio: 0-100)
lerp() {
    local c1="${1#\#}" c2="${2#\#}" r="$3"
    printf "#%02x%02x%02x" \
        $((16#${c1:0:2} + (16#${c2:0:2} - 16#${c1:0:2}) * r / 100)) \
        $((16#${c1:2:2} + (16#${c2:2:2} - 16#${c1:2:2}) * r / 100)) \
        $((16#${c1:4:2} + (16#${c2:4:2} - 16#${c1:4:2}) * r / 100))
}

pill() {
    echo -n "#[fg=$1,bg=$base]$left_cap#[fg=$crust,bg=$1]$2#[fg=$1,bg=$base]$right_cap"
}

"$SCRIPT_DIR/agents_cache_refresh.sh" &>/dev/null &

# Parse all values with single jq call
eval "$(jq -r '"five_hour=\(.five_hour//0) seven_day=\(.seven_day//0) credits=\(.credits//0) reset_utc=\(.five_hour_resets//"")"' "$CACHE_FILE" 2>/dev/null)"
five_hour="${five_hour:-0}" seven_day="${seven_day:-0}" credits="${credits:-0}"

# Calculate countdown to reset
reset_countdown="" reset_secs=0
if [[ -n "$reset_utc" ]]; then
    now=$(date +%s)
    reset_epoch=$(gdate -d "$reset_utc" +%s 2>/dev/null || date -j -f "%Y-%m-%dT%H:%M:%S" "${reset_utc%%.*}" +%s 2>/dev/null)
    if [[ -n "$reset_epoch" ]] && (( reset_epoch > now )); then
        reset_secs=$((reset_epoch - now))
        ((reset_secs >= 3600)) && reset_countdown="$((reset_secs/3600))h$((reset_secs%3600/60))m" || reset_countdown="$((reset_secs/60))m"
    fi
fi

# Build output (usage: green->red gradient, countdown: overlay->green gradient)
output=""
output+="$(pill "$(lerp "$green" "$red" $((five_hour/10*10)))" " 5h ${five_hour}% ")"
output+="$(pill "$(lerp "$green" "$red" $((seven_day/10*10)))" " 7d ${seven_day}% ")"
output+="$(pill "$(lerp "$green" "$red" $((credits/10*10)))" " 󰠠 ${credits}% ")"
[[ -n "$reset_countdown" ]] && output+="$(pill "$(lerp "$overlay" "$green" $((100 - reset_secs * 100 / 18000)))" " 󰦖 $reset_countdown ")"
output+="$(pill "$overlay" " 󰥔 $(date "+%-I:%M%p" | tr '[:upper:]' '[:lower:]') ")"
echo "$output"
