#!/bin/zsh

# Claude Code Status Line - Balanced Configuration
# Shows: directory, git branch, time, and context window usage

# Read JSON input from stdin
input=$(cat)

# Extract current directory (basename only)
current_dir=$(echo "$input" | jq -r '.workspace.current_dir')
dir_name=$(basename "$current_dir")

# Get git branch if in a git repo (skip optional locks for performance)
git_branch=""
if git -C "$current_dir" --no-optional-locks rev-parse --git-dir > /dev/null 2>&1; then
    branch=$(git -C "$current_dir" --no-optional-locks branch --show-current 2>/dev/null)
    if [[ -n "$branch" ]]; then
        git_branch=" ${branch}"
    fi
fi

# Get current time
current_time=$(date +%H:%M:%S)

# Calculate context window percentage (use current_usage, not cumulative totals)
context_info=""
usage=$(echo "$input" | jq '.context_window.current_usage')
if [[ "$usage" != "null" ]]; then
    current=$(echo "$usage" | jq '.input_tokens + .cache_creation_input_tokens + .cache_read_input_tokens')
    size=$(echo "$input" | jq '.context_window.context_window_size')
    if [[ "$size" -gt 0 ]]; then
        pct=$((current * 100 / size))
        context_info=" ${pct}%"
    fi
fi

# Output status line (colors will be dimmed by terminal)
printf "%s%s %s%s" "$dir_name" "$git_branch" "$current_time" "$context_info"