#!/usr/bin/env bash
# shellcheck disable=SC2016
# ^ widget strings intentionally hold literal $HOME / $(whoami) / #(...) —
#   powerkit evals them later at render time, so single quotes are correct.
# Build the @powerkit_plugins value for the current host.
#
# Plugins are external() wrappers with raw hex Catppuccin accent colors
# (hex values so powerkit's contrast function picks dark text automatically).
#
# SSH sessions: cpu, mem, gpu (only if a GPU is actually detected on this
#   host), host. Servers don't have batteries, so no battery widget;
#   hosts without an nvidia GPU don't get an empty gpu pill.
# Local sessions: cpu, mem, battery, weather, time, host.
set -euo pipefail

is_ssh_session() {
    [ -n "${SSH_CLIENT:-}" ] || [ -n "${SSH_TTY:-}" ]
}

has_gpu() {
    [ -n "$("$HOME/dotfiles/tmux/scripts/gpu_status.sh")" ]
}

cpu_widget_ssh() {
    printf '%s' 'external("󰘚"|"#($HOME/dotfiles/tmux/scripts/cpu_percent.sh)"|"#f5a97f"|"#f7bf9f"|"5")'
}

mem_widget_ssh() {
    printf '%s' 'external("󰍛"|"#($HOME/dotfiles/tmux/scripts/mem_usage.sh)"|"#c6a0f6"|"#d4b8f8"|"5")'
}

gpu_widget() {
    printf '%s' 'external("󰢮"|"#($HOME/dotfiles/tmux/scripts/gpu_status.sh)"|"#a6da95"|"#bee5b3"|"5")'
}

host_widget() {
    local accent="$1" alt="$2"
    printf '%s' "external(\"󰒋\"|\"#(\$HOME/dotfiles/tmux/scripts/host_status.sh)\"|\"$accent\"|\"$alt\"|\"30\")"
}

cpu_widget_local() {
    printf '%s' 'external("󰘚"|"#($HOME/dotfiles/tmux/scripts/cpu_percent.sh)"|"#fab387"|"#fcc9ab"|"5")'
}

mem_widget_local() {
    printf '%s' 'external("󰍛"|"#($HOME/dotfiles/tmux/scripts/mem_usage.sh)"|"#cba6f7"|"#d8bbf9"|"5")'
}

battery_widget() {
    printf '%s' 'external("󰂄"|"#(pmset -g batt | grep -o '"'"'[0-9]*%'"'"')"|"#a6e3a1"|"#beebba"|"60")'
}

weather_widget() {
    printf '%s' 'external("󰖐"|"#($HOME/dotfiles/tmux/scripts/weather_status.sh)"|"#f9e2af"|"#fbebc7"|"1800")'
}

time_widget() {
    printf '%s' 'external("󰃰"|"#(date +'"'"'%l:%M%p'"'"' | sed '"'"'s/^ //'"'"')"|"#74c7ec"|"#96d5f1"|"30")'
}

build_ssh_plugins() {
    local widgets=("$(cpu_widget_ssh)" "$(mem_widget_ssh)")
    if has_gpu; then
        widgets+=("$(gpu_widget)")
    fi
    widgets+=("$(host_widget "#f5bde6" "#f8d1ed")")
    local IFS=,
    printf '%s' "${widgets[*]}"
}

build_local_plugins() {
    local widgets=(
        "$(cpu_widget_local)"
        "$(mem_widget_local)"
        "$(battery_widget)"
        "$(weather_widget)"
        "$(time_widget)"
        "$(host_widget "#f5c2e7" "#f8d4ee")"
    )
    local IFS=,
    printf '%s' "${widgets[*]}"
}

main() {
    if is_ssh_session; then
        build_ssh_plugins
    else
        build_local_plugins
    fi
}

main
