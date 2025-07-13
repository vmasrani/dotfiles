#!/bin/bash
# shellcheck shell=bash

# Configuration for update checking system

# Cache directory for storing update check results
UPDATE_CACHE_DIR="$HOME/.cache/dotfiles_updates"

# Cache timeout in seconds (default: 3 hours)
UPDATE_CACHE_TIMEOUT=${UPDATE_CACHE_TIMEOUT:-10800}

# Enable/disable startup update checks
UPDATE_CHECK_ON_STARTUP=${UPDATE_CHECK_ON_STARTUP:-true}

# Show updates on startup (true/false)
SHOW_UPDATES_ON_STARTUP=${SHOW_UPDATES_ON_STARTUP:-true}

# Minimum time between startup checks in seconds (default: 1 hour)
STARTUP_CHECK_INTERVAL=${STARTUP_CHECK_INTERVAL:-3600}

# File to track last startup check
LAST_STARTUP_CHECK_FILE="$UPDATE_CACHE_DIR/.last_startup_check"