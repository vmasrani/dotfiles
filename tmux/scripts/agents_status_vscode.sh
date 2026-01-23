#!/usr/bin/env bash
# Usage metrics for agents session (RHS only)

CACHE_FILE="/tmp/claude_usage_cache.json"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TZ="${TZ:-America/Vancouver}"

base="#24273a"
crust="#181926"
green="#a6da95"
peach="#f5a97f"
red="#ed8796"
overlay="#6e738d"
left_cap=""
right_cap=""

usage_color() {
    local val="${1%\%}"
    [[ -z "$val" || "$val" == "null" ]] && val=0
    if (( val < 50 )); then echo "$green"
    elif (( val <= 80 )); then echo "$peach"
    else echo "$red"
    fi
}

pill() {
    local color="$1"
    local content="$2"
    echo -n "#[fg=$color,bg=$base]$left_cap#[fg=$crust,bg=$color]$content#[fg=$color,bg=$base]$right_cap"
}

"$SCRIPT_DIR/agents_cache_refresh.sh" &>/dev/null &

five_hour="0"; seven_day="0"; credits="0"; reset_local=""

if [[ -f "$CACHE_FILE" ]]; then
    five_hour=$(jq -r '.five_hour // 0' "$CACHE_FILE" 2>/dev/null)
    seven_day=$(jq -r '.seven_day // 0' "$CACHE_FILE" 2>/dev/null)
    credits=$(jq -r '.credits // 0' "$CACHE_FILE" 2>/dev/null)
    reset_utc=$(jq -r '.five_hour_resets // empty' "$CACHE_FILE" 2>/dev/null)
    if [[ -n "$reset_utc" ]]; then
        if command -v gdate &>/dev/null; then
            reset_local=$(TZ="$TZ" gdate -d "$reset_utc" "+%-I%p" 2>/dev/null | tr '[:upper:]' '[:lower:]')
        else
            reset_local=$(TZ="$TZ" date -j -f "%Y-%m-%dT%H:%M:%S" "${reset_utc%%.*}" "+%-I%p" 2>/dev/null | tr '[:upper:]' '[:lower:]')
        fi
    fi
fi

[[ "$five_hour" == "null" ]] && five_hour="0"
[[ "$seven_day" == "null" ]] && seven_day="0"
[[ "$credits" == "null" ]] && credits="0"

output=""
output+="$(pill "$(usage_color "$five_hour")" " 5h ${five_hour}% ")"
output+="$(pill "$(usage_color "$seven_day")" " 7d ${seven_day}% ")"
output+="$(pill "$(usage_color "$credits")" " 󰠠 ${credits}% ")"
[[ -n "$reset_local" ]] && output+="$(pill "$overlay" " 󰦖 $reset_local ")"

echo "$output"
