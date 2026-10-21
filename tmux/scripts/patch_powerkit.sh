#!/usr/bin/env bash
# shellcheck disable=SC2016  # literal ${...}/$(...) in anchors and patch lines is intentional
# Local fixes for upstream tmux-powerkit bugs, re-applied on every config load
# (TPM updates wipe them). Idempotent; must run before TPM loads powerkit.
#
# 1. options.sh: powerkit batch-loads @powerkit_* options from
#    `tmux show-options -g`, which (tmux 3.7+) escapes \ " $ inside
#    double-quoted values. Powerkit only strips the outer quotes, so every
#    external("..."|...) widget fails its format regex and the bar renders empty.
# 2. color_resolver.sh: raw hex accents are looked up as theme color names
#    first, logging "Color not found" for every hex on every render.
set -euo pipefail

pk="$HOME/.tmux/plugins/tmux-powerkit/src"
[[ -d "$pk" ]] || exit 0

# insert_after <file> <exact anchor line> <marker> <line to insert>
insert_after() {
    local file="$1" anchor="$2" marker="$3" line="$4"
    grep -qF "$marker" "$file" && return 0
    grep -qxF "$anchor" "$file" || {
        echo "patch_powerkit.sh: anchor not found in $file (powerkit changed upstream; update this patch)" >&2
        exit 1
    }
    # ENVIRON, not -v: awk -v interprets backslash escapes in the values
    ANCHOR="$anchor" MARKER="$marker" LINE="$line" awk '
        { print }
        $0 == ENVIRON["ANCHOR"] && !done {
            match($0, /^ */)
            print substr($0, 1, RLENGTH) "# " ENVIRON["MARKER"]
            print ENVIRON["LINE"]
            done = 1
        }
    ' "$file" >"$file.tmp" && mv "$file.tmp" "$file"
}

insert_after "$pk/core/options.sh" \
    '                value="${BASH_REMATCH[1]}"' \
    'dotfiles: unescape tmux show-options quoting' \
    '                value=$(sed -E '\''s/\\(["$\\])/\1/g'\'' <<<"$value")'

insert_after "$pk/renderer/color_resolver.sh" \
    '    # Check per-cycle cache first (fast path)' \
    'dotfiles: raw hex passes through without a theme lookup' \
    '    [[ "$name" =~ ^#[0-9a-fA-F]{6}$ ]] && { printf '\''%s'\'' "$name"; return 0; }'
