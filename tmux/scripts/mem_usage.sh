#!/usr/bin/env bash
# Memory usage (used/total) for tmux status bar
set -euo pipefail

parse_meminfo() {
  local meminfo="${1:-/proc/meminfo}"
  awk '
    /^MemTotal:/{t=$2}
    /^MemAvailable:/{a=$2}
    END{u=t-a; printf "%.1fG/%.1fG", u/1048576, t/1048576}
  ' "$meminfo"
}

os=$(uname -s)
case "$os" in
  Darwin)
    pagesize=$(sysctl -n hw.pagesize) || { echo "mem_usage: sysctl hw.pagesize failed" >&2; exit 1; }
    total=$(sysctl -n hw.memsize) || { echo "mem_usage: sysctl hw.memsize failed" >&2; exit 1; }
    vm_stat | awk -v ps="$pagesize" -v t="$total" '
      /Pages active:/{gsub(/\./,"",$3); a=$3+0}
      /Pages wired/{gsub(/\./,"",$4); w=$4+0}
      END{u=(a+w)*ps; printf "%.1fG/%.1fG", u/1073741824, t/1073741824}'
    ;;
  Linux)
    parse_meminfo
    ;;
  *)
    echo "unsupported OS: $os" >&2
    exit 1
    ;;
esac
