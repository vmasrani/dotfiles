#!/bin/bash
# shellcheck shell=bash

# Update checking functions for various package managers

source ~/dotfiles/update_checks/update_config.sh

# Check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Get cache file path for a specific package manager
get_cache_file() {
    local pm="$1"
    echo "$UPDATE_CACHE_DIR/.${pm}_updates"
}

# Check if cache file is valid (not older than cache timeout)
is_cache_valid() {
    local cache_file="$1"
    if [[ ! -f "$cache_file" ]]; then
        return 1
    fi
    
    local cache_age=$(($(date +%s) - $(stat -f %m "$cache_file" 2>/dev/null || stat -c %Y "$cache_file" 2>/dev/null || echo 0)))
    [[ $cache_age -lt $UPDATE_CACHE_TIMEOUT ]]
}

# Get cached result or run command and cache it
get_cached_or_update() {
    local pm="$1"
    local check_command="$2"
    local cache_file=$(get_cache_file "$pm")
    
    if is_cache_valid "$cache_file"; then
        cat "$cache_file"
        return
    fi
    
    # Run the check command and cache the result
    eval "$check_command" > "$cache_file" 2>/dev/null
    cat "$cache_file"
}

# Homebrew update check
check_brew_updates() {
    if ! command_exists "brew"; then
        return
    fi
    
    local updates=$(get_cached_or_update "brew" "brew outdated --quiet")
    if [[ -n "$updates" ]]; then
        local count=$(echo "$updates" | wc -l | tr -d ' ')
        echo "📦 Homebrew: $count packages can be updated"
    fi
}

# APT update check (Ubuntu/Debian)
check_apt_updates() {
    if ! command_exists "apt"; then
        return
    fi
    
    local updates=$(get_cached_or_update "apt" "apt list --upgradable 2>/dev/null | grep -v 'Listing...' | wc -l")
    if [[ "$updates" -gt 0 ]]; then
        echo "📦 APT: $updates packages can be updated"
    fi
}

# Cargo update check
check_cargo_updates() {
    if ! command_exists "cargo"; then
        return
    fi
    
    if ! command_exists "cargo-install-update"; then
        return
    fi
    
    local updates=$(get_cached_or_update "cargo" "cargo install-update --list | grep -v 'All packages are up to date' | wc -l")
    if [[ "$updates" -gt 0 ]]; then
        echo "🦀 Cargo: $updates packages can be updated"
    fi
}

# NPM global update check
check_npm_updates() {
    if ! command_exists "npm"; then
        return
    fi
    
    local updates=$(get_cached_or_update "npm" "npm outdated -g --parseable | wc -l")
    if [[ "$updates" -gt 0 ]]; then
        echo "📦 NPM: $updates global packages can be updated"
    fi
}

# UV tools update check
check_uv_updates() {
    if ! command_exists "uv"; then
        return
    fi
    
    local updates=$(get_cached_or_update "uv" "uv tool list | grep -v 'No tools installed' | wc -l")
    if [[ "$updates" -gt 0 ]]; then
        echo "🐍 UV: Check tools with 'uv tool list'"
    fi
}

# Pip update check
check_pip_updates() {
    if ! command_exists "pip"; then
        return
    fi
    
    local updates=$(get_cached_or_update "pip" "pip list --outdated --format=freeze | wc -l")
    if [[ "$updates" -gt 0 ]]; then
        echo "🐍 Pip: $updates packages can be updated"
    fi
}

# Main function to check all updates
check_all_updates() {
    local updates_found=false
    
    # Create cache directory if it doesn't exist
    mkdir -p "$UPDATE_CACHE_DIR"
    
    # Check each package manager
    local brew_output=$(check_brew_updates)
    local apt_output=$(check_apt_updates)
    local cargo_output=$(check_cargo_updates)
    local npm_output=$(check_npm_updates)
    local uv_output=$(check_uv_updates)
    local pip_output=$(check_pip_updates)
    
    # Display results
    if [[ -n "$brew_output" || -n "$apt_output" || -n "$cargo_output" || -n "$npm_output" || -n "$uv_output" || -n "$pip_output" ]]; then
        echo "🔄 Package Updates Available:"
        [[ -n "$brew_output" ]] && echo "  $brew_output"
        [[ -n "$apt_output" ]] && echo "  $apt_output"
        [[ -n "$cargo_output" ]] && echo "  $cargo_output"
        [[ -n "$npm_output" ]] && echo "  $npm_output"
        [[ -n "$uv_output" ]] && echo "  $uv_output"
        [[ -n "$pip_output" ]] && echo "  $pip_output"
        echo "  Run 'update-packages' to see update commands"
        echo ""
        updates_found=true
    fi
    
    return $updates_found
}

# Function to show update commands
show_update_commands() {
    echo "📦 Package Update Commands:"
    echo ""
    
    if command_exists "brew"; then
        echo "🍺 Homebrew:"
        echo "  brew update && brew upgrade"
        echo ""
    fi
    
    if command_exists "apt"; then
        echo "📦 APT:"
        echo "  sudo apt update && sudo apt upgrade"
        echo ""
    fi
    
    if command_exists "cargo" && command_exists "cargo-install-update"; then
        echo "🦀 Cargo:"
        echo "  cargo install-update -a"
        echo ""
    fi
    
    if command_exists "npm"; then
        echo "📦 NPM:"
        echo "  npm update -g"
        echo ""
    fi
    
    if command_exists "uv"; then
        echo "🐍 UV:"
        echo "  uv tool upgrade --all"
        echo ""
    fi
    
    if command_exists "pip"; then
        echo "🐍 Pip:"
        echo "  pip list --outdated --format=freeze | grep -v '^\\-e' | cut -d = -f 1 | xargs -n1 pip install -U"
        echo ""
    fi
}

# Force refresh all caches
refresh_update_cache() {
    echo "🔄 Refreshing update cache..."
    rm -rf "$UPDATE_CACHE_DIR"/*
    check_all_updates
}