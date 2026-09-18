#!/usr/bin/env bash
# Browse per-pane random background colors with pane-local history.
set -euo pipefail

readonly HISTORY_OPTION='@pane_color_history'
readonly CURSOR_OPTION='@pane_color_cursor'

fail() {
    printf 'pane-color-history: %s\n' "$1" >&2
    exit 1
}

generate_color() {
    local value

    value=$(( ((RANDOM << 16) | (RANDOM << 1) | (RANDOM & 1)) & 0xFFFFFF ))
    printf '#%06X' "$value"
}

[[ $# -eq 2 ]] || fail 'usage: pane-color-history.sh <forward|backward> <pane-id>'

direction=$1
pane_id=$2

case "$direction" in
    forward|backward) ;;
    *) fail "invalid direction '$direction'; expected forward or backward" ;;
esac

[[ "$pane_id" =~ ^%[0-9]+$ ]] || fail "invalid pane id '$pane_id'; expected a tmux pane id such as %1"

resolved_pane_id=$(tmux display-message -p -t "$pane_id" '#{pane_id}') \
    || fail "target pane '$pane_id' does not exist"
[[ "$resolved_pane_id" == "$pane_id" ]] \
    || fail "target pane '$pane_id' resolved unexpectedly as '$resolved_pane_id'"

history=$(tmux show-options -p -t "$pane_id" -qv "$HISTORY_OPTION")
cursor=$(tmux show-options -p -t "$pane_id" -qv "$CURSOR_OPTION")

if [[ -z "$history" && -z "$cursor" ]]; then
    [[ "$direction" == 'forward' ]] \
        || fail "pane '$pane_id' has no color history; use forward first"

    color=$(generate_color)
    history=$color
    cursor_index=0
else
    [[ -n "$history" && -n "$cursor" ]] \
        || fail "pane '$pane_id' has incomplete color history state"
    [[ "$history" =~ ^#[0-9A-Fa-f]{6}(,#[0-9A-Fa-f]{6})*$ ]] \
        || fail "pane '$pane_id' has malformed color history '$history'"
    [[ "$cursor" =~ ^[0-9]+$ ]] \
        || fail "pane '$pane_id' has malformed color cursor '$cursor'"

    IFS=, read -r -a colors <<< "$history"
    history_count=${#colors[@]}
    cursor_index=$((10#$cursor))
    (( cursor_index < history_count )) \
        || fail "pane '$pane_id' color cursor '$cursor' is outside its history"

    case "$direction" in
        forward)
            if (( cursor_index + 1 < history_count )); then
                ((cursor_index += 1))
                color=${colors[cursor_index]}
            else
                color=$(generate_color)
                history+=",$color"
                cursor_index=$history_count
            fi
            ;;
        backward)
            if (( cursor_index > 0 )); then
                cursor_index=$((cursor_index - 1))
            fi
            color=${colors[cursor_index]}
            ;;
    esac
fi

if ! tmux set-option -p -t "$pane_id" window-style "bg=$color"; then
    fail "could not apply background '$color' to pane '$pane_id'"
fi
if ! tmux set-option -p -t "$pane_id" window-active-style "bg=$color"; then
    fail "could not apply active background '$color' to pane '$pane_id'"
fi
if ! tmux set-option -p -t "$pane_id" "$HISTORY_OPTION" "$history"; then
    fail "could not save color history for pane '$pane_id'"
fi
if ! tmux set-option -p -t "$pane_id" "$CURSOR_OPTION" "$cursor_index"; then
    fail "could not save color cursor for pane '$pane_id'"
fi
if ! tmux display-message -t "$pane_id" "Pane background: $color"; then
    fail "applied '$color' but could not display it for pane '$pane_id'"
fi
