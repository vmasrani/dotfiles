#!/usr/bin/env bash
# Claude Code Instance Monitor for tmux Dracula theme
export LC_ALL=en_US.UTF-8

main() {
  # Count running claude processes
  local count
  count=$(pgrep claude 2>/dev/null | wc -l | tr -d ' ')

  # If no instances, output empty string (widget will be hidden)
  if [ "$count" -eq 0 ]; then
    echo ""
    return
  fi

  # Output with icon and count
  echo "🦀 ${count}"
}

main
