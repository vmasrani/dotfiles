#!/usr/bin/env bash
# Get battery percentage for tmux status bar

get_battery() {
    case $(uname -s) in
        Darwin)
            pmset -g batt 2>/dev/null | grep -o '[0-9]*%' | head -1 | tr -d '%'
            ;;
        Linux)
            if [[ -f /sys/class/power_supply/BAT0/capacity ]]; then
                cat /sys/class/power_supply/BAT0/capacity
            elif [[ -f /sys/class/power_supply/BAT1/capacity ]]; then
                cat /sys/class/power_supply/BAT1/capacity
            else
                echo "N/A"
            fi
            ;;
        *)
            echo "N/A"
            ;;
    esac
}

result=$(get_battery)
if [[ "$result" != "N/A" ]]; then
    echo "${result}%"
else
    echo "$result"
fi
