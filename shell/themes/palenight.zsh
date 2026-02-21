#!/usr/bin/env zsh
# Palenight — restore default iTerm2 palette via OSC sequences
# Use `source ~/dotfiles/shell/themes/palenight.zsh` to revert from gruvbox in an SSH session

export DOTFILES_THEME="palenight"

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
_set_ansi 0  "#292d3e"  # black
_set_ansi 1  "#ff5370"  # red
_set_ansi 2  "#c3e88d"  # green
_set_ansi 3  "#ffcb6b"  # yellow
_set_ansi 4  "#82aaff"  # blue
_set_ansi 5  "#c792ea"  # magenta
_set_ansi 6  "#89ddff"  # cyan
_set_ansi 7  "#d0d0d0"  # white

# ANSI 8-15 (bright)
_set_ansi 8  "#434758"  # bright black
_set_ansi 9  "#ff5370"  # bright red
_set_ansi 10 "#c3e88d"  # bright green
_set_ansi 11 "#ffcb6b"  # bright yellow
_set_ansi 12 "#82aaff"  # bright blue
_set_ansi 13 "#c792ea"  # bright magenta
_set_ansi 14 "#89ddff"  # bright cyan
_set_ansi 15 "#ffffff"  # bright white

# Special colors (OSC 10=fg, 11=bg, 12=cursor)
_set_special 10 "#a6accd"  # foreground
_set_special 11 "#292d3e"  # background
_set_special 12 "#ffcc00"  # cursor
