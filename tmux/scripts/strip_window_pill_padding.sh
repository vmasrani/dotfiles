#!/usr/bin/env bash
# Powerkit's window pill format ends with " #W " (trailing space) which renders
# as a 1-char pink padding cell after the active window name. With the rounded
# closing curve disabled (@powerkit_edge_separator_style "rounded"), that
# trailing cell becomes the visible right edge — looking like a gap between the
# name and the screen edge. Strip it so the pill ends right at the name.

for opt in window-status-current-format window-status-format; do
    fmt=$(tmux show-option -gv "$opt" 2>/dev/null) || continue
    [[ -z "$fmt" ]] && continue
    # Active pill: "#W #{?pane_synchronized" -> "#W#{?pane_synchronized"
    # Inactive pill: "#W #[norange]" -> "#W#[norange]"
    new_fmt="${fmt//#W #\{?pane_synchronized/#W#\{?pane_synchronized}"
    new_fmt="${new_fmt//#W #\[norange/#W#\[norange}"
    [[ "$new_fmt" != "$fmt" ]] && tmux set-option -g "$opt" "$new_fmt"
done
