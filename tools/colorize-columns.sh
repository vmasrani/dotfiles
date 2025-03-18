#!/bin/bash
awk '
{
    colors[1] = "\033[31m";  # Red
    colors[2] = "\033[32m";  # Green
    colors[3] = "\033[33m";  # Yellow
    colors[4] = "\033[34m";  # Blue
    colors[5] = "\033[35m";  # Magenta
    colors[6] = "\033[36m";  # Cyan
    colors[7] = "\033[91m";  # Light Red
    colors[8] = "\033[92m";  # Light Green
    colors[9] = "\033[93m";  # Light Yellow
    colors[10] = "\033[94m"; # Light Blue
    reset = "\033[0m";

    for (i = 1; i <= NF; i++) {
        printf "%s%s%s\t", colors[i], $i, reset;
    }
    print ""
}' | column -t
