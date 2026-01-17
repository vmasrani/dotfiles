#!/usr/bin/env bash
# Central cache refresh for Claude usage data
# Uses mkdir as atomic lock (works on macOS and Linux)

CACHE_FILE="/tmp/claude_usage_cache.json"
LOCK_DIR="/tmp/claude_usage_cache.lock"
CACHE_TTL=60

# Quick exit if cache is fresh
if [[ -f "$CACHE_FILE" ]]; then
    cache_age=$(( $(date +%s) - $(stat -f%m "$CACHE_FILE" 2>/dev/null || stat -c%Y "$CACHE_FILE" 2>/dev/null || echo 0) ))
    [[ $cache_age -lt $CACHE_TTL ]] && exit 0
fi

# Try to acquire lock (mkdir is atomic)
mkdir "$LOCK_DIR" 2>/dev/null || exit 0
trap 'rmdir "$LOCK_DIR" 2>/dev/null' EXIT

# Double-check cache after acquiring lock
if [[ -f "$CACHE_FILE" ]]; then
    cache_age=$(( $(date +%s) - $(stat -f%m "$CACHE_FILE" 2>/dev/null || stat -c%Y "$CACHE_FILE" 2>/dev/null || echo 0) ))
    [[ $cache_age -lt $CACHE_TTL ]] && exit 0
fi

# Get OAuth token
creds=$(security find-generic-password -s "Claude Code-credentials" -w 2>/dev/null)
token=$(echo "$creds" | jq -r '.claudeAiOauth.accessToken // empty' 2>/dev/null)

if [[ -z "$token" ]]; then
    echo '{"five_hour":0,"seven_day":0,"credits":0}' > "$CACHE_FILE"
    exit 0
fi

# Fetch and parse in one jq call
response=$(curl -s --max-time 5 "https://api.anthropic.com/api/oauth/usage" \
    -H "Authorization: Bearer $token" \
    -H "anthropic-beta: oauth-2025-04-20" \
    -H "Accept: application/json")

# Parse all values in single jq invocation
echo "$response" | jq '{
    five_hour: ((.five_hour.utilization // 0) | floor),
    seven_day: ((.seven_day.utilization // 0) | floor),
    five_hour_resets: (.five_hour.resets_at // null),
    credits: (if (.extra_usage.limit // 0) > 0
              then (((.extra_usage.used // 0) * 100 / .extra_usage.limit) | floor)
              else 0 end)
}' 2>/dev/null > "$CACHE_FILE" || echo '{"five_hour":0,"seven_day":0,"credits":0}' > "$CACHE_FILE"
