#!/usr/bin/env bash
# Central cache refresh for Claude usage data
# Uses mkdir as atomic lock (works on macOS and Linux)

CACHE_FILE="/tmp/claude_usage_cache.json"
LOCK_DIR="/tmp/claude_usage_cache.lock"
CACHE_TTL=120
EMPTY_CACHE='{"five_hour":0,"seven_day":0,"five_hour_resets":null,"credits":0,"opus":0,"sonnet":0}'

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

# Get OAuth token - try macOS keychain first, then Linux credentials file
creds=$(security find-generic-password -s "Claude Code-credentials" -w 2>/dev/null)
if [[ -z "$creds" ]] && [[ -f "$HOME/.claude/.credentials.json" ]]; then
    creds=$(cat "$HOME/.claude/.credentials.json")
fi
token=$(echo "$creds" | jq -r '.claudeAiOauth.accessToken // empty' 2>/dev/null)

if [[ -z "$token" ]]; then
    echo "$EMPTY_CACHE" > "$CACHE_FILE"
    exit 0
fi

# Fetch usage data
response=$(curl -s --max-time 5 "https://api.anthropic.com/api/oauth/usage" \
    -H "Authorization: Bearer $token" \
    -H "anthropic-beta: oauth-2025-04-20" \
    -H "Accept: application/json")

# If API returned an error, keep existing cache (don't overwrite good data with zeros)
if echo "$response" | jq -e '.error' &>/dev/null; then
    [[ -f "$CACHE_FILE" ]] && touch "$CACHE_FILE" && exit 0
    echo "$EMPTY_CACHE" > "$CACHE_FILE"
    exit 0
fi

# Parse all values in single jq invocation
echo "$response" | jq '{
    five_hour: ((.five_hour.utilization // 0) | floor),
    seven_day: ((.seven_day.utilization // 0) | floor),
    five_hour_resets: (.five_hour.resets_at // null),
    credits: ((.extra_usage.utilization // 0) | floor),
    opus: ((.seven_day_opus.utilization // 0) | floor),
    sonnet: ((.seven_day_sonnet.utilization // 0) | floor)
}' 2>/dev/null > "$CACHE_FILE" || echo "$EMPTY_CACHE" > "$CACHE_FILE"
