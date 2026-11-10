#!/usr/bin/env bash
# Give one window's status-bar tab a random colour, or reset it to the theme.
# usage: window-random-color.sh [random|reset] [window-target]   (default: random, current window)
#
# Powerkit bakes theme colours into the global window-status(-current)-format, so this
# copies those formats, swaps the theme colours for a random hue, and sets them as
# window-local overrides (window options shadow the global ones for that window only).
set -euo pipefail

fail() { printf 'window-random-color: %s\n' "$1" >&2; tmux display-message "window-random-color: $1"; exit 1; }

action=${1:-random}
target=${2:-}
target_args=()
[[ -n "$target" ]] && target_args=(-t "$target")

# Theme colours in powerkit's catppuccin-mocha window formats (see `tmux show -gv window-status-format`).
readonly INACTIVE_INDEX_BG='#6a6c7b' INACTIVE_NAME_BG='#45475a'
readonly ACTIVE_INDEX_BG='#f7ceeb' ACTIVE_NAME_BG='#f5c2e7'

# hsl_hex <hue 0-360> <sat 0-1> <light 0-1>
hsl_hex() {
    awk -v h="$1" -v s="$2" -v l="$3" 'BEGIN {
        c = (1 - (2*l - 1 < 0 ? 1 - 2*l : 2*l - 1)) * s
        hp = h / 60; m = hp - 2*int(hp/2) - 1; x = c * (1 - (m < 0 ? -m : m))
        if (hp < 1) { r=c; g=x; b=0 } else if (hp < 2) { r=x; g=c; b=0 }
        else if (hp < 3) { r=0; g=c; b=x } else if (hp < 4) { r=0; g=x; b=c }
        else if (hp < 5) { r=x; g=0; b=c } else { r=c; g=0; b=x }
        o = l - c/2
        printf "#%02x%02x%02x", (r+o)*255+0.5, (g+o)*255+0.5, (b+o)*255+0.5
    }'
}

case "$action" in
    reset)
        tmux set -uw "${target_args[@]}" window-status-format
        tmux set -uw "${target_args[@]}" window-status-current-format
        exit 0 ;;
    random) ;;
    *) fail "unknown action '$action'; expected random or reset" ;;
esac

inactive_fmt=$(tmux show -gv window-status-format)
active_fmt=$(tmux show -gv window-status-current-format)
[[ "$inactive_fmt" == *"bg=$INACTIVE_NAME_BG"* && "$active_fmt" == *"bg=$ACTIVE_NAME_BG"* ]] \
    || fail "theme colours not found in window formats; update the *_BG constants in $0"

hue=$((RANDOM % 360))
dim_name=$(hsl_hex "$hue" 0.45 0.36)
dim_index=$(hsl_hex "$hue" 0.40 0.48)
bright_name=$(hsl_hex "$hue" 0.75 0.78)
bright_index=$(hsl_hex "$hue" 0.75 0.86)

# Only the tokens that paint this tab; the leading separator's bg belongs to the previous tab.
tmux set -w "${target_args[@]}" window-status-format "$(sed \
    -e "s/fg=#dbdbdf,bg=$INACTIVE_INDEX_BG/fg=#dbdbdf,bg=$dim_index/" \
    -e "s/fg=$INACTIVE_NAME_BG,bg=$INACTIVE_INDEX_BG/fg=$dim_name,bg=$dim_index/" \
    -e "s/fg=#dbdbdf,bg=$INACTIVE_NAME_BG/fg=#dbdbdf,bg=$dim_name/" \
    -e "s/#\[fg=$INACTIVE_INDEX_BG#,/#[fg=$dim_index#,/" \
    <<<"$inactive_fmt")"
tmux set -w "${target_args[@]}" window-status-current-format "$(sed \
    -e "s/bg=$ACTIVE_INDEX_BG,bold/bg=$bright_index,bold/" \
    -e "s/fg=$ACTIVE_NAME_BG,bg=$ACTIVE_INDEX_BG/fg=$bright_name,bg=$bright_index/" \
    -e "s/bg=$ACTIVE_NAME_BG,bold/bg=$bright_name,bold/" \
    -e "s/#\[fg=$ACTIVE_INDEX_BG#,/#[fg=$bright_index#,/" \
    <<<"$active_fmt")"
