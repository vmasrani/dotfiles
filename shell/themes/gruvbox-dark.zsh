#!/usr/bin/env zsh
# Gruvbox Dark — redefine iTerm2 ANSI 0-15, bg, fg, cursor via OSC sequences
# Designed for SSH sessions to visually distinguish remote from local

export DOTFILES_THEME="gruvbox-dark"

[[ "$TERM_PROGRAM" == "iTerm.app" || -n "$ITERM_SESSION_ID" ]] || return 0

_send_osc() {
    if [[ -n "$TMUX" ]]; then
        printf "\033Ptmux;\033%s\033\\" "$1"
    else
        printf "%s" "$1"
    fi
}

_set_ansi() {
    local n=$1 hex=$2
    local r=${hex:1:2} g=${hex:3:2} b=${hex:5:2}
    _send_osc "\033]4;${n};rgb:${r}/${g}/${b}\007"
}

_set_special() {
    local osc=$1 hex=$2
    local r=${hex:1:2} g=${hex:3:2} b=${hex:5:2}
    _send_osc "\033]${osc};rgb:${r}/${g}/${b}\007"
}

# ANSI 0-7 (normal)
_set_ansi 0  "#282828"  # black
_set_ansi 1  "#cc241d"  # red
_set_ansi 2  "#98971a"  # green
_set_ansi 3  "#d79921"  # yellow
_set_ansi 4  "#458588"  # blue
_set_ansi 5  "#b16286"  # magenta
_set_ansi 6  "#689d6a"  # cyan
_set_ansi 7  "#a89984"  # white

# ANSI 8-15 (bright)
_set_ansi 8  "#928374"  # bright black
_set_ansi 9  "#fb4934"  # bright red
_set_ansi 10 "#b8bb26"  # bright green
_set_ansi 11 "#fabd2f"  # bright yellow
_set_ansi 12 "#83a598"  # bright blue
_set_ansi 13 "#d3869b"  # bright magenta
_set_ansi 14 "#8ec07c"  # bright cyan
_set_ansi 15 "#ebdbb2"  # bright white

# Special colors (OSC 10=fg, 11=bg, 12=cursor)
_set_special 10 "#ebdbb2"  # foreground
_set_special 11 "#282828"  # background
_set_special 12 "#ebdbb2"  # cursor
