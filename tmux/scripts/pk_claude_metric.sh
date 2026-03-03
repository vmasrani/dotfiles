#!/usr/bin/env bash
# Powerkit-compatible Claude usage metric script
# Usage: pk_claude_metric.sh <metric>
# Metrics: five_hour, seven_day, opus, sonnet, credits, reset
#
# Reads from shared cache (agents_cache_refresh.sh handles updates).
# Outputs plain text with short label — powerkit handles all rendering/colors.

set -e

CACHE_FILE="/tmp/claude_usage_cache.json"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
metric="${1:-five_hour}"

# Trigger background cache refresh (atomic lock prevents stampede)
"$SCRIPT_DIR/agents_cache_refresh.sh" &>/dev/null &

# Bail if no cache yet
[[ ! -f "$CACHE_FILE" ]] && exit 0

if [[ "$metric" == "reset" ]]; then
    reset_utc=$(jq -r '.five_hour_resets // empty' "$CACHE_FILE" 2>/dev/null)
    [[ -z "$reset_utc" ]] && exit 0

    now=$(date +%s)
    reset_epoch=$(gdate -d "$reset_utc" +%s 2>/dev/null || \
                  date -j -f "%Y-%m-%dT%H:%M:%S" "${reset_utc%%.*}" +%s 2>/dev/null)
    [[ -z "$reset_epoch" ]] && exit 0
    (( reset_epoch <= now )) && exit 0

    secs=$((reset_epoch - now))
    if (( secs >= 3600 )); then
        printf '%dh%dm' $((secs/3600)) $((secs%3600/60))
    else
        printf '%dm' $((secs/60))
    fi
else
    val=$(jq -r ".${metric} // 0" "$CACHE_FILE" 2>/dev/null)
    val="${val:-0}"

    # Short label so each pill is self-documenting
    case "$metric" in
        five_hour) printf '5h %s%%' "$val" ;;
        seven_day) printf '7d %s%%' "$val" ;;
        opus)      printf 'opus %s%%' "$val" ;;
        sonnet)    printf 'sonnet %s%%' "$val" ;;
        credits)   printf '%s%%' "$val" ;;
        *)         printf '%s%%' "$val" ;;
    esac
fi
