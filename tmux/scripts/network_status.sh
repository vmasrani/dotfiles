#!/usr/bin/env bash
# Network status with current speed and max over 5min/1hr windows
# Output: "SSID 󰇚 cur/5m/1h 󰕒 cur/5m/1h"

CACHE_FILE="/tmp/tmux_net_cache"
HISTORY_FILE="/tmp/tmux_net_history"

get_ssid() {
    case $(uname -s) in
        Darwin)
            local ssid
            ssid=$(networksetup -getairportnetwork en0 2>/dev/null | cut -d ':' -f 2 | sed 's/^ *//')
            if [[ -n "$ssid" && "$ssid" != "You are not associated with an AirPort network." ]]; then
                echo "$ssid"
            elif ifconfig en0 2>/dev/null | grep -q "status: active"; then
                echo "Eth"
            else
                echo "Off"
            fi
            ;;
        Linux)
            local ssid
            ssid=$(iwgetid -r 2>/dev/null)
            [[ -n "$ssid" ]] && echo "$ssid" || echo "Eth"
            ;;
        *)
            echo "?"
            ;;
    esac
}

get_iface() {
    if [[ $(uname -s) == "Darwin" ]]; then
        route -n get default 2>/dev/null | awk '/interface:/{print $2; exit}'
    else
        ip route get 1.1.1.1 2>/dev/null | awk '{for(i=1;i<=NF;i++) if($i=="dev"){print $(i+1); exit}}'
    fi
}

get_bytes() {
    local iface="$1"
    if [[ -d "/sys/class/net/$iface/statistics" ]]; then
        local rx tx
        rx=$(cat "/sys/class/net/$iface/statistics/rx_bytes" 2>/dev/null || echo 0)
        tx=$(cat "/sys/class/net/$iface/statistics/tx_bytes" 2>/dev/null || echo 0)
        echo "$rx $tx"
    else
        netstat -ib 2>/dev/null | awk -v IF="$iface" '$1==IF && $7 ~ /^[0-9]+$/ {rx=$7; tx=$10} END{print rx+0, tx+0}'
    fi
}

fmt_rate() {
    # Always outputs exactly 4 characters (e.g., "2.5K", " 45K", "120K", "1.2M")
    awk -v bps="$1" 'BEGIN {
        if (bps < 1024) {
            printf "  0K"
        } else if (bps < 1023488) {
            v = bps / 1024
            if (v < 10) printf "%3.1fK", v
            else printf "%3.0fK", v
        } else if (bps < 1048051712) {
            v = bps / 1048576
            if (v < 10) printf "%3.1fM", v
            else printf "%3.0fM", v
        } else {
            v = bps / 1073741824
            if (v < 10) printf "%3.1fG", v
            else printf "%3.0fG", v
        }
    }'
}

get_max_rates() {
    local window="$1"  # seconds
    local now="$2"
    local cutoff=$((now - window))

    awk -v cutoff="$cutoff" '
        $1 >= cutoff {
            if ($2 > max_down) max_down = $2
            if ($3 > max_up) max_up = $3
        }
        END { print max_down+0, max_up+0 }
    ' "$HISTORY_FILE" 2>/dev/null || echo "0 0"
}

# Get SSID
ssid=$(get_ssid)

# Get interface
iface=$(get_iface)
if [[ -z "$iface" ]]; then
    echo "$ssid"
    exit 0
fi

now=$(date +%s)
read -r rx tx < <(get_bytes "$iface")

# Read previous values and calculate current rate
down_rate=0
up_rate=0
if [[ -f "$CACHE_FILE" ]]; then
    read -r prev_time prev_rx prev_tx < "$CACHE_FILE" 2>/dev/null
    dt=$((now - prev_time))
    if (( dt > 0 && dt < 60 && prev_time > 0 )); then
        down_rate=$(( (rx - prev_rx) / dt ))
        up_rate=$(( (tx - prev_tx) / dt ))
        (( down_rate < 0 )) && down_rate=0
        (( up_rate < 0 )) && up_rate=0
    fi
fi

# Save current bytes for next run
echo "$now $rx $tx" > "$CACHE_FILE"

# Append current rates to history (only if we have valid rates)
if (( down_rate > 0 || up_rate > 0 )); then
    echo "$now $down_rate $up_rate" >> "$HISTORY_FILE"
fi

# Clean old history (keep last hour only) - do this occasionally
if (( now % 60 < 10 )); then
    cutoff=$((now - 3600))
    awk -v cutoff="$cutoff" '$1 >= cutoff' "$HISTORY_FILE" > "$HISTORY_FILE.tmp" 2>/dev/null
    mv -f "$HISTORY_FILE.tmp" "$HISTORY_FILE" 2>/dev/null
fi

# Get max rates for 5min and 1hr windows
read -r max5_down max5_up < <(get_max_rates 300 "$now")
read -r max60_down max60_up < <(get_max_rates 3600 "$now")

# Ensure current rate is included in max calculations
(( down_rate > max5_down )) && max5_down=$down_rate
(( up_rate > max5_up )) && max5_up=$up_rate
(( down_rate > max60_down )) && max60_down=$down_rate
(( up_rate > max60_up )) && max60_up=$up_rate

# Format output
cur_down=$(fmt_rate "$down_rate")
cur_up=$(fmt_rate "$up_rate")
m5_down=$(fmt_rate "$max5_down")
m5_up=$(fmt_rate "$max5_up")
m60_down=$(fmt_rate "$max60_down")
m60_up=$(fmt_rate "$max60_up")

# Output: SSID 󰇚cur/5m/1h 󰕒cur/5m/1h
echo "$ssid 󰇚$cur_down/$m5_down/$m60_down 󰕒$cur_up/$m5_up/$m60_up"
