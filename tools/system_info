#!/bin/bash

# Function to get GPU count
get_gpu_count() {
    if command -v nvidia-smi &> /dev/null; then
        nvidia-smi --query-gpu=gpu_name --format=csv,noheader | wc -l
    else
        echo "0"
    fi
}

# Function to get CPU info
get_cpu_info() {
    total_cores=$(nproc)
    # Get number of cores being used (load > 10%)
    active_cores=$(ps -eo pcpu | awk 'NR>1' | awk '$1 > 10' | wc -l)
    echo "${active_cores}/${total_cores}"
}

case "$1" in
    "gpu")
        gpu_count=$(get_gpu_count)
        if [ "$gpu_count" -eq "0" ]; then
            echo "󰢮 none"  # GPU icon + none
        else
            echo "󰢮 ${gpu_count}"  # GPU icon + count
        fi
        ;;
    "cpu")
        echo "󰻠 $(get_cpu_info)"  # CPU icon + active/total cores
        ;;
esac
