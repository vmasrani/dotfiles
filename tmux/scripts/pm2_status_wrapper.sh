#!/usr/bin/env bash
# Wrapper script that adds dynamic background colors to PM2 status output
export LC_ALL=en_US.UTF-8

current_dir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Get PM2 status from the main script
pm2_output=$($current_dir/pm2_status.sh 2>/dev/null)

# Define colors
light_green="#C8F7DC"
light_pink="#FFE5F0"
dark_gray="#22223B"

# Check status and output with appropriate background color
if [[ "$pm2_output" == *"🟢"* ]]; then
    # All processes running - light green background
    echo "#[fg=${dark_gray},bg=${light_green}]${pm2_output}#[fg=${light_green}]"
else
    # Processes stopped or errored - light pink background
    echo "#[fg=${dark_gray},bg=${light_pink}]${pm2_output}#[fg=${light_pink}]"
fi
