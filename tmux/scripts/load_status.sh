#!/usr/bin/env bash
# Get system load average (1m 5m 15m) for tmux status bar

get_load() {
    case $(uname -s) in
        Darwin)
            # macOS - parse sysctl output: { 10.20 8.56 9.73 }
            sysctl -n vm.loadavg | awk '{print $2, $3, $4}'
            ;;
        Linux)
            # Linux - first 3 fields of /proc/loadavg
            awk '{print $1, $2, $3}' /proc/loadavg
            ;;
        *)
            echo "N/A"
            ;;
    esac
}

get_load
