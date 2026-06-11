#!/bin/zsh

# Claude Code Status Line - Balanced Configuration
# Shows: model, path, git branch, time, context window usage, and disk usage

# Read JSON input from stdin
input=$(cat)

# Extract current directory (full path, $HOME abbreviated to ~)
current_dir=$(echo "$input" | jq -r '.workspace.current_dir')
display_path="${current_dir/#$HOME/~}"

# Model display name
model_name=$(echo "$input" | jq -r '.model.display_name // empty')

# Get git branch if in a git repo (skip optional locks for performance)
git_branch=""
if git -C "$current_dir" --no-optional-locks rev-parse --git-dir > /dev/null 2>&1; then
    branch=$(git -C "$current_dir" --no-optional-locks branch --show-current 2>/dev/null)
    if [[ -n "$branch" ]]; then
        git_branch=" ${branch}"
    fi
fi

# Get current time
current_time=$(date +%-I:%M:%S%p | tr 'APM' 'apm')

# Calculate context window percentage (use current_usage, not cumulative totals)
context_info=""
usage=$(echo "$input" | jq '.context_window.current_usage')
if [[ "$usage" != "null" ]]; then
    current=$(echo "$usage" | jq '.input_tokens + .cache_creation_input_tokens + .cache_read_input_tokens')
    size=$(echo "$input" | jq '.context_window.context_window_size')
    if [[ "$size" -gt 0 ]]; then
        pct=$((current * 100 / size))
        if [[ "$pct" -lt 40 ]]; then
            context_info=" \033[32m${pct}%\033[0m"
        elif [[ "$pct" -lt 60 ]]; then
            context_info=" \033[33m${pct}%\033[0m"
        elif [[ "$pct" -lt 80 ]]; then
            context_info=" \033[31m${pct}%\033[0m"
        else
            context_info=" \033[1;31m${pct}%\033[0m"
        fi
    fi
fi

# Disk usage of the filesystem containing the current directory
disk_pct=$(df "$current_dir" | awk 'NR==2 {gsub(/%/,"",$5); print $5}')
disk_info=""
if [[ -n "$disk_pct" ]]; then
    if [[ "$disk_pct" -lt 70 ]]; then
        disk_info=" \033[2m⛁ ${disk_pct}%\033[0m"
    elif [[ "$disk_pct" -lt 90 ]]; then
        disk_info=" \033[33m⛁ ${disk_pct}%\033[0m"
    else
        disk_info=" \033[1;31m⛁ ${disk_pct}%\033[0m"
    fi
fi

model_info=""
if [[ -n "$model_name" ]]; then
    model_info="\033[36m${model_name}\033[0m "
fi

# Session rate limits: 5h and 7d usage with reset times
color_pct() {
    if [[ "$1" -lt 60 ]]; then
        printf "\033[32m%s%%\033[0m" "$1"
    elif [[ "$1" -lt 80 ]]; then
        printf "\033[33m%s%%\033[0m" "$1"
    else
        printf "\033[1;31m%s%%\033[0m" "$1"
    fi
}

limit_segment() {
    local label=$1 pct=$2 resets_at=$3 reset_fmt=$4
    [[ "$pct" == "null" || -z "$pct" ]] && return
    local reset
    reset=$(date -r "$resets_at" "+${reset_fmt}" | tr 'APM' 'apm' | sed 's/:00//')
    printf " \033[2m%s\033[0m %s\033[2m→%s\033[0m" "$label" "$(color_pct "$pct")" "$reset"
}

five_pct=$(echo "$input" | jq -r '.rate_limits.five_hour.used_percentage // empty | round')
five_reset=$(echo "$input" | jq -r '.rate_limits.five_hour.resets_at // 0')
seven_pct=$(echo "$input" | jq -r '.rate_limits.seven_day.used_percentage // empty | round')
seven_reset=$(echo "$input" | jq -r '.rate_limits.seven_day.resets_at // 0')

limits_info="$(limit_segment "5h" "$five_pct" "$five_reset" "%-I:%M%p")$(limit_segment "7d" "$seven_pct" "$seven_reset" "%a %-I:%M%p")"

# Output status line: main info left, rate limits pushed to the right edge
left=$(printf "%b%s%s %s%b%b" "$model_info" "$display_path" "$git_branch" "$current_time" "$context_info" "$disk_info")
right="${limits_info# }"

visible_len() {
    local stripped=$(printf '%b' "$1" | sed $'s/\x1b\\[[0-9;]*m//g')
    echo ${#stripped}
}

# Terminal width: Claude Code sets COLUMNS for the statusline process (no tty available)
term_width=${COLUMNS:-$(tput cols 2>/dev/null)}
[[ -z "$term_width" ]] && term_width=120

# Claude Code reserves the far right of this row for its own indicators
rhs_margin=24

pad=$((term_width - $(visible_len "$left") - $(visible_len "$right") - rhs_margin))
[[ "$pad" -lt 2 ]] && pad=2

printf "%b%*s%b" "$left" "$pad" "" "$right"