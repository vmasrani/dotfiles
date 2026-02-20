#!/usr/bin/env bash
# Battery pill for tmux status bar
# Outputs full tmux-formatted pill with dynamic color and icon based on charge level
# Colors are theme-aware: Gruvbox Dark on SSH, Catppuccin Macchiato locally

# Theme-aware colors: Gruvbox Dark on SSH, Catppuccin Macchiato locally
if [[ -n "$SSH_CLIENT" || -n "$SSH_TTY" ]]; then
    BASE="#282828"
    CRUST="#1d2021"
else
    BASE="#24273a"
    CRUST="#181926"
fi

get_battery_percent() {
    case $(uname -s) in
        Darwin)
            pmset -g batt 2>/dev/null | grep -o '[0-9]*%' | head -1 | tr -d '%'
            ;;
        Linux)
            if [[ -f /sys/class/power_supply/BAT0/capacity ]]; then
                cat /sys/class/power_supply/BAT0/capacity
            elif [[ -f /sys/class/power_supply/BAT1/capacity ]]; then
                cat /sys/class/power_supply/BAT1/capacity
            fi
            ;;
    esac
}

is_charging() {
    case $(uname -s) in
        Darwin)
            pmset -g batt 2>/dev/null | grep -q 'AC Power'
            ;;
        Linux)
            local status=""
            if [[ -f /sys/class/power_supply/BAT0/status ]]; then
                status=$(cat /sys/class/power_supply/BAT0/status)
            elif [[ -f /sys/class/power_supply/BAT1/status ]]; then
                status=$(cat /sys/class/power_supply/BAT1/status)
            fi
            [[ "$status" == "Charging" || "$status" == "Full" ]]
            ;;
        *)
            return 1
            ;;
    esac
}

get_color() {
    local pct=$1
    if [[ -n "$SSH_CLIENT" || -n "$SSH_TTY" ]]; then
        # Gruvbox Dark gradient
        if   (( pct >= 80 )); then echo "#b8bb26"  # green
        elif (( pct >= 60 )); then echo "#fabd2f"  # yellow
        elif (( pct >= 40 )); then echo "#fe8019"  # orange
        elif (( pct >= 20 )); then echo "#fb4934"  # red
        else                       echo "#cc241d"  # dark red
        fi
    else
        # Catppuccin Macchiato gradient
        if   (( pct >= 80 )); then echo "#a6da95"  # green
        elif (( pct >= 60 )); then echo "#eed49f"  # yellow
        elif (( pct >= 40 )); then echo "#f5a97f"  # peach
        elif (( pct >= 20 )); then echo "#ed8796"  # red
        else                       echo "#ee99a0"  # maroon
        fi
    fi
}

get_icon() {
    local pct=$1
    local charging=$2
    if [[ "$charging" == "1" ]]; then
        # Charging icons (Nerd Font md-battery-charging-*)
        if   (( pct >= 90 )); then echo "󰂅"
        elif (( pct >= 80 )); then echo "󰂋"
        elif (( pct >= 60 )); then echo "󰂉"
        elif (( pct >= 40 )); then echo "󰂈"
        elif (( pct >= 20 )); then echo "󰂆"
        else                       echo "󰢜"
        fi
    else
        # Discharging icons (Nerd Font md-battery-*)
        if   (( pct >= 95 )); then echo "󰁹"
        elif (( pct >= 85 )); then echo "󰂂"
        elif (( pct >= 75 )); then echo "󰂁"
        elif (( pct >= 65 )); then echo "󰂀"
        elif (( pct >= 55 )); then echo "󰁿"
        elif (( pct >= 45 )); then echo "󰁾"
        elif (( pct >= 35 )); then echo "󰁽"
        elif (( pct >= 25 )); then echo "󰁼"
        elif (( pct >= 15 )); then echo "󰁻"
        elif (( pct >= 5  )); then echo "󰁺"
        else                       echo "󰂎"
        fi
    fi
}

pct=$(get_battery_percent)
[[ -z "$pct" ]] && exit 0

charging=0
is_charging && charging=1

color=$(get_color "$pct")
icon=$(get_icon "$pct" "$charging")

# Output full tmux-formatted pill: left cap, content, right cap
echo "#[fg=${color},bg=${BASE}]#[fg=${CRUST},bg=${color}] ${icon} ${pct}% #[fg=${color},bg=${BASE}]"
