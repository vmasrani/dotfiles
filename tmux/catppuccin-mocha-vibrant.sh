#!/usr/bin/env bash
# =============================================================================
# Theme: Catppuccin Mocha (Vibrant)
# Description: Mocha with colorful ok-base (blue instead of gray)
# Based on: catppuccin/mocha
# =============================================================================

declare -gA THEME_COLORS=(
    # CORE
    [background]="#1e1e2e"               # base
    # STATUS BAR
    [statusbar-bg]="#313244"             # surface0
    [statusbar-fg]="#cdd6f4"             # text
    # SESSION
    [session-bg]="#cba6f7"               # mauve
    [session-fg]="#1e1e2e"               # base
    [session-prefix-bg]="#fab387"        # peach
    [session-copy-bg]="#74c7ec"          # sapphire
    [session-search-bg]="#f9e2af"        # yellow
    [session-command-bg]="#f5c2e7"       # pink
    # WINDOW (active)
    [window-active-base]="#f5c2e7"       # pink
    [window-active-style]="bold"
    # WINDOW (inactive)
    [window-inactive-base]="#45475a"     # surface1
    [window-inactive-style]="none"
    # WINDOW STATE
    [window-activity-style]="italics"
    [window-bell-style]="bold"
    [window-zoomed-bg]="#74c7ec"         # sapphire
    # PANE
    [pane-border-active]="#cba6f7"       # mauve
    [pane-border-inactive]="#45475a"     # surface1
    # STATUS COLORS — ok-base changed from gray (#45475a) to blue (#89b4fa)
    [ok-base]="#89b4fa"                  # blue (vibrant ok state)
    [good-base]="#a6e3a1"                # green
    [info-base]="#89b4fa"                # blue
    [warning-base]="#f9e2af"             # yellow
    [error-base]="#f38ba8"               # red
    [disabled-base]="#6c7086"            # overlay0
    # MESSAGE
    [message-bg]="#313244"               # surface0
    [message-fg]="#cdd6f4"               # text
    # POPUP & MENU
    [popup-bg]="#313244"
    [popup-fg]="#cdd6f4"
    [popup-border]="#cba6f7"
    [menu-bg]="#313244"
    [menu-fg]="#cdd6f4"
    [menu-selected-bg]="#cba6f7"
    [menu-selected-fg]="#1e1e2e"
    [menu-border]="#cba6f7"
)
