#!/usr/bin/env bash
# Get network/wifi status for tmux status bar

get_ssid() {
    case $(uname -s) in
        Darwin)
            # macOS - try multiple methods
            local ssid=$(networksetup -getairportnetwork en0 2>/dev/null | cut -d ':' -f 2 | sed 's/^ *//')
            if [[ -n "$ssid" && "$ssid" != "You are not associated with an AirPort network." ]]; then
                echo "$ssid"
            else
                # Check if ethernet is connected
                if ifconfig en0 2>/dev/null | grep -q "status: active"; then
                    echo "Ethernet"
                else
                    echo "Offline"
                fi
            fi
            ;;
        Linux)
            local ssid=$(iwgetid -r 2>/dev/null)
            if [[ -n "$ssid" ]]; then
                echo "$ssid"
            else
                echo "Ethernet"
            fi
            ;;
        *)
            echo "N/A"
            ;;
    esac
}

get_ssid
