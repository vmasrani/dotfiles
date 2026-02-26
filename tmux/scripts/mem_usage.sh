#!/usr/bin/env bash
# Memory usage (used/total) for macOS status bar
ps=$(sysctl -n hw.pagesize 2>/dev/null || echo 4096)
total=$(sysctl -n hw.memsize 2>/dev/null || echo 0)
vm_stat 2>/dev/null | awk -v ps="$ps" -v t="$total" '
  /Pages active:/{gsub(/\./,"",$3); a=$3+0}
  /Pages wired/{gsub(/\./,"",$4); w=$4+0}
  END{u=(a+w)*ps; printf "%.1fG/%.1fG", u/1073741824, t/1073741824}'
