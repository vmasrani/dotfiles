#!/bin/zsh
# shellcheck shell=zsh
# ===================================================================
# Gum Utilities - Standardized Terminal UI Functions
# ===================================================================
# Provides semantic wrapper functions for gum with graceful fallback
# for non-TTY environments (pipes, cron, launchd, etc.)
#
# Usage:
#   gum_success "Operation completed"
#   gum_error "Failed to connect"
#   gum_warning "Instance is in pending state"
#   gum_info "Starting instance..."
#   gum_spin_quick "Checking..." command args
#   if gum_confirm "Continue?"; then ... fi
#
# Environment variables:
#   NO_GUM=1           - Disable gum and use plain text fallback
#   DOTFILES_NO_GUM=1  - Alternative variable for disabling gum
# ===================================================================

# === Gum Color Constants ===
# Use typeset -g to allow re-sourcing without errors
typeset -g GUM_COLOR_SUCCESS=46      # Green
typeset -g GUM_COLOR_ERROR=196       # Red
typeset -g GUM_COLOR_WARNING=208     # Orange
typeset -g GUM_COLOR_INFO=212        # Magenta
typeset -g GUM_COLOR_DIM=245         # Gray
typeset -g GUM_COLOR_GRAY=242        # Darker gray
typeset -g GUM_COLOR_BLUE=111        # Blue highlights

# === Symbol Constants ===
typeset -g GUM_SYMBOL_SUCCESS="✓"
typeset -g GUM_SYMBOL_ERROR="✗"
typeset -g GUM_SYMBOL_WARNING="⚠"
typeset -g GUM_SYMBOL_PROGRESS="→"

# === Gum Availability Detection ===
_GUM_AVAILABLE=""

_gum_init() {
    # Check env variable (NO_GUM or DOTFILES_NO_GUM)
    if [[ -n "${NO_GUM:-}" || -n "${DOTFILES_NO_GUM:-}" ]]; then
        _GUM_AVAILABLE=0
        return
    fi

    # Check if TTY (stdin and stdout)
    if [[ ! -t 0 || ! -t 1 ]]; then
        _GUM_AVAILABLE=0
        return
    fi

    # Check if gum command exists
    if ! command -v gum >/dev/null 2>&1; then
        _GUM_AVAILABLE=0
        return
    fi

    _GUM_AVAILABLE=1
}

_gum_check() {
    if [[ -z "$_GUM_AVAILABLE" ]]; then
        _gum_init
    fi
    [[ "$_GUM_AVAILABLE" -eq 1 ]]
}

# === Status Messages ===

gum_success() {
    if _gum_check; then
        gum style --foreground "$GUM_COLOR_SUCCESS" "$GUM_SYMBOL_SUCCESS $*"
    else
        echo "$GUM_SYMBOL_SUCCESS $*"
    fi
}

gum_error() {
    if _gum_check; then
        gum style --foreground "$GUM_COLOR_ERROR" --border double \
            --padding "0 1" --margin "1" "$@"
    else
        echo "ERROR: $*" >&2
    fi
}

gum_warning() {
    if _gum_check; then
        gum style --foreground "$GUM_COLOR_WARNING" "$GUM_SYMBOL_WARNING $*"
    else
        echo "WARNING: $*"
    fi
}

gum_info() {
    if _gum_check; then
        gum style --foreground "$GUM_COLOR_INFO" "$GUM_SYMBOL_PROGRESS $*"
    else
        echo "$GUM_SYMBOL_PROGRESS $*"
    fi
}

gum_dim() {
    if _gum_check; then
        gum style --foreground "$GUM_COLOR_DIM" "$@"
    else
        echo "$@"
    fi
}

# === Boxes and Headers ===

gum_box() {
    local title="$1"
    local color="${2:-$GUM_COLOR_INFO}"

    if _gum_check; then
        gum style --border rounded --padding "1 2" \
            --border-foreground "$color" "$title"
    else
        echo "=== $title ==="
    fi
}

gum_box_success() {
    if _gum_check; then
        gum style --border rounded --padding "0 2" \
            --border-foreground "$GUM_COLOR_SUCCESS" \
            --foreground "$GUM_COLOR_SUCCESS" "$@"
    else
        echo "=== $* ==="
    fi
}

# === Spinners ===

gum_spin_quick() {
    local title="$1"
    shift

    if _gum_check; then
        gum spin --spinner dot --title "$title" -- "$@"
    else
        echo "[$title]" >&2
        "$@"
    fi
}

gum_spin_wait() {
    local title="$1"
    shift

    if _gum_check; then
        gum spin --spinner meter --title "$title" -- "$@"
    else
        echo "[$title]" >&2
        "$@"
    fi
}

# === Interactive Prompts ===

gum_confirm() {
    if _gum_check; then
        gum confirm "$@"
    else
        # Auto-approve in non-interactive mode
        return 0
    fi
}

gum_choose() {
    if _gum_check; then
        gum choose "$@"
    else
        # Return first non-header option
        local skip_next=0
        for arg in "$@"; do
            if [[ "$arg" == "--header" ]]; then
                skip_next=1
                continue
            fi
            if [[ $skip_next -eq 1 ]]; then
                skip_next=0
                continue
            fi
            echo "$arg"
            return 0
        done
    fi
}

# === Multi-colored Output ===

gum_print_change() {
    local old="$1"
    local new="$2"

    if _gum_check; then
        printf "%s %s %s\n" \
            "$(gum style --foreground "$GUM_COLOR_GRAY" "$old")" \
            "$(gum style --foreground "$GUM_COLOR_DIM" "$GUM_SYMBOL_PROGRESS")" \
            "$(gum style --foreground "$GUM_COLOR_BLUE" "$new")"
    else
        printf "%s -> %s\n" "$old" "$new"
    fi
}
