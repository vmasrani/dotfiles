#!/bin/zsh

# Claude Code Status Line - Powerlevel10k Style
# Matches the lean aesthetic of P10k with clean icons and spacing

# Read JSON input from stdin
input=$(cat)

# Extract data from JSON
model_name=$(echo "$input" | jq -r '.model.display_name // "Claude"')
model_id=$(echo "$input" | jq -r '.model.id // ""')
current_dir=$(echo "$input" | jq -r '.workspace.current_dir // ""')
project_dir=$(echo "$input" | jq -r '.workspace.project_dir // ""')

# Color definitions (matching P10k lean style)
reset='\033[0m'
blue='\033[38;5;39m'        # Bright blue for model
green='\033[38;5;76m'       # Green for directory
yellow='\033[38;5;220m'     # Yellow for git
red='\033[38;5;203m'        # Red for warnings
gray='\033[38;5;244m'       # Gray for separators
white='\033[38;5;255m'      # White for text

# Icons (using Nerd Font symbols to match P10k)
claude_icon="󱚝"             # AI/brain icon
folder_icon=""             # Folder icon
git_icon=""               # Git icon
separator="❯"              # Arrow separator (matches P10k lean)

# Function to shorten directory path (P10k style)
shorten_path() {
    local path="$1"
    local project="$2"
    
    if [[ -n "$project" && "$path" == "$project"* ]]; then
        # Show relative to project root
        local rel_path="${path#$project}"
        local project_name=$(basename "$project")
        if [[ -z "$rel_path" || "$rel_path" == "/" ]]; then
            echo "$project_name"
        else
            echo "$project_name${rel_path}"
        fi
    else
        # Standard path shortening
        echo "$path" | sed "s|$HOME|~|" | awk -F/ '{
            if (NF <= 3) print $0
            else printf ".../%s/%s\n", $(NF-1), $NF
        }'
    fi
}

# Function to get git status
get_git_status() {
    if [[ -d .git ]] || git rev-parse --git-dir >/dev/null 2>&1; then
        local branch=$(git branch --show-current 2>/dev/null)
        local status=""
        
        # Check for changes
        if ! git diff --quiet 2>/dev/null; then
            status="${status}*"  # Modified files
        fi
        
        if ! git diff --cached --quiet 2>/dev/null; then
            status="${status}+"  # Staged files
        fi
        
        local unpushed=$(git log @{u}.. --oneline 2>/dev/null | wc -l | tr -d ' ')
        if [[ "$unpushed" -gt 0 ]]; then
            status="${status}↑$unpushed"  # Unpushed commits
        fi
        
        if [[ -n "$branch" ]]; then
            echo "$branch$status"
        fi
    fi
}

# Function to extract model short name
get_model_short() {
    case "$model_id" in
        *"sonnet"*) echo "Sonnet" ;;
        *"haiku"*) echo "Haiku" ;;
        *"opus"*) echo "Opus" ;;
        *) echo "$model_name" | cut -d' ' -f1-2 ;;
    esac
}

# Build status line components
model_short=$(get_model_short)
dir_short=$(shorten_path "$current_dir" "$project_dir")
git_status=$(get_git_status)

# Assemble the status line
status_line=""

# Model name with icon
status_line="${blue}${claude_icon} ${model_short}${reset}"

# Directory
if [[ -n "$dir_short" ]]; then
    status_line="${status_line} ${gray}${separator}${reset} ${green}${folder_icon} ${dir_short}${reset}"
fi

# Git status
if [[ -n "$git_status" ]]; then
    status_line="${status_line} ${gray}${separator}${reset} ${yellow}${git_icon} ${git_status}${reset}"
fi

# Output the final status line
printf "%b" "$status_line"