#!/usr/bin/env bash
# CPU usage percentage for macOS status bar (fast, using ps)
cores=$(sysctl -n hw.ncpu 2>/dev/null || echo 1)
ps -A -o %cpu | awk -v c="$cores" 'NR>1{s+=$1}END{a=s/c; if(a>100)a=100; printf "%.0f%%", a}'
