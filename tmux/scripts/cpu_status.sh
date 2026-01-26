#!/usr/bin/env bash
# Get CPU usage percentage for tmux status bar

get_cpu() {
    case $(uname -s) in
        Darwin)
            # macOS - use top to get CPU usage
            top -l 1 -n 0 2>/dev/null | awk '/CPU usage/ {print int($3)}' | head -1
            ;;
        Linux)
            # Linux - use /proc/stat
            read -r cpu user nice system idle rest < /proc/stat
            total=$((user + nice + system + idle))
            used=$((user + nice + system))
            echo $((used * 100 / total))
            ;;
        *)
            echo "N/A"
            ;;
    esac
}

result=$(get_cpu)
if [[ "$result" != "N/A" && -n "$result" ]]; then
    printf "%02d%%\n" "$result"
else
    echo "N/A"
fi
