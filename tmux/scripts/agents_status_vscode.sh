#!/usr/bin/env bash
# Usage metrics for agents session (RHS only)

CACHE_FILE="/tmp/claude_usage_cache.json"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Auto-detect timezone: use TZ env var, or read from system
if [[ -z "$TZ" ]]; then
    if [[ -L /etc/localtime ]]; then
        TZ=$(readlink /etc/localtime | sed 's|.*/zoneinfo/||')
    elif [[ -f /etc/timezone ]]; then
        TZ=$(cat /etc/timezone)
    fi
fi

base="#24273a"
crust="#181926"
green="#a6da95"
red="#ed8796"
overlay="#6e738d"
left_cap=""
right_cap=""

# 10-level gradient from green to red based on usage percentage
usage_color() {
    local val="${1%\%}"
    [[ -z "$val" || "$val" == "null" ]] && val=0
    (( val > 100 )) && val=100
    # Quantize to 10 levels (0, 10, 20, ..., 100)
    local level=$(( (val + 5) / 10 * 10 ))
    lerp_color "$green" "$red" "$level"
}

# Interpolate between two hex colors based on ratio (0.0 = color1, 1.0 = color2)
lerp_color() {
    local c1="${1#\#}" c2="${2#\#}" ratio="$3"
    local r1=$((16#${c1:0:2})) g1=$((16#${c1:2:2})) b1=$((16#${c1:4:2}))
    local r2=$((16#${c2:0:2})) g2=$((16#${c2:2:2})) b2=$((16#${c2:4:2}))
    local r=$(( r1 + (r2 - r1) * ratio / 100 ))
    local g=$(( g1 + (g2 - g1) * ratio / 100 ))
    local b=$(( b1 + (b2 - b1) * ratio / 100 ))
    printf "#%02x%02x%02x" "$r" "$g" "$b"
}

# Color based on time remaining (faded when far, green when close)
countdown_color() {
    local secs="$1"
    local max_secs=$((5 * 60 * 60))  # 5 hours
    (( secs > max_secs )) && secs=$max_secs
    local ratio=$(( (max_secs - secs) * 100 / max_secs ))
    lerp_color "$overlay" "$green" "$ratio"
}

pill() {
    local color="$1"
    local content="$2"
    echo -n "#[fg=$color,bg=$base]$left_cap#[fg=$crust,bg=$color]$content#[fg=$color,bg=$base]$right_cap"
}

"$SCRIPT_DIR/agents_cache_refresh.sh" &>/dev/null &

five_hour="0"; seven_day="0"; credits="0"; reset_countdown=""; reset_secs=0

if [[ -f "$CACHE_FILE" ]]; then
    five_hour=$(jq -r '.five_hour // 0' "$CACHE_FILE" 2>/dev/null)
    seven_day=$(jq -r '.seven_day // 0' "$CACHE_FILE" 2>/dev/null)
    credits=$(jq -r '.credits // 0' "$CACHE_FILE" 2>/dev/null)
    reset_utc=$(jq -r '.five_hour_resets // empty' "$CACHE_FILE" 2>/dev/null)
    if [[ -n "$reset_utc" ]]; then
        now=$(date +%s)
        if command -v gdate &>/dev/null; then
            reset_epoch=$(gdate -d "$reset_utc" +%s 2>/dev/null)
        else
            reset_epoch=$(date -j -f "%Y-%m-%dT%H:%M:%S" "${reset_utc%%.*}" +%s 2>/dev/null)
        fi
        if [[ -n "$reset_epoch" ]] && (( reset_epoch > now )); then
            reset_secs=$((reset_epoch - now))
            hours=$((reset_secs / 3600))
            mins=$(((reset_secs % 3600) / 60))
            if (( hours > 0 )); then
                reset_countdown="${hours}h${mins}m"
            else
                reset_countdown="${mins}m"
            fi
        fi
    fi
fi

[[ "$five_hour" == "null" ]] && five_hour="0"
[[ "$seven_day" == "null" ]] && seven_day="0"
[[ "$credits" == "null" ]] && credits="0"

current_time=$(date "+%-I:%M%p" | tr '[:upper:]' '[:lower:]')

output=""
output+="$(pill "$(usage_color "$five_hour")" " 5h ${five_hour}% ")"
output+="$(pill "$(usage_color "$seven_day")" " 7d ${seven_day}% ")"
output+="$(pill "$(usage_color "$credits")" " 󰠠 ${credits}% ")"
[[ -n "$reset_countdown" ]] && output+="$(pill "$(countdown_color "$reset_secs")" " 󰦖 ${reset_countdown} ")"
output+="$(pill "$overlay" " 󰥔 ${current_time} ")"

echo "$output"
