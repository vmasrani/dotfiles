#!/usr/bin/env bash
# PM2 Process Status Monitor for tmux Dracula theme
export LC_ALL=en_US.UTF-8

current_dir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
source $current_dir/utils.sh

get_pm2_status() {
  # Check if pm2 is installed
  if ! command -v pm2 &> /dev/null; then
    echo "PM2 N/A"
    return
  fi

  # Check if jq is installed
  if ! command -v jq &> /dev/null; then
    echo "jq N/A"
    return
  fi

  # Get PM2 process list in JSON format
  local pm2_output
  pm2_output=$(pm2 jlist 2>/dev/null)

  # Check if pm2 jlist succeeded
  if [ $? -ne 0 ] || [ -z "$pm2_output" ] || [ "$pm2_output" = "[]" ]; then
    echo "0"
    return
  fi

  # Count processes by status
  local total online stopped errored
  total=$(echo "$pm2_output" | jq 'length' 2>/dev/null || echo "0")
  online=$(echo "$pm2_output" | jq '[.[] | select(.pm2_env.status == "online")] | length' 2>/dev/null || echo "0")
  stopped=$(echo "$pm2_output" | jq '[.[] | select(.pm2_env.status == "stopped")] | length' 2>/dev/null || echo "0")
  errored=$(echo "$pm2_output" | jq '[.[] | select(.pm2_env.status == "errored")] | length' 2>/dev/null || echo "0")

  # Determine color based on status
  local color_code
  if [ "$total" -eq 0 ]; then
    color_code="#[fg=#E07A7A]"  # Soft red for no processes
    echo "${color_code}0#[default]"
  elif [ "$errored" -gt 0 ] || [ "$stopped" -gt 0 ]; then
    color_code="#[fg=#E07A7A]"  # Soft red for issues
    if [ "$errored" -gt 0 ]; then
      echo "${color_code}${online}/${total} ⚠#[default]"
    else
      echo "${color_code}${online}/${total}#[default]"
    fi
  else
    color_code="#[fg=#7FC8A9]"  # Soft green for all running
    echo "${color_code}${online}#[default]"
  fi
}

main() {
  # Get configuration options
  RATE=$(get_tmux_option "@dracula-refresh-rate" 5)
  pm2_label=$(get_tmux_option "@dracula-pm2-status-label" "PM2")

  # Get raw status without color codes
  if ! command -v pm2 &> /dev/null || ! command -v jq &> /dev/null; then
    echo "$pm2_label N/A"
    sleep $RATE
    return
  fi

  local pm2_output
  pm2_output=$(pm2 jlist 2>/dev/null)

  if [ $? -ne 0 ] || [ -z "$pm2_output" ] || [ "$pm2_output" = "[]" ]; then
    echo "🔴 0"
    sleep $RATE
    return
  fi

  # Count processes by status
  local total online stopped errored
  total=$(echo "$pm2_output" | jq 'length' 2>/dev/null || echo "0")
  online=$(echo "$pm2_output" | jq '[.[] | select(.pm2_env.status == "online")] | length' 2>/dev/null || echo "0")
  stopped=$(echo "$pm2_output" | jq '[.[] | select(.pm2_env.status == "stopped")] | length' 2>/dev/null || echo "0")
  errored=$(echo "$pm2_output" | jq '[.[] | select(.pm2_env.status == "errored")] | length' 2>/dev/null || echo "0")

  # Output with emoji - color will be set by tmux config
  if [ "$total" -eq 0 ]; then
    echo "🔴 0"
  elif [ "$errored" -gt 0 ] || [ "$stopped" -gt 0 ]; then
    if [ "$errored" -gt 0 ]; then
      echo "🔴 ${online}/${total} ⚠"
    else
      echo "🔴 ${online}/${total}"
    fi
  else
    echo "🟢 ${online}"
  fi

  sleep $RATE
}

# run main driver
main
