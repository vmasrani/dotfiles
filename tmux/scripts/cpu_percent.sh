#!/usr/bin/env bash
# CPU usage percentage for tmux status bar (fast, using ps)
set -euo pipefail

os=$(uname -s)
case "$os" in
  Darwin)
    cores=$(sysctl -n hw.ncpu) || { echo "cpu_percent: sysctl hw.ncpu failed" >&2; exit 1; }
    ;;
  Linux)
    cores=$(nproc)
    ;;
  *)
    echo "unsupported OS: $os" >&2
    exit 1
    ;;
esac

ps -A -o %cpu | awk -v c="$cores" 'NR>1{s+=$1}END{a=s/c; if(a>100)a=100; printf "%.0f%%", a}'
