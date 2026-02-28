#!/usr/bin/env bash
# =============================================================================
# Theme: Catppuccin Macchiato (Vibrant)
# Description: Macchiato with colorful ok-base (blue instead of gray)
# Based on: catppuccin/macchiato
# Used for: SSH sessions (visually distinct from local Mocha theme)
# =============================================================================

declare -gA THEME_COLORS=(
    # CORE
    [background]="#24273a"               # base
    # STATUS BAR
    [statusbar-bg]="#363a4f"             # surface0
    [statusbar-fg]="#cad3f5"             # text
    # SESSION
    [session-bg]="#c6a0f6"               # mauve
    [session-fg]="#24273a"               # base
    [session-prefix-bg]="#f5a97f"        # peach
    [session-copy-bg]="#7dc4e4"          # sapphire
    [session-search-bg]="#eed49f"        # yellow
    [session-command-bg]="#f5bde6"       # pink
    # WINDOW (active)
    [window-active-base]="#f5bde6"       # pink
    [window-active-style]="bold"
    # WINDOW (inactive)
    [window-inactive-base]="#494d64"     # surface1
    [window-inactive-style]="none"
    # WINDOW STATE
    [window-activity-style]="italics"
    [window-bell-style]="bold"
    [window-zoomed-bg]="#7dc4e4"         # sapphire
    # PANE
    [pane-border-active]="#c6a0f6"       # mauve
    [pane-border-inactive]="#494d64"     # surface1
    # STATUS COLORS — ok-base changed from gray to blue (vibrant ok state)
    [ok-base]="#8aadf4"                  # blue (vibrant ok state)
    [good-base]="#a6da95"                # green
    [info-base]="#8aadf4"                # blue
    [warning-base]="#eed49f"             # yellow
    [error-base]="#ed8796"               # red
    [disabled-base]="#6e738d"            # overlay0
    # MESSAGE
    [message-bg]="#363a4f"               # surface0
    [message-fg]="#cad3f5"               # text
    # POPUP & MENU
    [popup-bg]="#363a4f"
    [popup-fg]="#cad3f5"
    [popup-border]="#c6a0f6"
    [menu-bg]="#363a4f"
    [menu-fg]="#cad3f5"
    [menu-selected-bg]="#c6a0f6"
    [menu-selected-fg]="#24273a"
    [menu-border]="#c6a0f6"
)
