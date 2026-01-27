#!/usr/bin/env bash
# Get GPU info for tmux status bar
# Uses nvidia-smi query mode for fast execution (~20ms vs ~300ms for full output)

get_gpu() {
    # Check if nvidia-smi exists
    if ! command -v nvidia-smi &>/dev/null; then
        echo "N/A"
        return
    fi

    # Query GPU count, memory used/total, and utilization in one call
    # Format: used_mb, total_mb, utilization_percent (one line per GPU)
    local gpu_data
    gpu_data=$(nvidia-smi --query-gpu=memory.used,memory.total,utilization.gpu \
        --format=csv,noheader,nounits 2>/dev/null)

    if [[ -z "$gpu_data" ]]; then
        echo "N/A"
        return
    fi

    # Count GPUs and sum memory
    local gpu_count=0
    local total_used_mb=0
    local total_mem_mb=0
    local total_util=0

    while IFS=', ' read -r used total util; do
        ((gpu_count++))
        total_used_mb=$((total_used_mb + used))
        total_mem_mb=$((total_mem_mb + total))
        total_util=$((total_util + util))
    done <<< "$gpu_data"

    if [[ $gpu_count -eq 0 ]]; then
        echo "N/A"
        return
    fi

    # Convert to GB
    local used_gb total_gb avg_util
    used_gb=$(awk "BEGIN {printf \"%.1f\", $total_used_mb / 1024}")
    total_gb=$(awk "BEGIN {printf \"%.0f\", $total_mem_mb / 1024}")
    avg_util=$((total_util / gpu_count))

    # Format: "2x 45%|12.5G/48G" or "45%|12.5G/48G" for single GPU
    if [[ $gpu_count -eq 1 ]]; then
        echo "${avg_util}%|${used_gb}G/${total_gb}G"
    else
        echo "${gpu_count}x ${avg_util}%|${used_gb}G/${total_gb}G"
    fi
}

get_gpu
