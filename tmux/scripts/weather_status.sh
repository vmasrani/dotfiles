#!/usr/bin/env bash
# Weather status for tmux status bar using wttr.in
# Caches result for 30 minutes to avoid excessive API calls

CACHE_FILE="/tmp/tmux_weather_cache"
CACHE_TTL=1800  # 30 minutes in seconds

# Return cached value if fresh enough
if [[ -f "$CACHE_FILE" ]]; then
  age=$(( $(date +%s) - $(stat -f %m "$CACHE_FILE" 2>/dev/null || echo 0) ))
  if (( age < CACHE_TTL )); then
    cat "$CACHE_FILE"
    exit 0
  fi
fi

# Fetch weather: condition + temp (e.g. "☀️ 18°C")
result=$(curl -sf --max-time 3 "wttr.in/?format=%c+%t" 2>/dev/null | sed 's/+//g; s/  */ /g; s/^ *//; s/ *$//')

if [[ -n "$result" ]]; then
  echo "$result" > "$CACHE_FILE"
  echo "$result"
else
  # Return stale cache if fetch fails
  [[ -f "$CACHE_FILE" ]] && cat "$CACHE_FILE" || echo "N/A"
fi
