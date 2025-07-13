#!/bin/bash
# shellcheck shell=bash

# Package update checker command-line tool

source ~/dotfiles/update_checks/update_functions.sh

show_help() {
    echo "Package Update Checker"
    echo ""
    echo "Usage: update-packages [options]"
    echo ""
    echo "Options:"
    echo "  -h, --help       Show this help message"
    echo "  -c, --check      Check for available updates"
    echo "  -s, --show       Show update commands"
    echo "  -r, --refresh    Refresh update cache"
    echo "  -q, --quiet      Quiet mode (no output if no updates)"
    echo ""
    echo "Examples:"
    echo "  update-packages           # Check for updates"
    echo "  update-packages --show    # Show update commands"
    echo "  update-packages --refresh # Force refresh cache"
}

# Parse command line arguments
QUIET_MODE=false
ACTION="check"

while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            exit 0
            ;;
        -c|--check)
            ACTION="check"
            shift
            ;;
        -s|--show)
            ACTION="show"
            shift
            ;;
        -r|--refresh)
            ACTION="refresh"
            shift
            ;;
        -q|--quiet)
            QUIET_MODE=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Execute the requested action
case $ACTION in
    "check")
        if check_all_updates; then
            exit 0
        else
            if [[ "$QUIET_MODE" != "true" ]]; then
                echo "✅ All packages are up to date!"
            fi
            exit 0
        fi
        ;;
    "show")
        show_update_commands
        ;;
    "refresh")
        refresh_update_cache
        ;;
esac