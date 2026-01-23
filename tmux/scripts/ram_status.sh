#!/usr/bin/env bash
# Get RAM usage in used/total GB format for tmux status bar

get_ram() {
    case $(uname -s) in
        Darwin)
            # macOS - get total memory from sysctl
            local total_bytes
            total_bytes=$(sysctl -n hw.memsize)
            local total_gb
            total_gb=$(echo "scale=1; $total_bytes / 1073741824" | bc)

            # Get page size and calculate used memory from vm_stat
            local page_size
            page_size=$(pagesize)

            # Sum active + wired + compressed pages for "used" memory
            local used_gb
            used_gb=$(vm_stat | awk -v ps="$page_size" '
                /Pages active:/ { gsub(/\./, "", $3); active = $3 }
                /Pages wired down:/ { gsub(/\./, "", $4); wired = $4 }
                /Pages occupied by compressor:/ { gsub(/\./, "", $5); compressed = $5 }
                END { printf "%.1f", ((active + wired + compressed) * ps) / 1073741824 }
            ')

            echo "${used_gb}G/${total_gb}G"
            ;;
        Linux)
            # Linux - use /proc/meminfo
            awk '/MemTotal:/ { total = $2 }
                 /MemAvailable:/ { avail = $2 }
                 END {
                     used = total - avail
                     printf "%.1fG/%.1fG", used/1048576, total/1048576
                 }' /proc/meminfo
            ;;
        *)
            echo "N/A"
            ;;
    esac
}

get_ram
