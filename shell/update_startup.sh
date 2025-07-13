#!/bin/bash
# shellcheck shell=bash

# Startup update checker integration

source ~/dotfiles/update_checks/update_functions.sh

# Check if we should run startup update check
should_run_startup_check() {
    if [[ "$UPDATE_CHECK_ON_STARTUP" != "true" ]]; then
        return 1
    fi

    if [[ ! -f "$LAST_STARTUP_CHECK_FILE" ]]; then
        return 0
    fi

    local last_check=$(cat "$LAST_STARTUP_CHECK_FILE" 2>/dev/null || echo 0)
    local current_time=$(date +%s)
    local time_diff=$((current_time - last_check))

    [[ $time_diff -gt $STARTUP_CHECK_INTERVAL ]]
}

# Run startup update check
run_startup_update_check() {
    if ! should_run_startup_check; then
        return
    fi

    # Create cache directory if it doesn't exist
    mkdir -p "$UPDATE_CACHE_DIR"

    # Update last check time
    date +%s > "$LAST_STARTUP_CHECK_FILE"

    # Run update check in background to avoid blocking shell startup
    if [[ "$SHOW_UPDATES_ON_STARTUP" == "true" ]]; then
        (check_all_updates &)
    fi
}

# Only run if this script is being sourced during shell startup
if [[ "${BASH_SOURCE[0]}" != "${0}" ]] || [[ -n "$ZSH_VERSION" ]]; then
    run_startup_update_check
fi
