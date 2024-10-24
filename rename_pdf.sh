#!/bin/bash

set -e  # Exit immediately if a command exits with a non-zero status

# Source the necessary environment variables
source "$HOME/.secrets"
source "$HOME/.aliases-and-envs.zsh"
# Get the input filename from the first argument
input_filename="$1"
aichat --no-stream -r smartname "$input_filename" | tail -n 1
