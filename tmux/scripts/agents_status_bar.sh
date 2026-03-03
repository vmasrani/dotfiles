#!/usr/bin/env bash
# Renders Claude usage metrics as powerkit-style pills for the agents session
# Called from status-format[0] in place of powerkit-render center

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Separator glyphs (powerline rounded)
L=$(printf '\ue0b6')
R=$(printf '\ue0b4')

# Icon glyphs (Material Design nerd font, 4-byte UTF-8)
ICON_CLOCK=$(printf '\U000F0954')     # 󰥔 nf-md-clock (five_hour)
ICON_CAL=$(printf '\U000F00ED')       # 󰃭 nf-md-calendar (seven_day)
ICON_BRAIN=$(printf '\U000F06E8')     # 󰛨 nf-md-brain (opus)
ICON_BOLT=$(printf '\U000F0E39')      # 󰸹 nf-md-lightning-bolt (sonnet)
ICON_PKG=$(printf '\U000F0820')       # 󰠠 nf-md-package-variant (credits)
ICON_TIMER=$(printf '\U000F0996')     # 󰦖 nf-md-timer-sand (reset)

# Detect SSH vs local for color palette + base background
if [[ -n "$SSH_CLIENT" || -n "$SSH_TTY" ]]; then
    STATUS_BG="#24273a"  # Macchiato base
    ACCENTS=( "#eed49f" "#ee99a0"  "#b7bdf8" "#8aadf4" "#8bd5ca" "#f0c6c6")
    LIGHTERS=("#f3e0b8" "#f2b3b8"  "#cacefa" "#a5c3f7" "#a9dfda" "#f4d5d5")
else
    STATUS_BG="#1e1e2e"  # Mocha base
    ACCENTS=( "#f9e2af" "#eba0ac"  "#b4befe" "#89b4fa" "#94e2d5" "#f2cdcd")
    LIGHTERS=("#fbecc6" "#f0b8c1"  "#c8ccfe" "#a6c6fb" "#b0eae1" "#f6dcdc")
fi

METRICS=(five_hour seven_day opus sonnet credits reset)
ICONS=("$ICON_CLOCK" "$ICON_CAL" "$ICON_BRAIN" "$ICON_BOLT" "$ICON_PKG" "$ICON_TIMER")

output=""
prev_bg="$STATUS_BG"

for i in "${!METRICS[@]}"; do
    value=$("$SCRIPT_DIR/pk_claude_metric.sh" "${METRICS[$i]}" 2>/dev/null) || true
    [[ -z "$value" ]] && continue

    lighter="${LIGHTERS[$i]}"
    accent="${ACCENTS[$i]}"
    icon="${ICONS[$i]}"

    # Pill: left-cap icon | inner-sep value (matches powerkit rounded pill format)
    output+="#[fg=${lighter},bg=${prev_bg}]${L}#[none]"
    output+="#[fg=#000000,bg=${lighter}]${icon} "
    output+="#[fg=${accent},bg=${lighter}]${L}#[none]"
    output+="#[fg=#000000,bg=${accent}] ${value} "

    prev_bg="$accent"
done

# Right cap
if [[ -n "$output" ]]; then
    output+="#[fg=${prev_bg},bg=${STATUS_BG}]${R}#[none]"
fi

printf '%s' "$output"
