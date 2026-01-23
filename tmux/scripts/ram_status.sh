#!/usr/bin/env bash
# Get RAM usage percentage for tmux status bar

get_ram() {
    case $(uname -s) in
        Darwin)
            # macOS - use vm_stat
            local pages_free=$(vm_stat | awk '/Pages free/ {print $3}' | tr -d '.')
            local pages_active=$(vm_stat | awk '/Pages active/ {print $3}' | tr -d '.')
            local pages_inactive=$(vm_stat | awk '/Pages inactive/ {print $3}' | tr -d '.')
            local pages_speculative=$(vm_stat | awk '/Pages speculative/ {print $3}' | tr -d '.')
            local pages_wired=$(vm_stat | awk '/Pages wired/ {print $4}' | tr -d '.')
            local pages_compressed=$(vm_stat | awk '/Pages occupied by compressor/ {print $5}' | tr -d '.')

            local total_pages=$((pages_free + pages_active + pages_inactive + pages_speculative + pages_wired + pages_compressed))
            local used_pages=$((pages_active + pages_wired + pages_compressed))

            if [[ $total_pages -gt 0 ]]; then
                local percent=$((used_pages * 100 / total_pages))
                echo "${percent}%"
            else
                echo "N/A"
            fi
            ;;
        Linux)
            free | awk '/Mem:/ {printf "%.0f%%", $3/$2 * 100}'
            ;;
        *)
            echo "N/A"
            ;;
    esac
}

get_ram
